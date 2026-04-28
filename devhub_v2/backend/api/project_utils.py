import json
import logging
import re
from pathlib import Path

from django.db import OperationalError, ProgrammingError

from agents.core.base import normalize_ai_config
from agents.core.workspace import PROJECTS_DIR
from core.models import Project
from integrations.models import GitHubConnection, GitHubRepositoryLink

logger = logging.getLogger(__name__)

PIPELINE_STAGES = ['backlog', 'development', 'testing', 'code_review', 'staging']
DEVHUB_META_DIR = ".devhub"
PROJECT_MEMORY_FILE = "project-memory.md"
PROJECT_INSTRUCTIONS_FILE = "DEVHUB.md"
DEVHUB_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "devhub-settings.json"
MEMORY_DB_ERRORS = (OperationalError, ProgrammingError)

CHAT_ATTACHMENT_MAX_COUNT = 3
CHAT_ATTACHMENT_MAX_BYTES = 4 * 1024 * 1024
CHAT_ATTACHMENT_MAX_TOTAL_BYTES = 10 * 1024 * 1024
CHAT_ATTACHMENT_ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}


def _normalize_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def _managed_project_root(project: Project) -> Path:
    return PROJECTS_DIR / str(project.id)


def _normalize_tech_stack(raw_value) -> list[str]:
    if isinstance(raw_value, str):
        values = [item.strip() for item in raw_value.split(',')]
    elif isinstance(raw_value, list):
        values = [str(item).strip() for item in raw_value]
    else:
        values = []

    normalized = []
    seen = set()
    for value in values:
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _project_tokens(project: Project, *extra_parts: str) -> set[str]:
    tokens = set()
    for item in [*(project.tech_stack or []), project.name or "", project.description or "", *extra_parts]:
        for token in re.split(r'[\s,/+]+', str(item).strip().lower()):
            if token:
                tokens.add(token)
    return tokens


def _matches_any(tokens: set[str], values: set[str]) -> bool:
    return any(token in tokens for token in values)


def _project_intent_tokens(project: Project, *extra_parts: str) -> set[str]:
    tokens = set()
    for item in [project.name or "", project.description or "", *extra_parts]:
        for token in re.split(r'[\s,/+]+', str(item).strip().lower()):
            if token:
                tokens.add(token)
    return tokens


def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _prefers_backend_only_from_text(text: str) -> bool:
    lowered = str(text or "").lower()
    if not lowered:
        return False

    backend_only_hints = (
        "api only",
        "backend only",
        "rest api",
        "backend service",
        "python api",
        "fastapi api",
        "build an api",
        "api for",
    )
    interactive_hints = (
        "frontend",
        "react",
        "vite",
        "ui",
        "interface",
        "web app",
        "website",
        "screen",
        "page",
        "game",
        "canvas",
    )

    return _contains_any_phrase(lowered, backend_only_hints) and not _contains_any_phrase(lowered, interactive_hints)


def _wants_connected_fullstack_from_text(text: str) -> bool:
    lowered = str(text or "").lower()
    if not lowered or _prefers_backend_only_from_text(lowered):
        return False

    explicit_fullstack_hints = (
        "full stack",
        "full-stack",
        "fullstack",
        "frontend and backend",
        "backend and frontend",
        "frontend + backend",
        "backend + frontend",
    )
    persistence_hints = (
        "backend",
        "database",
        " db ",
        "db-backed",
        "db backed",
        "sqlite",
        "postgres",
        "postgresql",
        "mysql",
        "mongodb",
        "leaderboard",
        "score saving",
        "save scores",
        "scores",
        "auth",
        "login",
        "signup",
        "session",
        "persist",
        "persistence",
        "saved",
    )
    interactive_hints = (
        "frontend",
        "react",
        "vite",
        "ui",
        "interface",
        "web app",
        "website",
        "dashboard",
        "game",
        "snake",
        "canvas",
        "screen",
        "page",
        "player",
        "mobile app",
    )

    if _contains_any_phrase(lowered, explicit_fullstack_hints):
        return True

    return _contains_any_phrase(lowered, persistence_hints) and _contains_any_phrase(lowered, interactive_hints)


