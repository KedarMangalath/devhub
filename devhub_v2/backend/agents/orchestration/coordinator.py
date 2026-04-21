"""
Coordinator — Multi-agent orchestrator that can delegate tasks to workers.

Ported from Claude Code's coordinator/coordinatorMode.ts:
- Coordinator analyzes requests and decides whether to handle directly or delegate
- Workers execute sub-tasks with full tool access
- Read-only workers run in parallel, write workers run serially
- Coordinator synthesizes results (never lazy-delegates)

The coordinator itself has a QueryEngine with an extra tool: dispatch_worker.
"""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agents.core.base import normalize_ai_config
from agents.memory.store.compaction import ContextCompactor
from agents.customization.prompts import PromptBuilder
from agents.memory.store.query_engine import QueryEngine, QueryResult
from agents.tools.base_tool import BaseTool, ToolContext, ToolResult
from agents.tools.registry import ToolRegistry
from agents.orchestration.worker import Worker, WorkerResult

logger = logging.getLogger(__name__)


@dataclass
class CoordinatorResult:
    """Result from a coordinator run."""

    response: str = ""
    workers_spawned: list[dict] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    tool_calls_log: list[dict] = field(default_factory=list)
    total_turns: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


class DispatchWorkerTool(BaseTool):
    """
    Meta-tool that allows the coordinator to spawn worker agents.
    This tool is only available to the coordinator, not to workers.
    """

    name = "dispatch_worker"
    description = (
        "Spawn a worker agent to execute a sub-task. "
        "Use this for complex requests that benefit from breaking into independent sub-tasks. "
        "Each worker has full access to read files, edit files, search code, and run commands. "
        "Workers for read-only research can run in parallel. "
        "Workers that write files should be dispatched one at a time. "
        "Provide a detailed, self-contained prompt — workers cannot see the main conversation."
    )
    read_only = False

    def __init__(self, coordinator: "Coordinator"):
        self._coordinator = coordinator

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "Detailed, self-contained task description for the worker. "
                        "Include specific file paths, line numbers, and expected outcomes. "
                        "The worker cannot see the main conversation, so be thorough."
                    ),
                },
                "worker_type": {
                    "type": "string",
                    "description": "Type of worker: 'research' (read-only, can parallel), 'implement' (writes files, serial), or 'verify' (run tests/checks).",
                    "enum": ["research", "implement", "verify"],
                },
            },
            "required": ["task", "worker_type"],
        }

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        task = str(input_data.get("task") or "").strip()
        worker_type = str(input_data.get("worker_type") or "research").strip()

        if not task:
            return ToolResult(error="Parameter 'task' is required.")

        worker_id = f"worker-{uuid.uuid4().hex[:8]}"

        worker = Worker(
            worker_id=worker_id,
            task=task,
            workspace_id=context.workspace_id,
            workspace_path=context.workspace_path,
            ai_config=self._coordinator.ai_config,
            worker_type=worker_type,
            on_tool_start=self._coordinator._on_worker_tool_start,
            on_tool_end=self._coordinator._on_worker_tool_end,
        )

        # Notify coordinator of worker spawn
        self._coordinator._track_worker_spawn(worker_id, task, worker_type)

        # Execute the worker
        try:
            worker_result = worker.run(max_turns=15)
        except Exception as exc:
            logger.exception("Worker %s failed", worker_id)
            self._coordinator._track_worker_complete(worker_id, success=False, error=str(exc))
            return ToolResult(
                error=f"Worker {worker_id} failed: {exc}",
                metadata={"worker_id": worker_id, "worker_type": worker_type},
            )

        # Track completion
        self._coordinator._track_worker_complete(
            worker_id,
            success=worker_result.success,
            files_modified=worker_result.files_modified,
        )

        # Build result summary for the coordinator
        files_note = ""
        if worker_result.files_modified:
            files_note = f"\nFiles modified: {', '.join(worker_result.files_modified)}"

        tools_note = ""
        if worker_result.tool_calls_log:
            tools_used = [tc.get("tool", "") for tc in worker_result.tool_calls_log]
            tools_note = f"\nTools used: {', '.join(tools_used)}"

        return ToolResult(
            output=(
                f"Worker {worker_id} ({worker_type}) completed.\n"
                f"Result:\n{worker_result.response}"
                f"{files_note}{tools_note}"
            ),
            files_modified=worker_result.files_modified,
            files_read=worker_result.files_read,
            metadata={
                "worker_id": worker_id,
                "worker_type": worker_type,
                "turns_used": worker_result.turns_used,
            },
        )


