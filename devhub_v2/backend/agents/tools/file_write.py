"""
FileWriteTool — Write full content to a new file.
Prefer FileEditTool for modifications to existing files.
"""

from __future__ import annotations

from .base_tool import BaseTool, ToolContext, ToolResult


class FileWriteTool(BaseTool):
    name = "file_write"
    description = (
        "Create a new file or completely overwrite an existing file with the provided content. "
        "For modifying existing files, prefer the file_edit tool which makes surgical changes. "
        "Use this tool only for creating brand new files or when you need to replace the entire file content."
    )
    read_only = False

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path for the file within the workspace.",
                },
                "content": {
                    "type": "string",
                    "description": "The complete file content to write.",
                },
            },
            "required": ["path", "content"],
        }

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        rel_path = str(input_data.get("path") or "").strip()
        content = str(input_data.get("content") or "")

        if not rel_path:
            return ToolResult(error="Parameter 'path' is required.")

        file_path = context.workspace_path / rel_path
        try:
            file_path.resolve().relative_to(context.workspace_path.resolve())
        except ValueError:
            return ToolResult(error="Access denied: path is outside the workspace.")

        existed = file_path.exists()
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        except Exception as exc:
            return ToolResult(error=f"Failed to write file: {exc}")

        action = "overwritten" if existed else "created"
        return ToolResult(
            output=f"File {action}: {rel_path} ({len(content)} characters)",
            files_modified=[rel_path],
            metadata={"action": action, "existed": existed},
        )
