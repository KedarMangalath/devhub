import logging
from pathlib import Path

from agents.core.base import ai_config_is_usable
from agents.coding.scaffolder import ScaffolderAgent
from core.models import Project

from api.project_utils import (
    _display_description,
    _project_ai_config,
    _project_tokens,
)

logger = logging.getLogger(__name__)


def _safe_scaffold_files(files: dict) -> dict:
    sanitized = {}
    for raw_path, content in (files or {}).items():
        rel_path = Path(str(raw_path).replace('\\', '/'))
        if rel_path.is_absolute() or '..' in rel_path.parts:
            continue
        sanitized[str(rel_path).replace('\\', '/')] = str(content)
    return sanitized


def build_scaffold_files(project: Project, starter_brief: str = "") -> dict:
    ai_config = _project_ai_config(project)
    if not ai_config_is_usable(ai_config):
        raise RuntimeError(
            "No AI configuration is set up. Please configure an AI provider in Settings before creating a project."
        )

    tech_stack = ", ".join(project.tech_stack or []) or "HTML, CSS, JavaScript"
    description = _display_description(project)

    agent = ScaffolderAgent(ai_config=ai_config)
    scaffold = agent.generate_scaffold(
        description=(
            f"Create a small but working application for {project.name}. "
            f"Description: {description}. "
            f"Original user brief: {starter_brief or description}. "
            "Generate the actual product the user asked for, not a canned landing page or placeholder marketing screen. "
            "If the selected stack spans frontend and backend, create connected frontend and backend folders, "
            "wire the UI to real backend endpoints, and keep the whole project runnable after setup. "
            "If the request mentions games, leaderboards, saved scores, auth, or persistence, include the real backend models/routes/storage "
            "and connect the frontend to them. "
            "Do not collapse browser app requests with backend requirements into a single static HTML page. "
            "Prefer replacing the main scaffold files with app-specific code instead of adding disconnected alternates."
        ),
        tech_stack=tech_stack,
    )

    files = _safe_scaffold_files({
        item.get('path'): item.get('content')
        for item in scaffold.get('files', [])
        if isinstance(item, dict) and item.get('path') and item.get('content') is not None
    })

    if not files:
        raise RuntimeError(
            "The AI scaffolder did not return any files. Please try again or adjust the project description."
        )

    return files


def scaffold_project(project: Project, project_root: Path, starter_brief: str = ""):
    project_root.mkdir(parents=True, exist_ok=True)
    if any(project_root.iterdir()):
        return

    files = build_scaffold_files(project, starter_brief=starter_brief)

    for rel_path, content in files.items():
        target = project_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
