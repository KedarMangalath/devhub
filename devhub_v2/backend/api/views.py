import json
import hashlib
import logging
import os
import shutil
import subprocess
import threading
import time
from difflib import unified_diff
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError, close_old_connections
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from agents.memory import build_memory_context, compress_recent_activity, index_semantic_memory, record_episode, upsert_working_memory
from agents.workspace import PROJECTS_DIR, SKIP_DIRS, workspace_manager
from core.models import AgentRun, Changeset, ChatMessage, EpisodicMemory, Feature, FeatureApproval, FeatureHistory, FileDiff, Project, SemanticMemory, TestResult, WorkingMemory

PIPELINE_STAGES = ['backlog', 'development', 'testing', 'code_review', 'staging']
logger = logging.getLogger(__name__)
DEVHUB_META_DIR = ".devhub"
PROJECT_MEMORY_FILE = "project-memory.md"
MEMORY_DB_ERRORS = (OperationalError, ProgrammingError)


def _parse_json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body)


def _normalize_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def _managed_project_root(project: Project) -> Path:
    return PROJECTS_DIR / str(project.id)


def _project_tokens(project: Project) -> set[str]:
    tokens = set()
    for item in [*(project.tech_stack or []), project.name or "", project.description or ""]:
        for token in re.split(r'[\s,/+]+', str(item).strip().lower()):
            if token:
                tokens.add(token)
    return tokens


def _project_slug(project: Project) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', (project.name or 'devhub-app').lower()).strip('-')
    return slug or 'devhub-app'


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


def _react_scaffold_files(project: Project) -> dict:
    title = project.name or "DevHub App"
    description = _display_description(project)
    package_name = _project_slug(project)

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
        "src/App.jsx": f"""const highlights = [
  {{
    title: 'Working skeleton',
    description: 'This project was generated with a real runnable React starter so you can iterate immediately.',
  }},
  {{
    title: 'Chat-driven edits',
    description: 'Ask DevHub to change components, layout, copy, or interactions and it can write those files for you.',
  }},
  {{
    title: 'Feature pipeline',
    description: 'Track larger work items through planning, implementation, testing, and review.',
  }},
];

export default function App() {{
  return (
    <div className="page-shell">
      <section className="hero-card">
        <span className="eyebrow">DevHub React Starter</span>
        <h1>{title}</h1>
        <p className="description">{description}</p>
        <div className="hero-actions">
          <button type="button">Create a feature</button>
          <button type="button" className="secondary">Update the UI with chat</button>
        </div>
      </section>

      <section className="highlight-grid">
        {{highlights.map((item) => (
          <article key={{item.title}} className="highlight-card">
            <span className="pill">{{item.title}}</span>
            <p>{{item.description}}</p>
          </article>
        ))}}
      </section>

      <section className="status-card">
        <div>
          <span className="eyebrow">Starter Status</span>
          <h2>Ready for code changes</h2>
          <p>Run the app, keep the preview open, and evolve this skeleton through feature additions or direct chat instructions.</p>
        </div>
        <div className="terminal-card">
          <p>$ npm install</p>
          <p>$ npm run dev</p>
          <p>Server ready on http://127.0.0.1:4173</p>
        </div>
      </section>
    </div>
  );
}}
""",
        "src/styles.css": """* {
  box-sizing: border-box;
}

:root {
  color: #102033;
  background:
    radial-gradient(circle at top right, rgba(217, 119, 6, 0.24), transparent 24%),
    linear-gradient(180deg, #fffaf2 0%, #f4efe7 100%);
  font-family: 'Segoe UI', sans-serif;
}

body {
  margin: 0;
  min-height: 100vh;
}

button {
  border: none;
  border-radius: 999px;
  padding: 0.85rem 1.2rem;
  font: inherit;
  cursor: pointer;
  background: #c05621;
  color: white;
  box-shadow: 0 14px 24px rgba(192, 86, 33, 0.22);
}

button.secondary {
  background: rgba(16, 32, 51, 0.08);
  color: #102033;
  box-shadow: none;
}

.page-shell {
  width: min(1120px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 40px 0 64px;
}

.hero-card,
.highlight-card,
.status-card {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(16, 32, 51, 0.12);
  border-radius: 28px;
  box-shadow: 0 24px 64px rgba(16, 32, 51, 0.08);
}

.hero-card {
  padding: 32px;
}

.eyebrow,
.pill {
  display: inline-block;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.75rem;
  color: #c05621;
}

.hero-card h1 {
  margin: 0.6rem 0 0;
  font-size: clamp(3rem, 7vw, 5.2rem);
  line-height: 0.95;
}

.description,
.highlight-card p,
.status-card p {
  color: #5b6678;
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 24px;
}

.highlight-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin: 18px 0;
}

.highlight-card {
  padding: 22px;
}

.status-card {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 1fr);
  gap: 20px;
  padding: 24px;
}

.terminal-card {
  border-radius: 22px;
  background: #111827;
  color: #dbe6ff;
  font-family: Consolas, monospace;
  padding: 20px;
}

.terminal-card p {
  margin: 0 0 0.7rem;
  color: inherit;
}

@media (max-width: 720px) {
  .page-shell {
    width: min(100vw - 20px, 1120px);
    padding-top: 20px;
  }

  .hero-card,
  .highlight-card,
  .status-card {
    border-radius: 22px;
  }

  .hero-card {
    padding: 24px;
  }

  .status-card {
    grid-template-columns: 1fr;
  }
}
""",
        "README.md": f"""# {title}

{description}

## Run locally

```bash
npm install
npm run dev
```

Then open [http://127.0.0.1:4173](http://127.0.0.1:4173).
""",
        ".gitignore": "node_modules/\ndist/\n.vite/\n",
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


