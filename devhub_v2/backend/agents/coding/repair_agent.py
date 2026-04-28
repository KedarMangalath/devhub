"""
RepairAgent: given real execution errors + the broken files, rewrites them.

This is not rule-based. It reads the actual error output (Python traceback,
TypeScript compiler error, npm stderr) and uses an LLM to fix the files.
"""
import json
import logging
import re
from pathlib import Path
from agents.core.base import BaseAgent
from agents.coding.stack_conventions import build_constraint_block

logger = logging.getLogger(__name__)


class RepairAgent(BaseAgent):

    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="Senior Debugging Engineer",
            system_instruction=(
                "You are an expert debugging engineer. You receive real error output from "
                "running code (Python tracebacks, TypeScript errors, npm build errors) and "
                "the source files that caused them. You fix the minimum number of files needed "
                "to make the code run correctly. "
                "You return ONLY a JSON array of fixed files — no explanations, no markdown. "
                "Each element: {\"path\": \"relative/path\", \"content\": \"complete fixed file content\"}. "
                "Rewrite the entire file, not just the diff. "
                "Do not change files that are not related to the reported errors."
            ),
            ai_config=ai_config,
        )

    def repair(
        self,
        errors: list[dict],
        all_files: dict[str, str],
        spec: dict,
        tech_stack: str,
        file_plan: list[dict],
    ) -> dict[str, str]:
        """
        errors: list of {phase, command, stderr, stdout, exit_code}
        all_files: {path: content} — all currently generated files
        Returns: {path: fixed_content} — only the files that changed
        """
        constraint_block = build_constraint_block(tech_stack)

        # Build error summary
        error_text = self._format_errors(errors)

        # Identify which files are likely broken from error messages
        implicated = self._implicate_files(errors, all_files)

        # Build context: broken files + their direct deps
        context_files = self._gather_context(implicated, all_files, file_plan)

        # Build file contracts from plan for the broken files
        contracts = {
            e["path"]: e.get("description", "") + "\nImports: " + str(e.get("exact_imports", []))
            for e in file_plan
            if e["path"] in implicated
        }

        files_section = "\n\n".join(
            f"### {path}\n```\n{content}\n```"
            for path, content in context_files.items()
        )

        contracts_section = "\n".join(
            f"{path}: {desc}" for path, desc in contracts.items()
        ) or "No specific contracts available."

        prompt = f"""Fix the following errors in this project.

{constraint_block}

## Errors encountered
{error_text}

## File contracts (what each file should do)
{contracts_section}

## Current file contents (files implicated in errors + their dependencies)
{files_section}

## Product context
Product: {spec.get('product_name', '')} — {spec.get('tagline', '')}
Auth: {spec.get('auth_model', 'none')}
Models: {', '.join(m['name'] for m in spec.get('data_models', []))}
Endpoints: {', '.join(e['method']+' '+e['path'] for e in spec.get('api_endpoints', []))}

## Your task
1. Read each error carefully — identify the exact line, file, and cause.
2. Fix ONLY the files needed to resolve ALL listed errors.
3. Do not change unrelated logic — minimal fixes only.
4. Ensure fixed imports match the constraint block (e.g., flat imports for FastAPI).
5. Rewrite the ENTIRE file content for each file you fix.

Return ONLY a JSON array:
[
  {{"path": "backend/main.py", "content": "...complete fixed content..."}},
  ...
]
"""
        raw = self.generate(prompt=prompt)
        changes = self._parse_changes(raw)

        result = {}
        for change in changes:
            path = change.get("path", "").strip()
            content = change.get("content", "")
            if path and content:
                result[path] = _strip_fences(content)

        logger.info("RepairAgent fixed %d files", len(result))
        return result

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _format_errors(self, errors: list[dict]) -> str:
        parts = []
        for e in errors:
            phase = e.get("phase", "unknown")
            cmd = e.get("command", "")
            stderr = (e.get("stderr") or "").strip()
            stdout = (e.get("stdout") or "").strip()
            exit_code = e.get("exit_code", -1)

            parts.append(f"### Phase: {phase} | Command: `{cmd}` | Exit: {exit_code}")
            if stderr:
                parts.append(f"STDERR:\n{stderr[:3000]}")
            if stdout and exit_code != 0:
                parts.append(f"STDOUT:\n{stdout[:1000]}")
        return "\n\n".join(parts) if parts else "No error details captured."

    def _implicate_files(self, errors: list[dict], all_files: dict[str, str]) -> set[str]:
        """Extract file paths mentioned in error messages."""
        implicated = set()
        all_paths = set(all_files.keys())

        combined = " ".join(
            (e.get("stderr") or "") + " " + (e.get("stdout") or "")
            for e in errors
        )

        # Look for file paths in error output
        for path in all_paths:
            fname = Path(path).name
            if fname in combined or path in combined:
                implicated.add(path)

        # Python traceback: File "backend/foo.py", line N
        for m in re.finditer(r'File ["\']([^"\']+\.py)["\']', combined):
            raw = m.group(1).replace("\\", "/")
            # match against known paths
            for p in all_paths:
                if p.endswith(raw) or raw.endswith(p.lstrip("./")):
                    implicated.add(p)

        # TypeScript error: src/lib/auth.tsx(116,1):
        for m in re.finditer(r'([\w/\\.-]+\.[jt]sx?)\(?\d+', combined):
            raw = m.group(1).replace("\\", "/").lstrip("./")
            for p in all_paths:
                if p.endswith(raw):
                    implicated.add(p)

        # ModuleNotFoundError: No module named 'X'
        for m in re.finditer(r"No module named '([^']+)'", combined):
            mod = m.group(1).replace(".", "/")
            for p in all_paths:
                if mod in p:
                    implicated.add(p)
            # Also implicate the importer (likely main.py or __init__)
            for p in all_paths:
                if "main.py" in p or "__init__.py" in p:
                    implicated.add(p)

        # ImportError in specific file
        for m in re.finditer(r'from (\S+) import', combined):
            mod = m.group(1).replace(".", "/")
            for p in all_paths:
                if mod in p:
                    implicated.add(p)

        # If nothing found, implicate main entry files
        if not implicated:
            for p in all_paths:
                if any(x in p for x in ("main.py", "app.py", "manage.py", "main.jsx", "App.jsx")):
                    implicated.add(p)

        return implicated

    def _gather_context(
        self,
        implicated: set[str],
        all_files: dict[str, str],
        file_plan: list[dict],
    ) -> dict[str, str]:
        """Gather broken files + their direct dependencies."""
        dep_map = {e["path"]: e.get("depends_on", []) for e in file_plan}

        context = {}
        for path in implicated:
            if path in all_files:
                context[path] = all_files[path]
            # add direct deps
            for dep in dep_map.get(path, []):
                if dep in all_files:
                    context[dep] = all_files[dep]

        # Cap total context size
        MAX_CHARS = 60_000
        total = 0
        trimmed = {}
        for path, content in context.items():
            if total + len(content) > MAX_CHARS:
                break
            trimmed[path] = content
            total += len(content)

        return trimmed

    def _parse_changes(self, raw: str) -> list[dict]:
        raw = raw.strip()
        # Strip markdown fences
        raw = re.sub(r'^```[a-zA-Z]*\n?', '', raw)
        raw = re.sub(r'```\s*$', '', raw.strip())
        raw = raw.strip()
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
        return []


def _strip_fences(content: str) -> str:
    content = content.strip()
    m = re.match(r'^```[a-zA-Z0-9]*\n([\s\S]*?)```\s*$', content)
    if m:
        return m.group(1)
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)
    return content
