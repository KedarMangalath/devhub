"""
FileReadTool - Read file contents with optional line ranges.

Inspired by Claude Code for numbered slices and by opencode for
"did you mean" suggestions on missing paths.
"""

from __future__ import annotations

from pathlib import Path

from agents.workspace import SKIP_DIRS

from .base_tool import BaseTool, ToolContext, ToolResult, TOOL_RESULT_MAX_CHARS


class FileReadTool(BaseTool):
    name = "file_read"
    description = (
        "Read the contents of a file from the workspace. "
        "You can optionally specify a line range to read only part of the file. "
        "Lines are 1-indexed. Output includes line numbers for reference. "
        "Use this tool to understand existing code before making edits."
    )
    read_only = True

    MAX_LINES = 2000

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file within the workspace.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read (1-indexed, inclusive).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to read (1-indexed, inclusive).",
                },
            },
            "required": ["path"],
        }

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        rel_path = str(input_data.get("path") or "").strip()
        if not rel_path:
            return ToolResult(error="Parameter 'path' is required.")

        if context.budget is not None:
            over = context.budget.consume_read()
            if over:
                return ToolResult(error=over)

        file_path = context.workspace_path / rel_path
        try:
            file_path.resolve().relative_to(context.workspace_path.resolve())
        except ValueError:
            return ToolResult(error="Access denied: path is outside the workspace.")

        if not file_path.exists():
            suggestion = _missing_path_suggestion(rel_path, context.workspace_path)
            if suggestion:
                return ToolResult(error=f"File not found: {rel_path}\n\nDid you mean one of these?\n{suggestion}")
            return ToolResult(error=f"File not found: {rel_path}")
        if not file_path.is_file():
            return ToolResult(error=f"Not a file: {rel_path}")

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return ToolResult(error=f"Failed to read file: {exc}")

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        start = max(1, int(input_data.get("start_line") or 1))
        end = min(total_lines, int(input_data.get("end_line") or total_lines))

        if start > total_lines:
            return ToolResult(
                output=(
                    f"File {rel_path} has {total_lines} lines. "
                    f"Requested start_line={start} is beyond the end."
                ),
                files_read=[rel_path],
            )

        selected = lines[start - 1 : end]
        if len(selected) > self.MAX_LINES:
            selected = selected[: self.MAX_LINES]
            end = start + self.MAX_LINES - 1

        numbered = [f"{line_no:>6}: {line.rstrip()}" for line_no, line in enumerate(selected, start=start)]
        header = f"File: {rel_path} ({total_lines} lines total, showing {start}-{end})"
        full_output = header + "\n" + "\n".join(numbered)

        truncation_note = ""
        if len(full_output) > TOOL_RESULT_MAX_CHARS:
            full_output = full_output[:TOOL_RESULT_MAX_CHARS]
            truncation_note = f"\n[TRUNCATED - output capped at {TOOL_RESULT_MAX_CHARS} chars]"

        return ToolResult(
            output=full_output + truncation_note,
            files_read=[rel_path],
            metadata={"total_lines": total_lines, "start": start, "end": end},
        )


def _missing_path_suggestion(rel_path: str, workspace_path: Path, limit: int = 3) -> str:
    target = Path(rel_path)
    base = target.name.lower()
    candidates: list[str] = []

    parent = workspace_path / target.parent
    if parent.exists() and parent.is_dir():
        for item in sorted(parent.iterdir()):
            name_lower = item.name.lower()
            if base in name_lower or name_lower in base:
                suggestion = str((target.parent / item.name).as_posix()).lstrip("./")
                candidates.append(suggestion)
            if len(candidates) >= limit:
                break

    if not candidates and base:
        for item in workspace_path.rglob("*"):
            if len(candidates) >= limit:
                break
            if not item.is_file():
                continue
            rel_candidate = str(item.relative_to(workspace_path)).replace("\\", "/")
            parent_parts = Path(rel_candidate).parts[:-1]
            if any(part in SKIP_DIRS for part in parent_parts):
                continue
            if any(part.startswith(".") and part != ".github" for part in parent_parts):
                continue
            if base in item.name.lower() or item.name.lower() in base:
                candidates.append(rel_candidate)

    return "\n".join(dict.fromkeys(candidates))
