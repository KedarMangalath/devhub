"""
Context compaction — auto-summarize old conversation turns when
approaching the model's context window limit.

Ported from Claude Code's autoCompact.ts / compact.ts:
- Threshold-based trigger (80% of context window)
- Preserves recent turns and system prompt
- Uses LLM to generate a summary of older turns
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Approximate context-window sizes (input tokens)
CONTEXT_LIMITS: dict[str, int] = {
    "gemini-3.1-pro-preview": 1_048_576,
    "gemini-3.1-pro": 1_048_576,
    "gemini-2.0-flash": 1_048_576,
    "gemini-2.0-pro": 2_097_152,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "claude-3-5-sonnet-latest": 200_000,
}

# Trigger compaction when usage exceeds this fraction of the limit
COMPACT_THRESHOLD = 0.75

# Number of recent messages to always preserve (never summarized)
RESERVE_RECENT_MESSAGES = 8

# Chars-per-token approximation for fast estimation
CHARS_PER_TOKEN = 4

SUMMARY_SYSTEM_PROMPT = """\
You are a conversation summarizer for a coding assistant.
Summarize the following older conversation turns into a concise but information-dense summary.
Preserve:
  - Key decisions made
  - Files that were read, edited, or created and why
  - Important code patterns or architecture details discussed
  - Any errors encountered and how they were resolved
  - The user's stated goals and constraints
Omit:
  - Verbose tool output (just note which tools were called and what they found)
  - Repeated back-and-forth that led to the same conclusion
  - Full file contents (just note file names and key changes)
Return ONLY the summary text, no JSON wrapping."""


class ContextCompactor:
    """Manages automatic context compaction for the query engine."""

    def estimate_tokens(self, messages: list[dict]) -> int:
        """Fast, rough token estimate based on character count."""
        total_chars = 0
        for msg in messages:
            content = msg.get("content") or ""
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        total_chars += len(str(part.get("text", "")))
                    else:
                        total_chars += len(str(part))
            # Also count tool call content
            for tc in msg.get("tool_calls", []):
                total_chars += len(str(tc.get("args", {})))
        return max(1, total_chars // CHARS_PER_TOKEN)

    def context_limit(self, model: str) -> int:
        """Return the context-window size for a given model name."""
        model_lower = (model or "").lower().strip()
        for key, limit in CONTEXT_LIMITS.items():
            if key.lower() in model_lower or model_lower in key.lower():
                return limit
        return 128_000  # Conservative fallback

    def should_compact(self, messages: list[dict], model: str) -> bool:
        """Return True if estimated tokens exceed the threshold."""
        limit = self.context_limit(model)
        estimated = self.estimate_tokens(messages)
        return estimated > int(limit * COMPACT_THRESHOLD)

    def compact(
        self,
        messages: list[dict],
        model: str,
        generate_fn,
        anchor_context: str | None = None,
    ) -> list[dict]:
        """
        Compact the conversation by summarizing older messages.

        Mirrors Claude Code's post-compact cleanup: after summarising old turns,
        re-injects ``anchor_context`` (e.g. the blueprint compact_summary) so
        the agent retains codebase orientation across compaction boundaries.

        Args:
            messages: Full conversation history.
            model: Current model name (for context limit lookup).
            generate_fn: Callable(system_instruction: str, prompt: str) -> str
                         that calls the LLM to generate a summary.
            anchor_context: Optional text re-injected after compaction as a
                            system-level reminder (capped at 12 KB).

        Returns:
            A shorter list of messages with old turns replaced by a summary.
        """
        if len(messages) <= RESERVE_RECENT_MESSAGES + 1:
            return messages  # Nothing to compact

        # Split: system prompt (if any) | old messages | recent messages
        system_msgs: list[dict] = []
        conversation_msgs: list[dict] = list(messages)

        if conversation_msgs and conversation_msgs[0].get("role") == "system":
            system_msgs = [conversation_msgs[0]]
            conversation_msgs = conversation_msgs[1:]

        if len(conversation_msgs) <= RESERVE_RECENT_MESSAGES:
            return messages  # Nothing to compact

        old_messages = conversation_msgs[:-RESERVE_RECENT_MESSAGES]
        recent_messages = conversation_msgs[-RESERVE_RECENT_MESSAGES:]

        # Build the text to summarize
        summary_input = _format_messages_for_summary(old_messages)

        try:
            summary_text = generate_fn(SUMMARY_SYSTEM_PROMPT, summary_input)
            if not summary_text or not summary_text.strip():
                logger.warning("Compaction LLM returned empty summary; keeping original messages")
                return messages
        except Exception:
            logger.exception("Context compaction failed; keeping original messages")
            return messages

        # Build the compacted conversation
        summary_message = {
            "role": "user",
            "content": (
                "[CONVERSATION SUMMARY — The following is a summary of earlier turns "
                "that were compacted to save context space]\n\n"
                f"{summary_text.strip()}\n\n"
                "[END SUMMARY — Recent conversation continues below]"
            ),
        }
        summary_ack = {
            "role": "model",
            "content": (
                "Understood. I have the context from the summarized conversation above "
                "and will continue working with the recent messages below."
            ),
        }

        # Post-compact anchor re-injection — mirrors Claude Code's post-compact
        # cleanup where it restores the top files + skills into fresh context.
        # Here we re-inject the codebase compact_summary so the agent doesn't
        # lose orientation after a large exploration session is summarised.
        anchor_messages: list[dict] = []
        if anchor_context and anchor_context.strip():
            anchor_text = anchor_context.strip()[:12_000]
            anchor_messages = [
                {
                    "role": "user",
                    "content": (
                        "[POST-COMPACT ANCHOR — Codebase context restored after compaction]\n\n"
                        f"{anchor_text}\n\n"
                        "[END ANCHOR — Continue your exploration / generation task]"
                    ),
                },
                {
                    "role": "model",
                    "content": "Codebase context reloaded. Continuing.",
                },
            ]

        compacted = system_msgs + [summary_message, summary_ack] + anchor_messages + recent_messages
        old_tokens = self.estimate_tokens(messages)
        new_tokens = self.estimate_tokens(compacted)
        logger.info(
            "Context compacted: %d messages → %d messages, ~%d tokens → ~%d tokens",
            len(messages),
            len(compacted),
            old_tokens,
            new_tokens,
        )
        return compacted


def _format_messages_for_summary(messages: list[dict]) -> str:
    """Format a list of messages into a readable transcript for the summarizer."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    text_parts.append(str(part.get("text", "")))
                else:
                    text_parts.append(str(part))
            content = "\n".join(text_parts)

        # Truncate very long messages 
        if len(content) > 4000:
            content = content[:3800] + "\n... [truncated for summary]"

        label = "User" if role == "user" else "Assistant" if role in ("assistant", "model") else role.title()
        parts.append(f"### {label}\n{content}")

        # Include tool call info if present
        for tc in msg.get("tool_calls", []):
            tool_name = tc.get("name", "unknown_tool")
            parts.append(f"  [Called tool: {tool_name}]")

    return "\n\n".join(parts)
