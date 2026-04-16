"""
ToolRegistry — Central registry that holds all tool instances and
serializes them to Gemini function-calling format.
"""

from __future__ import annotations

import logging
from typing import Any

from .base_tool import BaseTool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Register tools, list schemas for LLM, and dispatch execution."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("Tool must have a non-empty name.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    # ------------------------------------------------------------------
    # Gemini function-calling format
    # ------------------------------------------------------------------

    def to_gemini_tools(self) -> list[dict]:
        """
        Return the tools payload for Gemini's ``generateContent`` API.
        Format: ``[{"functionDeclarations": [...]}]``
        """
        declarations = [tool.to_function_schema() for tool in self._tools.values()]
        return [{"functionDeclarations": declarations}]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, name: str, input_data: dict, context: ToolContext) -> ToolResult:
        """Look up a tool by name and execute it."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(error=f"Unknown tool: {name}")

        try:
            validated = tool.validate_input(input_data)
        except (ValueError, TypeError) as exc:
            return ToolResult(error=f"Invalid input for {name}: {exc}")

        if not tool.is_safe(validated):
            return ToolResult(error=f"Tool {name} blocked this input for safety.")

        try:
            return tool.call(validated, context)
        except Exception as exc:
            logger.exception("Tool %s raised an exception", name)
            return ToolResult(error=f"Tool {name} failed: {exc}")

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def default_registry(cls) -> "ToolRegistry":
        """Create a registry pre-loaded with the standard DevHub tools."""
        from .bash_tool import BashTool
        from .file_edit import FileEditTool
        from .file_read import FileReadTool
        from .file_write import FileWriteTool
        from .glob_tool import GlobTool
        from .grep_tool import GrepTool
        from .list_dir import ListDirTool

        registry = cls()
        registry.register(FileReadTool())
        registry.register(FileEditTool())
        registry.register(FileWriteTool())
        registry.register(GrepTool())
        registry.register(GlobTool())
        registry.register(BashTool())
        registry.register(ListDirTool())
        return registry