class Coordinator:
    """
    Orchestrates multiple worker agents for complex tasks.

    The coordinator runs its own QueryEngine with an extra tool (dispatch_worker)
    that lets it spawn workers. For simple tasks, it handles them directly using
    the standard tools. For complex tasks, it delegates to workers.
    """

    def __init__(
        self,
        workspace_id: str,
        workspace_path: Path,
        ai_config: dict,
        on_event: Callable[[dict], None] | None = None,
    ):
        self.workspace_id = workspace_id
        self.workspace_path = workspace_path
        self.ai_config = normalize_ai_config(ai_config)
        self.on_event = on_event

        # Worker tracking
        self._workers: dict[str, dict] = {}
        self._lock = threading.Lock()

        # Build the coordinator's registry (standard tools + dispatch_worker)
        self.registry = ToolRegistry.default_registry()
        self.registry.register(DispatchWorkerTool(self))

        self.prompt_builder = PromptBuilder()
        self.compactor = ContextCompactor()

        self.engine = QueryEngine(
            tool_registry=self.registry,
            prompt_builder=self.prompt_builder,
            compactor=self.compactor,
            ai_config=self.ai_config,
            workspace_id=workspace_id,
            workspace_path=workspace_path,
            on_tool_start=self._on_coordinator_tool_start,
            on_tool_end=self._on_coordinator_tool_end,
        )

    def handle_request(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
        max_turns: int = 30,
    ) -> CoordinatorResult:
        """
        Main entry point. The coordinator decides whether to handle
        directly or delegate to workers.
        """
        system_prompt = self.prompt_builder.build_coordinator_prompt(
            workspace_path=self.workspace_path,
            tools=self.registry.all_tools(),
        )

        qr = self.engine.run(
            user_message=user_message,
            conversation_history=conversation_history,
            system_prompt=system_prompt,
            max_turns=max_turns,
        )

        # Collect all files modified (coordinator + workers)
        all_files_modified = list(qr.files_modified)
        for worker_info in self._workers.values():
            all_files_modified.extend(worker_info.get("files_modified", []))
        all_files_modified = list(dict.fromkeys(all_files_modified))

        return CoordinatorResult(
            response=qr.response,
            workers_spawned=[
                {
                    "worker_id": w_id,
                    "task": info.get("task", ""),
                    "type": info.get("type", ""),
                    "status": info.get("status", ""),
                    "files_modified": info.get("files_modified", []),
                }
                for w_id, info in self._workers.items()
            ],
            files_modified=all_files_modified,
            tool_calls_log=qr.tool_calls_log,
            total_turns=qr.turns_used,
            error=qr.error,
        )

    # ------------------------------------------------------------------
    # Internal tracking
    # ------------------------------------------------------------------

    def _emit(self, event: dict) -> None:
        """Send an event to the frontend via callback."""
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                logger.exception("Event callback failed")

    def _track_worker_spawn(self, worker_id: str, task: str, worker_type: str) -> None:
        with self._lock:
            self._workers[worker_id] = {
                "task": task,
                "type": worker_type,
                "status": "running",
                "files_modified": [],
            }
        self._emit({
            "type": "worker_spawned",
            "worker_id": worker_id,
            "task": task[:200],
            "worker_type": worker_type,
        })

    def _track_worker_complete(
        self,
        worker_id: str,
        success: bool = True,
        files_modified: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]["status"] = "completed" if success else "failed"
                self._workers[worker_id]["files_modified"] = files_modified or []
                if error:
                    self._workers[worker_id]["error"] = error
        self._emit({
            "type": "worker_completed",
            "worker_id": worker_id,
            "success": success,
            "files_modified": files_modified or [],
            "error": error,
        })

    def _on_coordinator_tool_start(self, name: str, args: dict) -> None:
        self._emit({
            "type": "tool_start",
            "agent": "coordinator",
            "tool": name,
            "args_preview": {k: str(v)[:100] for k, v in args.items()},
        })

    def _on_coordinator_tool_end(self, name: str, result: ToolResult) -> None:
        self._emit({
            "type": "tool_end",
            "agent": "coordinator",
            "tool": name,
            "success": result.success,
            "output_preview": (result.output or "")[:200],
        })

    def _on_worker_tool_start(self, worker_id: str, name: str, args: dict) -> None:
        self._emit({
            "type": "tool_start",
            "agent": worker_id,
            "tool": name,
            "args_preview": {k: str(v)[:100] for k, v in args.items()},
        })

    def _on_worker_tool_end(self, worker_id: str, name: str, result: ToolResult) -> None:
        self._emit({
            "type": "tool_end",
            "agent": worker_id,
            "tool": name,
            "success": result.success,
            "output_preview": (result.output or "")[:200],
        })
