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
        env["PAGER"] = "cat"

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