def build_scaffold_files(project: Project) -> dict:
    tokens = _project_tokens(project)

    if 'react' in tokens or 'vite' in tokens:
        files = _react_scaffold_files(project)
    elif 'fastapi' in tokens:
        files = _fastapi_scaffold_files(project)
    elif 'django' in tokens:
        files = _django_scaffold_files(project)
    else:
        files = _static_scaffold_files(project)

    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return files

    try:
        from agents.scaffolder import ScaffolderAgent

        agent = ScaffolderAgent()
        scaffold = agent.generate_scaffold(
            description=(
                f"Create a small but working starter application for {project.name}. "
                f"Description: {_display_description(project)}. "
                "The starter must be runnable immediately after setup, include a visible UI, "
                "and support future edits from an AI coding assistant."
            ),
            tech_stack=", ".join(project.tech_stack or []) or "HTML, CSS, JavaScript",
        )
        ai_files = _safe_scaffold_files({
            item.get('path'): item.get('content')
            for item in scaffold.get('files', [])
            if isinstance(item, dict) and item.get('path') and item.get('content') is not None
        })
        if ai_files:
            protected_files = {
                'package.json',
                'vite.config.js',
                'vite.config.ts',
                'requirements.txt',
                'main.py',
                'manage.py',
                'index.html',
                'src/main.jsx',
                'src/main.js',
            }
            for rel_path, content in ai_files.items():
                if rel_path in protected_files and rel_path in files:
                    continue
                files[rel_path] = content
    except Exception:
        pass

    return files


def scaffold_project(project: Project, project_root: Path):
    project_root.mkdir(parents=True, exist_ok=True)
    if any(project_root.iterdir()):
        return

    files = build_scaffold_files(project)

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


def _python_executable_command() -> str:
    return f'"{sys.executable}"'


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


