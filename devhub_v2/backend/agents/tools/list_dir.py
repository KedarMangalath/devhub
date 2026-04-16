"""
ListDirTool — List directory contents in the workspace.
"""

from __future__ import annotations

import os

from agents.workspace import SKIP_DIRS

from .base_tool import BaseTool, ToolContext, ToolResult

MAX_ENTRIES = 500


class ListDirTool(BaseTool):
    name = "list_dir"
    description = (
        "List the contents of a directory in the workspace. "
        "Shows files and subdirectories with sizes. "
        "Automatically skips common non-essential directories like node_modules, .git, __pycache__, etc."
    )
    read_only = True

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the directory. Defaults to workspace root.",
                },
            },
            "required": [],
        }

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        rel_path = str(input_data.get("path") or "").strip() or "."
        target = context.workspace_path / rel_path

        try:
            target.resolve().relative_to(context.workspace_path.resolve())
        except ValueError:
            return ToolResult(error="Access denied: path is outside the workspace.")

        if not target.exists():
            return ToolResult(error=f"Directory not found: {rel_path}")
        if not target.is_dir():
            return ToolResult(error=f"Not a directory: {rel_path}")

        entries: list[str] = []
        try:
            for item in sorted(target.iterdir()):
                if len(entries) >= MAX_ENTRIES:
                    break
                name = item.name
                if item.is_dir():
                    if name in SKIP_DIRS:
                        entries.append(f"  {name}/  [skipped]")
                        continue
                    try:
                        child_count = sum(1 for _ in item.iterdir())
                    except PermissionError:
                        child_count = 0
                    entries.append(f"  {name}/  ({child_count} items)")
                else:
                    try:
                        size = item.stat().st_size
                        if size < 1024:
                            size_str = f"{size} B"
                        elif size < 1024 * 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        else:
                            size_str = f"{size / (1024 * 1024):.1f} MB"
                    except OSError:
                        size_str = "?"
                    entries.append(f"  {name}  ({size_str})")
        except PermissionError:
            return ToolResult(error=f"Permission denied: {rel_path}")

        if not entries:
            return ToolResult(output=f"Directory is empty: {rel_path}")

        display_path = rel_path if rel_path != "." else "(workspace root)"
        return ToolResult(
            output=f"{display_path}:\n" + "\n".join(entries),
            metadata={"entry_count": len(entries)},
        )
