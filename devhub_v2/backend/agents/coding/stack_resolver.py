"""
StackResolverAgent — derives a full conventions dict from any free-form tech_stack string.

Replaces the silent _DEFAULT_KEY fallback in get_conventions():
  1. Try the fast-path hardcoded convention lookup.
  2. If no match, call the LLM to derive correct conventions for this stack.
  3. Cache the result in .devhub/stack.json so downstream agents agree.

The output schema MUST match _CONVENTIONS entries in stack_conventions.py.
"""
from __future__ import annotations

import json
import logging
from agents.core.base import BaseAgent

logger = logging.getLogger(__name__)

# The schema every resolved conventions dict must satisfy
_REQUIRED_KEYS = {
    "label", "frontend_framework", "backend_framework",
    "frontend_dir", "backend_dir",
    "frontend_port", "backend_port",
    "frontend_entry", "backend_entry",
    "frontend_run", "backend_run",
    "install_frontend", "install_backend",
    "vite_proxy", "api_prefix", "import_style",
    "backend_import_note", "frontend_import_note",
    "file_extensions", "required_files",
    "package_json_scripts", "vite_version", "notes",
}

_CONVENTIONS_SCHEMA = """{
  "label": "short human-readable label, e.g. 'React + Vite + FastAPI'",
  "frontend_framework": "full framework description, e.g. 'React 18 with Vite 4, React Router v6, Tailwind CSS'",
  "backend_framework": "full backend description or null if none",
  "frontend_dir": "directory name for frontend code, e.g. 'frontend' or '.' for project root",
  "backend_dir": "directory name for backend code, e.g. 'backend' or null if none",
  "frontend_port": 5173,
  "backend_port": 8000,
  "frontend_entry": "e.g. 'frontend/src/main.jsx' or 'src/main.ts'",
  "backend_entry": "e.g. 'backend/main.py' or null",
  "frontend_run": "shell command to start frontend dev server, e.g. 'cd frontend && npm run dev'",
  "backend_run": "shell command to start backend, e.g. 'cd backend && uvicorn main:app --reload' or null",
  "install_frontend": "npm/yarn/pnpm install command, e.g. 'cd frontend && npm install'",
  "install_backend": "pip/poetry/npm install command or null",
  "startup_check_backend": "shell command that imports/checks backend startup, or null",
  "vite_proxy": true,
  "api_prefix": "/api/",
  "import_style": "flat | django_apps | frontend_mock | esm_modules",
  "backend_import_note": "critical import rule for backend files, or null",
  "frontend_import_note": "critical rule for frontend API calls, or null",
  "file_extensions": {"components": ".jsx", "pages": ".jsx", "hooks": ".js", "utils": ".js"},
  "required_files": ["list of files that MUST exist"],
  "package_json_scripts": {"dev": "...", "build": "..."},
  "vite_version": "^4.5.2 or null if not Vite",
  "notes": "any critical runtime or platform notes"
}"""


