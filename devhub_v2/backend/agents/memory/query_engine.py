"""
QueryEngine — Iterative tool-calling loop for the DevHub agentic system.

Ported from Claude Code's query.ts architecture:
- Multi-turn tool execution cycle
- Max-turn safety limits
- Auto-compaction when context grows too large
- Structured result tracking (files modified, tools called, token estimates)

Flow:
  1. Build system prompt → send to LLM with tool schemas
  2. If LLM returns functionCall → execute tools, append results, loop
  3. If LLM returns text (no tool calls) → done
  4. After each loop, check token count → auto-compact if needed
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agents.core.base import BaseAgent, build_multimodal_message_content, normalize_ai_config
from agents.memory.compaction import ContextCompactor
from agents.customization.prompts import PromptBuilder
from agents.tools.base_tool import ToolContext, ToolResult
from agents.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 25


@dataclass
class QueryResult:
    """Structured result from a full query-engine run."""

    response: str = ""
    tool_calls_log: list[dict] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    turns_used: int = 0
    compacted: bool = False
    total_duration_ms: int = 0
    error: str | None = None
    hit_turn_limit: bool = False

    @property
    def success(self) -> bool:
        return self.error is None


class QueryEngine:
    """
    Multi-turn tool-calling loop.

    The engine sends messages + tool schemas to the LLM. If the LLM responds
    with function calls, the engine executes them, appends results, and loops.
    This continues until the LLM responds with plain text or the turn limit
    is reached.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        prompt_builder: PromptBuilder,
        compactor: ContextCompactor,
        ai_config: dict,
        workspace_id: str = "",
        workspace_path: Path | None = None,
        on_tool_start: Callable[[str, dict], None] | None = None,
        on_tool_end: Callable[[str, ToolResult], None] | None = None,
    ):
        self.registry = tool_registry
        self.prompt_builder = prompt_builder
        self.compactor = compactor
        self.ai_config = normalize_ai_config(ai_config)
        self.workspace_id = workspace_id
        self.workspace_path = workspace_path or Path(".")
        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end

    def run(
        self,
        user_message: str,
        attachments: list[dict] | None = None,
        conversation_history: list[dict] | None = None,
        system_prompt: str = "",
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> QueryResult:
        """
        Execute the full query loop.

        Args:
            user_message: The user's input message.
            attachments: Optional image attachments for the current user turn.
            conversation_history: Previous conversation messages (optional).
            system_prompt: Override system prompt (if empty, PromptBuilder generates one).
            max_turns: Maximum tool-calling turns before forcing a text response.

        Returns:
            QueryResult with the final response and all tracking data.
        """
        start_time = time.time()
        result = QueryResult()

        # Build the agent
        if not system_prompt:
            system_prompt = self.prompt_builder.build_system_prompt(
                workspace_path=self.workspace_path,
                tools=self.registry.all_tools(),
            )

        agent = BaseAgent(
            role="DevHub Coding Agent",
            system_instruction=system_prompt,
            ai_config=self.ai_config,
        )

        # Build tool schemas for Gemini
        tools_payload = self.registry.to_gemini_tools()

        # Build the tool execution context
        tool_context = ToolContext(
            workspace_id=self.workspace_id,
            workspace_path=self.workspace_path,
        )

        # Build initial messages
        messages: list[dict] = []
        messages.append({"role": "system", "content": system_prompt})

        # Append conversation history
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "user")
                if role == "system":
                    continue  # Already have system prompt
                messages.append(msg)

        # Append the new user message
        messages.append({"role": "user", "content": build_multimodal_message_content(user_message, attachments)})

        # ── MAIN LOOP ────────────────────────────────────────────────
        for turn in range(max_turns):
            result.turns_used = turn + 1

            # Auto-compact if approaching context limit
            model_name = self.ai_config.get("model", "")
            if self.compactor.should_compact(messages, model_name):
                logger.info("Auto-compacting conversation at turn %d", turn)

                def _summarize(sys_prompt: str, text: str) -> str:
                    summarizer = BaseAgent(
                        role="Summarizer",
                        system_instruction=sys_prompt,
                        ai_config=self.ai_config,
                    )
                    return summarizer.generate(text)

                # Pass anchor_context if the compactor supports it (e.g.
                # _AnchorAwareCompactor used by BlueprintQueryAgent).
                anchor = getattr(self.compactor, "_anchor", None)
                messages = self.compactor.compact(
                    messages, model_name, _summarize,
                    **({"anchor_context": anchor} if anchor else {}),
                )
                result.compacted = True

            # Call LLM with tools
            try:
                llm_response = agent.complete_with_tools(messages, tools_payload)
            except Exception as exc:
                logger.exception("LLM call failed at turn %d", turn)
                result.error = f"LLM call failed: {exc}"
                break

            text = llm_response.get("text", "")
            tool_calls = llm_response.get("tool_calls", [])

            # ── NO TOOL CALLS → DONE ─────────────────────────────────
            if not tool_calls:
                result.response = text
                break

            # ── EXECUTE TOOL CALLS ────────────────────────────────────
            # Append the model's response (with tool calls) to conversation
            model_msg: dict = {"role": "model", "content": text, "tool_calls": tool_calls}
            model_parts = llm_response.get("model_parts")
            if isinstance(model_parts, list) and model_parts:
                model_msg["gemini_parts"] = model_parts
            messages.append(model_msg)

            # Execute each tool and collect results
            tool_results: list[dict] = []
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})

                # Callback: tool starting
                if self.on_tool_start:
                    try:
                        self.on_tool_start(tool_name, tool_args)
                    except Exception:
                        pass

                # Execute
                tool_result = self.registry.execute(tool_name, tool_args, tool_context)

                # Track
                log_entry = {
                    "tool": tool_name,
                    "args": _truncate_args(tool_args),
                    "success": tool_result.success,
                    "output_preview": (tool_result.output or "")[:200],
                    "error": tool_result.error,
                }
                result.tool_calls_log.append(log_entry)
                result.files_modified.extend(tool_result.files_modified)
                result.files_read.extend(tool_result.files_read)

                # Build the tool result message
                output_text = tool_result.output or ""
                if tool_result.error:
                    output_text = f"ERROR: {tool_result.error}\n{output_text}".strip()

                tool_results.append({
                    "name": tool_name,
                    "output": output_text[:15000],  # Cap tool output
                })

                # Callback: tool ended
                if self.on_tool_end:
                    try:
                        self.on_tool_end(tool_name, tool_result)
                    except Exception:
                        pass

            # Append tool results as a user message (Gemini format)
            results_msg: dict = {"role": "user", "content": "", "tool_results": tool_results}
            messages.append(results_msg)

        else:
            # Hit max turns
            result.hit_turn_limit = True
            result.response = (
                f"I've reached the maximum number of tool-calling turns ({max_turns}). "
                "Here's what I accomplished so far:\n\n"
                + _summarize_tool_log(result.tool_calls_log)
            )

        # Deduplicate file lists
        result.files_modified = list(dict.fromkeys(result.files_modified))
        result.files_read = list(dict.fromkeys(result.files_read))
        result.total_duration_ms = int((time.time() - start_time) * 1000)

        return result


def _truncate_args(args: dict, max_len: int = 200) -> dict:
    """Truncate arg values for logging (don't log full file contents)."""
    truncated = {}
    for key, value in args.items():
        s = str(value)
        truncated[key] = s[:max_len] + "…" if len(s) > max_len else s
    return truncated


def _summarize_tool_log(log: list[dict]) -> str:
    """Human-readable summary of tool calls made."""
    if not log:
        return "No tools were called."
    lines = []
    for entry in log:
        status = "✓" if entry.get("success") else "✗"
        tool = entry.get("tool", "unknown")
        preview = entry.get("output_preview", "")[:80]
        lines.append(f"  {status} {tool}: {preview}")
    return "\n".join(lines)
