"""Auto-fix loop for runtime startup errors.

When a project crashes on startup, this module:
1. Classifies the error: installable-package missing (healer) vs code-level issue (agent)
2. For code issues: extracts the failing files from the traceback, invokes the CoderAgent,
   writes the fixes, then restarts the runtime.
3. Runs in a background thread so the HTTP response isn't blocked.

Rate-limited per workspace to avoid infinite fix loops.
"""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

# These patterns mean a package is simply not installed — the healer handles them.
_INSTALLABLE_PATTERNS = [
    re.compile(r"ModuleNotFoundError: No module named '([a-zA-Z_][a-zA-Z0-9_]*)'\s*$", re.MULTILINE),
]

# These patterns mean the code itself has wrong imports / API usage — agent must fix.
_CODE_ERROR_PATTERNS = [
    # dotted sub-module missing (package exists, sub-module moved/renamed)
    re.compile(r"ModuleNotFoundError: No module named '([a-zA-Z_][a-zA-Z0-9_]+\.[a-zA-Z0-9_.]+)'"),
    # cannot import name (API change)
    re.compile(r"ImportError: cannot import name '([^']+)' from '([^']+)'"),
    # attribute removed from module
    re.compile(r"AttributeError: module '([^']+)' has no attribute '([^']+)'"),
    # SyntaxError in project file
    re.compile(r"SyntaxError: "),
    # NameError in project file
    re.compile(r"NameError: name '([^']+)' is not defined"),
]

# Files that belong to installed packages (not the project itself) — skip these.
_VENV_PATH_MARKERS = [".venv", "site-packages", "dist-packages", "\\Lib\\", "/lib/python"]


def classify_error(error_text: str) -> str:
    """Return 'installable', 'code', or 'unknown'."""
    for pattern in _CODE_ERROR_PATTERNS:
        if pattern.search(error_text):
            return "code"
    for pattern in _INSTALLABLE_PATTERNS:
        if pattern.search(error_text):
            return "installable"
    return "unknown"


# ---------------------------------------------------------------------------
# Traceback file extraction
# ---------------------------------------------------------------------------

_FILE_LINE_RE = re.compile(r'File "([^"]+)", line \d+')


def extract_project_files_from_traceback(error_text: str, workspace_path: Path) -> list[dict]:
    """Return list of {path, content} for project files mentioned in the traceback."""
    workspace_str = str(workspace_path.resolve())
    seen: set[str] = set()
    results: list[dict] = []

    for match in _FILE_LINE_RE.finditer(error_text):
        abs_path = match.group(1).replace("\\", "/")

        # Skip venv / stdlib files.
        if any(marker.replace("\\", "/") in abs_path for marker in _VENV_PATH_MARKERS):
            continue

        path_obj = Path(abs_path.replace("/", "\\"))
        try:
            rel = path_obj.resolve().relative_to(Path(workspace_str))
        except ValueError:
            continue

        rel_str = rel.as_posix()
        if rel_str in seen or not path_obj.exists():
            continue
        seen.add(rel_str)

        try:
            content = path_obj.read_text(encoding="utf-8", errors="ignore")
            results.append({"path": rel_str, "content": content})
        except Exception:
            pass

    return results


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

MAX_AUTOFIX_ATTEMPTS = 3
AUTOFIX_WINDOW_SECONDS = 600

_autofix_attempts: dict[str, list[float]] = defaultdict(list)
_autofix_lock = threading.Lock()


def _can_attempt_fix(workspace_id: str) -> bool:
    now = time.time()
    with _autofix_lock:
        attempts = _autofix_attempts[workspace_id]
        attempts[:] = [t for t in attempts if now - t < AUTOFIX_WINDOW_SECONDS]
        if len(attempts) >= MAX_AUTOFIX_ATTEMPTS:
            return False
        attempts.append(now)
        return True


def reset_autofix_attempts(workspace_id: str) -> None:
    with _autofix_lock:
        _autofix_attempts.pop(workspace_id, None)


# ---------------------------------------------------------------------------
# Background auto-fix runner
# ---------------------------------------------------------------------------

_active_fixes: dict[str, bool] = {}
_active_fixes_lock = threading.Lock()


def is_autofix_running(workspace_id: str) -> bool:
    with _active_fixes_lock:
        return _active_fixes.get(workspace_id, False)


def run_autofix_background(
    workspace_id: str,
    workspace_path: Path,
    error_text: str,
    runtime_type: str,
    on_complete: Callable[[dict], None],
    on_event: Callable[[dict], None] | None = None,
) -> bool:
    """Start a background thread that invokes CoderAgent to fix the error.

    Returns True if a fix was started, False if rate-limited or already running.
    `on_complete` is called with a result dict when done.
    """
    if is_autofix_running(workspace_id):
        return False
    if not _can_attempt_fix(workspace_id):
        on_complete({"status": "rate_limited", "workspace_id": workspace_id})
        return False

    files_context = extract_project_files_from_traceback(error_text, workspace_path)
    if not files_context:
        on_complete({"status": "no_files_found", "workspace_id": workspace_id})
        return False

    with _active_fixes_lock:
        _active_fixes[workspace_id] = True

    def _run():
        try:
            from agents.coding.coder import CoderAgent
            agent = CoderAgent()
            result = agent.fix_runtime_error(
                workspace_id=workspace_id,
                error_text=error_text,
                files_context=files_context,
                runtime_type=runtime_type,
                on_event=on_event,
            )
            on_complete({**result, "workspace_id": workspace_id})
        except Exception as exc:
            on_complete({"status": "agent_error", "error": str(exc), "workspace_id": workspace_id})
        finally:
            with _active_fixes_lock:
                _active_fixes.pop(workspace_id, None)

    thread = threading.Thread(target=_run, daemon=True, name=f"autofix-{workspace_id[:8]}")
    thread.start()
    return True