def detect_runtime(project_root: Path) -> dict:
    package_json_path = project_root / "package.json"
    if package_json_path.exists():
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

        return {
            "label": package_json.get("name") or project_root.name,
            "runtime_type": "node",
            "entrypoint": "package.json",
            "run_command": run_command,
            "setup_command": "npm install",
            "install_required": not (project_root / "node_modules").exists(),
            "preview_url": _preview_url_for_command(run_command),
        }

    if (project_root / "manage.py").exists():
        requirements_file = project_root / "requirements.txt"
        python_cmd = _python_executable_command()
        port = _stable_runtime_port(project_root, start=8100)
        return {
            "label": project_root.name,
            "runtime_type": "django",
            "entrypoint": "manage.py",
            "run_command": f"{python_cmd} manage.py runserver 127.0.0.1:{port}",
            "setup_command": f"{python_cmd} -m pip install -r requirements.txt" if requirements_file.exists() else None,
            "install_required": False,
            "preview_url": f"http://127.0.0.1:{port}",
        }

    if (project_root / "main.py").exists() or (project_root / "app.py").exists():
        entrypoint = "main.py" if (project_root / "main.py").exists() else "app.py"
        requirements_file = project_root / "requirements.txt"
        python_cmd = _python_executable_command()
        return {
            "label": project_root.name,
            "runtime_type": "python",
            "entrypoint": entrypoint,
            "run_command": f'{python_cmd} {entrypoint}',
            "setup_command": f"{python_cmd} -m pip install -r requirements.txt" if requirements_file.exists() else None,
            "install_required": False,
            "preview_url": _preview_url_for_command(f'{python_cmd} {entrypoint}'),
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
    payload = {**runtime, "process_id": process_id, "status": status, "ready": False, "preview_error": None}
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


def _devhub_meta_dir(workspace_path: Path) -> Path:
    path = workspace_path / DEVHUB_META_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _project_memory_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / PROJECT_MEMORY_FILE


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
    return "\n".join(lines) if lines else "No tracked features yet."


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


def _read_project_memory(project: Project, workspace_path: Path) -> str:
    memory_path = _project_memory_path(workspace_path)
    if not memory_path.exists():
        memory_path.write_text(_build_default_project_memory(project, workspace_path), encoding='utf-8')
    return memory_path.read_text(encoding='utf-8', errors='ignore')


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
) -> dict:
    file_inventory = _workspace_file_inventory(workspace_path)
    blueprint_summary = json.dumps(project.blueprint or {}, indent=2)[:3500] if project.blueprint else "No blueprint available."
    supporting_context = f"""Recent Features:
{_render_project_features_summary(project)}

Recent Changes:
{_render_recent_changes_summary(project)}

Recent Chat:
{_recent_chat_history(project)}

Memory Recall:
{memory_context_text or 'No additional memory recall available.'}
"""

    if not os.environ.get('OPENAI_API_KEY'):
        return _fallback_plan(selected_file, file_inventory, request_text)

    try:
        from agents.planner import PlannerAgent

        planner = PlannerAgent()
        plan = planner.create_plan(
            project_name=project.name,
            request_title=request_title,
            request_text=request_text,
            project_memory=project_memory[:12000],
            file_inventory=file_inventory[:12000],
            blueprint_summary=blueprint_summary,
            supporting_context=supporting_context[:8000],
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
    selected_file: str = "",
    selected_content: str = "",
    limit: int = 20,
) -> list[dict]:
    context = []
    seen = set()

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


