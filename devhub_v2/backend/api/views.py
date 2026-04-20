import base64
import json
import hashlib
import html
import logging
import os
import posixpath
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from difflib import unified_diff
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError, close_old_connections
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from agents.base import ai_config_is_usable, describe_image_attachments, normalize_ai_config
from agents.checkpoints import create_workspace_checkpoint, delete_workspace_checkpoint, restore_workspace_checkpoint, snapshot_previous_contents
from agents.documentation import generate_codebase_reference_sync
from agents.memory import _file_summary, _query_requests_broad_listing, _query_requests_system_explanation, build_blueprint_context, build_memory_context, compress_recent_activity, index_semantic_memory, read_query_relevant_file_content, record_episode, retrieve_relevant_files, upsert_working_memory
from agents.project_customization import bootstrap_project_customization, build_implementation_customization_bundle, build_project_customization_summary, build_role_customization_addendum, build_role_prompt_context, implementation_request_text, list_project_prompt_overrides, list_project_skills, suggested_project_customization_files
from agents.workspace import PROJECTS_DIR, SKIP_DIRS, workspace_manager
from core.models import AgentRun, Changeset, ChatMessage, DocumentationRun, EpisodicMemory, Feature, FeatureApproval, FeatureHistory, FileDiff, Project, SemanticMemory, TestResult, WorkingMemory
from integrations.github import GitHubIntegrationError, clone_repository_with_token, get_user_repository, github_oauth_config
from integrations.models import GitHubConnection, GitHubRepositoryLink

PIPELINE_STAGES = ['backlog', 'development', 'testing', 'code_review', 'staging']
logger = logging.getLogger(__name__)
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


def _parse_json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body)


def _chat_attachment_data_parts(data_url: str) -> tuple[str, str]:
    value = str(data_url or "").strip()
    if not value.startswith("data:") or ";base64," not in value:
        raise ValueError("Attachments must be base64 data URLs.")
    header, encoded = value.split(",", 1)
    mime_type = str(header[5:].replace(";base64", "")).strip().lower()
    encoded = "".join(encoded.split())
    if not mime_type or not encoded:
        raise ValueError("Attachments must include a mime type and image data.")
    return mime_type, encoded


def _normalize_chat_attachments(raw_attachments) -> list[dict]:
    if raw_attachments in (None, ""):
        return []
    if not isinstance(raw_attachments, list):
        raise ValueError("attachments must be a list.")
    if len(raw_attachments) > CHAT_ATTACHMENT_MAX_COUNT:
        raise ValueError(f"You can attach up to {CHAT_ATTACHMENT_MAX_COUNT} images per message.")

    normalized: list[dict] = []
    total_bytes = 0

    for index, item in enumerate(raw_attachments, start=1):
        if not isinstance(item, dict):
            raise ValueError("Each attachment must be an object.")

        data_url = str(item.get("data_url") or item.get("dataUrl") or "").strip()
        mime_type, encoded = _chat_attachment_data_parts(data_url)
        if mime_type not in CHAT_ATTACHMENT_ALLOWED_MIME_TYPES:
            raise ValueError("Only PNG, JPEG, WEBP, and GIF images are supported.")

        try:
            binary = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("One of the attached images could not be decoded.") from exc

        size_bytes = len(binary)
        if size_bytes > CHAT_ATTACHMENT_MAX_BYTES:
            raise ValueError("Each attached image must be 4 MB or smaller.")

        total_bytes += size_bytes
        if total_bytes > CHAT_ATTACHMENT_MAX_TOTAL_BYTES:
            raise ValueError("The total attached image payload is too large for one message.")

        raw_name = str(item.get("name") or f"image-{index}").strip() or f"image-{index}"
        safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw_name)[:120].strip(" .") or f"image-{index}"
        normalized.append(
            {
                "name": safe_name,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "data_url": f"data:{mime_type};base64,{encoded}",
            }
        )

    return normalized


def _chat_request_text(content: str, attachments: list[dict] | None = None, *, include_attachment_inventory: bool = False) -> str:
    text = str(content or "").strip()
    if not text and attachments:
        text = "Please inspect the attached image and use it as the primary context for this request."
        if len(attachments) != 1:
            text = "Please inspect the attached images and use them as the primary context for this request."

    if include_attachment_inventory:
        attachment_summary = describe_image_attachments(attachments)
        if attachment_summary:
            text = f"{text}\n\n{attachment_summary}" if text else attachment_summary
    return text


def _chat_message_attachments(item: dict | None) -> list[dict]:
    metadata = {}
    if isinstance(item, dict):
        metadata = item if "attachments" in item else dict(item.get("metadata") or {})
    attachments = metadata.get("attachments")
    if not isinstance(attachments, list):
        return []
    return [attachment for attachment in attachments if isinstance(attachment, dict) and attachment.get("data_url")]


def _chat_checkpoint_review_payload(checkpoint: dict | None, *, source: str, chat_mode: str | None, undo_label: str = 'Undo') -> dict:
    payload = {
        'source': source,
        'chat_mode': chat_mode or 'auto',
    }
    if not checkpoint:
        return payload
    payload['checkpoint'] = {
        'id': str(checkpoint.get('id') or ''),
        'created_at': checkpoint.get('created_at'),
        'label': checkpoint.get('label'),
        'source': checkpoint.get('source'),
    }
    payload['undo'] = {
        'available': True,
        'checkpoint_id': str(checkpoint.get('id') or ''),
        'label': undo_label or 'Undo',
    }
    return payload


def _chat_undo_payload_from_review(changeset_id: str, ai_review: dict | None) -> dict | None:
    ai_review = dict(ai_review or {})
    undo = dict(ai_review.get('undo') or {})
    checkpoint = dict(ai_review.get('checkpoint') or {})
    checkpoint_id = str(undo.get('checkpoint_id') or checkpoint.get('id') or '').strip()
    if not checkpoint_id:
        return None
    return {
        'available': bool(undo.get('available')),
        'changeset_id': str(changeset_id),
        'checkpoint_id': checkpoint_id,
        'label': str(undo.get('label') or 'Undo'),
        'undone_at': undo.get('undone_at'),
        'restored_by_changeset_id': undo.get('restored_by_changeset_id'),
        'source': str(ai_review.get('source') or 'chat'),
    }


def _chat_changeset_trace_metadata(changeset: Changeset | None) -> dict:
    if not changeset:
        return {}
    payload = {'changeset_id': str(changeset.id)}
    undo = _chat_undo_payload_from_review(str(changeset.id), changeset.ai_review)
    if undo:
        payload['undo'] = undo
        payload['undo_available'] = bool(undo.get('available'))
    return payload


def _changeset_by_id(project: Project, changeset_id: str) -> Changeset | None:
    normalized = str(changeset_id or '').strip()
    if not normalized:
        return None
    try:
        return Changeset.objects.filter(project=project, id=normalized).first()
    except Exception:
        return None


def _mark_changeset_undone(changeset: Changeset, restoring_changeset: Changeset | None = None) -> None:
    review = dict(changeset.ai_review or {})
    undo = dict(review.get('undo') or {})
    undo.update({
        'available': False,
        'checkpoint_id': str(undo.get('checkpoint_id') or (review.get('checkpoint') or {}).get('id') or ''),
        'label': str(undo.get('label') or 'Undo'),
        'undone_at': timezone.now().isoformat(),
        'restored_by_changeset_id': str(restoring_changeset.id) if restoring_changeset else None,
    })
    review['undo'] = undo
    changeset.ai_review = review
    changeset.save(update_fields=['ai_review'])


def _normalize_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def _managed_project_root(project: Project) -> Path:
    return PROJECTS_DIR / str(project.id)


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
        return ["React", "FastAPI"]
    return ["React", "FastAPI"]


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


def _safe_scaffold_files(files: dict) -> dict:
    sanitized = {}
    for raw_path, content in (files or {}).items():
        rel_path = Path(str(raw_path).replace('\\', '/'))
        if rel_path.is_absolute() or '..' in rel_path.parts:
            continue
        sanitized[str(rel_path).replace('\\', '/')] = str(content)
    return sanitized


def _static_scaffold_files(project: Project) -> dict:
    title = project.name or "New Project"
    description = _display_description(project)

    return {
        "index.html": f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <link rel="stylesheet" href="./styles.css" />
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <p class="eyebrow">DevHub Starter</p>
        <h1>{title}</h1>
        <p class="hero-copy">{description}</p>
        <div class="actions">
          <button id="primary-action">Add a feature</button>
          <button id="secondary-action" class="secondary">Update the UI with chat</button>
        </div>
      </section>

      <section class="grid">
        <article class="card">
          <span class="label">Project Goal</span>
          <h2>Start from a working base</h2>
          <p>This skeleton is runnable immediately and ready for AI-driven edits.</p>
        </article>
        <article class="card">
          <span class="label">Workflow</span>
          <h2>Chat + features</h2>
          <p>Add functionality through feature planning or by asking DevHub to change code directly.</p>
        </article>
        <article class="card">
          <span class="label">Preview</span>
          <h2>See it live</h2>
          <p>Run the project and refresh the preview after each change.</p>
        </article>
      </section>

      <section class="status-card">
        <div class="status-copy">
          <span class="label">Live Status</span>
          <h2>Ready for your first iteration</h2>
          <p id="status-text">Use the feature pipeline or the embedded chat to evolve this starter into a real product.</p>
        </div>
        <div class="status-log" id="status-log"></div>
      </section>
    </main>
    <script type="module" src="./app.js"></script>
  </body>
</html>
""",
        "styles.css": """* { box-sizing: border-box; }
:root {
  --bg: #f4efe7;
  --surface: rgba(255, 255, 255, 0.86);
  --ink: #112033;
  --muted: #5d6b7f;
  --accent: #d4552d;
  --accent-soft: rgba(212, 85, 45, 0.12);
  --border: rgba(17, 32, 51, 0.12);
}
body {
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top right, rgba(212, 85, 45, 0.18), transparent 28%),
    radial-gradient(circle at left, rgba(17, 32, 51, 0.1), transparent 32%),
    linear-gradient(180deg, #fbf8f4 0%, var(--bg) 100%);
}
.shell {
  width: min(1120px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 40px 0 64px;
}
.hero,
.card,
.status-card {
  border-radius: 28px;
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: 0 24px 64px rgba(17, 32, 51, 0.08);
}
.hero {
  padding: 32px;
}
.eyebrow,
.label {
  display: inline-block;
  margin: 0 0 12px;
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
}
h1 {
  margin: 0;
  font-size: clamp(2.8rem, 7vw, 5rem);
  line-height: 0.94;
}
h2 {
  margin: 0;
  font-size: 1.25rem;
}
.hero-copy,
.card p,
.status-copy p {
  color: var(--muted);
  line-height: 1.6;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 24px;
}
button {
  border: 0;
  border-radius: 999px;
  padding: 12px 20px;
  font: inherit;
  cursor: pointer;
  background: var(--accent);
  color: white;
  box-shadow: 0 12px 24px rgba(212, 85, 45, 0.22);
}
button.secondary {
  background: var(--accent-soft);
  color: var(--ink);
  box-shadow: none;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin: 18px 0;
}
.card {
  padding: 22px;
}
.status-card {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 1fr);
  gap: 18px;
  padding: 24px;
}
.status-log {
  min-height: 180px;
  border-radius: 22px;
  background: #0f1726;
  color: #dbe6ff;
  padding: 18px;
  font-family: Consolas, monospace;
  white-space: pre-wrap;
}
@media (max-width: 720px) {
  .shell {
    width: min(100vw - 20px, 1120px);
    padding-top: 20px;
  }
  .hero,
  .card,
  .status-card {
    border-radius: 22px;
  }
  .hero {
    padding: 24px;
  }
  .status-card {
    grid-template-columns: 1fr;
  }
}
""",
        "app.js": """const statusText = document.getElementById('status-text');
const statusLog = document.getElementById('status-log');
const primaryAction = document.getElementById('primary-action');
const secondaryAction = document.getElementById('secondary-action');

function log(message) {
  const stamp = new Date().toLocaleTimeString();
  statusLog.textContent = `[${stamp}] ${message}\\n` + statusLog.textContent;
}

primaryAction.addEventListener('click', () => {
  statusText.textContent = 'Create a feature in DevHub and let the AI wire it into this project.';
  log('Feature workflow is ready. Add your first feature from the Features tab.');
});

secondaryAction.addEventListener('click', () => {
  statusText.textContent = 'Select a file in the workspace and ask DevHub to change the UI or behavior.';
  log('Embedded chat can now make code changes directly in this project.');
});

log('Skeleton application booted successfully.');
""",
        "README.md": f"""# {title}

{description}

## Run locally

```bash
python -m http.server 4173 --bind 127.0.0.1
```

Open [http://127.0.0.1:4173](http://127.0.0.1:4173).

## Next steps

- Add features through DevHub's feature flow.
- Use the embedded chat to modify UI and behavior directly.
- Refresh the live preview after each applied change.
""",
        ".gitignore": "__pycache__/\n*.pyc\nnode_modules/\ndist/\nbuild/\n",
    }


def _is_calculator_project(project: Project, starter_brief: str = "") -> bool:
    tokens = _project_tokens(project, starter_brief)
    return any(token in tokens for token in {"calculator", "calc", "arithmetic"})


def _react_calculator_app_source(title: str, description: str) -> str:
    return f"""import {{ useMemo, useState }} from 'react';

const BUTTON_ROWS = [
  ['C', 'DEL', '%', '÷'],
  ['7', '8', '9', '×'],
  ['4', '5', '6', '-'],
  ['1', '2', '3', '+'],
  ['+/-', '0', '.', '='],
  ['√', 'x²'],
];

const DISPLAY_OPERATORS = {{
  '/': '÷',
  '*': '×',
  '-': '−',
  '+': '+',
}};

function sanitizeExpression(value) {{
  return value
    .replace(/×/g, '*')
    .replace(/÷/g, '/')
    .replace(/−/g, '-')
    .replace(/[^0-9+\\-*/.() ]/g, '');
}}

function evaluateExpression(value) {{
  const sanitized = sanitizeExpression(value);
  if (!sanitized.trim()) return '0';
  if (!/^[0-9+\\-*/.() ]+$/.test(sanitized)) throw new Error('Invalid expression');
  const result = Function(`"use strict"; return (${{sanitized}})` )();
  if (!Number.isFinite(result)) throw new Error('Invalid result');
  return String(Number(result.toFixed(10)));
}}

function applyUnary(value, transform) {{
  const result = transform(Number(evaluateExpression(value)));
  if (!Number.isFinite(result)) throw new Error('Invalid result');
  return String(Number(result.toFixed(10)));
}}

function prettify(value) {{
  return value.replace(/[/*\\-+]/g, (symbol) => DISPLAY_OPERATORS[symbol] || symbol);
}}

export default function App() {{
  const [expression, setExpression] = useState('0');
  const [history, setHistory] = useState([
    'Tap numbers and operators to start calculating.',
    'Use √, x², %, and +/- for quick utility actions.',
  ]);
  const [solved, setSolved] = useState(false);

  const livePreview = useMemo(() => prettify(expression), [expression]);

  const updateHistory = (entry) => {{
    setHistory((current) => [entry, ...current].slice(0, 6));
  }};

  const onPress = (value) => {{
    if (/^[0-9]$/.test(value)) {{
      setExpression((current) => (current === '0' || solved ? value : current + value));
      setSolved(false);
      return;
    }}

    if (value === '.') {{
      setExpression((current) => (solved ? '0.' : current.includes('.') ? current : current + '.'));
      setSolved(false);
      return;
    }}

    if (value === 'C') {{
      setExpression('0');
      setSolved(false);
      updateHistory('Calculator reset.');
      return;
    }}

    if (value === 'DEL') {{
      setExpression((current) => {{
        const next = solved ? '0' : current.slice(0, -1);
        return next || '0';
      }});
      setSolved(false);
      return;
    }}

    if (value === '+/-') {{
      try {{
        setExpression((current) => String(Number(evaluateExpression(current)) * -1));
        setSolved(false);
      }} catch {{
        updateHistory('Could not toggle the current value.');
      }}
      return;
    }}

    if (value === '%') {{
      try {{
        setExpression((current) => applyUnary(current, (number) => number / 100));
        setSolved(false);
      }} catch {{
        updateHistory('Could not convert the value to a percentage.');
      }}
      return;
    }}

    if (value === '√') {{
      try {{
        setExpression((current) => applyUnary(current, (number) => Math.sqrt(number)));
        setSolved(true);
        updateHistory('Square root applied.');
      }} catch {{
        updateHistory('Square root is only available for valid positive values.');
      }}
      return;
    }}

    if (value === 'x²') {{
      try {{
        setExpression((current) => applyUnary(current, (number) => number ** 2));
        setSolved(true);
        updateHistory('Squared the current value.');
      }} catch {{
        updateHistory('Could not square the current value.');
      }}
      return;
    }}

    if (value === '=') {{
      try {{
        const result = evaluateExpression(expression);
        updateHistory(`${{prettify(expression)}} = ${{result}}`);
        setExpression(result);
        setSolved(true);
      }} catch {{
        updateHistory('That expression could not be evaluated.');
        setExpression('0');
        setSolved(false);
      }}
      return;
    }}

    setExpression((current) => {{
      const next = solved ? `${{current}}${{value}}` : current;
      if (/[+\\-*/]$/.test(next)) return next.slice(0, -1) + value;
      return `${{next}}${{value}}`;
    }});
    setSolved(false);
  }};

  return (
    <main className="calculator-shell">
      <section className="calculator-frame">
        <div className="hero-copy">
          <span className="eyebrow">Working Calculator</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>

        <section className="calculator-panel">
          <div className="display-panel">
            <div className="display-meta">
              <span>Live expression</span>
              <span className="status-pill">{{solved ? 'Solved' : 'Editing'}}</span>
            </div>
            <div className="expression-preview">{{livePreview}}</div>
            <div className="display-value">{{prettify(expression)}}</div>
          </div>

          <div className="button-grid">
            {{BUTTON_ROWS.flat().map((button) => (
              <button
                key={{button}}
                type="button"
                onClick={{() => onPress(button)}}
                className={{`calc-button ${{button === '=' ? 'accent' : ''}} ${{['÷', '×', '-', '+'].includes(button) ? 'operator' : ''}} ${{['C', 'DEL'].includes(button) ? 'utility' : ''}} ${{button === '0' ? 'wide' : ''}}`}}
              >
                {{button}}
              </button>
            ))}}
          </div>
        </section>

        <aside className="history-panel">
          <div>
            <span className="eyebrow">Recent Activity</span>
            <h2>History</h2>
          </div>
          <div className="history-list">
            {{history.map((entry, index) => (
              <div key={{`${{entry}}-${{index}}`}} className="history-item">{{entry}}</div>
            ))}}
          </div>
        </aside>
      </section>
    </main>
  );
}}
"""


def _react_calculator_styles_source() -> str:
    return """* {
  box-sizing: border-box;
}

:root {
  color: #0f172a;
  background:
    radial-gradient(circle at top left, rgba(148, 163, 184, 0.16), transparent 22%),
    radial-gradient(circle at top right, rgba(191, 219, 254, 0.22), transparent 24%),
    linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
  font-family: 'Segoe UI', sans-serif;
}

body {
  margin: 0;
  min-height: 100vh;
}

button,
input,
textarea {
  font: inherit;
}

.calculator-shell {
  width: min(1180px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 36px 0 56px;
}

.calculator-frame {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.7fr);
  gap: 20px;
}

.hero-copy,
.calculator-panel,
.history-panel {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 30px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(16px);
}

.hero-copy {
  grid-column: 1 / -1;
  padding: 28px 32px 18px;
}

.eyebrow {
  display: inline-block;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.75rem;
  color: #2563eb;
}

.hero-copy h1 {
  margin: 0.75rem 0 0;
  font-size: clamp(2.9rem, 8vw, 5rem);
  line-height: 0.95;
}

.hero-copy p,
.history-item,
.expression-preview,
.display-meta {
  color: #5b6476;
}

.calculator-panel {
  padding: 24px;
}

.display-panel {
  border-radius: 26px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
  color: white;
  padding: 20px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.display-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.85rem;
}

.status-pill {
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  background: rgba(148, 163, 184, 0.18);
  color: #dbeafe;
}

.expression-preview {
  margin-top: 12px;
  min-height: 24px;
  text-align: right;
  font-size: 0.95rem;
}

.display-value {
  margin-top: 6px;
  text-align: right;
  font-size: clamp(2.4rem, 5vw, 4rem);
  font-weight: 700;
  line-height: 1;
}

.button-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.calc-button {
  border: 0;
  min-height: 68px;
  border-radius: 22px;
  cursor: pointer;
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease;
}

.calc-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.12);
}

.calc-button.operator {
  background: #e0f2fe;
  color: #0f172a;
}

.calc-button.utility {
  background: #fee2e2;
  color: #991b1b;
}

.calc-button.accent {
  background: linear-gradient(135deg, #2563eb, #0f172a);
  color: white;
}

.calc-button.wide {
  grid-column: span 1;
}

.history-panel {
  padding: 24px;
}

.history-panel h2 {
  margin: 0.6rem 0 0;
  font-size: 1.5rem;
}

.history-list {
  margin-top: 18px;
  display: grid;
  gap: 12px;
}

.history-item {
  border-radius: 20px;
  background: rgba(241, 245, 249, 0.9);
  padding: 14px 16px;
  line-height: 1.5;
}

@media (max-width: 960px) {
  .calculator-frame {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .calculator-shell {
    width: min(100vw - 20px, 1180px);
    padding-top: 20px;
  }

  .hero-copy,
  .calculator-panel,
  .history-panel {
    border-radius: 24px;
  }

  .hero-copy {
    padding: 24px;
  }

  .calculator-panel,
  .history-panel {
    padding: 18px;
  }

  .calc-button {
    min-height: 58px;
    border-radius: 18px;
  }
}
"""


def _react_generated_shell_app_source(title: str, description: str) -> str:
    title_literal = json.dumps(title)
    description_literal = json.dumps(description)
    return f"""const title = {title_literal};
const description = {description_literal};

const focusAreas = description
  .split(/[.]/)
  .map((item) => item.trim())
  .filter(Boolean)
  .slice(0, 3);

export default function App() {{
  return (
    <main className="generated-shell">
      <section className="generated-hero">
        <p className="generated-kicker">Prompt-driven starter</p>
        <h1>{{title}}</h1>
        <p className="generated-copy">{{description}}</p>
      </section>

      <section className="generated-grid">
        <article className="generated-card">
          <h2>Ready to shape</h2>
          <p>
            DevHub created a clean React surface for this request. The coding agent can
            now turn it into the exact product flow you described instead of forcing a
            canned template.
          </p>
        </article>

        <article className="generated-card">
          <h2>Current scope</h2>
          <ul>
            {{(focusAreas.length ? focusAreas : ['Initial UI shell', 'Live preview wiring', 'Ready for generated features']).map((item) => (
              <li key={{item}}>{{item}}</li>
            ))}}
          </ul>
        </article>
      </section>
    </main>
  );
}}
"""


def _react_generated_shell_styles_source() -> str:
    return """* {
  box-sizing: border-box;
}

:root {
  color: #111827;
  background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%);
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

body {
  margin: 0;
  min-height: 100vh;
  background: inherit;
}

.generated-shell {
  min-height: 100vh;
  padding: 56px 24px 72px;
}

.generated-hero,
.generated-card {
  width: min(100%, 1040px);
  margin: 0 auto;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: #ffffff;
  box-shadow: 0 22px 70px rgba(15, 23, 42, 0.08);
}

.generated-hero {
  padding: 28px;
}

.generated-kicker {
  margin: 0 0 12px;
  font-size: 0.82rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #2563eb;
}

.generated-hero h1 {
  margin: 0;
  font-size: clamp(2.8rem, 8vw, 5rem);
  line-height: 0.96;
}

.generated-copy {
  max-width: 760px;
  margin: 18px 0 0;
  font-size: 1.06rem;
  line-height: 1.7;
  color: #475569;
}

.generated-grid {
  display: grid;
  gap: 22px;
  width: min(100%, 1040px);
  margin: 22px auto 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.generated-card {
  padding: 24px;
}

.generated-card h2 {
  margin: 0 0 12px;
  font-size: 1.3rem;
}

.generated-card p,
.generated-card li {
  color: #475569;
  font-size: 1rem;
  line-height: 1.7;
}

.generated-card ul {
  margin: 0;
  padding-left: 18px;
}

@media (max-width: 760px) {
  .generated-shell {
    padding: 24px 16px 40px;
  }

  .generated-grid {
    grid-template-columns: 1fr;
  }
}
"""


def _react_fastapi_frontend_app_source(title: str, description: str) -> str:
    title_literal = json.dumps(title)
    description_literal = json.dumps(description)
    return f"""import {{ useEffect, useState }} from 'react';

const title = {title_literal};
const description = {description_literal};

export default function App() {{
  const [health, setHealth] = useState({{ loading: true, payload: null, error: '' }});
  const [context, setContext] = useState(null);

  useEffect(() => {{
    let active = true;

    const load = async () => {{
      try {{
        const [healthResponse, contextResponse] = await Promise.all([
          fetch('/api/health'),
          fetch('/api/app-context'),
        ]);

        const healthPayload = await healthResponse.json();
        const contextPayload = await contextResponse.json();

        if (!active) return;
        setHealth({{ loading: false, payload: healthPayload, error: '' }});
        setContext(contextPayload);
      }} catch (error) {{
        if (!active) return;
        setHealth({{
          loading: false,
          payload: null,
          error: error instanceof Error ? error.message : 'Unable to reach the backend.',
        }});
      }}
    }};

    load();
    return () => {{
      active = false;
    }};
  }}, []);

  return (
    <main className="stack-shell">
      <section className="stack-hero">
        <p className="stack-kicker">Connected full-stack starter</p>
        <h1>{{title}}</h1>
        <p className="stack-copy">{{description}}</p>
      </section>

      <section className="stack-grid">
        <article className="stack-card">
          <div className="stack-card-head">
            <h2>Frontend</h2>
            <span>React + Vite</span>
          </div>
          <p>
            This UI is already wired to the backend through <code>/api</code> so generated
            features can use real data instead of placeholder copy.
          </p>
        </article>

        <article className="stack-card">
          <div className="stack-card-head">
            <h2>Backend</h2>
            <span>FastAPI</span>
          </div>
          <p>
            {{health.loading ? 'Checking backend status...' : health.error ? `Backend error: ${{health.error}}` : `Backend status: ${{health.payload?.status || 'ok'}}`}}
          </p>
          <pre>{{JSON.stringify(context || health.payload || {{ status: 'loading' }}, null, 2)}}</pre>
        </article>
      </section>
    </main>
  );
}}
"""


def _react_fastapi_frontend_styles_source() -> str:
    return """* {
  box-sizing: border-box;
}

:root {
  color: #111827;
  background: radial-gradient(circle at top, #f8fbff 0%, #edf3ff 48%, #e8f0ff 100%);
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

body {
  margin: 0;
  min-height: 100vh;
  background: inherit;
}

.stack-shell {
  min-height: 100vh;
  padding: 52px 24px 64px;
}

.stack-hero,
.stack-card {
  width: min(100%, 1120px);
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.08);
}

.stack-hero {
  padding: 32px;
}

.stack-kicker {
  margin: 0 0 12px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.82rem;
  color: #2563eb;
}

.stack-hero h1 {
  margin: 0;
  font-size: clamp(3rem, 8vw, 5.4rem);
  line-height: 0.95;
}

.stack-copy {
  max-width: 840px;
  margin: 18px 0 0;
  font-size: 1.08rem;
  line-height: 1.7;
  color: #475569;
}

.stack-grid {
  display: grid;
  gap: 24px;
  width: min(100%, 1120px);
  margin: 24px auto 0;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.stack-card {
  padding: 26px;
}

.stack-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.stack-card-head h2 {
  margin: 0;
  font-size: 1.4rem;
}

.stack-card-head span {
  padding: 8px 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 0.85rem;
  font-weight: 600;
}

.stack-card p {
  margin: 16px 0 0;
  color: #475569;
  font-size: 1rem;
  line-height: 1.7;
}

.stack-card pre {
  margin: 16px 0 0;
  overflow: auto;
  padding: 18px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 0.92rem;
  line-height: 1.6;
}

@media (max-width: 860px) {
  .stack-shell {
    padding: 24px 16px 40px;
  }

  .stack-grid {
    grid-template-columns: 1fr;
  }
}
"""


def _react_planner_app_source(title: str, description: str) -> str:
    return f"""import {{ useMemo, useState }} from 'react';

const INITIAL_COLUMNS = {{
  backlog: [
    {{ id: 1, title: 'Capture the user flow', detail: 'Map the first-screen experience and define the must-have actions.' }},
    {{ id: 2, title: 'Shape the MVP scope', detail: 'Keep the launch small, clear, and easy to iterate on.' }},
  ],
  active: [
    {{ id: 3, title: 'Build the core interaction', detail: 'Implement the primary value loop for the product idea.' }},
  ],
  shipped: [
    {{ id: 4, title: 'Starter workspace ready', detail: 'This project already boots with a real working interface.' }},
  ],
}};

const COLUMN_META = [
  {{ key: 'backlog', label: 'Backlog' }},
  {{ key: 'active', label: 'In Progress' }},
  {{ key: 'shipped', label: 'Done' }},
];

export default function App() {{
  const [columns, setColumns] = useState(INITIAL_COLUMNS);
  const [titleInput, setTitleInput] = useState('');
  const [detailInput, setDetailInput] = useState('');

  const totals = useMemo(() => {{
    const values = Object.values(columns).map((items) => items.length);
    return {{
      total: values.reduce((sum, count) => sum + count, 0),
      active: columns.active.length,
      shipped: columns.shipped.length,
    }};
  }}, [columns]);

  const addTask = () => {{
    const cleanTitle = titleInput.trim();
    if (!cleanTitle) return;

    const nextItem = {{
      id: Date.now(),
      title: cleanTitle,
      detail: detailInput.trim() || 'New work item added from the starter app.',
    }};

    setColumns((current) => ({{
      ...current,
      backlog: [nextItem, ...current.backlog],
    }}));
    setTitleInput('');
    setDetailInput('');
  }};

  const moveTask = (itemId, fromKey, toKey) => {{
    if (fromKey === toKey) return;

    setColumns((current) => {{
      const item = current[fromKey].find((entry) => entry.id === itemId);
      if (!item) return current;

      return {{
        ...current,
        [fromKey]: current[fromKey].filter((entry) => entry.id !== itemId),
        [toKey]: [item, ...current[toKey]],
      }};
    }});
  }};

  return (
    <div className="planner-shell">
      <section className="hero-card">
        <div>
          <span className="eyebrow">Working Planner Starter</span>
          <h1>{title}</h1>
          <p className="description">{description}</p>
        </div>
        <div className="hero-stats">
          <article>
            <span>Total Items</span>
            <strong>{{totals.total}}</strong>
          </article>
          <article>
            <span>Active</span>
            <strong>{{totals.active}}</strong>
          </article>
          <article>
            <span>Done</span>
            <strong>{{totals.shipped}}</strong>
          </article>
        </div>
      </section>

      <section className="composer-card">
        <div className="composer-copy">
          <span className="eyebrow">Quick Add</span>
          <h2>Turn the idea into tracked work</h2>
          <p>Start with a real mini app: add items, move them through stages, and evolve the experience with DevHub chat.</p>
        </div>
        <div className="composer-form">
          <input value={{titleInput}} onChange={{(event) => setTitleInput(event.target.value)}} placeholder="Add a work item title" />
          <textarea value={{detailInput}} onChange={{(event) => setDetailInput(event.target.value)}} rows={{3}} placeholder="Add acceptance notes, implementation intent, or user value." />
          <button type="button" onClick={{addTask}}>Add Work Item</button>
        </div>
      </section>

      <section className="board-grid">
        {{COLUMN_META.map((column) => (
          <article key={{column.key}} className="board-column">
            <div className="column-header">
              <div>
                <span className="eyebrow">{{column.label}}</span>
                <h3>{{column.label}}</h3>
              </div>
              <span className="count-pill">{{columns[column.key].length}}</span>
            </div>

            <div className="column-list">
              {{columns[column.key].map((item) => (
                <div key={{item.id}} className="task-card">
                  <h4>{{item.title}}</h4>
                  <p>{{item.detail}}</p>
                  <div className="task-actions">
                    {{column.key !== 'backlog' ? <button type="button" className="secondary" onClick={{() => moveTask(item.id, column.key, 'backlog')}}>Backlog</button> : null}}
                    {{column.key !== 'active' ? <button type="button" className="secondary" onClick={{() => moveTask(item.id, column.key, 'active')}}>In Progress</button> : null}}
                    {{column.key !== 'shipped' ? <button type="button" className="secondary" onClick={{() => moveTask(item.id, column.key, 'shipped')}}>Done</button> : null}}
                  </div>
                </div>
              ))}}
            </div>
          </article>
        ))}}
      </section>
    </div>
  );
}}
"""


def _react_planner_styles_source() -> str:
    return """* {
  box-sizing: border-box;
}

:root {
  color: #102033;
  background:
    radial-gradient(circle at top right, rgba(45, 212, 191, 0.18), transparent 28%),
    linear-gradient(180deg, #f7fbff 0%, #eef4f8 100%);
  font-family: 'Segoe UI', sans-serif;
}

body {
  margin: 0;
  min-height: 100vh;
}

button,
input,
textarea {
  font: inherit;
}

button {
  border: none;
  border-radius: 999px;
  padding: 0.85rem 1.15rem;
  cursor: pointer;
  background: #0f172a;
  color: white;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.16);
}

button.secondary {
  background: rgba(15, 23, 42, 0.08);
  color: #102033;
  box-shadow: none;
}

input,
textarea {
  width: 100%;
  border: 1px solid rgba(16, 32, 51, 0.12);
  border-radius: 18px;
  background: white;
  padding: 0.9rem 1rem;
  color: #102033;
}

textarea {
  resize: vertical;
}

.planner-shell {
  width: min(1160px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 32px 0 56px;
}

.hero-card,
.composer-card,
.board-column,
.task-card {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(16, 32, 51, 0.1);
  border-radius: 28px;
  box-shadow: 0 24px 60px rgba(16, 32, 51, 0.08);
}

.hero-card,
.composer-card {
  padding: 28px;
}

.hero-card {
  display: grid;
  gap: 20px;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.9fr);
}

.eyebrow {
  display: inline-block;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.75rem;
  color: #0f766e;
}

.hero-card h1 {
  margin: 0.7rem 0 0;
  font-size: clamp(2.7rem, 6vw, 4.8rem);
  line-height: 0.94;
}

.description,
.composer-card p,
.task-card p {
  color: #5b6678;
  line-height: 1.6;
}

.hero-stats {
  display: grid;
  gap: 14px;
}

.hero-stats article {
  border-radius: 22px;
  background: #f8fcfd;
  padding: 18px;
}

.hero-stats span {
  display: block;
  color: #5b6678;
  font-size: 0.8rem;
}

.hero-stats strong {
  display: block;
  margin-top: 8px;
  font-size: 2rem;
  color: #102033;
}

.composer-card {
  margin-top: 18px;
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 1.1fr);
}

.composer-copy h2 {
  margin: 0.65rem 0 0;
  font-size: 1.8rem;
}

.composer-form {
  display: grid;
  gap: 12px;
}

.board-grid {
  margin-top: 18px;
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.board-column {
  padding: 18px;
}

.column-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.column-header h3 {
  margin: 0.45rem 0 0;
  font-size: 1.15rem;
}

.count-pill {
  min-width: 40px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.12);
  color: #0f766e;
  font-size: 0.85rem;
  font-weight: 700;
  padding: 0.45rem 0.8rem;
  text-align: center;
}

.column-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.task-card {
  padding: 18px;
}

.task-card h4 {
  margin: 0;
  font-size: 1rem;
}

.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

@media (max-width: 960px) {
  .hero-card,
  .composer-card,
  .board-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .planner-shell {
    width: min(100vw - 18px, 1160px);
    padding-top: 18px;
  }

  .hero-card,
  .composer-card,
  .board-column,
  .task-card {
    border-radius: 22px;
  }

  .hero-card,
  .composer-card,
  .board-column {
    padding: 20px;
  }
}
"""


def _react_dashboard_app_source(title: str, description: str) -> str:
    return f"""import {{ useMemo, useState }} from 'react';

const DATA = {{
  day: {{
    metrics: [
      {{ label: 'Active Users', value: '1,284', change: '+8.2%' }},
      {{ label: 'Conversion', value: '4.8%', change: '+0.6%' }},
      {{ label: 'Open Tickets', value: '17', change: '-3' }},
    ],
    activity: [
      'Launch campaign crossed the morning traffic target.',
      'Three onboarding issues were resolved within SLA.',
      'The preview environment is stable and ready for review.',
    ],
  }},
  week: {{
    metrics: [
      {{ label: 'Active Users', value: '8,920', change: '+14.1%' }},
      {{ label: 'Conversion', value: '5.2%', change: '+0.8%' }},
      {{ label: 'Open Tickets', value: '62', change: '-11' }},
    ],
    activity: [
      'Weekly acquisition is outperforming the prior cycle.',
      'Retention improved after the latest UX cleanup.',
      'Support load is trending down across the core funnel.',
    ],
  }},
  month: {{
    metrics: [
      {{ label: 'Active Users', value: '34,500', change: '+22.4%' }},
      {{ label: 'Conversion', value: '5.7%', change: '+1.4%' }},
      {{ label: 'Open Tickets', value: '210', change: '-28' }},
    ],
    activity: [
      'Monthly growth remains healthy across activation and paid conversion.',
      'The product team can now use this starter as a live control surface.',
      'Customer operations are ready for the next iteration wave.',
    ],
  }},
}};

const PIPELINE = [
  {{ name: 'Qualified', count: 24 }},
  {{ name: 'Proposal', count: 11 }},
  {{ name: 'Negotiation', count: 6 }},
  {{ name: 'Won', count: 4 }},
];

export default function App() {{
  const [range, setRange] = useState('week');
  const snapshot = useMemo(() => DATA[range], [range]);

  return (
    <div className="dashboard-shell">
      <section className="dashboard-hero">
        <div>
          <span className="eyebrow">Live Dashboard Starter</span>
          <h1>{title}</h1>
          <p className="description">{description}</p>
        </div>
        <div className="range-switcher">
          {{['day', 'week', 'month'].map((value) => (
            <button
              key={{value}}
              type="button"
              className={{range === value ? 'active' : 'secondary'}}
              onClick={{() => setRange(value)}}
            >
              {{value}}
            </button>
          ))}}
        </div>
      </section>

      <section className="metric-grid">
        {{snapshot.metrics.map((metric) => (
          <article key={{metric.label}} className="metric-card">
            <span>{{metric.label}}</span>
            <strong>{{metric.value}}</strong>
            <p>{{metric.change}} vs previous period</p>
          </article>
        ))}}
      </section>

      <section className="dashboard-grid">
        <article className="panel-card">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Pipeline</span>
              <h2>Deal flow</h2>
            </div>
          </div>
          <div className="pipeline-list">
            {{PIPELINE.map((stage) => (
              <div key={{stage.name}} className="pipeline-row">
                <span>{{stage.name}}</span>
                <strong>{{stage.count}}</strong>
              </div>
            ))}}
          </div>
        </article>

        <article className="panel-card">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Signals</span>
              <h2>Recent activity</h2>
            </div>
          </div>
          <div className="activity-list">
            {{snapshot.activity.map((item) => (
              <div key={{item}} className="activity-item">{{item}}</div>
            ))}}
          </div>
        </article>
      </section>
    </div>
  );
}}
"""


def _react_dashboard_styles_source() -> str:
    return """* {
  box-sizing: border-box;
}

:root {
  color: #112033;
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.2), transparent 26%),
    linear-gradient(180deg, #f7fbff 0%, #edf4fb 100%);
  font-family: 'Segoe UI', sans-serif;
}

body {
  margin: 0;
  min-height: 100vh;
}

button {
  border: none;
  border-radius: 999px;
  padding: 0.8rem 1.1rem;
  font: inherit;
  cursor: pointer;
  background: #0f172a;
  color: white;
}

button.secondary {
  background: rgba(15, 23, 42, 0.08);
  color: #112033;
}

.dashboard-shell {
  width: min(1120px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 34px 0 56px;
}

.dashboard-hero,
.metric-card,
.panel-card {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(17, 32, 51, 0.1);
  border-radius: 28px;
  box-shadow: 0 24px 64px rgba(17, 32, 51, 0.08);
}

.dashboard-hero {
  padding: 28px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.eyebrow {
  display: inline-block;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.75rem;
  color: #0284c7;
}

.dashboard-hero h1 {
  margin: 0.7rem 0 0;
  font-size: clamp(2.8rem, 6vw, 5rem);
  line-height: 0.95;
}

.description,
.metric-card p,
.activity-item {
  color: #5b6678;
  line-height: 1.6;
}

.range-switcher {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.range-switcher .active {
  box-shadow: 0 16px 30px rgba(15, 23, 42, 0.16);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.metric-card,
.panel-card {
  padding: 22px;
}

.metric-card span {
  display: block;
  color: #5b6678;
  font-size: 0.82rem;
}

.metric-card strong {
  display: block;
  margin-top: 10px;
  font-size: 2rem;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.1fr);
  gap: 16px;
  margin-top: 18px;
}

.panel-header h2 {
  margin: 0.5rem 0 0;
}

.pipeline-list,
.activity-list {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.pipeline-row,
.activity-item {
  border-radius: 20px;
  background: #f8fbff;
  padding: 16px;
}

.pipeline-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 860px) {
  .dashboard-hero,
  .metric-grid,
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-hero {
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .dashboard-shell {
    width: min(100vw - 18px, 1120px);
    padding-top: 18px;
  }

  .dashboard-hero,
  .metric-card,
  .panel-card {
    border-radius: 22px;
  }
}
"""


def _react_expense_app_source(title: str, description: str) -> str:
    return f"""import {{ useMemo, useState }} from 'react';

const INITIAL_ITEMS = [
  {{ id: 1, label: 'Design subscription', amount: 24, category: 'Tools' }},
  {{ id: 2, label: 'Customer interview incentive', amount: 80, category: 'Research' }},
  {{ id: 3, label: 'Hosting', amount: 36, category: 'Infra' }},
];

export default function App() {{
  const [items, setItems] = useState(INITIAL_ITEMS);
  const [label, setLabel] = useState('');
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('General');

  const totals = useMemo(() => {{
    const spend = items.reduce((sum, item) => sum + item.amount, 0);
    const avg = items.length ? spend / items.length : 0;
    return {{
      spend,
      avg: avg.toFixed(2),
      count: items.length,
    }};
  }}, [items]);

  const addItem = () => {{
    const numericAmount = Number(amount);
    if (!label.trim() || !Number.isFinite(numericAmount) || numericAmount <= 0) return;

    setItems((current) => [
      {{ id: Date.now(), label: label.trim(), amount: numericAmount, category }},
      ...current,
    ]);
    setLabel('');
    setAmount('');
    setCategory('General');
  }};

  return (
    <div className="expense-shell">
      <section className="expense-hero">
        <div>
          <span className="eyebrow">Working Expense Starter</span>
          <h1>{title}</h1>
          <p className="description">{description}</p>
        </div>
        <div className="totals-grid">
          <article><span>Total Spend</span><strong>${{totals.spend.toFixed(2)}}</strong></article>
          <article><span>Avg Entry</span><strong>${{totals.avg}}</strong></article>
          <article><span>Entries</span><strong>{{totals.count}}</strong></article>
        </div>
      </section>

      <section className="expense-composer">
        <input value={{label}} onChange={{(event) => setLabel(event.target.value)}} placeholder="Expense label" />
        <input value={{amount}} onChange={{(event) => setAmount(event.target.value)}} placeholder="Amount" inputMode="decimal" />
        <select value={{category}} onChange={{(event) => setCategory(event.target.value)}}>
          <option>General</option>
          <option>Tools</option>
          <option>Research</option>
          <option>Infra</option>
          <option>Marketing</option>
        </select>
        <button type="button" onClick={{addItem}}>Add Expense</button>
      </section>

      <section className="expense-list">
        {{items.map((item) => (
          <article key={{item.id}} className="expense-row">
            <div>
              <h3>{{item.label}}</h3>
              <p>{{item.category}}</p>
            </div>
            <strong>${{item.amount.toFixed(2)}}</strong>
          </article>
        ))}}
      </section>
    </div>
  );
}}
"""


def _react_expense_styles_source() -> str:
    return """* {
  box-sizing: border-box;
}

:root {
  color: #1f2937;
  background:
    radial-gradient(circle at top right, rgba(234, 179, 8, 0.16), transparent 24%),
    linear-gradient(180deg, #fffdf7 0%, #f8f4ea 100%);
  font-family: 'Segoe UI', sans-serif;
}

body {
  margin: 0;
  min-height: 100vh;
}

button,
input,
select {
  font: inherit;
}

button {
  border: none;
  border-radius: 999px;
  padding: 0.85rem 1.15rem;
  cursor: pointer;
  background: #92400e;
  color: white;
  box-shadow: 0 14px 24px rgba(146, 64, 14, 0.2);
}

input,
select {
  width: 100%;
  border: 1px solid rgba(31, 41, 55, 0.12);
  border-radius: 18px;
  background: white;
  color: #1f2937;
  padding: 0.9rem 1rem;
}

.expense-shell {
  width: min(1080px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 32px 0 56px;
}

.expense-hero,
.expense-composer,
.expense-row {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(31, 41, 55, 0.1);
  border-radius: 28px;
  box-shadow: 0 24px 64px rgba(31, 41, 55, 0.08);
}

.expense-hero,
.expense-composer {
  padding: 26px;
}

.expense-hero {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.9fr);
}

.eyebrow {
  display: inline-block;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.75rem;
  color: #b45309;
}

.expense-hero h1 {
  margin: 0.7rem 0 0;
  font-size: clamp(2.8rem, 6vw, 5rem);
  line-height: 0.95;
}

.description,
.expense-row p {
  color: #6b7280;
  line-height: 1.6;
}

.totals-grid {
  display: grid;
  gap: 12px;
}

.totals-grid article {
  border-radius: 22px;
  background: #fffaf0;
  padding: 16px;
}

.totals-grid span {
  display: block;
  color: #6b7280;
  font-size: 0.8rem;
}

.totals-grid strong {
  display: block;
  margin-top: 8px;
  font-size: 1.9rem;
}

.expense-composer {
  margin-top: 18px;
  display: grid;
  gap: 12px;
  grid-template-columns: 2fr 1fr 1fr auto;
  align-items: center;
}

.expense-list {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.expense-row {
  padding: 18px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.expense-row h3,
.expense-row p {
  margin: 0;
}

.expense-row p {
  margin-top: 4px;
}

@media (max-width: 860px) {
  .expense-hero,
  .expense-composer {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .expense-shell {
    width: min(100vw - 18px, 1080px);
    padding-top: 18px;
  }

  .expense-hero,
  .expense-composer,
  .expense-row {
    border-radius: 22px;
  }
}
"""


def _react_scaffold_files(project: Project, starter_brief: str = "") -> dict:
    title = project.name or "DevHub App"
    description = _display_description(project)
    package_name = _project_slug(project)
    app_source = _react_generated_shell_app_source(title, description)
    styles_source = _react_generated_shell_styles_source()
    starter_note = (
        "This starter stays intentionally neutral so DevHub can generate the requested product "
        "instead of forcing a canned demo template."
    )

    return {
        "package.json": f"""{{
  "name": "{package_name}",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "dev": "vite --host 127.0.0.1 --port 4173",
    "build": "vite build",
    "preview": "vite preview --host 127.0.0.1 --port 4173"
  }},
  "dependencies": {{
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }},
  "devDependencies": {{
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^5.4.10"
  }}
}}
""",
        "vite.config.js": """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 4173,
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
  },
});
""",
        "index.html": f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""",
        "src/main.jsx": """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
""",
        "src/App.jsx": app_source,
        "src/styles.css": styles_source,
        "README.md": f"""# {title}

{description}

## Run locally

```bash
npm install
npm run dev
```

Then open [http://127.0.0.1:4173](http://127.0.0.1:4173).

{starter_note}
""",
        ".gitignore": "node_modules/\ndist/\n.vite/\n",
    }


def _react_fastapi_scaffold_files(project: Project, starter_brief: str = "") -> dict:
    title = project.name or "DevHub App"
    description = _display_description(project)
    package_name = _project_slug(project)
    title_literal = json.dumps(title)
    description_literal = json.dumps(description)

    return {
        "package.json": f"""{{
  "name": "{package_name}",
  "private": true,
  "version": "0.1.0",
  "scripts": {{
    "dev": "concurrently -k -n frontend,backend -c cyan,magenta \\"npm --prefix frontend run dev -- --host 127.0.0.1 --port 4173\\" \\"python -m uvicorn backend.main:app --host 127.0.0.1 --port 8100 --reload\\"",
    "build": "npm --prefix frontend run build",
    "preview": "npm --prefix frontend run preview -- --host 127.0.0.1 --port 4173",
    "postinstall": "npm --prefix frontend install"
  }},
  "devDependencies": {{
    "concurrently": "^9.0.1"
  }}
}}
""",
        "requirements.txt": "fastapi==0.116.1\nuvicorn[standard]==0.35.0\n",
        "frontend/package.json": f"""{{
  "name": "{package_name}-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }},
  "devDependencies": {{
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^5.4.10"
  }}
}}
""",
        "frontend/vite.config.js": """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
  },
});
""",
        "frontend/index.html": f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""",
        "frontend/src/main.jsx": """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
""",
        "frontend/src/App.jsx": _react_fastapi_frontend_app_source(title, description),
        "frontend/src/styles.css": _react_fastapi_frontend_styles_source(),
        "backend/main.py": f"""from fastapi import FastAPI

app = FastAPI(title={title_literal}, description={description_literal})


@app.get("/api/health")
def health():
    return {{"status": "ok", "project": {title_literal}, "message": "Backend connected successfully."}}


@app.get("/api/app-context")
def app_context():
    return {{
        "name": {title_literal},
        "description": {description_literal},
        "stack": ["React", "FastAPI"],
        "mode": "fullstack-starter",
    }}
""",
        "README.md": f"""# {title}

{description}

## Structure

- `frontend/` contains the React + Vite client
- `backend/` contains the FastAPI server
- root `package.json` boots both services together inside DevHub

## Run locally

```bash
npm install
python -m pip install -r requirements.txt
npm run dev
```
""",
        ".gitignore": "__pycache__/\n*.pyc\nnode_modules/\nfrontend/node_modules/\n.devhub/\ndist/\n",
    }


def _fastapi_scaffold_files(project: Project) -> dict:
    title = project.name or "DevHub API App"
    description = _display_description(project)

    return {
        "requirements.txt": "fastapi==0.116.1\nuvicorn[standard]==0.35.0\n",
        "main.py": f"""from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title={title!r})
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    with open("templates/index.html", "r", encoding="utf-8") as handle:
        return handle.read()


@app.get("/api/health")
async def health():
    return {{"status": "ok", "project": {title!r}}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
""",
        "templates/index.html": f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <span class="eyebrow">FastAPI Starter</span>
        <h1>{title}</h1>
        <p>{description}</p>
        <div class="actions">
          <button id="health-button">Check API health</button>
          <button id="chat-button" class="secondary">Update this UI with chat</button>
        </div>
      </section>
      <section class="panel">
        <h2>Server Response</h2>
        <pre id="output">Click "Check API health" to verify the backend is live.</pre>
      </section>
    </main>
    <script type="module" src="/static/app.js"></script>
  </body>
</html>
""",
        "static/styles.css": """body {
  margin: 0;
  min-height: 100vh;
  font-family: 'Segoe UI', sans-serif;
  color: #102033;
  background: linear-gradient(180deg, #f7fbff 0%, #edf4f8 100%);
}

.shell {
  width: min(920px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 36px 0 60px;
}

.hero,
.panel {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(16, 32, 51, 0.1);
  border-radius: 24px;
  box-shadow: 0 20px 48px rgba(16, 32, 51, 0.08);
  padding: 24px;
}

.panel {
  margin-top: 18px;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.75rem;
  color: #2563eb;
}

h1 {
  margin: 10px 0;
  font-size: clamp(2.8rem, 6vw, 4.8rem);
  line-height: 0.95;
}

.actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 20px;
}

button {
  border: 0;
  border-radius: 999px;
  padding: 12px 18px;
  font: inherit;
  cursor: pointer;
  background: #2563eb;
  color: white;
}

button.secondary {
  background: rgba(37, 99, 235, 0.12);
  color: #102033;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: Consolas, monospace;
}
""",
        "static/app.js": """const output = document.getElementById('output');

document.getElementById('health-button').addEventListener('click', async () => {
  output.textContent = 'Checking API health...';
  const response = await fetch('/api/health');
  const data = await response.json();
  output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById('chat-button').addEventListener('click', () => {
  output.textContent = 'Use the embedded DevHub chat to modify templates, styles, and backend logic.';
});
""",
        "README.md": f"""# {title}

{description}

## Run locally

```bash
python -m pip install -r requirements.txt
python main.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).
""",
        ".gitignore": "__pycache__/\n*.pyc\n",
    }


def _django_scaffold_files(project: Project) -> dict:
    title = project.name or "DevHub Django App"
    description = _display_description(project)
    settings_module = "project_core.settings"

    return {
        "requirements.txt": "Django==5.2.1\n",
        "manage.py": f"""#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{settings_module}")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
""",
        "project_core/__init__.py": "",
        "project_core/settings.py": f"""from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "devhub-generated-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "webapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "project_core.urls"

TEMPLATES = [
    {{
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {{
            "context_processors": [],
        }},
    }},
]

WSGI_APPLICATION = "project_core.wsgi.application"

DATABASES = {{
    "default": {{
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }}
}}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
PROJECT_TITLE = {title!r}
PROJECT_DESCRIPTION = {description!r}
""",
        "project_core/urls.py": """from django.urls import include, path

urlpatterns = [
    path("", include("webapp.urls")),
]
""",
        "project_core/wsgi.py": f"""import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{settings_module}")

application = get_wsgi_application()
""",
        "webapp/__init__.py": "",
        "webapp/apps.py": """from django.apps import AppConfig


class WebappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "webapp"
""",
        "webapp/views.py": """from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render


def home(request):
    return render(
        request,
        "webapp/home.html",
        {
            "project_name": settings.PROJECT_TITLE,
            "project_description": settings.PROJECT_DESCRIPTION,
        },
    )


def health(request):
    return JsonResponse({"status": "ok", "project": settings.PROJECT_TITLE})
""",
        "webapp/urls.py": """from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("api/health/", views.health, name="health"),
]
""",
        "templates/webapp/home.html": """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{ project_name }}</title>
    <link rel="stylesheet" href="/static/webapp/styles.css" />
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <span class="eyebrow">Django Starter</span>
        <h1>{{ project_name }}</h1>
        <p>{{ project_description }}</p>
        <div class="actions">
          <button id="health-button">Check backend</button>
          <button id="chat-button" class="secondary">Update this starter with chat</button>
        </div>
      </section>
      <section class="panel">
        <h2>Status</h2>
        <pre id="output">The starter is ready. Ask DevHub to add pages, API routes, or UI changes.</pre>
      </section>
    </main>
    <script type="module" src="/static/webapp/app.js"></script>
  </body>
</html>
""",
        "static/webapp/styles.css": """body {
  margin: 0;
  min-height: 100vh;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
  color: #162033;
  font-family: 'Segoe UI', sans-serif;
}

.shell {
  width: min(920px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 36px 0 60px;
}

.hero,
.panel {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(22, 32, 51, 0.1);
  border-radius: 24px;
  box-shadow: 0 24px 56px rgba(22, 32, 51, 0.08);
  padding: 24px;
}

.panel {
  margin-top: 18px;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.75rem;
  color: #4f46e5;
}

h1 {
  margin: 10px 0;
  font-size: clamp(2.8rem, 6vw, 4.8rem);
  line-height: 0.95;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 20px;
}

button {
  border: 0;
  border-radius: 999px;
  padding: 12px 18px;
  font: inherit;
  cursor: pointer;
  background: #4f46e5;
  color: white;
}

button.secondary {
  background: rgba(79, 70, 229, 0.12);
  color: #162033;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: Consolas, monospace;
}
""",
        "static/webapp/app.js": """const output = document.getElementById('output');

document.getElementById('health-button').addEventListener('click', async () => {
  output.textContent = 'Checking backend...';
  const response = await fetch('/api/health/');
  const data = await response.json();
  output.textContent = JSON.stringify(data, null, 2);
});

document.getElementById('chat-button').addEventListener('click', () => {
  output.textContent = 'Use DevHub chat to update templates, styles, routes, or backend code.';
});
""",
        "README.md": f"""# {title}

{description}

## Run locally

```bash
python -m pip install -r requirements.txt
python manage.py runserver 127.0.0.1:8000
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).
""",
        ".gitignore": "__pycache__/\n*.pyc\ndb.sqlite3\n",
    }


def build_scaffold_files(project: Project, starter_brief: str = "") -> dict:
    tokens = _project_tokens(project, starter_brief)
    starter_text = " ".join(filter(None, [project.name or "", project.description or "", starter_brief])).lower()

    if "react" in tokens and "fastapi" in tokens:
        files = _react_fastapi_scaffold_files(project, starter_brief=starter_brief)
    elif _wants_connected_fullstack_from_text(starter_text):
        files = _react_fastapi_scaffold_files(project, starter_brief=starter_brief)
    elif 'react' in tokens or 'vite' in tokens:
        files = _react_scaffold_files(project, starter_brief=starter_brief)
    elif 'fastapi' in tokens:
        files = _fastapi_scaffold_files(project)
    elif 'django' in tokens:
        files = _django_scaffold_files(project)
    else:
        files = _static_scaffold_files(project)

    ai_config = _project_ai_config(project)
    if not ai_config_is_usable(ai_config):
        return files

    try:
        from agents.scaffolder import ScaffolderAgent

        agent = ScaffolderAgent(ai_config=ai_config)
        scaffold = agent.generate_scaffold(
            description=(
                f"Create a small but working application for {project.name}. "
                f"Description: {_display_description(project)}. "
                f"Original user brief: {starter_brief or _display_description(project)}. "
                "Generate the actual product the user asked for, not a canned landing page or placeholder marketing screen. "
                "If the selected stack spans frontend and backend, create connected frontend and backend folders, "
                "wire the UI to real backend endpoints, and keep the whole project runnable after setup. "
                "If the request mentions games, leaderboards, saved scores, auth, or persistence, include the real backend models/routes/storage "
                "and connect the frontend to them. "
                "Do not collapse browser app requests with backend requirements into a single static HTML page. "
                "Prefer replacing the main scaffold files with app-specific code instead of adding disconnected alternates."
            ),
            tech_stack=", ".join(project.tech_stack or []) or "HTML, CSS, JavaScript",
        )
        ai_files = _safe_scaffold_files({
            item.get('path'): item.get('content')
            for item in scaffold.get('files', [])
            if isinstance(item, dict) and item.get('path') and item.get('content') is not None
        })
        if ai_files:
            for rel_path, content in ai_files.items():
                files[rel_path] = content
    except Exception:
        pass

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


def _preview_url_for_command(command: str | None) -> str | None:
    if not command:
        return None
    match = re.search(r'(\d{4,5})', command)
    if not match:
        return None
    return f"http://127.0.0.1:{match.group(1)}"


def _vite_config_preview_url(project_root: Path) -> str | None:
    for rel_path in ("vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.cjs"):
        config_path = project_root / rel_path
        if not config_path.exists():
            continue
        try:
            content = config_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        port_match = re.search(r'port\s*:\s*(\d{4,5})', content)
        host_match = re.search(r"host\s*:\s*['\"]([^'\"]+)['\"]", content)
        port = port_match.group(1) if port_match else "5173"
        host = host_match.group(1) if host_match else "127.0.0.1"
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        return f"http://{host}:{port}"
    return None


def _node_preview_url(project_root: Path, scripts: dict, run_command: str | None) -> str | None:
    candidate_scripts = [
        scripts.get("dev"),
        scripts.get("start"),
        scripts.get("preview"),
        run_command,
    ]
    for candidate in candidate_scripts:
        preview_url = _preview_url_for_command(candidate)
        if preview_url:
            return preview_url

    lower_scripts = " ".join(str(candidate or "").lower() for candidate in candidate_scripts)
    if "vite" in lower_scripts:
        return _vite_config_preview_url(project_root) or "http://127.0.0.1:5173"
    if "react-scripts start" in lower_scripts:
        return "http://127.0.0.1:3000"
    if "next dev" in lower_scripts or "next start" in lower_scripts:
        return "http://127.0.0.1:3000"
    if "nuxt" in lower_scripts:
        return "http://127.0.0.1:3000"
    return None


def _node_setup_command(project_root: Path) -> str | None:
    commands: list[str] = []
    if (project_root / "package.json").exists():
        commands.append("npm install")
    if (project_root / "requirements.txt").exists():
        python_cmd = _python_executable_command()
        commands.append(f"{python_cmd} -m pip install -r requirements.txt")
    return " && ".join(commands) if commands else None


def _node_install_required(project_root: Path) -> bool:
    frontend_package = project_root / "frontend" / "package.json"
    frontend_node_modules = project_root / "frontend" / "node_modules"
    needs_frontend_packages = frontend_package.exists() and not frontend_node_modules.exists()
    needs_root_packages = (project_root / "package.json").exists() and not (project_root / "node_modules").exists()
    needs_python_packages = (project_root / "requirements.txt").exists() and _python_install_required(project_root)
    return needs_root_packages or needs_frontend_packages or needs_python_packages


def _python_executable_command() -> str:
    sandbox_mode = str(os.environ.get("DEVHUB_SANDBOX_MODE") or "").strip().lower()
    if sandbox_mode == "docker":
        return "python"
    return f'"{sys.executable}"'


def _read_runtime_text_if_exists(path: Path) -> str:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        pass
    return ""


def _detect_python_app_runtime(project_root: Path, entrypoint: str, python_cmd: str) -> tuple[str, str | None]:
    entrypoint_path = project_root / entrypoint
    entrypoint_text = _read_runtime_text_if_exists(entrypoint_path).lower()
    requirements_blob = _read_runtime_text_if_exists(project_root / "requirements.txt").lower()
    port = _stable_runtime_port(project_root, start=8100)
    module_name = Path(entrypoint).stem

    if "fastapi" in requirements_blob or "uvicorn" in requirements_blob or "fastapi(" in entrypoint_text:
        return (
            f"{python_cmd} -m uvicorn {module_name}:app --host 127.0.0.1 --port {port}",
            f"http://127.0.0.1:{port}",
        )

    if "flask" in requirements_blob or "flask(" in entrypoint_text:
        return (
            f"{python_cmd} -m flask --app {module_name}:app run --host 127.0.0.1 --port {port}",
            f"http://127.0.0.1:{port}",
        )

    return (
        f"{python_cmd} {entrypoint}",
        _preview_url_for_command(f"{python_cmd} {entrypoint}"),
    )


def _python_install_required(project_root: Path) -> bool:
    requirements_file = project_root / "requirements.txt"
    if not requirements_file.exists():
        return False

    sandbox_mode = str(os.environ.get("DEVHUB_SANDBOX_MODE") or "").strip().lower()
    if sandbox_mode == "docker":
        return not (project_root / ".devhub" / "python-packages").exists()

    return False


def _stable_runtime_port(project_root: Path, *, start: int, size: int = 700) -> int:
    digest = hashlib.md5(str(project_root.resolve()).encode('utf-8')).hexdigest()
    return start + (int(digest[:8], 16) % size)


def _probe_preview_url(preview_url: str, timeout: float = 1.2) -> tuple[bool, str | None]:
    request = Request(preview_url, headers={"User-Agent": "DevHub Preview Probe"})
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read(1)
        return True, None
    except HTTPError:
        return True, None
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        return False, str(reason or exc)
    except Exception as exc:
        return False, str(exc)


def _wait_for_preview_ready(preview_url: str, sandbox, process_id: str, timeout_seconds: float = 8.0) -> tuple[bool, str | None]:
    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        status = sandbox.get_status(process_id)
        if not status.get("running"):
            startup_output = "".join(sandbox.get_output(process_id)).strip()
            if startup_output:
                return False, startup_output[-2000:]
            return False, last_error or "Runtime process exited before the preview became reachable."

        ready, error = _probe_preview_url(preview_url)
        if ready:
            return True, None

        last_error = error
        time.sleep(0.35)

    return False, last_error or "Preview did not become reachable in time."


def _detect_node_runtime_at_path(project_root: Path, runtime_root: Path) -> dict | None:
    package_json_path = runtime_root / "package.json"
    if not package_json_path.exists():
        return None
    try:
        package_json = json.loads(package_json_path.read_text(encoding='utf-8'))
    except Exception:
        package_json = {}

    scripts = package_json.get("scripts", {})
    run_command = None
    if scripts.get("dev"):
        run_command = "npm run dev"
    elif scripts.get("start"):
        run_command = "npm start"
    elif scripts.get("preview"):
        run_command = "npm run preview"

    rel_runtime_root = runtime_root.relative_to(project_root) if runtime_root != project_root else Path(".")
    entrypoint = "package.json" if rel_runtime_root == Path(".") else f"{rel_runtime_root.as_posix()}/package.json"
    return {
        "label": package_json.get("name") or runtime_root.name or project_root.name,
        "runtime_type": "node",
        "entrypoint": entrypoint,
        "run_command": run_command,
        "setup_command": _node_setup_command(runtime_root),
        "install_required": _node_install_required(runtime_root),
        "preview_url": _node_preview_url(runtime_root, scripts, run_command),
        "runtime_root": runtime_root.as_posix(),
    }


def _detect_django_runtime_at_path(project_root: Path, runtime_root: Path) -> dict | None:
    manage_py = runtime_root / "manage.py"
    if not manage_py.exists():
        return None
    requirements_file = runtime_root / "requirements.txt"
    python_cmd = _python_executable_command()
    port = _stable_runtime_port(runtime_root, start=8100)
    rel_runtime_root = runtime_root.relative_to(project_root) if runtime_root != project_root else Path(".")
    entrypoint = "manage.py" if rel_runtime_root == Path(".") else f"{rel_runtime_root.as_posix()}/manage.py"
    run_prefix = "" if rel_runtime_root == Path(".") else f"cd {rel_runtime_root.as_posix()} && "
    setup_prefix = "" if rel_runtime_root == Path(".") else f"cd {rel_runtime_root.as_posix()} && "
    return {
        "label": runtime_root.name or project_root.name,
        "runtime_type": "django",
        "entrypoint": entrypoint,
        "run_command": f"{run_prefix}{python_cmd} manage.py runserver 127.0.0.1:{port}",
        "setup_command": f"{setup_prefix}{python_cmd} -m pip install -r requirements.txt" if requirements_file.exists() else None,
        "install_required": _python_install_required(runtime_root),
        "preview_url": f"http://127.0.0.1:{port}",
        "runtime_root": runtime_root.as_posix(),
    }


def _combine_detected_runtime(project_root: Path, frontend_runtime: dict | None, backend_runtime: dict | None) -> dict:
    if frontend_runtime and backend_runtime:
        combined = dict(backend_runtime)
        combined.update({
            "label": f"{project_root.name} ({backend_runtime.get('runtime_type')} + {frontend_runtime.get('runtime_type')})",
            "runtime_type": backend_runtime.get("runtime_type") or frontend_runtime.get("runtime_type") or "unknown",
            "entrypoint": backend_runtime.get("entrypoint") or frontend_runtime.get("entrypoint"),
            "run_command": backend_runtime.get("run_command") or frontend_runtime.get("run_command"),
            "setup_command": backend_runtime.get("setup_command") or frontend_runtime.get("setup_command"),
            "install_required": bool(backend_runtime.get("install_required")) or bool(frontend_runtime.get("install_required")),
            "preview_url": frontend_runtime.get("preview_url") or backend_runtime.get("preview_url"),
            "secondary_runtime": frontend_runtime,
        })
        return combined
    return frontend_runtime or backend_runtime or {}


def detect_runtime(project_root: Path) -> dict:
    direct_node_runtime = _detect_node_runtime_at_path(project_root, project_root)
    if direct_node_runtime:
        return direct_node_runtime

    direct_django_runtime = _detect_django_runtime_at_path(project_root, project_root)
    if direct_django_runtime:
        return direct_django_runtime

    if (project_root / "main.py").exists() or (project_root / "app.py").exists():
        entrypoint = "main.py" if (project_root / "main.py").exists() else "app.py"
        requirements_file = project_root / "requirements.txt"
        python_cmd = _python_executable_command()
        run_command, preview_url = _detect_python_app_runtime(project_root, entrypoint, python_cmd)
        return {
            "label": project_root.name,
            "runtime_type": "python",
            "entrypoint": entrypoint,
            "run_command": run_command,
            "setup_command": f"{python_cmd} -m pip install -r requirements.txt" if requirements_file.exists() else None,
            "install_required": _python_install_required(project_root),
            "preview_url": preview_url,
        }

    if (project_root / "index.html").exists():
        python_cmd = _python_executable_command()
        port = _stable_runtime_port(project_root, start=4173)
        return {
            "label": project_root.name,
            "runtime_type": "static",
            "entrypoint": "index.html",
            "run_command": f"{python_cmd} -m http.server {port} --bind 127.0.0.1",
            "setup_command": None,
            "install_required": False,
            "preview_url": f"http://127.0.0.1:{port}",
        }

    frontend_runtime = None
    for subdir in ("frontend", "client", "web", "app", "ui"):
        candidate_root = project_root / subdir
        frontend_runtime = _detect_node_runtime_at_path(project_root, candidate_root)
        if frontend_runtime:
            break

    backend_runtime = None
    for subdir in ("backend", "server", "api", "src"):
        candidate_root = project_root / subdir
        backend_runtime = _detect_django_runtime_at_path(project_root, candidate_root)
        if backend_runtime:
            break

    combined_runtime = _combine_detected_runtime(project_root, frontend_runtime, backend_runtime)
    if combined_runtime:
        return combined_runtime

    return {
        "label": project_root.name,
        "runtime_type": "unknown",
        "entrypoint": None,
        "run_command": None,
        "setup_command": None,
        "install_required": False,
        "preview_url": None,
    }


def runtime_process_id(workspace_id: str) -> str:
    return f"{workspace_id}_runtime"


def setup_process_id(workspace_id: str) -> str:
    return f"{workspace_id}_setup"


def _runtime_response_payload(runtime: dict, process_id: str, sandbox, *, wait_for_preview: bool = False) -> dict:
    status = sandbox.get_status(process_id)
    payload = {
        **runtime,
        "process_id": process_id,
        "status": status,
        "ready": False,
        "preview_error": None,
        "sandbox": sandbox.details(),
    }
    preview_url = runtime.get("preview_url")

    if not preview_url or not status.get("running"):
        return payload

    if wait_for_preview:
        ready, preview_error = _wait_for_preview_ready(preview_url, sandbox, process_id)
        status = sandbox.get_status(process_id)
        payload["status"] = status
    else:
        ready, preview_error = _probe_preview_url(preview_url)

    payload["ready"] = ready
    payload["preview_error"] = preview_error
    return payload


def scan_local_folder(folder_path: str) -> str:
    base = Path(folder_path)
    if not base.exists() or not base.is_dir():
        return f"Path not found: {folder_path}"

    config_files = [
        "README.md", "readme.md", "package.json", "requirements.txt", "setup.py",
        "pyproject.toml", "Dockerfile", "docker-compose.yml", ".env.example",
        "pom.xml", "go.mod", "Cargo.toml", "angular.json", "next.config.js",
        "vite.config.js", "vite.config.ts", "webpack.config.js",
    ]

    result = ["=== FILE STRUCTURE ==="]
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        depth = len(Path(root).relative_to(base).parts)
        if depth > 3:
            dirs[:] = []
            continue
        indent = "  " * depth
        folder_name = Path(root).name if depth > 0 else base.name
        result.append(f"{indent}{folder_name}/")
        for filename in sorted(files)[:30]:
            result.append(f"{indent}  {filename}")

    result.append("\n=== KEY FILES ===")
    for filename in config_files:
        file_path = base / filename
        if not file_path.exists():
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")[:2000]
        except Exception:
            continue
        result.append(f"\n--- {filename} ---\n{content}")

    result.append("\n=== SAMPLE SOURCE FILES ===")
    source_exts = {".py", ".js", ".ts", ".tsx", ".go", ".java", ".rb", ".php", ".rs"}
    found = 0
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for filename in files:
            if found >= 3:
                break
            if Path(filename).suffix not in source_exts:
                continue
            file_path = Path(root) / filename
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:1500]
            except Exception:
                continue
            rel_path = file_path.relative_to(base)
            result.append(f"\n--- {rel_path} ---\n{content}")
            found += 1
        if found >= 3:
            break

    return "\n".join(result)[:8000]


def _read_text_if_exists(file_path: Path, limit: int = 5000) -> str:
    try:
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        logger.exception("Failed to read file during import inspection: %s", file_path)
    return ""


def _repo_name_from_github_url(github_url: str) -> str:
    cleaned = str(github_url or "").rstrip("/").split("/")[-1]
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    cleaned = re.sub(r"[-_]+", " ", cleaned).strip()
    return cleaned.title() if cleaned else "Imported Project"


def _detected_stack_for_path(project_root: Path) -> list[str]:
    detected: list[str] = []

    package_json = _read_text_if_exists(project_root / "package.json")
    frontend_package_json = _read_text_if_exists(project_root / "frontend" / "package.json")
    package_blob = "\n".join([package_json, frontend_package_json]).lower()

    requirements_blob = "\n".join([
        _read_text_if_exists(project_root / "requirements.txt"),
        _read_text_if_exists(project_root / "pyproject.toml"),
        _read_text_if_exists(project_root / "backend" / "requirements.txt"),
        _read_text_if_exists(project_root / "backend" / "pyproject.toml"),
    ]).lower()

    config_names = {path.name.lower() for path in project_root.glob("*")}
    config_names.update(path.name.lower() for path in (project_root / "frontend").glob("*") if (project_root / "frontend").exists())
    runtime = detect_runtime(project_root)
    runtime_type = str(runtime.get("runtime_type") or "").lower()

    if "next.config.js" in config_names or "next.config.mjs" in config_names or "next" in package_blob:
        detected.extend(["Next.js", "React", "Node.js"])
    elif "react" in package_blob:
        detected.extend(["React", "Node.js"])
    elif "vue" in package_blob:
        detected.extend(["Vue", "Node.js"])
    elif package_blob:
        detected.append("Node.js")

    if "express" in package_blob:
        detected.append("Express")
    if "tailwind" in package_blob or "tailwind.config.js" in config_names or "tailwind.config.ts" in config_names:
        detected.append("Tailwind")
    if "typescript" in package_blob or (project_root / "tsconfig.json").exists() or (project_root / "frontend" / "tsconfig.json").exists():
        detected.append("TypeScript")

    if (project_root / "manage.py").exists() or "django" in requirements_blob:
        detected.append("Django")
    elif "fastapi" in requirements_blob:
        detected.append("FastAPI")
    elif requirements_blob or runtime_type == "python":
        detected.append("Python")

    postgres_markers = [
        "postgres",
        "psycopg",
        "postgresql",
    ]
    combined_blob = "\n".join([
        package_blob,
        requirements_blob,
        _read_text_if_exists(project_root / ".env.example"),
        _read_text_if_exists(project_root / ".env"),
        _read_text_if_exists(project_root / "docker-compose.yml"),
    ]).lower()
    if any(marker in combined_blob for marker in postgres_markers):
        detected.append("PostgreSQL")

    if runtime_type == "node" and "Node.js" not in detected:
        detected.append("Node.js")
    if runtime_type == "static" and not detected:
        detected.append("HTML/CSS/JS")

    return _normalize_tech_stack(detected)


def _build_import_inspection(project_root: Path, source_type: str, idea: str = "", source_label: str = "") -> dict:
    project_root = _normalize_path(str(project_root))
    scan_summary = scan_local_folder(str(project_root))
    detected_stack = _detected_stack_for_path(project_root)
    suggestion_seed_parts = [
        idea.strip(),
        source_label.strip(),
        f"Project root: {project_root.name}",
        scan_summary[:2400],
    ]
    suggestion_seed = "\n\n".join(part for part in suggestion_seed_parts if part)
    suggestion = _suggest_project_details(suggestion_seed, source_type, detected_stack)
    runtime = detect_runtime(project_root)

    suggested_name = suggestion.get("name") or project_root.name.replace("-", " ").replace("_", " ").title()
    if source_type == "github" and source_label:
        repo_name = _repo_name_from_github_url(source_label)
        if repo_name:
            suggested_name = repo_name

    lines = [line for line in scan_summary.splitlines() if line.strip()]
    structure_preview = "\n".join(lines[:24])

    return {
        "name": suggested_name,
        "description": suggestion.get("description") or f"Imported from {source_type} source.",
        "tech_stack": suggestion.get("tech_stack") or detected_stack,
        "detected_stack": detected_stack,
        "resolved_path": str(project_root),
        "root_name": project_root.name,
        "runtime": runtime,
        "structure_preview": structure_preview,
        "source_summary": scan_summary[:3200],
    }


def _pick_local_folder() -> str | None:
    if sys.platform.startswith("win"):
        powershell_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$dialog.Description = 'Select a project folder for DevHub'; "
            "$dialog.ShowNewFolderButton = $false; "
            "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
            "Write-Output $dialog.SelectedPath }"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", powershell_script],
                capture_output=True,
                text=True,
                timeout=120,
            )
            selected = result.stdout.strip()
            if result.returncode == 0 and selected:
                return selected
        except Exception:
            logger.exception("PowerShell folder picker failed")

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="Select a project folder for DevHub")
        root.destroy()
        return selected or None
    except Exception:
        logger.exception("Tk folder picker failed")
        return None


def _devhub_meta_dir(workspace_path: Path) -> Path:
    path = workspace_path / DEVHUB_META_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _project_memory_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / PROJECT_MEMORY_FILE


def _project_instructions_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / PROJECT_INSTRUCTIONS_FILE


def _deep_docs_progress_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / "deep-docs-progress.json"


def _write_deep_docs_progress(workspace_path: Path, payload: dict) -> None:
    path = _deep_docs_progress_path(workspace_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    progress = dict(payload)
    progress["updated_at"] = timezone.now().isoformat()
    serialized = json.dumps(progress)
    temp_fd, temp_path = tempfile.mkstemp(prefix="deep-docs-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)

        for attempt in range(5):
            try:
                os.replace(temp_path, path)
                temp_path = None
                return
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))

        path.write_text(serialized, encoding="utf-8")
        temp_path = None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _safe_write_deep_docs_progress(workspace_path: Path, payload: dict) -> None:
    try:
        _write_deep_docs_progress(workspace_path, payload)
    except Exception:
        logger.exception("Failed to write deep docs progress for %s", workspace_path)


def _read_deep_docs_progress(workspace_path: Path) -> dict | None:
    path = _deep_docs_progress_path(workspace_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read deep docs progress from %s", path)
        return None


BLUEPRINT_SECTION_LABELS = {
    'design_doc': 'Design Doc',
    'overview': 'Overview',
    'repository': 'Repository',
    'services': 'Services & Components',
    'api': 'API Reference',
    'database': 'Database Schema',
    'workflows': 'Workflows & Sequences',
    'setup': 'Setup & Environment',
    'quality': 'Quality & Security',
    'knowledge': 'Knowledge Base',
}

BLUEPRINT_SECTION_FIELDS = {
    'design_doc': ['design_document_markdown', 'design_document_sections'],
    'overview': ['project_summary', 'architecture_overview', 'mermaid_architecture', 'mermaid_service_dependencies', 'data_flow', 'tech_stack_details', 'feature_inventory', 'sdlc_pipeline', 'overview_project_health', 'overview_current_risks', 'overview_runtime_entrypoints', 'overview_read_first', 'overview_recent_changes', 'overview_next_steps'],
    'repository': ['directory_guide', 'repository_map', 'repo_tree', 'repo_tree_nodes', 'readme_excerpt', 'instruction_files', 'file_structure_visualizer', 'change_guide'],
    'services': ['services', 'key_components', 'integration_points'],
    'api': ['api_endpoints'],
    'database': ['database_schema', 'mermaid_erd'],
    'workflows': ['sequence_flows', 'common_workflows'],
    'setup': ['setup_steps', 'environment_variables', 'onboarding_checklist'],
    'quality': ['security_considerations', 'performance_notes', 'testing_strategy', 'code_quality_standards'],
    'knowledge': ['key_concepts', 'faq', 'gotchas'],
}

LLM_BLUEPRINT_SECTION_KEYS = {'overview', 'services', 'api', 'database', 'workflows', 'setup', 'quality', 'knowledge'}
TOKEN_FREE_BLUEPRINT_SECTION_KEYS = {'design_doc', 'repository', 'api', 'setup', 'quality', 'knowledge'}


def _slice_blueprint_section(blueprint: dict, section_key: str) -> dict[str, Any]:
    return {
        field: blueprint.get(field)
        for field in BLUEPRINT_SECTION_FIELDS.get(section_key, [])
        if field in blueprint
    }


def _persist_blueprint_state(project: Project, blueprint: dict) -> None:
    project.blueprint = blueprint
    project.save(update_fields=['blueprint'])


def _render_project_features_summary(project: Project, limit: int = 10) -> str:
    lines = []
    features = Feature.objects.filter(project=project).order_by('-created_at')[:limit]
    for feature in features:
        lines.append(f"- {feature.title} [{feature.status}]")
        if feature.description:
            lines.append(f"  Description: {feature.description[:240]}")
        spec = feature.spec or {}
        if spec.get('technical_approach'):
            lines.append(f"  Approach: {str(spec['technical_approach'])[:240]}")
    return "\n".join(lines) if lines else "No active DevHub work items are recorded yet."


def _render_recent_changes_summary(project: Project, limit: int = 8) -> str:
    lines = []
    changesets = Changeset.objects.filter(project=project).order_by('-created_at')[:limit]
    for changeset in changesets:
        file_list = list(changeset.files_changed.values_list('file_path', flat=True)[:8])
        lines.append(f"- {changeset.title} [{changeset.status}]")
        if file_list:
            lines.append(f"  Files: {', '.join(file_list)}")
    return "\n".join(lines) if lines else "No recorded changesets yet."


def _build_default_project_memory(project: Project, workspace_path: Path) -> str:
    runtime = detect_runtime(workspace_path)
    tech = ", ".join(project.tech_stack or []) or "Unknown"
    blueprint = project.blueprint or {}
    setup_steps = blueprint.get('setup_steps') or []
    setup_text = "\n".join(f"- {step if isinstance(step, str) else step.get('step', '')}" for step in setup_steps[:5]) or "- No setup guidance yet."
    architecture = str(blueprint.get('architecture_overview') or project.description or "No architecture summary yet.")[:1200]

    return f"""# Project Memory

## Project
- Name: {project.name}
- Tech Stack: {tech}
- Runtime: {runtime.get('runtime_type') or 'unknown'}
- Run Command: {runtime.get('run_command') or 'unknown'}

## Architecture Summary
{architecture}

## Setup Notes
{setup_text}

## Known Features
{_render_project_features_summary(project)}

## Recent Changes
{_render_recent_changes_summary(project)}
"""


def _build_default_project_instructions(project: Project, workspace_path: Path) -> str:
    runtime = detect_runtime(workspace_path)
    tech = ", ".join(project.tech_stack or []) or "Unknown"
    return f"""# DevHub Instructions

Project: {project.name}
Tech Stack: {tech}
Runtime: {runtime.get('runtime_type') or 'unknown'}

## Guidance
- Preserve the existing project structure and runtime conventions.
- Prefer editing existing files over creating duplicate parallel implementations.
- Keep Blueprint, Features, Pipeline, and Onboarding aligned with real code changes.
- Update related UI, logic, styles, and runtime wiring together when behavior changes.

## Product Expectations
- This project should remain runnable after changes.
- New features should reflect the current codebase, not a generic starter.
- Favor minimal, targeted edits and reuse existing architecture patterns.

## Notes
- Add project-specific architecture rules, conventions, and deployment constraints here over time.
"""


def _read_project_memory(project: Project, workspace_path: Path) -> str:
    memory_path = _project_memory_path(workspace_path)
    if not memory_path.exists():
        memory_path.write_text(_build_default_project_memory(project, workspace_path), encoding='utf-8')
    return memory_path.read_text(encoding='utf-8', errors='ignore')


def _read_project_instructions(project: Project, workspace_path: Path) -> str:
    instructions_path = _project_instructions_path(workspace_path)
    if not instructions_path.exists():
        instructions_path.write_text(_build_default_project_instructions(project, workspace_path), encoding='utf-8')
    return instructions_path.read_text(encoding='utf-8', errors='ignore')


def _write_project_memory(project: Project, workspace_path: Path, content: str):
    memory_path = _project_memory_path(workspace_path)
    memory_path.write_text(content, encoding='utf-8')


def _update_project_memory(project: Project, workspace_path: Path, request_text: str, applied_files: list[str], memory_updates: list[str] | None = None):
    current_memory = _read_project_memory(project, workspace_path)
    updates = "\n".join(f"- {item}" for item in (memory_updates or []) if item)
    if not updates:
        updates = "- No planner-authored memory updates."
    changed = ", ".join(applied_files) if applied_files else "No files changed."
    appended = f"""

## Latest Update
- Request: {request_text}
- Changed Files: {changed}

### Durable Notes
{updates}

## Recent Changes
{_render_recent_changes_summary(project)}
"""
    _write_project_memory(project, workspace_path, (current_memory[:14000] + appended)[:18000])


def _workspace_file_inventory(workspace_path: Path, limit: int = 400) -> str:
    items = []
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for filename in sorted(files):
            path = Path(root) / filename
            rel_path = str(path.relative_to(workspace_path)).replace('\\', '/')
            if rel_path.startswith(f"{DEVHUB_META_DIR}/"):
                continue
            items.append(rel_path)
            if len(items) >= limit:
                return "\n".join(items)
    return "\n".join(items)


def _recent_chat_history(project: Project, limit: int = 12) -> str:
    messages = list(ChatMessage.objects.filter(project=project).order_by('-created_at')[:limit].values('role', 'content'))
    messages.reverse()
    if not messages:
        return "No recent chat history."
    return "\n".join(f"- {item['role']}: {item['content'][:400]}" for item in messages)


def _normalize_mermaid_chart(chart: str, diagram_type: str = "graph") -> str:
    text = str(chart or "").replace("\\n", "\n").strip()
    if not text:
        return ""

    def _escape_graph_label_text(value: str) -> str:
        label = html.unescape(str(value or ""))
        label = label.replace("\\n", " ")
        label = label.replace("\r", " ").replace("\n", " ")
        label = re.sub(r"\s+", " ", label).strip()
        label = label.replace("\\", "\\\\").replace('"', '\\"')
        return label

    def _rewrite_graph_label(match: re.Match[str], template: str) -> str:
        node_id = str(match.group("id") or "").strip()
        raw_label = str(match.group("label") or "").strip()
        if not node_id or not raw_label:
            return match.group(0)
        if raw_label.startswith('"') and raw_label.endswith('"'):
            return match.group(0)
        return template.format(id=node_id, label=_escape_graph_label_text(raw_label))

    def _normalize_graph_line(line: str) -> str:
        patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\[\((?P<label>[^"\n][^)\n]*?)\)\]'), '{id}[("{label}")]'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\[\[(?P<label>[^"\n][^\]\n]*?)\]\]'), '{id}[["{label}"]]'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\(\((?P<label>[^"\n][^)\n]*?)\)\)'), '{id}(("{label}"))'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\(\[(?P<label>[^"\n][^\]\n]*?)\]\)'), '{id}(["{label}"])'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\[(?P<label>[^"\[(\n][^\]\n]*?)\]'), '{id}["{label}"]'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\((?P<label>[^"\[(\n][^)\n]*?)\)'), '{id}("{label}")'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\{(?P<label>[^"\n][^}\n]*?)\}'), '{id}{{"{label}"}}'),
        ]

        normalized = str(line or "")
        for pattern, template in patterns:
            normalized = pattern.sub(lambda match, tpl=template: _rewrite_graph_label(match, tpl), normalized)
        return normalized

    if diagram_type == "erd":
        text = re.sub(r'^\s*erDiagram\s*;?', 'erDiagram\n', text, flags=re.IGNORECASE)
        text = re.sub(r';\s*', '\n', text)
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if not lines or lines[0].strip().lower() != 'erdiagram':
            lines.insert(0, 'erDiagram')
        return "\n".join(lines)

    if diagram_type == "sequence":
        def _escape_sequence_label_text(value: str) -> str:
            text = html.unescape(str(value or ""))
            text = text.replace("\\n", " newline ")
            text = text.replace("\r", "").replace("\n", " newline ")
            text = re.sub(r"<([^>]+)>", r" \1 ", text)
            text = re.sub(r"\[([^\]]+)\]", r" \1 ", text)
            text = re.sub(r"[{}()]", " ", text)
            text = text.replace("&", " and ")
            text = re.sub(r"""["'`]""", "", text)
            text = re.sub(r"[^A-Za-z0-9 _-]+", " ", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()

        def _starts_sequence_statement(line: str) -> bool:
            stripped = str(line or "").strip()
            if not stripped:
                return False
            if stripped.lower() == "sequencediagram":
                return True
            if re.match(r"^(participant|actor|note|activate|deactivate|autonumber|title|link|box|end|alt|else|opt|loop|par|and|critical|break|rect)\b", stripped, re.IGNORECASE):
                return True
            return bool(re.match(r"^[A-Za-z0-9_.()[\]`\"'/-]+\s*(?:-->>|->>|-->|->|<<--|<<->>|<<->|--x|x--)", stripped))

        text = re.sub(r'^\s*sequenceDiagram\s*;?', 'sequenceDiagram\n', text, flags=re.IGNORECASE)
        text = re.sub(r';\s*', '\n', text)
        raw_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        merged_lines: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not merged_lines or _starts_sequence_statement(stripped):
                merged_lines.append(stripped)
            else:
                merged_lines[-1] = f"{merged_lines[-1]}\\n{stripped}"
        if not merged_lines or merged_lines[0].strip().lower() != 'sequencediagram':
            merged_lines.insert(0, 'sequenceDiagram')
        sanitized_lines: list[str] = []
        for line in merged_lines:
            if line.strip().lower() == "sequencediagram":
                sanitized_lines.append("sequenceDiagram")
                continue
            if ":" in line and re.search(r"(?:-->>|->>|-->|->|<<--|<<->>|<<->|--x|x--)", line):
                prefix, label = line.split(":", 1)
                sanitized_lines.append(f"{prefix}: {_escape_sequence_label_text(label.strip())}")
            else:
                sanitized_lines.append(line)
        return "\n".join(sanitized_lines)

    if text.lower().startswith('graph ') or text.lower().startswith('flowchart '):
        text = re.sub(r';\s*', '\n', text)
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        return "\n".join(_normalize_graph_line(line) for line in lines)
    return text


def _read_workspace_text(workspace_path: Path | None, rel_path: str) -> str:
    if not workspace_path:
        return ""
    target = workspace_path / rel_path
    if not target.exists() or not target.is_file():
        return ""
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _content_has_all(text: str, *needles: str) -> bool:
    haystack = str(text or "").lower()
    return all(str(needle or "").lower() in haystack for needle in needles if needle)


def _content_has_any(text: str, *needles: str) -> bool:
    haystack = str(text or "").lower()
    return any(str(needle or "").lower() in haystack for needle in needles if needle)


def _workflow_touchpoints(workspace_path: Path, rel_paths: dict[str, str], *keys: str) -> list[str]:
    touchpoints: list[str] = []
    seen: set[str] = set()
    for key in keys:
        rel_path = rel_paths.get(key)
        if not rel_path or rel_path in seen:
            continue
        if (workspace_path / rel_path).exists():
            touchpoints.append(rel_path)
            seen.add(rel_path)
    return touchpoints


def _matches_devhub_workflow_signature(files: dict[str, str]) -> bool:
    lowered = {key: str(value or "").lower() for key, value in files.items()}
    return (
        _content_has_any(
            lowered.get("codeworkspace", ""),
            "/workspace/${workspaceid}/spawn/",
            "/workspace/${workspaceid}/runtime/",
            "/workspace/${workspaceid}/fs/",
        )
        and _content_has_any(
            lowered.get("projectview", ""),
            "/projects/${id}/agent/deep-docs/",
            "/projects/${id}/pipeline/action/",
            "/projects/${id}/documentation/",
        )
        and _content_has_any(
            lowered.get("views", ""),
            "def workspace_spawn",
            "def workspace_runtime",
            "def project_chat",
            "def project_documentation",
        )
    )


def _build_evidence_backed_workflows(workspace_path: Path | None) -> tuple[list[dict], list[dict]]:
    if not workspace_path or not workspace_path.is_dir():
        return [], []

    rel_paths = {
        "codeworkspace": "frontend/src/components/CodeWorkspace.tsx",
        "documentationpanel": "frontend/src/components/DocumentationPanel.tsx",
        "projectchat": "frontend/src/components/ProjectChatPanel.tsx",
        "projectview": "frontend/src/pages/ProjectView.tsx",
        "dashboard": "frontend/src/pages/Dashboard.tsx",
        "views": "backend/api/views.py",
        "urls": "backend/api/urls.py",
        "consumers": "backend/editor/consumers.py",
        "routing": "backend/editor/routing.py",
        "executor": "backend/sandbox/executor.py",
        "deepdocs": "backend/agents/deep_documentation.py",
        "workspace_agent": "backend/agents/workspace.py",
    }
    files = {key: _read_workspace_text(workspace_path, rel_path) for key, rel_path in rel_paths.items()}
    lowered = {key: value.lower() for key, value in files.items()}

    # This evidence override is intentionally reserved for repos that expose the
    # DevHub workspace/project workflow surface. Other repositories should keep
    # the generic LLM-generated workflow section instead of inheriting these
    # product-specific flows.
    if not _matches_devhub_workflow_signature(files):
        return [], []

    sequence_flows: list[dict] = []
    common_workflows: list[dict] = []
    sequence_titles: set[str] = set()
    workflow_titles: set[str] = set()

    def add_sequence(flow: dict) -> None:
        title = str(flow.get("title") or "").strip()
        if not title or title in sequence_titles:
            return
        sequence_titles.add(title)
        sequence_flows.append(flow)

    def add_workflow(flow: dict) -> None:
        title = str(flow.get("title") or "").strip()
        if not title or title in workflow_titles:
            return
        workflow_titles.add(title)
        common_workflows.append(flow)

    if (
        _content_has_all(
            lowered["codeworkspace"],
            "/workspace/${workspaceid}/spawn/",
            "new websocket(",
            "process/${pid}/",
            "json.stringify({ input: data })",
        )
        and _content_has_all(
            lowered["consumers"],
            "class processconsumer",
            "poll_process_output",
            "sandbox.send_input(self.process_id",
            "sandbox.get_output(self.process_id)",
            "sandbox.get_status(self.process_id)",
        )
        and _content_has_all(
            lowered["executor"],
            "def run_command",
            "def get_output",
            "def get_status",
            "def send_input",
        )
        and _content_has_all(
            lowered["views"],
            "def workspace_spawn",
            "sandbox.run_command(",
        )
    ):
        add_sequence(
            {
                "title": "Terminal Process Execution and I/O Streaming",
                "description": (
                    "This flow starts when CodeWorkspace opens the terminal and POSTs to the workspace spawn endpoint. "
                    "The API asks SandboxManager to start a subprocess, returns a process id, and the frontend then opens "
                    "a process WebSocket. ProcessConsumer polls sandbox status/output and streams stdout or stderr back to "
                    "the terminal while forwarding user input into SandboxManager.send_input."
                ),
                "mermaid_sequence": "\n".join(
                    [
                        "sequenceDiagram",
                        "participant CodeWorkspace",
                        "participant API",
                        "participant SandboxManager",
                        "participant ProcessConsumer",
                        "CodeWorkspace->>API: POST workspace spawn",
                        "API->>SandboxManager: run_command process_id command work_dir",
                        "SandboxManager-->>API: process handle and process id",
                        "API-->>CodeWorkspace: process_id",
                        "CodeWorkspace->>ProcessConsumer: open process websocket",
                        "loop Polling output",
                        "ProcessConsumer->>SandboxManager: get_status and get_output",
                        "SandboxManager-->>ProcessConsumer: stdout stderr and status",
                        "ProcessConsumer-->>CodeWorkspace: send output and status",
                        "end",
                        "CodeWorkspace->>ProcessConsumer: send input command text",
                        "ProcessConsumer->>SandboxManager: send_input process_id input",
                    ]
                ),
                "touchpoints": [
                    *_workflow_touchpoints(
                        workspace_path,
                        rel_paths,
                        "codeworkspace",
                        "views",
                        "consumers",
                        "routing",
                        "executor",
                    ),
                ],
            }
        )
        add_workflow(
            {
                "title": "Interacting with the Workspace Terminal",
                "steps": [
                    "Step 1: Open CodeWorkspace; it auto-calls POST /api/workspace/<workspace_id>/spawn/ with {command: 'cmd.exe'} from frontend/src/components/CodeWorkspace.tsx.",
                    "Step 2: backend/api/views.py creates a process id and delegates the command to sandbox.run_command in backend/sandbox/executor.py.",
                    "Step 3: The frontend opens ws://localhost:8000/ws/workspace/<workspace_id>/process/<process_id>/ and ProcessConsumer starts poll_process_output().",
                    "Step 4: Typing in the terminal sends JSON {input: data} over the socket and ProcessConsumer forwards it to SandboxManager.send_input().",
                    "Step 5: Output and status are polled with sandbox.get_output() and sandbox.get_status() and streamed back into the terminal UI.",
                ],
            }
        )

    if (
        _content_has_all(
            lowered["codeworkspace"],
            "/workspace/${workspaceid}/fs/?path=",
            "const loadfile = async",
            "const savefile = async",
            "/workspace/${workspaceid}/fs/",
        )
        and _content_has_all(
            lowered["views"],
            "def workspace_fs",
            "workspace_manager.write_file(",
        )
    ):
        add_sequence(
            {
                "title": "Workspace File Read and Save",
                "description": (
                    "This flow covers how CodeWorkspace browses directories, loads a file into the editor, and persists changes. "
                    "The frontend requests file contents through the workspace filesystem endpoint, the backend resolves and reads the "
                    "target path directly for GET requests, and then POSTs the updated content back to backend/api/views.py, which writes "
                    "the file through workspace_manager."
                ),
                "mermaid_sequence": "\n".join(
                    [
                        "sequenceDiagram",
                        "participant CodeWorkspace",
                        "participant API",
                        "participant WorkspaceManager",
                        "CodeWorkspace->>API: GET workspace fs path file",
                        "API->>API: resolve workspace path and read file or directory",
                        "API-->>CodeWorkspace: file content or directory items",
                        "CodeWorkspace->>CodeWorkspace: edit content in Monaco",
                        "CodeWorkspace->>API: POST workspace fs path content",
                        "API->>WorkspaceManager: write file to workspace",
                        "WorkspaceManager-->>API: save success",
                        "API-->>CodeWorkspace: save complete",
                    ]
                ),
                "touchpoints": [
                    *_workflow_touchpoints(
                        workspace_path,
                        rel_paths,
                        "codeworkspace",
                        "views",
                        "workspace_agent",
                    ),
                ],
            }
        )
        add_workflow(
            {
                "title": "Editing a File in the Workspace",
                "steps": [
                    "Step 1: Expand the tree or click a file in frontend/src/components/CodeWorkspace.tsx, which calls GET /api/workspace/<workspace_id>/fs/?path=<file_path>.",
                    "Step 2: backend/api/views.py resolves the workspace path and returns either directory entries or the file content.",
                    "Step 3: CodeWorkspace loads the returned content into the editor and keeps local edits in component state.",
                    "Step 4: Click Save File to POST /api/workspace/<workspace_id>/fs/ with {path, content}.",
                    "Step 5: backend/api/views.py persists the new content via workspace_manager.write_file and the workspace view refreshes as needed.",
                ],
            }
        )

    if (
        _content_has_all(
            lowered["codeworkspace"],
            "fetchruntime",
            "/workspace/${workspaceid}/runtime/",
            "const runproject = async",
            "const stopproject = async",
        )
        and _content_has_any(
            lowered["codeworkspace"],
            "connectsocket(runtime.process_id",
            "runtime?.process_id && runtime.status?.running",
        )
        and _content_has_all(
            lowered["views"],
            "def workspace_runtime",
            "detect_runtime(",
            "runtime_process_id(",
            "_runtime_response_payload(",
            "sandbox.run_command(",
        )
    ):
        add_sequence(
            {
                "title": "Project Runtime Execution and Preview Streaming",
                "description": (
                    "This flow powers the Run Project and Stop Project controls in CodeWorkspace. "
                    "The frontend asks the runtime endpoint to detect or reuse the run command, the backend launches the managed "
                    "process through SandboxManager, and CodeWorkspace then streams stdout into the App Output panel while it "
                    "waits for the preview URL to become healthy."
                ),
                "mermaid_sequence": "\n".join(
                    [
                        "sequenceDiagram",
                        "participant CodeWorkspace",
                        "participant API",
                        "participant SandboxManager",
                        "participant ProcessConsumer",
                        "CodeWorkspace->>API: POST workspace runtime",
                        "API->>API: detect runtime and preview URL",
                        "API->>SandboxManager: run_command runtime process",
                        "SandboxManager-->>API: process status and handle",
                        "API-->>CodeWorkspace: runtime payload with process_id preview_url ready",
                        "CodeWorkspace->>ProcessConsumer: open runtime process websocket",
                        "ProcessConsumer-->>CodeWorkspace: stream stdout stderr and status",
                        "CodeWorkspace->>API: DELETE workspace runtime when stopping",
                        "API->>SandboxManager: kill_process runtime process",
                    ]
                ),
                "touchpoints": [
                    *_workflow_touchpoints(
                        workspace_path,
                        rel_paths,
                        "codeworkspace",
                        "views",
                        "consumers",
                        "routing",
                        "executor",
                    ),
                ],
            }
        )
        add_workflow(
            {
                "title": "Running the Project Preview",
                "steps": [
                    "Step 1: Click Run Project in frontend/src/components/CodeWorkspace.tsx, which POSTs to /api/workspace/<workspace_id>/runtime/.",
                    "Step 2: backend/api/views.py calls detect_runtime(), chooses the runtime process id, and starts or refreshes the process through sandbox.run_command().",
                    "Step 3: The runtime response includes process_id, run_command, preview_url, and ready state so CodeWorkspace can switch the bottom panel to App Output.",
                    "Step 4: CodeWorkspace opens the runtime process WebSocket and streams output through ProcessConsumer while polling preview readiness.",
                    "Step 5: Click Stop Project to DELETE /api/workspace/<workspace_id>/runtime/ and terminate the managed runtime process.",
                ],
            }
        )

    if (
        _content_has_all(
            lowered["codeworkspace"],
            "/workspace/${workspaceid}/setup/",
            "const runsetup = async",
            "setsetuprunning(true)",
        )
        and _content_has_any(
            lowered["codeworkspace"],
            "connectsocket(`${workspaceid}_setup`",
            "connectsocket(`${workspaceid}_setup`,",
        )
        and _content_has_all(
            lowered["views"],
            "def workspace_setup",
            "setup_process_id(",
            "sandbox.run_command(",
        )
    ):
        add_sequence(
            {
                "title": "Workspace Setup Command Execution",
                "description": (
                    "This flow runs the detected setup command for the current workspace. "
                    "CodeWorkspace POSTs to the setup endpoint, the backend launches the setup process under a stable setup "
                    "process id, and the frontend reuses ProcessConsumer to stream setup output until the command exits."
                ),
                "mermaid_sequence": "\n".join(
                    [
                        "sequenceDiagram",
                        "participant CodeWorkspace",
                        "participant API",
                        "participant SandboxManager",
                        "participant ProcessConsumer",
                        "CodeWorkspace->>API: POST workspace setup",
                        "API->>API: detect setup command",
                        "API->>SandboxManager: run_command setup process",
                        "SandboxManager-->>API: process status",
                        "API-->>CodeWorkspace: setup process_id and command",
                        "CodeWorkspace->>ProcessConsumer: open setup process websocket",
                        "ProcessConsumer-->>CodeWorkspace: stream setup output and status",
                    ]
                ),
                "touchpoints": [
                    *_workflow_touchpoints(
                        workspace_path,
                        rel_paths,
                        "codeworkspace",
                        "views",
                        "consumers",
                        "routing",
                        "executor",
                    ),
                ],
            }
        )
        add_workflow(
            {
                "title": "Running Workspace Setup",
                "steps": [
                    "Step 1: Click Setup in frontend/src/components/CodeWorkspace.tsx when the detected runtime exposes a setup_command.",
                    "Step 2: CodeWorkspace POSTs to /api/workspace/<workspace_id>/setup/ and clears the setup output panel state.",
                    "Step 3: backend/api/views.py derives the stable setup process id and launches the setup command through sandbox.run_command().",
                    "Step 4: CodeWorkspace connects to the setup process WebSocket and appends streamed output into the App Output panel.",
                    "Step 5: When ProcessConsumer reports that the setup process is no longer running, the UI clears the setup-running state automatically.",
                ],
            }
        )

    if (
        _content_has_all(
            lowered["projectview"],
            "/projects/${id}/features/",
            "/projects/${id}/pipeline/action/",
            "const createfeature = async",
            "setimplementationrun(",
        )
        and _content_has_any(
            lowered["projectview"],
            "const runaction = async",
            "const pipelineaction = async",
        )
        and _content_has_any(
            lowered["projectview"],
            "implementationpollref.current = window.setinterval(",
            "window.setinterval(() => {",
        )
        and _content_has_all(
            lowered["views"],
            "def project_features",
            "def pipeline_action",
            "def implement_feature_sync",
            "thread = threading.thread(target=implement_feature_sync",
            "featurehistory.objects.create(feature=feature, stage='development', action='implementation_started'",
        )
    ):
        add_sequence(
            {
                "title": "Feature Implementation and Progress Tracking",
                "description": (
                    "This flow begins when ProjectView creates a work item or sends a pipeline action for an existing feature. "
                    "The backend persists the feature, starts async spec generation or implementation work, and ProjectView keeps polling "
                    "the project state every 2.5 seconds until the feature history reflects completion."
                ),
                "mermaid_sequence": "\n".join(
                    [
                        "sequenceDiagram",
                        "participant ProjectView",
                        "participant API",
                        "participant FeaturePipeline",
                        "ProjectView->>API: POST projects project_id features",
                        "API->>FeaturePipeline: create feature and start spec generation",
                        "FeaturePipeline-->>ProjectView: feature created",
                        "ProjectView->>API: POST projects project_id pipeline action implement",
                        "API->>FeaturePipeline: start implementation flow",
                        "loop Poll project state every 2.5 seconds",
                        "ProjectView->>API: GET projects project_id",
                        "API-->>ProjectView: updated feature history and status",
                        "end",
                        "FeaturePipeline-->>ProjectView: implementation completed",
                    ]
                ),
                "touchpoints": [
                    *_workflow_touchpoints(
                        workspace_path,
                        rel_paths,
                        "projectview",
                        "views",
                        "urls",
                    ),
                ],
            }
        )
        add_workflow(
            {
                "title": "Advancing a Feature through the Pipeline",
                "steps": [
                    "Step 1: Create a work item in ProjectView by POSTing to /api/projects/<project_id>/features/ with a title and description.",
                    "Step 2: backend/api/views.py stores the Feature record and starts generate_feature_spec_sync in a background thread.",
                    "Step 3: Use POST /api/projects/<project_id>/pipeline/action/ to approve, advance, or implement the feature.",
                    "Step 4: ProjectView starts its implementation polling loop and refreshes the project every 2.5 seconds.",
                    "Step 5: Watch feature status and pipeline history update until the implementation run completes.",
                ],
            }
        )

    if (
        _content_has_all(
            lowered["projectview"],
            "const startagent = async",
            "/projects/${id}/agent/deep-docs/",
            "/projects/${id}/agent/deep-docs/progress/",
            "applydeepdocsprogressevent",
        )
        and _content_has_any(
            lowered["projectview"],
            "response.body?.getreader()",
            "buffer.split('\\n')",
        )
        and _content_has_all(
            lowered["views"],
            "def deep_documentation_stream",
            "def deep_documentation_progress",
            "streaminghttpresponse",
            "_safe_write_deep_docs_progress(",
        )
        and _content_has_all(
            lowered["deepdocs"],
            "class deepdocumentationagent",
            "def generate_all_sections",
            "def generate_section",
        )
    ):
        add_sequence(
            {
                "title": "AI Deep Documentation Generation",
                "description": (
                    "This flow powers Blueprint regeneration. ProjectView POSTs to the deep documentation stream endpoint, "
                    "keeps a secondary polling loop against the progress endpoint, and incrementally applies section updates "
                    "as DeepDocumentationAgent completes each section."
                ),
                "mermaid_sequence": "\n".join(
                    [
                        "sequenceDiagram",
                        "participant ProjectView",
                        "participant API",
                        "participant DeepDocumentationAgent",
                        "ProjectView->>API: POST projects project_id agent deep-docs",
                        "API->>DeepDocumentationAgent: start section generation",
                        "loop Poll progress",
                        "ProjectView->>API: GET projects project_id agent deep-docs progress",
                        "API-->>ProjectView: status running section progress",
                        "end",
                        "DeepDocumentationAgent-->>API: blueprint section updates",
                        "API-->>ProjectView: stream completed sections",
                    ]
                ),
                "touchpoints": [
                    *_workflow_touchpoints(
                        workspace_path,
                        rel_paths,
                        "projectview",
                        "views",
                        "deepdocs",
                        "urls",
                    ),
                ],
            }
        )
        add_workflow(
            {
                "title": "Regenerating Blueprint Documentation",
                "steps": [
                    "Step 1: Click Regenerate Blueprint or a section-specific regenerate button in ProjectView.",
                    "Step 2: The frontend POSTs to /api/projects/<project_id>/agent/deep-docs/ and starts polling /api/projects/<project_id>/agent/deep-docs/progress/ every second.",
                    "Step 3: backend/api/views.py streams section events from DeepDocumentationAgent as each Blueprint section finishes.",
                    "Step 4: ProjectView applies progress updates through applyDeepDocsProgressEvent and merges section payloads into local state.",
                    "Step 5: When the stream completes, the refreshed Blueprint becomes the new persisted project documentation snapshot.",
                ],
            }
        )

    if (
        _content_has_all(
            lowered["projectview"],
            "const generatedocumentation = async",
            "/projects/${id}/documentation/",
        )
        and _content_has_any(
            lowered["documentationpanel"],
            "generate codebase reference",
            "regenerate",
            "ongenerate",
        )
        and _content_has_all(
            lowered["views"],
            "def project_documentation",
            "generate_codebase_reference_sync(project)",
            "_documentation_run_payload(",
        )
    ):
        add_sequence(
            {
                "title": "Codebase Reference Documentation Generation",
                "description": (
                    "This flow powers the Docs panel reference generation. "
                    "ProjectView triggers the documentation endpoint, the backend runs the synchronous codebase reference generator "
                    "against the live workspace, persists the latest DocumentationRun payload, and then the frontend refreshes the project "
                    "to render the generated sections."
                ),
                "mermaid_sequence": "\n".join(
                    [
                        "sequenceDiagram",
                        "participant DocumentationPanel",
                        "participant ProjectView",
                        "participant API",
                        "participant DocumentationGenerator",
                        "DocumentationPanel->>ProjectView: onGenerate",
                        "ProjectView->>API: POST projects project_id documentation",
                        "API->>DocumentationGenerator: generate_codebase_reference_sync",
                        "DocumentationGenerator-->>API: DocumentationRun and sections",
                        "API-->>ProjectView: documentation payload",
                        "ProjectView->>API: GET projects project_id refresh state",
                    ]
                ),
                "touchpoints": [
                    *_workflow_touchpoints(
                        workspace_path,
                        rel_paths,
                        "documentationpanel",
                        "projectview",
                        "views",
                        "urls",
                    ),
                ],
            }
        )
        add_workflow(
            {
                "title": "Generating the Codebase Reference",
                "steps": [
                    "Step 1: Open the Docs tab and click Generate Codebase Reference or Regenerate from frontend/src/components/DocumentationPanel.tsx.",
                    "Step 2: frontend/src/pages/ProjectView.tsx runs generateDocumentation() and POSTs to /api/projects/<project_id>/documentation/.",
                    "Step 3: backend/api/views.py calls generate_codebase_reference_sync(project) against the current workspace path.",
                    "Step 4: The backend returns the latest DocumentationRun payload, including generated sections, evidence, and metadata.",
                    "Step 5: ProjectView refreshes the project so DocumentationPanel renders the updated evidence-backed codebase reference.",
                ],
            }
        )

    if (
        _content_has_all(
            lowered["dashboard"],
            "const handlecreate = async",
            "/projects/create/",
        )
        and _content_has_any(
            lowered["dashboard"],
            "/projects/suggest/",
            "/projects/import/github/inspect/",
            "/projects/import/folder/inspect/",
        )
        and _content_has_all(
            lowered["views"],
            "def create_project",
            "workspace_manager.create_workspace",
            "_schedule_project_context_generation(",
        )
        and _content_has_any(
            lowered["views"],
            "def suggest_project_details",
            "def inspect_github_import",
            "def inspect_folder_import",
        )
    ):
        add_sequence(
            {
                "title": "Project Creation and Scaffolding",
                "description": (
                    "This flow starts in the Dashboard create-project flow. DevHub can first inspect a repo or local folder, "
                    "or suggest metadata for a starter idea, before the final create request provisions the project source, "
                    "registers a workspace, and schedules background blueprint generation."
                ),
                "mermaid_sequence": "\n".join(
                    [
                        "sequenceDiagram",
                        "participant Dashboard",
                        "participant API",
                        "participant WorkspaceManager",
                        "Dashboard->>API: inspect source or suggest metadata",
                        "API-->>Dashboard: detected stack runtime and project details",
                        "Dashboard->>API: POST projects create",
                        "API->>API: clone repo connect folder or scaffold starter",
                        "API->>WorkspaceManager: create workspace",
                        "WorkspaceManager-->>API: workspace id",
                        "API->>API: build blueprint context and schedule background generation",
                        "API-->>Dashboard: project id workspace id runtime",
                    ]
                ),
                "touchpoints": [
                    *_workflow_touchpoints(
                        workspace_path,
                        rel_paths,
                        "dashboard",
                        "views",
                        "urls",
                        "workspace_agent",
                    ),
                ],
            }
        )
        add_workflow(
            {
                "title": "Creating, Importing, or Connecting a Project",
                "steps": [
                    "Step 1: Use frontend/src/pages/Dashboard.tsx to enter an idea, GitHub URL, or local folder path.",
                    "Step 2: Dashboard can call /api/projects/suggest/, /api/projects/import/github/inspect/, or /api/projects/import/folder/inspect/ before the final create call.",
                    "Step 3: handleCreate() POSTs to /api/projects/create/ with the resolved name, description, source details, and tech_stack.",
                    "Step 4: backend/api/views.py clones the repo, connects the folder, or scaffolds starter files and then registers the workspace through workspace_manager.create_workspace().",
                    "Step 5: The API builds initial blueprint context, schedules background project context generation, and the frontend navigates into /project/:id.",
                ],
            }
        )

    if (
        _content_has_all(
            lowered["projectchat"],
            "const sendchat = async",
            "/projects/${projectid}/chat/",
        )
        and _content_has_any(
            lowered["projectchat"],
            "data.applied_changes?.applied_files?.length",
            "oncodeapplied",
        )
        and _content_has_all(
            lowered["views"],
            "def project_chat",
            "build_memory_context(",
            "_resolve_chat_context(",
            "apply_chat_changes(",
            "chatmessage.objects.create(",
        )
    ):
        add_sequence(
            {
                "title": "Workspace Chat Requests and Direct Code Application",
                "description": (
                    "This flow powers the floating Workspace Chat assistant. "
                    "ProjectChatPanel posts the user request, selected file, and explicit context mentions to the chat endpoint, "
                    "the backend builds memory-backed context, and then either answers directly from the current workspace context or "
                    "applies code changes for edit-style requests before returning assistant trace data and any modified files."
                ),
                "mermaid_sequence": "\n".join(
                    [
                        "sequenceDiagram",
                        "participant ProjectChatPanel",
                        "participant API",
                        "participant BuildMemoryContext",
                        "participant DevHubAssistant",
                        "participant ApplyChatChanges",
                        "participant CodeWorkspace",
                        "ProjectChatPanel->>API: POST project chat content selected_file context mentions",
                        "API->>BuildMemoryContext: build_memory_context and _resolve_chat_context",
                        "alt Edit style request and workspace available",
                        "API->>ApplyChatChanges: apply_chat_changes for edit requests",
                        "ApplyChatChanges-->>API: applied files and validation results",
                        "API-->>ProjectChatPanel: assistant message trace and applied_changes",
                        "ProjectChatPanel-->>CodeWorkspace: onCodeApplied refreshes files and runtime",
                        "else Explain or planning request",
                        "API->>DevHubAssistant: generate answer from workspace context",
                        "DevHubAssistant-->>API: assistant response and trace",
                        "API-->>ProjectChatPanel: assistant message and trace",
                        "end",
                    ]
                ),
                "touchpoints": [
                    *_workflow_touchpoints(
                        workspace_path,
                        rel_paths,
                        "projectchat",
                        "codeworkspace",
                        "views",
                        "urls",
                    ),
                ],
            }
        )
        add_workflow(
            {
                "title": "Using Workspace Chat to Explain or Change Code",
                "steps": [
                    "Step 1: Send a message from frontend/src/components/ProjectChatPanel.tsx, optionally including the selected file and explicit context mentions.",
                    "Step 2: ProjectChatPanel POSTs the request to /api/projects/<project_id>/chat/ and keeps the active chat session id in local state.",
                    "Step 3: backend/api/views.py stores the user message, builds memory context, and resolves file or codebase evidence for the request.",
                    "Step 4: If the message looks like an edit request, the backend runs apply_chat_changes(); otherwise it asks the assistant to answer against the current workspace context.",
                    "Step 5: Any returned applied_files trigger CodeWorkspace refresh hooks so the file tree, active file, and runtime view stay up to date.",
                ],
            }
        )

    return sequence_flows, common_workflows


_REPO_META_DIRS = frozenset({
    '.devhub', '.claude', '.claude-backup2', '.code-review-graph', '.git',
    'node_modules', '__pycache__', '.venv', 'venv', 'data',
})


def _build_repository_map_from_context(codebase_context: dict) -> list[dict]:
    indexed_paths = [str(path) for path in (codebase_context.get('indexed_paths') or []) if path]
    important_files = codebase_context.get('important_files') or []
    grouped: dict[str, dict] = {}
    raw_directory_counts = codebase_context.get('directory_counts') or {}
    root_directories = [str(item) for item in (codebase_context.get('root_directories') or []) if str(item or '').strip()]
    normalized_counts: dict[str, int] = {}
    for area, count in raw_directory_counts.items():
        normalized_area = '.' if str(area or '').strip() in {'.', './'} else str(area or '').strip()
        if not normalized_area or normalized_area in _REPO_META_DIRS:
            continue
        normalized_counts[normalized_area] = normalized_counts.get(normalized_area, 0) + int(count or 0)
    for directory in root_directories:
        normalized_directory = '.' if str(directory or '').strip() in {'.', './'} else str(directory or '').strip().strip('/')
        if normalized_directory and normalized_directory not in _REPO_META_DIRS:
            normalized_counts.setdefault(normalized_directory, 0)

    for area, count in sorted(normalized_counts.items(), key=lambda item: (-item[1], item[0]))[:20]:
        samples = [path for path in indexed_paths if path == area or path.startswith(f'{area}/')][:6]
        hints = sorted({
            hint
            for item in important_files
            if str(item.get('path') or '').startswith(f'{area}/') or (area == '.' and '/' not in str(item.get('path') or ''))
            for hint in (item.get('role_hints') or [])
        })
        grouped[area] = {
            'area': f'{area}/' if area != '.' else 'Project Root',
            'description': (
                f"Contains about {count} indexed files in the {'project root' if area == '.' else area} area of the project."
                if count
                else f"Detected top-level repository area for {'project root' if area == '.' else area}."
            ),
            'important_files': samples,
            'relationships': [f"Owns {hint} concerns" for hint in hints] or ['Contains mixed project responsibilities'],
        }

    return list(grouped.values())[:16]


def _describe_directory_area(area: str, role_hints: list[str]) -> str:
    lowered = area.lower()
    if area in {'.', './'}:
        return 'Project root containing entrypoints, config, and workspace-level files.'
    if lowered in {'src', 'app', 'frontend', 'client'}:
        return 'Primary application source area where most user-facing and core logic files live.'
    if lowered in {'backend', 'server', 'api'}:
        return 'Server-side application area for API, runtime, and backend integration logic.'
    if lowered in {'docs', 'doc'}:
        return 'Documentation and project reference material used to understand setup, architecture, and workflow.'
    if lowered in {'test', 'tests', '__tests__'}:
        return 'Automated test coverage area for validating runtime behavior and preventing regressions.'
    if lowered in {'lib', 'common', 'shared', 'utils'}:
        return 'Shared implementation area containing reusable modules, helpers, and internal abstractions.'
    if lowered in {'ci', '.github'}:
        return 'Automation and delivery area for CI, workflows, and repository-level operational setup.'
    if lowered in {'typings', 'types'}:
        return 'Type and contract definitions used across the codebase.'
    if lowered in {'patches'}:
        return 'Local dependency or source patches that affect build/runtime behavior.'
    if lowered in {'.tours'}:
        return 'Interactive onboarding or guided-tour assets for helping users explore the project.'
    if role_hints:
        return f"Area focused on {', '.join(role_hints[:3])} concerns within the active project."
    return 'Detected project area from the indexed repository structure.'


def _sample_paths_for_area(indexed_paths: list[str], area: str, limit: int = 8) -> list[str]:
    if area in {'.', './'}:
        return [path for path in indexed_paths if '/' not in path][:limit]
    return [path for path in indexed_paths if path.startswith(f'{area}/')][:limit]


def _important_files_for_area(important_files: list[dict], area: str) -> list[dict]:
    if area in {'.', './'}:
        return [item for item in important_files if '/' not in str(item.get('path') or '')]
    return [item for item in important_files if str(item.get('path') or '').startswith(f'{area}/')]


def _build_directory_guide_from_context(codebase_context: dict) -> list[dict]:
    guide = []
    indexed_paths = [str(path) for path in (codebase_context.get('indexed_paths') or []) if path]
    important_files = codebase_context.get('important_files') or []
    raw_directory_counts = codebase_context.get('directory_counts') or {}
    root_directories = [str(item) for item in (codebase_context.get('root_directories') or []) if str(item or '').strip()]
    normalized_counts: dict[str, int] = {}
    for area, count in raw_directory_counts.items():
        normalized_area = '.' if str(area or '').strip() in {'.', './'} else str(area or '').strip()
        if not normalized_area or normalized_area in _REPO_META_DIRS:
            continue
        normalized_counts[normalized_area] = normalized_counts.get(normalized_area, 0) + int(count or 0)
    for directory in root_directories:
        normalized_directory = '.' if str(directory or '').strip() in {'.', './'} else str(directory or '').strip().strip('/')
        if normalized_directory and normalized_directory not in _REPO_META_DIRS:
            normalized_counts.setdefault(normalized_directory, 0)

    for area, count in sorted(normalized_counts.items(), key=lambda item: (-item[1], item[0]))[:20]:
        area_files = _important_files_for_area(important_files, area)
        example_paths = _sample_paths_for_area(indexed_paths, area, limit=6)
        role_hints = sorted({hint for item in area_files for hint in (item.get('role_hints') or [])})

        if area_files:
            key_files = [item.get('brief') or item.get('path') for item in area_files[:6]]
        else:
            key_files = example_paths

        guide.append({
            'path': f'{area}/' if area != '.' else './',
            'purpose': (
                f"{_describe_directory_area(area, role_hints)} It currently contains about {count} indexed files."
                if count
                else f"{_describe_directory_area(area, role_hints)} This top-level area exists in the repository but was not deeply indexed."
            ),
            'key_files': key_files,
            'pattern': ", ".join(role_hints) if role_hints else 'mixed responsibilities',
        })
    return guide[:16]


def _build_file_structure_visualizer(codebase_context: dict) -> list[dict]:
    indexed_paths = [str(path) for path in (codebase_context.get('indexed_paths') or []) if path]
    important_files = codebase_context.get('important_files') or []
    important_by_path = {
        str(item.get('path') or ''): item
        for item in important_files
        if item.get('path')
    }
    visualizer = []
    for area, count in sorted((codebase_context.get('directory_counts') or {}).items(), key=lambda item: (-item[1], item[0]))[:20]:
        if str(area or '').strip() in _REPO_META_DIRS:
            continue
        files_in_area = _sample_paths_for_area(indexed_paths, area, limit=10)
        area_files = _important_files_for_area(important_files, area)
        role_hints = sorted({hint for item in area_files for hint in (item.get('role_hints') or [])})
        file_rows = []
        for path in files_in_area:
            meta = important_by_path.get(path, {})
            role = ", ".join(meta.get('role_hints') or []) or meta.get('language') or path.rsplit('.', 1)[-1]
            symbol = meta.get('symbol')
            imports = [str(item) for item in (meta.get('imports') or [])[:6]]
            routes = [str(item) for item in (meta.get('routes') or [])[:6]]
            data_models = [str(item) for item in (meta.get('data_models') or [])[:6]]
            area_label = 'project root' if area == '.' else area
            summary = meta.get('purpose') or meta.get('summary') or meta.get('brief') or f'{path} participates in the {area_label} area of the project.'
            why_text = meta.get('why') or ''
            if not why_text:
                why_bits = []
                if symbol:
                    why_bits.append(f"Primary symbol: {symbol}.")
                if routes:
                    why_bits.append(f"Routes: {', '.join(routes)}.")
                if data_models:
                    why_bits.append(f"Data types: {', '.join(data_models)}.")
                if imports:
                    why_bits.append(f"Imports: {', '.join(imports[:4])}.")
                why_text = " ".join(why_bits)
            how_text = meta.get('how') or (
                f"Change this file when working on {', '.join(meta.get('role_hints') or role_hints[:2] or ['behavior'])}. "
                f"It has about {meta.get('lines', 'unknown')} lines."
            )
            file_rows.append({
                'path': path,
                'role': meta.get('file_kind') or role,
                'purpose': summary,
                'why': why_text[:500] or f"This file is one of the indexed representatives for the {area if area != '.' else 'project root'} area.",
                'how': how_text[:500],
                'related_symbols': [symbol] if symbol else [],
                'excerpt': str(meta.get('excerpt') or '')[:600],
                'imports': imports,
                'routes': routes,
                'data_models': data_models,
                'lines': meta.get('lines'),
                'headings': meta.get('headings') or [],
                'json_keys': meta.get('json_keys') or [],
                'commands': meta.get('commands') or [],
            })

        if not file_rows:
            continue

        visualizer.append({
            'folder': f'{area}/' if area != '.' else 'Project Root',
            'summary': f'{_describe_directory_area(area, role_hints)}',
            'purpose': f"This section shows real files from {'the project root' if area == '.' else area}, why they are present, and how to navigate them.",
            'files': file_rows,
        })
    return visualizer


def _build_change_guide(codebase_context: dict) -> list[dict]:
    guides = []
    important_files = codebase_context.get('important_files') or []
    ui_files = [item.get('path') for item in important_files if 'ui' in (item.get('role_hints') or [])][:6]
    api_files = [item.get('path') for item in important_files if 'api' in (item.get('role_hints') or [])][:6]
    data_files = [item.get('path') for item in important_files if 'data-model' in (item.get('role_hints') or [])][:6]
    if ui_files:
        guides.append({'area': 'UI changes', 'where': ui_files, 'notes': 'Start with these files when changing user-facing behavior.'})
    if api_files:
        guides.append({'area': 'API changes', 'where': api_files, 'notes': 'Review routes, handlers, and service files together.'})
    if data_files:
        guides.append({'area': 'Data model changes', 'where': data_files, 'notes': 'Update models, schema, and related consumers together.'})
    return guides


def _blueprint_text(value, fallback: str = 'Not clearly detected from the scanned codebase.') -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _blueprint_list(value) -> list:
    return value if isinstance(value, list) else []


def _markdown_bullets(items: list[str], empty_text: str = 'Not clearly detected from the scanned codebase.') -> list[str]:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return [f"- {empty_text}"]
    return [f"- {item}" for item in values]


def _slugify_heading(text: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', str(text or '').strip().lower()).strip('-')
    return slug or 'section'


def _project_workspace_path(project: Project) -> Path | None:
    if not project.local_path:
        return None
    candidate = Path(project.local_path)
    return candidate if candidate.is_dir() else None


def _read_workspace_excerpt(workspace_path: Path | None, *relative_paths: str, limit: int = 12000) -> str:
    if not workspace_path:
        return ""
    for relative_path in relative_paths:
        path = workspace_path / relative_path
        try:
            if path.exists() and path.is_file():
                return path.read_text(encoding="utf-8", errors="ignore")[:limit]
        except Exception:
            continue
    return ""


def _load_workspace_package_json(workspace_path: Path | None) -> dict:
    raw = _read_workspace_excerpt(workspace_path, "package.json", limit=20000)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _codebase_doc_target(workspace_path: Path, rel_path: str = "") -> tuple[Path, str]:
    normalized = str(rel_path or "").replace("\\", "/").strip("/")
    target = workspace_path if not normalized else workspace_path / normalized
    target = target.resolve()
    target.relative_to(workspace_path.resolve())
    return target, normalized


def _codebase_doc_breadcrumbs(rel_path: str) -> list[dict]:
    normalized = str(rel_path or "").replace("\\", "/").strip("/")
    crumbs = [{"label": "codebase", "path": ""}]
    if not normalized:
        return crumbs
    current = []
    for part in normalized.split("/"):
        current.append(part)
        crumbs.append({"label": part, "path": "/".join(current)})
    return crumbs


def _iter_codebase_files(base_path: Path, workspace_path: Path, limit: int = 48) -> list[Path]:
    files: list[Path] = []
    allowed_suffixes = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".md", ".yml", ".yaml", ".toml", ".txt"
    }
    for root, dirs, filenames in os.walk(base_path):
        dirs[:] = [name for name in sorted(dirs) if name not in SKIP_DIRS and name != ".env"]
        for filename in sorted(filenames):
            path = Path(root) / filename
            rel_path = str(path.relative_to(workspace_path)).replace("\\", "/")
            if rel_path.startswith(f"{DEVHUB_META_DIR}/"):
                continue
            if path.suffix.lower() not in allowed_suffixes and filename not in {
                "Dockerfile",
                "README",
                "README.md",
                "readme.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "AGENTS.md",
                "DEVHUB.md",
            }:
                continue
            files.append(path)
            if len(files) >= limit:
                return files
    return files


def _extract_code_symbols(content: str, language: str, limit: int = 18) -> list[str]:
    patterns = [
        r"^\s*class\s+([A-Za-z0-9_]+)",
        r"^\s*def\s+([A-Za-z0-9_]+)",
        r"^\s*async\s+def\s+([A-Za-z0-9_]+)",
        r"^\s*function\s+([A-Za-z0-9_]+)",
        r"^\s*const\s+([A-Za-z0-9_]+)\s*=",
        r"^\s*export\s+function\s+([A-Za-z0-9_]+)",
        r"^\s*export\s+default\s+function\s+([A-Za-z0-9_]+)",
        r"^\s*interface\s+([A-Za-z0-9_]+)",
        r"^\s*type\s+([A-Za-z0-9_]+)\s*=",
    ]
    if language == "markdown":
        headings = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                headings.append(stripped.lstrip("#").strip())
            if len(headings) >= limit:
                break
        return headings

    symbols: list[str] = []
    for line in content.splitlines()[:400]:
        for pattern in patterns:
            match = re.search(pattern, line)
            if not match:
                continue
            symbol = match.group(1)
            if symbol not in symbols:
                symbols.append(symbol)
            if len(symbols) >= limit:
                return symbols
    return symbols


def _build_file_explanation(summary: dict, sibling_paths: list[str], docs_available: list[str]) -> dict:
    role_hints = [str(item) for item in (summary.get("role_hints") or []) if item]
    routes = [str(item) for item in (summary.get("routes") or []) if item]
    data_models = [str(item) for item in (summary.get("data_models") or []) if item]
    imports = [str(item) for item in (summary.get("imports") or []) if item]
    headings = [str(item) for item in (summary.get("headings") or []) if item]
    json_keys = [str(item) for item in (summary.get("json_keys") or []) if item]
    commands = [str(item) for item in (summary.get("commands") or []) if item]
    symbol = str(summary.get("symbol") or "").strip()
    path = str(summary.get("path") or "")
    file_kind = str(summary.get("file_kind") or "").strip()

    what = str(summary.get("purpose") or summary.get("summary") or f"{path} is part of the project codebase.").strip()
    why_bits = []
    if summary.get("why"):
        why_bits.append(str(summary.get("why")))
    if role_hints:
        why_bits.append(f"Responsibilities hinted by the file and path include {', '.join(role_hints)}.")
    if routes:
        why_bits.append(f"It defines or references routes/endpoints such as {', '.join(routes[:4])}.")
    if data_models:
        why_bits.append(f"It declares or works with data types like {', '.join(data_models[:4])}.")
    if headings and file_kind in {"documentation", "readme", "security-doc", "contributing-doc", "prompt-doc"}:
        why_bits.append(f"The document structure is organized around headings like {', '.join(headings[:4])}.")
    if json_keys and file_kind in {"config", "package-manifest", "typescript-config"}:
        why_bits.append(f"The file is organized around keys such as {', '.join(json_keys[:6])}.")
    if not why_bits:
        why_bits.append("It is part of the repository structure and should be read together with nearby files in the same folder.")

    how_bits = []
    if summary.get("how"):
        how_bits.append(str(summary.get("how")))
    if symbol:
        how_bits.append(f"Start with `{symbol}` to understand the main entry point in this file.")
    if imports:
        how_bits.append(f"The import surface shows its main dependencies: {', '.join(imports[:4])}.")
    if headings:
        how_bits.append(f"Headings worth reading first: {', '.join(headings[:4])}.")
    if json_keys:
        how_bits.append(f"Top-level keys to inspect: {', '.join(json_keys[:6])}.")
    if commands:
        how_bits.append(f"Operational commands referenced here include {', '.join(commands[:4])}.")
    if sibling_paths:
        how_bits.append(f"Related neighbors in the same folder include {', '.join(sibling_paths[:4])}.")
    if docs_available:
        how_bits.append(f"Repo guidance is also available in {', '.join(docs_available[:3])}.")

    return {
        "what": what,
        "why": " ".join(why_bits),
        "how": " ".join(how_bits) or "Review the code excerpt and top-level symbols to understand how this file works.",
        "change_guidance": (
            f"Edit `{path}` when you need to change behavior owned by this file. "
            "Check its imports, exports, and nearby files before making cross-cutting changes."
        ),
    }


def _read_context_docs(workspace_path: Path, target_path: Path) -> list[dict]:
    docs: list[dict] = []
    candidates = []
    if target_path.is_dir():
        candidates.extend([
            target_path / "README.md",
            target_path / "readme.md",
            target_path / "CONTRIBUTING.md",
        ])
    else:
        parent = target_path.parent
        candidates.extend([
            parent / "README.md",
            parent / "readme.md",
        ])
    candidates.extend(
        [
            workspace_path / "README.md",
            workspace_path / "CONTRIBUTING.md",
            workspace_path / "SECURITY.md",
            workspace_path / "AGENTS.md",
            workspace_path / "DEVHUB.md",
        ]
    )

    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(workspace_path.resolve())
        except Exception:
            continue
        if resolved in seen or not resolved.exists() or not resolved.is_file():
            continue
        seen.add(resolved)
        try:
            rel_path = str(resolved.relative_to(workspace_path)).replace("\\", "/")
            docs.append(
                {
                    "path": rel_path,
                    "excerpt": resolved.read_text(encoding="utf-8", errors="ignore")[:2400],
                }
            )
        except Exception:
            continue
        if len(docs) >= 4:
            break
    return docs


def _generate_file_explanation_llm(project, rel_path: str, content: str, summary: dict) -> dict | None:
    try:
        from agents.base import BaseAgent
        agent = BaseAgent(
            role="Codebase Documenter",
            system_instruction=(
                "You are an expert software architect providing dynamic documentation for a codebase file.\n"
                "Return a JSON object with exactly FOUR string keys:\n"
                "- 'what': A single short sentence summarizing what the file does.\n"
                "- 'why': A short paragraph explaining why it exists.\n"
                "- 'how': A short paragraph guiding a developer on how to read or change it.\n"
                "- 'change_guidance': A short tip on what to watch out for when modifying this file.\n"
                "Return ONLY valid JSON. Use Markdown inside the values if needed."
            ),
            ai_config=_project_ai_config(project)
        )
        prompt = f"File: {rel_path}\nMetadata: {summary}\nExcerpt:\n{content[:9000]}"
        response = agent.generate(prompt, response_schema=True)
        data = agent.parse_json(response)
        if not isinstance(data, dict):
            return None
        return {
            "what": str(data.get("what") or summary.get("purpose") or ""),
            "why": str(data.get("why") or ""),
            "how": str(data.get("how") or ""),
            "change_guidance": str(data.get("change_guidance") or ""),
        }
    except Exception:
        logger.exception("Failed to generate LLM documentation for %s", rel_path)
        return None


def _build_file_doc_payload(project, workspace_path: Path, rel_path: str, codebase_context: dict) -> dict:
    target_path, normalized = _codebase_doc_target(workspace_path, rel_path)
    summary = _cached_file_summary(codebase_context, normalized) or _file_summary(target_path, workspace_path, include_excerpt=True) or {
        "path": normalized,
        "language": target_path.suffix.lstrip(".") or "text",
        "lines": 0,
        "imports": [],
        "routes": [],
        "data_models": [],
        "role_hints": [],
        "symbol": "",
        "excerpt": "",
        "summary": f"{normalized} could not be summarized automatically.",
    }
    content = target_path.read_text(encoding="utf-8", errors="ignore")
    sibling_paths = []
    for sibling in sorted(target_path.parent.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
        if sibling == target_path or sibling.name in SKIP_DIRS or sibling.name == ".env":
            continue
        sibling_paths.append(sibling.name + ("/" if sibling.is_dir() else ""))
        if len(sibling_paths) >= 8:
            break
    docs = _read_context_docs(workspace_path, target_path)
    symbols = _extract_code_symbols(content, str(summary.get("language") or "text"))
    exports = _extract_export_symbols(content, str(summary.get("language") or "text"))
    
    explanation_override = None
    try:
        if target_path.stat().st_size <= 150 * 1024:
            explanation_override = _generate_file_explanation_llm(project, normalized, content, summary)
    except Exception:
        pass

    if explanation_override and explanation_override.get("what"):
        explanation = explanation_override
    else:
        explanation = _build_file_explanation(summary, sibling_paths, [item["path"] for item in docs])
        
    excerpt = content[:9000]
    dependency_graph = _build_dependency_graph(codebase_context)
    models_summary = _build_models_summary(codebase_context)
    routes_summary = _build_routes_summary(codebase_context)
    prerequisites = _build_file_prerequisites_summary(workspace_path, normalized, summary, codebase_context)

    markdown_lines = [
        f"# `{normalized}`",
        "",
        f"- Kind: `{summary.get('file_kind') or 'source-file'}`",
        f"- Language: `{summary.get('language') or 'text'}`",
        f"- Approx. lines: `{summary.get('lines') or 0}`",
        f"- Primary symbol: `{summary.get('symbol') or 'not clearly detected'}`",
        f"- Role hints: `{', '.join(summary.get('role_hints') or []) or 'not clearly detected'}`",
        "",
        "## What This File Does",
        explanation["what"],
        "",
        "## Why It Exists",
        explanation["why"],
        "",
        "## How To Read Or Change It",
        explanation["how"],
        "",
        "## Change Guidance",
        explanation["change_guidance"],
    ]
    if symbols:
        markdown_lines.extend(["", "## Top-Level Symbols"])
        markdown_lines.extend([f"- `{symbol}`" for symbol in symbols])
    if exports:
        markdown_lines.extend(["", "## Exports"])
        markdown_lines.extend([f"- `{item}`" for item in exports[:12]])
    if summary.get("headings"):
        markdown_lines.extend(["", "## Headings"])
        markdown_lines.extend([f"- `{item}`" for item in summary.get("headings")[:12]])
    if summary.get("json_keys"):
        markdown_lines.extend(["", "## Top-Level Keys"])
        markdown_lines.extend([f"- `{item}`" for item in summary.get("json_keys")[:12]])
    if summary.get("imports"):
        markdown_lines.extend(["", "## Imports"])
        markdown_lines.extend([f"- `{item}`" for item in summary.get("imports")[:12]])
    if summary.get("routes"):
        markdown_lines.extend(["", "## Routes / Endpoints"])
        markdown_lines.extend([f"- `{item}`" for item in summary.get("routes")[:12]])
    if summary.get("data_models"):
        markdown_lines.extend(["", "## Data Models / Types"])
        markdown_lines.extend([f"- `{item}`" for item in summary.get("data_models")[:12]])
    if summary.get("commands"):
        markdown_lines.extend(["", "## Referenced Commands"])
        markdown_lines.extend([f"- `{item}`" for item in summary.get("commands")[:12]])
    if docs:
        markdown_lines.extend(["", "## Related Repo Docs"])
        markdown_lines.extend([f"- `{item['path']}`" for item in docs])
    markdown_lines.extend(
        [
            "",
            "## Code Excerpt",
            f"```{summary.get('language') or ''}",
            excerpt,
            "```",
        ]
    )

    return {
        "kind": "file",
        "path": normalized,
        "name": target_path.name,
        "breadcrumbs": _codebase_doc_breadcrumbs(normalized),
        "summary": explanation["what"],
        "details": explanation,
        "stats": {
            "language": summary.get("language"),
            "lines": summary.get("lines"),
            "imports": len(summary.get("imports") or []),
            "routes": len(summary.get("routes") or []),
            "data_models": len(summary.get("data_models") or []),
        },
        "symbols": symbols,
        "exports": exports,
        "imports": summary.get("imports") or [],
        "routes": summary.get("routes") or [],
        "data_models": summary.get("data_models") or [],
        "siblings": sibling_paths,
        "docs": docs,
        "excerpt": excerpt,
        "dependency_graph": dependency_graph,
        "all_models": models_summary,
        "all_routes": routes_summary,
        "prerequisites": prerequisites,
        "markdown": "\n".join(markdown_lines),
        "trace": {
            "approach": "Read the requested file directly, extracted symbols/imports/routes, and pulled nearby repo docs for context.",
            "files_accessed": [
                {"path": normalized, "source": "file", "reason": "Primary requested file."},
                *[
                    {"path": item["path"], "source": "docs", "reason": "Documentation context for this file."}
                    for item in docs
                ],
            ],
            "commands_ran": [],
        },
    }


def _describe_directory_children(file_summaries: list[dict], doc_files: list[dict]) -> str:
    languages = []
    roles = []
    for item in file_summaries:
        language = str(item.get("language") or "").strip()
        if language and language not in languages:
            languages.append(language)
        for role in item.get("role_hints") or []:
            if role not in roles:
                roles.append(role)
    bits = []
    if languages:
        bits.append(f"Directory composition includes {', '.join(languages[:5])} files.")
    if roles:
        bits.append(f"Primary detected responsibilities involve {', '.join(roles[:5])}.")
    if doc_files:
        bits.append(f"Local documentation context found in {', '.join(item['path'] for item in doc_files[:3])}.")
    if not bits:
        bits.append("Directory has mixed responsibilities; explore its children for detailed context.")
    return " ".join(bits)


def _codebase_summary_pool(codebase_context: dict, limit: int = 200) -> list[dict]:
    seen_paths: set[str] = set()
    items: list[dict] = []
    for entry in list(codebase_context.get("all_file_summaries") or []) + list(codebase_context.get("important_files") or []):
        path = str(entry.get("path") or "")
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        items.append(entry)
        if len(items) >= limit:
            break
    return items


def _cached_file_summary(codebase_context: dict, rel_path: str) -> dict | None:
    normalized = str(rel_path or "").replace("\\", "/").strip("/")
    for item in _codebase_summary_pool(codebase_context):
        if str(item.get("path") or "") == normalized:
            return item
    return None


def _extract_export_symbols(content: str, language: str, limit: int = 18) -> list[str]:
    exports: list[str] = []
    patterns: list[str] = []
    if language.startswith("python"):
        patterns = [
            r"^__all__\s*=\s*\[(.*?)\]",
            r"^\s*class\s+([A-Za-z0-9_]+)",
            r"^\s*def\s+([A-Za-z0-9_]+)",
            r"^\s*async\s+def\s+([A-Za-z0-9_]+)",
        ]
    elif language in {"javascript", "javascript-react", "typescript", "typescript-react"}:
        patterns = [
            r"^\s*export\s+default\s+function\s+([A-Za-z0-9_]+)",
            r"^\s*export\s+function\s+([A-Za-z0-9_]+)",
            r"^\s*export\s+(?:const|let|var|class|interface|type)\s+([A-Za-z0-9_]+)",
            r"^\s*export\s*\{\s*([^}]+)\s*\}",
        ]
    else:
        return exports

    for line in content.splitlines()[:200]:
        for pattern in patterns:
            match = re.search(pattern, line)
            if not match:
                continue
            value = str(match.group(1) or "").strip()
            if not value:
                continue
            if "," in value:
                parts = [part.strip().split(" as ")[0].strip() for part in value.split(",")]
            else:
                parts = [value]
            for part in parts:
                cleaned = part.strip("'\" ")
                if cleaned and cleaned not in exports:
                    exports.append(cleaned)
                    if len(exports) >= limit:
                        return exports
    return exports


def _resolve_relative_import(source_path: str, target: str) -> str:
    normalized = str(target or "").strip().strip("'\"")
    if not normalized.startswith("."):
        return ""
    source_parent = PurePosixPath(source_path).parent
    candidate = str(source_parent.joinpath(normalized))
    candidate = posixpath.normpath(candidate).lstrip("./")
    return "" if candidate == "." else candidate


def _possible_import_paths(import_path: str) -> list[str]:
    base = str(import_path or "").strip().replace("\\", "/")
    if not base:
        return []
    options = [
        base,
        f"{base}.ts",
        f"{base}.tsx",
        f"{base}.js",
        f"{base}.jsx",
        f"{base}.py",
        f"{base}.json",
        f"{base}.md",
        f"{base}/index.ts",
        f"{base}/index.tsx",
        f"{base}/index.js",
        f"{base}/index.jsx",
        f"{base}/__init__.py",
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for option in options:
        normalized = posixpath.normpath(option).lstrip("./")
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _extract_import_reference(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return ""
    patterns = [
        r"from\s+['\"]([^'\"]+)['\"]",
        r"require\(\s*['\"]([^'\"]+)['\"]\s*\)",
        r"from\s+([A-Za-z0-9_\.]+)",
        r"import\s+([A-Za-z0-9_\.]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return str(match.group(1) or "").strip()
    return ""


def _build_dependency_graph(codebase_context: dict) -> dict:
    cached_graph = codebase_context.get("dependency_graph") or {}
    cached_edges = list(cached_graph.get("edges") or [])[:48]
    labels: dict[str, str] = {}
    lines = ["graph LR"]
    nodes: set[str] = set()

    def node_id(path: str) -> str:
        digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]
        return f"n{digest}"

    def node_label(path: str) -> str:
        path_obj = PurePosixPath(path)
        if len(path_obj.parts) <= 2:
            return path
        return f"{path_obj.parts[-2]}/{path_obj.parts[-1]}"

    for edge in cached_edges:
        source_path = str(edge.get("from") or "")
        target_path = str(edge.get("to") or "")
        if not source_path or not target_path:
            continue
        for path in (source_path, target_path):
            if path not in nodes:
                nodes.add(path)
                labels[path] = node_label(path)
                lines.append(f'  {node_id(path)}["{labels[path]}"]')
        lines.append(f"  {node_id(source_path)} --> {node_id(target_path)}")

    return {
        "mermaid": "\n".join(lines) if len(lines) > 1 else "",
        "edges": cached_edges,
        "nodes": [{"path": path, "label": labels.get(path) or node_label(path)} for path in nodes],
    }


def _build_models_summary(codebase_context: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in _codebase_summary_pool(codebase_context):
        path = str(item.get("path") or "")
        for model in item.get("data_models") or []:
            key = (str(model), path)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": str(model),
                    "file": path,
                    "kind": str(item.get("file_kind") or item.get("language") or "model"),
                    "purpose": str(item.get("purpose") or item.get("summary") or ""),
                }
            )
    return rows[:200]


def _route_parts(route_value: str) -> tuple[str, str]:
    route_text = str(route_value or "").strip()
    match = re.match(r"^(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+(.+)$", route_text, re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2).strip()
    return "DETECTED", route_text


def _build_routes_summary(codebase_context: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item in _codebase_summary_pool(codebase_context):
        path = str(item.get("path") or "")
        for route in item.get("routes") or []:
            method, route_path = _route_parts(str(route))
            key = (method, route_path, path)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "method": method,
                    "path": route_path,
                    "file": path,
                    "purpose": str(item.get("purpose") or item.get("summary") or ""),
                }
            )
    return rows[:200]


def _is_devhub_internal_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").strip()
    return normalized.startswith(f"{DEVHUB_META_DIR}/")


def _is_reference_noise_child(parent_path: str, child_name: str) -> bool:
    if str(parent_path or "").strip():
        return False
    lowered = str(child_name or "").strip().lower()
    if not lowered:
        return True
    return lowered in {'.git', '.devhub', '.code-review-graph', '__pycache__'} or lowered.startswith('.claude')


def _public_instruction_files(codebase_context: dict) -> list[dict]:
    visible: list[dict] = []
    for item in codebase_context.get("instruction_files") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if not path or _is_devhub_internal_path(path):
            continue
        visible.append(
            {
                "path": path,
                "content": str(item.get("content") or "")[:3000],
            }
        )
    return visible[:24]


def _is_setup_command_source(item: dict) -> bool:
    file_kind = str(item.get("file_kind") or "").strip().lower()
    if file_kind in {"readme", "contributing-doc", "script", "container-config"}:
        return True
    if file_kind != "documentation":
        return False

    haystack = " ".join(
        [
            str(item.get("path") or ""),
            *[str(heading or "") for heading in (item.get("headings") or [])[:8]],
        ]
    ).lower()
    return any(
        token in haystack
        for token in (
            "setup",
            "install",
            "getting started",
            "getting-started",
            "quickstart",
            "quick-start",
            "onboarding",
            "local dev",
            "run locally",
        )
    )


def _looks_like_setup_command(command: str) -> bool:
    candidate = str(command or "").strip()
    if not candidate:
        return False
    lowered = candidate.lower()
    patterns = (
        r"^(pnpm|npm)\s+(install|ci|run\s+\S+|exec\s+\S+|dev\b|start\b|test\b|build\b|lint\b|preview\b)",
        r"^yarn\s+\S+",
        r"^bun\s+(install|run\s+\S+|dev\b|test\b|build\b|start\b)",
        r"^npx\s+\S+",
        r"^python(?:3)?\s+(?:-m\s+\S+|[^\s]+\.py(?:\s|$)|manage\.py(?:\s|$))",
        r"^py\s+(?:-m\s+\S+|[^\s]+\.py(?:\s|$)|manage\.py(?:\s|$))",
        r"^pip(?:3)?\s+\S+",
        r"^uv\s+\S+",
        r"^poetry\s+\S+",
        r"^docker\s+\S+",
        r"^make\s+\S+",
        r"^cargo\s+\S+",
        r"^go\s+(run|test|build|get|install|mod|fmt|vet|generate)\b",
        r"^(bash|sh)\s+\S+",
        r"^\./\S+",
    )
    return any(re.match(pattern, lowered) for pattern in patterns)


def _command_tool_name(command: str) -> str:
    lowered = str(command or "").strip().lower()
    if lowered.startswith("python") or lowered.startswith("py "):
        return "python"
    for tool in ("pnpm", "npm", "yarn", "bun", "npx", "pip", "uv", "poetry", "docker", "make", "cargo", "go", "bash", "sh"):
        if lowered.startswith(f"{tool} "):
            return tool
    if lowered.startswith("./"):
        return Path(lowered.split()[0]).name
    return lowered.split()[0] if lowered else ""


def _package_manifest_commands(workspace_path: Path, path: str) -> list[str]:
    target = workspace_path / path
    try:
        payload = json.loads(target.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []

    scripts = payload.get("scripts") or {}
    if not isinstance(scripts, dict):
        return []

    package_manager = _detect_workspace_package_manager(workspace_path, payload) or "npm"
    commands: list[str] = []
    for script_name in list(scripts.keys())[:8]:
        name = str(script_name or "").strip()
        if not name:
            continue
        if package_manager == "npm":
            commands.append(f"npm run {name}")
        elif package_manager == "pnpm":
            commands.append(f"pnpm {name}")
        elif package_manager == "yarn":
            commands.append(f"yarn {name}")
        elif package_manager == "bun":
            commands.append(f"bun run {name}")
    return commands


def _build_prerequisites_summary(workspace_path: Path, codebase_context: dict) -> dict:
    summaries = _codebase_summary_pool(codebase_context)
    commands: list[str] = []
    tools: list[str] = []
    env_files: list[str] = []
    env_variables: list[str] = []
    for item in summaries:
        path = str(item.get("path") or "")
        if item.get("file_kind") == "env-template":
            env_files.append(path)
            try:
                content = (workspace_path / path).read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or "=" not in stripped:
                        continue
                    variable = stripped.split("=", 1)[0].strip()
                    if variable and variable not in env_variables:
                        env_variables.append(variable)
            except Exception:
                pass

        file_kind = str(item.get("file_kind") or "").strip().lower()
        candidate_commands: list[str] = []
        if file_kind == "package-manifest" and Path(path).name.lower() == "package.json":
            candidate_commands.extend(_package_manifest_commands(workspace_path, path))
        if _is_setup_command_source(item):
            candidate_commands.extend(str(command).strip() for command in (item.get("commands") or []))

        for command_text in candidate_commands:
            if not _looks_like_setup_command(command_text):
                continue
            if command_text not in commands:
                commands.append(command_text)
            tool = _command_tool_name(command_text)
            if tool and tool not in tools:
                tools.append(tool)
    return {
        "readme_excerpt": str(codebase_context.get("readme_excerpt") or "").strip(),
        "instruction_files": _public_instruction_files(codebase_context),
        "commands": commands[:24],
        "required_tools": tools[:16],
        "environment_files": env_files[:12],
        "environment_variables": env_variables[:80],
    }


def _build_file_prerequisites_summary(workspace_path: Path, rel_path: str, summary: dict, codebase_context: dict) -> dict | None:
    normalized = str(rel_path or "").replace("\\", "/").strip("/")
    path_name = PurePosixPath(normalized).name.lower()
    file_kind = str(summary.get("file_kind") or "").strip().lower()
    setup_like_kinds = {
        "readme",
        "contributing-doc",
        "package-manifest",
        "container-config",
        "env-template",
    }
    setup_like_names = {
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "manage.py",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yaml",
        "compose.yml",
        "makefile",
        "justfile",
        ".env.example",
        ".env.sample",
    }
    if file_kind in setup_like_kinds or path_name in setup_like_names:
        return _build_prerequisites_summary(workspace_path, codebase_context)
    return None


def _build_directory_doc_payload(project, workspace_path: Path, rel_path: str, codebase_context: dict) -> dict:
    target_path, normalized = _codebase_doc_target(workspace_path, rel_path)
    doc_files = _read_context_docs(workspace_path, target_path)
    manifest_entries = list(codebase_context.get("manifest") or [])
    summary_lookup = {str(item.get("path") or ""): item for item in _codebase_summary_pool(codebase_context)}
    child_entries = []
    files_accessed = []
    normalized_prefix = f"{normalized}/" if normalized else ""
    direct_children: dict[str, dict] = {}
    for item in manifest_entries:
        path = str(item.get("path") or "")
        if not path or (normalized and not path.startswith(normalized_prefix)):
            continue
        remainder = path[len(normalized_prefix):] if normalized else path
        if not remainder or "/" not in remainder:
            child_name = remainder
            if not child_name:
                continue
            if _is_reference_noise_child(normalized, child_name):
                continue
            direct_children.setdefault(
                child_name,
                {
                    "name": child_name,
                    "path": path,
                    "type": "file",
                    "entry": item,
                },
            )
        else:
            directory_name = remainder.split("/", 1)[0]
            if _is_reference_noise_child(normalized, directory_name):
                continue
            child_path = f"{normalized_prefix}{directory_name}".strip("/")
            bucket = direct_children.setdefault(
                directory_name,
                {
                    "name": directory_name,
                    "path": child_path,
                    "type": "directory",
                    "entries": [],
                },
            )
            bucket.setdefault("entries", []).append(item)

    for child in sorted(direct_children.values(), key=lambda item: (item.get("type") != "directory", str(item.get("name") or "").lower()))[:120]:
        if child.get("type") == "file":
            rel_entry = str(child.get("path") or "")
            summary = summary_lookup.get(rel_entry) or {}
            entry = child.get("entry") or {}
            child_entries.append(
                {
                    "name": child.get("name"),
                    "path": rel_entry,
                    "type": "file",
                    "summary": summary.get("purpose") or summary.get("summary") or f"Tier {entry.get('tier', 3)} file discovered from the repository manifest.",
                    "language": summary.get("language") or entry.get("language"),
                    "lines": summary.get("lines"),
                    "size": entry.get("size"),
                    "tier": entry.get("tier"),
                    "tier_reason": entry.get("tier_reason"),
                    "role_hints": summary.get("role_hints") or [],
                    "symbol": summary.get("symbol"),
                    "file_kind": summary.get("file_kind"),
                }
            )
            files_accessed.append({"path": rel_entry, "source": "manifest", "reason": "Listed from manifest and cached summary for the selected directory."})
        else:
            entries = list(child.get("entries") or [])
            sample_summaries = [
                summary_lookup.get(str(item.get("path") or ""))
                for item in entries[:8]
                if summary_lookup.get(str(item.get("path") or ""))
            ]
            child_entries.append(
                {
                    "name": child.get("name"),
                    "path": child.get("path"),
                    "type": "directory",
                    "summary": _describe_directory_children(sample_summaries, []),
                    "child_count": len(entries),
                    "sample_files": [str(item.get("path") or "") for item in sample_summaries[:4]],
                }
            )
            for item in sample_summaries[:4]:
                files_accessed.append({"path": str(item.get("path") or ""), "source": "manifest_summary", "reason": f"Used to summarize the `{child.get('path')}/` folder."})

    file_rows = [item for item in child_entries if item["type"] == "file"]
    dir_rows = [item for item in child_entries if item["type"] == "directory"]
    directory_summary = _describe_directory_children(file_rows, doc_files)
    dependency_graph = _build_dependency_graph(codebase_context)
    models_summary = _build_models_summary(codebase_context)
    routes_summary = _build_routes_summary(codebase_context)
    prerequisites = _build_prerequisites_summary(workspace_path, codebase_context)
    markdown_lines = [
        f"# `{normalized or './'}`",
        "",
        "## What This Folder Contains",
        directory_summary,
        "",
        f"- Direct child folders: `{len(dir_rows)}`",
        f"- Direct child files: `{len(file_rows)}`",
    ]
    if doc_files:
        markdown_lines.extend(["", "## Local Documentation"])
        markdown_lines.extend([f"- `{item['path']}`" for item in doc_files])
    if dir_rows:
        markdown_lines.extend(["", "## Subdirectories"])
        markdown_lines.extend([f"- `{item['path']}/`: {item.get('summary') or 'Directory summary unavailable.'}" for item in dir_rows[:24]])
    if file_rows:
        markdown_lines.extend(["", "## Files"])
        markdown_lines.extend([f"- `{item['path']}`: {item.get('summary') or 'File summary unavailable.'}" for item in file_rows[:48]])

    return {
        "kind": "directory",
        "path": normalized,
        "name": target_path.name or "codebase",
        "breadcrumbs": _codebase_doc_breadcrumbs(normalized),
        "summary": directory_summary,
        "stats": {
            "directories": len(dir_rows),
            "files": len(file_rows),
        },
        "children": child_entries,
        "docs": doc_files,
        "dependency_graph": dependency_graph,
        "all_models": models_summary,
        "all_routes": routes_summary,
        "prerequisites": prerequisites,
        "markdown": "\n".join(markdown_lines),
        "trace": {
            "approach": "Read the selected directory directly, summarized its immediate children, and sampled nested files for folder-level explanations.",
            "files_accessed": [
                *files_accessed[:48],
                *[
                    {"path": item["path"], "source": "docs", "reason": "Documentation context for the selected directory."}
                    for item in doc_files
                ],
            ],
            "commands_ran": [],
        },
    }


def _build_codebase_doc_payload(project: Project, rel_path: str = "") -> dict:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        raise FileNotFoundError("Project workspace is not available")
    codebase_context = build_blueprint_context(project, workspace_path)
    target_path, normalized = _codebase_doc_target(workspace_path, rel_path)
    if not target_path.exists():
        raise FileNotFoundError(f"Path not found: {normalized}")
    if target_path.is_file():
        return _build_file_doc_payload(project, workspace_path, normalized, codebase_context)
    return _build_directory_doc_payload(project, workspace_path, normalized, codebase_context)


def _detect_workspace_package_manager(workspace_path: Path | None, package_data: dict) -> str:
    package_manager = str(package_data.get("packageManager") or "").strip().lower()
    if package_manager:
        return package_manager.split("@", 1)[0]
    if workspace_path and (workspace_path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if workspace_path and (workspace_path / "pnpm-workspace.yaml").exists():
        return "pnpm"
    if workspace_path and (workspace_path / "yarn.lock").exists():
        return "yarn"
    if workspace_path and ((workspace_path / "bun.lock").exists() or (workspace_path / "bun.lockb").exists()):
        return "bun"
    if workspace_path and (workspace_path / "package-lock.json").exists():
        return "npm"
    return "npm" if package_data else ""


def _run_script_command(package_manager: str, script_name: str) -> str:
    script = str(script_name or "").strip()
    if not script:
        return ""
    if package_manager == "npm":
        return f"npm run {script}"
    if package_manager in {"pnpm", "yarn", "bun"}:
        return f"{package_manager} {script}"
    return script


def _extract_shell_commands(text: str) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    in_block = False
    command_prefix = re.compile(
        r"^(pnpm|npm|yarn|bun|openclaw|python|pip|uv|poetry|docker|cargo|go|make|swift|xcodebuild|adb|bash|sh|\./)",
        re.IGNORECASE,
    )

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_block = not in_block
            continue

        candidates: list[str] = []
        if in_block:
            candidate = line.split("#", 1)[0].strip()
            if candidate:
                candidates.append(candidate)
        else:
            for match in re.finditer(r"`([^`]+)`", raw_line):
                candidate = match.group(1).strip()
                if candidate:
                    candidates.append(candidate)

        for candidate in candidates:
            if not command_prefix.match(candidate):
                continue
            if candidate not in seen:
                seen.add(candidate)
                commands.append(candidate)

    return commands


def _pick_command(commands: list[str], *keywords: str) -> str:
    wanted = [keyword.lower() for keyword in keywords if keyword]
    matches = []
    for command in commands:
        lowered = command.lower()
        if all(keyword in lowered for keyword in wanted):
            matches.append(command)
    if not matches:
        return ""
    matches.sort(key=lambda item: (len(item.split()), len(item)), reverse=True)
    return matches[0]


def _top_repository_areas(codebase_context: dict, limit: int = 5) -> list[str]:
    directories = []
    for directory, _count in sorted((codebase_context.get("directory_counts") or {}).items(), key=lambda item: (-item[1], item[0])):
        name = str(directory or "").strip()
        if not name or name in {".", ".git", ".devhub", ".claude", ".claude-backup2", ".code-review-graph", "node_modules", "__pycache__", "data"}:
            continue
        directories.append(f"{name}/")
        if len(directories) >= limit:
            break
    return directories


def _guidance_item_text(item) -> str:
    if isinstance(item, dict):
        return " ".join(
            str(item.get(key) or "")
            for key in ("step", "task", "command", "instructions", "why_important", "explanation", "os_note", "category")
        ).strip().lower()
    return str(item or "").strip().lower()


def _guidance_field_needs_refresh(value, field_name: str) -> bool:
    items = _blueprint_list(value)
    if not items:
        return True

    markers = {
        "setup_steps": {
            "clone the repository",
            "install dependencies",
            "run migrations",
            "start the server",
            "python manage.py migrate",
            "python manage.py runserver",
            "run onboarding",
            "set up development environment",
            "review repository map",
            "read local setup docs",
            "run the project",
        },
        "onboarding_checklist": {
            "read the repo map",
            "inspect runtime entrypoints",
            "review onboarding first",
            "open the blueprint",
            "inspect architecture",
        },
        "gotchas": {
            "areas without evidence should be treated as unknown",
            "ai blueprint generation failed",
            "use .devhub/repo-map.md",
            "no gotchas were documented",
        },
    }.get(field_name, set())

    texts = [_guidance_item_text(item) for item in items]
    generic_hits = sum(1 for text in texts if any(marker in text for marker in markers))
    if generic_hits == len(texts):
        return True
    if len(texts) <= 3 and generic_hits >= max(1, len(texts) - 1):
        return True
    return False


DESIGN_DOC_TEMPLATE_MARKERS = {
    "third-party services",
    "additional functionalities",
    "<repository-url>",
    "specifies the settings module for django",
    "use pytest for unit testing",
    "django's test client",
    "utilize cypress",
    "ensure secure handling of user credentials and tokens",
    "consider implementing caching strategies",
    "restful principles for api design",
    "avoid database inconsistencies",
    "no tracked features yet",
}


def _normalize_design_doc_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _looks_like_design_doc_template(value) -> bool:
    normalized = _normalize_design_doc_text(value)
    if not normalized:
        return False
    return any(marker in normalized for marker in DESIGN_DOC_TEMPLATE_MARKERS)


def _filter_design_doc_dict_items(items: list, text_keys: tuple[str, ...]) -> list[dict]:
    filtered: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        combined = " ".join(str(item.get(key) or "") for key in text_keys).strip()
        if not combined or _looks_like_design_doc_template(combined):
            continue
        filtered.append(item)
    return filtered


def _filter_design_doc_strings(items: list) -> list[str]:
    filtered: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or _looks_like_design_doc_template(text):
            continue
        filtered.append(text)
    return filtered


def _dedupe_json_items(items: list) -> list:
    deduped = []
    seen = set()
    for item in items:
        key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _manifest_paths(codebase_context: dict) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for item in codebase_context.get("manifest") or []:
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if not path or path in seen or _is_devhub_internal_path(path):
            continue
        seen.add(path)
        paths.append(path)
    return paths


def _normalize_rel_dir(value: str) -> str:
    normalized = str(value or "").replace("\\", "/").strip().strip("/")
    return "" if normalized in {"", "."} else normalized


def _format_path_list(paths: list[str], max_paths: int = 3) -> str:
    unique = []
    seen = set()
    for path in paths:
        normalized = str(path or "").replace("\\", "/").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(f"`{normalized}`")
    if not unique:
        return ""
    shown = unique[:max_paths]
    if len(shown) == 1:
        return shown[0]
    if len(shown) == 2:
        return f"{shown[0]} and {shown[1]}"
    return f"{', '.join(shown[:-1])}, and {shown[-1]}"


def _prefix_command_for_dir(rel_dir: str, command: str) -> str:
    normalized = _normalize_rel_dir(rel_dir)
    command_text = str(command or "").strip()
    if not command_text:
        return ""
    if not normalized:
        return command_text
    target = f"\"{normalized}\"" if " " in normalized else normalized
    return f"cd {target} && {command_text}"


def _workspace_package_manifests(workspace_path: Path, codebase_context: dict) -> list[dict]:
    manifests: list[dict] = []
    for rel_path in _manifest_paths(codebase_context):
        if PurePosixPath(rel_path).name.lower() != "package.json":
            continue
        file_path = workspace_path / rel_path
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        rel_dir = _normalize_rel_dir(PurePosixPath(rel_path).parent.as_posix())
        scripts = payload.get("scripts") if isinstance(payload.get("scripts"), dict) else {}
        manifests.append({
            "path": rel_path,
            "rel_dir": rel_dir,
            "name": str(payload.get("name") or PurePosixPath(rel_path).parent.name or "package").strip(),
            "package_manager": _detect_workspace_package_manager(file_path.parent, payload) or "npm",
            "scripts": scripts,
            "workspaces": bool(payload.get("workspaces")) or (rel_dir == "" and (workspace_path / "pnpm-workspace.yaml").exists()),
        })
    manifests.sort(key=lambda item: (item.get("rel_dir") != "", str(item.get("rel_dir") or ""), str(item.get("path") or "")))
    return manifests


def _workspace_python_roots(workspace_path: Path, codebase_context: dict) -> list[dict]:
    roots: dict[str, dict] = {}
    manifest_paths = _manifest_paths(codebase_context)
    for rel_path in manifest_paths:
        name = PurePosixPath(rel_path).name.lower()
        if name not in {"manage.py", "requirements.txt", "requirements-dev.txt", "pyproject.toml", "pipfile", "poetry.lock", "uv.lock"}:
            continue
        rel_dir = _normalize_rel_dir(PurePosixPath(rel_path).parent.as_posix())
        entry = roots.setdefault(rel_dir, {
            "rel_dir": rel_dir,
            "manage_py": "",
            "requirements": "",
            "pyproject": "",
            "tooling": [],
            "framework": "",
        })
        if name == "manage.py":
            entry["manage_py"] = rel_path
            manage_text = _read_workspace_excerpt(workspace_path, rel_path, limit=4000).lower()
            if "django" in manage_text or "settings" in manage_text:
                entry["framework"] = "django"
        elif name == "requirements.txt" or (name == "requirements-dev.txt" and not entry.get("requirements")):
            entry["requirements"] = rel_path
        elif name == "pyproject.toml":
            entry["pyproject"] = rel_path
        else:
            entry.setdefault("tooling", []).append(rel_path)

    for rel_dir, entry in roots.items():
        if entry.get("framework"):
            continue
        prefix = f"{rel_dir}/" if rel_dir else ""
        if any(path.startswith(prefix) and PurePosixPath(path).name.lower() == "settings.py" for path in manifest_paths):
            entry["framework"] = "django"

    ordered = list(roots.values())
    ordered.sort(
        key=lambda item: (
            item.get("rel_dir") != "",
            str(item.get("rel_dir") or ""),
            0 if item.get("manage_py") else 1,
            0 if item.get("requirements") else 1,
        )
    )
    return ordered


def _env_template_paths(workspace_path: Path, codebase_context: dict) -> list[str]:
    candidates: list[str] = []
    for item in _codebase_summary_pool(codebase_context):
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if not path:
            continue
        file_kind = str(item.get("file_kind") or "").strip().lower()
        file_name = PurePosixPath(path).name.lower()
        if file_kind == "env-template" or file_name in {".env.example", ".env.sample", ".env.template", ".env.local.example", ".env.development.example"}:
            candidates.append(path)
    if not candidates:
        for rel_path in _manifest_paths(codebase_context):
            file_name = PurePosixPath(rel_path).name.lower()
            if file_name in {".env.example", ".env.sample", ".env.template", ".env.local.example", ".env.development.example"}:
                candidates.append(rel_path)
    return _dedupe_json_items(candidates)[:12]


def _sanitize_env_value(value: str) -> str:
    text = str(value or "").strip().strip('"').strip("'")
    if not text:
        return ""
    lowered = text.lower()
    if any(token in lowered for token in ("<", ">", "changeme", "replace", "your-", "your_", "example", "sample", "placeholder", "dummy")):
        return text
    if re.match(r"^(sk-|ghp_|AIza|ya29\.)", text):
        return "<configured secret>"
    if len(text) >= 24 and not re.match(r"^(https?://|[A-Za-z]:/|/|\.{0,2}/)", text) and not re.fullmatch(r"[0-9.]+", text):
        return "<configured value>"
    return text


def _infer_env_category(name: str) -> str:
    upper = str(name or "").upper()
    if upper.startswith(("VITE_", "NEXT_PUBLIC_", "PUBLIC_")):
        return "frontend"
    if any(token in upper for token in ("OPENAI", "ANTHROPIC", "GEMINI", "VERTEX", "MODEL", "LLM", "AI_")):
        return "ai"
    if any(token in upper for token in ("SECRET", "TOKEN", "KEY", "PASSWORD", "CREDENTIAL")):
        return "secret"
    if any(token in upper for token in ("DB_", "DATABASE", "POSTGRES", "MYSQL", "SQLITE", "REDIS", "MONGO")):
        return "database"
    if any(token in upper for token in ("AUTH", "JWT", "SESSION", "CSRF", "CORS", "ALLOWED_HOSTS")):
        return "auth"
    if any(token in upper for token in ("S3", "BUCKET", "STORAGE", "UPLOAD", "MEDIA")):
        return "storage"
    if any(token in upper for token in ("URL", "HOST", "PORT", "ORIGIN", "BASE_URL", "API_BASE")):
        return "runtime"
    return "config"


def _is_ai_related_env(name: str) -> bool:
    upper = str(name or "").upper()
    return any(token in upper for token in ("OPENAI", "OPENROUTER", "ANTHROPIC", "CLAUDE", "GEMINI", "VERTEX", "GOOGLE_API", "GOOGLE_CLOUD", "MODEL", "LLM", "AI_"))


def _is_ai_override_env(name: str) -> bool:
    upper = str(name or "").upper()
    if not _is_ai_related_env(upper):
        return False
    return any(
        token in upper
        for token in ("MODEL", "BASE_URL", "PROVIDER", "MODE", "LOCATION", "PROJECT", "CLI_COMMAND")
    )


def _env_family_prefix(name: str) -> str:
    upper = str(name or "").upper()
    if "_" not in upper:
        return ""
    prefix = upper.split("_", 1)[0].strip()
    return prefix if prefix and prefix not in {"VITE", "NEXT", "PUBLIC", "DATABASE", "DJANGO", "NODE"} else ""


def _is_ai_family_env(name: str, ai_prefixes: set[str]) -> bool:
    upper = str(name or "").upper()
    if _is_ai_related_env(upper):
        return True
    prefix = _env_family_prefix(upper)
    if not prefix or prefix not in ai_prefixes:
        return False
    return any(
        upper.endswith(suffix)
        for suffix in ("_API_KEY", "_MODEL", "_BASE_URL", "_PROVIDER", "_MODE", "_LOCATION", "_PROJECT", "_CLI_COMMAND", "_ACCESS_TOKEN")
    )


def _summarize_ai_env_entry(variable_names: list[str]) -> dict:
    credential_candidates = [
        name for name in variable_names
        if name in {
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENROUTER_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
        }
    ]
    extra_candidates = [
        name for name in variable_names
        if _is_ai_override_env(name)
    ]
    examples = credential_candidates[:4] + [name for name in extra_candidates[:2] if name not in credential_candidates[:4]]
    description = "Multiple AI or model-provider variables were detected. Credentials are usually the actionable values to set locally, while provider, model, base URL, or location fields are often optional overrides."
    if examples:
        description = f"{description} Common variables include {', '.join(f'`{name}`' for name in examples)}."
    return {
        "name": "AI provider configuration",
        "required": False,
        "default": "No default detected",
        "example": " / ".join(examples[:3]) if examples else "Provider-specific credential env vars",
        "category": "ai",
        "description": description,
    }


def _env_display_score(name: str, item: dict, references: list[str], from_template: bool) -> int:
    upper = str(name or "").upper()
    score = 0
    if from_template:
        score += 10
    score += min(8, len(references) * 2)
    if upper.startswith(("VITE_", "NEXT_PUBLIC_", "PUBLIC_")):
        score += 8
    if upper in {"DATABASE_URL", "SECRET_KEY", "DJANGO_SETTINGS_MODULE", "PORT", "HOST"}:
        score += 6
    if upper in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"}:
        score += 5
    if any(path.lower().endswith("settings.py") for path in references):
        score += 4
    if any("/frontend/" in path.lower() or path.lower().startswith("frontend/") for path in references):
        score += 3
    if _is_ai_override_env(upper) and not from_template:
        score -= 6
    if item.get("category") == "secret":
        score += 2
    if not references and not from_template:
        score -= 2
    return score


def _normalized_loose_tokens(value: str) -> set[str]:
    tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", str(value or "").lower())
        if token and token not in {"the", "a", "an", "and", "or", "to", "of", "for", "in", "is", "are", "be", "by", "with", "this", "that", "it", "from"}
    }
    return tokens


def _dedupe_similar_strings(items: list[str], similarity_threshold: float = 0.72) -> list[str]:
    deduped: list[str] = []
    token_sets: list[set[str]] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        current_tokens = _normalized_loose_tokens(text)
        normalized_text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        duplicate = False
        for existing, existing_tokens in zip(deduped, token_sets):
            existing_normalized = re.sub(r"[^a-z0-9]+", " ", str(existing).lower()).strip()
            if not current_tokens or not existing_tokens:
                if normalized_text == existing_normalized:
                    duplicate = True
                    break
                continue
            overlap = len(current_tokens & existing_tokens) / max(1, len(current_tokens | existing_tokens))
            if overlap >= similarity_threshold or normalized_text in existing_normalized or existing_normalized in normalized_text:
                duplicate = True
                break
        if duplicate:
            continue
        deduped.append(text)
        token_sets.append(current_tokens)
    return deduped


def _scan_environment_variable_usage(workspace_path: Path, codebase_context: dict, variable_names: list[str]) -> dict[str, list[str]]:
    if not variable_names:
        return {}
    usage = {name: [] for name in variable_names}
    candidate_paths: list[str] = []
    for item in _codebase_summary_pool(codebase_context, limit=240):
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if not path:
            continue
        file_kind = str(item.get("file_kind") or "").strip().lower()
        lowered_path = path.lower()
        if file_kind == "env-template":
            continue
        if file_kind in {"config", "build-config", "api-module", "routing-module", "package-manifest", "container-config", "script"} or any(
            token in lowered_path for token in ("settings", "config", "runtime", "process", "consumer", "executor", "sandbox", "workspace", "views", "urls", "docker", "compose", "vite", "next")
        ):
            candidate_paths.append(path)
    if not candidate_paths:
        candidate_paths = _manifest_paths(codebase_context)[:80]

    for rel_path in _dedupe_json_items(candidate_paths)[:80]:
        text = _read_workspace_excerpt(workspace_path, rel_path, limit=18000)
        if not text:
            continue
        for name in variable_names:
            if name in text and rel_path not in usage[name]:
                usage[name].append(rel_path)
    return usage


def _derive_environment_variables(workspace_path: Path, codebase_context: dict) -> list[dict]:
    parsed: dict[str, dict] = {}
    template_paths = _env_template_paths(workspace_path, codebase_context)
    parsed_from_template = bool(template_paths)

    for rel_path in template_paths:
        content = _read_workspace_excerpt(workspace_path, rel_path, limit=16000)
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            if stripped.lower().startswith("export "):
                stripped = stripped[7:].strip()
            name, raw_value = stripped.split("=", 1)
            env_name = name.strip()
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", env_name):
                continue
            sanitized = _sanitize_env_value(raw_value)
            entry = parsed.setdefault(env_name, {
                "name": env_name,
                "required": False,
                "default": "",
                "example": "",
                "category": _infer_env_category(env_name),
            })
            if sanitized and not entry.get("default"):
                entry["default"] = sanitized
            if sanitized and not entry.get("example"):
                entry["example"] = sanitized
            placeholder = not sanitized or any(token in sanitized.lower() for token in ("<", ">", "changeme", "replace", "your-", "your_", "placeholder", "dummy"))
            entry["required"] = bool(entry.get("required")) or placeholder or entry["category"] == "secret"

    if not parsed:
        pattern_hits: dict[str, dict] = {}
        patterns = [
            r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]",
            r"os\.environ(?:\.get)?\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\]",
            r"os\.environ\.get\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]",
            r"process\.env\.([A-Z][A-Z0-9_]*)",
            r"import\.meta\.env\.([A-Z][A-Z0-9_]*)",
        ]
        for rel_path in _manifest_paths(codebase_context)[:500]:
            text = _read_workspace_excerpt(workspace_path, rel_path, limit=16000)
            if not text:
                continue
            for pattern in patterns:
                for match in re.findall(pattern, text):
                    if match not in pattern_hits:
                        pattern_hits[match] = {
                            "name": match,
                            "required": True,
                            "default": "",
                            "example": "",
                            "category": _infer_env_category(match),
                        }
        parsed = pattern_hits

    usage = _scan_environment_variable_usage(workspace_path, codebase_context, sorted(parsed.keys()))
    env_vars: list[dict] = []
    ai_related_names: list[str] = []
    scored_items: list[tuple[int, dict]] = []
    ai_prefixes = {
        _env_family_prefix(name)
        for name in parsed.keys()
        if _env_family_prefix(name) and _is_ai_related_env(name)
    }

    for name in sorted(parsed.keys()):
        item = dict(parsed[name])
        category = str(item.get("category") or _infer_env_category(name))
        references = usage.get(name) or []
        ai_family_env = _is_ai_family_env(name, ai_prefixes)
        description_prefix = {
            "frontend": "Frontend-facing setting that affects the client bundle or browser runtime.",
            "ai": "AI or model-provider configuration referenced by the application runtime.",
            "secret": "Credential or secret that should be supplied per environment rather than committed into source.",
            "database": "Database connection or persistence setting used by the application runtime.",
            "auth": "Authentication, session, or trust-boundary setting that changes request security behavior.",
            "storage": "Storage or upload configuration used to locate buckets, files, or media backends.",
            "runtime": "Runtime or network setting that changes host, port, origin, or base URL behavior.",
            "config": "Environment-driven configuration that changes how the application boots or behaves.",
        }.get(category, "Environment-driven configuration used by the project at runtime.")
        if references:
            description = f"{description_prefix} Referenced in {_format_path_list(references, max_paths=2)}."
        elif template_paths:
            description = f"{description_prefix} Declared in {_format_path_list(template_paths[:2], max_paths=2)}."
        else:
            description = description_prefix
        if ai_family_env and category == "secret":
            category = "ai"
        item["category"] = category
        item["description"] = description
        if ai_family_env:
            ai_related_names.append(name)
        score = _env_display_score(name, item, references, parsed_from_template)
        if ai_family_env and not parsed_from_template and _is_ai_override_env(name):
            score -= 2
        item["_score"] = score
        scored_items.append((score, item))

    collapse_ai_settings = not parsed_from_template and len(ai_related_names) >= 8
    if collapse_ai_settings:
        env_vars.append(_summarize_ai_env_entry(sorted(ai_related_names)))

    for score, item in sorted(scored_items, key=lambda pair: (-pair[0], str(pair[1].get("name") or ""))):
        name = str(item.get("name") or "")
        if collapse_ai_settings and _is_ai_family_env(name, ai_prefixes):
            continue
        if score < (3 if parsed_from_template else 0) and env_vars:
            continue
        cleaned = {key: value for key, value in item.items() if key != "_score"}
        env_vars.append(cleaned)

    return _dedupe_json_items(env_vars)[:30]


def _detect_coverage_target(workspace_path: Path, codebase_context: dict) -> str:
    config_names = {
        "package.json",
        "pyproject.toml",
        "pytest.ini",
        "mypy.ini",
        "tox.ini",
        "setup.cfg",
        "vitest.config.ts",
        "vitest.config.js",
        "jest.config.js",
        "jest.config.ts",
    }
    patterns = [
        r"coverageThreshold[^0-9]{0,80}(\d+)",
        r"fail_under\s*=\s*(\d+)",
        r"--cov-fail-under(?:=|\s+)(\d+)",
    ]
    for rel_path in _manifest_paths(codebase_context):
        if PurePosixPath(rel_path).name.lower() not in config_names:
            continue
        text = _read_workspace_excerpt(workspace_path, rel_path, limit=18000)
        if not text:
            continue
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return f"{match.group(1)}% minimum coverage detected in `{rel_path}`."
    return "No numeric coverage threshold was detected in the indexed test config."


def _derive_testing_strategy(project: Project, codebase_context: dict) -> dict:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return {}

    manifest_paths = _manifest_paths(codebase_context)
    python_test_paths = [path for path in manifest_paths if re.search(r"(^|/)(test_.*\.py|tests\.py)$", path, re.IGNORECASE) or "/tests/" in path.lower()]
    js_test_paths = [path for path in manifest_paths if re.search(r"(\.test|\.spec)\.(js|jsx|ts|tsx)$", path, re.IGNORECASE)]
    e2e_paths = [path for path in manifest_paths if any(token in path.lower() for token in ("cypress/", "playwright/", "/e2e/", "e2e."))]
    integration_paths = [path for path in manifest_paths if any(token in path.lower() for token in ("/integration/", "integration_test", "/api/tests", "/tests/api"))]

    run_commands: list[str] = []
    for root in _workspace_python_roots(workspace_path, codebase_context):
        rel_dir = str(root.get("rel_dir") or "")
        if root.get("manage_py") and any(path.startswith(f"{rel_dir}/") if rel_dir else True for path in python_test_paths):
            run_commands.append(_prefix_command_for_dir(rel_dir, "python manage.py test"))
        elif root.get("pyproject") or any(PurePosixPath(path).name.lower() == "pytest.ini" and path.startswith(f"{rel_dir}/") for path in manifest_paths):
            run_commands.append(_prefix_command_for_dir(rel_dir, "pytest"))

    for manifest in _workspace_package_manifests(workspace_path, codebase_context):
        scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
        if scripts.get("test"):
            run_commands.append(_prefix_command_for_dir(str(manifest.get("rel_dir") or ""), _run_script_command(str(manifest.get("package_manager") or "npm"), "test")))

    run_command = "\n".join(_dedupe_json_items(run_commands)[:4]).strip()
    if python_test_paths and js_test_paths:
        unit = f"Backend tests live in {_format_path_list(python_test_paths, max_paths=1)} and frontend/unit specs also exist in {_format_path_list(js_test_paths, max_paths=1)}."
    elif python_test_paths:
        unit = f"Python test modules are present in {_format_path_list(python_test_paths, max_paths=2)}."
    elif js_test_paths:
        unit = f"JavaScript or TypeScript test files are present in {_format_path_list(js_test_paths, max_paths=2)}."
    else:
        unit = "No dedicated unit-test files were detected from the indexed repository paths."

    if integration_paths:
        integration = f"Integration-style coverage appears in {_format_path_list(integration_paths, max_paths=2)}."
    elif any("/api/tests" in path.lower() for path in python_test_paths):
        integration = f"API-oriented test coverage appears to live alongside backend tests in {_format_path_list([path for path in python_test_paths if '/api/tests' in path.lower()], max_paths=1)}."
    else:
        integration = "No separate integration-test directory was detected from indexed files."

    if e2e_paths:
        e2e = f"Browser or end-to-end coverage is present in {_format_path_list(e2e_paths, max_paths=2)}."
    else:
        e2e = "No dedicated browser-level or end-to-end suite was detected from the indexed repository."

    return {
        "unit": unit,
        "integration": integration,
        "e2e": e2e,
        "coverage_target": _detect_coverage_target(workspace_path, codebase_context),
        "run_command": run_command,
    }


def _scan_workspace_pattern_hits(workspace_path: Path, codebase_context: dict) -> dict[str, list[str]]:
    hits = {
        "shell_true": [],
        "csrf_exempt": [],
        "debug_true": [],
        "cors_allow_all": [],
        "secret_key_literal": [],
        "inmemory_channel_layer": [],
        "polling_loop": [],
        "sqlite": [],
    }
    candidate_paths: list[str] = []
    allowed_suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yml", ".yaml", ".ini", ".cfg"}
    for rel_path in _manifest_paths(codebase_context):
        lowered = rel_path.lower()
        file_name = PurePosixPath(rel_path).name.lower()
        suffix = PurePosixPath(rel_path).suffix.lower()
        if file_name not in {"manage.py", "package.json"} and suffix not in allowed_suffixes:
            continue
        if any(token in lowered for token in ("settings", "config", "consumer", "executor", "sandbox", "workspace", "runtime", "process", "channel", "views", "urls", "auth", "manage.py", "package.json", "pyproject.toml", "pytest.ini", "eslint", "tsconfig", "prettier", "mypy", "ruff")):
            candidate_paths.append(rel_path)
    if not candidate_paths:
        candidate_paths = _manifest_paths(codebase_context)[:120]

    for rel_path in _dedupe_json_items(candidate_paths)[:120]:
        text = _read_workspace_excerpt(workspace_path, rel_path, limit=20000)
        if not text:
            continue
        lowered = text.lower()
        if re.search(r"shell\s*=\s*True", text):
            hits["shell_true"].append(rel_path)
        if re.search(r"@csrf_exempt\b|csrf_exempt\(", text):
            hits["csrf_exempt"].append(rel_path)
        if re.search(r"(?m)^\s*DEBUG\s*=\s*True\b", text):
            hits["debug_true"].append(rel_path)
        if re.search(r"(?m)^\s*CORS_ALLOW_ALL_ORIGINS\s*=\s*True\b", text):
            hits["cors_allow_all"].append(rel_path)
        if re.search(r"(?m)^\s*SECRET_KEY\s*=\s*['\"][^'\"]+['\"]", text):
            hits["secret_key_literal"].append(rel_path)
        if "inmemorychannellayer" in lowered:
            hits["inmemory_channel_layer"].append(rel_path)
        if ("while true" in lowered or "for (;;)" in lowered) and ("asyncio.sleep" in lowered or "sleep(" in lowered or "setinterval(" in lowered):
            hits["polling_loop"].append(rel_path)
        if "db.sqlite3" in lowered or "sqlite3" in lowered:
            hits["sqlite"].append(rel_path)

    return {key: _dedupe_json_items(value) for key, value in hits.items()}


def _derive_code_quality_standards(workspace_path: Path, codebase_context: dict) -> list[dict]:
    standards: list[dict] = []

    def add(tool: str, purpose: str, config_file: str) -> None:
        if not tool or not config_file:
            return
        standards.append({
            "tool": tool,
            "purpose": purpose,
            "config_file": config_file,
        })

    manifest_paths = _manifest_paths(codebase_context)
    package_manifests = _workspace_package_manifests(workspace_path, codebase_context)

    for rel_path in manifest_paths:
        file_name = PurePosixPath(rel_path).name.lower()
        if file_name in {"eslint.config.js", "eslint.config.cjs", ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json"}:
            add("ESLint", "Lint rules for JavaScript or TypeScript source are configured here.", rel_path)
        elif file_name.startswith("tsconfig") and file_name.endswith(".json"):
            add("TypeScript", "Compiler settings here control type-checking, module resolution, and editor/tooling expectations.", rel_path)
        elif file_name in {".prettierrc", ".prettierrc.json", ".prettierrc.js", "prettier.config.js", "prettier.config.cjs"}:
            add("Prettier", "Formatting rules are defined here to keep source files and generated diffs consistent.", rel_path)
        elif file_name in {"pytest.ini", "tox.ini"}:
            add("Pytest", "Python test discovery and execution settings are configured here.", rel_path)
        elif file_name in {"mypy.ini"}:
            add("MyPy", "Static type-checking rules for Python modules are configured here.", rel_path)
        elif file_name in {"ruff.toml", ".ruff.toml"}:
            add("Ruff", "Python linting and formatting rules are configured here.", rel_path)

    for rel_path in manifest_paths:
        if PurePosixPath(rel_path).name.lower() not in {"pyproject.toml", "setup.cfg"}:
            continue
        text = _read_workspace_excerpt(workspace_path, rel_path, limit=16000)
        if not text:
            continue
        lowered = text.lower()
        if "[tool.ruff" in lowered or "[ruff" in lowered:
            add("Ruff", "Python linting or formatting rules are defined in this shared tool config.", rel_path)
        if "[tool.black" in lowered:
            add("Black", "Python formatting expectations are defined here.", rel_path)
        if "[tool.mypy" in lowered or "[mypy" in lowered:
            add("MyPy", "Python type-checking rules are defined here.", rel_path)
        if "[tool.pytest" in lowered or "[tool.pytest.ini_options" in lowered or "[pytest" in lowered:
            add("Pytest", "Python test discovery and execution settings are defined here.", rel_path)

    for manifest in package_manifests:
        scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
        path = str(manifest.get("path") or "")
        package_manager = str(manifest.get("package_manager") or "npm")
        if scripts.get("lint") and not any(item.get("tool") == "ESLint" for item in standards):
            add("Lint script", f"The package manifest exposes `{_run_script_command(package_manager, 'lint')}` as the repo's JavaScript/TypeScript lint entrypoint.", path)
        if scripts.get("typecheck") and not any(item.get("tool") == "TypeScript" for item in standards):
            add("Type checking", f"The package manifest exposes `{_run_script_command(package_manager, 'typecheck')}` for static type validation.", path)
        if scripts.get("format") and not any(item.get("tool") == "Prettier" for item in standards):
            add("Format script", f"The package manifest exposes `{_run_script_command(package_manager, 'format')}` for source formatting.", path)

    return _dedupe_json_items(standards)[:10]


def _derive_quality_guidance(project: Project, codebase_context: dict) -> dict:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return {
            "security_considerations": [],
            "performance_notes": [],
            "testing_strategy": {},
            "code_quality_standards": [],
        }

    hits = _scan_workspace_pattern_hits(workspace_path, codebase_context)
    api_reference = _blueprint_list(codebase_context.get("api_reference"))
    mutating_public = [
        f"{item.get('method')} {item.get('path')}"
        for item in api_reference
        if str(item.get("method") or "").upper() in {"POST", "PUT", "PATCH", "DELETE"} and not item.get("auth_required")
    ]
    csrf_exempt_public = [
        f"{item.get('method')} {item.get('path')}"
        for item in api_reference
        if str(item.get("method") or "").upper() in {"POST", "PUT", "PATCH", "DELETE"} and "csrf is exempted" in str(item.get("access") or "").lower()
    ]

    security: list[dict] = []
    if hits.get("shell_true"):
        security.append({
            "area": "Shell-based command execution",
            "severity": "high",
            "description": f"{_format_path_list(hits.get('shell_true') or [], max_paths=2)} uses subprocess calls with `shell=True`, so command text is expanded by the shell instead of running as structured argv.",
        })
    if hits.get("debug_true") or hits.get("cors_allow_all") or hits.get("secret_key_literal"):
        exposed_settings = []
        if hits.get("debug_true"):
            exposed_settings.append("`DEBUG = True`")
        if hits.get("cors_allow_all"):
            exposed_settings.append("`CORS_ALLOW_ALL_ORIGINS = True`")
        if hits.get("secret_key_literal"):
            exposed_settings.append("a literal `SECRET_KEY`")
        settings_paths = (hits.get("debug_true") or []) + (hits.get("cors_allow_all") or []) + (hits.get("secret_key_literal") or [])
        security.append({
            "area": "Development settings exposed",
            "severity": "high",
            "description": f"{_format_path_list(settings_paths, max_paths=2)} enables {', '.join(exposed_settings)}. Those defaults are convenient locally but should not be treated as production-safe runtime config.",
        })
    if mutating_public:
        severity = "high" if csrf_exempt_public else "medium"
        description = f"The routed API catalog shows mutating operations without explicit auth or permission markers, including {', '.join(f'`{item}`' for item in mutating_public[:3])}."
        if csrf_exempt_public:
            description += f" CSRF-exempt handlers were also detected for {', '.join(f'`{item}`' for item in csrf_exempt_public[:2])}."
        security.append({
            "area": "Mutating routes without explicit auth markers",
            "severity": severity,
            "description": description,
        })

    performance: list[dict] = []
    if hits.get("inmemory_channel_layer"):
        performance.append({
            "area": "In-memory channel layer",
            "impact": "high",
            "description": f"{_format_path_list(hits.get('inmemory_channel_layer') or [], max_paths=1)} uses `InMemoryChannelLayer`, which is fine for local development but does not support multi-process or horizontally scaled websocket delivery.",
        })
    if hits.get("polling_loop"):
        performance.append({
            "area": "Polling-based process or websocket loops",
            "impact": "medium",
            "description": f"{_format_path_list(hits.get('polling_loop') or [], max_paths=2)} contains long-running polling loops with sleep calls, which can become chatty under many concurrent sessions.",
        })
    if hits.get("sqlite"):
        performance.append({
            "area": "SQLite-backed local state",
            "impact": "medium",
            "description": f"{_format_path_list(hits.get('sqlite') or [], max_paths=1)} references SQLite-style local persistence, which is convenient for development but can become a bottleneck for concurrent write-heavy workloads.",
        })

    return {
        "security_considerations": _dedupe_json_items(security)[:6],
        "performance_notes": _dedupe_json_items(performance)[:6],
        "testing_strategy": _derive_testing_strategy(project, codebase_context),
        "code_quality_standards": _derive_code_quality_standards(workspace_path, codebase_context),
    }


def _summary_path_with_tokens(codebase_context: dict, *tokens: str) -> str:
    wanted = [str(token or "").strip().lower() for token in tokens if str(token or "").strip()]
    best_path = ""
    best_score = 0
    for item in _codebase_summary_pool(codebase_context, limit=200):
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if not path:
            continue
        haystack = " ".join(
            str(value)
            for value in [
                path,
                item.get("summary"),
                item.get("purpose"),
                item.get("why"),
                item.get("how"),
                " ".join(item.get("routes") or []),
                " ".join(item.get("data_models") or []),
                " ".join(item.get("role_hints") or []),
                item.get("file_kind"),
            ]
            if value
        ).lower()
        score = sum(1 for token in wanted if token in haystack)
        if score > best_score:
            best_score = score
            best_path = path
    return best_path


def _setup_commands_by_kind(setup_steps: list[dict], *kinds: str) -> list[str]:
    wanted = {str(kind or "").strip().lower() for kind in kinds if str(kind or "").strip()}
    commands: list[str] = []
    for item in setup_steps:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        command = str(item.get("command") or "").strip()
        if wanted and kind not in wanted:
            continue
        if command and command not in commands:
            commands.append(command)
    return commands


def _derive_knowledge_guidance(project: Project, codebase_context: dict, setup_guidance: dict, quality_guidance: dict) -> dict:
    api_reference = _blueprint_list(codebase_context.get("api_reference"))
    database_schema = _blueprint_list(codebase_context.get("database_schema"))
    database_sources = _blueprint_list(codebase_context.get("database_source_files"))
    top_areas = _top_repository_areas(codebase_context)
    summary_pool = _codebase_summary_pool(codebase_context, limit=220)
    summary_paths = [str(item.get("path") or "").replace("\\", "/").strip() for item in summary_pool if str(item.get("path") or "").strip()]
    setup_steps = _blueprint_list(setup_guidance.get("setup_steps"))
    testing_strategy = quality_guidance.get("testing_strategy") if isinstance(quality_guidance.get("testing_strategy"), dict) else {}
    table_names = {str(item.get("table") or "").strip() for item in database_schema if str(item.get("table") or "").strip()}
    workspace_ops = [item for item in api_reference if "/workspace/" in str(item.get("path") or "")]
    route_paths = {str(item.get("path") or "").strip() for item in api_reference}
    has_workspace_runtime = bool(workspace_ops) and any(any(token in path.lower() for token in ("sandbox", "executor", "workspace", "consumer")) for path in summary_paths)
    has_feature_pipeline = (
        "/api/projects/<project_id>/pipeline/action/" in route_paths
        or {"Feature", "FeatureHistory", "FeatureApproval"} <= table_names
        or any(any(token in path.lower() for token in ("feature", "pipeline")) for path in summary_paths)
    )
    has_chat_memory = (
        any("/chat/" in path for path in route_paths)
        and ({"ChatMessage", "WorkingMemory", "EpisodicMemory", "SemanticMemory"} & table_names
             or any(any(token in path.lower() for token in ("memory.py", "project_chat", "chat")) for path in summary_paths))
    )
    has_blueprint_pipeline = (
        any(any(token in str(item.get("path") or "") for token in ("/documentation/", "/agent/deep-docs", "/documentation/runs/")) for item in api_reference)
        or any(any(token in path.lower() for token in ("deep_documentation.py", "architect.py", "documentation.py")) for path in summary_paths)
    )

    concepts: list[dict] = []

    def add_concept(concept: str, explanation: str, why_important: str, related_code: str = "", related_concepts: list[str] | None = None) -> None:
        if not concept or not explanation:
            return
        concepts.append({
            "concept": concept,
            "explanation": explanation,
            "why_important": why_important,
            "related_code": related_code,
            "related_concepts": related_concepts or [],
        })

    if has_workspace_runtime:
        add_concept(
            "Managed workspace execution",
            "The codebase exposes workspace-oriented APIs for filesystem access, process I/O, or runtime control, so project execution is mediated by backend handlers rather than only by direct local commands.",
            "Changes to terminals, preview flows, editors, or runtime state usually cross both client code and backend workspace or process-management modules.",
            _summary_path_with_tokens(codebase_context, "workspace", "executor", "sandbox"),
            ["Process IO", "Runtime control"],
        )

    if has_feature_pipeline:
        add_concept(
            "Tracked delivery workflow",
            "The repository models work items or pipeline stages explicitly, with backend routes and persisted records coordinating approval, implementation, or status changes.",
            "When work-item behavior changes, the source of truth is usually shared between API handlers, workflow models, and any UI that reflects those stages.",
            _summary_path_with_tokens(codebase_context, "Feature", "pipeline", "approval"),
            ["Feature lifecycle", "Background implementation"],
        )

    if has_blueprint_pipeline:
        add_concept(
            "Generated documentation pipeline",
            "Repository reference or documentation sections are assembled from indexed codebase evidence and generation steps, instead of living only as hand-maintained markdown.",
            "When generated docs look wrong, the fix is usually in indexing, extraction, or enrichment logic before it is in the rendering layer.",
            _summary_path_with_tokens(codebase_context, "deep_documentation", "architect", "documentation"),
            ["Repository indexing", "Documentation runs"],
        )

    if has_chat_memory:
        add_concept(
            "Persistent conversational context",
            "The project stores chat or memory state in backend models, which lets assistant-style flows reuse earlier context instead of treating each interaction as isolated.",
            "Changes to assistant behavior often involve both request handling and the persistence or retrieval layer that supplies context.",
            _summary_path_with_tokens(codebase_context, "project_chat", "memory", "ChatMessage"),
            ["Chat sessions", "Semantic retrieval"],
        )

    if database_schema and len(concepts) < 5:
        add_concept(
            "Backend data model",
            f"Structured backend records are defined for entities such as {', '.join(sorted(table_names)[:4])}.",
            "Those models tell you what the system persists for projects, work items, chat, and long-lived context, so they are the safest starting point before changing request payloads or workflows.",
            str(database_sources[0] or "") if database_sources else _summary_path_with_tokens(codebase_context, "models", "data-model"),
            ["Persistence", "API contracts"],
        )

    if api_reference and len(concepts) < 4:
        groups = []
        for item in api_reference:
            group = str(item.get("group") or "").strip()
            if group and group not in groups:
                groups.append(group)
        first_source = (api_reference[0].get("source") or {}) if isinstance(api_reference[0], dict) else {}
        route_source = str(first_source.get("url_file") or first_source.get("view_file") or "") if isinstance(first_source, dict) else ""
        add_concept(
            "Routed API surface",
            f"The backend exposes {len(api_reference)} routed API operations grouped into areas such as {', '.join(groups[:4]) or 'the detected route groups'}.",
            "This is the fastest way to map URL shape to handler ownership before changing backend behavior or frontend fetch calls.",
            route_source or _summary_path_with_tokens(codebase_context, "urls", "api"),
            ["Request handling", "Backend services"],
        )

    if top_areas and len(concepts) < 4:
        add_concept(
            "Repository surface areas",
            f"The repository is split across top-level areas such as {', '.join(top_areas[:4])}.",
            "Reading the repo as distinct surfaces makes it much easier to find the right runtime, config, and ownership boundary before editing.",
            _summary_path_with_tokens(codebase_context, "readme", "package", "config"),
            ["Local development", "Code ownership"],
        )

    if not concepts:
        for item in _codebase_summary_pool(codebase_context, limit=12):
            path = str(item.get("path") or "")
            purpose = str(item.get("purpose") or "").strip()
            why = str(item.get("why") or "").strip()
            if not path or not purpose or not why:
                continue
            concept_name = str(item.get("symbol") or PurePosixPath(path).stem.replace("_", " ").replace("-", " ").title()).strip()
            add_concept(concept_name, purpose, why, path, [str(item.get("file_kind") or "source")])
            if len(concepts) >= 4:
                break

    faq: list[dict] = []
    install_commands = _setup_commands_by_kind(setup_steps, "install")
    migrate_commands = _setup_commands_by_kind(setup_steps, "migrate")
    runtime_commands = _setup_commands_by_kind(setup_steps, "runtime")
    validate_commands = _setup_commands_by_kind(setup_steps, "validate")

    if install_commands or runtime_commands:
        run_parts: list[str] = []
        if install_commands:
            run_parts.append(f"install dependencies with {' and '.join(f'`{command}`' for command in install_commands[:2])}")
        if migrate_commands:
            run_parts.append(f"apply migrations with {' and '.join(f'`{command}`' for command in migrate_commands[:1])}")
        if len(runtime_commands) > 1:
            run_parts.append(
                "run the main app processes in separate terminals using "
                + " and ".join(f"`{command}`" for command in runtime_commands[:2])
            )
        elif runtime_commands:
            run_parts.append(f"start the main runtime with `{runtime_commands[0]}`")
        faq.append({
            "question": "How do I run the project locally?",
            "answer": "Start by " + ", then ".join(run_parts) + "." if run_parts else "Follow the setup steps captured from the repo manifests, env templates, and runtime entrypoints.",
        })
    if has_workspace_runtime:
        faq.append({
            "question": "How does project execution work?",
            "answer": "The client-facing runtime features route through workspace or process-management APIs, while backend modules handle file access, process I/O, and runtime state changes.",
        })
    if has_blueprint_pipeline:
        faq.append({
            "question": "How are generated docs or repository references produced?",
            "answer": "They are assembled from indexed repository context and generation logic, then merged into the stored project documentation state. If a section looks wrong, inspect extraction and enrichment before only changing display copy.",
        })
    if has_feature_pipeline:
        faq.append({
            "question": "How do tracked work items move through the system?",
            "answer": "Work items flow through explicit pipeline or status transitions backed by routes and persisted records, so workflow behavior usually spans both API handlers and data models.",
        })
    if testing_strategy:
        run_command = str(testing_strategy.get("run_command") or "").strip()
        faq.append({
            "question": "How should I validate changes before merging?",
            "answer": f"{testing_strategy.get('unit') or 'Review the detected test layout.'} Use `{run_command}` as the primary validation command." if run_command else str(testing_strategy.get("unit") or "Review the detected test layout before merging."),
        })
    if api_reference:
        source_files = []
        for item in api_reference[:6]:
            source = item.get("source") or {}
            if isinstance(source, dict):
                for key in ("url_file", "view_file"):
                    value = str(source.get(key) or "").strip()
                    if value and value not in source_files:
                        source_files.append(value)
        faq.append({
            "question": "Where are the API routes and handlers defined?",
            "answer": f"Start with the routed API catalog and the source files behind it, such as {_format_path_list(source_files, max_paths=2)}. The URL wiring tells you which backend module actually owns each endpoint.",
        })
    elif database_schema:
        faq.append({
            "question": "Where are the main data models defined?",
            "answer": f"The structured backend schema currently comes from {_format_path_list([str(path) for path in database_sources], max_paths=2) or 'the detected model files'}. Start there before changing API payloads or persistence behavior.",
        })

    gotchas: list[str] = list(setup_guidance.get("gotchas") or [])
    if len(runtime_commands) > 1:
        gotchas.append("Full local development usually requires more than one long-running process, so backend and frontend changes may not appear until both runtimes are up.")
    if quality_guidance.get("security_considerations"):
        public_route_note = next(
            (
                item for item in quality_guidance.get("security_considerations") or []
                if "auth" in str(item.get("area") or "").lower() or "route" in str(item.get("area") or "").lower()
            ),
            None,
        )
        if public_route_note:
            gotchas.append("Several mutating backend routes do not advertise explicit auth decorators, so do not assume the local API surface is hardened for untrusted exposure.")
    if quality_guidance.get("performance_notes"):
        scale_note = next(
            (
                item for item in quality_guidance.get("performance_notes") or []
                if "channel layer" in str(item.get("area") or "").lower() or "polling" in str(item.get("area") or "").lower()
            ),
            None,
        )
        if scale_note:
            gotchas.append("Realtime or terminal streaming behavior is tuned for local, single-process development first, so scale assumptions can break before the UI makes that obvious.")
    if testing_strategy and "no dedicated browser-level" in str(testing_strategy.get("e2e") or "").lower():
        gotchas.append("No dedicated browser-level or end-to-end suite was detected, so UI regressions may still rely on manual verification.")

    return {
        "key_concepts": _dedupe_json_items(concepts)[:6],
        "faq": _dedupe_json_items(faq)[:6],
        "gotchas": _filter_design_doc_strings(_dedupe_similar_strings(_dedupe_json_items(gotchas)[:8])[:5]),
    }


def _testing_strategy_lines_for_design_doc(project: Project, blueprint: dict, codebase_context: dict) -> list[str]:
    strategy = blueprint.get("testing_strategy")
    strategy = strategy if isinstance(strategy, dict) else {}
    derived = _derive_testing_strategy(project, codebase_context)
    merged = dict(derived)
    merged.update({key: value for key, value in strategy.items() if value})

    def cleaned(value) -> str:
        text = str(value or "").strip()
        if not text or _looks_like_design_doc_template(text):
            return ""
        return text

    lines: list[str] = []
    unit = cleaned(merged.get("unit"))
    integration = cleaned(merged.get("integration"))
    e2e = cleaned(merged.get("e2e"))
    run_command = cleaned(merged.get("run_command"))
    if unit:
        lines.append(f"- Unit: {unit}")
    if integration:
        lines.append(f"- Integration: {integration}")
    if e2e:
        lines.append(f"- E2E: {e2e}")
    if run_command:
        lines.append(f"- Run command: `{run_command}`")
    if not lines:
        lines.append("- No evidence-backed testing strategy was detected from the indexed repository yet.")
    return lines


def _derive_repo_guidance(project: Project, codebase_context: dict) -> dict:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return {
            "setup_steps": [],
            "environment_variables": [],
            "onboarding_checklist": [],
            "gotchas": [],
        }

    readme_text = _read_workspace_excerpt(workspace_path, "README.md", "readme.md")
    contributing_text = _read_workspace_excerpt(workspace_path, "CONTRIBUTING.md", "contributing.md")
    security_text = _read_workspace_excerpt(workspace_path, "SECURITY.md", "security.md", limit=6000)
    command_evidence = _extract_shell_commands("\n".join([readme_text, contributing_text, security_text]))
    top_areas = _top_repository_areas(codebase_context)
    env_template_paths = _env_template_paths(workspace_path, codebase_context)
    environment_variables = _derive_environment_variables(workspace_path, codebase_context)
    package_manifests = _workspace_package_manifests(workspace_path, codebase_context)
    python_roots = _workspace_python_roots(workspace_path, codebase_context)
    testing_strategy = _derive_testing_strategy(project, codebase_context)
    setup_steps: list[dict] = []

    if env_template_paths:
        copy_commands = []
        for rel_path in env_template_paths[:3]:
            rel_dir = _normalize_rel_dir(PurePosixPath(rel_path).parent.as_posix())
            file_name = PurePosixPath(rel_path).name
            copy_commands.append(_prefix_command_for_dir(rel_dir, f"cp {file_name} .env"))
        setup_steps.append({
            "kind": "config",
            "step": "Create local environment files",
            "command": "\n".join(_dedupe_json_items(copy_commands)),
            "explanation": "The repo declares environment templates that should be copied or mirrored into local `.env` files before you start the runtime.",
            "os_note": "If `cp` is unavailable in your shell, use the platform equivalent copy command instead.",
        })
    elif environment_variables:
        setup_steps.append({
            "kind": "config",
            "step": "Review runtime configuration inputs",
            "command": "",
            "explanation": "No checked-in env template was detected, but the codebase references environment-driven configuration that should be reviewed before first run.",
            "os_note": "Use the detected environment variables and config files to decide which local values need to be supplied.",
        })

    for root in python_roots[:4]:
        rel_dir = str(root.get("rel_dir") or "")
        area = f"`{rel_dir}/`" if rel_dir else "the project root"
        if root.get("requirements"):
            setup_steps.append({
                "kind": "install",
                "step": f"Install Python dependencies for {area}",
                "command": _prefix_command_for_dir(rel_dir, f"python -m pip install -r {PurePosixPath(str(root.get('requirements'))).name}"),
                "explanation": "This repository section has an explicit Python requirements file that defines its runtime dependencies.",
                "os_note": "",
            })
        elif root.get("pyproject"):
            setup_steps.append({
                "kind": "install",
                "step": f"Install Python package metadata for {area}",
                "command": _prefix_command_for_dir(rel_dir, "python -m pip install -e ."),
                "explanation": "The Python project metadata is managed through `pyproject.toml`, so an editable install keeps local code and the environment aligned.",
                "os_note": "",
            })
        if root.get("manage_py") and str(root.get("framework") or "").lower() == "django":
            setup_steps.append({
                "kind": "migrate",
                "step": f"Apply Django migrations for {area}",
                "command": _prefix_command_for_dir(rel_dir, "python manage.py migrate"),
                "explanation": "A Django `manage.py` entrypoint was detected here, so migrations are part of the normal local boot sequence.",
                "os_note": "",
            })

    root_workspace_manifest = next((item for item in package_manifests if not item.get("rel_dir") and item.get("workspaces")), None)
    for manifest in package_manifests[:6]:
        rel_dir = str(manifest.get("rel_dir") or "")
        if root_workspace_manifest and rel_dir and manifest.get("path") != root_workspace_manifest.get("path"):
            continue
        package_manager = str(manifest.get("package_manager") or "npm")
        install_command = {
            "pnpm": "pnpm install",
            "yarn": "yarn install",
            "bun": "bun install",
            "npm": "npm install",
        }.get(package_manager, "npm install")
        area = f"`{rel_dir}/`" if rel_dir else "the project root"
        setup_steps.append({
            "kind": "install",
            "step": f"Install Node dependencies for {area}",
            "command": _prefix_command_for_dir(rel_dir, install_command),
            "explanation": "A package manifest was detected for this repo surface, so install the declared dependencies before running scripts from it.",
            "os_note": "",
        })

    dev_steps: list[dict] = []
    for root in python_roots[:4]:
        rel_dir = str(root.get("rel_dir") or "")
        area = f"`{rel_dir}/`" if rel_dir else "the project root"
        if root.get("manage_py") and str(root.get("framework") or "").lower() == "django":
            dev_steps.append({
                "kind": "runtime",
                "step": f"Start the Django runtime for {area}",
                "command": _prefix_command_for_dir(rel_dir, "python manage.py runserver"),
                "explanation": "The detected Python entrypoint is a Django management command, so `runserver` is the local application runtime.",
                "os_note": "",
            })

    for manifest in package_manifests[:6]:
        scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
        package_manager = str(manifest.get("package_manager") or "npm")
        rel_dir = str(manifest.get("rel_dir") or "")
        area = f"`{rel_dir}/`" if rel_dir else "the project root"
        chosen_script = ""
        for key in ("dev", "start", "serve", "preview", "watch"):
            if scripts.get(key):
                chosen_script = key
                break
        if not chosen_script:
            for key in ("build", "compile"):
                if scripts.get(key):
                    chosen_script = key
                    break
        if chosen_script:
            dev_steps.append({
                "kind": "runtime",
                "step": f"Run the main package script for {area}",
                "command": _prefix_command_for_dir(rel_dir, _run_script_command(package_manager, chosen_script)),
                "explanation": "This command comes from the detected package manifest scripts and is the best evidence-backed entrypoint for that repo surface.",
                "os_note": "",
            })

    if not setup_steps and command_evidence:
        install_command = _pick_command(command_evidence, "install") or _pick_command(command_evidence, "setup")
        if install_command:
            setup_steps.append({
                "kind": "install",
                "step": "Install dependencies",
                "command": install_command,
                "explanation": "This command was extracted directly from the repository documentation or setup notes.",
                "os_note": "",
            })
    if not dev_steps and command_evidence:
        dev_command = _pick_command(command_evidence, "dev") or _pick_command(command_evidence, "start") or _pick_command(command_evidence, "run")
        if dev_command:
            dev_steps.append({
                "kind": "runtime",
                "step": "Start the local runtime",
                "command": dev_command,
                "explanation": "This command was extracted directly from the repository documentation or onboarding notes.",
                "os_note": "",
            })

    setup_steps.extend(dev_steps[:4])

    docs_to_read = []
    for filename in ("README.md", "CONTRIBUTING.md", "VISION.md", "AGENTS.md", "SECURITY.md"):
        if (workspace_path / filename).exists():
            docs_to_read.append(filename)
    for item in _public_instruction_files(codebase_context):
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if path and path not in docs_to_read:
            docs_to_read.append(path)

    onboarding_checklist: list[dict] = []
    if docs_to_read:
        onboarding_checklist.append({
            "task": "Read the root project docs first",
            "category": "codebase",
            "estimated_time": "15 min",
            "why_important": "Top-level docs and instruction files usually explain product context, contribution rules, and setup order faster than reading source files cold.",
            "instructions": f"Start with {', '.join(docs_to_read[:4])}.",
        })
    if top_areas:
        onboarding_checklist.append({
            "task": "Map the major repo areas",
            "category": "codebase",
            "estimated_time": "10 min",
            "why_important": "The indexed repository spans multiple top-level surfaces, so it helps to understand the boundaries before choosing where to edit.",
            "instructions": f"Begin with {', '.join(top_areas[:5])} and then open the repo map for file-level detail.",
        })
    if environment_variables or security_text:
        onboarding_checklist.append({
            "task": "Review environment and security defaults",
            "category": "environment",
            "estimated_time": "10 min",
            "why_important": "The repo declares environment-driven configuration and may include local-only security defaults that should be understood before first run.",
            "instructions": "Compare the detected env templates with SECURITY.md or settings files before enabling external integrations or remote access.",
        })
    if setup_steps:
        instructions_parts = [
            f"`{command}`"
            for command in (
                _setup_commands_by_kind(setup_steps, "install")[:2]
                + _setup_commands_by_kind(setup_steps, "migrate")[:1]
                + _setup_commands_by_kind(setup_steps, "runtime")[:2]
            )
            if command
        ]
        onboarding_checklist.append({
            "task": "Use the documented source workflow",
            "category": "tools",
            "estimated_time": "15 min",
            "why_important": "Following the detected setup sequence keeps local installs, migrations, and runtime entrypoints aligned with the repo's actual manifests and scripts.",
            "instructions": "Follow this order: " + " then ".join(instructions_parts) if instructions_parts else "Use the documented source workflow from the README.",
        })
    if testing_strategy:
        run_command = str(testing_strategy.get("run_command") or "").strip()
        onboarding_checklist.append({
            "task": "Learn the validation command early",
            "category": "processes",
            "estimated_time": "10 min",
            "why_important": "Knowing the test or validation entrypoint up front makes it easier to work in smaller safe changes.",
            "instructions": f"Use `{run_command}` before opening a PR." if run_command else str(testing_strategy.get("unit") or "Review the detected test layout before opening a PR."),
        })
    if contributing_text:
        onboarding_checklist.append({
            "task": "Follow the contributor rules before opening a PR",
            "category": "processes",
            "estimated_time": "10 min",
            "why_important": "The contribution guide usually captures repo-specific expectations around testing, review, and change scope.",
            "instructions": "Check CONTRIBUTING.md for the review and validation expectations before shipping changes.",
        })

    gotchas: list[str] = []
    if root_workspace_manifest:
        gotchas.append("The repository appears to use a workspace-aware package manager at the root, so running isolated installs inside child packages can leave the dependency graph out of sync.")
    if len(env_template_paths) > 1:
        gotchas.append(f"Configuration is split across multiple env templates: {_format_path_list(env_template_paths, max_paths=3)}.")
    if python_roots and package_manifests:
        gotchas.append("This repository mixes Python and Node-based surfaces, so setup and validation span more than one toolchain.")
    if len(dev_steps) > 1:
        gotchas.append("Local development appears to require multiple long-running commands or services, so one terminal session may not be enough for the full stack.")
    if "wsl2" in readme_text.lower():
        gotchas.append("The README references WSL2 for Windows setup, so native Windows commands may not exactly match the documented path.")

    return {
        "setup_steps": _dedupe_json_items(setup_steps)[:8],
        "environment_variables": _dedupe_json_items(environment_variables)[:30],
        "onboarding_checklist": _dedupe_json_items(onboarding_checklist)[:6],
        "gotchas": _filter_design_doc_strings(_dedupe_similar_strings(_dedupe_json_items(gotchas)[:8])[:6]),
    }


def _merge_by_key(llm_items, pipeline_items, key_fn, prefer='llm'):
    """Union two lists of dicts, deduplicating by key_fn.

    On same-key conflict: merge subfields so the secondary source only fills
    gaps in the preferred entry.
    """
    primary_items = llm_items if prefer == 'llm' else pipeline_items
    secondary_items = pipeline_items if prefer == 'llm' else llm_items
    by_key: dict[Any, dict] = {}

    for item in (primary_items or []):
        if not isinstance(item, dict):
            continue
        key = key_fn(item)
        if key:
            by_key[key] = dict(item)

    for item in (secondary_items or []):
        if not isinstance(item, dict):
            continue
        key = key_fn(item)
        if not key:
            continue
        if key not in by_key:
            by_key[key] = dict(item)
            continue
        existing = by_key[key]
        for sub_key, sub_val in item.items():
            if sub_key not in existing or not existing[sub_key]:
                existing[sub_key] = sub_val

    return list(by_key.values())


def _merge_repo_guidance_into_blueprint(project: Project, blueprint: dict, codebase_context: dict) -> dict:
    blueprint = dict(blueprint or {})
    setup_guidance = _derive_repo_guidance(project, codebase_context)
    quality_guidance = _derive_quality_guidance(project, codebase_context)
    knowledge_guidance = _derive_knowledge_guidance(project, codebase_context, setup_guidance, quality_guidance)

    blueprint['environment_variables'] = _merge_by_key(
        blueprint.get('environment_variables') or [],
        setup_guidance.get('environment_variables') or [],
        key_fn=lambda x: x.get('name', '').upper() if isinstance(x, dict) else '',
        prefer='llm',
    )

    blueprint['setup_steps'] = _merge_by_key(
        blueprint.get('setup_steps') or [],
        setup_guidance.get('setup_steps') or [],
        key_fn=lambda x: (x.get('kind', '') + ':' + x.get('command', '')[:60]).lower() if isinstance(x, dict) else '',
        prefer='llm',
    )

    for field in ("onboarding_checklist",):
        llm_val = blueprint.get(field)
        pipeline_val = setup_guidance.get(field)
        if llm_val:
            pass
        elif pipeline_val:
            blueprint[field] = pipeline_val

    for field in ("security_considerations", "performance_notes", "code_quality_standards"):
        llm_val = blueprint.get(field)
        pipeline_val = quality_guidance.get(field)
        if llm_val:
            pass
        elif pipeline_val:
            blueprint[field] = pipeline_val

    llm_testing = blueprint.get('testing_strategy')
    pipeline_testing = quality_guidance.get('testing_strategy')
    if isinstance(llm_testing, dict) and isinstance(pipeline_testing, dict):
        for sub_key in ('unit', 'integration', 'e2e', 'coverage_target', 'run_command'):
            if not llm_testing.get(sub_key) and pipeline_testing.get(sub_key):
                llm_testing[sub_key] = pipeline_testing[sub_key]
    elif not llm_testing and pipeline_testing:
        blueprint['testing_strategy'] = pipeline_testing

    for field in ("key_concepts", "faq", "gotchas"):
        llm_val = blueprint.get(field)
        pipeline_val = knowledge_guidance.get(field)
        if llm_val:
            pass
        elif pipeline_val:
            blueprint[field] = pipeline_val
    return blueprint


def _resolve_blueprint_path(workspace_path: Path | None, raw_path: str, expect_dir: bool = False) -> Path | None:
    if not workspace_path:
        return None

    raw = str(raw_path or "").strip()
    if raw in {".", "./", ".//"}:
        return workspace_path.resolve() if (workspace_path.is_dir() or expect_dir) else None
    if not raw:
        return None

    candidates: list[Path] = []
    path_obj = Path(raw)
    if path_obj.is_absolute():
        candidates.append(path_obj)

    normalized = raw.replace("\\", "/").strip()
    variants = [normalized]
    if normalized.startswith("./"):
        variants.append(normalized[2:])
    for variant in variants:
        if not variant:
            continue
        candidates.append(workspace_path / variant)
        if variant.startswith(f"{workspace_path.name}/"):
            candidates.append(workspace_path / variant[len(workspace_path.name) + 1 :])

    workspace_root = workspace_path.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(workspace_root)
        except Exception:
            continue
        if expect_dir and resolved.is_dir():
            return resolved
        if not expect_dir and resolved.exists():
            return resolved
    return None


def _is_valid_env_var_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]*", str(name or "").strip()))


def _placeholder_environment_variable(name: str) -> dict[str, Any]:
    category = _infer_env_category(name)
    description_prefix = {
        "frontend": "Frontend-facing environment variable referenced by the client bundle or browser runtime.",
        "ai": "AI or model-provider configuration referenced in the codebase.",
        "secret": "Credential or secret referenced in the codebase.",
        "database": "Database or persistence configuration referenced in the codebase.",
        "auth": "Authentication or trust-boundary setting referenced in the codebase.",
        "storage": "Storage or upload configuration referenced in the codebase.",
        "runtime": "Runtime or network setting referenced in the codebase.",
        "config": "Environment-driven configuration referenced in the codebase.",
    }.get(category, "Environment-driven configuration referenced in the codebase.")
    return {
        "name": name,
        "description": f"{description_prefix} Detailed usage was not fully resolved from the scanned evidence.",
        "required": False,
        "default": "No default detected",
        "example": "",
        "category": category,
    }


def _finalize_blueprint_environment_variables(workspace_path: Path | None, blueprint: dict, codebase_context: dict) -> list[dict]:
    llm_items: list[dict] = []
    for item in _blueprint_list(blueprint.get("environment_variables")):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().upper()
        if not _is_valid_env_var_name(name):
            continue
        cleaned = dict(item)
        cleaned["name"] = name
        cleaned["category"] = str(cleaned.get("category") or _infer_env_category(name))
        llm_items.append(cleaned)

    pipeline_items: list[dict] = []
    if workspace_path:
        for item in _derive_environment_variables(workspace_path, codebase_context):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip().upper()
            if not _is_valid_env_var_name(name):
                continue
            cleaned = dict(item)
            cleaned["name"] = name
            cleaned["category"] = str(cleaned.get("category") or _infer_env_category(name))
            pipeline_items.append(cleaned)

    merged = _merge_by_key(
        llm_items,
        pipeline_items,
        key_fn=lambda item: str(item.get("name") or "").strip().upper() if isinstance(item, dict) else "",
        prefer="llm",
    )

    seen = {
        str(item.get("name") or "").strip().upper()
        for item in merged
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }
    for raw_name in codebase_context.get("env_var_names") or []:
        name = str(raw_name or "").strip().upper()
        if not _is_valid_env_var_name(name) or name in seen:
            continue
        seen.add(name)
        merged.append(_placeholder_environment_variable(name))

    return _dedupe_json_items(merged)[:60]


def _setup_step_semantic_key(item: dict) -> str:
    command = re.sub(r"\s+", " ", str(item.get("command") or "").strip().lower())
    step = re.sub(r"\s+", " ", str(item.get("step") or "").strip().lower())
    kind = str(item.get("kind") or "").strip().lower()

    if "python -m venv" in command or "uv venv" in command:
        return "create-venv"
    if "activate" in command and ("venv" in command or ".venv" in command):
        return "activate-venv"
    if re.search(r"\b(python\s+-m\s+pip|pip|poetry|uv\s+pip)\s+install\b", command):
        return "python-install"
    if re.search(r"\b(npm|pnpm|yarn)\s+install\b", command):
        return "node-install"
    if "manage.py migrate" in command:
        return "django-migrate"
    if "manage.py runserver" in command:
        return "django-runserver"
    if re.search(r"\b(npm|pnpm|yarn)\s+(run\s+)?dev\b", command):
        return "node-dev"
    if re.search(r"\b(npm|pnpm|yarn)\s+(run\s+)?test\b", command) or "manage.py test" in command or "pytest" in command:
        return "validate"
    if kind and command:
        return f"{kind}:{command[:80]}"
    if command:
        return command[:80]
    if step:
        return f"step:{step[:80]}"
    return ""


def _setup_step_score(item: dict, readme_excerpt: str) -> int:
    score = 0
    command = re.sub(r"\s+", " ", str(item.get("command") or "").strip().lower())
    readme_lower = str(readme_excerpt or "").lower()

    if not str(item.get("kind") or "").strip():
        score += 3
    if command and command in readme_lower:
        score += 3
    if str(item.get("explanation") or "").strip():
        score += 1
    if str(item.get("step") or "").strip():
        score += 1
    if command == "python -m pip install -e ." and "python -m pip install -e ." not in readme_lower:
        score -= 3
    return score


def _normalize_setup_steps_for_blueprint(setup_steps: list[dict], readme_excerpt: str) -> list[dict]:
    winners: dict[str, tuple[int, dict]] = {}
    order: list[str] = []

    for raw_item in setup_steps or []:
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        if not str(item.get("command") or "").strip() and not str(item.get("step") or "").strip():
            continue
        key = _setup_step_semantic_key(item)
        if not key:
            continue
        score = _setup_step_score(item, readme_excerpt)
        existing = winners.get(key)
        if existing is None:
            winners[key] = (score, item)
            order.append(key)
            continue
        existing_score, existing_item = existing
        if score > existing_score:
            winners[key] = (score, item)
            continue
        if score == existing_score and len(json.dumps(item, sort_keys=True)) > len(json.dumps(existing_item, sort_keys=True)):
            winners[key] = (score, item)

    normalized: list[dict] = []
    seen_entries: set[tuple[str, str]] = set()
    for key in order:
        item = winners[key][1]
        dedupe_key = (
            re.sub(r"\s+", " ", str(item.get("command") or "").strip().lower()),
            re.sub(r"\s+", " ", str(item.get("step") or "").strip().lower()),
        )
        if dedupe_key in seen_entries:
            continue
        seen_entries.add(dedupe_key)
        normalized.append(item)
    return normalized[:12]


def _normalize_repository_map_entries(items: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        area = str(cleaned.get("area") or "").replace("\\", "/").strip()
        if area in {".", "./", ".//", "Project Root/", "Project Root"}:
            cleaned["area"] = "Project Root"
        elif area:
            cleaned["area"] = f"{area.rstrip('/')}/"
        normalized.append(cleaned)
    return normalized


def _finalize_blueprint_document(project: Project, blueprint: dict, codebase_context: dict) -> dict:
    finalized = dict(blueprint or {})
    workspace_path = _project_workspace_path(project)

    key_components: list[dict] = []
    for item in _blueprint_list(finalized.get("key_components")):
        if not isinstance(item, dict):
            continue
        if workspace_path and not _resolve_blueprint_path(workspace_path, str(item.get("file_path") or "")):
            continue
        key_components.append(item)
    finalized["key_components"] = key_components

    services: list[dict] = []
    for item in _blueprint_list(finalized.get("services")):
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        key_files: list[str] = []
        for raw_path in item.get("key_files") or []:
            if not isinstance(raw_path, str):
                continue
            for separator in (" - ", " – ", " — ", " : "):
                if separator in raw_path:
                    raw_path = raw_path.split(separator)[0].strip()
                    break
            path_part = raw_path.strip()
            basename = path_part.replace("\\", "/").split("/")[-1] if path_part else ""
            looks_like_path = bool(path_part) and ("/" in path_part or "\\" in path_part or "." in basename)
            if not looks_like_path:
                continue
            if workspace_path and not _resolve_blueprint_path(workspace_path, path_part):
                continue
            key_files.append(path_part.replace("\\", "/"))
        cleaned["key_files"] = key_files
        services.append(cleaned)
    finalized["services"] = services

    directory_guide: list[dict] = []
    for item in _blueprint_list(finalized.get("directory_guide")):
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        raw_path = str(cleaned.get("path") or "").replace("\\", "/").strip()
        if raw_path in {".", "./", ".//", ""}:
            normalized_path = "./"
        else:
            normalized_path = f"{raw_path.rstrip('/')}/"
        if workspace_path and not _resolve_blueprint_path(workspace_path, normalized_path, expect_dir=True):
            continue
        cleaned["path"] = normalized_path
        directory_guide.append(cleaned)
    finalized["directory_guide"] = directory_guide

    finalized["repository_map"] = _normalize_repository_map_entries(_blueprint_list(finalized.get("repository_map")))
    finalized["environment_variables"] = _finalize_blueprint_environment_variables(workspace_path, finalized, codebase_context)
    finalized["setup_steps"] = _normalize_setup_steps_for_blueprint(
        _blueprint_list(finalized.get("setup_steps")),
        str(finalized.get("readme_excerpt") or codebase_context.get("readme_excerpt") or ""),
    )

    api_endpoints: list[dict] = []
    seen_endpoints: set[tuple[str, str]] = set()
    for item in _blueprint_list(finalized.get("api_endpoints")):
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        params = cleaned.get("path_params")
        if isinstance(params, list):
            seen_params: set[str] = set()
            deduped_params: list[Any] = []
            for param in params:
                if isinstance(param, dict):
                    param_key = str(param.get("name") or "").strip().lower()
                else:
                    param_key = str(param or "").strip().lower()
                if not param_key or param_key in seen_params:
                    continue
                seen_params.add(param_key)
                deduped_params.append(param)
            cleaned["path_params"] = deduped_params
        path = str(cleaned.get("path") or "").strip()
        norm_path = path.rstrip("/") if len(path) > 1 else path
        endpoint_key = (str(cleaned.get("method") or "GET").upper(), norm_path)
        if endpoint_key in seen_endpoints:
            continue
        seen_endpoints.add(endpoint_key)
        api_endpoints.append(cleaned)
    finalized["api_endpoints"] = api_endpoints

    repo_tree = str(finalized.get("repo_tree") or "")
    if repo_tree:
        finalized["repo_tree"] = repo_tree.replace("project root/", "./").replace(".//", "./")

    return finalized


def _first_sentence(text: str, fallback: str = "") -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized:
        return fallback
    parts = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)
    return (parts[0] or normalized).strip()


def _confirmed_overview_doc_paths(blueprint: dict, codebase_context: dict, limit: int = 8) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        normalized = str(path or "").replace("\\", "/").strip()
        if not normalized or normalized in seen or _is_devhub_internal_path(normalized):
            return
        seen.add(normalized)
        paths.append(normalized)

    if str(blueprint.get('readme_excerpt') or '').strip():
        add('README.md')
    for item in _blueprint_list(blueprint.get('instruction_files')):
        if isinstance(item, dict):
            add(str(item.get('path') or ''))
    for item in _blueprint_list(codebase_context.get('manifest')):
        path = str(item.get('path') or '').replace("\\", "/").strip()
        lower = path.lower()
        if not path:
            continue
        if lower.startswith('docs/') or '/docs/' in lower:
            add(path)
            continue
        if lower in {'readme.md', 'contributing.md', 'security.md', 'vision.md', 'agents.md'}:
            add(path)
    return paths[:limit]


def _is_speculative_risk_text(text: str) -> bool:
    lowered = str(text or '').strip().lower()
    if not lowered:
        return True
    return any(token in lowered for token in ('not confirmed', 'might ', 'may ', 'could ', 'appears ', 'seems '))


def _design_doc_problem_statement(project: Project, blueprint: dict) -> list[str]:
    # Use the full project_summary (not just first sentence) for the opening description
    full_summary = str(blueprint.get('project_summary') or '').strip()
    description = str(project.description or '').strip()

    # Prefer project description if it reads as a product description (not a workflow step)
    # Heuristic: workflow text starts with verbs like "When", "After", "First", "Click"
    workflow_starters = ('when ', 'after ', 'first ', 'click', 'submit', 'upload', 'navigate', 'go to', 'step')
    desc_is_workflow = any(description.lower().startswith(s) for s in workflow_starters)

    if description and not desc_is_workflow:
        opening = description
        if full_summary and full_summary.lower() not in description.lower() and len(full_summary) > 40:
            opening = f"{description}\n\n{full_summary}"
    else:
        opening = full_summary or 'The blueprint does not yet contain a grounded product problem statement.'

    services = [item for item in _blueprint_list(blueprint.get('services')) if isinstance(item, dict)]
    endpoints = [item for item in _blueprint_list(blueprint.get('api_endpoints')) if isinstance(item, dict)]
    schema = [item for item in _blueprint_list(blueprint.get('database_schema')) if isinstance(item, dict)]

    bullets: list[str] = []
    service_names = [str(item.get('name') or '').strip() for item in services if str(item.get('name') or '').strip()]
    if service_names:
        bullets.append(f"Implemented as: {', '.join(service_names[:4])}.")
    if endpoints:
        auth_count = sum(1 for ep in endpoints if ep.get('auth_required'))
        bullets.append(f"Backend exposes {len(endpoints)} API endpoints, {auth_count} of which require authentication.")
    if schema:
        model_names = [str(item.get('name') or '').strip() for item in schema[:6] if str(item.get('name') or '').strip()]
        if model_names:
            bullets.append(f"Core data models include: {', '.join(model_names)}.")
    return [opening, '', *(_markdown_bullets(bullets, 'No grounded problem signals were extracted beyond the repository structure.'))]


def _design_doc_goal_lines(blueprint: dict) -> tuple[list[str], list[str]]:
    goals: list[str] = []
    non_goals: list[str] = []

    # Goals derived from the architecture overview and services
    arch = str(blueprint.get('architecture_overview') or '').strip()
    if arch:
        # Use up to two sentences from the architecture overview as the first goal
        arch_sentences = [s.strip() for s in arch.replace('\n', ' ').split('.') if len(s.strip()) > 20]
        if arch_sentences:
            goals.append(arch_sentences[0] + '.')

    services = [item for item in _blueprint_list(blueprint.get('services')) if isinstance(item, dict)]
    for svc in services[:4]:
        name = str(svc.get('name') or '').strip()
        svc_type = str(svc.get('type') or '').strip()
        desc_first = _first_sentence(svc.get('description'))
        if name and desc_first:
            goals.append(f"{name} ({svc_type}): {desc_first}")

    endpoints = [item for item in _blueprint_list(blueprint.get('api_endpoints')) if isinstance(item, dict)]
    if endpoints:
        non_goals.append(
            f"Complete response schema and status-code contracts are not yet authoritative for all {len(endpoints)} endpoints — "
            "callers should verify against live responses until endpoint docs are fully annotated."
        )

    testing = blueprint.get('testing_strategy') if isinstance(blueprint.get('testing_strategy'), dict) else {}
    run_command = str(testing.get('run_command') or '').strip()
    if run_command:
        goals.append(f"Local validation: `{run_command}`.")

    non_goals.append('Features or endpoints with no repository evidence are out of scope for this design document.')
    return goals[:6], non_goals[:3]


def _api_design_summary_lines(endpoints: list[dict], routes: list[Any]) -> list[str]:
    if not endpoints:
        return _markdown_bullets(routes, 'No routes or endpoints were clearly detected.')

    grouped: dict[str, dict[str, Any]] = {}
    for item in endpoints:
        if not isinstance(item, dict):
            continue
        path = str(item.get('path') or '/').strip() or '/'
        method = str(item.get('method') or 'GET').upper()
        segments = [seg for seg in path.strip('/').split('/') if seg and not seg.startswith('<') and not seg.startswith('{')]
        if segments and segments[0] == 'api':
            segments = segments[1:]
        if segments:
            prefix = '/' + '/'.join(segments[:2])
        else:
            prefix = '/api' if path.startswith('/api') else '/'
        bucket = grouped.setdefault(prefix, {'count': 0, 'methods': set(), 'auth': 0})
        bucket['count'] += 1
        bucket['methods'].add(method)
        if item.get('auth_required'):
            bucket['auth'] += 1

    lines = [f"Detected {len(endpoints)} routed endpoints across the indexed backend.", '']
    bullets = []
    for prefix, bucket in sorted(grouped.items(), key=lambda entry: (-int(entry[1]['count']), entry[0]))[:10]:
        methods = ', '.join(sorted(bucket['methods']))
        auth_note = 'mostly authenticated' if bucket['auth'] >= max(1, bucket['count'] // 2) else 'mixed auth visibility'
        bullets.append(f"`{prefix}/*`: {bucket['count']} endpoints across {methods}; {auth_note}.")
    lines.extend(_markdown_bullets(bullets, 'No API groupings were available.'))
    return lines


def _render_blueprint_design_document(project: Project, blueprint: dict, codebase_context: dict, feature_summary: str) -> tuple[str, list[dict]]:
    generated_on = timezone.now().strftime('%Y-%m-%d')
    title = project.name or 'Project'
    services = _blueprint_list(blueprint.get('services'))
    endpoints = _blueprint_list(blueprint.get('api_endpoints'))
    schema = _blueprint_list(blueprint.get('database_schema'))
    key_components = _blueprint_list(blueprint.get('key_components'))
    directories = _blueprint_list(blueprint.get('directory_guide'))
    workflows = _blueprint_list(blueprint.get('common_workflows'))
    setup_steps = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('setup_steps')), ('step', 'command', 'explanation', 'os_note'))
    env_vars = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('environment_variables')), ('name', 'description', 'default', 'example', 'category'))
    security = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('security_considerations')), ('area', 'description', 'severity'))
    performance = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('performance_notes')), ('area', 'description', 'impact'))
    integrations = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('integration_points')), ('name', 'type', 'description', 'evidence'))
    onboarding = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('onboarding_checklist')), ('task', 'instructions', 'why_important', 'category'))
    concepts = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('key_concepts')), ('concept', 'explanation', 'why_important', 'why_it_matters'))
    gotchas = _filter_design_doc_strings(_blueprint_list(blueprint.get('gotchas')))
    feature_inventory = _blueprint_list(blueprint.get('feature_inventory'))
    tech_stack_details = _blueprint_list(blueprint.get('tech_stack_details'))
    change_guide = _blueprint_list(blueprint.get('change_guide'))
    sequence_flows = _blueprint_list(blueprint.get('sequence_flows'))
    pipeline = blueprint.get('sdlc_pipeline') or {}
    routes = _blueprint_list(codebase_context.get('routes'))
    data_models = _blueprint_list(codebase_context.get('data_models'))
    testing_strategy_lines = _testing_strategy_lines_for_design_doc(project, blueprint, codebase_context)

    sections = []

    sections.append({
        'id': 'executive-summary',
        'title': 'Executive Summary',
        'body': [
            _blueprint_text(blueprint.get('project_summary'), project.description or 'No project summary has been generated yet.'),
            '',
            _blueprint_text(blueprint.get('architecture_overview')),
        ],
    })

    sections.append({
        'id': 'problem-statement',
        'title': 'Problem Statement',
        'body': _design_doc_problem_statement(project, blueprint),
    })

    goal_lines, non_goal_lines = _design_doc_goal_lines(blueprint)
    sections.append({
        'id': 'goals-non-goals',
        'title': 'Goals & Non-Goals',
        'body': [
            'Goals inferred from the current repository evidence:',
            *_markdown_bullets(goal_lines, 'No explicit goals were captured in the blueprint yet.'),
            '',
            'Non-goals and boundaries:',
            *_markdown_bullets(non_goal_lines, 'Non-goals were not clearly documented.'),
        ],
    })

    architecture_body = [
        _blueprint_text(blueprint.get('architecture_overview')),
        '',
        'Repository shape:',
        *_markdown_bullets(
            [f"{item.get('area')}: {item.get('description')}" for item in _blueprint_list(blueprint.get('repository_map')) if isinstance(item, dict)],
            'Repository area mapping is not available.',
        ),
    ]
    if blueprint.get('mermaid_architecture'):
        architecture_body.extend(['', '```mermaid', blueprint.get('mermaid_architecture', ''), '```'])
    sections.append({
        'id': 'system-architecture-overview',
        'title': 'System Architecture Overview',
        'body': architecture_body,
    })

    sections.append({
        'id': 'technology-stack',
        'title': 'Technology Stack',
        'body': [
            *(
                [
                    f"- `{item.get('tech', 'Unknown')}`: {item.get('purpose') or item.get('why_chosen') or 'No purpose documented.'}"
                    for item in tech_stack_details if isinstance(item, dict)
                ] or _markdown_bullets(project.tech_stack or [], 'No technology stack details were captured.')
            )
        ],
    })

    sections.append({
        'id': 'component-design',
        'title': 'Component Design',
        'body': [
            'Services and major modules:',
            *_markdown_bullets(
                [
                    f"{item.get('name', 'Unnamed service')} ({item.get('type', 'unknown')}): {item.get('description') or 'No description available.'}"
                    for item in services if isinstance(item, dict)
                ],
                'No service-level component design was detected.',
            ),
            '',
            'Key files and components:',
            *_markdown_bullets(
                [
                    f"{item.get('file_path', 'unknown file')}: {item.get('purpose') or item.get('summary') or 'No purpose available.'}"
                    for item in key_components if isinstance(item, dict)
                ],
                'No key components were identified.',
            ),
        ],
    })

    data_body = []
    if schema:
        data_body.extend(
            _markdown_bullets(
                [
                    f"{item.get('table', 'Unnamed entity')}: {item.get('description') or item.get('relationships') or 'No entity detail available.'}"
                    for item in schema if isinstance(item, dict)
                ],
                'No schema entities were documented.',
            )
        )
    else:
        data_body.extend(_markdown_bullets(data_models, 'No models or typed entities were clearly detected.'))
    sections.append({
        'id': 'data-model',
        'title': 'Data Model',
        'body': data_body,
    })

    api_body = []
    if endpoints:
        api_body.extend(_api_design_summary_lines(endpoints, routes))
    else:
        api_body.extend(_markdown_bullets(routes, 'No routes or endpoints were clearly detected.'))
    sections.append({
        'id': 'api-design',
        'title': 'API Design',
        'body': api_body,
    })

    workflow_body = [
        'Common workflows:',
        *_markdown_bullets(
            [
                f"{item.get('title', 'Workflow')}: {', '.join(_blueprint_list(item.get('steps'))[:5])}"
                for item in workflows if isinstance(item, dict)
            ],
            'No common workflows were documented.',
        ),
        '',
        'Pipeline and execution flow:',
        *_markdown_bullets(
            [stage.get('name') for stage in _blueprint_list(pipeline.get('stages')) if isinstance(stage, dict)],
            'No explicit SDLC stages were documented.',
        ),
    ]
    if blueprint.get('mermaid_service_dependencies'):
        workflow_body.extend(['', '```mermaid', blueprint.get('mermaid_service_dependencies', ''), '```'])
    sections.append({
        'id': 'workflow-design',
        'title': 'Workflow Design',
        'body': workflow_body,
    })

    sections.append({
        'id': 'frontend-repository-architecture',
        'title': 'Frontend / Repository Architecture',
        'body': [
            'Directory guide:',
            *_markdown_bullets(
                [
                    f"{item.get('path', './')}: {item.get('purpose') or 'No purpose summary available.'}"
                    for item in directories if isinstance(item, dict)
                ],
                'No directory guide is available yet.',
            ),
            '',
            'Repository tree:',
            '```text',
            str(blueprint.get('repo_tree') or 'No repository tree available.'),
            '```',
        ],
    })

    sections.append({
        'id': 'ai-integration-design',
        'title': 'AI / Integration Design',
        'body': [
            *_markdown_bullets(
                [
                    f"{item.get('name', 'Integration')}: {item.get('description') or 'No description available.'}"
                    for item in integrations if isinstance(item, dict)
                ],
                'No AI or external integration points were clearly documented.',
            )
        ],
    })

    sections.append({
        'id': 'setup-operations',
        'title': 'Setup & Operations',
        'body': [
            'Setup steps:',
            *_markdown_bullets(
                [
                    f"{item.get('step', 'Setup step')}: {item.get('command') or item.get('explanation') or 'No command documented.'}"
                    for item in setup_steps if isinstance(item, dict)
                ],
                'No setup steps were documented.',
            ),
            '',
            'Environment variables:',
            *_markdown_bullets(
                [
                    f"{item.get('name', 'VAR_NAME')}: {item.get('description') or 'No description available.'}"
                    for item in env_vars if isinstance(item, dict)
                ],
                'No environment variables were documented.',
            ),
            '',
            'Testing strategy:',
            *testing_strategy_lines,
        ],
    })

    sections.append({
        'id': 'security-performance',
        'title': 'Security & Performance',
        'body': [
            'Security considerations:',
            *_markdown_bullets(
                [
                    f"{item.get('area', 'Security area')}: {item.get('description') or 'No detail available.'}"
                    for item in security if isinstance(item, dict)
                ],
                'No explicit security considerations were documented.',
            ),
            '',
            'Performance notes:',
            *_markdown_bullets(
                [
                    f"{item.get('area', 'Performance area')}: {item.get('description') or 'No detail available.'}"
                    for item in performance if isinstance(item, dict)
                ],
                'No explicit performance notes were documented.',
            ),
        ],
    })

    sections.append({
        'id': 'onboarding-knowledge',
        'title': 'Onboarding & Knowledge',
        'body': [
            'Onboarding checklist:',
            *_markdown_bullets(
                [
                    f"{item.get('task', 'Task')}: {item.get('instructions') or item.get('why_important') or 'No instructions available.'}"
                    for item in onboarding if isinstance(item, dict)
                ],
                'No onboarding checklist was documented.',
            ),
            '',
            'Key concepts:',
            *_markdown_bullets(
                [
                    f"{item.get('concept', 'Concept')}: {item.get('explanation') or 'No explanation available.'}"
                    for item in concepts if isinstance(item, dict)
                ],
                'No key concepts were documented.',
            ),
        ],
    })

    sections.append({
        'id': 'known-limitations-future-work',
        'title': 'Known Limitations & Future Work',
        'body': [
            'Known gotchas and sharp edges:',
            *_markdown_bullets(gotchas, 'No gotchas were documented.'),
            '',
            'Backlog and future-facing work:',
            *_markdown_bullets(
                [
                    f"{item.get('title', 'Work item')} [{item.get('status', 'unknown')}]"
                    for item in feature_inventory if isinstance(item, dict) and item.get('status') in {'backlog', 'development', 'testing', 'code_review'}
                ],
                feature_summary[:200] or 'No future work items were captured.',
            ),
        ],
    })

    toc_lines = []
    for index, section in enumerate(sections, start=1):
        toc_lines.append(f"{index}. [{section['title']}](#{_slugify_heading(section['title'])})")

    lines = [
        f"# {title} - Blueprint Design Document",
        '',
        '**Version:** 1.0',
        f'**Date:** {generated_on}',
        '**Source:** DevHub Blueprint',
        '',
        '---',
        '',
        '## Table of Contents',
        '',
        *toc_lines,
        '',
        '---',
        '',
    ]

    for index, section in enumerate(sections, start=1):
        lines.append(f"## {index}. {section['title']}")
        lines.append('')
        lines.extend(section['body'])
        lines.append('')
        lines.append('---')
        lines.append('')

    return '\n'.join(lines).strip(), sections


def _enrich_blueprint_document(project: Project, blueprint: dict, codebase_context: dict, feature_summary: str) -> dict:
    blueprint = dict(blueprint or {})
    workspace_path = Path(project.local_path) if project.local_path else None
    indexed_endpoints = _blueprint_list(codebase_context.get('api_reference'))
    existing_endpoints = blueprint.get('api_endpoints') or []
    # Prefer indexed (AST-extracted) data when it has >= entries — ground truth over stale LLM output.
    if indexed_endpoints and len(indexed_endpoints) >= len(existing_endpoints):
        blueprint['api_endpoints'] = indexed_endpoints
    elif existing_endpoints:
        blueprint['api_endpoints'] = existing_endpoints
    elif indexed_endpoints:
        blueprint['api_endpoints'] = indexed_endpoints
    indexed_schema = _blueprint_list(codebase_context.get('database_schema'))
    if indexed_schema and len(indexed_schema) >= len(blueprint.get('database_schema') or []):
        blueprint['database_schema'] = indexed_schema
    indexed_erd = str(codebase_context.get('database_mermaid_erd') or '')
    if indexed_erd and len(indexed_erd) > len(blueprint.get('mermaid_erd') or ''):
        blueprint['mermaid_erd'] = indexed_erd
    evidence_sequence_flows, evidence_common_workflows = _build_evidence_backed_workflows(workspace_path)
    if evidence_sequence_flows:
        blueprint['sequence_flows'] = evidence_sequence_flows
    if evidence_common_workflows:
        blueprint['common_workflows'] = evidence_common_workflows
    blueprint['mermaid_architecture'] = _normalize_mermaid_chart(blueprint.get('mermaid_architecture', ''), 'graph')
    blueprint['mermaid_service_dependencies'] = _normalize_mermaid_chart(blueprint.get('mermaid_service_dependencies', ''), 'graph')
    blueprint['mermaid_erd'] = _normalize_mermaid_chart(blueprint.get('mermaid_erd', ''), 'erd')

    sequence_flows = []
    for flow in (blueprint.get('sequence_flows') or []):
        if isinstance(flow, dict):
            normalized = dict(flow)
            normalized['mermaid_sequence'] = _normalize_mermaid_chart(normalized.get('mermaid_sequence', ''), 'sequence')
            sequence_flows.append(normalized)
    blueprint['sequence_flows'] = sequence_flows

    # Structural sections must come from the indexed repository cache, not model guesses.
    blueprint['directory_guide'] = _build_directory_guide_from_context(codebase_context)
    blueprint['repository_map'] = _build_repository_map_from_context(codebase_context)
    blueprint['repo_tree'] = str(codebase_context.get('repo_tree') or '')
    blueprint['repo_tree_nodes'] = _blueprint_list(codebase_context.get('repo_tree_nodes'))
    blueprint['readme_excerpt'] = str(codebase_context.get('readme_excerpt') or '')
    blueprint['instruction_files'] = _blueprint_list(_public_instruction_files(codebase_context))
    blueprint['file_structure_visualizer'] = _build_file_structure_visualizer(codebase_context)
    blueprint['change_guide'] = _build_change_guide(codebase_context)
    live_features = _project_features_payload(project)
    blueprint['feature_inventory'] = _live_feature_inventory(project) or [{
        'title': 'Current project work',
        'status': 'unknown',
        'description': feature_summary[:1200] or 'No feature inventory available yet.',
        'implementation_notes': 'Use Work Items to create and track project scope.',
    }]
    blueprint['sdlc_pipeline'] = _live_pipeline_document(project, live_features)
    blueprint = _merge_repo_guidance_into_blueprint(project, blueprint, codebase_context)
    blueprint = _finalize_blueprint_document(project, blueprint, codebase_context)
    blueprint.update(_build_blueprint_overview_insights(project, blueprint, codebase_context, live_features))
    design_document_markdown, design_document_sections = _render_blueprint_design_document(project, blueprint, codebase_context, feature_summary)
    blueprint['design_document_markdown'] = design_document_markdown
    blueprint['design_document_sections'] = [
        {
            'id': section.get('id'),
            'title': section.get('title'),
            'markdown': '\n'.join(section.get('body') or []).strip(),
        }
        for section in design_document_sections
    ]
    return blueprint


def _fallback_plan(selected_file: str, file_inventory: str, request_text: str) -> dict:
    inventory_lines = [line.strip() for line in file_inventory.splitlines() if line.strip()]
    relevant = []
    if selected_file:
        relevant.append(selected_file)
    priority_matches = []
    for candidate in inventory_lines:
        lower = candidate.lower()
        if any(token in lower for token in ('app', 'index', 'main', 'style', 'component', 'view', 'page', 'url', 'route')):
            priority_matches.append(candidate)
        if len(priority_matches) >= 7:
            break
    for item in priority_matches:
        if item not in relevant:
            relevant.append(item)
    return {
        "objective": request_text,
        "relevant_files": relevant[:8],
        "new_files": [],
        "implementation_steps": [
            "Inspect the existing implementation.",
            "Update the minimum set of files needed for a consistent change.",
            "Keep related UI, logic, and docs aligned.",
        ],
        "consistency_requirements": [
            "Reuse the current project structure.",
            "Reflect the request in all directly related files.",
        ],
        "risks": [
            "Changing the wrong scaffold files can make the app unrunnable.",
        ],
        "validation_commands": [],
        "acceptance_checks": [
            "The requested behavior is implemented in the current project structure.",
        ],
        "memory_updates": [],
    }


def _create_implementation_plan(
    project: Project,
    request_title: str,
    request_text: str,
    workspace_path: Path,
    project_memory: str,
    memory_context_text: str = "",
    selected_file: str = "",
    customization_bundle: dict | None = None,
    request_attachments: list[dict] | None = None,
) -> dict:
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        logger.exception("Failed to load cached codebase context for planning in project %s", project.id)
    codebase_summary = (codebase_context or {}).get('compact_summary') or 'No cached codebase summary available.'
    file_inventory = _workspace_file_inventory(workspace_path, limit=160)
    blueprint_summary = json.dumps(project.blueprint or {}, indent=2)[:3500] if project.blueprint else "No blueprint available."
    supporting_context = f"""Recent Features:
{_render_project_features_summary(project)}

Recent Changes:
{_render_recent_changes_summary(project)}

Recent Chat:
{_recent_chat_history(project)}

Memory Recall:
{memory_context_text or 'No additional memory recall available.'}

Cached Codebase Context:
{codebase_summary[:5000]}
"""
    customization_context = build_role_prompt_context(customization_bundle, "planner")
    if customization_context:
        supporting_context = f"{supporting_context}\n\nProject Customization:\n{customization_context[:8000]}"

    if not ai_config_is_usable(_project_ai_config(project)):
        return _fallback_plan(selected_file, file_inventory, request_text)

    try:
        from agents.planner import PlannerAgent

        planner = PlannerAgent(
            ai_config=_project_ai_config(project),
            customization_instruction=build_role_customization_addendum(customization_bundle, "planner"),
        )
        plan = planner.create_plan(
            project_name=project.name,
            request_title=request_title,
            request_text=request_text,
            project_memory=project_memory[:12000],
            codebase_summary=codebase_summary[:9000],
            file_inventory=file_inventory[:5000],
            blueprint_summary=blueprint_summary,
            supporting_context=supporting_context[:8000],
            customization_context=customization_context[:8000],
            request_attachments=request_attachments,
        )
        if not isinstance(plan, dict):
            return _fallback_plan(selected_file, file_inventory, request_text)
        return plan
    except Exception:
        logger.exception("Implementation planner failed for project %s", project.id)
        return _fallback_plan(selected_file, file_inventory, request_text)


def _collect_relevant_files(
    workspace_path: Path,
    plan: dict,
    request_text: str = "",
    codebase_context: dict | None = None,
    selected_file: str = "",
    selected_content: str = "",
    limit: int = 20,
) -> list[dict]:
    context = []
    seen = set()
    codebase_context = codebase_context or {}

    def add_file(rel_path: str, content_override: str | None = None):
        normalized = rel_path.replace('\\', '/')
        if normalized in seen or len(context) >= limit:
            return
        candidate = workspace_path / normalized
        if not candidate.exists() or not candidate.is_file():
            return
        try:
            content = content_override if content_override is not None else candidate.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return
        seen.add(normalized)
        context.append({"path": normalized, "content": content})

    if selected_file:
        add_file(selected_file, selected_content or None)

    for rel_path in plan.get('relevant_files', [])[:limit]:
        if isinstance(rel_path, str):
            add_file(rel_path)

    for item in (codebase_context.get('instruction_files') or [])[:4]:
        if isinstance(item, dict) and item.get('path'):
            add_file(str(item['path']), str(item.get('content') or '') or None)

    for item in (codebase_context.get('important_files') or [])[:10]:
        rel_path = item.get('path')
        if isinstance(rel_path, str):
            add_file(rel_path)

    search_terms = _tokenize_search_terms(
        request_text,
        plan.get('objective', ''),
        ' '.join(plan.get('acceptance_checks', []) or []),
        ' '.join(plan.get('implementation_steps', []) or []),
    )
    for rel_path in _search_workspace_paths(workspace_path, search_terms, limit=10):
        add_file(rel_path)
    for rel_path in _search_workspace_content(workspace_path, search_terms, limit=10):
        add_file(rel_path)

    # Fill remaining slots with priority files and a broader sample if the plan is sparse.
    for rel_path in [
        "package.json", "vite.config.js", "vite.config.ts", "index.html",
        "main.py", "app.py", "requirements.txt", "manage.py", "README.md",
    ]:
        add_file(rel_path)

    if len(context) < limit:
        for item in _collect_workspace_context(workspace_path, selected_file=selected_file, selected_content=selected_content, limit=limit):
            if len(context) >= limit:
                break
            if item['path'] not in seen:
                seen.add(item['path'])
                context.append(item)

    return context


def _build_supporting_context(project: Project, plan: dict, workspace_path: Path, customization_bundle: dict | None = None) -> str:
    runtime = detect_runtime(workspace_path)
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        logger.exception("Failed to load codebase context for supporting context in project %s", project.id)
    instruction_context = codebase_context.get('instruction_files') or []
    customization_context = build_role_prompt_context(customization_bundle, "coder")
    return f"""Runtime:
{json.dumps(runtime, indent=2)}

Recent Features:
{_render_project_features_summary(project)}

Recent Changes:
{_render_recent_changes_summary(project)}

Recent Chat:
{_recent_chat_history(project)}

Plan Acceptance Checks:
{json.dumps(plan.get('acceptance_checks', []), indent=2)}

Project Instructions:
{json.dumps(instruction_context, indent=2)[:2500] if instruction_context else 'No DEVHUB.md / AGENTS.md style instruction file detected.'}

Project Customization:
{customization_context[:8000] if customization_context else 'No additional implementation customization detected.'}
"""


def _tokenize_search_terms(*values: str, limit: int = 12) -> list[str]:
    tokens = []
    seen = set()
    for value in values:
        for token in re.findall(r'[A-Za-z0-9_./-]+', str(value or '').lower()):
            normalized = token.strip('./-')
            if len(normalized) < 3:
                continue
            if normalized in {'the', 'and', 'with', 'from', 'this', 'that', 'feature', 'project', 'update'}:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            tokens.append(normalized)
            if len(tokens) >= limit:
                return tokens
    return tokens


def _search_workspace_paths(workspace_path: Path, terms: list[str], limit: int = 24) -> list[str]:
    if not terms:
        return []

    results = []
    seen = set()

    try:
        completed = subprocess.run(
            ['rg', '--files', str(workspace_path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode == 0:
            for rel_path in completed.stdout.splitlines():
                normalized = str(rel_path).replace('\\', '/')
                lower = normalized.lower()
                if normalized.startswith(f"{DEVHUB_META_DIR}/"):
                    continue
                if any(term in lower for term in terms):
                    if normalized not in seen:
                        seen.add(normalized)
                        results.append(normalized)
                        if len(results) >= limit:
                            return results
    except Exception:
        pass

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for filename in sorted(files):
            rel_path = str((Path(root) / filename).relative_to(workspace_path)).replace('\\', '/')
            lower = rel_path.lower()
            if rel_path.startswith(f"{DEVHUB_META_DIR}/"):
                continue
            if any(term in lower for term in terms):
                if rel_path not in seen:
                    seen.add(rel_path)
                    results.append(rel_path)
                    if len(results) >= limit:
                        return results
    return results


def _search_workspace_content(workspace_path: Path, terms: list[str], limit: int = 16) -> list[str]:
    if not terms:
        return []

    results = []
    seen = set()
    source_exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".md"}

    for term in terms[:6]:
        try:
            completed = subprocess.run(
                ['rg', '--files-with-matches', '--glob', '!*.min.*', term, str(workspace_path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if completed.returncode in (0, 1):
                for rel_path in completed.stdout.splitlines():
                    normalized = str(rel_path).replace('\\', '/')
                    if normalized.startswith(f"{DEVHUB_META_DIR}/") or normalized in seen:
                        continue
                    seen.add(normalized)
                    results.append(normalized)
                    if len(results) >= limit:
                        return results
        except Exception:
            break

    if results:
        return results

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for filename in sorted(files):
            path = Path(root) / filename
            rel_path = str(path.relative_to(workspace_path)).replace('\\', '/')
            if rel_path.startswith(f"{DEVHUB_META_DIR}/") or path.suffix.lower() not in source_exts:
                continue
            try:
                content = path.read_text(encoding='utf-8', errors='ignore').lower()
            except Exception:
                continue
            if any(term in content for term in terms):
                if rel_path not in seen:
                    seen.add(rel_path)
                    results.append(rel_path)
                    if len(results) >= limit:
                        return results
    return results


def _package_scripts(project_root: Path) -> dict:
    package_json_path = project_root / "package.json"
    if not package_json_path.exists():
        return {}
    try:
        package_json = json.loads(package_json_path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return package_json.get('scripts', {}) or {}


def _validation_commands(workspace_path: Path) -> list[str]:
    runtime = detect_runtime(workspace_path)
    commands: list[str] = []

    if runtime.get('runtime_type') == 'node':
        scripts = _package_scripts(workspace_path)
        if scripts.get('lint'):
            commands.append('npm run lint')
        if scripts.get('typecheck'):
            commands.append('npm run typecheck')
        elif scripts.get('build'):
            commands.append('npm run build')
        if scripts.get('test'):
            commands.append('npm run test -- --watch=false')
    elif runtime.get('runtime_type') == 'django':
        commands.append('python manage.py check')
        commands.append('python manage.py test')
    elif runtime.get('runtime_type') == 'python':
        if (workspace_path / 'pytest.ini').exists() or (workspace_path / 'tests').exists():
            commands.append('pytest')
        elif runtime.get('entrypoint'):
            commands.append(f"python -m py_compile {runtime.get('entrypoint')}")

    return commands[:3]


def _run_validation_suite(workspace_path: Path) -> list[dict]:
    results = []
    for command in _validation_commands(workspace_path):
        try:
            completed = subprocess.run(
                command,
                cwd=str(workspace_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            results.append({
                'command': command,
                'success': completed.returncode == 0,
                'exit_code': completed.returncode,
                'stdout': completed.stdout[:4000],
                'stderr': completed.stderr[:4000],
            })
        except subprocess.TimeoutExpired:
            results.append({
                'command': command,
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': 'Timed out after 180 seconds.',
            })
        except Exception as exc:
            results.append({
                'command': command,
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': str(exc),
            })
    return results


def _validation_summary(results: list[dict]) -> str:
    if not results:
        return "No validation commands were available."
    lines = []
    for result in results:
        status = 'passed' if result.get('success') else 'failed'
        lines.append(f"- {result.get('command')}: {status}")
        if result.get('stderr'):
            lines.append(f"  stderr: {str(result['stderr'])[:240]}")
    return "\n".join(lines)


def _all_validations_passed(results: list[dict]) -> bool:
    return all(result.get('success') for result in results) if results else True


def _build_review_diff(workspace_path: Path, previous_contents: dict, applied_files: list[str]) -> str:
    sections = []
    for rel_path in applied_files:
        current_path = workspace_path / rel_path
        before = previous_contents.get(rel_path, "")
        after = current_path.read_text(encoding='utf-8', errors='ignore') if current_path.exists() else ""
        diff = ''.join(
            unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f'a/{rel_path}',
                tofile=f'b/{rel_path}',
            )
        )
        sections.append(diff or f"# {rel_path}\nNo textual diff available.")
    return "\n".join(sections)[:14000]


def _review_attempt(
    project: Project,
    workspace_path: Path,
    previous_contents: dict,
    applied_files: list[str],
    validation_results: list[dict],
    customization_bundle: dict | None = None,
    request_text: str = "",
    request_attachments: list[dict] | None = None,
) -> dict:
    if not applied_files:
        return {
            'approved': True,
            'score': 100,
            'summary': 'No file changes were produced.',
            'issues': [],
        }

    if not ai_config_is_usable(_project_ai_config(project)):
        issues = []
        for result in validation_results:
            if not result.get('success'):
                issues.append({
                    'severity': 'high',
                    'file': '',
                    'description': f"Validation failed for {result.get('command')}",
                    'suggestion': str(result.get('stderr') or result.get('stdout') or '')[:300],
                })
        return {
            'approved': _all_validations_passed(validation_results),
            'score': 95 if _all_validations_passed(validation_results) else 40,
            'summary': _validation_summary(validation_results),
            'issues': issues,
        }

    try:
        from agents.reviewer import ReviewerAgent

        reviewer = ReviewerAgent(
            ai_config=_project_ai_config(project),
            customization_instruction=build_role_customization_addendum(customization_bundle, "reviewer"),
        )
        return reviewer.review_changeset(
            changeset_diff=_build_review_diff(workspace_path, previous_contents, applied_files),
            tech_stack=", ".join(project.tech_stack or []),
            blueprint=json.dumps(project.blueprint or {}, indent=2)[:3000],
            evaluation_summary=_validation_summary(validation_results),
            customization_context=build_role_prompt_context(customization_bundle, "reviewer")[:8000],
            request_text=request_text,
            request_attachments=request_attachments,
        )
    except Exception:
        logger.exception("ReviewerAgent failed for project %s", project.id)
        return {
            'approved': _all_validations_passed(validation_results),
            'score': 70 if _all_validations_passed(validation_results) else 45,
            'summary': _validation_summary(validation_results),
            'issues': [],
        }


def _count_total_workspace_files(workspace_path: Path) -> int:
    """
    Count all files in the workspace (not just indexable ones).
    Used for routing decisions so that Go/Rust/Java/etc. repos aren't
    incorrectly classified as empty by manifest_file_count.
    """
    try:
        total = 0
        for root, dirs, files in os.walk(workspace_path):
            # Mirror SKIP_DIRS logic to avoid inflating counts with node_modules etc.
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            total += len(files)
            if total > 100_000:  # Cap to avoid hanging on massive repos
                return total
        return total
    except Exception:
        return 0


def generate_blueprint_sync(project: Project):
    """
    Generate a project blueprint and persist it to ``project.blueprint``.

    Size-based routing uses TOTAL file count (all files, any language) so
    that Go/Rust/Java/Ruby/etc. repos are routed correctly.

      any size w/ workspace → BlueprintQueryAgent (tool-based exploration)
                              agent self-discovers the tech stack via tools
      ≥ 10 000 total files  → BlueprintQueryAgent.generate_parallel()
                              (Coordinator + 3 parallel workers)
      no workspace / no AI  → ArchitectAgent fallback (best-effort)

    All paths enrich the raw blueprint through _enrich_blueprint_document and
    store _meta for UI transparency.
    """
    # ── Thresholds ────────────────────────────────────────────────────────
    PARALLEL_PATH_MIN_FILES = 10_000

    codebase_context: dict = {}
    feature_summary = _render_project_features_summary(project, limit=20)

    try:
        from agents.architect import ArchitectAgent
        from agents.blueprint_agent import BlueprintQueryAgent
        from agents.explorer import CodebaseExplorerAgent
        from agents.memory import slim_context_for_llm

        local_scan = ""
        readme = ""
        exploration_report: dict = {}
        repo_map_text = ""
        workspace_path: Path | None = None
        total_file_count = 0

        if project.local_path and Path(project.local_path).is_dir():
            workspace_path = Path(project.local_path)
            local_scan = scan_local_folder(project.local_path)

            readme_path = workspace_path / "README.md"
            if not readme_path.exists():
                readme_path = workspace_path / "readme.md"
            if readme_path.exists():
                try:
                    readme = readme_path.read_text(encoding="utf-8", errors="ignore")[:3000]
                except Exception:
                    pass

            try:
                codebase_context = build_blueprint_context(project, workspace_path, force=True)
                repo_map_path = workspace_path / DEVHUB_META_DIR / "repo-map.md"
                if repo_map_path.exists():
                    repo_map_text = repo_map_path.read_text(encoding="utf-8", errors="ignore")[:12000]
            except Exception:
                logger.exception("Blueprint context build failed for project %s", project.id)
                codebase_context = {}

            # Count ALL files (not just indexable) for routing
            total_file_count = _count_total_workspace_files(workspace_path)

        manifest_file_count = int((codebase_context or {}).get('manifest_file_count') or 0)
        ai_config = _project_ai_config(project)
        usable_ai = ai_config_is_usable(ai_config)

        logger.info(
            "Blueprint routing for project %s: total_files=%d manifest_files=%d",
            project.id,
            total_file_count,
            manifest_file_count,
        )

        # ── Route: always use tool-based BlueprintQueryAgent when possible ─
        # The agent self-discovers the tech stack; no hardcoded language assumptions.
        if usable_ai and workspace_path:
            compact_summary = str((codebase_context or {}).get('compact_summary') or '')
            repo_tree = str((codebase_context or {}).get('repo_tree') or repo_map_text or '')
            graph_summary = str((codebase_context or {}).get('graph_summary') or '')
            dir_count = len((codebase_context or {}).get('directory_counts') or {})

            agent = BlueprintQueryAgent(
                workspace_path=workspace_path,
                ai_config=ai_config,
            )

            if total_file_count >= PARALLEL_PATH_MIN_FILES:
                logger.info("Blueprint: parallel coordinator path (%d total files)", total_file_count)
                blueprint = agent.generate_parallel(
                    project_name=project.name,
                    tech_stack=project.tech_stack or [],
                    compact_summary=compact_summary,
                    repo_tree=repo_tree,
                    graph_summary=graph_summary,
                    feature_summary=feature_summary,
                    file_count=total_file_count,
                )
            else:
                logger.info("Blueprint: single-agent tool path (%d total files)", total_file_count)
                blueprint = agent.generate(
                    project_name=project.name,
                    tech_stack=project.tech_stack or [],
                    compact_summary=compact_summary,
                    repo_tree=repo_tree,
                    graph_summary=graph_summary,
                    feature_summary=feature_summary,
                    file_count=total_file_count,
                    dir_count=dir_count,
                )

        # ── Fallback: no workspace or no AI → ArchitectAgent single-call ──
        else:
            if usable_ai and codebase_context:
                try:
                    explorer = CodebaseExplorerAgent(ai_config=ai_config)
                    exploration_report = explorer.explore_codebase(
                        project_name=project.name,
                        tech_stack=project.tech_stack or [],
                        codebase_context=codebase_context,
                    )
                    upsert_working_memory(
                        project,
                        'blueprint_exploration',
                        json.dumps(exploration_report, indent=2)[:12000],
                        {
                            'fingerprint': codebase_context.get('fingerprint'),
                            'important_files': [
                                item.get('path')
                                for item in (codebase_context.get('important_files') or [])[:12]
                            ],
                        },
                    )
                except Exception:
                    logger.exception("Blueprint exploration failed for project %s", project.id)

            architect = ArchitectAgent(ai_config=ai_config)
            blueprint = architect.generate_blueprint(
                project_name=project.name,
                tech_stack=project.tech_stack or [],
                local_scan=local_scan,
                readme=readme,
                codebase_context=codebase_context,
                exploration_report=exploration_report,
                feature_summary=feature_summary,
                repo_map=repo_map_text,
            )

        blueprint = _enrich_blueprint_document(project, blueprint, codebase_context, feature_summary)
        if isinstance(blueprint, dict):
            blueprint["_meta"] = {
                "codebase_fingerprint": (codebase_context or {}).get("fingerprint"),
                "indexed_files": (codebase_context or {}).get("file_count"),
                "total_files": total_file_count,
                "manifest_files": manifest_file_count,
                "generation_path": (
                    "parallel_coordinator" if total_file_count >= PARALLEL_PATH_MIN_FILES
                    else "tool_agent" if workspace_path and usable_ai
                    else "fallback_single_call"
                ),
                "cached": bool(codebase_context),
            }
        project.blueprint = blueprint
        project.save()

    except Exception as exc:
        fallback_blueprint = {
            "architecture_overview": (
                f"Blueprint generation failed: {str(exc)}. "
                "Check the configured DevHub AI provider settings."
            ),
            "tech_stack_details": [
                {"tech": t, "purpose": "Core technology"} for t in (project.tech_stack or [])
            ],
            "services": [],
            "setup_steps": [],
            "gotchas": [str(exc)],
        }
        try:
            fallback_blueprint = _enrich_blueprint_document(
                project, fallback_blueprint, codebase_context, feature_summary
            )
            fallback_blueprint["_meta"] = {
                "codebase_fingerprint": (codebase_context or {}).get("fingerprint"),
                "indexed_files": (codebase_context or {}).get("file_count"),
                "manifest_files": int((codebase_context or {}).get("manifest_file_count") or 0),
                "generation_path": "fallback",
                "cached": bool(codebase_context),
            }
        except Exception:
            logger.exception("Blueprint fallback enrichment failed for project %s", project.id)
        project.blueprint = fallback_blueprint
        project.save()


def _generate_blueprint_for_project_id(project_id: str) -> None:
    close_old_connections()
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return
    except OperationalError:
        logger.warning("Skipped background blueprint generation for project %s because the database was busy.", project_id)
        return
    try:
        generate_blueprint_sync(project)
    except Exception:
        logger.exception("Background blueprint generation failed for project %s", project_id)
    finally:
        close_old_connections()


def _generate_documentation_for_project_id(project_id: str) -> None:
    close_old_connections()
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return
    except OperationalError:
        logger.warning("Skipped background documentation generation for project %s because the database was busy.", project_id)
        return
    try:
        generate_codebase_reference_sync(project)
    except Exception:
        logger.exception("Background documentation generation failed for project %s", project_id)
    finally:
        close_old_connections()


def _schedule_project_context_generation(
    project: Project,
    *,
    include_documentation: bool = False,
    include_blueprint: bool = True,
) -> None:
    if include_blueprint:
        logger.info("Scheduling background blueprint generation for project %s", project.id)
        blueprint_thread = threading.Thread(target=_generate_blueprint_for_project_id, args=(str(project.id),))
        blueprint_thread.daemon = True
        blueprint_thread.start()

    if not include_documentation:
        return

    if DocumentationRun.objects.filter(project=project, status__in=['pending', 'running']).exists():
        return

    logger.info("Scheduling background documentation generation for project %s", project.id)
    documentation_thread = threading.Thread(target=_generate_documentation_for_project_id, args=(str(project.id),))
    documentation_thread.daemon = True
    documentation_thread.start()


def generate_feature_spec_sync(feature: Feature, project: Project):
    try:
        from agents.feature import FeatureAgent

        agent = FeatureAgent(ai_config=_project_ai_config(project))
        blueprint_summary = json.dumps(project.blueprint, indent=2)[:2000] if project.blueprint else "No blueprint available"
        tech_stack = ", ".join(project.tech_stack) if project.tech_stack else "Not specified"

        spec = agent.generate_spec(
            feature_title=feature.title,
            feature_desc=feature.description,
            tech_stack=tech_stack,
            blueprint=blueprint_summary,
        )
        feature.spec = spec
        feature.save()
    except Exception as exc:
        feature.spec = {"error": str(exc), "user_story": f"Feature: {feature.title}", "technical_approach": feature.description}
        feature.save()


def _run_multi_agent_implementation(
    project: Project,
    request_title: str,
    request_text: str,
    spec: dict,
    selected_file: str = "",
    selected_content: str = "",
    request_attachments: list[dict] | None = None,
    checkpoint: dict | None = None,
    chat_mode: str | None = None,
    changeset_source: str = 'chat',
) -> dict:
    if not project.workspace_id:
        raise ValueError("No active workspace for this project.")

    from agents.coder import CoderAgent

    workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
    try:
        semantic_exists = SemanticMemory.objects.filter(project=project).exists()
    except MEMORY_DB_ERRORS:
        semantic_exists = True
    if not semantic_exists:
        index_semantic_memory(project, workspace_path)

    compressed_summary = compress_recent_activity(project)
    project_memory = _read_project_memory(project, workspace_path)
    project_instructions = _read_project_instructions(project, workspace_path)
    customization_bundle = build_implementation_customization_bundle(workspace_path, request_text)
    base_request_text = implementation_request_text(customization_bundle, request_text) or request_text
    memory_context = build_memory_context(project, base_request_text, selected_file=selected_file)
    memory_context_text = f"""Working Memory:
{memory_context.get('working_summary') or compressed_summary}

Cached Codebase Summary:
{memory_context.get('blueprint_summary', '')[:1800]}

Episodic Memory:
{memory_context.get('episodic_summary')}

Semantic Memory:
{memory_context.get('semantic_summary')}
"""

    baseline_contents: dict[str, str] = {}
    attempt_logs = []
    all_applied_files: list[str] = []
    latest_plan = {}
    latest_review = {}
    latest_validation_results: list[dict] = []
    latest_context_files: list[str] = []
    current_request_text = base_request_text
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        logger.exception("Failed to load cached codebase context for implementation in project %s", project.id)

    active_skill = customization_bundle.get("skill") if isinstance(customization_bundle.get("skill"), dict) else {}
    if active_skill:
        spec = {
            **(spec or {}),
            "project_skill": {
                "name": active_skill.get("name"),
                "description": active_skill.get("description"),
                "path": active_skill.get("path"),
                "arguments": customization_bundle.get("skill_arguments") or "",
            },
        }

    agent = CoderAgent(
        ai_config=_project_ai_config(project),
        customization_instruction=build_role_customization_addendum(customization_bundle, "coder"),
    )

    for attempt in range(1, 4):
        plan = _create_implementation_plan(
            project=project,
            request_title=request_title,
            request_text=current_request_text,
            workspace_path=workspace_path,
            project_memory=f"{project_memory[:8000]}\n\nProject Instructions:\n{project_instructions[:3000]}\n\n{memory_context_text[:4000]}",
            memory_context_text=memory_context_text,
            selected_file=selected_file,
            customization_bundle=customization_bundle,
            request_attachments=request_attachments,
        )
        latest_plan = plan

        files_context = _collect_relevant_files(
            workspace_path=workspace_path,
            plan=plan,
            request_text=current_request_text,
            codebase_context=codebase_context,
            selected_file=selected_file,
            selected_content=selected_content,
        )
        latest_context_files = [item.get('path') for item in files_context if item.get('path')]
        for item in files_context:
            baseline_contents.setdefault(item['path'], item['content'])

        supporting_context = (
            _build_supporting_context(project, plan, workspace_path, customization_bundle=customization_bundle)
            + "\n\nMemory Recall:\n"
            + memory_context_text
            + "\n\nValidation Guidance:\n"
            + _validation_summary(latest_validation_results)
        )

        result = agent.implement_feature(
            workspace_id=project.workspace_id,
            feature_title=request_title,
            feature_desc=current_request_text,
            spec=spec,
            files_context=files_context,
            implementation_plan=plan,
            project_memory=f"{project_memory[:8000]}\n\nProject Instructions:\n{project_instructions[:3000]}",
            supporting_context=supporting_context[:10000],
            customization_context=build_role_prompt_context(customization_bundle, "coder")[:10000],
            request_attachments=request_attachments,
        )

        if result.get("status") != "success":
            raise RuntimeError(result.get("error", "Failed to apply changes."))

        applied_files = result.get("files_modified", [])
        for rel_path in applied_files:
            if rel_path not in all_applied_files:
                all_applied_files.append(rel_path)

        latest_validation_results = _run_validation_suite(workspace_path)
        latest_review = _review_attempt(
            project,
            workspace_path,
            baseline_contents,
            all_applied_files,
            latest_validation_results,
            customization_bundle=customization_bundle,
            request_text=current_request_text,
            request_attachments=request_attachments,
        )
        attempt_logs.append({
            'attempt': attempt,
            'applied_files': applied_files,
            'validation': latest_validation_results,
            'review': latest_review,
        })

        if _all_validations_passed(latest_validation_results) and latest_review.get('approved', True):
            break

        if attempt == 3:
            break

        repair_issues = latest_review.get('issues', [])
        repair_lines = [
            base_request_text,
            "",
            f"Repair pass {attempt}: keep the requested behavior, but fix the validation and review issues below.",
            "Validation Results:",
            _validation_summary(latest_validation_results),
            "Reviewer Summary:",
            latest_review.get('summary', 'No reviewer summary.'),
        ]
        if repair_issues:
            repair_lines.append("Reviewer Issues:")
            for issue in repair_issues[:8]:
                repair_lines.append(f"- {issue.get('severity', 'issue')}: {issue.get('description', '')} :: {issue.get('suggestion', '')}")
        current_request_text = "\n".join(repair_lines)
        spec = {
            **spec,
            'repair_iteration': attempt,
            'validation_results': latest_validation_results,
            'review_feedback': latest_review,
        }
        memory_context = build_memory_context(project, current_request_text, selected_file=selected_file)
        memory_context_text = f"""Working Memory:
{memory_context.get('working_summary') or compressed_summary}

Cached Codebase Summary:
{memory_context.get('blueprint_summary', '')[:1800]}

Episodic Memory:
{memory_context.get('episodic_summary')}

Semantic Memory:
{memory_context.get('semantic_summary')}
"""

    if not _all_validations_passed(latest_validation_results) or not latest_review.get('approved', True):
        raise RuntimeError(
            "Implementation did not pass the validation/review loop.\n"
            f"{_validation_summary(latest_validation_results)}\n"
            f"Reviewer: {latest_review.get('summary', 'No summary available.')}"
        )

    changeset = _record_chat_changes(
        project,
        request_text,
        workspace_path,
        baseline_contents,
        all_applied_files,
        ai_review=_chat_checkpoint_review_payload(
            checkpoint,
            source=changeset_source,
            chat_mode=chat_mode,
            undo_label='Undo Restore' if changeset_source == 'chat_undo' else 'Undo',
        ),
    )
    if checkpoint and not changeset:
        delete_workspace_checkpoint(str(project.id), str(checkpoint.get('id') or ''))
    _update_project_memory(project, workspace_path, request_text, all_applied_files, latest_plan.get('memory_updates', []))
    index_semantic_memory(project, workspace_path, changed_paths=all_applied_files)
    record_episode(
        project=project,
        memory_type='implementation',
        title=request_title,
        summary=(
            f"Completed implementation for '{request_title}'. "
            f"Files: {', '.join(all_applied_files) or 'none'}. "
            f"Validation: {_validation_summary(latest_validation_results)}. "
            f"Reviewer: {latest_review.get('summary', 'approved')}."
        ),
        related_files=all_applied_files,
        metadata={
            'plan': latest_plan,
            'validation': latest_validation_results,
            'review': latest_review,
            'attempts': attempt_logs,
        },
    )
    upsert_working_memory(
        project,
        'implementation',
        (
            f"Latest implementation request: {request_title}\n"
            f"Files touched: {', '.join(all_applied_files) or 'none'}\n"
            f"Validation summary:\n{_validation_summary(latest_validation_results)}\n"
            f"Reviewer summary: {latest_review.get('summary', 'No reviewer summary.')}"
        ),
        {'latest_request': request_title, 'files': all_applied_files},
    )

    if ai_config_is_usable(_project_ai_config(project)):
        refresh_thread = threading.Thread(target=generate_blueprint_sync, args=(project,))
        refresh_thread.daemon = True
        refresh_thread.start()

    return {
        "applied_files": all_applied_files,
        "count": len(all_applied_files),
        "plan": latest_plan,
        "review": latest_review,
        "validation_results": latest_validation_results,
        "attempts": attempt_logs,
        "context_files": latest_context_files,
        "changeset_id": str(changeset.id) if changeset else None,
        "undo": _chat_changeset_trace_metadata(changeset).get('undo') if changeset else None,
    }


def implement_feature_sync(feature: Feature, project: Project):
    try:
        close_old_connections()

        feature.status = 'development'
        feature.save()
        FeatureHistory.objects.create(feature=feature, stage='development', action='implementation_started', by='AI Coder')

        result = _run_multi_agent_implementation(
            project=project,
            request_title=feature.title,
            request_text=feature.description,
            spec=feature.spec or {},
        )

        if result.get("count", 0) >= 0:
            files_mod = ", ".join(result.get('applied_files', []))
            FeatureHistory.objects.create(feature=feature, stage='development', action='implementation_completed', by='AI Coder', comment=f"Modified files: {files_mod}")
    except Exception as exc:
        try:
            FeatureHistory.objects.create(feature=feature, stage='development', action='implementation_failed', by='System', comment=str(exc))
            record_episode(
                project=project,
                memory_type='implementation_failure',
                title=feature.title,
                summary=f"Implementation failed for '{feature.title}': {str(exc)}",
                related_files=[],
                metadata={'error': str(exc)},
            )
        except Exception:
            logger.exception("Failed to persist implementation failure for feature %s", feature.id)
        logger.exception("Feature implementation failed for feature %s", feature.id)
    finally:
        close_old_connections()


def _collect_workspace_context(workspace_path: Path, selected_file: str = "", selected_content: str = "", limit: int = 24) -> list[dict]:
    source_exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".md"}
    context = []
    seen = set()

    def add_entry(rel_path: str, content: str):
        normalized = rel_path.replace('\\', '/')
        if normalized in seen or len(context) >= limit:
            return
        seen.add(normalized)
        context.append({"path": normalized, "content": content})

    if selected_file:
        if selected_content:
            add_entry(selected_file, selected_content)
        else:
            selected_path = workspace_path / selected_file
            if selected_path.exists() and selected_path.is_file():
                try:
                    add_entry(selected_file, selected_path.read_text(encoding='utf-8', errors='ignore'))
                except Exception:
                    pass

    priority_files = [
        "package.json", "vite.config.js", "vite.config.ts", "index.html",
        "main.py", "app.py", "requirements.txt", "manage.py", "README.md",
    ]
    for rel_path in priority_files:
        candidate = workspace_path / rel_path
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            add_entry(rel_path, candidate.read_text(encoding='utf-8', errors='ignore'))
        except Exception:
            continue

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for filename in sorted(files):
            if len(context) >= limit:
                return context
            path = Path(root) / filename
            rel_path = str(path.relative_to(workspace_path)).replace('\\', '/')
            if path.suffix.lower() not in source_exts:
                continue
            try:
                add_entry(rel_path, path.read_text(encoding='utf-8', errors='ignore'))
            except Exception:
                continue

    return context


def _looks_like_edit_request(message: str) -> bool:
    lower = message.lower()
    edit_verbs = (
        'add', 'build', 'change', 'create', 'edit', 'fix', 'implement',
        'make',
        'improve', 'modify', 'redesign', 'refactor', 'remove', 'rename',
        'replace', 'restyle', 'update',
    )
    question_starts = ('what', 'why', 'how', 'explain', 'show', 'where', 'which')
    return any(re.search(rf'\b{verb}\b', lower) for verb in edit_verbs) and not lower.startswith(question_starts)


def _looks_like_read_only_request(message: str) -> bool:
    lowered = str(message or '').strip().lower()
    if not lowered:
        return False

    edit_verbs = (
        'add', 'build', 'change', 'create', 'edit', 'fix', 'implement',
        'make', 'improve', 'modify', 'redesign', 'refactor', 'remove',
        'rename', 'replace', 'restyle', 'update',
    )
    if any(re.search(rf'\b{verb}\b', lowered) for verb in edit_verbs):
        return False

    explicit_read_only_prefixes = (
        'what ', 'why ', 'how ', 'where ', 'which ', 'explain ',
        'inspect ', 'analyze ', 'analyse ', 'review ', 'summarize ',
        'summarise ', 'show me ', 'tell me ', 'read through ', 'go through ',
    )
    explicit_read_only_phrases = (
        'how does',
        'what does',
        'why does',
        'can you explain',
        'could you explain',
        'can you inspect',
        'could you inspect',
        'can you review',
        'could you review',
        'just explain',
        'just inspect',
        'just analyze',
        'just review',
        'without changing',
        'without edits',
        'do not change',
        "don't change",
        'read-only',
    )
    return (
        any(lowered.startswith(prefix) for prefix in explicit_read_only_prefixes)
        or any(phrase in lowered for phrase in explicit_read_only_phrases)
    )


CHAT_SPECIAL_CONTEXTS = {
    'codebase': 'Whole-project summary and indexed repo context',
    'currentfile': 'The file currently open in the workspace',
    'readme': 'Root docs like README, CONTRIBUTING, SECURITY, and VISION',
    'rules': 'Project instructions and workspace rules',
    'conversation': 'Recent chat history in this project',
    'terminal': 'Runtime status and detected commands',
}
LEGACY_CHAT_SESSION_ID = "legacy-project-chat"


def _chat_workspace_path(project: Project) -> Path | None:
    if project.workspace_id:
        try:
            return workspace_manager.get_workspace_path(project.workspace_id)
        except Exception:
            pass
    return _project_workspace_path(project)


def _normalize_chat_mentions(raw_mentions) -> list[dict]:
    normalized = []
    for item in raw_mentions or []:
        if isinstance(item, str):
            value = item.strip()
            if not value:
                continue
            mention_type = 'special' if value.lower().lstrip('@') in CHAT_SPECIAL_CONTEXTS else 'file'
            normalized.append({'type': mention_type, 'value': value.lstrip('@'), 'label': f"@{value.lstrip('@')}"})
            continue
        if not isinstance(item, dict):
            continue
        mention_type = str(item.get('type') or '').strip().lower()
        value = str(item.get('value') or '').strip().lstrip('@')
        if mention_type not in {'special', 'file', 'folder'} or not value:
            continue
        normalized.append({
            'type': mention_type,
            'value': value,
            'label': str(item.get('label') or f"@{value}"),
        })
    return normalized


def _infer_inline_chat_mentions(content: str) -> list[dict]:
    inferred = []
    for token in re.findall(r'@([A-Za-z0-9_./-]+)', str(content or '')):
        value = token.strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in CHAT_SPECIAL_CONTEXTS:
            inferred.append({'type': 'special', 'value': value, 'label': f"@{value}"})
        elif '/' in value or '.' in value:
            inferred.append({'type': 'file', 'value': value, 'label': f"@{value}"})
    return inferred


def _dedupe_chat_mentions(*groups: list[dict]) -> list[dict]:
    seen = set()
    merged = []
    for group in groups:
        for item in group or []:
            key = (item.get('type'), item.get('value'))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _chat_session_id_from_metadata(metadata) -> str:
    if isinstance(metadata, dict):
        session_id = str(metadata.get('session_id') or '').strip()
        if session_id:
            return session_id
    return LEGACY_CHAT_SESSION_ID


def _chat_message_session_id(message) -> str:
    if isinstance(message, dict):
        return _chat_session_id_from_metadata(message.get('metadata') or {})
    return _chat_session_id_from_metadata(getattr(message, 'metadata', {}) or {})


def _chat_session_title(messages: list[dict], session_id: str) -> str:
    for item in messages:
        if str(item.get('role') or '') != 'user':
            continue
        content = str(item.get('content') or '').strip()
        attachments = _chat_message_attachments(item)
        if not content:
            if attachments:
                first_name = str((attachments[0] or {}).get('name') or 'Attached image').strip() or 'Attached image'
                if len(attachments) == 1:
                    return first_name
                return f"{first_name} (+{len(attachments) - 1} more)"
            continue
        first_line = content.splitlines()[0].strip()
        if not first_line:
            continue
        return first_line if len(first_line) <= 72 else f"{first_line[:69]}..."
    return 'Previous chat' if session_id == LEGACY_CHAT_SESSION_ID else 'New chat'


def _serialize_chat_message(project: Project, item: dict) -> dict:
    metadata = dict(item.get('metadata') or {})
    attachments = _chat_message_attachments(metadata)
    if attachments:
        metadata['attachments'] = attachments
    changeset = _changeset_by_id(project, metadata.get('changeset_id'))
    if changeset:
        metadata.update(_chat_changeset_trace_metadata(changeset))
    return {
        'id': item.get('id'),
        'role': item.get('role'),
        'content': item.get('content'),
        'metadata': metadata,
        'created_at': item.get('created_at'),
        'session_id': _chat_session_id_from_metadata(metadata),
    }


def _project_chat_messages(project: Project) -> list[dict]:
    return list(
        ChatMessage.objects.filter(project=project)
        .order_by('created_at', 'id')
        .values('id', 'role', 'content', 'metadata', 'created_at')
    )


def _group_project_chat_sessions(project: Project) -> tuple[dict[str, list[dict]], list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in _project_chat_messages(project):
        grouped.setdefault(_chat_message_session_id(item), []).append(item)

    sessions = []
    for session_id, messages in grouped.items():
        latest = messages[-1]
        sessions.append(
            {
                'session_id': session_id,
                'title': _chat_session_title(messages, session_id),
                'updated_at': latest.get('created_at'),
                'message_count': len(messages),
                'legacy': session_id == LEGACY_CHAT_SESSION_ID,
            }
        )
    sessions.sort(key=lambda item: item.get('updated_at') or timezone.now(), reverse=True)
    return grouped, sessions


def _safe_read_workspace_file(workspace_path: Path, rel_path: str, limit: int = 5000) -> str:
    normalized = str(rel_path or '').replace('\\', '/').strip('/')
    if not normalized:
        return ''
    candidate = workspace_path / normalized
    try:
        candidate.resolve().relative_to(workspace_path.resolve())
    except Exception:
        return ''
    try:
        if candidate.exists() and candidate.is_file():
            return candidate.read_text(encoding='utf-8', errors='ignore')[:limit]
    except Exception:
        return ''
    return ''


def _folder_context_block(codebase_context: dict, folder_path: str) -> tuple[str, list[dict]]:
    normalized = str(folder_path or '').replace('\\', '/').strip('/').rstrip('/')
    if not normalized:
        return '', []
    important_files = [
        item for item in (codebase_context.get('important_files') or [])
        if str(item.get('path') or '').startswith(f"{normalized}/")
    ][:8]
    if not important_files:
        return '', []
    lines = [f"Folder context for `{normalized}/`:"]
    evidence = []
    for item in important_files:
        path = str(item.get('path') or '')
        lines.append(f"- `{path}`: {item.get('summary') or item.get('brief') or 'Indexed file'}")
        evidence.append({
            'path': path,
            'source': 'folder',
            'reason': f"Used as representative evidence for the `{normalized}/` folder.",
        })
    return "\n".join(lines), evidence


def _lazy_chat_file_context(workspace_path: Path | None, rel_path: str, codebase_context: dict | None = None, limit: int = 5000) -> tuple[str, dict | None]:
    if not workspace_path or not rel_path:
        return "", None
    try:
        target_path = (workspace_path / rel_path).resolve()
        if workspace_path.resolve() not in target_path.parents and target_path != workspace_path.resolve():
            return "", None
        if not target_path.exists() or not target_path.is_file():
            return "", None
    except Exception:
        return "", None

    normalized = str(rel_path).replace("\\", "/").strip("/")
    summary = _cached_file_summary(codebase_context or {}, normalized) or _file_summary(target_path, workspace_path, include_excerpt=True)
    content = read_query_relevant_file_content(workspace_path, normalized, query=normalized, limit=limit)
    if not content:
        return "", summary

    blocks = [f"`{normalized}`"]
    if summary:
        blocks.append(f"Summary: {summary.get('summary') or summary.get('purpose') or 'No summary available.'}")
        if summary.get("symbol"):
            blocks.append(f"Primary symbol: {summary.get('symbol')}")
        if summary.get("routes"):
            blocks.append(f"Routes: {', '.join(summary.get('routes')[:6])}")
        if summary.get("data_models"):
            blocks.append(f"Models: {', '.join(summary.get('data_models')[:6])}")
    blocks.append("Content:")
    blocks.append(content)
    return "\n".join(blocks), summary


def _looks_like_ui_style_question(content: str) -> bool:
    lowered = str(content or '').lower()
    if not lowered:
        return False
    broad_redesign_markers = (
        'whole ui', 'entire ui', 'make it dark', 'dark theme', 'dark themed',
        'glassmorphism', 'glassmorph', 'translucent', 'topbar', 'top bar',
        'delete button', 'remove the', 'move it', 'move the', 'retheme',
        'redesign', 'restyle the whole', 'overall theme',
    )
    if any(marker in lowered for marker in broad_redesign_markers):
        return False
    style_markers = (
        'color', 'colour', 'highlight', 'background', 'bg-', 'hover', 'text color',
        'text-color', 'selected', 'active', 'border', 'hover state',
    )
    ui_markers = (
        'sidebar', 'side bar', 'nav', 'navigation', 'menu', 'tab', 'tabs',
        'item', 'items', 'button', 'buttons', 'file tree', 'explorer',
        'folder', 'panel', 'selected', 'active',
    )
    action_markers = ('change', 'edit', 'update', 'modify', 'set', 'switch', 'customize', 'tweak')
    has_style = any(marker in lowered for marker in style_markers)
    has_ui = any(marker in lowered for marker in ui_markers)
    has_action = any(marker in lowered for marker in action_markers) or 'how do i' in lowered or 'how to' in lowered
    return has_style and has_ui and has_action


def _looks_like_ui_redesign_request(content: str) -> bool:
    lowered = str(content or '').lower()
    if not lowered:
        return False
    redesign_markers = (
        'whole ui', 'entire ui', 'make it dark', 'dark theme', 'dark themed',
        'glassmorphism', 'glassmorph', 'translucent', 'topbar', 'top bar',
        'toolbar', 'header', 'delete button', 'remove the', 'move it', 'move the',
        'layout', '2 pane', 'two pane', 'two-pane', 'split pane', 'split view',
        'restyle', 'redesign', 'workspace',
    )
    action_markers = ('change', 'edit', 'update', 'modify', 'make', 'move', 'remove', 'convert')
    return any(marker in lowered for marker in redesign_markers) and any(marker in lowered for marker in action_markers)


CHAT_STATE_NEEDS_CLARIFICATION = 'needs_clarification'
CHAT_STATE_GROUNDED_ANSWER = 'grounded_answer'
CHAT_STATE_EDIT_REQUEST = 'edit_request'
CHAT_STATE_BROAD_REDESIGN = 'broad_redesign'
CHAT_STATE_AGENT_REQUEST = 'agent_request'

CHAT_MODE_ASK = 'ask'
CHAT_MODE_EDIT = 'edit'
CHAT_MODE_AGENT = 'agent'
CHAT_MODE_VALUES = {CHAT_MODE_ASK, CHAT_MODE_EDIT, CHAT_MODE_AGENT}


def _normalize_chat_mode(value) -> str | None:
    normalized = str(value or '').strip().lower()
    if normalized in CHAT_MODE_VALUES:
        return normalized
    return None


def _should_apply_changes_for_chat_mode(chat_mode: str | None, content: str, apply_changes) -> bool:
    if chat_mode == CHAT_MODE_ASK:
        return False
    if chat_mode == CHAT_MODE_EDIT:
        return True
    if chat_mode == CHAT_MODE_AGENT:
        if apply_changes is None:
            return not _looks_like_read_only_request(content)
        return bool(apply_changes)
    return _looks_like_edit_request(content) if apply_changes is None else bool(apply_changes)


def _extract_class_fragments(snippet: str) -> list[str]:
    fragments: list[str] = []
    seen: set[str] = set()
    patterns = [
        r"'([^']+)'",
        r'"([^"]+)"',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, str(snippet or '')):
            normalized = str(match or '').strip()
            if not normalized or normalized in seen:
                continue
            if any(marker in normalized for marker in ('${', '?', '=>', '{', '}')):
                continue
            tokens = [token for token in normalized.split() if token]
            if not tokens:
                continue
            if not any(
                token.startswith(('bg-', 'text-', 'hover:', 'border-', 'shadow-[', 'fill-', 'ring-', 'outline-', 'from-', 'to-'))
                for token in tokens
            ):
                continue
            seen.add(normalized)
            fragments.append(normalized)
    return fragments


def _describe_ui_style_match(snippet: str) -> str:
    lowered = str(snippet or '').lower()
    if 'activetab === tab.id' in lowered:
        return 'active navigation item'
    if 'selectedfile === node.path' in lowered:
        return 'selected file row'
    if 'activesidepanel' in lowered:
        return 'active side panel icon'
    if 'hover:bg' in lowered or 'hover:text' in lowered:
        return 'hover state'
    if 'selected' in lowered:
        return 'selected item'
    if 'active' in lowered:
        return 'active item'
    return 'matching UI state'


def _extract_ui_style_evidence(workspace_path: Path | None, file_paths: list[str], query: str, limit: int = 4) -> list[dict]:
    if not workspace_path:
        return []

    unique_paths: list[str] = []
    seen_paths: set[str] = set()
    for raw_path in file_paths:
        normalized = str(raw_path or '').replace('\\', '/').strip('/')
        if not normalized or normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        unique_paths.append(normalized)

    def path_score(rel_path: str) -> float:
        lowered_path = str(rel_path or '').lower()
        score = 0.0
        if 'sidebar' in str(query or '').lower():
            if any(token in lowered_path for token in ('projectview', 'workspace', 'sidebar', 'nav', 'panel')):
                score += 3.0
        if any(token in lowered_path for token in ('projectview', 'workspace', 'panel', 'layout', 'header', 'nav', 'sidebar')):
            score += 1.5
        if '/pages/' in lowered_path:
            score += 1.0
        return score

    unique_paths.sort(key=lambda path: (-path_score(path), path))

    query_terms = {
        term for term in re.findall(r'[a-z0-9_#-]+', str(query or '').lower())
        if len(term) > 2
    }
    target_terms = query_terms | {
        'sidebar', 'views', 'explorer', 'navigation', 'nav', 'tab', 'tabs',
        'item', 'items', 'selected', 'active', 'hover', 'foldertree',
    }

    evidence: list[dict] = []
    for rel_path in unique_paths[:24]:
        if not rel_path.lower().endswith(('.tsx', '.jsx', '.ts', '.js', '.css', '.scss')):
            continue
        content = _safe_read_workspace_file(workspace_path, rel_path, limit=50000)
        if not content:
            continue
        lines = content.splitlines()
        matches: list[dict] = []
        for index in range(len(lines)):
            window_start = max(0, index - 2)
            window_end = min(len(lines), index + 3)
            snippet = "\n".join(lines[window_start:window_end]).strip()
            lowered = snippet.lower()
            if not any(marker in lowered for marker in ('classname', 'class=', 'bg-', 'text-', 'hover:', 'border-', 'selected', 'active')):
                continue
            classes = _extract_class_fragments(snippet)
            if not classes and 'classname' not in lowered and 'class=' not in lowered:
                continue
            score = 0.0
            if 'classname' in lowered or 'class=' in lowered:
                score += 2.0
            if classes:
                score += 1.0
                if any(any(token.startswith(prefix) for prefix in ('bg-', 'hover:bg', 'text-white', 'border-', 'shadow-[')) for token in " ".join(classes).split()):
                    score += 1.5
            if any(marker in lowered for marker in ('selected', 'active', 'hover')):
                score += 1.5
            if any(marker in lowered for marker in ('activetab ===', 'selectedfile ===', 'activesidepanel', '=== node.path')):
                score += 3.0
            if any(term in lowered for term in target_terms):
                score += 2.0
            if any(term in rel_path.lower() for term in ('view', 'sidebar', 'workspace', 'panel', 'nav', 'explorer')):
                score += 1.0
            if score < 2.5:
                continue
            matches.append(
                {
                    'path': rel_path,
                    'line_number': index + 1,
                    'snippet': snippet,
                    'classes': classes,
                    'label': _describe_ui_style_match(snippet),
                    'score': score,
                }
            )
        matches.sort(key=lambda item: (-float(item.get('score') or 0), int(item.get('line_number') or 0)))
        evidence.extend(matches[:2])

    evidence.sort(key=lambda item: (-float(item.get('score') or 0), str(item.get('path') or ''), int(item.get('line_number') or 0)))
    return evidence[:limit]


def _answer_ui_style_question_from_evidence(
    project: Project,
    content: str,
    selected_file: str,
    context_trace: dict,
) -> str:
    if not _looks_like_ui_style_question(content):
        return ''

    workspace_path = _chat_workspace_path(project)
    if not workspace_path:
        return ''

    candidate_paths = []
    if selected_file:
        candidate_paths.append(selected_file)
    candidate_paths.extend(str(item.get('path') or '') for item in (context_trace.get('files_accessed') or []))
    evidence = _extract_ui_style_evidence(workspace_path, candidate_paths, content)
    if not evidence:
        return ''

    high_confidence = [
        item for item in evidence
        if str(item.get('label') or '') in {'active navigation item', 'selected file row', 'active side panel icon'}
    ]
    if 'sidebar' in str(content or '').lower():
        if not high_confidence:
            return ''
        evidence = high_confidence[:4]
    elif high_confidence:
        evidence = high_confidence[:4]

    lines = ["I found the current sidebar-related highlight styles directly in the codebase."]
    if len(evidence) > 1:
        lines.append("There are multiple sidebar-like surfaces in this project:")

    for item in evidence:
        path = str(item.get('path') or '')
        line_number = int(item.get('line_number') or 1)
        label = str(item.get('label') or 'matching UI state')
        classes = list(item.get('classes') or [])
        if classes:
            class_text = "`, `".join(classes[:3])
            lines.append(f"- `{path}:{line_number}` controls the {label} with `{class_text}`.")
        else:
            snippet = " ".join(str(item.get('snippet') or '').split())
            lines.append(f"- `{path}:{line_number}` controls the {label}. Current code: `{snippet[:220]}`")

    lines.append("Change those current class strings to your new Tailwind colors instead of adding a separate template example.")
    return "\n".join(lines)


def _build_ui_clarification_question(
    project: Project,
    content: str,
    selected_file: str,
    context_mentions,
    context_trace: dict,
) -> str:
    lowered = str(content or '').lower()
    if not _looks_like_ui_style_question(content):
        return ''
    if selected_file:
        return ''

    normalized_mentions = _normalize_chat_mentions(context_mentions)
    if any(item.get('type') == 'file' for item in normalized_mentions):
        return ''
    if any(token in lowered for token in ('@currentfile', '@codebase', '.tsx', '.jsx', '.ts', '.js', '/', '\\')):
        return ''
    if any(token in lowered for token in ('workspace', 'file explorer', 'explorer', 'project view', 'views nav', 'navigation menu', 'blueprint')):
        return ''

    ambiguous_terms = [term for term in ('sidebar', 'panel', 'topbar', 'top bar', 'header', 'toolbar') if term in lowered]
    if not ambiguous_terms:
        return ''

    workspace_path = _chat_workspace_path(project)
    if not workspace_path:
        return ''

    candidate_paths = [str(item.get('path') or '') for item in (context_trace.get('files_accessed') or [])]
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        codebase_context = {}
    candidate_paths.extend(_ui_style_candidate_paths(codebase_context, candidate_paths))

    evidence = _extract_ui_style_evidence(workspace_path, candidate_paths, content, limit=8)
    if not evidence:
        return ''

    distinct: list[dict] = []
    seen = set()
    for item in evidence:
        key = (str(item.get('path') or ''), str(item.get('label') or ''))
        if key in seen:
            continue
        seen.add(key)
        distinct.append(item)

    if len({str(item.get('path') or '') for item in distinct}) < 2:
        return ''

    lines = ["I’m not fully sure which UI surface you mean."]
    lines.append("Which one should I help you change?")
    lines[0] = "I'm not fully sure which UI surface you mean."
    for item in distinct[:3]:
        path = str(item.get('path') or '')
        label = str(item.get('label') or 'UI state')
        lines.append(f"- `{path}`: {label}")
    lines.append("Reply with the one you mean, and I’ll point to the exact classes to edit.")
    lines = [line for line in lines if "Reply with the one you mean" not in line]
    lines.append("Reply with the one you mean, and I'll point to the exact classes to edit.")
    return "\n".join(lines)


def _classify_chat_state(
    project: Project,
    content: str,
    selected_file: str,
    context_mentions,
    context_trace: dict,
    should_apply_changes: bool,
) -> dict:
    if should_apply_changes and project.workspace_id:
        return {
            'state': CHAT_STATE_EDIT_REQUEST,
            'reason': 'The request looks like a code change and the project has an editable workspace.',
            'response_contract': (
                "When the change succeeds, summarize what changed and which files were touched. "
                "If the change fails, explain the failure plainly and keep the trace intact."
            ),
        }

    clarification_question = _build_ui_clarification_question(
        project,
        content,
        selected_file,
        context_mentions,
        context_trace,
    )
    if clarification_question:
        return {
            'state': CHAT_STATE_NEEDS_CLARIFICATION,
            'reason': 'The request names an ambiguous UI surface and needs a human follow-up before suggesting edits.',
            'response': clarification_question,
            'response_contract': (
                "Ask one short clarifying question, list the most likely UI surfaces, and wait for the user's reply."
            ),
        }

    if _looks_like_ui_redesign_request(content):
        return {
            'state': CHAT_STATE_BROAD_REDESIGN,
            'reason': 'The request is a broader UI or layout redesign and should use full grounded code context.',
            'response_contract': (
                "Response contract:\n"
                "1. Current implementation\n"
                "2. Files to edit\n"
                "3. Change plan\n"
                "4. Risks or follow-ups\n"
                "Use only retrieved evidence when describing the current layout, and do not invent panes or components."
            ),
        }

    direct_style_answer = _answer_ui_style_question_from_evidence(
        project,
        content,
        selected_file,
        context_trace,
    )
    if direct_style_answer:
        return {
            'state': CHAT_STATE_GROUNDED_ANSWER,
            'reason': 'Exact style evidence was extracted from retrieved files, so the answer can be grounded directly.',
            'response': direct_style_answer,
            'response_contract': (
                "Response contract:\n"
                "1. File to edit\n"
                "2. Exact current classes or tokens\n"
                "3. What to change"
            ),
            'mode': 'deterministic_ui_style',
        }

    return {
        'state': CHAT_STATE_GROUNDED_ANSWER,
        'reason': 'The question can be answered from retrieved workspace evidence without asking for clarification.',
        'response_contract': (
            "Response contract:\n"
            "1. Files or surfaces involved\n"
            "2. Current implementation\n"
            "3. Suggested next step\n"
            "Keep examples clearly labeled when they are not the current implementation."
        ),
    }


def _extract_agent_explicit_command(content: str) -> str:
    text = str(content or '').strip()
    if not text:
        return ''
    fenced = re.search(r"```(?:bash|sh|shell|powershell|cmd)?\s*\n(.+?)```", text, re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
        if candidate:
            return candidate
    inline = re.search(r"`([^`\n]+)`", text)
    if inline:
        candidate = inline.group(1).strip()
        if candidate:
            return candidate
    return ''


def _default_agent_terminal_command(content: str, runtime: dict, workspace_path: Path) -> str:
    lowered = str(content or '').lower()
    runtime_type = str(runtime.get('runtime_type') or '').lower()
    python_cmd = _python_executable_command()

    if any(marker in lowered for marker in ('run tests', 'run the tests', 'test suite', 'execute tests', 'pytest')):
        if runtime_type == 'node':
            return 'npm test'
        return 'pytest'

    if any(marker in lowered for marker in ('run build', 'build the project', 'production build')):
        if runtime_type == 'node':
            return 'npm run build'

    if any(marker in lowered for marker in ('makemigrations', 'make migrations')) and (workspace_path / 'manage.py').exists():
        return f'{python_cmd} manage.py makemigrations'

    if any(marker in lowered for marker in ('run migrations', 'migrate database', 'apply migrations', 'migrate')) and (workspace_path / 'manage.py').exists():
        return f'{python_cmd} manage.py migrate'

    return ''


def _plan_agent_workspace_actions(content: str, runtime: dict, *, edits_applied: bool = False, workspace_path: Path | None = None) -> dict:
    lowered = str(content or '').lower()
    explicit_command = _extract_agent_explicit_command(content)
    generated_command = ''
    if not explicit_command and workspace_path:
        generated_command = _default_agent_terminal_command(content, runtime, workspace_path)

    wants_stop = any(marker in lowered for marker in ('stop project', 'stop the project', 'stop app', 'stop the app', 'stop server', 'kill server', 'shut down'))
    wants_restart = any(marker in lowered for marker in ('restart project', 'restart the project', 'restart app', 'restart the app', 'restart server', 're-run the project', 'rerun the project'))
    wants_run = any(marker in lowered for marker in ('run project', 'run the project', 'start project', 'start the project', 'launch the project', 'launch app', 'open preview', 'boot the app'))
    wants_setup = any(marker in lowered for marker in ('setup project', 'install dependencies', 'prepare project', 'run setup', 'setup & start'))

    should_run_after_edits = edits_applied and bool(runtime.get('run_command'))
    terminal_command = explicit_command or generated_command
    run_setup = bool(runtime.get('setup_command')) and (
        wants_setup
        or ((wants_run or wants_restart or should_run_after_edits or bool(terminal_command)) and runtime.get('install_required'))
    )
    start_runtime = bool(runtime.get('run_command')) and not terminal_command and (wants_run or wants_restart or should_run_after_edits)
    stop_runtime = bool(runtime.get('run_command')) and (wants_stop or wants_restart)

    return {
        'explicit_command': explicit_command,
        'terminal_command': terminal_command,
        'run_setup': run_setup,
        'start_runtime': start_runtime,
        'stop_runtime': stop_runtime,
        'restart_runtime': wants_restart,
        'should_run_after_edits': should_run_after_edits,
        'actionable': any([run_setup, start_runtime, stop_runtime, bool(terminal_command), wants_restart]),
    }


def _trim_agent_output(output: str, limit: int = 320) -> str:
    text = str(output or '').strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _agent_project_memory_text(memory_context: dict | None) -> str:
    memory_context = memory_context or {}
    sections: list[str] = []

    blueprint_summary = str(memory_context.get('blueprint_summary') or '').strip()
    if blueprint_summary and blueprint_summary != 'No cached codebase summary yet.':
        sections.append(f"Codebase Summary:\n{blueprint_summary[:9000]}")

    semantic_summary = str(memory_context.get('semantic_summary') or '').strip()
    if semantic_summary and semantic_summary != 'No semantic matches yet.':
        sections.append(f"Relevant Semantic Recall:\n{semantic_summary[:5000]}")

    if not sections:
        return ''

    sections.append(
        "Use project memory only as background context. Do not treat earlier tasks, examples, or unrelated past chat topics as current requirements unless the user repeats them in this request."
    )
    return "\n\n".join(sections)


def _agent_execution_prompt_addendum(*, should_apply_changes: bool, selected_file: str = '') -> str:
    lines = [
        "## Workspace Agent Contract",
        "You are operating in a live project workspace with permission to inspect files, edit files, create files, replace files, search code, and run non-destructive commands.",
        "- If the user asks to build, fix, change, refactor, restyle, wire up, migrate, or otherwise modify the project, perform that work directly with tools instead of stopping after analysis.",
        "- Read and search only as much as needed to find the right files, then make the change.",
        "- Use `file_edit` for focused patches.",
        "- Use `file_write` after reading a file first when a full-file rewrite is the clearest or safest way to implement the request.",
        "- Treat prior memory as background only. Do not anchor on previous examples, stale feature ideas, or earlier chats unless the user explicitly asks for them again.",
        "- Keep the request generic to the current project. Do not inject unrelated themes or canned examples.",
        "- Before finishing, inspect the changed files and run a targeted verification command when practical.",
        "- Your final response must summarize the concrete work completed, list files changed, and mention commands run or blockers.",
    ]

    if selected_file:
        lines.append(f"- The currently open file is `{selected_file}`. Use it as a hint, not as a hard limit, if the request spans other files.")

    if should_apply_changes:
        lines.append(
            "- The current user request is an execution request. Apply the requested change in the workspace before you respond; do not answer with analysis alone unless you are blocked."
        )

    return "\n".join(lines)


def _agent_response_fallback(qr, applied_files: list[str]) -> str:
    response = str(getattr(qr, 'response', '') or '').strip()
    if response:
        return response

    tool_calls = list(getattr(qr, 'tool_calls_log', []) or [])
    files_read = list(getattr(qr, 'files_read', []) or [])
    bash_calls = [entry for entry in tool_calls if entry.get('tool') == 'bash']

    if applied_files:
        preview = ", ".join(applied_files[:6])
        if bash_calls:
            return (
                f"Applied changes to {len(applied_files)} file(s): {preview}. "
                f"Ran {len(bash_calls)} command(s) to verify or update the workspace."
            )
        return f"Applied changes to {len(applied_files)} file(s): {preview}."

    if files_read or tool_calls:
        inspected = f"inspected {len(files_read)} file(s)" if files_read else f"used {len(tool_calls)} tool call(s)"
        tools_used = ", ".join(
            dict.fromkeys(str(entry.get('tool') or '') for entry in tool_calls if entry.get('tool'))
        )
        if tools_used:
            return f"The agent {inspected} using {tools_used}, but no code changes were applied."
        return f"The agent {inspected}, but no code changes were applied."

    return "The agent did not return a final summary."


def _wait_for_sandbox_process(sandbox, process_id: str, *, timeout_seconds: float = 240.0, poll_interval: float = 0.35) -> tuple[dict, str]:
    deadline = time.time() + timeout_seconds
    chunks: list[str] = []
    while time.time() < deadline:
        chunks.extend(sandbox.get_output(process_id))
        status = sandbox.get_status(process_id)
        if not status.get('running'):
            chunks.extend(sandbox.get_output(process_id))
            return sandbox.get_status(process_id), ''.join(chunks)
        time.sleep(poll_interval)
    chunks.extend(sandbox.get_output(process_id))
    return sandbox.get_status(process_id), ''.join(chunks)


def _handle_agent_chat_request(
    project: Project,
    content: str,
    *,
    selected_file: str = '',
    selected_content: str = '',
    attachments: list[dict] | None = None,
    session_id: str = '',
    should_apply_changes: bool = False,
    context_trace: dict | None = None,
    memory_context: dict | None = None,
    checkpoint: dict | None = None,
) -> dict:
    from pathlib import Path as _Path
    from sandbox.executor import sandbox

    context_trace = dict(context_trace or {})
    memory_context = memory_context or {}
    attachments = list(attachments or [])
    request_text = _chat_request_text(content, attachments)
    prompt_text = _chat_request_text(content, attachments, include_attachment_inventory=True)
    workspace_path = _chat_workspace_path(project)
    if not project.workspace_id or not workspace_path:
        return {
            'handled': True,
            'assistant_message': (
                "Agent mode needs a connected workspace before it can edit files or run sandbox commands."
            ),
            'assistant_trace': {
                'approach': 'Agent mode was requested, but this project has no active workspace attached.',
                'chat_state': CHAT_STATE_AGENT_REQUEST,
                'chat_mode': CHAT_MODE_AGENT,
                'state_reason': 'Agent mode requires an editable workspace.',
                'session_id': session_id,
                'context_mentions': context_trace.get('context_mentions') or [],
                'context_sources': context_trace.get('context_sources') or [],
                'files_accessed': context_trace.get('files_accessed') or [],
                'commands_ran': [],
                'workspace_actions': [],
                'applied_files': [],
            },
            'applied_changes': None,
            'workspace_actions': [],
        }

    # ── NEW: Use QueryEngine for tool-calling agent loop ──────────
    try:
        from agents.compaction import ContextCompactor
        from agents.coordinator import Coordinator
        from agents.prompts import PromptBuilder
        from agents.query_engine import QueryEngine
        from agents.tools.registry import ToolRegistry

        ai_config = _project_ai_config(project)
        registry = ToolRegistry.default_registry()
        compactor = ContextCompactor()
        prompt_builder = PromptBuilder()

        # Build conversation history from session
        conversation_history = []
        try:
            _grouped, _ = _group_project_chat_sessions(project)
            recent = _grouped.get(session_id, [])[-10:]
            for msg in recent:
                role = msg.get('role', 'user') if isinstance(msg, dict) else getattr(msg, 'role', 'user')
                msg_content = msg.get('content', '') if isinstance(msg, dict) else getattr(msg, 'content', '')
                msg_attachments = _chat_message_attachments(msg if isinstance(msg, dict) else {'metadata': getattr(msg, 'metadata', {})})
                gemini_role = 'model' if role == 'assistant' else 'user'
                conversation_history.append(
                    {
                        'role': gemini_role,
                        'content': _chat_request_text(str(msg_content), msg_attachments, include_attachment_inventory=True),
                    }
                )
        except Exception:
            logger.debug("Could not load chat history for session %s", session_id)

        # Build enhanced system prompt
        project_memory_text = _agent_project_memory_text(memory_context)
        project_instructions_text = ''
        try:
            project_instructions_text = _read_project_instructions(project, workspace_path)
        except Exception:
            pass

        customization_ctx = ''
        try:
            from agents.project_customization import build_project_customization_summary
            customization_ctx = build_project_customization_summary(workspace_path)
        except Exception:
            pass

        system_prompt = prompt_builder.build_system_prompt(
            workspace_path=workspace_path,
            tools=registry.all_tools(),
            project_memory=project_memory_text,
            project_instructions=project_instructions_text,
            customization_context=customization_ctx,
        )
        system_prompt += "\n\n" + _agent_execution_prompt_addendum(
            should_apply_changes=should_apply_changes,
            selected_file=selected_file,
        )

        # Add file context if a file is selected
        if selected_file:
            file_context = f"\n\n## Active File Context\nThe user has file `{selected_file}` open."
            if selected_content:
                file_context += f"\nContent:\n```\n{selected_content[:4000]}\n```"
            system_prompt += file_context

        # Collect events for the trace
        tool_events: list[dict] = []

        def on_tool_start(name, args):
            tool_events.append({'type': 'tool_start', 'tool': name, 'args_preview': {k: str(v)[:100] for k, v in args.items()}})

        def on_tool_end(name, result):
            tool_events.append({'type': 'tool_end', 'tool': name, 'success': result.success, 'preview': (result.output or '')[:200]})

        engine = QueryEngine(
            tool_registry=registry,
            prompt_builder=prompt_builder,
            compactor=compactor,
            ai_config=ai_config,
            workspace_id=project.workspace_id,
            workspace_path=workspace_path,
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
        )

        qr = engine.run(
            user_message=prompt_text,
            attachments=attachments,
            conversation_history=conversation_history,
            system_prompt=system_prompt,
            max_turns=25,
        )

        # Build response
        applied_files = list(qr.files_modified)
        workspace_actions = []
        for tc in qr.tool_calls_log:
            workspace_actions.append({
                'type': tc.get('tool', 'tool_call'),
                'status': 'completed' if tc.get('success') else 'failed',
                'command': str(tc.get('args', {}).get('command', ''))[:200] if tc.get('tool') == 'bash' else '',
                'detail': tc.get('output_preview', '')[:200],
            })

        assistant_trace = {
            'approach': f"Agent used {len(qr.tool_calls_log)} tool calls across {qr.turns_used} turns. {'Context was auto-compacted.' if qr.compacted else ''}",
            'chat_state': CHAT_STATE_AGENT_REQUEST,
            'chat_mode': CHAT_MODE_AGENT,
            'state_reason': 'Agentic tool-calling loop completed.',
            'session_id': session_id,
            'context_mentions': context_trace.get('context_mentions') or [],
            'context_sources': context_trace.get('context_sources') or [],
            'files_accessed': [{'path': p, 'reason': 'Read by agent'} for p in qr.files_read[:12]],
            'commands_ran': [
                {'command': tc.get('args', {}).get('command', tc.get('tool', '')), 'status': 'passed' if tc.get('success') else 'failed', 'detail': tc.get('output_preview', '')[:200]}
                for tc in qr.tool_calls_log if tc.get('tool') == 'bash'
            ],
            'workspace_actions': workspace_actions,
            'applied_files': applied_files,
            'tool_events': tool_events[-20:],
            'turns_used': qr.turns_used,
            'compacted': qr.compacted,
            'duration_ms': qr.total_duration_ms,
            'semantic_hits': [
                {'path': item.get('file_path'), 'symbol': item.get('symbol')}
                for item in (memory_context.get('semantic_hits') or [])[:8]
            ],
        }

        applied_changes = None
        if applied_files:
            changeset = _record_chat_changes(
                project,
                content,
                workspace_path,
                snapshot_previous_contents(str(project.id), str((checkpoint or {}).get('id') or ''), applied_files),
                applied_files,
                ai_review=_chat_checkpoint_review_payload(
                    checkpoint,
                    source='chat_agent',
                    chat_mode=CHAT_MODE_AGENT,
                    undo_label='Undo',
                ),
            )
            if changeset:
                applied_changes = {
                    'applied_files': applied_files,
                    'count': len(applied_files),
                    'changeset_id': str(changeset.id),
                    'undo': _chat_changeset_trace_metadata(changeset).get('undo'),
                }
                assistant_trace.update(_chat_changeset_trace_metadata(changeset))
                try:
                    _update_project_memory(project, workspace_path, content, applied_files, [])
                except Exception:
                    logger.exception("Failed to update project memory for agent changes in project %s", project.id)
                try:
                    index_semantic_memory(project, workspace_path, changed_paths=applied_files)
                except Exception:
                    logger.exception("Failed to re-index semantic memory for project %s", project.id)
                try:
                    record_episode(
                        project=project,
                        memory_type='implementation',
                        title='Workspace agent execution',
                        summary=f"Agent mode applied changes for '{request_text[:120]}'. Files: {', '.join(applied_files)}.",
                        related_files=applied_files,
                        metadata={'source': 'chat_agent', 'workspace_actions': workspace_actions},
                    )
                    upsert_working_memory(
                        project,
                        'implementation',
                        (
                            f"Latest implementation request: {request_text[:240]}\n"
                            f"Files touched: {', '.join(applied_files)}\n"
                            "Validation summary:\nNo structured validation was recorded for this direct agent tool execution.\n"
                            "Reviewer summary: No structured review was recorded for this direct agent tool execution."
                        ),
                        {'latest_request': request_text[:240], 'files': applied_files, 'source': 'chat_agent'},
                    )
                except Exception:
                    logger.exception("Failed to persist memory updates for agent changes in project %s", project.id)
        assistant_message_override = ''

        if should_apply_changes and not applied_files:
            try:
                fallback_changes = apply_chat_changes(
                    project,
                    request_text,
                    selected_file=selected_file,
                    selected_content=selected_content,
                    request_attachments=attachments,
                    checkpoint=checkpoint,
                    chat_mode=CHAT_MODE_AGENT,
                    changeset_source='chat_agent',
                )
                fallback_applied_files = list(fallback_changes.get('applied_files') or [])
                if fallback_applied_files:
                    applied_files = fallback_applied_files
                    applied_changes = fallback_changes
                    fallback_trace = _build_chat_trace_from_changes(fallback_changes, context_trace, memory_context)
                    workspace_actions.append({
                        'type': 'implementation_fallback',
                        'status': 'completed',
                        'detail': 'The tool-calling loop inspected the workspace but made no edits, so the structured implementation pipeline applied the requested code changes.',
                    })
                    assistant_trace.update({
                        'approach': 'Agent mode inspected the workspace with tools first, then completed the edit through the structured implementation pipeline because the tool loop returned without file changes.',
                        'state_reason': 'Tool-calling loop completed without file edits; implementation fallback applied.',
                        'files_accessed': [
                            *list(assistant_trace.get('files_accessed') or []),
                            *list(fallback_trace.get('files_accessed') or []),
                        ][:24],
                        'commands_ran': list(fallback_trace.get('commands_ran') or []),
                        'workspace_actions': workspace_actions,
                        'applied_files': applied_files,
                        'plan': fallback_trace.get('plan') or {},
                        'review': fallback_trace.get('review') or {},
                        'semantic_hits': list(fallback_trace.get('semantic_hits') or assistant_trace.get('semantic_hits') or []),
                    })
                    assistant_trace.update({
                        key: value
                        for key, value in fallback_trace.items()
                        if key in {'changeset_id', 'undo', 'undo_available'}
                    })
                    assistant_message_override = (
                        f"Applied the requested update to {len(applied_files)} file(s): "
                        f"{', '.join(applied_files[:6])}."
                    )
            except Exception as fallback_exc:
                logger.exception("Agent mode implementation fallback failed for project %s", project.id)
                workspace_actions.append({
                    'type': 'implementation_fallback',
                    'status': 'failed',
                    'detail': str(fallback_exc)[:220],
                })
                assistant_trace['state_reason'] = 'Tool-calling loop completed without file edits, and the implementation fallback also failed.'
                assistant_trace['fallback_error'] = str(fallback_exc)
                assistant_trace['workspace_actions'] = workspace_actions
        elif checkpoint and not applied_files:
            delete_workspace_checkpoint(str(project.id), str(checkpoint.get('id') or ''))

        # After edits, also handle sandbox actions (setup + runtime)
        runtime = detect_runtime(workspace_path)
        if applied_files:
            action_plan = _plan_agent_workspace_actions(
                request_text, runtime, edits_applied=True, workspace_path=workspace_path,
            )
            runtime_pid = runtime_process_id(project.workspace_id)
            setup_pid = setup_process_id(project.workspace_id)

            if action_plan.get('run_setup') and runtime.get('setup_command'):
                sandbox.run_command(setup_pid, str(runtime.get('setup_command')), str(workspace_path), kind='setup')
                setup_status, setup_output = _wait_for_sandbox_process(sandbox, setup_pid)
                setup_success = int(setup_status.get('returncode') or 0) == 0
                workspace_actions.append({
                    'type': 'setup',
                    'status': 'completed' if setup_success else 'failed',
                    'command': runtime.get('setup_command'),
                    'detail': _trim_agent_output(setup_output) or ('Setup completed.' if setup_success else 'Setup failed.'),
                })

            if action_plan.get('start_runtime') and runtime.get('run_command'):
                sandbox.run_command(runtime_pid, str(runtime.get('run_command')), str(workspace_path), kind='runtime', preview_url=runtime.get('preview_url'))
                runtime_payload = _runtime_response_payload(runtime, runtime_pid, sandbox, wait_for_preview=True)
                runtime_ready = bool(runtime_payload.get('ready'))
                workspace_actions.append({
                    'type': 'runtime_start',
                    'status': 'completed' if runtime_ready else 'running',
                    'command': runtime.get('run_command'),
                    'preview_url': runtime_payload.get('preview_url'),
                    'detail': 'Preview is ready.' if runtime_ready else 'Runtime started.',
                })

            assistant_trace['workspace_actions'] = workspace_actions

        return {
            'handled': True,
            'assistant_message': assistant_message_override or _agent_response_fallback(qr, applied_files),
            'assistant_trace': assistant_trace,
            'applied_changes': applied_changes,
            'workspace_actions': workspace_actions,
        }

    except Exception as exc:
        logger.exception("QueryEngine agent mode failed for project %s — falling back", project.id)

        # ── FALLBACK: Original agent handler for when engine fails ──
        runtime = detect_runtime(workspace_path)
        applied_changes = None
        applied_files_fallback: list[str] = []
        commands_ran_fallback = list(context_trace.get('commands_ran') or [])
        workspace_actions_fallback: list[dict[str, Any]] = []
        assistant_trace_fallback = {
            'approach': f'Agent mode QueryEngine failed ({exc}), fell back to direct handler.',
            'chat_state': CHAT_STATE_AGENT_REQUEST,
            'chat_mode': CHAT_MODE_AGENT,
            'state_reason': 'Agent mode fallback.',
            'session_id': session_id,
            'context_mentions': context_trace.get('context_mentions') or [],
            'context_sources': context_trace.get('context_sources') or [],
            'files_accessed': context_trace.get('files_accessed') or [],
            'commands_ran': commands_ran_fallback,
            'workspace_actions': workspace_actions_fallback,
            'applied_files': applied_files_fallback,
            'error': str(exc),
        }

        if should_apply_changes:
            try:
                applied_changes = apply_chat_changes(
                    project,
                    request_text,
                    selected_file=selected_file,
                    selected_content=selected_content,
                    request_attachments=attachments,
                    checkpoint=checkpoint,
                    chat_mode=CHAT_MODE_AGENT,
                    changeset_source='chat_agent',
                )
                applied_files_fallback = list(applied_changes.get('applied_files') or [])
                assistant_trace_fallback['applied_files'] = applied_files_fallback
                assistant_trace_fallback.update({
                    key: value
                    for key, value in applied_changes.items()
                    if key in {'changeset_id', 'undo'}
                })
                assistant_trace_fallback['undo_available'] = bool((applied_changes.get('undo') or {}).get('available'))
            except Exception as apply_exc:
                assistant_trace_fallback['error'] = str(apply_exc)
        elif checkpoint:
            delete_workspace_checkpoint(str(project.id), str(checkpoint.get('id') or ''))

        action_plan = _plan_agent_workspace_actions(request_text, runtime, edits_applied=bool(applied_files_fallback), workspace_path=workspace_path)
        if not action_plan.get('actionable') and not applied_files_fallback:
            if checkpoint and not applied_files_fallback:
                delete_workspace_checkpoint(str(project.id), str(checkpoint.get('id') or ''))
            return {'handled': False, 'assistant_message': '', 'assistant_trace': assistant_trace_fallback, 'applied_changes': None, 'workspace_actions': []}

        summary_parts = []
        if applied_files_fallback:
            summary_parts.append(f"Updated {len(applied_files_fallback)} file(s): {', '.join(applied_files_fallback[:6])}.")
        summary_parts.append(f"(Note: the advanced agent engine encountered an error: {exc})")

        return {
            'handled': True,
            'assistant_message': " ".join(summary_parts) or f"Agent mode encountered an issue: {exc}",
            'assistant_trace': assistant_trace_fallback,
            'applied_changes': applied_changes,
            'workspace_actions': workspace_actions_fallback,
        }


def _build_chat_evidence_index(context_trace: dict, limit: int = 12) -> str:
    evidence_index_lines = []
    for item in (context_trace.get('files_accessed') or [])[:limit]:
        path = str(item.get('path') or '').strip()
        if not path:
            continue
        reason = str(item.get('reason') or 'Retrieved as relevant evidence for this question.').strip()
        evidence_index_lines.append(f"- {path}: {reason}")
    return "\n".join(evidence_index_lines) or "- No explicit file evidence was captured for this turn."


def _build_chat_llm_prompt(
    project: Project,
    content: str,
    attachments: list[dict] | None,
    selected_file: str,
    selected_content: str,
    session_id: str,
    context_trace: dict,
    memory_context: dict,
    resolved_context_text: str,
    chat_mode: str | None,
    chat_state: str,
    response_contract: str,
) -> tuple[str, str]:
    blueprint = project.blueprint or {}
    arch = json.dumps(blueprint.get('architecture_overview', ''))[:800]
    tech = ", ".join(project.tech_stack) if project.tech_stack else "Unknown"

    grouped_sessions, _ = _group_project_chat_sessions(project)
    recent = grouped_sessions.get(session_id, [])[-10:]
    history_text = "\n".join(
        [
            f"{message['role']}: {_chat_request_text(message.get('content', ''), _chat_message_attachments(message), include_attachment_inventory=True)}"
            for message in recent
        ]
    )

    file_context = "No file selected."
    if selected_file:
        file_context = f"Active file: {selected_file}\n"
        if selected_content:
            file_context += selected_content[:4000]
        elif project.workspace_id:
            try:
                file_context += workspace_manager.read_file(project.workspace_id, selected_file)[:4000]
            except Exception:
                file_context += "(Unable to read file content.)"
    if resolved_context_text:
        file_context += f"\n\nExplicit context mentions:\n{resolved_context_text[:48000]}"
    attachment_context = describe_image_attachments(attachments) or "No image attachments were supplied for this turn."

    evidence_index = _build_chat_evidence_index(context_trace)
    system_instruction = f"""You are the DevHub AI assistant for the project "{project.name}".
Tech Stack: {tech}
Architecture: {arch}
Working Memory: {memory_context.get('working_summary', '')[:2000]}
Cached Codebase Summary: {memory_context.get('blueprint_summary', '')[:3000]}
Episodic Memory: {memory_context.get('episodic_summary', '')[:1200]}

Help the developer understand, plan and implement features, debug issues, and reason about the current code.
Default to depth, not brevity: unless the user explicitly asks for a short or compact answer, give a thorough answer.
For implementation or architecture questions, explain the real code path step by step using the retrieved evidence, not generic possibilities.
When the question is system-level or end-to-end, cover all relevant layers that appear in context, including backend and frontend pieces when both are involved.
Prefer sections like overview, backend, frontend, flow, and files to change when that helps clarity.
When @codebase is mentioned, provide thorough, evidence-based answers citing specific file paths, function names, and code patterns you can see in the context.
When relevant, use the active file context and keep answers action-oriented and detailed.
If the current user turn includes attached images, treat them as first-class context and incorporate what you can directly observe from them.
For codebase questions, prefer the exact implementation over examples:
- name the real file path(s) first,
- quote the current className, function, route, or variable that controls the behavior when it is present in context,
- do not invent alternative code unless you clearly label it as an example,
- if the evidence is incomplete, say what is confirmed versus what is inferred.
If the retrieved evidence shows a concrete implementation that matches the question, answer from that implementation first and do not hedge with phrases like "might be in" or "it will look something like".
Only mention multiple candidate files when the evidence truly shows multiple distinct implementations that fit the question.
For UI or styling questions, identify the exact component and the current classes or style tokens that control the color, spacing, or state change before suggesting edits, and quote the current class string when available.
For broader UI/layout redesign requests, first describe the current layout using only retrieved evidence, then name the exact file(s) to edit, and do not invent panes, panels, or components that are not present in the code you were given.
DevHub can inspect the current workspace, and in Edit or Agent mode it can also modify files and run sandboxed project commands.
Never say that you lack access to the local codebase or cannot make edits; instead respect the current mode:
- Ask mode: answer only and suggest switching modes if the user wants action.
- Edit mode: treat the request as an implementation request against the actual codebase.
- Agent mode: assume DevHub may edit files and drive the sandboxed runtime when the request is actionable.

Current chat mode: {chat_mode or 'auto'}
Current chat state: {chat_state}
{response_contract}"""
    prompt = (
        f"Current chat mode: {chat_mode or 'auto'}\n"
        f"Current chat state: {chat_state}\n"
        f"{response_contract}\n\n"
        f"Attached images for this turn:\n{attachment_context}\n\n"
        f"Retrieved evidence index:\n{evidence_index}\n\n"
        f"Chat history:\n{history_text}\n\n"
        f"Semantic recall:\n{memory_context.get('semantic_summary', 'No semantic recall.')}\n\n"
        f"Active workspace context:\n{file_context}\n\nUser: {content}"
    )
    return system_instruction, prompt


def _query_prefers_full_primary_files(content: str) -> bool:
    lowered = str(content or '').lower()
    if not lowered:
        return False
    if _looks_like_ui_style_question(content):
        return True
    if _looks_like_ui_redesign_request(content):
        return True
    if _looks_like_edit_request(content):
        return True
    markers = (
        'how do i change', 'how to change', 'where do i change', 'which file',
        'where is', 'where are', 'how do i update', 'how to update',
        'how do i modify', 'how to modify', 'how do i edit', 'how to edit',
        'how do i fix', 'how to fix', 'how does this work', 'trace this',
        'follow this', 'walk me through',
    )
    return any(marker in lowered for marker in markers)


def _chat_primary_file_paths(
    retrieval: dict,
    explicit_paths: list[str] | None,
    query: str,
    max_primary: int = 2,
) -> set[str]:
    primary: list[str] = []
    seen: set[str] = set()
    for path in explicit_paths or []:
        normalized = str(path or '').replace('\\', '/').strip('/')
        if normalized and normalized not in seen:
            seen.add(normalized)
            primary.append(normalized)
    if _query_prefers_full_primary_files(query):
        for item in retrieval.get('files', []):
            path = str(item.get('path') or '').replace('\\', '/').strip('/')
            if not path or path in seen:
                continue
            seen.add(path)
            primary.append(path)
            if len(primary) >= max_primary:
                break
    return set(primary[:max_primary])


def _ui_style_candidate_paths(cache: dict, existing_paths: list[str] | None = None, max_extra: int = 6) -> list[str]:
    seen = {
        str(path or '').replace('\\', '/').strip('/')
        for path in (existing_paths or [])
        if str(path or '').strip()
    }
    extras: list[str] = []
    pool: list[dict] = []
    for item in list(cache.get('all_file_summaries') or []) + list(cache.get('important_files') or []):
        if not isinstance(item, dict):
            continue
        pool.append(item)
        if len(pool) >= 240:
            break
    for item in pool:
        path = str(item.get('path') or '').replace('\\', '/').strip('/')
        lowered = path.lower()
        if not path or path in seen:
            continue
        if not lowered.endswith(('.tsx', '.jsx', '.ts', '.js')):
            continue
        if '/frontend/' not in f'/{lowered}':
            continue
        if not any(token in lowered for token in ('view', 'workspace', 'panel', 'layout', 'header', 'nav', 'sidebar')):
            continue
        seen.add(path)
        extras.append(path)
        if len(extras) >= max_extra:
            break
    return extras


def _resolve_chat_context(
    project: Project,
    content: str,
    selected_file: str = '',
    selected_content: str = '',
    context_mentions=None,
    session_id: str = '',
) -> tuple[str, dict]:
    workspace_path = _chat_workspace_path(project)
    codebase_context = {}
    runtime = {}
    project_instructions = ''
    if workspace_path:
        try:
            codebase_context = build_blueprint_context(project, workspace_path)
        except Exception:
            logger.exception("Failed to build codebase context for chat in project %s", project.id)
        try:
            runtime = detect_runtime(workspace_path)
        except Exception:
            runtime = {}
        try:
            project_instructions = _read_project_instructions(project, workspace_path)
        except Exception:
            project_instructions = ''

    mentions = _dedupe_chat_mentions(
        _normalize_chat_mentions(context_mentions),
        _infer_inline_chat_mentions(content),
    )

    trace = {
        'approach': 'Resolved explicit context mentions, loaded relevant project context, and answered against the current workspace.',
        'context_mentions': mentions,
        'files_accessed': [],
        'context_sources': [],
        'commands_ran': [],
    }
    context_blocks = []
    explicit_file_mentions: list[str] = []
    broad_listing = _query_requests_broad_listing(content)
    system_explanation = _query_requests_system_explanation(content)
    retrieval_max_files = 14 if broad_listing else (10 if system_explanation else 6)
    retrieval_file_limit = 2600 if broad_listing else (2800 if system_explanation else 2200)
    if system_explanation:
        trace['approach'] = 'Resolved explicit context mentions, pulled both architectural context and concrete file evidence, and answered against the current workspace.'

    for mention in mentions:
        mention_type = mention.get('type')
        value = str(mention.get('value') or '')
        lowered = value.lower()
        if mention_type == 'special' and lowered == 'codebase':
            summary = str((codebase_context or {}).get('compact_summary') or '')
            retrieval = retrieve_relevant_files(
                codebase_context or {},
                workspace_path,
                content,
                section_key='knowledge',
                max_files=16 if broad_listing else 8,
                include_neighbors=True,
            ) if workspace_path and codebase_context else {'files': [], 'trace': []}
            codebase_parts = []
            if summary:
                codebase_parts.append(f"=== PROJECT OVERVIEW ===\n{summary[:4000]}")
            if retrieval.get('files') and workspace_path:
                codebase_parts.append("\n=== PLANNED READING LIST ===")
                chars_used = 0
                max_chars = 32000 if system_explanation else 22000
                files_included = 0
                full_primary_paths = _chat_primary_file_paths(retrieval, explicit_file_mentions, content)
                for file_item in retrieval.get('files', []):
                    if chars_used >= max_chars:
                        break
                    rel_path = str(file_item.get('path') or '')
                    if not rel_path:
                        continue
                    use_full_content = rel_path in full_primary_paths
                    file_content = read_query_relevant_file_content(
                        workspace_path,
                        rel_path,
                        query=content,
                        limit=12000 if use_full_content else (3200 if not broad_listing else 2600),
                        force_full=use_full_content,
                    )
                    if not file_content:
                        continue
                    file_summary = file_item.get('summary') or file_item.get('purpose') or ''
                    block_kind = "FULL FILE" if use_full_content else "FILE"
                    block = f"\n--- {block_kind}: {rel_path} ---\nSummary: {file_summary}\nContent:\n{file_content}\n--- END {block_kind} ---"
                    codebase_parts.append(block)
                    chars_used += len(block)
                    files_included += 1
                for item in retrieval.get('trace', [])[:20]:
                    item_path = str(item.get('path') or '')
                    trace['files_accessed'].append({
                        'path': item_path,
                        'source': item.get('source') or 'retrieval',
                        'mode': 'full' if item_path in full_primary_paths else 'chunked',
                        'reason': item.get('reason') or 'Selected by codebase retrieval.',
                    })
            if codebase_parts:
                context_blocks.append(f"@codebase\n" + "\n".join(codebase_parts))
                trace['context_sources'].append({'label': '@codebase', 'detail': f'Used manifest-backed retrieval plus contents of {files_included} planned files.'})
        elif mention_type == 'special' and lowered == 'currentfile':
            if selected_file:
                explicit_file_mentions.append(selected_file)
                if selected_content:
                    context_blocks.append(f"@currentFile `{selected_file}`\n{selected_content}")
                    trace['files_accessed'].append({'path': selected_file, 'source': 'current_file', 'reason': 'Explicit current file context requested.'})
                else:
                    current_block, current_summary = _lazy_chat_file_context(workspace_path, selected_file, codebase_context, limit=5000)
                    if current_block:
                        context_blocks.append(f"@currentFile\n{current_block}")
                        trace['files_accessed'].append({
                            'path': selected_file,
                            'source': 'lazy_file',
                            'reason': 'Explicit current file context requested, loaded directly from the workspace on demand.',
                        })
                        if current_summary and not _cached_file_summary(codebase_context, selected_file):
                            trace['context_sources'].append({'label': '@currentFile', 'detail': 'Loaded a file on demand even though it was not part of the cached blueprint index.'})
        elif mention_type == 'special' and lowered == 'readme':
            if workspace_path:
                doc_files = ['README.md', 'CONTRIBUTING.md', 'SECURITY.md', 'VISION.md', 'AGENTS.md']
                doc_chunks = []
                for rel_path in doc_files:
                    excerpt = _safe_read_workspace_file(workspace_path, rel_path, limit=2500)
                    if not excerpt:
                        continue
                    doc_chunks.append(f"## {rel_path}\n{excerpt}")
                    trace['files_accessed'].append({'path': rel_path, 'source': 'docs', 'reason': 'Explicit root documentation context requested.'})
                if doc_chunks:
                    context_blocks.append("@readme\n" + "\n\n".join(doc_chunks))
                    trace['context_sources'].append({'label': '@readme', 'detail': 'Loaded root documentation and contributor guidance files.'})
        elif mention_type == 'special' and lowered == 'rules':
            if project_instructions:
                context_blocks.append(f"@rules\n{project_instructions[:4000]}")
                trace['context_sources'].append({'label': '@rules', 'detail': 'Loaded workspace rules and project instruction files.'})
        elif mention_type == 'special' and lowered == 'conversation':
            grouped_sessions, _ = _group_project_chat_sessions(project)
            recent = [
                {'role': item.get('role'), 'content': item.get('content')}
                for item in grouped_sessions.get(session_id or LEGACY_CHAT_SESSION_ID, [])[-8:]
            ]
            if recent:
                history_text = "\n".join(f"{item['role']}: {item['content'][:500]}" for item in recent)
                context_blocks.append(f"@conversation\n{history_text}")
                trace['context_sources'].append({'label': '@conversation', 'detail': 'Loaded recent chat history from the active session.'})
        elif mention_type == 'special' and lowered == 'terminal':
            if runtime:
                context_blocks.append(f"@terminal\n{json.dumps(runtime, indent=2)[:3000]}")
                trace['context_sources'].append({'label': '@terminal', 'detail': 'Loaded detected runtime command, preview status, and process state.'})
        elif mention_type == 'folder':
            folder_block, evidence = _folder_context_block(codebase_context, value)
            if folder_block:
                context_blocks.append(f"@{value}\n{folder_block}")
                trace['files_accessed'].extend(evidence)
        elif mention_type == 'file' and workspace_path:
            explicit_file_mentions.append(value)
            file_block, file_summary = _lazy_chat_file_context(workspace_path, value, codebase_context, limit=5000)
            if file_block:
                context_blocks.append(f"@{value}\n{file_block}")
                trace['files_accessed'].append({
                    'path': value,
                    'source': 'lazy_file',
                    'reason': 'Explicit file mention requested and loaded directly from the workspace on demand.',
                })
                if file_summary and not _cached_file_summary(codebase_context, value):
                    trace['context_sources'].append({'label': f'@{value}', 'detail': 'Loaded a skipped or uncached file lazily from disk for this chat turn.'})

    if workspace_path and codebase_context and not any(block.startswith('@codebase') for block in context_blocks):
        if _looks_like_ui_style_question(content) or _looks_like_ui_redesign_request(content):
            for rel_path in _ui_style_candidate_paths(codebase_context, explicit_file_mentions):
                if rel_path not in explicit_file_mentions:
                    explicit_file_mentions.append(rel_path)
        retrieval = retrieve_relevant_files(
            codebase_context,
            workspace_path,
            content,
            explicit_paths=explicit_file_mentions,
            max_files=retrieval_max_files,
            include_neighbors=True,
        )
        if _looks_like_ui_style_question(content):
            existing_ui_paths = [str(item.get('path') or '') for item in trace['files_accessed']]
            for rel_path in _ui_style_candidate_paths(codebase_context, existing_ui_paths):
                trace['files_accessed'].append({
                    'path': rel_path,
                    'source': 'ui_candidate',
                    'mode': 'candidate',
                    'reason': 'Added as a likely UI surface for a styling question.',
                })
        planned_blocks = []
        full_primary_paths = _chat_primary_file_paths(retrieval, explicit_file_mentions, content)
        for item in retrieval.get('files', [])[:retrieval_max_files]:
            rel_path = str(item.get('path') or '')
            if not rel_path:
                continue
            use_full_content = rel_path in full_primary_paths
            file_content = read_query_relevant_file_content(
                workspace_path,
                rel_path,
                query=content,
                limit=12000 if use_full_content else retrieval_file_limit,
                force_full=use_full_content,
            )
            if not file_content:
                continue
            planned_blocks.append(
                f"--- {'FULL FILE' if use_full_content else 'FILE'}: {rel_path} ---\n"
                f"Summary: {item.get('summary') or item.get('purpose') or 'No summary available.'}\n"
                f"Content:\n{file_content}\n"
                f"--- END {'FULL FILE' if use_full_content else 'FILE'} ---"
            )
        if planned_blocks:
            context_blocks.append("@codebase-planned\n" + "\n\n".join(planned_blocks))
            trace['context_sources'].append({'label': '@codebase-planned', 'detail': f"Planned and loaded {len(planned_blocks)} files based on the current question before answering."})
            existing_paths = {str(item.get('path') or '') for item in trace['files_accessed']}
            for item in retrieval.get('trace', [])[:16]:
                rel_path = str(item.get('path') or '')
                if rel_path in existing_paths:
                    continue
                trace['files_accessed'].append({
                    'path': rel_path,
                    'source': item.get('source') or 'retrieval',
                    'mode': 'full' if rel_path in full_primary_paths else 'chunked',
                    'reason': item.get('reason') or 'Selected by manifest-backed retrieval for this chat turn.',
                })

    return "\n\n".join(block for block in context_blocks if block).strip(), trace


def _build_chat_trace_from_changes(
    applied_changes: dict | None,
    context_trace: dict | None,
    memory_context: dict | None,
) -> dict:
    applied_changes = applied_changes or {}
    context_trace = dict(context_trace or {})
    memory_context = memory_context or {}
    commands_ran = list(context_trace.get('commands_ran') or [])
    for result in applied_changes.get('validation_results') or []:
        commands_ran.append({
            'command': result.get('command'),
            'status': 'passed' if result.get('success') else 'failed',
            'detail': str(result.get('stderr') or result.get('stdout') or '')[:280],
        })

    trace = {
        'approach': context_trace.get('approach') or 'Applied a workspace change request and validated the result.',
        'context_mentions': context_trace.get('context_mentions') or [],
        'context_sources': context_trace.get('context_sources') or [],
        'files_accessed': [
            *list(context_trace.get('files_accessed') or []),
            *[
                {'path': path, 'source': 'implementation_context', 'reason': 'Used as code context while preparing the edit plan.'}
                for path in (applied_changes.get('context_files') or [])[:12]
            ],
        ],
        'commands_ran': commands_ran,
        'plan': applied_changes.get('plan') or {},
        'applied_files': applied_changes.get('applied_files') or [],
        'review': applied_changes.get('review') or {},
        'semantic_hits': [
            {
                'path': item.get('file_path'),
                'symbol': item.get('symbol'),
            }
            for item in (memory_context.get('semantic_hits') or [])[:8]
        ],
    }
    if applied_changes.get('changeset_id'):
        trace['changeset_id'] = applied_changes.get('changeset_id')
    if isinstance(applied_changes.get('undo'), dict):
        trace['undo'] = applied_changes.get('undo')
        trace['undo_available'] = bool((applied_changes.get('undo') or {}).get('available'))
    return trace


def _record_chat_changes(
    project: Project,
    request_text: str,
    workspace_path: Path,
    previous_contents: dict | None,
    applied_files: list[str],
    *,
    ai_review: dict | None = None,
):
    if not applied_files:
        return None

    before_contents = dict(previous_contents or {})
    checkpoint_review = dict(ai_review or {})
    checkpoint_id = str(((checkpoint_review.get('checkpoint') or {}).get('id')) or '').strip()
    if checkpoint_id:
        checkpoint_contents = snapshot_previous_contents(str(project.id), checkpoint_id, applied_files)
        for rel_path, content in checkpoint_contents.items():
            before_contents.setdefault(rel_path, content)

    changeset = Changeset.objects.create(
        project=project,
        title=(request_text[:252] + '...') if len(request_text) > 255 else request_text,
        description=request_text,
        status='approved',
        ai_review=checkpoint_review or {'source': 'chat'},
    )

    for rel_path in applied_files:
        new_path = workspace_path / rel_path
        before = before_contents.get(rel_path, "")
        after = ""
        action = 'modified'

        if new_path.exists():
            after = new_path.read_text(encoding='utf-8', errors='ignore')
            action = 'modified' if rel_path in before_contents else 'added'
        else:
            action = 'deleted'

        diff = ''.join(
            unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f'a/{rel_path}',
                tofile=f'b/{rel_path}',
            )
        )

        FileDiff.objects.create(
            changeset=changeset,
            file_path=rel_path,
            diff_content=diff or f'{action}: {rel_path}',
            action=action,
        )

    return changeset


def apply_chat_changes(
    project: Project,
    request_text: str,
    selected_file: str = "",
    selected_content: str = "",
    *,
    request_attachments: list[dict] | None = None,
    checkpoint: dict | None = None,
    chat_mode: str | None = None,
    changeset_source: str = 'chat',
) -> dict:
    result = _run_multi_agent_implementation(
        project=project,
        request_title="Chat-requested update",
        request_text=request_text,
        spec={
            "source": "chat",
            "request": request_text,
            "selected_file": selected_file or None,
            "instruction": "Apply the requested changes directly in code. Update related UI, logic, styles, routing, and supporting files so the project stays consistent and runnable.",
        },
        selected_file=selected_file,
        selected_content=selected_content,
        request_attachments=request_attachments,
        checkpoint=checkpoint,
        chat_mode=chat_mode,
        changeset_source=changeset_source,
    )
    return {
        "applied_files": result.get("applied_files", []),
        "count": result.get("count", 0),
        "plan": result.get("plan", {}),
        "review": result.get("review", {}),
        "validation_results": result.get("validation_results", []),
        "context_files": result.get("context_files", []),
        "changeset_id": result.get("changeset_id"),
        "undo": result.get("undo"),
    }


def run_ai_test_simulation(feature: Feature, tech_stack):
    try:
        from agents.base import BaseAgent

        agent = BaseAgent(
            role="QA Lead",
            system_instruction="You are a QA lead. Evaluate feature specs and simulate test results. Always return valid JSON.",
            ai_config=_project_ai_config(feature.project),
        )
        prompt = f"""Evaluate this feature and simulate test results.

Feature: {feature.title}
Description: {feature.description}
Spec: {json.dumps(feature.spec, indent=2) if feature.spec else 'No spec'}
Tech Stack: {', '.join(tech_stack)}

Return ONLY valid JSON with overall_status, score, summary, tests, coverage, suggestions, and blockers."""

        result = agent.generate(prompt)
        return agent.parse_json(result)
    except Exception as exc:
        return {
            "overall_status": "warning",
            "score": 0,
            "summary": f"Test simulation failed: {str(exc)}",
            "tests": [],
            "coverage": 0,
            "suggestions": [],
            "blockers": [],
        }


def _project_features_payload(project: Project):
    features = list(
        Feature.objects.filter(project=project).order_by('-created_at').values(
            'id', 'title', 'description', 'status', 'spec', 'created_by', 'created_at', 'suggestions'
        )
    )
    for feature in features:
        try:
            test_result = TestResult.objects.get(feature_id=feature['id'])
            feature['test_results'] = {
                'overall_status': test_result.overall_status,
                'score': test_result.score,
                'summary': test_result.summary,
                'tests': test_result.tests,
                'coverage': test_result.coverage,
                'suggestions': test_result.suggestions,
                'blockers': test_result.blockers,
            }
        except TestResult.DoesNotExist:
            feature['test_results'] = None

        feature['pipeline_history'] = list(FeatureHistory.objects.filter(feature_id=feature['id']).order_by('at').values('stage', 'action', 'by', 'comment', 'at'))
        feature['approvals'] = list(FeatureApproval.objects.filter(feature_id=feature['id']).order_by('at').values('by', 'role', 'comment', 'at'))
    return features


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


def _project_source_type(project: Project) -> str:
    if project.github_url:
        return 'github'
    if project.local_path and not str(project.local_path).startswith(str(PROJECTS_DIR)):
        return 'folder'
    return 'starter'


def _recommended_start_tab(project: Project) -> str:
    source_type = _project_source_type(project)
    if source_type in {'github', 'folder'}:
        return 'onboarding'
    return 'overview'


def _feature_stage_counts(features: list[dict]) -> dict:
    counts = {stage: 0 for stage in PIPELINE_STAGES}
    for feature in features:
        status = str(feature.get('status') or '')
        if status in counts:
            counts[status] += 1
    return counts


def _live_feature_inventory(project: Project) -> list[dict]:
    inventory = []
    for feature in Feature.objects.filter(project=project).order_by('-created_at')[:20]:
        spec = feature.spec or {}
        latest_history = FeatureHistory.objects.filter(feature=feature).order_by('-at').first()
        inventory.append({
            'title': feature.title,
            'status': feature.status or 'unknown',
            'description': feature.description or spec.get('user_story') or 'No feature description captured yet.',
            'implementation_notes': (
                (latest_history.comment if latest_history and latest_history.comment else '')
                or str(spec.get('technical_approach') or '')[:320]
                or 'Tracked as a live work item in DevHub.'
            ),
        })
    return inventory


def _live_pipeline_document(project: Project, features_payload: list[dict] | None = None) -> dict:
    features_payload = features_payload or _project_features_payload(project)
    counts = _feature_stage_counts(features_payload)
    stage_titles = {
        'backlog': 'Scoped work waiting to be started.',
        'development': 'Work currently being implemented in code.',
        'testing': 'Changes being validated through tests and checks.',
        'code_review': 'Work waiting for approval or review.',
        'staging': 'Changes that are nearly ready to ship.',
    }
    stage_rows = []
    for stage in PIPELINE_STAGES:
        stage_features = [feature for feature in features_payload if feature.get('status') == stage][:6]
        stage_rows.append({
            'name': stage.replace('_', ' ').title(),
            'purpose': stage_titles.get(stage, 'Tracked work stage'),
            'entry_criteria': [f'Feature reaches {stage.replace("_", " ")} stage.'],
            'exit_criteria': ['Advance to the next stage or send back for changes.'],
            'count': counts.get(stage, 0),
            'active_features': [item.get('title') for item in stage_features if item.get('title')],
        })
    return {
        'stages': stage_rows,
        'approval_gates': [
            'Approve confirms a feature is ready for the next checkpoint.',
            'Move Forward advances the same work item through the shared lifecycle.',
        ],
        'ai_capabilities': [
            'AI can generate specs, implement changes, simulate tests, and refresh architecture context.',
            'Pipeline actions update the same work items used by Overview and Onboarding.',
        ],
        'team_workflow': 'DevHub tracks one work-item model that can be viewed as either a list of features or a delivery board.',
    }


def _work_items_summary(project: Project, features_payload: list[dict] | None = None) -> dict:
    features_payload = features_payload or _project_features_payload(project)
    counts = _feature_stage_counts(features_payload)
    in_progress = [feature.get('title') for feature in features_payload if feature.get('status') in {'development', 'testing', 'code_review'}][:6]
    return {
        'total': len(features_payload),
        'by_stage': counts,
        'in_progress': in_progress,
        'completed_like': counts.get('staging', 0),
        'empty': len(features_payload) == 0,
    }


def _overview_time_label(value) -> str:
    if not value:
        return ""
    try:
        delta = timezone.now() - value
    except Exception:
        return str(value)
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    days = hours // 24
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return value.strftime("%Y-%m-%d")


def _overview_severity_weight(value: str) -> int:
    normalized = str(value or "").strip().lower()
    return {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "warning": 2,
        "low": 1,
        "info": 0,
    }.get(normalized, 0)


def _build_overview_project_health(blueprint: dict, runtime: dict, features_payload: list[dict], codebase_context: dict) -> list[dict]:
    counts = _feature_stage_counts(features_payload)
    active_count = counts.get('development', 0) + counts.get('testing', 0) + counts.get('code_review', 0)
    runtime_type = str(runtime.get('runtime_type') or '').strip().lower()
    runtime_command = str(runtime.get('run_command') or '').strip()
    testing = blueprint.get('testing_strategy') if isinstance(blueprint.get('testing_strategy'), dict) else {}
    validation_command = str(testing.get('run_command') or '').strip()
    doc_paths = _confirmed_overview_doc_paths(blueprint, codebase_context)
    return [
        {
            'label': 'Runtime',
            'value': runtime_type.title() if runtime_type and runtime_type != 'unknown' else 'Not detected',
            'detail': runtime_command or 'No primary run command was detected from the indexed entrypoints.',
            'tone': 'good' if runtime_command else 'warn',
        },
        {
            'label': 'Validation',
            'value': 'Command detected' if validation_command else 'Manual validation',
            'detail': validation_command or str(testing.get('unit') or 'No primary validation command was detected yet.'),
            'tone': 'good' if validation_command else 'warn',
        },
        {
            'label': 'Docs',
            'value': f'{len(doc_paths)} source{"s" if len(doc_paths) != 1 else ""}' if doc_paths else 'Thin docs',
            'detail': _format_path_list(doc_paths, max_paths=3) or 'No README, instruction file, or docs directory content was detected in the indexed paths.',
            'tone': 'good' if doc_paths else 'warn',
        },
        {
            'label': 'Active Work',
            'value': f'{active_count} active / {len(features_payload)} total' if features_payload else 'No tracked work',
            'detail': f"Backlog {counts.get('backlog', 0)}, development {counts.get('development', 0)}, testing {counts.get('testing', 0)}, review {counts.get('code_review', 0)}.",
            'tone': 'neutral' if features_payload else 'warn',
        },
    ]


def _build_overview_current_risks(blueprint: dict) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for item in _blueprint_list(blueprint.get('security_considerations'))[:3]:
        if not isinstance(item, dict):
            continue
        detail = str(item.get('description') or '').strip()
        if not detail or detail in seen:
            continue
        seen.add(detail)
        items.append({
            'title': str(item.get('area') or 'Security consideration').strip(),
            'severity': str(item.get('severity') or 'medium').strip().lower(),
            'detail': detail,
        })
    for item in _blueprint_list(blueprint.get('performance_notes'))[:2]:
        if not isinstance(item, dict):
            continue
        detail = str(item.get('description') or '').strip()
        if not detail or detail in seen:
            continue
        seen.add(detail)
        items.append({
            'title': str(item.get('area') or 'Performance note').strip(),
            'severity': str(item.get('impact') or 'medium').strip().lower(),
            'detail': detail,
        })
    for note in _blueprint_list(blueprint.get('gotchas'))[:2]:
        detail = str(note or '').strip()
        if not detail or detail in seen or _is_speculative_risk_text(detail):
            continue
        seen.add(detail)
        items.append({
            'title': 'Operational gotcha',
            'severity': 'medium',
            'detail': detail,
        })
    items.sort(key=lambda item: (-_overview_severity_weight(str(item.get('severity') or '')), str(item.get('title') or '')))
    return items[:5]


def _setup_command_entry_path(workspace_path: Path, codebase_context: dict, runtime: dict) -> str:
    setup_command = str(runtime.get('setup_command') or '').strip()
    if not setup_command:
        return str(runtime.get('entrypoint') or '')

    lowered = setup_command.lower()
    if any(token in lowered for token in ('npm', 'pnpm', 'yarn')):
        manifests = _workspace_package_manifests(workspace_path, codebase_context)
        preferred = next(
            (
                manifest
                for manifest in manifests
                if str(manifest.get('rel_dir') or '').strip()
                and any((manifest.get('scripts') or {}).get(name) for name in ('dev', 'start', 'serve', 'preview'))
            ),
            None,
        )
        if preferred:
            return str(preferred.get('path') or '')
        if manifests:
            return str(manifests[0].get('path') or '')

    if any(token in lowered for token in ('pip', 'poetry', 'uv ', 'manage.py', 'pytest', 'tox')):
        for root in _workspace_python_roots(workspace_path, codebase_context):
            for candidate in (root.get('requirements'), root.get('pyproject'), root.get('manage_py')):
                if str(candidate or '').strip():
                    return str(candidate)

    return str(runtime.get('entrypoint') or '')


def _build_overview_runtime_entrypoints(project: Project, codebase_context: dict, runtime: dict) -> list[dict]:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return []

    items: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(label: str, path: str = "", command: str = "", detail: str = "") -> None:
        normalized_path = str(path or "").replace("\\", "/").strip()
        normalized_command = str(command or "").strip()
        normalized_detail = str(detail or "").strip()
        if not (normalized_path or normalized_command or normalized_detail):
            return
        key = (normalized_path, normalized_command)
        if key in seen:
            return
        seen.add(key)
        items.append({
            'label': label,
            'path': normalized_path,
            'command': normalized_command,
            'detail': normalized_detail,
        })

    runtime_type = str(runtime.get('runtime_type') or '').strip().lower()
    if runtime_type and runtime_type != 'unknown':
        runtime_detail = 'Detected from repository entrypoints.'
        if runtime.get('preview_url'):
            runtime_detail = f"Preview URL: {runtime.get('preview_url')}"
        add(
            f"{runtime_type.title()} runtime",
            str(runtime.get('entrypoint') or ''),
            str(runtime.get('run_command') or ''),
            runtime_detail,
        )
    if runtime.get('setup_command'):
        add(
            'Setup command',
            _setup_command_entry_path(workspace_path, codebase_context, runtime),
            str(runtime.get('setup_command') or ''),
            'Detected setup or install command for the active runtime.',
        )

    for root in _workspace_python_roots(workspace_path, codebase_context)[:4]:
        rel_dir = str(root.get('rel_dir') or '')
        manage_py = str(root.get('manage_py') or '')
        if manage_py:
            command = _prefix_command_for_dir(rel_dir, 'python manage.py runserver') if str(root.get('framework') or '').lower() == 'django' else ''
            detail = 'Django management entrypoint.' if str(root.get('framework') or '').lower() == 'django' else 'Python entrypoint root.'
            add(f"Python entrypoint in {rel_dir or 'project root'}", manage_py, command, detail)

    for manifest in _workspace_package_manifests(workspace_path, codebase_context)[:6]:
        scripts = manifest.get('scripts') if isinstance(manifest.get('scripts'), dict) else {}
        package_manager = str(manifest.get('package_manager') or 'npm')
        rel_dir = str(manifest.get('rel_dir') or '')
        for script_name in ('dev', 'start', 'serve', 'preview'):
            if scripts.get(script_name):
                add(
                    f"Package script in {rel_dir or 'project root'}",
                    str(manifest.get('path') or ''),
                    _prefix_command_for_dir(rel_dir, _run_script_command(package_manager, script_name)),
                    f"Uses `{script_name}` from `{manifest.get('path')}`.",
                )
                break

    return items[:5]


def _build_overview_read_first(blueprint: dict, codebase_context: dict, runtime_entrypoints: list[dict]) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()

    def add(title: str, path: str, reason: str) -> None:
        normalized = str(path or '').replace("\\", "/").strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        items.append({
            'title': title,
            'path': normalized,
            'reason': reason,
        })

    for path in _confirmed_overview_doc_paths(blueprint, codebase_context)[:3]:
        add(PurePosixPath(path).name, path, 'Repository documentation or instruction content detected from indexed files.')
    for entry in runtime_entrypoints[:2]:
        if isinstance(entry, dict) and entry.get('path'):
            add('Runtime entrypoint', str(entry.get('path')), 'Useful for understanding how the application boots locally.')
    api_source_paths: list[str] = []
    for item in _blueprint_list(blueprint.get('api_endpoints'))[:8]:
        if not isinstance(item, dict):
            continue
        source = item.get('source') or {}
        if not isinstance(source, dict):
            continue
        for key in ('url_file', 'view_file'):
            value = str(source.get(key) or '').strip()
            if value:
                api_source_paths.append(value)
    if api_source_paths:
        add('Primary backend routes', api_source_paths[0], 'Start here to trace routed endpoints back to their handlers.')
    database_sources = _blueprint_list(codebase_context.get('database_source_files'))
    if database_sources:
        add('Primary data model', str(database_sources[0]), 'Useful before changing persistence rules, schema, or API payloads.')
    return items[:5]


def _build_overview_recent_changes(project: Project) -> list[dict]:
    items: list[dict] = []
    changesets = Changeset.objects.filter(project=project).prefetch_related('files_changed', 'feature').order_by('-created_at')[:4]
    for changeset in changesets:
        file_list = list(changeset.files_changed.values_list('file_path', flat=True)[:3])
        detail = str(changeset.description or '').strip()
        if not detail and file_list:
            detail = f"Affects {_format_path_list(file_list, max_paths=3)}."
        items.append({
            'title': changeset.title,
            'status': changeset.status,
            'detail': detail or 'Recorded project changeset.',
            'meta': _overview_time_label(changeset.created_at),
        })
    if items:
        return items

    history = FeatureHistory.objects.select_related('feature').order_by('-at')[:4]
    for entry in history:
        stage = str(entry.stage or '').replace('_', ' ').strip() or 'workflow'
        action = str(entry.action or 'updated').replace('_', ' ').strip()
        detail = str(entry.comment or '').strip() or f"{action.title()} in {stage} by {entry.by}."
        items.append({
            'title': entry.feature.title if entry.feature_id else 'Tracked work item',
            'status': stage,
            'detail': detail,
            'meta': _overview_time_label(entry.at),
        })
    return items


def _build_overview_next_steps(blueprint: dict, runtime_entrypoints: list[dict], read_first: list[dict], features_payload: list[dict]) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()

    def add(title: str, detail: str) -> None:
        normalized_title = str(title or '').strip()
        normalized_detail = str(detail or '').strip()
        if not normalized_title or not normalized_detail:
            return
        key = f"{normalized_title}|{normalized_detail}"
        if key in seen:
            return
        seen.add(key)
        items.append({
            'title': normalized_title,
            'detail': normalized_detail,
        })

    for item in _blueprint_list(blueprint.get('onboarding_checklist'))[:2]:
        if isinstance(item, dict):
            add(str(item.get('task') or '').strip(), str(item.get('instructions') or item.get('why_important') or '').strip())

    first_runtime = next((item for item in runtime_entrypoints if isinstance(item, dict) and item.get('command')), None)
    if first_runtime:
        runtime_path = str(first_runtime.get('path') or '').strip()
        runtime_command = str(first_runtime.get('command') or '').strip()
        location = f" from `{runtime_path}`" if runtime_path else ""
        add('Run the main entrypoint locally', f"Use `{runtime_command}`{location} to confirm the current baseline before changing behavior.")

    testing = blueprint.get('testing_strategy') if isinstance(blueprint.get('testing_strategy'), dict) else {}
    validation_command = str(testing.get('run_command') or '').strip()
    if validation_command:
        add('Validate the current baseline', f"Run `{validation_command}` early so later regressions are easier to isolate.")

    if read_first:
        read_paths = [str(item.get('path') or '') for item in read_first[:3] if isinstance(item, dict) and item.get('path')]
        if read_paths:
            add('Read the core repo files first', f"Start with {_format_path_list(read_paths, max_paths=3)} before editing deeper modules.")

    active_count = sum(1 for item in features_payload if str(item.get('status') or '') in {'development', 'testing', 'code_review'})
    if active_count:
        add('Check in-flight work before large edits', f"There {'is' if active_count == 1 else 'are'} {active_count} active tracked work item{'s' if active_count != 1 else ''} that may already touch the same surfaces.")

    return items[:5]


def _build_blueprint_overview_insights(project: Project, blueprint: dict, codebase_context: dict, features_payload: list[dict]) -> dict:
    workspace_path = _project_workspace_path(project)
    runtime = detect_runtime(workspace_path) if workspace_path else {}
    runtime_entrypoints = _build_overview_runtime_entrypoints(project, codebase_context, runtime)
    read_first = _build_overview_read_first(blueprint, codebase_context, runtime_entrypoints)
    return {
        'overview_project_health': _build_overview_project_health(blueprint, runtime, features_payload, codebase_context),
        'overview_current_risks': _build_overview_current_risks(blueprint),
        'overview_runtime_entrypoints': runtime_entrypoints,
        'overview_read_first': read_first,
        'overview_recent_changes': _build_overview_recent_changes(project),
        'overview_next_steps': _build_overview_next_steps(blueprint, runtime_entrypoints, read_first, features_payload),
    }


def _suggested_work_items(project: Project, features_payload: list[dict] | None = None) -> list[dict]:
    features_payload = features_payload or _project_features_payload(project)
    existing_titles = {str(item.get('title') or '').strip().lower() for item in features_payload}
    suggestions = []

    for item in (project.blueprint or {}).get('feature_inventory') or []:
        title = str(item.get('title') or '').strip()
        if not title or title.lower() in existing_titles:
            continue
        suggestions.append({
            'title': title,
            'reason': str(item.get('description') or item.get('implementation_notes') or 'Suggested from the current blueprint.'),
            'source': 'blueprint',
            'suggested_stage': str(item.get('status') or 'backlog'),
        })
        if len(suggestions) >= 5:
            return suggestions

    for item in (project.blueprint or {}).get('change_guide') or []:
        area = str(item.get('area') or '').strip()
        if not area:
            continue
        title = f"{area} follow-up"
        if title.lower() in existing_titles:
            continue
        suggestions.append({
            'title': title,
            'reason': str(item.get('notes') or 'Suggested from the blueprint change guide.'),
            'source': 'change_guide',
            'suggested_stage': 'backlog',
        })
        if len(suggestions) >= 5:
            break
    return suggestions


def _derive_onboarding_ai_suggestions(
    project: Project,
    runtime: dict | None,
    features_payload: list[dict],
    suggested_work_items: list[dict],
) -> list[str]:
    blueprint = project.blueprint if isinstance(project.blueprint, dict) else {}
    suggestions: list[str] = []
    source_type = _project_source_type(project)

    read_first = _blueprint_list(blueprint.get('overview_read_first'))
    if read_first:
        item = read_first[0] if isinstance(read_first[0], dict) else {}
        title = str(item.get('title') or item.get('label') or 'the recommended starting files').strip()
        reason = str(item.get('reason') or '').strip()
        suggestions.append(
            f"Start with {title}{f' to {reason.lower()}' if reason else ' before making changes'}."
        )

    runtime_command = str((runtime or {}).get('run_command') or '').strip()
    if runtime_command:
        suggestions.append(f"Run `{runtime_command}` in Workspace to verify the app boots before changing behavior.")
    elif project.workspace_id:
        suggestions.append("Open Workspace and confirm the detected runtime or setup commands before editing code.")

    if suggested_work_items:
        top_item = suggested_work_items[0]
        title = str(top_item.get('title') or 'the top suggested work item').strip()
        reason = str(top_item.get('reason') or '').strip()
        suggestions.append(
            f"Turn {title} into a tracked work item{f' because {reason.lower()}' if reason else ''}."
        )
    elif not features_payload:
        suggestions.append("Create the first work item from the current blueprint so planning and implementation stay aligned.")
    else:
        active_feature = next(
            (feature for feature in features_payload if str(feature.get('status') or '') in {'backlog', 'development', 'testing', 'code_review'}),
            None,
        )
        if active_feature:
            title = str(active_feature.get('title') or 'the active work item').strip()
            status = str(active_feature.get('status') or 'current').replace('_', ' ')
            suggestions.append(f"Continue with {title} from the {status} stage and keep the blueprint in sync with the change.")

    docs_available = bool(str(blueprint.get('readme_excerpt') or '').strip()) or bool(_blueprint_list(blueprint.get('instruction_files')))
    if docs_available and source_type in {'github', 'folder'}:
        suggestions.append("Use the Repository and Onboarding tabs together to map root docs, important folders, and runtime entrypoints before deeper edits.")

    if blueprint and source_type in {'starter', 'github', 'folder'}:
        suggestions.append("Regenerate the blueprint after structural changes so repository docs, onboarding context, and architecture notes stay accurate.")

    return _dedupe_json_items([item for item in suggestions if item])[:4]


def _derive_onboarding_summary(project: Project, runtime: dict | None, features_payload: list[dict] | None = None) -> dict:
    features_payload = features_payload or _project_features_payload(project)
    source_type = _project_source_type(project)
    source_label = {
        'starter': 'Managed starter project',
        'github': 'Imported GitHub repository',
        'folder': 'Connected local project folder',
    }.get(source_type, 'Project')
    next_steps = []
    if source_type in {'github', 'folder'}:
        next_steps.extend([
            'Review onboarding first to understand how this codebase is organized.',
            'Open the blueprint to inspect architecture, repository structure, and key workflows.',
        ])
    else:
        next_steps.extend([
            'Review the overview and first-run context for the generated starter.',
            'Create or review the initial work items before editing code.',
        ])
    next_steps.append('Use Work Items to manage scope and Workspace to implement code changes.')
    suggested_work_items = _suggested_work_items(project, features_payload)
    ai_suggestions = _derive_onboarding_ai_suggestions(project, runtime, features_payload, suggested_work_items)

    runtime_hint = runtime.get('run_command') if isinstance(runtime, dict) else None
    return {
        'source_label': source_label,
        'recommended_start_tab': _recommended_start_tab(project),
        'next_steps': next_steps,
        'ai_suggestions': ai_suggestions,
        'suggested_work_items': suggested_work_items,
        'runtime_hint': runtime_hint or 'Runtime command will appear once detected.',
        'existing_work_items': len(features_payload),
        'has_blueprint': bool(project.blueprint),
    }


def _project_flow_payload(project: Project, runtime: dict | None, features_payload: list[dict] | None = None) -> list[dict]:
    features_payload = features_payload or _project_features_payload(project)
    source_type = _project_source_type(project)
    recommended = _recommended_start_tab(project)
    runtime_suffix = ''
    if isinstance(runtime, dict) and runtime.get('runtime_type'):
        runtime_suffix = f" using {runtime.get('runtime_type')}"
    steps = [
        {
            'id': 'overview',
            'title': 'Project overview',
            'description': 'Understand the project source, stack, runtime, and current health.',
            'status': 'current' if recommended == 'overview' else 'ready',
        },
        {
            'id': 'onboarding',
            'title': 'Get oriented',
            'description': 'Learn how the repo is structured and where to start contributing.',
            'status': 'current' if recommended == 'onboarding' else 'ready',
        },
        {
            'id': 'blueprint',
            'title': 'Read the blueprint',
            'description': 'Inspect architecture, repository map, APIs, schema, and workflows.',
            'status': 'ready' if project.blueprint else 'pending',
        },
        {
            'id': 'work_items',
            'title': 'Plan and track work',
            'description': 'Manage the same work items in list and board views.',
            'status': 'ready' if features_payload else 'pending',
        },
        {
            'id': 'code',
            'title': 'Edit in workspace',
            'description': f"Implement and review changes in the live workspace{runtime_suffix}.",
            'status': 'ready' if project.workspace_id else 'pending',
        },
    ]
    if source_type == 'starter':
        steps[0]['status'] = 'current'
        if len(steps) > 1 and steps[1]['status'] == 'current':
            steps[1]['status'] = 'ready'
    return steps


def _slug_to_title(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9]+', ' ', text or '').strip()
    return cleaned.title() or 'New Project'


def _fallback_project_suggestion(idea: str, source_type: str, tech_stack: list[str]) -> dict:
    source_label = {
        'starter': 'AI-generated starter',
        'github': 'GitHub import',
        'folder': 'existing local folder',
    }.get(source_type, 'project')
    suggested_stack = _suggested_stack_from_text(idea, tech_stack)
    name = _slug_to_title(idea[:60] or 'new project')
    description = (
        f"{name} is a {source_label} built around {', '.join(suggested_stack)}. "
        "It starts from a working foundation, supports iterative feature delivery, "
        "and stays easy to evolve through the workspace, feature pipeline, and AI chat."
    )
    return {
        'name': name,
        'description': description,
        'tech_stack': suggested_stack,
    }


def _suggest_project_details(idea: str, source_type: str, tech_stack: list[str]) -> dict:
    fallback = _fallback_project_suggestion(idea, source_type, tech_stack)

    try:
        from agents.base import BaseAgent

        agent = BaseAgent(
            role="Project Setup Assistant",
            system_instruction=(
                "You generate concise but polished DevHub project metadata. "
                "Return valid JSON with keys name, description, and tech_stack. "
                "Descriptions should be clear, practical, and editable."
            ),
            ai_config=_global_ai_config(),
        )
        response = agent.generate(
            json.dumps({"idea": idea, "source_type": source_type, "tech_stack": tech_stack}),
            response_schema=True,
        )
        parsed = agent.parse_json(response)
        return {
            'name': str(parsed.get('name') or fallback['name']).strip() or fallback['name'],
            'description': str(parsed.get('description') or fallback['description']).strip() or fallback['description'],
            'tech_stack': _normalize_tech_stack(parsed.get('tech_stack') or fallback['tech_stack']),
        }
    except Exception:
        logger.exception("Project detail suggestion failed; using fallback")
        return fallback


@csrf_exempt
def devhub_ai_settings(request):
    if request.method == 'GET':
        return JsonResponse({'ai_config': _global_ai_config()})

    if request.method in {'POST', 'PATCH'}:
        try:
            body = _parse_json_body(request)
            ai_config = normalize_ai_config(body.get('ai_config'))
            settings = _load_devhub_settings()
            settings['ai_config'] = ai_config
            _save_devhub_settings(settings)
            return JsonResponse({'ai_config': ai_config})
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def suggest_project_details(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        body = _parse_json_body(request)
        idea = str(body.get('idea') or body.get('name') or '').strip()
        source_type = str(body.get('source_type') or 'starter').strip().lower()
        tech_stack = _normalize_tech_stack(body.get('tech_stack', []))
        return JsonResponse(_suggest_project_details(idea, source_type, tech_stack))
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def inspect_github_import(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    temp_dir = None
    try:
        body = _parse_json_body(request)
        github_url = str(body.get('github_url') or '').strip()
        idea = str(body.get('idea') or '').strip()
        if not github_url:
            return JsonResponse({'error': 'GitHub URL is required'}, status=400)

        temp_dir = Path(tempfile.mkdtemp(prefix='devhub-import-'))
        repo_root = temp_dir / "repo"
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', github_url, str(repo_root)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return JsonResponse({'error': f'git clone failed: {result.stderr.strip() or "unknown git error"}'}, status=400)

        inspection = _build_import_inspection(repo_root, 'github', idea=idea, source_label=github_url)
        inspection['github_url'] = github_url
        return JsonResponse(inspection)
    except subprocess.TimeoutExpired:
        return JsonResponse({'error': 'GitHub inspection timed out'}, status=408)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@csrf_exempt
def pick_local_folder(request):
    if request.method not in {'POST', 'GET'}:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        selected = _pick_local_folder()
        if not selected:
            return JsonResponse({'error': 'Folder selection was cancelled'}, status=400)
        return JsonResponse({'local_path': selected})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def inspect_folder_import(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        body = _parse_json_body(request)
        local_path = str(body.get('local_path') or '').strip()
        idea = str(body.get('idea') or '').strip()
        if not local_path:
            return JsonResponse({'error': 'Local path is required'}, status=400)

        resolved_path = _normalize_path(local_path)
        if not resolved_path.exists() or not resolved_path.is_dir():
            return JsonResponse({'error': 'Local path does not exist or is not a directory'}, status=400)

        inspection = _build_import_inspection(resolved_path, 'folder', idea=idea, source_label=local_path)
        return JsonResponse(inspection)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


def list_projects(request):
    projects = [
        {
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'status': project.status,
            'tech_stack': project.tech_stack,
            'registered_at': project.registered_at,
            'local_path': project.local_path,
            'github_url': project.github_url,
            'github_integration': _github_integration_payload(project),
            'source_type': _project_source_type(project),
        }
        for project in Project.objects.all().order_by('-registered_at')
    ]
    return JsonResponse({'projects': list(projects)})


@csrf_exempt
def create_project(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        body = _parse_json_body(request)
        name = body.get('name', '').strip()
        starter_brief = body.get('idea', '').strip()
        description = body.get('description', '').strip() or starter_brief
        local_path = body.get('local_path', '').strip()
        github_url = body.get('github_url', '').strip()
        github_connection_id = int(body.get('github_connection_id') or 0)
        github_repository_full_name = str(body.get('github_repository_full_name') or '').strip()
        tech_stack = _normalize_tech_stack(body.get('tech_stack', []))
        if not tech_stack and starter_brief and not github_url and not local_path and not github_repository_full_name:
            tech_stack = _suggested_stack_from_text(starter_brief)

        if not name:
            return JsonResponse({'error': 'Project name is required'}, status=400)

        project = Project.objects.create(
            name=name,
            description=description,
            local_path=None,
            github_url=github_url or None,
            tech_stack=tech_stack,
        )

        if github_connection_id and github_repository_full_name:
            repo_folder = _managed_project_root(project)
            repo_folder.parent.mkdir(parents=True, exist_ok=True)
            try:
                connection = GitHubConnection.objects.filter(id=github_connection_id, is_active=True).first()
                if not connection or not connection.access_token:
                    raise GitHubIntegrationError('Connect GitHub before importing a connected repository.')
                config = github_oauth_config()
                repository = get_user_repository(config, connection.access_token, github_repository_full_name)
                clone_repository_with_token(connection.access_token, github_repository_full_name, repo_folder)
            except GitHubIntegrationError as exc:
                if repo_folder.exists():
                    shutil.rmtree(repo_folder, ignore_errors=True)
                project.delete()
                return JsonResponse({'error': str(exc)}, status=400)
            except subprocess.TimeoutExpired:
                if repo_folder.exists():
                    shutil.rmtree(repo_folder, ignore_errors=True)
                project.delete()
                return JsonResponse({'error': 'GitHub clone timed out'}, status=408)
            except Exception as exc:
                if repo_folder.exists():
                    shutil.rmtree(repo_folder, ignore_errors=True)
                project.delete()
                return JsonResponse({'error': f'GitHub clone error: {str(exc)}'}, status=500)

            project.github_url = str(repository.get('html_url') or f'https://github.com/{github_repository_full_name}')
            project.local_path = str(repo_folder)
            project.workspace_id = workspace_manager.create_workspace(str(repo_folder), managed=True)
            project.save()
            _upsert_project_github_link(project, repository, connection)
        elif github_url:
            repo_folder = _managed_project_root(project)
            repo_folder.parent.mkdir(parents=True, exist_ok=True)
            try:
                result = subprocess.run(['git', 'clone', '--depth', '1', github_url, str(repo_folder)], capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    project.delete()
                    return JsonResponse({'error': f'git clone failed: {result.stderr.strip()}'}, status=400)
            except subprocess.TimeoutExpired:
                project.delete()
                return JsonResponse({'error': 'git clone timed out'}, status=408)
            except Exception as exc:
                if repo_folder.exists():
                    shutil.rmtree(repo_folder, ignore_errors=True)
                project.delete()
                return JsonResponse({'error': f'GitHub clone error: {str(exc)}'}, status=500)

            project.local_path = str(repo_folder)
            project.workspace_id = workspace_manager.create_workspace(str(repo_folder), managed=True)
            project.save()
        elif local_path:
            normalized_path = _normalize_path(local_path)
            if not normalized_path.exists() or not normalized_path.is_dir():
                project.delete()
                return JsonResponse({'error': 'Local path does not exist or is not a directory'}, status=400)
            project.local_path = str(normalized_path)
            project.workspace_id = workspace_manager.create_workspace(str(normalized_path), managed=False)
            project.save()
        else:
            project_root = _managed_project_root(project)
            scaffold_project(project, project_root, starter_brief=starter_brief)
            project.local_path = str(project_root)
            project.workspace_id = workspace_manager.create_workspace(str(project_root), managed=True)
            project.save()

        try:
            workspace_path = Path(project.local_path)
            index_semantic_memory(project, workspace_path)
            compress_recent_activity(project)
            _read_project_memory(project, workspace_path)
            _read_project_instructions(project, workspace_path)
            build_blueprint_context(project, workspace_path)
        except MEMORY_DB_ERRORS:
            logger.warning("Memory tables are not ready yet for project %s", project.id)
        except Exception:
            logger.exception("Failed to initialize project memory for project %s", project.id)

        # Seed the first blueprint before returning so the project page never lands
        # on an empty architecture screen while longer documentation work continues.
        try:
            if not project.blueprint:
                logger.info("Generating initial blueprint seed for project %s", project.id)
                generate_blueprint_sync(project)
                project.refresh_from_db(fields=['blueprint'])
        except MEMORY_DB_ERRORS:
            logger.warning("Skipped initial blueprint seed for project %s because the database was busy.", project.id)
        except Exception:
            logger.exception("Failed to generate initial blueprint seed for project %s", project.id)

        _schedule_project_context_generation(
            project,
            include_documentation=bool(github_url or local_path or github_repository_full_name),
            include_blueprint=not bool(project.blueprint),
        )

        documentation_run = DocumentationRun.objects.filter(project=project).prefetch_related('sections').first()
        documentation = _documentation_run_payload(documentation_run)
        documentation_status = str(documentation.get('status') or '').lower()
        context_initializing = (not bool(project.blueprint)) or documentation_status in {'pending', 'running'}

        return JsonResponse({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'workspace_id': project.workspace_id,
            'status': 'ready',
            'blueprint': project.blueprint,
            'documentation': documentation,
            'context_initializing': context_initializing,
            'github_integration': _github_integration_payload(project),
            'runtime': detect_runtime(Path(project.local_path)),
        }, status=201)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


def _project_coder_customization_payload(project: Project) -> dict:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return {
            "available": False,
            "meta_root": ".devhub",
            "meta_path": "",
            "summary": "",
            "skills": [],
            "prompt_overrides": [],
            "slash_commands": [],
            "suggested_files": suggested_project_customization_files(),
            "can_bootstrap": False,
        }

    try:
        raw_skills = list_project_skills(workspace_path, limit=24)
        raw_prompts = list_project_prompt_overrides(workspace_path)
        summary = build_project_customization_summary(workspace_path)
    except Exception:
        logger.exception("Failed to build coder customization payload for project %s", project.id)
        raw_skills = []
        raw_prompts = []
        summary = ""

    skills = [
        {
            "name": str(item.get("name") or "").strip(),
            "slug": str(item.get("slug") or "").strip(),
            "description": str(item.get("description") or "").strip(),
            "path": str(item.get("path") or "").strip(),
        }
        for item in raw_skills
        if str(item.get("name") or "").strip()
    ]

    prompt_overrides = [
        {
            "name": str(item.get("name") or "").strip(),
            "path": str(item.get("path") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
        }
        for item in raw_prompts
        if str(item.get("name") or "").strip()
    ]

    return {
        "available": bool(skills or prompt_overrides),
        "meta_root": ".devhub",
        "meta_path": str((workspace_path / ".devhub").resolve()),
        "summary": summary[:4000],
        "skills": skills,
        "prompt_overrides": prompt_overrides,
        "slash_commands": [f"/{item.get('slug') or item.get('name')}" for item in skills[:12]],
        "suggested_files": suggested_project_customization_files(),
        "can_bootstrap": True,
    }


def get_project(request, project_id):
    try:
        project = Project.objects.get(id=project_id)
        if not project.workspace_id and project.local_path and Path(project.local_path).is_dir():
            try:
                project.workspace_id = workspace_manager.create_workspace(project.local_path, managed=False)
                project.save()
            except Exception:
                pass

        runtime = None
        features_payload = _project_features_payload(project)
        if project.local_path and Path(project.local_path).is_dir():
            workspace_path = Path(project.local_path)
            runtime = detect_runtime(workspace_path)
            try:
                memory_exists = WorkingMemory.objects.filter(project=project, scope='implementation').exists()
            except MEMORY_DB_ERRORS:
                memory_exists = True
            if not memory_exists:
                try:
                    compress_recent_activity(project)
                except Exception:
                    logger.exception("Failed to refresh working memory for project %s", project.id)
            if project.blueprint:
                try:
                    codebase_context = build_blueprint_context(project, workspace_path)
                    enriched_blueprint = dict(project.blueprint or {})
                    evidence_sequence_flows, evidence_common_workflows = _build_evidence_backed_workflows(workspace_path)
                    blueprint_backfilled = False
                    api_reference = _blueprint_list(codebase_context.get('api_reference'))
                    if api_reference and enriched_blueprint.get('api_endpoints') != api_reference:
                        enriched_blueprint['api_endpoints'] = api_reference
                        blueprint_backfilled = True
                    if evidence_sequence_flows and enriched_blueprint.get('sequence_flows') != evidence_sequence_flows:
                        enriched_blueprint['sequence_flows'] = evidence_sequence_flows
                        blueprint_backfilled = True
                    if evidence_common_workflows and enriched_blueprint.get('common_workflows') != evidence_common_workflows:
                        enriched_blueprint['common_workflows'] = evidence_common_workflows
                        blueprint_backfilled = True
                    enriched_blueprint = _merge_repo_guidance_into_blueprint(project, enriched_blueprint, codebase_context)
                    enriched_blueprint.update(_build_blueprint_overview_insights(project, enriched_blueprint, codebase_context, features_payload))
                    if blueprint_backfilled:
                        feature_summary = _render_project_features_summary(project, limit=20)
                        design_document_markdown, design_document_sections = _render_blueprint_design_document(
                            project,
                            enriched_blueprint,
                            codebase_context,
                            feature_summary,
                        )
                        enriched_blueprint['design_document_markdown'] = design_document_markdown
                        enriched_blueprint['design_document_sections'] = [
                            {
                                'id': section.get('id'),
                                'title': section.get('title'),
                                'markdown': '\n'.join(section.get('body') or []).strip(),
                            }
                            for section in design_document_sections
                        ]
                    if enriched_blueprint != (project.blueprint or {}):
                        project.blueprint = enriched_blueprint
                        project.save(update_fields=['blueprint'])
                except Exception:
                    logger.exception("Failed to backfill onboarding guidance for project %s", project.id)

        source_type = _project_source_type(project)
        recommended_start_tab = _recommended_start_tab(project)
        work_items_summary = _work_items_summary(project, features_payload)
        onboarding_summary = _derive_onboarding_summary(project, runtime, features_payload)
        project_flow = _project_flow_payload(project, runtime, features_payload)
        coder_customization = _project_coder_customization_payload(project)
        blueprint_meta = {
            'available': bool(project.blueprint),
            'generated': bool(project.blueprint),
            'indexed_files': (project.blueprint or {}).get('_meta', {}).get('indexed_files'),
            'cached': (project.blueprint or {}).get('_meta', {}).get('cached'),
        }
        documentation_run = DocumentationRun.objects.filter(project=project).prefetch_related('sections').first()
        documentation = _documentation_run_payload(documentation_run)
        documentation_status = str(documentation.get('status') or '').lower()
        context_initializing = (not bool(project.blueprint)) or documentation_status in {'pending', 'running'}

        return JsonResponse({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'github_url': project.github_url,
            'github_integration': _github_integration_payload(project),
            'local_path': project.local_path,
            'source_type': source_type,
            'workspace_id': project.workspace_id,
            'tech_stack': project.tech_stack,
            'status': project.status,
            'blueprint': project.blueprint,
            'features': features_payload,
            'recommended_start_tab': recommended_start_tab,
            'project_flow': project_flow,
            'work_items_summary': work_items_summary,
            'onboarding_summary': onboarding_summary,
            'blueprint_meta': blueprint_meta,
            'documentation': documentation,
            'context_initializing': context_initializing,
            'runtime': runtime,
            'coder_customization': coder_customization,
        })
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except (ValidationError, ValueError):
        return JsonResponse({'error': 'Invalid project ID'}, status=400)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def project_coder_customization_bootstrap(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValidationError, ValueError):
        return JsonResponse({'error': 'Project not found'}, status=404)

    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return JsonResponse({'error': 'Project has no editable local workspace.'}, status=400)

    try:
        bootstrap_result = bootstrap_project_customization(workspace_path)
        return JsonResponse(
            {
                'status': 'ok',
                'created': bootstrap_result.get('created') or [],
                'existing': bootstrap_result.get('existing') or [],
                'coder_customization': _project_coder_customization_payload(project),
            }
        )
    except Exception as exc:
        logger.exception("Failed to bootstrap coder customization for project %s", project.id)
        return JsonResponse({'error': str(exc)}, status=500)


def _documentation_run_payload(run: DocumentationRun | None) -> dict:
    if not run:
        return {
            'available': False,
            'status': 'idle',
            'sections': [],
        }

    sections = []
    for section in run.sections.all().order_by('order', 'title'):
        sections.append({
            'id': str(section.id),
            'key': section.key,
            'title': section.title,
            'order': section.order,
            'status': section.status,
            'summary': section.summary,
            'markdown': section.markdown,
            'evidence': section.evidence,
            'metadata': section.metadata,
            'updated_at': section.updated_at.isoformat() if section.updated_at else None,
        })

    return {
        'available': True,
        'id': str(run.id),
        'mode': run.mode,
        'status': run.status,
        'summary': run.summary,
        'output_path': run.output_path,
        'target_fingerprint': run.target_fingerprint,
        'error': run.error,
        'metadata': run.metadata,
        'started_at': run.started_at.isoformat() if run.started_at else None,
        'completed_at': run.completed_at.isoformat() if run.completed_at else None,
        'sections': sections,
    }


@csrf_exempt
def project_documentation(request, project_id):
    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValidationError, ValueError):
        return JsonResponse({'error': 'Project not found'}, status=404)

    if request.method == 'GET':
        latest_run = DocumentationRun.objects.filter(project=project).prefetch_related('sections').first()
        return JsonResponse({'documentation': _documentation_run_payload(latest_run)})

    if request.method == 'POST':
        if not project.local_path or not Path(project.local_path).is_dir():
            return JsonResponse({'error': 'Project workspace is not available'}, status=400)

        run = generate_codebase_reference_sync(project)
        payload = _documentation_run_payload(run)
        if run.status == 'failed':
            return JsonResponse({'documentation': payload, 'error': run.error or 'Documentation generation failed.'}, status=500)
        return JsonResponse({'documentation': payload}, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def project_codebase_doc(request, project_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValidationError, ValueError):
        return JsonResponse({'error': 'Project not found'}, status=404)

    try:
        rel_path = str(request.GET.get('path') or '').strip()
        payload = _build_codebase_doc_payload(project, rel_path=rel_path)
        return JsonResponse({'doc': payload})
    except FileNotFoundError as exc:
        return JsonResponse({'error': str(exc)}, status=404)
    except PermissionError:
        return JsonResponse({'error': 'Path is outside the project workspace'}, status=403)
    except Exception as exc:
        logger.exception("Failed to build codebase doc for project %s", project.id)
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def update_project(request, project_id):
    if request.method not in {'POST', 'PATCH'}:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
        body = _parse_json_body(request)
        name = str(body.get('name') or project.name).strip()
        description = str(body.get('description') or project.description).strip()
        github_url = str(body.get('github_url') or '').strip() or None
        tech_stack = _normalize_tech_stack(body.get('tech_stack', project.tech_stack))

        if not name:
            return JsonResponse({'error': 'Project name is required'}, status=400)

        project.name = name
        project.description = description
        project.github_url = github_url
        project.tech_stack = tech_stack
        project.save(update_fields=['name', 'description', 'github_url', 'tech_stack'])

        thread = threading.Thread(target=generate_blueprint_sync, args=(project,))
        thread.daemon = True
        thread.start()

        return JsonResponse({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'github_url': project.github_url,
            'local_path': project.local_path,
            'source_type': _project_source_type(project),
            'workspace_id': project.workspace_id,
            'tech_stack': project.tech_stack,
            'status': project.status,
        })
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def delete_project(request, project_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        project = Project.objects.get(id=project_id)
        if project.workspace_id:
            try:
                workspace_manager.delete_workspace(project.workspace_id)
            except Exception:
                pass
        project.delete()
        return JsonResponse({'ok': True})
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)


@csrf_exempt
def project_features(request, project_id):
    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValidationError, ValueError):
        return JsonResponse({'error': 'Project not found'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'features': _project_features_payload(project)})

    if request.method == 'POST':
        try:
            body = _parse_json_body(request)
            title = body.get('title', '').strip()
            description = body.get('description', '').strip()
            created_by = body.get('created_by', 'Developer')
            if not title:
                return JsonResponse({'error': 'Title is required'}, status=400)

            feature = Feature.objects.create(project=project, title=title, description=description, created_by=created_by)
            FeatureHistory.objects.create(feature=feature, stage='backlog', action='created', by=created_by)

            thread = threading.Thread(target=generate_feature_spec_sync, args=(feature, project))
            thread.daemon = True
            thread.start()

            return JsonResponse({'id': str(feature.id), 'title': feature.title, 'description': feature.description, 'status': feature.status}, status=201)
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def pipeline_action(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
        body = _parse_json_body(request)
        feature_id = body.get('feature_id')
        action = body.get('action')
        by = body.get('by', 'Developer')
        comment = body.get('comment', '')

        feature = Feature.objects.get(id=feature_id, project=project)
        previous_status = feature.status
        message = ''

        if action == 'advance':
            if feature.status not in PIPELINE_STAGES:
                return JsonResponse({'error': f'Cannot advance from {feature.status}'}, status=400)
            current_idx = PIPELINE_STAGES.index(feature.status)
            if current_idx >= len(PIPELINE_STAGES) - 1:
                return JsonResponse({'error': 'Already at last stage'}, status=400)
            next_stage = PIPELINE_STAGES[current_idx + 1]
            feature.status = next_stage
            feature.save()
            FeatureHistory.objects.create(feature=feature, stage=next_stage, action='advanced', by=by, comment=comment)
            message = f'Feature moved from {previous_status} to {next_stage}.'

            if next_stage == 'testing':
                try:
                    test_results = run_ai_test_simulation(feature, project.tech_stack or [])
                    TestResult.objects.update_or_create(
                        feature=feature,
                        defaults={
                            'overall_status': test_results.get('overall_status', 'warning'),
                            'score': test_results.get('score', 0),
                            'summary': test_results.get('summary', ''),
                            'tests': test_results.get('tests', []),
                            'coverage': test_results.get('coverage', 0),
                            'suggestions': test_results.get('suggestions', []),
                            'blockers': test_results.get('blockers', []),
                        },
                    )
                    message += ' Test simulation completed.'
                except Exception:
                    pass
        elif action == 'reject':
            feature.status = 'backlog'
            feature.save()
            FeatureHistory.objects.create(feature=feature, stage='backlog', action='rejected', by=by, comment=comment)
            message = 'Feature moved back to backlog.'
        elif action == 'approve':
            FeatureApproval.objects.create(feature=feature, by=by, role='developer', comment=comment)
            FeatureHistory.objects.create(feature=feature, stage=feature.status, action='approved', by=by, comment=comment)
            approvals_count = FeatureApproval.objects.filter(feature=feature).count()
            message = f'Approval recorded. Total approvals: {approvals_count}.'
        elif action == 'implement':
            if feature.status != 'development':
                feature.status = 'development'
                feature.save(update_fields=['status'])
            thread = threading.Thread(target=implement_feature_sync, args=(feature, project))
            thread.daemon = True
            thread.start()
            message = 'AI implementation started in the background. Refresh shortly to see modified files and history.'
        else:
            return JsonResponse({'error': 'Invalid action. Use advance, reject, approve, or implement.'}, status=400)

        return JsonResponse({
            'id': str(feature.id),
            'status': feature.status,
            'previous_status': previous_status,
            'action': action,
            'message': message,
        })
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except Feature.DoesNotExist:
        return JsonResponse({'error': 'Feature not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def project_chat(request, project_id):
    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValidationError, ValueError):
        return JsonResponse({'error': 'Project not found'}, status=404)

    if request.method == 'GET':
        requested_session_id = str(request.GET.get('session_id') or '').strip()
        fresh_session = str(request.GET.get('fresh') or '').strip().lower() in {'1', 'true', 'yes'}
        grouped_sessions, sessions = _group_project_chat_sessions(project)
        if fresh_session:
            active_session_id = ''
            active_messages = []
        else:
            active_session_id = requested_session_id or (sessions[0]['session_id'] if sessions else '')
            active_messages = [_serialize_chat_message(project, item) for item in grouped_sessions.get(active_session_id, [])]
        return JsonResponse(
            {
                'messages': active_messages,
                'sessions': sessions,
                'active_session_id': active_session_id or None,
            }
        )

    if request.method == 'POST':
        content = ''
        session_id = ''
        chat_checkpoint = None
        try:
            body = _parse_json_body(request)
            content = str(body.get('content') or '').strip()
            selected_file = str(body.get('selected_file') or '').strip()
            selected_content = str(body.get('selected_content') or '')
            context_mentions = body.get('context_mentions') or []
            try:
                attachments = _normalize_chat_attachments(body.get('attachments'))
            except ValueError as exc:
                return JsonResponse({'error': str(exc)}, status=400)
            apply_changes = body.get('apply_changes')
            explicit_chat_mode = _normalize_chat_mode(body.get('mode'))
            session_id = str(body.get('session_id') or '').strip() or str(uuid.uuid4())
            if not content and not attachments:
                return JsonResponse({'error': 'Message or image attachment is required'}, status=400)
            request_text = _chat_request_text(content, attachments)

            user_trace = {
                'context_mentions': _dedupe_chat_mentions(
                    _normalize_chat_mentions(context_mentions),
                    _infer_inline_chat_mentions(content),
                ),
                'selected_file': selected_file or None,
                'session_id': session_id,
                'chat_mode': explicit_chat_mode or 'auto',
                'attachments': attachments,
            }
            ChatMessage.objects.create(project=project, role='user', content=content, metadata=user_trace)

            should_apply_changes = _should_apply_changes_for_chat_mode(explicit_chat_mode, request_text, apply_changes)
            applied_changes = None
            assistant_trace = {}
            workspace_actions = []
            chat_checkpoint = None
            memory_context = build_memory_context(project, request_text, selected_file=selected_file)
            resolved_context_text, context_trace = _resolve_chat_context(
                project,
                request_text,
                selected_file=selected_file,
                selected_content=selected_content,
                context_mentions=context_mentions,
                session_id=session_id,
            )
            chat_decision = _classify_chat_state(
                project,
                request_text,
                selected_file,
                context_mentions,
                context_trace,
                should_apply_changes,
            )
            chat_state = str(chat_decision.get('state') or CHAT_STATE_GROUNDED_ANSWER)
            if explicit_chat_mode == CHAT_MODE_EDIT:
                chat_state = CHAT_STATE_EDIT_REQUEST
                chat_decision = {
                    'state': CHAT_STATE_EDIT_REQUEST,
                    'reason': 'Explicit edit mode was selected.',
                    'response_contract': (
                        "Apply the requested change directly to the codebase and summarize which files changed."
                    ),
                }
            elif explicit_chat_mode == CHAT_MODE_AGENT:
                if should_apply_changes and project.workspace_id:
                    workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
                    chat_checkpoint = create_workspace_checkpoint(
                        str(project.id),
                        workspace_path,
                        label=(content or request_text)[:160],
                        source='chat_agent',
                    )
                agent_result = _handle_agent_chat_request(
                    project,
                    request_text,
                    selected_file=selected_file,
                    selected_content=selected_content,
                    attachments=attachments,
                    session_id=session_id,
                    should_apply_changes=should_apply_changes,
                    context_trace=context_trace,
                    memory_context=memory_context,
                    checkpoint=chat_checkpoint,
                )
                if agent_result.get('handled'):
                    applied_changes = agent_result.get('applied_changes')
                    workspace_actions = list(agent_result.get('workspace_actions') or [])
                    ai_response = str(agent_result.get('assistant_message') or '')
                    assistant_trace = dict(agent_result.get('assistant_trace') or {})
                    assistant_trace['session_id'] = session_id
                    assistant_trace['chat_mode'] = CHAT_MODE_AGENT
                    if workspace_actions:
                        assistant_trace['workspace_actions'] = workspace_actions

                    try:
                        assistant_metadata = dict(assistant_trace or {})
                        assistant_metadata['session_id'] = session_id
                        ChatMessage.objects.create(project=project, role='assistant', content=ai_response, metadata=assistant_metadata)
                    except Exception:
                        logger.exception("Failed to persist assistant chat message for project %s", project.id)
                    _, sessions = _group_project_chat_sessions(project)
                    return JsonResponse({
                        'user_message': content,
                        'assistant_message': ai_response,
                        'applied_changes': applied_changes,
                        'workspace_actions': workspace_actions,
                        'trace': assistant_trace,
                        'session_id': session_id,
                        'sessions': sessions,
                    })

            if chat_state == CHAT_STATE_EDIT_REQUEST and project.workspace_id:
                if should_apply_changes and not chat_checkpoint:
                    workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
                    chat_checkpoint = create_workspace_checkpoint(
                        str(project.id),
                        workspace_path,
                        label=(content or request_text)[:160],
                        source='chat_edit',
                    )
                try:
                    applied_changes = apply_chat_changes(
                        project,
                        request_text,
                        selected_file=selected_file,
                        selected_content=selected_content,
                        request_attachments=attachments,
                        checkpoint=chat_checkpoint,
                        chat_mode=explicit_chat_mode or CHAT_MODE_EDIT,
                        changeset_source='chat',
                    )
                    applied_list = applied_changes['applied_files']
                    ai_response = (
                        "Applied the requested update directly to the project."
                        if not applied_list
                        else f"Applied the requested update to {len(applied_list)} file(s): {', '.join(applied_list)}."
                    )
                    assistant_trace = _build_chat_trace_from_changes(applied_changes, context_trace, memory_context)
                    assistant_trace['session_id'] = session_id
                    assistant_trace['chat_state'] = chat_state
                    assistant_trace['chat_mode'] = explicit_chat_mode or CHAT_MODE_EDIT
                    assistant_trace['state_reason'] = chat_decision.get('reason')
                except Exception as exc:
                    if chat_checkpoint:
                        delete_workspace_checkpoint(str(project.id), str(chat_checkpoint.get('id') or ''))
                        chat_checkpoint = None
                    logger.exception("Chat code application failed for project %s", project.id)
                    ai_response = f"I understood this as a code-change request, but the edit failed: {str(exc)}"
                    assistant_trace = {
                        'approach': context_trace.get('approach') or 'Tried to apply a code change request.',
                        'chat_state': chat_state,
                        'chat_mode': explicit_chat_mode or CHAT_MODE_EDIT,
                        'state_reason': chat_decision.get('reason'),
                        'session_id': session_id,
                        'context_mentions': context_trace.get('context_mentions') or [],
                        'context_sources': context_trace.get('context_sources') or [],
                        'files_accessed': context_trace.get('files_accessed') or [],
                        'commands_ran': [],
                        'applied_files': [],
                        'error': str(exc),
                    }
            else:
                try:
                    if chat_state == CHAT_STATE_NEEDS_CLARIFICATION and chat_decision.get('response'):
                        ai_response = str(chat_decision.get('response') or '')
                        assistant_trace = {
                            'approach': 'Paused for human clarification because the requested UI surface was ambiguous.',
                            'chat_state': chat_state,
                            'chat_mode': explicit_chat_mode or CHAT_MODE_ASK,
                            'state_reason': chat_decision.get('reason'),
                            'session_id': session_id,
                            'context_mentions': context_trace.get('context_mentions') or [],
                            'context_sources': list(context_trace.get('context_sources') or []) + [
                                {'label': '@clarification-needed', 'detail': 'Asked the user to clarify which UI surface they want to change before suggesting edits.'}
                            ],
                            'files_accessed': context_trace.get('files_accessed') or [],
                            'commands_ran': [],
                            'awaiting_clarification': True,
                            'semantic_hits': [
                                {
                                    'path': item.get('file_path'),
                                    'symbol': item.get('symbol'),
                                }
                                for item in (memory_context.get('semantic_hits') or [])[:8]
                            ],
                        }
                    elif chat_state == CHAT_STATE_GROUNDED_ANSWER and chat_decision.get('mode') == 'deterministic_ui_style' and chat_decision.get('response'):
                        ai_response = str(chat_decision.get('response') or '')
                        assistant_trace = {
                            'approach': 'Answered directly from deterministic UI style evidence extracted from retrieved files.',
                            'chat_state': chat_state,
                            'chat_mode': explicit_chat_mode or CHAT_MODE_ASK,
                            'state_reason': chat_decision.get('reason'),
                            'session_id': session_id,
                            'context_mentions': context_trace.get('context_mentions') or [],
                            'context_sources': list(context_trace.get('context_sources') or []) + [
                                {'label': '@ui-style-evidence', 'detail': 'Extracted exact class strings for the requested UI styling question.'}
                            ],
                            'files_accessed': context_trace.get('files_accessed') or [],
                            'commands_ran': [],
                            'semantic_hits': [
                                {
                                    'path': item.get('file_path'),
                                    'symbol': item.get('symbol'),
                                }
                                for item in (memory_context.get('semantic_hits') or [])[:8]
                            ],
                        }
                    else:
                        from agents.base import BaseAgent

                        system_instruction, prompt = _build_chat_llm_prompt(
                            project,
                            request_text,
                            attachments,
                            selected_file,
                            selected_content,
                            session_id,
                            context_trace,
                            memory_context,
                            resolved_context_text,
                            explicit_chat_mode,
                            chat_state,
                            str(chat_decision.get('response_contract') or ''),
                        )
                        agent = BaseAgent(
                            role="DevHub AI Assistant",
                            system_instruction=system_instruction,
                            ai_config=_project_ai_config(project),
                        )
                        ai_response = agent.generate_with_attachments(prompt, attachments) if attachments else agent.generate(prompt)
                        assistant_trace = {
                            'approach': context_trace.get('approach') or 'Answered the question using project memory, semantic recall, and explicit workspace context.',
                            'chat_state': chat_state,
                            'chat_mode': explicit_chat_mode or CHAT_MODE_ASK,
                            'state_reason': chat_decision.get('reason'),
                            'session_id': session_id,
                            'context_mentions': context_trace.get('context_mentions') or [],
                            'context_sources': context_trace.get('context_sources') or [],
                            'files_accessed': context_trace.get('files_accessed') or [],
                            'commands_ran': [],
                            'semantic_hits': [
                                {
                                    'path': item.get('file_path'),
                                    'symbol': item.get('symbol'),
                                }
                                for item in (memory_context.get('semantic_hits') or [])[:8]
                            ],
                        }
                except Exception as exc:
                    logger.exception("Chat assistant response failed for project %s", project.id)
                    ai_response = f"AI agent unavailable ({str(exc)}). Check the configured DevHub AI provider settings to enable chat."
                    assistant_trace = {
                        'approach': context_trace.get('approach') or 'Tried to answer using workspace context.',
                        'chat_state': chat_state,
                        'chat_mode': explicit_chat_mode or CHAT_MODE_ASK,
                        'state_reason': chat_decision.get('reason'),
                        'session_id': session_id,
                        'context_mentions': context_trace.get('context_mentions') or [],
                        'context_sources': context_trace.get('context_sources') or [],
                        'files_accessed': context_trace.get('files_accessed') or [],
                        'commands_ran': [],
                        'error': str(exc),
                    }

            try:
                assistant_metadata = dict(assistant_trace or {})
                assistant_metadata['session_id'] = session_id
                ChatMessage.objects.create(project=project, role='assistant', content=ai_response, metadata=assistant_metadata)
            except Exception:
                logger.exception("Failed to persist assistant chat message for project %s", project.id)
            _, sessions = _group_project_chat_sessions(project)
            return JsonResponse({
                'user_message': content,
                'assistant_message': ai_response,
                'applied_changes': applied_changes,
                'workspace_actions': workspace_actions,
                'trace': assistant_trace,
                'session_id': session_id,
                'sessions': sessions,
            })
        except Exception as exc:
            if chat_checkpoint:
                delete_workspace_checkpoint(str(project.id), str(chat_checkpoint.get('id') or ''))
            logger.exception("Unhandled project_chat failure for project %s", project.id)
            fallback = f"Chat request failed unexpectedly: {str(exc)}"
            if content:
                try:
                    ChatMessage.objects.create(project=project, role='assistant', content=fallback, metadata={'error': str(exc), 'session_id': session_id or LEGACY_CHAT_SESSION_ID})
                except Exception:
                    logger.exception("Failed to persist fallback assistant message for project %s", project.id)
            return JsonResponse({
                'user_message': content,
                'assistant_message': fallback,
                'applied_changes': None,
                'trace': {'error': str(exc), 'session_id': session_id or None},
                'session_id': session_id or None,
            })

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def project_chat_undo(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValidationError, ValueError):
        return JsonResponse({'error': 'Project not found'}, status=404)

    if not project.workspace_id:
        return JsonResponse({'error': 'Project has no active workspace'}, status=400)

    checkpoint_to_cleanup = None
    try:
        body = _parse_json_body(request)
        session_id = str(body.get('session_id') or '').strip() or str(uuid.uuid4())
        changeset_id = str(body.get('changeset_id') or '').strip()
        if not changeset_id:
            return JsonResponse({'error': 'changeset_id is required'}, status=400)

        target_changeset = _changeset_by_id(project, changeset_id)
        if not target_changeset:
            return JsonResponse({'error': 'Changeset not found'}, status=404)

        target_source = str((target_changeset.ai_review or {}).get('source') or '')
        if not target_source.startswith('chat'):
            return JsonResponse({'error': 'Only chat-driven changes can be undone from workspace chat.'}, status=400)

        undo_payload = _chat_undo_payload_from_review(str(target_changeset.id), target_changeset.ai_review)
        if not undo_payload or not undo_payload.get('checkpoint_id'):
            return JsonResponse({'error': 'This changeset does not have a stored checkpoint.'}, status=400)
        if not undo_payload.get('available'):
            return JsonResponse({'error': 'Undo is no longer available for this changeset.'}, status=400)

        workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
        checkpoint_to_cleanup = create_workspace_checkpoint(
            str(project.id),
            workspace_path,
            label=f"Undo restore for {target_changeset.title}"[:160],
            source='chat_undo',
        )
        restore_result = restore_workspace_checkpoint(
            str(project.id),
            workspace_path,
            str(undo_payload.get('checkpoint_id') or ''),
        )
        restored_files = list(restore_result.get('restored_files') or [])

        workspace_actions = [
            {
                'type': 'undo_restore',
                'status': 'completed',
                'detail': (
                    'Restored the workspace to the checkpoint captured before the selected chat execution.'
                    if restored_files
                    else 'The workspace already matched the selected checkpoint.'
                ),
            }
        ]

        if restored_files:
            undo_changeset = _record_chat_changes(
                project,
                f"Undo chat execution: {target_changeset.title}",
                workspace_path,
                snapshot_previous_contents(str(project.id), str(checkpoint_to_cleanup.get('id') or ''), restored_files),
                restored_files,
                ai_review=_chat_checkpoint_review_payload(
                    checkpoint_to_cleanup,
                    source='chat_undo',
                    chat_mode=str((target_changeset.ai_review or {}).get('chat_mode') or CHAT_MODE_EDIT),
                    undo_label='Undo Restore',
                ),
            )
            _mark_changeset_undone(target_changeset, undo_changeset)
            _update_project_memory(project, workspace_path, f"Undo chat execution: {target_changeset.title}", restored_files, ['Restored the workspace to the pre-change checkpoint.'])
            index_semantic_memory(project, workspace_path, changed_paths=restored_files)
            record_episode(
                project=project,
                memory_type='implementation',
                title='Undo workspace chat execution',
                summary=f"Restored the workspace to the checkpoint for '{target_changeset.title}'. Files: {', '.join(restored_files)}.",
                related_files=restored_files,
                metadata={'source': 'chat_undo', 'target_changeset_id': str(target_changeset.id)},
            )
            upsert_working_memory(
                project,
                'implementation',
                (
                    f"Latest implementation request: Undo chat execution: {target_changeset.title}\n"
                    f"Files touched: {', '.join(restored_files)}\n"
                    "Validation summary:\nRestored from a stored workspace checkpoint.\n"
                    "Reviewer summary: Undo completed successfully."
                ),
                {'latest_request': f"Undo chat execution: {target_changeset.title}", 'files': restored_files, 'source': 'chat_undo'},
            )
            applied_changes = {
                'applied_files': restored_files,
                'count': len(restored_files),
                'changeset_id': str(undo_changeset.id) if undo_changeset else None,
                'undo': _chat_changeset_trace_metadata(undo_changeset).get('undo') if undo_changeset else None,
            }
            assistant_trace = {
                'approach': 'Restored the workspace to the checkpoint captured immediately before the selected chat execution.',
                'chat_state': 'undo_restore',
                'chat_mode': str((target_changeset.ai_review or {}).get('chat_mode') or CHAT_MODE_EDIT),
                'state_reason': 'Undo restored the workspace from the pre-change checkpoint.',
                'session_id': session_id,
                'context_mentions': [],
                'context_sources': [],
                'files_accessed': [{'path': item, 'reason': 'Restored from checkpoint'} for item in restored_files[:12]],
                'commands_ran': [],
                'workspace_actions': workspace_actions,
                'applied_files': restored_files,
            }
            if undo_changeset:
                assistant_trace.update(_chat_changeset_trace_metadata(undo_changeset))
            assistant_message = (
                f"Restored the workspace to the checkpoint before that chat change, reverting {len(restored_files)} file(s): "
                f"{', '.join(restored_files[:6])}."
            )
        else:
            _mark_changeset_undone(target_changeset, None)
            delete_workspace_checkpoint(str(project.id), str(checkpoint_to_cleanup.get('id') or ''))
            checkpoint_to_cleanup = None
            applied_changes = None
            assistant_trace = {
                'approach': 'Compared the current workspace against the stored pre-change checkpoint and found no differences to restore.',
                'chat_state': 'undo_restore',
                'chat_mode': str((target_changeset.ai_review or {}).get('chat_mode') or CHAT_MODE_EDIT),
                'state_reason': 'Undo checkpoint matched the current workspace already.',
                'session_id': session_id,
                'context_mentions': [],
                'context_sources': [],
                'files_accessed': [],
                'commands_ran': [],
                'workspace_actions': workspace_actions,
                'applied_files': [],
            }
            assistant_message = 'The workspace already matches that checkpoint, so there was nothing to restore.'

        assistant_metadata = dict(assistant_trace or {})
        assistant_metadata['session_id'] = session_id
        ChatMessage.objects.create(project=project, role='assistant', content=assistant_message, metadata=assistant_metadata)
        _, sessions = _group_project_chat_sessions(project)
        return JsonResponse({
            'assistant_message': assistant_message,
            'applied_changes': applied_changes,
            'workspace_actions': workspace_actions,
            'trace': assistant_trace,
            'session_id': session_id,
            'sessions': sessions,
        })
    except Exception as exc:
        if checkpoint_to_cleanup:
            delete_workspace_checkpoint(str(project.id), str(checkpoint_to_cleanup.get('id') or ''))
        logger.exception("Chat undo failed for project %s", project.id)
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def start_agent(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
        body = _parse_json_body(request)
        agent_type = body.get('agent_type', 'architect')

        agent_run = AgentRun.objects.create(project=project, agent_type=agent_type, status='running', logs=[{'step': 'started', 'message': f'{agent_type} agent initiated'}])

        if agent_type == 'architect':
            generate_blueprint_sync(project)
            agent_run.status = 'completed'
            agent_run.logs.append({'step': 'completed', 'message': 'Blueprint generated successfully'})
        elif agent_type == 'documentation':
            documentation_run = generate_codebase_reference_sync(project)
            if documentation_run.status == 'failed':
                agent_run.status = 'failed'
                agent_run.logs.append({'step': 'failed', 'message': documentation_run.error or 'Documentation generation failed'})
            else:
                agent_run.status = 'completed'
                agent_run.logs.append({'step': 'completed', 'message': 'Documentation generated successfully'})
        else:
            agent_run.status = 'completed'
            agent_run.logs.append({'step': 'completed', 'message': f'{agent_type} agent finished'})

        agent_run.save()

        return JsonResponse({'id': str(agent_run.id), 'agent_type': agent_run.agent_type, 'status': agent_run.status, 'logs': agent_run.logs})
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def deep_documentation_progress(request, project_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)

    workspace_path = Path(project.local_path) if project.local_path else None
    if not workspace_path or not workspace_path.is_dir():
        return JsonResponse({'error': 'Project has no valid workspace path'}, status=400)

    payload = _read_deep_docs_progress(workspace_path) or {
        'section_key': 'idle',
        'section_label': 'Idle',
        'status': 'idle',
        'progress_pct': 0,
        'total_sections': 7,
        'completed_sections': 0,
        'section_data': {},
    }
    return JsonResponse(payload)


@csrf_exempt
def deep_documentation_stream(request, project_id):
    """SSE endpoint that generates either the full Blueprint or one requested section."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)

    from django.http import StreamingHttpResponse
    from agents.deep_documentation import DeepDocumentationAgent

    workspace_path = Path(project.local_path) if project.local_path else None
    if not workspace_path or not workspace_path.is_dir():
        return JsonResponse({'error': 'Project has no valid workspace path'}, status=400)

    body = _parse_json_body(request)
    requested_section = str(body.get('section_key') or '').strip().lower()
    if requested_section and requested_section not in BLUEPRINT_SECTION_FIELDS:
        return JsonResponse({'error': f'Unsupported Blueprint section: {requested_section}'}, status=400)

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def event_stream():
        total_sections = 1 if requested_section else 7
        completion_label = (
            f"{BLUEPRINT_SECTION_LABELS.get(requested_section, requested_section)} complete"
            if requested_section
            else 'Blueprint complete'
        )
        initial_event = {
            'section_key': 'build_context',
            'section_label': 'Preparing codebase context',
            'status': 'started',
            'progress_pct': 0,
            'total_sections': total_sections,
            'completed_sections': 0,
            'section_data': {},
        }
        _safe_write_deep_docs_progress(workspace_path, initial_event)
        yield _sse(initial_event)

        try:
            codebase_context = build_blueprint_context(project, workspace_path, force=True)
        except Exception as exc:
            logger.exception("Failed to build blueprint context for project %s", project_id)
            failure_event = {
                'section_key': 'build_context',
                'section_label': 'Preparing codebase context',
                'status': 'failed',
                'progress_pct': 0,
                'total_sections': total_sections,
                'completed_sections': 0,
                'section_data': {'_error': str(exc)},
                'error': str(exc),
            }
            _safe_write_deep_docs_progress(workspace_path, failure_event)
            yield _sse(failure_event)
            return

        if not codebase_context:
            message = 'Could not build codebase context. Ensure the project has indexed files.'
            failure_event = {
                'section_key': 'build_context',
                'section_label': 'Preparing codebase context',
                'status': 'failed',
                'progress_pct': 0,
                'total_sections': total_sections,
                'completed_sections': 0,
                'section_data': {'_error': message},
                'error': message,
            }
            _safe_write_deep_docs_progress(workspace_path, failure_event)
            yield _sse(failure_event)
            return

        context_ready_event = {
            'section_key': 'build_context',
            'section_label': 'Codebase context ready',
            'status': 'completed',
            'progress_pct': 1,
            'total_sections': total_sections,
            'completed_sections': 0,
            'section_data': {},
        }
        _safe_write_deep_docs_progress(workspace_path, context_ready_event)
        yield _sse(context_ready_event)

        import queue as _queue_mod
        from agents.observability import AgentObserver
        _live_queue: _queue_mod.Queue = _queue_mod.Queue()
        observer = AgentObserver(str(project_id), live_queue=_live_queue)
        agent = DeepDocumentationAgent(ai_config=_project_ai_config(project), observer=observer)
        feature_summary = _render_project_features_summary(project, limit=20)

        def _persist_section_update(section_key: str, section_data: dict[str, Any]) -> dict[str, Any]:
            close_old_connections()
            project.refresh_from_db()
            current_bp = dict(project.blueprint or {})
            for key, value in section_data.items():
                if key != '_error':
                    current_bp[key] = value
            refreshed = _enrich_blueprint_document(project, current_bp, codebase_context, feature_summary)
            if isinstance(refreshed, dict):
                refreshed["_meta"] = {
                    "codebase_fingerprint": codebase_context.get("fingerprint") if isinstance(codebase_context, dict) else None,
                    "indexed_files": codebase_context.get("file_count") if isinstance(codebase_context, dict) else None,
                    "cached": True if codebase_context else False,
                }
            _persist_blueprint_state(project, refreshed)
            if section_key in BLUEPRINT_SECTION_FIELDS:
                return _slice_blueprint_section(refreshed, section_key)
            return dict(section_data or {})

        if requested_section:
            started_event = {
                'section_key': requested_section,
                'section_label': BLUEPRINT_SECTION_LABELS.get(requested_section, requested_section),
                'section_data': {},
                'progress_pct': 5,
                'status': 'started',
                'total_sections': total_sections,
                'completed_sections': 0,
            }
            _safe_write_deep_docs_progress(workspace_path, started_event)
            yield _sse(started_event)

            try:
                project.refresh_from_db()
                current_bp = dict(project.blueprint or {})
                if requested_section in TOKEN_FREE_BLUEPRINT_SECTION_KEYS:
                    refreshed = _enrich_blueprint_document(project, current_bp, codebase_context, feature_summary)
                    if isinstance(refreshed, dict):
                        refreshed["_meta"] = {
                            "codebase_fingerprint": codebase_context.get("fingerprint") if isinstance(codebase_context, dict) else None,
                            "indexed_files": codebase_context.get("file_count") if isinstance(codebase_context, dict) else None,
                            "cached": True if codebase_context else False,
                        }
                    _persist_blueprint_state(project, refreshed)
                    section_data = _slice_blueprint_section(refreshed, requested_section)
                else:
                    section_data = agent.generate_section(
                        requested_section,
                        project.name,
                        codebase_context,
                        workspace_path,
                        existing_blueprint=current_bp,
                    )
                    section_data = _persist_section_update(requested_section, section_data)
            except Exception as exc:
                logger.exception("Failed to generate section %s for project %s", requested_section, project_id)
                failed_event = {
                    'section_key': requested_section,
                    'section_label': BLUEPRINT_SECTION_LABELS.get(requested_section, requested_section),
                    'section_data': {'_error': str(exc)},
                    'progress_pct': 100,
                    'status': 'failed',
                    'total_sections': total_sections,
                    'completed_sections': 1,
                    'error': str(exc),
                }
                _safe_write_deep_docs_progress(workspace_path, failed_event)
                yield _sse(failed_event)
                return

            completed_event = {
                'section_key': requested_section,
                'section_label': BLUEPRINT_SECTION_LABELS.get(requested_section, requested_section),
                'section_data': section_data,
                'progress_pct': 100,
                'status': 'completed',
                'total_sections': total_sections,
                'completed_sections': 1,
            }
            _safe_write_deep_docs_progress(workspace_path, completed_event)
            yield _sse(completed_event)
        else:
            import concurrent.futures as _cf
            import queue as _queue
            from agents.deep_documentation import SECTION_ORDER as _SECTION_ORDER, SECTION_LABELS as _SECTION_LABELS

            _existing_bp = dict(project.blueprint or {})
            _results: dict[str, dict] = {}
            _result_q: _queue.Queue = _queue.Queue()
            _total = len(_SECTION_ORDER)

            def _run_one(sk: str, idx: int):
                try:
                    data = agent.generate_section(
                        sk, project.name, codebase_context, workspace_path, existing_blueprint=_existing_bp
                    )
                    if isinstance(data, dict) and data.get('_error'):
                        status = 'failed'
                    else:
                        data = agent._run_validators(sk, data, workspace_path, cache=codebase_context)
                        status = 'completed'
                except Exception as exc:
                    data = {'_error': str(exc)}
                    status = 'failed'
                _result_q.put({
                    'section_key': sk,
                    'section_label': _SECTION_LABELS.get(sk, sk),
                    'section_data': data,
                    'progress_pct': int(((idx + 1) / _total) * 100),
                    'status': status,
                    'total_sections': _total,
                    'agent_events': agent.observer.events_for_section(sk) if agent.observer else [],
                })

            # Emit started events for all sections first
            for idx, sk in enumerate(_SECTION_ORDER):
                started_evt = {
                    'section_key': sk, 'section_label': _SECTION_LABELS.get(sk, sk),
                    'section_data': {}, 'progress_pct': int((idx / _total) * 100),
                    'status': 'started', 'total_sections': _total, 'completed_sections': idx,
                }
                yield _sse(started_evt)

            with _cf.ThreadPoolExecutor(max_workers=min(len(_SECTION_ORDER), 4)) as pool:
                futs = [pool.submit(_run_one, sk, idx) for idx, sk in enumerate(_SECTION_ORDER)]
                completed_count = 0
                while completed_count < len(futs):
                    # Drain live observer events first — stream them immediately to the client
                    while True:
                        try:
                            live_evt = _live_queue.get_nowait()
                            yield _sse({'type': 'agent_event', 'event': live_evt})
                        except _queue.Empty:
                            break

                    # Check for a completed section (short timeout to keep live events flowing)
                    try:
                        event = _result_q.get(timeout=0.3)
                    except _queue.Empty:
                        continue
                    completed_count += 1
                    section_data = dict(event.get('section_data') or {})
                    sk = str(event.get('section_key') or '')
                    if event.get('status') != 'started':
                        try:
                            section_data = _persist_section_update(sk, section_data)
                        except Exception:
                            logger.exception("Failed to persist section %s for project %s", sk, project_id)
                    sse_payload = {
                        'section_key': sk,
                        'section_label': event.get('section_label'),
                        'section_data': section_data,
                        'progress_pct': event.get('progress_pct'),
                        'status': event.get('status'),
                        'total_sections': _total,
                        'completed_sections': completed_count,
                        'agent_events': event.get('agent_events') or [],
                    }
                    _safe_write_deep_docs_progress(workspace_path, sse_payload)
                    yield _sse(sse_payload)

        done_event = {
            'status': 'done',
            'section_key': 'complete',
            'section_label': completion_label,
            'progress_pct': 100,
            'total_sections': total_sections,
            'completed_sections': total_sections,
            'section_data': {},
        }
        _safe_write_deep_docs_progress(workspace_path, done_event)
        yield _sse(done_event)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Access-Control-Allow-Origin'] = '*'
    return response



@csrf_exempt
def workspace_fs(request, workspace_id):
    try:
        workspace_path = workspace_manager.get_workspace_path(workspace_id)
        if request.method == 'GET':
            rel_path = request.GET.get('path', '')
            target_path = workspace_path / rel_path
            target_path.resolve().relative_to(workspace_path.resolve())
            if not target_path.exists():
                return JsonResponse({'error': 'Path not found'}, status=404)
            if target_path.is_file():
                content = target_path.read_text(encoding='utf-8', errors='replace')
                return JsonResponse({'type': 'file', 'content': content})

            items = []
            for entry in os.scandir(target_path):
                if entry.name in SKIP_DIRS or entry.name == '.env':
                    continue
                items.append({
                    'name': entry.name,
                    'type': 'directory' if entry.is_dir() else 'file',
                    'path': os.path.relpath(entry.path, workspace_path).replace('\\', '/'),
                })
            items.sort(key=lambda item: (item['type'] == 'file', item['name'].lower()))
            return JsonResponse({'type': 'directory', 'items': items})

        if request.method == 'POST':
            body = _parse_json_body(request)
            rel_path = body.get('path')
            content = body.get('content', '')
            if not rel_path:
                return JsonResponse({'error': 'Path is required'}, status=400)
            workspace_manager.write_file(workspace_id, rel_path, content)
            return JsonResponse({'status': 'success'})
    except PermissionError as exc:
        return JsonResponse({'error': str(exc)}, status=403)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def workspace_spawn(request, workspace_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        from sandbox.executor import sandbox

        body = _parse_json_body(request)
        command = body.get('command')
        if not command:
            return JsonResponse({'error': 'Command is required'}, status=400)
        workspace_path = workspace_manager.get_workspace_path(workspace_id)
        process_id = f"{workspace_id}_{command.split()[0]}"
        sandbox.run_command(process_id, command, str(workspace_path), kind='terminal')
        return JsonResponse({'status': 'success', 'process_id': process_id, 'sandbox': sandbox.details()})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def workspace_process_io(request, workspace_id, process_id):
    from sandbox.executor import sandbox

    if request.method == 'GET':
        lines = sandbox.get_output(process_id)
        return JsonResponse({'output': ''.join(lines), 'status': sandbox.get_status(process_id)})

    if request.method == 'POST':
        try:
            body = _parse_json_body(request)
            sandbox.send_input(process_id, body.get('input', ''))
            return JsonResponse({'status': 'success'})
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)

    if request.method == 'DELETE':
        sandbox.kill_process(process_id)
        return JsonResponse({'status': 'killed'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def workspace_runtime(request, workspace_id):
    from sandbox.executor import sandbox

    try:
        workspace_path = workspace_manager.get_workspace_path(workspace_id)
        runtime = detect_runtime(workspace_path)
        process_id = runtime_process_id(workspace_id)

        if request.method == 'GET':
            return JsonResponse(_runtime_response_payload(runtime, process_id, sandbox))

        if request.method == 'POST':
            body = _parse_json_body(request)
            command = body.get('command') or runtime.get('run_command')
            if not command:
                return JsonResponse({'error': 'No runtime command detected for this project'}, status=400)
            current_status = sandbox.get_status(process_id)
            if current_status.get('running'):
                command_changed = current_status.get('command') != command
                unhealthy_preview = False
                if runtime.get('preview_url'):
                    healthy, _ = _probe_preview_url(runtime['preview_url'])
                    unhealthy_preview = not healthy
                if command_changed or unhealthy_preview:
                    sandbox.kill_process(process_id)
            sandbox.run_command(
                process_id,
                command,
                str(workspace_path),
                kind='runtime',
                preview_url=runtime.get('preview_url'),
            )
            payload = _runtime_response_payload(runtime, process_id, sandbox, wait_for_preview=True)
            return JsonResponse(payload, status=200)

        if request.method == 'DELETE':
            sandbox.kill_process(process_id)
            return JsonResponse({'status': 'stopped', 'process_id': process_id})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def workspace_setup(request, workspace_id):
    from sandbox.executor import sandbox

    try:
        workspace_path = workspace_manager.get_workspace_path(workspace_id)
        runtime = detect_runtime(workspace_path)
        process_id = setup_process_id(workspace_id)

        if request.method == 'GET':
            return JsonResponse({
                'process_id': process_id,
                'command': runtime.get('setup_command'),
                'status': sandbox.get_status(process_id),
                'sandbox': sandbox.details(),
            })

        if request.method == 'POST':
            body = _parse_json_body(request)
            command = body.get('command') or runtime.get('setup_command')
            if not command:
                return JsonResponse({'error': 'No setup command detected for this project'}, status=400)
            sandbox.run_command(process_id, command, str(workspace_path), kind='setup')
            return JsonResponse({
                'process_id': process_id,
                'command': command,
                'status': sandbox.get_status(process_id),
                'sandbox': sandbox.details(),
            })

        if request.method == 'DELETE':
            sandbox.kill_process(process_id)
            return JsonResponse({'status': 'stopped', 'process_id': process_id})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)
