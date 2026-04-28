import json
import logging
from pathlib import Path

from agents.core.base import ai_config_is_usable
from agents.coding.pipeline import ScaffoldPipeline
from agents.coding.scaffolder import ScaffolderAgent
from agents.coding.stack_conventions import get_conventions
from core.models import Project

from api.project_utils import (
    _display_description,
    _project_ai_config,
)

logger = logging.getLogger(__name__)


def _safe_files(files: dict) -> dict:
    sanitized = {}
    for raw_path, content in (files or {}).items():
        rel_path = Path(str(raw_path).replace("\\", "/"))
        if rel_path.is_absolute() or ".." in rel_path.parts:
            continue
        sanitized[str(rel_path).replace("\\", "/")] = str(content)
    return sanitized


def has_project_source_files(project_root: Path) -> bool:
    """Return True only when the workspace has real project files, ignoring DevHub metadata."""
    if not project_root.exists():
        return False
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(project_root).parts
        except ValueError:
            continue
        if not rel_parts or rel_parts[0] == ".devhub":
            continue
        return True
    return False


def build_scaffold_files(project: Project, starter_brief: str = "") -> dict:
    """Test/utility wrapper — returns {path: content} without writing to disk."""
    ai_config = _project_ai_config(project)
    if not ai_config_is_usable(ai_config):
        raise RuntimeError("No AI configuration is set up.")
    tech_stack = ", ".join(project.tech_stack or []) or "HTML, CSS, JavaScript"
    description = _display_description(project)
    brief = starter_brief or description
    full_desc = f"Build a complete, working application for: {project.name}. {brief}"

    try:
        pipeline = ScaffoldPipeline(ai_config=ai_config)
        result = pipeline.run(description=full_desc, tech_stack=tech_stack)
        files = _safe_files(result.get("files", {}))
        if files:
            return files
    except Exception as exc:
        logger.warning("Pipeline failed in build_scaffold_files (%s), falling back", exc)

    agent = ScaffolderAgent(ai_config=ai_config)
    raw = agent.generate_scaffold(description=full_desc, tech_stack=tech_stack)
    return _safe_files({
        item.get("path"): item.get("content")
        for item in raw.get("files", [])
        if isinstance(item, dict) and item.get("path") and item.get("content") is not None
    })


def scaffold_project(project: Project, project_root: Path, starter_brief: str = "", on_event=None) -> dict:
    project_root.mkdir(parents=True, exist_ok=True)
    if has_project_source_files(project_root):
        return {}

    ai_config = _project_ai_config(project)
    if not ai_config_is_usable(ai_config):
        raise RuntimeError(
            "No AI configuration is set up. Please configure an AI provider in Settings before creating a project."
        )

    tech_stack = ", ".join(project.tech_stack or []) or "HTML, CSS, JavaScript"
    description = _display_description(project)
    brief = starter_brief or description
    full_desc = f"Build a complete, working application for: {project.name}. {brief}"

    conventions = get_conventions(tech_stack)
    files: dict = {}
    spec: dict = {}
    file_plan: list = []

    # ── Multi-stage pipeline ─────────────────────────────────────────────────
    try:
        pipeline = ScaffoldPipeline(ai_config=ai_config, on_event=on_event)
        result = pipeline.run(
            description=full_desc,
            tech_stack=tech_stack,
            project_root=project_root,  # enables validation + repair loop
        )
        files = _safe_files(result.get("files", {}))
        spec = result.get("spec", {})
        file_plan = result.get("file_plan", [])
        logger.info("Pipeline completed: %d files", len(files))
    except Exception as exc:
        logger.warning("Pipeline failed (%s) — falling back to single-shot scaffolder", exc)
        files = {}

    # ── Single-shot fallback ─────────────────────────────────────────────────
    if not files:
        logger.info("Using ScaffolderAgent fallback")
        agent = ScaffolderAgent(ai_config=ai_config)
        raw = agent.generate_scaffold(description=full_desc, tech_stack=tech_stack)
        files = _safe_files({
            item.get("path"): item.get("content")
            for item in raw.get("files", [])
            if isinstance(item, dict) and item.get("path") and item.get("content") is not None
        })
        # Write fallback files (pipeline writes its own)
        for rel_path, content in files.items():
            target = project_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    if not files:
        raise RuntimeError(
            "The AI scaffolder did not return any files. Please try again or adjust the project description."
        )

    # ── Persist spec ─────────────────────────────────────────────────────────
    if spec:
        devhub_dir = project_root / ".devhub"
        devhub_dir.mkdir(exist_ok=True)
        (devhub_dir / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

    # ── Derive start URL and commands from conventions ────────────────────────
    start_url = f"http://localhost:{conventions.get('frontend_port', 5173)}"
    commands = []
    if conventions.get("install_frontend"):
        commands.append(conventions["install_frontend"])
    if conventions.get("install_backend"):
        commands.append(conventions["install_backend"])
    if conventions.get("backend_run"):
        commands.append(conventions["backend_run"])
    if conventions.get("frontend_run"):
        commands.append(conventions["frontend_run"])

    return {
        "files": list(files.keys()),
        "start_url": start_url,
        "commands": commands,
        "file_plan": file_plan,
    }