def _build_supporting_context(project: Project, plan: dict, workspace_path: Path) -> str:
    runtime = detect_runtime(workspace_path)
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
"""


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


def _review_attempt(project: Project, workspace_path: Path, previous_contents: dict, applied_files: list[str], validation_results: list[dict]) -> dict:
    if not applied_files:
        return {
            'approved': True,
            'score': 100,
            'summary': 'No file changes were produced.',
            'issues': [],
        }

    if not os.environ.get('OPENAI_API_KEY'):
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

        reviewer = ReviewerAgent()
        return reviewer.review_changeset(
            changeset_diff=_build_review_diff(workspace_path, previous_contents, applied_files),
            tech_stack=", ".join(project.tech_stack or []),
            blueprint=json.dumps(project.blueprint or {}, indent=2)[:3000],
            evaluation_summary=_validation_summary(validation_results),
        )
    except Exception:
        logger.exception("ReviewerAgent failed for project %s", project.id)
        return {
            'approved': _all_validations_passed(validation_results),
            'score': 70 if _all_validations_passed(validation_results) else 45,
            'summary': _validation_summary(validation_results),
            'issues': [],
        }


def generate_blueprint_sync(project: Project):
    try:
        from agents.architect import ArchitectAgent

        local_scan = ""
        readme = ""
        if project.local_path and Path(project.local_path).is_dir():
            local_scan = scan_local_folder(project.local_path)
            readme_path = Path(project.local_path) / "README.md"
            if readme_path.exists():
                try:
                    readme = readme_path.read_text(encoding="utf-8", errors="ignore")[:3000]
                except Exception:
                    pass

        architect = ArchitectAgent()
        blueprint = architect.generate_blueprint(
            project_name=project.name,
            tech_stack=project.tech_stack or [],
            local_scan=local_scan,
            readme=readme,
        )
        project.blueprint = blueprint
        project.save()
    except Exception as exc:
        project.blueprint = {
            "architecture_overview": f"Blueprint generation failed: {str(exc)}. Set your OPENAI_API_KEY environment variable.",
            "tech_stack_details": [{"tech": t, "purpose": "Core technology"} for t in (project.tech_stack or [])],
            "services": [],
            "setup_steps": [],
            "gotchas": [str(exc)],
        }
        project.save()


def generate_feature_spec_sync(feature: Feature, project: Project):
    try:
        from agents.feature import FeatureAgent

        agent = FeatureAgent()
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
    memory_context = build_memory_context(project, request_text, selected_file=selected_file)
    memory_context_text = f"""Working Memory:
{memory_context.get('working_summary') or compressed_summary}

Episodic Memory:
{memory_context.get('episodic_summary')}