class StackResolverAgent(BaseAgent):
    """
    Derives full conventions for any tech_stack string.
    Falls through to LLM derivation when the stack is not in the hardcoded list.
    """

    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="DevOps Architect",
            system_instruction=(
                "You are a DevOps architect who knows the exact conventions, file layouts, "
                "port numbers, run commands, and import rules for any web framework combination. "
                "Given a tech stack description, produce a precise conventions object. "
                "Return ONLY valid JSON — no markdown, no explanation."
            ),
            ai_config=ai_config,
        )

    def resolve(self, tech_stack: str) -> dict:
        """
        Returns a full conventions dict for the given stack string.
        First checks the hardcoded registry; falls back to LLM derivation.
        """
        # Fast path — hardcoded registry
        from agents.coding.stack_conventions import detect_stack_key, _CONVENTIONS, _DEFAULT_KEY
        key = detect_stack_key(tech_stack)
        if key in _CONVENTIONS:
            logger.info("StackResolver: fast-path hit '%s' for '%s'", key, tech_stack)
            return _CONVENTIONS[key]

        # LLM derivation
        logger.info("StackResolver: LLM derivation for unknown stack '%s'", tech_stack)
        return self._derive_from_llm(tech_stack)

    def _derive_from_llm(self, tech_stack: str) -> dict:
        prompt = f"""Produce a precise conventions object for this tech stack:

Tech stack: {tech_stack}

Return a JSON object that EXACTLY matches this schema:
{_CONVENTIONS_SCHEMA}

Critical rules:
- frontend_framework: describe the exact framework, version, and key libraries
- vite_proxy: true ONLY if Vite is used as frontend AND there is a backend API
- import_style:
    "flat"          → Python FastAPI/Flask scripts in the same directory, import each other directly
    "django_apps"   → Django app structure with relative .models imports
    "frontend_mock" → frontend-only, no backend, no network calls
    "esm_modules"   → Node.js ESM or TypeScript project
- For Next.js: frontend_dir="frontend", NO vite_proxy, api_prefix uses full URL
- For Vite+React only: frontend_dir=".", backend_dir=null, vite_proxy=false
- For SvelteKit: frontend_dir=".", no separate backend unless specified
- For Node/Express backend: backend_dir="backend", backend_run uses "node" or "nodemon"
- For Python backend: install_backend includes pip install + migrations/seed
- required_files must list every file that a developer would expect to exist
- package_json_scripts must have at minimum "dev" and "build"
- vite_version: "^4.5.2" for Vite projects on Windows (NOT 5.x), null for others
- Notes must call out any platform-specific gotchas (Windows, port conflicts, etc.)

Return ONLY the JSON object."""

        try:
            raw = super().generate(prompt=prompt)
            resolved = self.parse_json(raw)
            return _validate_and_fill(resolved, tech_stack)
        except Exception as exc:
            logger.error("StackResolverAgent LLM failed: %s — using default", exc)
            from agents.coding.stack_conventions import _CONVENTIONS, _DEFAULT_KEY
            return _CONVENTIONS[_DEFAULT_KEY]


def _validate_and_fill(conventions: dict, tech_stack: str) -> dict:
    """Ensure all required keys exist; fill missing ones with sensible defaults."""
    s = tech_stack.lower()
    defaults = {
        "label": tech_stack,
        "frontend_framework": tech_stack,
        "backend_framework": None,
        "frontend_dir": "frontend",
        "backend_dir": None,
        "frontend_port": 3000,
        "backend_port": None,
        "frontend_entry": None,
        "backend_entry": None,
        "frontend_run": "npm run dev",
        "backend_run": None,
        "install_frontend": "npm install",
        "install_backend": None,
        "startup_check_backend": None,
        "syntax_check_backend": None,
        "vite_proxy": False,
        "api_prefix": "/api/",
        "import_style": "esm_modules",
        "backend_import_note": None,
        "frontend_import_note": None,
        "file_extensions": {"components": ".tsx", "pages": ".tsx", "hooks": ".ts", "utils": ".ts"},
        "required_files": [],
        "package_json_scripts": {"dev": "dev", "build": "build"},
        "vite_version": "^4.5.2" if "vite" in s else None,
        "notes": "",
    }
    for k, v in defaults.items():
        if k not in conventions:
            conventions[k] = v
    return conventions


def resolve_conventions(tech_stack: str, ai_config: dict | None = None) -> dict:
    """
    Public entry point. Try hardcoded registry first; LLM-derive if missing.
    Always returns a valid conventions dict.
    """
    from agents.coding.stack_conventions import detect_stack_key, _CONVENTIONS
    key = detect_stack_key(tech_stack)
    if key in _CONVENTIONS:
        return _CONVENTIONS[key]

    agent = StackResolverAgent(ai_config=ai_config)
    return agent.resolve(tech_stack)
