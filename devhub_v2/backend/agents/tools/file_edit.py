"""
FileEditTool — Surgical search/replace file editing.
Ported from Claude Code's FileEditTool architecture.

Key design decisions (from Claude Code):
- old_string must match EXACTLY ONE location in the file
- Empty old_string + non-existent file = create new file
- Empty old_string + existing file = error (ambiguous)
- Returns a unified diff preview of the change
- Preserves original encoding and line endings
"""

from __future__ import annotations

import difflib
from pathlib import Path

from .base_tool import BaseTool, ToolContext, ToolResult


class FileEditTool(BaseTool):
    name = "file_edit"
    description = (
        "Make a surgical edit to a file using exact string matching. "
        "Specify the exact text to find (old_string) and what to replace it with (new_string). "
        "The old_string must match EXACTLY ONE location in the file (including whitespace and indentation). "
        "To create a new file, provide an empty old_string with the file content as new_string. "
        "Always read the file first to get the exact content before editing."
    )
    read_only = False

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file within the workspace.",
                },
                "old_string": {
                    "type": "string",
                    "description": (
                        "The exact text to find and replace. Must match exactly one location. "
                        "Include enough context (surrounding lines) to make the match unique. "
                        "Use an empty string to create a new file."
                    ),
                },
                "new_string": {
                    "type": "string",
                    "description": "The replacement text. Use an empty string to delete the matched text.",
                },
            },
            "required": ["path", "old_string", "new_string"],
        }

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        rel_path = str(input_data.get("path") or "").strip()
        if not rel_path:
            return ToolResult(error="Parameter 'path' is required.")

        old_string = str(input_data.get("old_string", ""))
        new_string = str(input_data.get("new_string", ""))

        file_path = context.workspace_path / rel_path
        try:
            file_path.resolve().relative_to(context.workspace_path.resolve())
        except ValueError:
            return ToolResult(error="Access denied: path is outside the workspace.")

        # ── CREATE NEW FILE ──────────────────────────────────────────
        if not old_string:
            if file_path.exists():
                return ToolResult(
                    error=(
                        f"File already exists: {rel_path}. "
                        "To edit an existing file, provide a non-empty old_string. "
                        "Read the file first to find the exact text to replace."
                    )
                )
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(new_string, encoding="utf-8")
            except Exception as exc:
                return ToolResult(error=f"Failed to create file: {exc}")

            return ToolResult(
                output=f"Created new file: {rel_path} ({len(new_string)} characters)",
                files_modified=[rel_path],
                metadata={"action": "created"},
            )

        # ── EDIT EXISTING FILE ───────────────────────────────────────
        if not file_path.exists():
            return ToolResult(error=f"File not found: {rel_path}. Cannot search for old_string in a non-existent file.")
        if not file_path.is_file():
            return ToolResult(error=f"Not a file: {rel_path}")

        try:
            original = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return ToolResult(error=f"Failed to read file: {exc}")

        # Count occurrences
        count = original.count(old_string)
        if count == 0:
            # Provide helpful diagnostic
            snippet = old_string[:120].replace("\n", "\\n")
            return ToolResult(
                error=(
                    f"old_string not found in {rel_path}. "
                    f"The text '{snippet}' does not appear in the file. "
                    "Read the file first with file_read to get the exact content, "
                    "including correct indentation and whitespace."
                )
            )
        if count > 1:
            return ToolResult(
                error=(
                    f"old_string matches {count} locations in {rel_path}. "
                    "Include more surrounding context in old_string to make the match unique — "
                    "add a few lines before and after the target text."
                )
            )

        # Apply the replacement
        new_content = original.replace(old_string, new_string, 1)

        # Generate diff
        diff_text = _unified_diff(original, new_content, rel_path)

        try:
            file_path.write_text(new_content, encoding="utf-8")
        except Exception as exc:
            return ToolResult(error=f"Failed to write file: {exc}")

        action = "deleted_text" if not new_string else "edited"
        return ToolResult(
            output=f"Applied edit to {rel_path}:\n{diff_text}",
            files_modified=[rel_path],
            metadata={"action": action, "diff": diff_text},
        )


def _unified_diff(old: str, new: str, path: str, context_lines: int = 3) -> str:
    """Generate a compact unified diff between two strings."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=context_lines,
    )
    return "".join(diff)
