"""
Base tool abstraction for the DevHub agentic system.
Ported from Claude Code's Tool.ts architecture: structured tool interface
with input schemas, validation, permission checks, and result typing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Hard cap on individual tool result size — mirrors Claude Code's 20KB limit.
# Prevents a single large file or grep result from blowing up the context window.
TOOL_RESULT_MAX_CHARS = 20_000


@dataclass
class ToolBudget:
    """
    Per-session tool call budget injected into ToolContext for blueprint
    generation.  Mirrors Claude Code's token-budget discipline: caps the
    total number of file reads and search calls so the exploration phase
    terminates predictably.

    When a budget is attached, tools return a budget-exhausted message
    instead of executing — this surfaces in the LLM's next turn as a
    signal to stop exploring and start generating.
    """

    max_reads: int = 30
    max_searches: int = 15  # glob + grep combined
    reads_used: int = 0
    searches_used: int = 0

    @classmethod
    def for_repo(cls, file_count: int) -> "ToolBudget":
        if file_count < 200:
            return cls(max_reads=20, max_searches=10)
        if file_count < 2000:
            return cls(max_reads=40, max_searches=20)
        if file_count < 5000:
            return cls(max_reads=55, max_searches=28)
        return cls(max_reads=70, max_searches=35)

    def consume_read(self) -> str | None:
        """Increment read counter. Returns over-budget error string or None."""
        if self.reads_used >= self.max_reads:
            return (
                f"[BUDGET] File-read budget exhausted "
                f"({self.max_reads} reads used). "
                "You have gathered enough evidence — generate the blueprint JSON now."
            )
        self.reads_used += 1
        return None

    def consume_search(self) -> str | None:
        """Increment search counter. Returns over-budget error string or None."""
        if self.searches_used >= self.max_searches:
            return (
                f"[BUDGET] Search budget exhausted "
                f"({self.max_searches} searches used). "
                "You have gathered enough evidence — generate the blueprint JSON now."
            )
        self.searches_used += 1
        return None

    @property
    def summary(self) -> str:
        return (
            f"reads={self.reads_used}/{self.max_reads} "
            f"searches={self.searches_used}/{self.max_searches}"
        )


@dataclass
class ToolContext:
    """Runtime context passed to every tool invocation."""

    workspace_id: str
    workspace_path: Path
    agent_id: str = ""
    budget: ToolBudget | None = None


@dataclass
class ToolResult:
    """Structured result returned by every tool call."""

    output: str = ""
    error: str | None = None
    files_read: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.error is None


class BaseTool:
    """
    Abstract base for all DevHub tools.

    Subclasses must set ``name``, ``description``, and implement
    ``input_schema()`` and ``call()``.
    """

    name: str = ""
    description: str = ""
    read_only: bool = True

    # ------------------------------------------------------------------
    # Subclass API
    # ------------------------------------------------------------------

    def input_schema(self) -> dict:
        """Return a JSON-Schema dict describing the tool's input parameters."""
        raise NotImplementedError

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        """Execute the tool and return a structured result."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def validate_input(self, input_data: dict) -> dict:
        """
        Basic validation.  Override for tool-specific checks.
        Returns the (possibly sanitized) input or raises ``ValueError``.
        """
        return dict(input_data or {})

    def is_safe(self, input_data: dict) -> bool:  # noqa: ARG002
        """Return *False* if the input would perform a destructive action."""
        return True

    def to_function_schema(self) -> dict:
        """
        Serialize this tool to the Gemini ``functionDeclarations`` format
        so it can be sent alongside a ``generateContent`` request.
        """
        schema = self.input_schema()

        # Gemini does not support the ``additionalProperties`` key.
        cleaned = _strip_unsupported_keys(schema)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": cleaned,
        }


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _strip_unsupported_keys(schema: dict) -> dict:
    """
    Recursively strip JSON-Schema keys that Gemini does not support
    (``additionalProperties``, ``default``, ``$schema``, …).
    """
    UNSUPPORTED = {"additionalProperties", "default", "$schema", "$id"}
    cleaned: dict = {}
    for key, value in schema.items():
        if key in UNSUPPORTED:
            continue
        if isinstance(value, dict):
            cleaned[key] = _strip_unsupported_keys(value)
        elif isinstance(value, list):
            cleaned[key] = [
                _strip_unsupported_keys(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned
