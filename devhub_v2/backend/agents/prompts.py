"""
PromptBuilder — Rich system prompts with git context, tool descriptions,
code quality rules, and project memory.

Ported from Claude Code's context.ts (git context injection) and the
detailed tool-specific prompt engineering embedded throughout the codebase.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from agents.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


IDENTITY_PROMPT = """\
You are DevHub, an expert AI coding assistant embedded in a development platform.
You help developers understand, modify, and extend codebases by reading files,
making surgical edits, searching code, running commands, and answering questions.

You have access to tools that let you interact with the workspace filesystem and
shell. Use them proactively to explore and understand the codebase before making changes.
"""

TOOL_USAGE_PROMPT = """\
## Tool Usage Rules

### Reading Before Writing
- ALWAYS read a file with file_read before editing it with file_edit.
- NEVER guess file contents — use grep or glob to find files first.
- When editing, use file_edit for focused patches and use file_write for brand new files or full-file rewrites after reading the existing file first.
- If a request needs a broad rewrite of a file, it is okay to replace the whole file with file_write after you have inspected the current contents.

### Surgical Editing (file_edit)
- Provide enough context in old_string to uniquely match the target location.
- Include surrounding lines if the target text appears more than once.
- Check indentation carefully — old_string must match exactly, including whitespace.
- After editing, consider reading the file again to verify the change was applied correctly.

### Searching (grep, glob)
- Use grep to find where functions, classes, variables, or strings are defined and used.
- Use glob to discover files: '**/*.py' for Python, '**/*.tsx' for React, etc.
- Search before asking — the codebase usually has the answer.

### Shell Commands (bash)
- Use bash for running tests, builds, installs, git operations, and verification.
- Keep commands focused and readable.
- Always check the exit code in the result.

### Code Quality
- Match the existing code style: indentation, naming conventions, patterns.
- Make the minimum change needed — don't refactor unrelated code.
- Don't add unnecessary comments or docstrings to existing code.
- Don't remove code that isn't related to the current task.
- Group logically related changes together.
- If the user asked for an implementation or fix, keep going until the code is actually changed or you can clearly explain the blocker.
"""

RESPONSE_RULES_PROMPT = """\
## Response Rules
- Be concise and technical. Skip unnecessary preamble.
- When you make changes, summarize what you did and which files were modified.
- When the user asked you to build, fix, or modify something, do not stop at analysis alone if the tools can carry out the change.
- If a task is ambiguous, ask for clarification rather than guessing.
- If you encounter an error, explain what happened and suggest a fix.
- When presenting code, use fenced code blocks with the language specified.
"""


class PromptBuilder:
    """Build rich system prompts by assembling identity, tools, git context, and project memory."""

    def build_system_prompt(
        self,
        workspace_path: Path | None = None,
        tools: list[BaseTool] | None = None,
        project_memory: str = "",
        project_instructions: str = "",
        customization_context: str = "",
    ) -> str:
        """
        Assemble the full system prompt from modular sections.

        Sections:
        1. Identity — who the agent is
        2. Tool usage rules — when/how to use each tool
        3. Response rules — output format expectations
        4. Git context — current branch, status, recent commits
        5. Project memory — from the memory system
        6. Project instructions — DEVHUB.md / custom instructions
        7. Customization — project-specific overrides
        """
        sections: list[str] = [IDENTITY_PROMPT.strip()]

        # Tool descriptions
        if tools:
            tool_desc = self._tool_descriptions(tools)
            sections.append(f"## Available Tools\n{tool_desc}")

        sections.append(TOOL_USAGE_PROMPT.strip())
        sections.append(RESPONSE_RULES_PROMPT.strip())

        # Git context
        if workspace_path:
            git_ctx = self._git_context(workspace_path)
            if git_ctx:
                sections.append(f"## Git Context\n{git_ctx}")

        # Project memory
        if project_memory:
            sections.append(f"## Project Memory\n{project_memory[:8000]}")

        # Project instructions (DEVHUB.md)
        if project_instructions:
            sections.append(f"## Project Instructions\n{project_instructions[:6000]}")

        # Custom overrides
        if customization_context:
            sections.append(f"## Project Customization\n{customization_context[:6000]}")

        return "\n\n".join(sections)

    def build_coordinator_prompt(
        self,
        workspace_path: Path | None = None,
        tools: list[BaseTool] | None = None,
    ) -> str:
        """System prompt for the coordinator agent."""
        base = self.build_system_prompt(workspace_path=workspace_path, tools=tools)
        coordinator_addendum = """\

## Coordinator Role
You are operating as a **coordinator** that can delegate tasks to worker agents.
Your job is to:
1. Analyze the user's request and break it into sub-tasks if needed.
2. Decide which tasks to run in parallel (research/read-only) vs serial (writes).
3. Use the `dispatch_worker` tool to spawn workers for complex sub-tasks.
4. Synthesize worker results into a coherent response.

**Key rules:**
- Do NOT just relay worker results verbatim. Understand them, then respond.
- Parallel workers are for research: reading files, searching code, exploring.
- Serial workers are for writes: editing files, running commands that modify state.
- If the task is simple, handle it directly without spawning workers.
- Always provide a final, synthesized answer to the user.
"""
        return base + coordinator_addendum

    def _tool_descriptions(self, tools: list[BaseTool]) -> str:
        """Generate a human-readable description of available tools."""
        lines: list[str] = []
        for tool in tools:
            mode = "read-only" if tool.read_only else "read-write"
            lines.append(f"- **{tool.name}** ({mode}): {tool.description}")
        return "\n".join(lines)

    def _git_context(self, workspace_path: Path) -> str:
        """Detect git repo and inject branch, status, and recent commits."""
        git_dir = workspace_path / ".git"
        if not git_dir.exists():
            return ""

        parts: list[str] = []

        # Branch
        branch = _git_command(workspace_path, ["git", "rev-parse", "--abbrev-ref", "HEAD"])
        if branch:
            parts.append(f"Branch: {branch}")

        # Status (short)
        status = _git_command(workspace_path, ["git", "status", "--short"])
        if status:
            truncated = "\n".join(status.splitlines()[:20])
            parts.append(f"Status:\n{truncated}")
        else:
            parts.append("Status: Clean working tree")

        # Recent commits (last 5)
        log = _git_command(
            workspace_path,
            ["git", "log", "--oneline", "-5", "--no-decorate"],
        )
        if log:
            parts.append(f"Recent commits:\n{log}")

        return "\n".join(parts) if parts else ""


def _git_command(cwd: Path, args: list[str], timeout: int = 5) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""
