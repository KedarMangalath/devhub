"""
GrepTool - Search for text patterns across the workspace.

Inspired by gemini-cli and opencode:
- names_only mode for cheap discovery passes
- max_matches_per_file and total_max_matches caps
- auto-context when only a few matches are found
- recency-aware file ordering
- brace glob expansion for include filters like '*.{ts,tsx}'
"""

from __future__ import annotations

import fnmatch
import os
import re
import time
from pathlib import Path

from agents.core.workspace import SKIP_DIRS

from .base_tool import BaseTool, ToolContext, ToolResult, TOOL_RESULT_MAX_CHARS

DEFAULT_TOTAL_MAX_MATCHES = 200
DEFAULT_MAX_LINE_LENGTH = 400
AUTO_CONTEXT_THRESHOLD = 3
AUTO_CONTEXT_LINES_1 = 40
AUTO_CONTEXT_LINES_FEW = 10
RECENCY_THRESHOLD_SECS = 3 * 24 * 3600


class GrepTool(BaseTool):
    name = "grep"
    description = (
        "Search for a text pattern across files in the workspace. "
        "Returns matching lines with file paths and line numbers. "
        "Supports regex patterns. "
        "Use names_only=true for a fast discovery pass (returns file paths only). "
        "Use include to restrict results with globs like '*.go', 'src/**/*.ts', or '*.{ts,tsx}'. "
        "When only 1-3 matches are found, surrounding context lines are shown automatically."
    )
    read_only = True

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex or literal string).",
                },
                "path": {
                    "type": "string",
                    "description": "Optional subdirectory to search within. Defaults to workspace root.",
                },
                "include": {
                    "type": "string",
                    "description": "Optional file glob filter, e.g. '*.py', 'src/**/*.ts', '*.{ts,tsx}'.",
                },
                "names_only": {
                    "type": "boolean",
                    "description": "If true, return only file paths, not matched lines.",
                },
                "max_matches_per_file": {
                    "type": "integer",
                    "description": "Max matches to return per file. Useful for noisy files.",
                },
                "total_max_matches": {
                    "type": "integer",
                    "description": f"Max total matches to return (default: {DEFAULT_TOTAL_MAX_MATCHES}).",
                },
            },
            "required": ["pattern"],
        }

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        pattern_str = str(input_data.get("pattern") or "").strip()
        if not pattern_str:
            return ToolResult(error="Parameter 'pattern' is required.")

        if context.budget is not None:
            over = context.budget.consume_search()
            if over:
                return ToolResult(error=over)

        sub_path = str(input_data.get("path") or "").strip()
        include = str(input_data.get("include") or "").strip()
        names_only = bool(input_data.get("names_only", False))
        max_per_file = input_data.get("max_matches_per_file")
        if max_per_file is not None:
            max_per_file = int(max_per_file)
        total_max = int(input_data.get("total_max_matches") or DEFAULT_TOTAL_MAX_MATCHES)

        search_root = context.workspace_path
        if sub_path:
            search_root = context.workspace_path / sub_path
            try:
                search_root.resolve().relative_to(context.workspace_path.resolve())
            except ValueError:
                return ToolResult(error="Access denied: search path is outside the workspace.")

        if not search_root.exists():
            return ToolResult(error=f"Path not found: {sub_path or '.'}")

        try:
            regex = re.compile(
                pattern_str,
                re.IGNORECASE if pattern_str == pattern_str.lower() else 0,
            )
        except re.error as exc:
            return ToolResult(error=f"Invalid regex pattern: {exc}")

        include_patterns = _parse_include_patterns(include)

        matches_by_file: dict[str, list[tuple[int, str]]] = {}
        files_searched = 0
        total_found = 0

        for dirpath, dirnames, filenames in os.walk(search_root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

            for filename in sorted(filenames):
                file_path = os.path.join(dirpath, filename)
                rel = os.path.relpath(file_path, context.workspace_path).replace("\\", "/")
                if include_patterns and not _matches_include(rel, filename, include_patterns):
                    continue

                try:
                    file_matches: list[tuple[int, str]] = []
                    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                        files_searched += 1
                        for lineno, line in enumerate(fh, start=1):
                            if max_per_file and len(file_matches) >= max_per_file:
                                break
                            if total_found >= total_max:
                                break
                            if regex.search(line):
                                display_line = line.rstrip()
                                if len(display_line) > DEFAULT_MAX_LINE_LENGTH:
                                    display_line = display_line[:DEFAULT_MAX_LINE_LENGTH] + "..."
                                file_matches.append((lineno, display_line))
                                total_found += 1

                    if file_matches:
                        matches_by_file[rel] = file_matches
                except (OSError, UnicodeDecodeError):
                    continue

                if total_found >= total_max:
                    break

            if total_found >= total_max:
                break

        if not matches_by_file:
            return ToolResult(
                output=f"No matches found for '{pattern_str}' in {files_searched} files.",
                metadata={"files_searched": files_searched, "match_count": 0},
            )

        ordered_paths = _sort_paths_by_recency(matches_by_file.keys(), context.workspace_path)

        if names_only:
            out = f"Files matching '{pattern_str}' ({len(ordered_paths)} files):\n" + "\n".join(ordered_paths)
            if len(out) > TOOL_RESULT_MAX_CHARS:
                out = out[:TOOL_RESULT_MAX_CHARS] + "\n[TRUNCATED]"
            return ToolResult(
                output=out,
                metadata={"files_searched": files_searched, "match_count": len(ordered_paths)},
            )

        if total_found <= AUTO_CONTEXT_THRESHOLD:
            context_lines = AUTO_CONTEXT_LINES_1 if total_found == 1 else AUTO_CONTEXT_LINES_FEW
            matches_by_file = _enrich_with_context(matches_by_file, context.workspace_path, context_lines)

        lines_out: list[str] = []
        for rel_path in ordered_paths:
            file_matches = matches_by_file[rel_path]
            lines_out.append(f"\n{rel_path}:")
            for lineno, line_text in file_matches:
                lines_out.append(f"  {lineno}: {line_text}")

        truncated_note = f" (showing first {total_max})" if total_found >= total_max else ""
        header = (
            f"Found {total_found} matches{truncated_note} across "
            f"{len(matches_by_file)} files (searched {files_searched}):"
        )
        full_output = header + "\n".join(lines_out)

        if len(full_output) > TOOL_RESULT_MAX_CHARS:
            full_output = full_output[:TOOL_RESULT_MAX_CHARS] + (
                f"\n[TRUNCATED - capped at {TOOL_RESULT_MAX_CHARS} chars]"
            )

        return ToolResult(
            output=full_output,
            metadata={
                "files_searched": files_searched,
                "match_count": total_found,
                "files_matched": len(matches_by_file),
            },
        )


def _parse_include_patterns(include: str) -> list[str]:
    if not include:
        return []
    return [pattern.replace("\\", "/") for pattern in _expand_braces(include.strip())]


def _expand_braces(pattern: str) -> list[str]:
    match = re.search(r"\{([^{}]+)\}", pattern)
    if not match:
        return [pattern]

    options = [option.strip() for option in match.group(1).split(",") if option.strip()]
    if not options:
        return [pattern]

    expanded: list[str] = []
    prefix = pattern[:match.start()]
    suffix = pattern[match.end():]
    for option in options:
        expanded.extend(_expand_braces(prefix + option + suffix))
    return expanded


def _matches_include(rel_path: str, filename: str, include_patterns: list[str]) -> bool:
    rel_path = rel_path.replace("\\", "/")
    for pattern in include_patterns:
        pattern = pattern.replace("\\", "/")
        if "/" in pattern:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            continue
        if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def _sort_paths_by_recency(paths, workspace_path: Path) -> list[str]:
    now = time.time()
    recent: list[tuple[str, float]] = []
    older: list[str] = []

    for rel_path in paths:
        try:
            mtime = (workspace_path / rel_path).stat().st_mtime
        except OSError:
            mtime = 0.0
        if (now - mtime) < RECENCY_THRESHOLD_SECS:
            recent.append((rel_path, mtime))
        else:
            older.append(rel_path)

    recent.sort(key=lambda item: item[1], reverse=True)
    older.sort()
    return [item[0] for item in recent] + older


def _enrich_with_context(
    matches_by_file: dict[str, list[tuple[int, str]]],
    workspace_path: Path,
    context_lines: int,
) -> dict[str, list[tuple[int, str]]]:
    enriched: dict[str, list[tuple[int, str]]] = {}
    for rel_path, file_matches in matches_by_file.items():
        abs_path = workspace_path / rel_path
        try:
            all_lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            enriched[rel_path] = file_matches
            continue

        seen: set[int] = set()
        result: list[tuple[int, str]] = []
        match_linenos = {line_no for line_no, _ in file_matches}

        for match_lineno, _ in sorted(file_matches, key=lambda item: item[0]):
            start = max(1, match_lineno - context_lines)
            end = min(len(all_lines), match_lineno + context_lines)
            for line_no in range(start, end + 1):
                if line_no in seen:
                    continue
                prefix = "-> " if line_no in match_linenos else "   "
                result.append((line_no, prefix + all_lines[line_no - 1].rstrip()))
                seen.add(line_no)

        enriched[rel_path] = sorted(result, key=lambda item: item[0])

    return enriched
