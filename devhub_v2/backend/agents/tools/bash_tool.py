"""
BashTool — Execute shell commands in the workspace sandbox.
Wraps the existing SandboxManager with safety checks ported from
Claude Code's BashTool: blocked patterns, timeout, output truncation.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from .base_tool import BaseTool, ToolContext, ToolResult

DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 120
MAX_OUTPUT = 10000

BLOCKED_PATTERNS = [
    re.compile(r"\brm\s+-rf\s+/\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=.*of=/dev/", re.IGNORECASE),
    re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\s+~", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\s+\*", re.IGNORECASE),
    re.compile(r":(){ :\|:& };:", re.IGNORECASE),  # fork bomb
]


def _inject_unix_tools(env: dict[str, str]) -> None:
    """Add Git for Windows Unix tools (grep, find, etc.) to PATH on Windows."""
    import shutil
    if shutil.which("grep"):
        return
    candidates = [
        r"C:\Program Files\Git\usr\bin",
        r"C:\Program Files (x86)\Git\usr\bin",
    ]
    for path in candidates:
        if Path(path).is_dir():
            env["PATH"] = f"{path}{os.pathsep}{env.get('PATH', os.environ.get('PATH', ''))}"
            break


def _project_virtualenv_env(work_dir: str) -> dict[str, str]:
    env_updates: dict[str, str] = {}
    workspace_root = Path(work_dir)
    runtime_root = workspace_root

    try:
        from api.workspace.runtime import detect_runtime  # noqa: PLC0415

        detected = detect_runtime(workspace_root)
        detected_root = detected.get("runtime_root")
        if detected_root:
            runtime_root = Path(detected_root)
    except Exception:
        runtime_root = workspace_root

    if os.name == "nt":
        candidates = [
            runtime_root / ".venv" / "Scripts",
            runtime_root / "venv" / "Scripts",
            workspace_root / ".venv" / "Scripts",
            workspace_root / "venv" / "Scripts",
        ]
    else:
        candidates = [
            runtime_root / ".venv" / "bin",
            runtime_root / "venv" / "bin",
            workspace_root / ".venv" / "bin",
            workspace_root / "venv" / "bin",
        ]

    bin_dir = next((candidate for candidate in candidates if candidate.exists()), None)
    if not bin_dir:
        return env_updates

    env_updates["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    env_updates["VIRTUAL_ENV"] = str(bin_dir.parent)
    return env_updates


class BashTool(BaseTool):
    name = "bash"
    description = (
        "Execute a shell command in the workspace directory. "
        "Use this for running tests, builds, installs, git commands, or any CLI operation. "
        "Commands run with a timeout (default 30s, max 120s). "
        "Output is truncated after 10000 characters. "
        "Destructive commands (rm -rf /, format, etc.) are blocked."
    )
    read_only = False

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (default {DEFAULT_TIMEOUT}, max {MAX_TIMEOUT}).",
                },
            },
            "required": ["command"],
        }

    def is_safe(self, input_data: dict) -> bool:
        command = str(input_data.get("command") or "")
        return not any(pattern.search(command) for pattern in BLOCKED_PATTERNS)

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        command = str(input_data.get("command") or "").strip()
        if not command:
            return ToolResult(error="Parameter 'command' is required.")

        timeout = min(int(input_data.get("timeout") or DEFAULT_TIMEOUT), MAX_TIMEOUT)

        if not self.is_safe(input_data):
            return ToolResult(error=f"Command blocked for safety: {command}")

        work_dir = str(context.workspace_path)
        env = os.environ.copy()
        env.pop("DJANGO_SETTINGS_MODULE", None)
        env["PAGER"] = "cat"
        env.update(_project_virtualenv_env(work_dir))
        if os.name == "nt":
            _inject_unix_tools(env)

        start = time.time()
        try:
            result = subprocess.run(
                command,
                cwd=work_dir,
                env=env,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = int((time.time() - start) * 1000)

            stdout = (result.stdout or "")[:MAX_OUTPUT]
            stderr = (result.stderr or "")[:MAX_OUTPUT]

            parts: list[str] = []
            if stdout.strip():
                parts.append(stdout.strip())
            if stderr.strip():
                parts.append(f"STDERR:\n{stderr.strip()}")

            output = "\n".join(parts) if parts else "(no output)"
            if result.returncode != 0:
                output = f"Exit code: {result.returncode}\n{output}"

            return ToolResult(
                output=output,
                error=None if result.returncode == 0 else f"Command exited with code {result.returncode}",
                metadata={
                    "exit_code": result.returncode,
                    "duration_ms": duration_ms,
                    "command": command,
                },
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                error=f"Command timed out after {timeout}s: {command}",
                metadata={"command": command, "timeout": timeout},
            )
        except Exception as exc:
            return ToolResult(error=f"Failed to execute command: {exc}")