Semantic Memory:
{memory_context.get('semantic_summary')}
"""

    baseline_contents: dict[str, str] = {}
    agent = CoderAgent()
    attempt_logs = []
    all_applied_files: list[str] = []
    latest_plan = {}
    latest_review = {}
    latest_validation_results: list[dict] = []
    current_request_text = request_text

    for attempt in range(1, 4):
        plan = _create_implementation_plan(
            project=project,
            request_title=request_title,
            request_text=current_request_text,
            workspace_path=workspace_path,
            project_memory=f"{project_memory[:10000]}\n\n{memory_context_text[:4000]}",
            memory_context_text=memory_context_text,
            selected_file=selected_file,
        )
        latest_plan = plan

        files_context = _collect_relevant_files(
            workspace_path=workspace_path,
            plan=plan,
            selected_file=selected_file,
            selected_content=selected_content,
        )
        for item in files_context:
            baseline_contents.setdefault(item['path'], item['content'])

        supporting_context = (
            _build_supporting_context(project, plan, workspace_path)
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
            project_memory=project_memory[:12000],
            supporting_context=supporting_context[:10000],
        )

        if result.get("status") != "success":
            raise RuntimeError(result.get("error", "Failed to apply changes."))

        applied_files = result.get("files_modified", [])
        for rel_path in applied_files:
            if rel_path not in all_applied_files:
                all_applied_files.append(rel_path)

        latest_validation_results = _run_validation_suite(workspace_path)
        latest_review = _review_attempt(project, workspace_path, baseline_contents, all_applied_files, latest_validation_results)
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
            request_text,
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

    _record_chat_changes(project, request_text, workspace_path, baseline_contents, all_applied_files)
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

    if os.environ.get('OPENAI_API_KEY'):
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
        'improve', 'modify', 'redesign', 'refactor', 'remove', 'rename',
        'replace', 'restyle', 'update',
    )
    question_starts = ('what', 'why', 'how', 'explain', 'show', 'where', 'which')
    return any(re.search(rf'\b{verb}\b', lower) for verb in edit_verbs) and not lower.startswith(question_starts)


def _record_chat_changes(project: Project, request_text: str, workspace_path: Path, previous_contents: dict, applied_files: list[str]):
    if not applied_files:
        return

    changeset = Changeset.objects.create(
        project=project,
        title=(request_text[:252] + '...') if len(request_text) > 255 else request_text,
        description=request_text,
        status='approved',
        ai_review={'source': 'chat'},
    )

    for rel_path in applied_files:
        new_path = workspace_path / rel_path
        before = previous_contents.get(rel_path, "")
        after = ""
        action = 'modified'

        if new_path.exists():
            after = new_path.read_text(encoding='utf-8', errors='ignore')
            action = 'modified' if rel_path in previous_contents else 'added'
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


def apply_chat_changes(project: Project, request_text: str, selected_file: str = "", selected_content: str = "") -> dict:
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
    )
    return {
        "applied_files": result.get("applied_files", []),
        "count": result.get("count", 0),
        "plan": result.get("plan", {}),
    }


def run_ai_test_simulation(feature: Feature, tech_stack):
    try:
        from agents.base import BaseAgent

        agent = BaseAgent(
            role="QA Lead",
            system_instruction="You are a QA lead. Evaluate feature specs and simulate test results. Always return valid JSON.",
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


def list_projects(request):
    projects = Project.objects.all().order_by('-registered_at').values('id', 'name', 'description', 'status', 'tech_stack', 'registered_at', 'local_path')
    return JsonResponse({'projects': list(projects)})


@csrf_exempt
def create_project(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        body = _parse_json_body(request)
        name = body.get('name', '').strip()
        description = body.get('description', '').strip()
        local_path = body.get('local_path', '').strip()
        github_url = body.get('github_url', '').strip()
        tech_stack = body.get('tech_stack', [])

        if not name:
            return JsonResponse({'error': 'Project name is required'}, status=400)

        project = Project.objects.create(
            name=name,
            description=description,
            local_path=None,
            github_url=github_url or None,
            tech_stack=tech_stack,
        )

        if github_url:
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
            scaffold_project(project, project_root)
            project.local_path = str(project_root)
            project.workspace_id = workspace_manager.create_workspace(str(project_root), managed=True)
            project.save()

        try:
            workspace_path = Path(project.local_path)
            index_semantic_memory(project, workspace_path)
            compress_recent_activity(project)
            _read_project_memory(project, workspace_path)
        except MEMORY_DB_ERRORS:
            logger.warning("Memory tables are not ready yet for project %s", project.id)
        except Exception:
            logger.exception("Failed to initialize project memory for project %s", project.id)

        thread = threading.Thread(target=generate_blueprint_sync, args=(project,))
        thread.daemon = True
        thread.start()

        return JsonResponse({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'workspace_id': project.workspace_id,
            'status': 'ready',
            'runtime': detect_runtime(Path(project.local_path)),
        }, status=201)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


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
        if project.local_path and Path(project.local_path).is_dir():
            runtime = detect_runtime(Path(project.local_path))
            try:
                memory_exists = WorkingMemory.objects.filter(project=project, scope='implementation').exists()
            except MEMORY_DB_ERRORS:
                memory_exists = True
            if not memory_exists:
                try:
                    compress_recent_activity(project)
                except Exception:
                    logger.exception("Failed to refresh working memory for project %s", project.id)

        return JsonResponse({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'github_url': project.github_url,
            'local_path': project.local_path,
            'workspace_id': project.workspace_id,
            'tech_stack': project.tech_stack,
            'status': project.status,
            'blueprint': project.blueprint,
            'features': _project_features_payload(project),
            'runtime': runtime,
        })
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except (ValidationError, ValueError):
        return JsonResponse({'error': 'Invalid project ID'}, status=400)
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
        messages = list(ChatMessage.objects.filter(project=project).order_by('created_at').values('id', 'role', 'content', 'created_at'))
        return JsonResponse({'messages': messages})

    if request.method == 'POST':
        content = ''
        try:
            body = _parse_json_body(request)
            content = str(body.get('content') or '').strip()
            selected_file = str(body.get('selected_file') or '').strip()
            selected_content = str(body.get('selected_content') or '')
            apply_changes = body.get('apply_changes')
            if not content:
                return JsonResponse({'error': 'Message is required'}, status=400)

            ChatMessage.objects.create(project=project, role='user', content=content)

            should_apply_changes = _looks_like_edit_request(content) if apply_changes is None else bool(apply_changes)
            applied_changes = None

            if should_apply_changes and project.workspace_id:
                try:
                    applied_changes = apply_chat_changes(
                        project,
                        content,
                        selected_file=selected_file,
                        selected_content=selected_content,
                    )
                    applied_list = applied_changes['applied_files']
                    ai_response = (
                        "Applied the requested update directly to the project."
                        if not applied_list
                        else f"Applied the requested update to {len(applied_list)} file(s): {', '.join(applied_list)}."
                    )
                except Exception as exc:
                    logger.exception("Chat code application failed for project %s", project.id)
                    ai_response = f"I understood this as a code-change request, but the edit failed: {str(exc)}"
            else:
                try:
                    from agents.base import BaseAgent

                    blueprint = project.blueprint or {}
                    arch = json.dumps(blueprint.get('architecture_overview', ''))[:800]
                    tech = ", ".join(project.tech_stack) if project.tech_stack else "Unknown"
                    memory_context = build_memory_context(project, content, selected_file=selected_file)

                    recent = list(ChatMessage.objects.filter(project=project).order_by('-created_at')[:10].values('role', 'content'))
                    recent.reverse()
                    history_text = "\n".join([f"{message['role']}: {message['content']}" for message in recent])

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

                    agent = BaseAgent(
                        role="DevHub AI Assistant",
                        system_instruction=f"""You are the DevHub AI assistant for the project "{project.name}".
