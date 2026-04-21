"""
GlobTool - Find files matching glob patterns in the workspace.

Inspired by gemini-cli:
- recent files sorted first
- older files sorted alphabetically
- brace expansion support for patterns like '**/*.{ts,tsx}'
"""

from __future__ import annotations

import time
from pathlib import Path

from agents.core.workspace import SKIP_DIRS

from .base_tool import BaseTool, ToolContext, ToolResult, TOOL_RESULT_MAX_CHARS

MAX_RESULTS = 200
RECENCY_THRESHOLD_SECS = 3 * 24 * 3600


class GlobTool(BaseTool):
    name = "glob"
    description = (
        "Find files in the workspace matching a glob pattern. "
        "Use patterns like '**/*.py', '**/go.mod', or '**/*.{ts,tsx}'. "
        "Recently modified files appear first. Returns relative file paths."
    )
    read_only = True

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern, e.g. '**/*.py', '**/go.mod', '**/*.{ts,tsx}'.",
                },
                "path": {
                    "type": "string",
                    "description": "Optional subdirectory to search within. Defaults to workspace root.",
                },
            },
            "required": ["pattern"],
        }

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        pattern = str(input_data.get("pattern") or "").strip()
        if not pattern:
            return ToolResult(error="Parameter 'pattern' is required.")

        if context.budget is not None:
            over = context.budget.consume_search()
            if over:
                return ToolResult(error=over)

        sub_path = str(input_data.get("path") or "").strip()
        search_root = context.workspace_path
        if sub_path:
            search_root = context.workspace_path / sub_path
            try:
                search_root.resolve().relative_to(context.workspace_path.resolve())
            except ValueError:
                return ToolResult(error="Access denied: path is outside the workspace.")

        if not search_root.exists():
            return ToolResult(error=f"Path not found: {sub_path or '.'}")

        entries: list[tuple[str, float]] = []
        seen: set[str] = set()
        try:
            for expanded_pattern in _expand_braces(pattern):
                for match in search_root.glob(expanded_pattern):
                    if not match.is_file():
                        continue
                    rel = str(match.relative_to(context.workspace_path)).replace("\\", "/")
                    parts = rel.split("/")
                    if any(part in SKIP_DIRS for part in parts[:-1]):
                        continue
                    if rel in seen:
                        continue
                    seen.add(rel)
                    try:
                        mtime = match.stat().st_mtime
                    except OSError:
                        mtime = 0.0
                    entries.append((rel, mtime))
                    if len(entries) >= MAX_RESULTS:
                        break
                if len(entries) >= MAX_RESULTS:
                    break
        except Exception as exc:
            return ToolResult(error=f"Glob failed: {exc}")

        if not entries:
            return ToolResult(
                output=f"No files matched pattern '{pattern}'.",
                metadata={"match_count": 0},
            )

        results = _sort_entries(entries)
        truncated = f" (showing first {MAX_RESULTS})" if len(entries) >= MAX_RESULTS else ""
        full_output = f"Found {len(results)} files{truncated}:\n" + "\n".join(results)

        if len(full_output) > TOOL_RESULT_MAX_CHARS:
            full_output = full_output[:TOOL_RESULT_MAX_CHARS] + (
                f"\n[TRUNCATED - capped at {TOOL_RESULT_MAX_CHARS} chars]"
            )

        return ToolResult(output=full_output, metadata={"match_count": len(results)})


def _expand_braces(pattern: str) -> list[str]:
    import re

    match = re.search(r"\{([^{}]+)\}", pattern)
    if not match:
        return [pattern]

    options = [option.strip() for option in match.group(1).split(",") if option.strip()]
    if not options:
        return [pattern]

    prefix = pattern[:match.start()]
    suffix = pattern[match.end():]
    expanded: list[str] = []
    for option in options:
        expanded.extend(_expand_braces(prefix + option + suffix))
    return expanded


def _sort_entries(entries: list[tuple[str, float]]) -> list[str]:
    now = time.time()
    recent: list[tuple[str, float]] = []
    older: list[str] = []

    for rel, mtime in entries:
        if (now - mtime) < RECENCY_THRESHOLD_SECS:
            recent.append((rel, mtime))
        else:
            older.append(rel)

    recent.sort(key=lambda item: item[1], reverse=True)
    older.sort()
    return [item[0] for item in recent] + older