def _suggested_stack_from_text(idea: str, tech_stack: list[str] | None = None) -> list[str]:
    existing = _normalize_tech_stack(tech_stack or [])
    if existing:
        return existing

    text = str(idea or "").lower()
    if any(token in text for token in ("django", "manage.py", "admin panel", "django app")):
        return ["Django"]
    if any(token in text for token in ("vue", "nuxt")):
        return ["Vue", "Node.js"]
    if any(token in text for token in ("next.js", "nextjs", "next app")):
        return ["Next.js", "React", "Node.js"]
    if _wants_connected_fullstack_from_text(text):
        return ["React", "FastAPI"]
    if any(token in text for token in ("fastapi", "api", "backend", "python api")):
        return ["FastAPI"]
    if any(token in text for token in ("react", "vite", "frontend", "ui", "dashboard", "landing page", "web app", "app", "game", "snake")):
        return ["React"]
    return ["React"]


def _starter_app_kind(project: Project, starter_brief: str = "") -> str:
    tokens = _project_tokens(project, starter_brief)
    if _matches_any(tokens, {"calculator", "calc", "arithmetic"}):
        return "calculator"
    if _matches_any(tokens, {"expense", "budget", "finance", "financial", "invoice", "billing", "transaction"}):
        return "expense"
    if _matches_any(tokens, {"dashboard", "analytics", "metric", "metrics", "admin", "crm", "saas", "report", "reports"}):
        return "dashboard"
    return "planner"


def _project_slug(project: Project) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', (project.name or 'devhub-app').lower()).strip('-')
    return slug or 'devhub-app'


def _load_devhub_settings() -> dict:
    if not DEVHUB_SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(DEVHUB_SETTINGS_FILE.read_text(encoding='utf-8'))
    except Exception:
        logger.exception("Failed to load DevHub settings from %s", DEVHUB_SETTINGS_FILE)
        return {}


def _save_devhub_settings(settings: dict) -> None:
    DEVHUB_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEVHUB_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding='utf-8')


def _global_ai_config() -> dict:
    return normalize_ai_config((_load_devhub_settings().get("ai_config") or {}))


def _project_ai_config(project: Project | None = None) -> dict:
    return _global_ai_config()


def _upsert_project_github_link(project: Project, repository: dict, connection: GitHubConnection | None = None) -> None:
    owner = repository.get("owner") or {}
    GitHubRepositoryLink.objects.update_or_create(
        project=project,
        defaults={
            "connection": connection,
            "repository_id": repository.get("id"),
            "owner_login": str(owner.get("login") or ""),
            "repository_name": str(repository.get("name") or ""),
            "full_name": str(repository.get("full_name") or ""),
            "default_branch": str(repository.get("default_branch") or ""),
            "html_url": str(repository.get("html_url") or ""),
            "clone_url": str(repository.get("clone_url") or ""),
            "issues_url": str(repository.get("issues_url") or "").replace("{/number}", ""),
            "pulls_url": str(repository.get("pulls_url") or "").replace("{/number}", ""),
            "is_private": bool(repository.get("private")),
            "permissions": repository.get("permissions") or {},
            "raw_payload": repository,
        },
    )


def _github_integration_payload(project: Project) -> dict | None:
    try:
        link = GitHubRepositoryLink.objects.select_related("connection").filter(project=project).first()
    except MEMORY_DB_ERRORS:
        return None
    if not link:
        return None
    return {
        "connection_id": link.connection_id,
        "connection_login": link.connection.login if link.connection else "",
        "full_name": link.full_name,
        "owner_login": link.owner_login,
        "repository_name": link.repository_name,
        "default_branch": link.default_branch,
        "html_url": link.html_url,
        "private": link.is_private,
        "permissions": link.permissions or {},
    }


def _display_description(project: Project) -> str:
    return project.description or "A new runnable project created in DevHub."