Tech Stack: {tech}
Architecture: {arch}
Working Memory: {memory_context.get('working_summary', '')[:1200]}
Episodic Memory: {memory_context.get('episodic_summary', '')[:1200]}

Help the developer plan and implement features, debug issues, and reason about the current code.
When relevant, use the active file context and keep answers action-oriented.""",
                    )
                    ai_response = agent.generate(
                        f"Chat history:\n{history_text}\n\n"
                        f"Semantic recall:\n{memory_context.get('semantic_summary', 'No semantic recall.')}\n\n"
                        f"Active workspace context:\n{file_context}\n\nUser: {content}"
                    )
                except Exception as exc:
                    logger.exception("Chat assistant response failed for project %s", project.id)
                    ai_response = f"AI agent unavailable ({str(exc)}). Set OPENAI_API_KEY in your environment to enable AI chat."

            try:
                ChatMessage.objects.create(project=project, role='assistant', content=ai_response)
            except Exception:
                logger.exception("Failed to persist assistant chat message for project %s", project.id)
            return JsonResponse({
                'user_message': content,
                'assistant_message': ai_response,
                'applied_changes': applied_changes,
            })
        except Exception as exc:
            logger.exception("Unhandled project_chat failure for project %s", project.id)
            fallback = f"Chat request failed unexpectedly: {str(exc)}"
            if content:
                try:
                    ChatMessage.objects.create(project=project, role='assistant', content=fallback)
                except Exception:
                    logger.exception("Failed to persist fallback assistant message for project %s", project.id)
            return JsonResponse({
                'user_message': content,
                'assistant_message': fallback,
                'applied_changes': None,
            })

    return JsonResponse({'error': 'Method not allowed'}, status=405)


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
        sandbox.run_command(process_id, command, str(workspace_path))
        return JsonResponse({'status': 'success', 'process_id': process_id})
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
            if current_status.get('running') and runtime.get('preview_url'):
                healthy, _ = _probe_preview_url(runtime['preview_url'])
                if not healthy:
                    sandbox.kill_process(process_id)
            sandbox.run_command(process_id, command, str(workspace_path))
            payload = _runtime_response_payload(runtime, process_id, sandbox, wait_for_preview=True)
            status_code = 200 if payload.get('ready') or not runtime.get('preview_url') else 502
            return JsonResponse(payload, status=status_code)

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
            return JsonResponse({'process_id': process_id, 'command': runtime.get('setup_command'), 'status': sandbox.get_status(process_id)})

        if request.method == 'POST':
            body = _parse_json_body(request)
            command = body.get('command') or runtime.get('setup_command')
            if not command:
                return JsonResponse({'error': 'No setup command detected for this project'}, status=400)
            sandbox.run_command(process_id, command, str(workspace_path))
            return JsonResponse({'process_id': process_id, 'command': command, 'status': sandbox.get_status(process_id)})

        if request.method == 'DELETE':
            sandbox.kill_process(process_id)
            return JsonResponse({'status': 'stopped', 'process_id': process_id})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)
