"""Dependency healer: detect missing modules from runtime stderr, install them, restart.

Called when a runtime process has exited with an error. Scans the recent output
buffer for known missing-import signatures, maps them to PyPI/npm package names,
pip/npm installs, and schedules a restart. Rate-limited per workspace to prevent
infinite heal loops.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path


# Reuse the import->package mapping used by the auto-install script.
PY_MAPPINGS = {
    "dotenv": "python-dotenv", "cv2": "opencv-python", "PIL": "Pillow",
    "bs4": "beautifulsoup4", "yaml": "pyyaml", "dateutil": "python-dateutil",
    "github": "PyGithub", "jwt": "PyJWT", "skimage": "scikit-image",
    "sklearn": "scikit-learn", "Crypto": "pycryptodome", "serial": "pyserial",
    "attr": "attrs", "OpenGL": "PyOpenGL", "magic": "python-magic",
    "MySQLdb": "mysqlclient", "psycopg2": "psycopg2-binary",
    "django_extensions": "django-extensions",
    "rest_framework": "djangorestframework",
    "corsheaders": "django-cors-headers",
}

MAX_HEAL_ATTEMPTS = 3
HEAL_WINDOW_SECONDS = 300  # 5 min rolling window

_heal_attempts: dict[str, list[float]] = defaultdict(list)
_heal_lock = threading.Lock()


_PY_PATTERNS = [
    re.compile(r"ModuleNotFoundError: No module named ['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]"),
    re.compile(r"ImportError: No module named ['\"]?([a-zA-Z_][a-zA-Z0-9_]*)['\"]?"),
]
_NODE_PATTERNS = [
    re.compile(r"Cannot find module ['\"]([^'\"]+)['\"]"),
    re.compile(r"Error: Cannot find package ['\"]([^'\"]+)['\"]"),
]


def _register_attempt(workspace_id: str) -> bool:
    """Return True if another heal attempt is allowed."""
    now = time.time()
    with _heal_lock:
        attempts = _heal_attempts[workspace_id]
        attempts[:] = [t for t in attempts if now - t < HEAL_WINDOW_SECONDS]
        if len(attempts) >= MAX_HEAL_ATTEMPTS:
            return False
        attempts.append(now)
        return True


def detect_missing_python_module(output: str) -> str | None:
    for pattern in _PY_PATTERNS:
        match = pattern.search(output)
        if match:
            return match.group(1)
    return None


def detect_missing_node_module(output: str) -> str | None:
    for pattern in _NODE_PATTERNS:
        match = pattern.search(output)
        if match:
            name = match.group(1).strip()
            # Skip relative paths.
            if name.startswith(".") or name.startswith("/"):
                return None
            return name
    return None


def install_python_package(module_name: str, work_dir: str) -> tuple[bool, str]:
    package = PY_MAPPINGS.get(module_name, module_name)
    root = Path(work_dir)
    candidates = []
    if sys.platform == "win32":
        candidates.extend([
            root / ".venv" / "Scripts" / "python.exe",
            root / "venv" / "Scripts" / "python.exe",
        ])
    else:
        candidates.extend([
            root / ".venv" / "bin" / "python",
            root / "venv" / "bin" / "python",
        ])
    python_executable = next((str(candidate) for candidate in candidates if candidate.exists()), sys.executable)
    try:
        result = subprocess.run(
            [python_executable, "-m", "pip", "install", "--disable-pip-version-check", package],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0, (result.stdout + result.stderr)[-2000:]
    except Exception as exc:
        return False, str(exc)


def install_node_package(package_name: str, work_dir: str) -> tuple[bool, str]:
    # Pick the manager based on what lockfile is present; default to npm.
    root = Path(work_dir)
    if (root / "pnpm-lock.yaml").exists():
        cmd = ["pnpm", "add", package_name]
    elif (root / "yarn.lock").exists():
        cmd = ["yarn", "add", package_name]
    elif (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        cmd = ["bun", "add", package_name]
    else:
        cmd = ["npm", "install", package_name]
    try:
        result = subprocess.run(
            cmd, cwd=work_dir, capture_output=True, text=True, timeout=300, shell=False,
        )
        return result.returncode == 0, (result.stdout + result.stderr)[-2000:]
    except Exception as exc:
        return False, str(exc)


def try_heal_runtime(
    workspace_id: str,
    process_id: str,
    work_dir: str,
    recent_output: str,
    runtime_type: str | None = None,
    runtime_root: str | None = None,
) -> dict | None:
    """Try to heal a crashed runtime. Returns diagnostic dict or None if not healable."""
    py_mod = detect_missing_python_module(recent_output)
    node_mod = detect_missing_node_module(recent_output) if not py_mod else None

    if not py_mod and not node_mod:
        return None

    if not _register_attempt(workspace_id):
        return {
            "healed": False,
            "reason": "heal-rate-limit-exceeded",
            "module": py_mod or node_mod,
        }

    if py_mod:
        install_dir = runtime_root or work_dir
        ok, log = install_python_package(py_mod, install_dir)
        return {
            "healed": ok,
            "module": py_mod,
            "package": PY_MAPPINGS.get(py_mod, py_mod),
            "language": "python",
            "log_tail": log,
        }

    ok, log = install_node_package(node_mod, work_dir)
    return {
        "healed": ok,
        "module": node_mod,
        "package": node_mod,
        "language": "node",
        "log_tail": log,
    }
