"""
Worker — Sub-agent with its own QueryEngine and isolated conversation.
Used by the Coordinator to execute delegated tasks.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agents.compaction import ContextCompactor
from agents.prompts import PromptBuilder
from agents.query_engine import QueryEngine, QueryResult
from agents.tools.base_tool import ToolResult
from agents.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class WorkerResult:
    """Result from a worker execution."""

    worker_id: str = ""
    task: str = ""
    response: str = ""
    files_modified: list[str] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    tool_calls_log: list[dict] = field(default_factory=list)
    turns_used: int = 0
    success: bool = True
    error: str | None = None


class Worker:
    """
    A sub-agent that executes a self-contained task with full tool access.

    Each worker has its own QueryEngine and conversation history, so it
    can be continued with follow-up messages while preserving context.

    Ported from Claude Code's coordinator worker pattern:
    - Workers receive a detailed prompt from the coordinator
    - They have access to the full tool suite
    - They report structured results back
    - They can be continued with follow-up messages
    """

    def __init__(
        self,
        worker_id: str,
        task: str,
        workspace_id: str,
        workspace_path: Path,
        ai_config: dict,
        worker_type: str = "general",
        on_tool_start: Callable[[str, str, dict], None] | None = None,
        on_tool_end: Callable[[str, str, ToolResult], None] | None = None,
    ):
        self.worker_id = worker_id
        self.task = task
        self.worker_type = worker_type
        self.workspace_id = workspace_id
        self.workspace_path = workspace_path
        self.ai_config = ai_config
        self.conversation_history: list[dict] = []
        self._on_tool_start = on_tool_start
        self._on_tool_end = on_tool_end

        # Each worker gets its own engine
        self.registry = ToolRegistry.default_registry()
        self.prompt_builder = PromptBuilder()
        self.compactor = ContextCompactor()

        # Wrap callbacks to include worker_id
        def _tool_start(name: str, args: dict) -> None:
            if self._on_tool_start:
                self._on_tool_start(self.worker_id, name, args)

        def _tool_end(name: str, result: ToolResult) -> None:
            if self._on_tool_end:
                self._on_tool_end(self.worker_id, name, result)

        self.engine = QueryEngine(
            tool_registry=self.registry,
            prompt_builder=self.prompt_builder,
            compactor=self.compactor,
            ai_config=ai_config,
            workspace_id=workspace_id,
            workspace_path=workspace_path,
            on_tool_start=_tool_start,
            on_tool_end=_tool_end,
        )

    def run(self, prompt: str | None = None, max_turns: int = 20) -> WorkerResult:
        """Execute the worker's task."""
        message = prompt or self.task

        system_prompt = self.prompt_builder.build_system_prompt(
            workspace_path=self.workspace_path,
            tools=self.registry.all_tools(),
        )
        # Add worker-specific context
        system_prompt += f"\n\n## Worker Context\nYou are a worker agent executing a specific sub-task. Focus on this task and report your findings clearly.\nWorker ID: {self.worker_id}\nTask Type: {self.worker_type}\n"

        qr = self.engine.run(
            user_message=message,
            conversation_history=self.conversation_history,
            system_prompt=system_prompt,
            max_turns=max_turns,
        )

        # Update conversation history for continuation
        self.conversation_history.append({"role": "user", "content": message})
        self.conversation_history.append({"role": "model", "content": qr.response})

        return WorkerResult(
            worker_id=self.worker_id,
            task=self.task,
            response=qr.response,
            files_modified=qr.files_modified,
            files_read=qr.files_read,
            tool_calls_log=qr.tool_calls_log,
            turns_used=qr.turns_used,
            success=qr.success,
            error=qr.error,
        )

    def continue_with(self, message: str, max_turns: int = 15) -> WorkerResult:
        """Continue the worker with a follow-up message, preserving context."""
        return self.run(prompt=message, max_turns=max_turns)
