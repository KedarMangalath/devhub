import json
import hashlib
import logging
import os
import posixpath
import shutil
import subprocess
import tempfile
import threading
import time
from difflib import unified_diff
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError, close_old_connections
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from agents.base import normalize_ai_config
from agents.documentation import generate_codebase_reference_sync
from agents.memory import _file_summary, build_blueprint_context, build_memory_context, compress_recent_activity, index_semantic_memory, record_episode, upsert_working_memory
from agents.workspace import PROJECTS_DIR, SKIP_DIRS, workspace_manager
from core.models import AgentRun, Changeset, ChatMessage, DocumentationRun, EpisodicMemory, Feature, FeatureApproval, FeatureHistory, FileDiff, Project, SemanticMemory, TestResult, WorkingMemory

PIPELINE_STAGES = ['backlog', 'development', 'testing', 'code_review', 'staging']
logger = logging.getLogger(__name__)
DEVHUB_META_DIR = ".devhub"
PROJECT_MEMORY_FILE = "project-memory.md"
PROJECT_INSTRUCTIONS_FILE = "DEVHUB.md"
DEVHUB_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "devhub-settings.json"
MEMORY_DB_ERRORS = (OperationalError, ProgrammingError)


def _parse_json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body)


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


def _suggested_stack_from_text(idea: str, tech_stack: list[str] | None = None) -> list[str]:
    existing = _normalize_tech_stack(tech_stack or [])
    if existing:
        return existing

    text = str(idea or "").lower()
    if any(token in text for token in ("django", "manage.py", "admin panel", "django app")):
        return ["Django"]
    if any(token in text for token in ("fastapi", "api", "backend", "python api")):
        return ["FastAPI"]
    if any(token in text for token in ("vue", "nuxt")):
        return ["Vue", "Node.js"]
    if any(token in text for token in ("next.js", "nextjs", "next app")):
        return ["Next.js", "React", "Node.js"]
    if any(token in text for token in ("react", "vite", "frontend", "ui", "dashboard", "landing page", "web app", "app")):
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
    app_kind = _starter_app_kind(project, starter_brief)

    if app_kind == "calculator":
        app_source = _react_calculator_app_source(title, description)
        styles_source = _react_calculator_styles_source()
        starter_note = "This starter includes a working calculator interface instead of a generic landing screen."
    elif app_kind == "expense":
        app_source = _react_expense_app_source(title, description)
        styles_source = _react_expense_styles_source()
        starter_note = "This starter includes a working expense tracker with totals and entry management."
    elif app_kind == "dashboard":
        app_source = _react_dashboard_app_source(title, description)
        styles_source = _react_dashboard_styles_source()
        starter_note = "This starter includes a working dashboard with live range switching and operational panels."
    else:
        app_source = _react_planner_app_source(title, description)
        styles_source = _react_planner_styles_source()
        starter_note = "This starter includes a working planner board so the idea starts as a real application."

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

    if 'react' in tokens or 'vite' in tokens:
        files = _react_scaffold_files(project, starter_brief=starter_brief)
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
                f"Original user brief: {starter_brief or _display_description(project)}. "
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
            "preview_url": _node_preview_url(project_root, scripts, run_command),
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

    if diagram_type == "erd":
        text = re.sub(r'^\s*erDiagram\s*;?', 'erDiagram\n', text, flags=re.IGNORECASE)
        text = re.sub(r';\s*', '\n', text)
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if not lines or lines[0].strip().lower() != 'erdiagram':
            lines.insert(0, 'erDiagram')
        return "\n".join(lines)

    if diagram_type == "sequence":
        text = re.sub(r'^\s*sequenceDiagram\s*;?', 'sequenceDiagram\n', text, flags=re.IGNORECASE)
        text = re.sub(r';\s*', '\n', text)
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if not lines or lines[0].strip().lower() != 'sequencediagram':
            lines.insert(0, 'sequenceDiagram')
        return "\n".join(lines)

    if text.lower().startswith('graph ') or text.lower().startswith('flowchart '):
        return re.sub(r';\s*', '\n', text)
    return text


def _build_repository_map_from_context(codebase_context: dict) -> list[dict]:
    indexed_paths = [str(path) for path in (codebase_context.get('indexed_paths') or []) if path]
    important_files = codebase_context.get('important_files') or []
    grouped: dict[str, dict] = {}

    for area, count in sorted((codebase_context.get('directory_counts') or {}).items(), key=lambda item: (-item[1], item[0]))[:20]:
        samples = [path for path in indexed_paths if path == area or path.startswith(f'{area}/')][:6]
        hints = sorted({
            hint
            for item in important_files
            if str(item.get('path') or '').startswith(f'{area}/') or (area == '.' and '/' not in str(item.get('path') or ''))
            for hint in (item.get('role_hints') or [])
        })
        grouped[area] = {
            'area': f'{area}/' if area != '.' else 'Project Root',
            'description': f"Contains about {count} indexed files in the {'project root' if area == '.' else area} area of the project.",
            'important_files': samples,
            'relationships': [f"Owns {hint} concerns" for hint in hints] or ['Contains mixed project responsibilities'],
        }

    return list(grouped.values())[:16]


def _describe_directory_area(area: str, role_hints: list[str]) -> str:
    lowered = area.lower()
    if area == '.':
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
    if area == '.':
        return [path for path in indexed_paths if '/' not in path][:limit]
    return [path for path in indexed_paths if path.startswith(f'{area}/')][:limit]


def _important_files_for_area(important_files: list[dict], area: str) -> list[dict]:
    if area == '.':
        return [item for item in important_files if '/' not in str(item.get('path') or '')]
    return [item for item in important_files if str(item.get('path') or '').startswith(f'{area}/')]


def _build_directory_guide_from_context(codebase_context: dict) -> list[dict]:
    guide = []
    indexed_paths = [str(path) for path in (codebase_context.get('indexed_paths') or []) if path]
    important_files = codebase_context.get('important_files') or []

    for area, count in sorted((codebase_context.get('directory_counts') or {}).items(), key=lambda item: (-item[1], item[0]))[:20]:
        area_files = _important_files_for_area(important_files, area)
        example_paths = _sample_paths_for_area(indexed_paths, area, limit=6)
        role_hints = sorted({hint for item in area_files for hint in (item.get('role_hints') or [])})

        if area_files:
            key_files = [item.get('brief') or item.get('path') for item in area_files[:6]]
        else:
            key_files = example_paths

        guide.append({
            'path': f'{area}/' if area != '.' else './',
            'purpose': f"{_describe_directory_area(area, role_hints)} It currently contains about {count} indexed files.",
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
    for area, count in sorted((codebase_context.get('directory_counts') or {}).items(), key=lambda item: (-item[1], item[0]))[:16]:
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


def _build_file_doc_payload(workspace_path: Path, rel_path: str, codebase_context: dict) -> dict:
    target_path, normalized = _codebase_doc_target(workspace_path, rel_path)
    summary = _cached_file_summary(codebase_context, normalized) or _file_summary(target_path, workspace_path) or {
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
    explanation = _build_file_explanation(summary, sibling_paths, [item["path"] for item in docs])
    excerpt = content[:9000]
    dependency_graph = _build_dependency_graph(codebase_context)
    models_summary = _build_models_summary(codebase_context)
    routes_summary = _build_routes_summary(codebase_context)
    prerequisites = _build_prerequisites_summary(workspace_path, codebase_context)

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
        bits.append(f"It contains {', '.join(languages[:5])} files.")
    if roles:
        bits.append(f"The main responsibilities look like {', '.join(roles[:5])}.")
    if doc_files:
        bits.append(f"There is local documentation in {', '.join(item['path'] for item in doc_files[:3])}.")
    if not bits:
        bits.append("This directory currently has mixed responsibilities and needs to be read through its children.")
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
    summaries = _codebase_summary_pool(codebase_context, limit=80)
    ranked = sorted(
        summaries,
        key=lambda item: (
            -len(item.get("imports") or []),
            -len(item.get("routes") or []),
            -len(item.get("data_models") or []),
            -int(item.get("lines") or 0),
            str(item.get("path") or ""),
        ),
    )[:28]
    path_set = {str(item.get("path") or "") for item in summaries if item.get("path")}
    labels: dict[str, str] = {}
    lines = ["graph LR"]
    edges: list[dict] = []

    def node_id(path: str) -> str:
        digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]
        return f"n{digest}"

    def node_label(path: str) -> str:
        path_obj = PurePosixPath(path)
        if len(path_obj.parts) <= 2:
            return path
        return f"{path_obj.parts[-2]}/{path_obj.parts[-1]}"

    emitted_nodes: set[str] = set()
    for item in ranked:
        source_path = str(item.get("path") or "")
        if not source_path:
            continue
        source_id = node_id(source_path)
        if source_path not in emitted_nodes:
            emitted_nodes.add(source_path)
            labels[source_path] = node_label(source_path)
            lines.append(f'  {source_id}["{labels[source_path]}"]')
        for raw_import in item.get("imports") or []:
            import_ref = _extract_import_reference(str(raw_import))
            if not import_ref:
                continue
            candidates = _possible_import_paths(_resolve_relative_import(source_path, import_ref) if import_ref.startswith(".") else import_ref)
            target_path = next((candidate for candidate in candidates if candidate in path_set), "")
            if not target_path and not import_ref.startswith("."):
                lowered = import_ref.lower()
                target_path = next(
                    (
                        str(candidate.get("path") or "")
                        for candidate in summaries
                        if lowered
                        and (
                            str(candidate.get("path") or "").lower().endswith(f"/{lowered}.py")
                            or str(candidate.get("path") or "").lower().endswith(f"/{lowered}.ts")
                            or str(candidate.get("path") or "").lower().endswith(f"/{lowered}.tsx")
                            or str(candidate.get("path") or "").lower().endswith(f"/{lowered}.js")
                            or str(candidate.get("path") or "").lower().endswith(f"/{lowered}.jsx")
                            or PurePosixPath(str(candidate.get("path") or "")).stem.lower() == lowered
                        )
                    ),
                    "",
                )
            if not target_path or target_path == source_path:
                continue
            target_id = node_id(target_path)
            if target_path not in emitted_nodes:
                emitted_nodes.add(target_path)
                labels[target_path] = node_label(target_path)
                lines.append(f'  {target_id}["{labels[target_path]}"]')
            edge = {"from": source_path, "to": target_path, "reason": str(raw_import)}
            if edge not in edges:
                edges.append(edge)
                lines.append(f"  {source_id} --> {target_id}")
            if len(edges) >= 48:
                break
        if len(edges) >= 48:
            break

    return {
        "mermaid": "\n".join(lines) if len(lines) > 1 else "",
        "edges": edges,
        "nodes": [{"path": path, "label": labels.get(path) or node_label(path)} for path in emitted_nodes],
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
        for command in item.get("commands") or []:
            command_text = str(command).strip()
            if command_text and command_text not in commands:
                commands.append(command_text)
                tool = command_text.split()[0]
                if tool and tool not in tools:
                    tools.append(tool)
    return {
        "readme_excerpt": str(codebase_context.get("readme_excerpt") or "").strip(),
        "instruction_files": list(codebase_context.get("instruction_files") or []),
        "commands": commands[:24],
        "required_tools": tools[:16],
        "environment_files": env_files[:12],
        "environment_variables": env_variables[:80],
    }


def _build_directory_doc_payload(workspace_path: Path, rel_path: str, codebase_context: dict) -> dict:
    target_path, normalized = _codebase_doc_target(workspace_path, rel_path)
    doc_files = _read_context_docs(workspace_path, target_path)
    child_entries = []
    files_accessed = []
    for entry in sorted(target_path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
        if entry.name in SKIP_DIRS or entry.name == ".env":
            continue
        rel_entry = str(entry.relative_to(workspace_path)).replace("\\", "/")
        if rel_entry.startswith(f"{DEVHUB_META_DIR}/"):
            continue
        if entry.is_file():
            summary = _file_summary(entry, workspace_path)
            if not summary:
                continue
            child_entries.append(
                {
                    "name": entry.name,
                    "path": rel_entry,
                    "type": "file",
                    "summary": summary.get("purpose") or summary.get("summary"),
                    "language": summary.get("language"),
                    "lines": summary.get("lines"),
                    "role_hints": summary.get("role_hints") or [],
                    "symbol": summary.get("symbol"),
                    "file_kind": summary.get("file_kind"),
                }
            )
            files_accessed.append({"path": rel_entry, "source": "file", "reason": "Indexed as part of the selected directory."})
        else:
            sample_files = _iter_codebase_files(entry, workspace_path, limit=6)
            sample_summaries = [summary for summary in (_file_summary(item, workspace_path) for item in sample_files) if summary]
            child_entries.append(
                {
                    "name": entry.name,
                    "path": rel_entry,
                    "type": "directory",
                    "summary": _describe_directory_children(sample_summaries, []),
                    "child_count": len([item for item in entry.iterdir() if item.name not in SKIP_DIRS and item.name != ".env"]),
                    "sample_files": [str(item.get("path") or "") for item in sample_summaries[:4]],
                }
            )
            files_accessed.extend(
                {"path": str(item.relative_to(workspace_path)).replace("\\", "/"), "source": "folder_sample", "reason": f"Used to summarize the `{rel_entry}/` folder."}
                for item in sample_files[:4]
            )
        if len(child_entries) >= 120:
            break

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
        return _build_file_doc_payload(workspace_path, normalized, codebase_context)
    return _build_directory_doc_payload(workspace_path, normalized, codebase_context)


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
        if not name or name in {".", ".git", ".devhub"}:
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
            "install dependencies",
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


def _derive_repo_guidance(project: Project, codebase_context: dict) -> dict:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return {
            "setup_steps": [],
            "onboarding_checklist": [],
            "gotchas": [],
        }

    readme_text = _read_workspace_excerpt(workspace_path, "README.md", "readme.md")
    contributing_text = _read_workspace_excerpt(workspace_path, "CONTRIBUTING.md", "contributing.md")
    vision_text = _read_workspace_excerpt(workspace_path, "VISION.md", "vision.md", limit=6000)
    agents_text = _read_workspace_excerpt(workspace_path, "AGENTS.md", "agents.md", limit=6000)
    security_text = _read_workspace_excerpt(workspace_path, "SECURITY.md", "security.md", limit=6000)
    env_text = _read_workspace_excerpt(workspace_path, ".env.example", ".env.sample", ".env.template", limit=10000)

    package_data = _load_workspace_package_json(workspace_path)
    scripts = package_data.get("scripts") if isinstance(package_data.get("scripts"), dict) else {}
    package_manager = _detect_workspace_package_manager(workspace_path, package_data)
    command_evidence = _extract_shell_commands("\n".join([readme_text, contributing_text, agents_text, vision_text]))
    top_areas = _top_repository_areas(codebase_context)

    install_command = ""
    if package_data:
        install_command = {
            "pnpm": "pnpm install",
            "yarn": "yarn install",
            "bun": "bun install",
            "npm": "npm install",
        }.get(package_manager, "npm install")
    elif (workspace_path / "requirements.txt").exists():
        install_command = "python -m pip install -r requirements.txt"
    elif (workspace_path / "pyproject.toml").exists():
        install_command = "python -m pip install -e ."
    elif (workspace_path / "Cargo.toml").exists():
        install_command = "cargo build"

    build_command = ""
    if scripts.get("ui:build") and scripts.get("build"):
        build_command = f"{_run_script_command(package_manager, 'ui:build')} && {_run_script_command(package_manager, 'build')}"
    elif scripts.get("build"):
        build_command = _run_script_command(package_manager, "build")
    elif scripts.get("compile"):
        build_command = _run_script_command(package_manager, "compile")

    onboarding_command = _pick_command(command_evidence, "onboard")
    if not onboarding_command and scripts.get("onboard"):
        onboarding_command = _run_script_command(package_manager, "onboard")

    dev_command = ""
    for key in ("gateway:watch", "gateway:dev", "dev", "start", "ui:dev"):
        if scripts.get(key):
            dev_command = _run_script_command(package_manager, key)
            break
    if not dev_command:
        dev_command = _pick_command(command_evidence, "watch") or _pick_command(command_evidence, "dev")

    contributor_command = _pick_command(command_evidence, "check", "test")
    if not contributor_command and package_data:
        segments = []
        for key in ("build", "check", "test"):
            if scripts.get(key):
                segments.append(_run_script_command(package_manager, key))
        contributor_command = " && ".join(segments[:3])

    node_engine = ""
    engines = package_data.get("engines")
    if isinstance(engines, dict):
        node_engine = str(engines.get("node") or "").strip()

    node_note = ""
    if node_engine:
        node_note = f"package.json requires Node {node_engine}."
    if "node 24" in readme_text.lower():
        node_note = f"{node_note} README recommends Node 24 for local development.".strip()

    windows_note = ""
    readme_lower = readme_text.lower()
    if "wsl2" in readme_lower:
        windows_note = "README recommends WSL2 for Windows setup."

    setup_steps = []
    if install_command:
        setup_steps.append({
            "step": "Install workspace dependencies",
            "command": install_command,
            "explanation": "Install from the repository root so the detected workspace config and scripts stay in sync.",
            "os_note": " ".join(part for part in [node_note, windows_note] if part).strip(),
        })
    if env_text:
        env_note = "PowerShell: Copy-Item .env.example .env."
        if "~/.openclaw/.env" in env_text:
            env_note = f"{env_note} Daemon installs can also read ~/.openclaw/.env."
        setup_steps.append({
            "step": "Create a local env file",
            "command": "cp .env.example .env",
            "explanation": "The repo ships a root env example with gateway auth, model provider keys, and channel config.",
            "os_note": env_note,
        })
    if build_command:
        setup_steps.append({
            "step": "Build source artifacts",
            "command": build_command,
            "explanation": "Use the source build path documented in the repository before running the app locally.",
            "os_note": "Run from the repo root.",
        })
    if onboarding_command:
        setup_steps.append({
            "step": "Run the recommended onboarding flow",
            "command": onboarding_command,
            "explanation": "The README recommends this as the supported first-run path for configuring the gateway, workspace, and channels.",
            "os_note": windows_note,
        })
    if dev_command:
        setup_steps.append({
            "step": "Start the main development loop",
            "command": dev_command,
            "explanation": "Use the repo's preferred watch/dev command rather than guessing at the runtime entrypoint.",
            "os_note": "",
        })
    if contributor_command:
        setup_steps.append({
            "step": "Run contributor checks before a PR",
            "command": contributor_command,
            "explanation": "The contribution guide expects the build, checks, and tests to pass before review.",
            "os_note": "",
        })

    docs_to_read = []
    for filename in ("README.md", "CONTRIBUTING.md", "VISION.md", "AGENTS.md", "SECURITY.md"):
        if (workspace_path / filename).exists():
            docs_to_read.append(filename)

    onboarding_checklist = []
    if docs_to_read:
        onboarding_checklist.append({
            "task": "Read the root project docs first",
            "category": "codebase",
            "estimated_time": "15 min",
            "why_important": "This repo has explicit setup, product, and contribution guidance in top-level docs.",
            "instructions": f"Start with {', '.join(docs_to_read[:4])}.",
        })
    if top_areas:
        onboarding_checklist.append({
            "task": "Map the major repo areas",
            "category": "codebase",
            "estimated_time": "10 min",
            "why_important": "The imported project spans multiple top-level surfaces, so it helps to know the ownership boundaries before editing.",
            "instructions": f"Begin with {', '.join(top_areas[:5])} and then open the repo map for file-level detail.",
        })
    if env_text or security_text:
        onboarding_checklist.append({
            "task": "Review environment and security defaults",
            "category": "environment",
            "estimated_time": "10 min",
            "why_important": "This repo uses real credentials, channels, or runtime services, so the default auth and env behavior matters before first run.",
            "instructions": "Read .env.example and SECURITY.md before enabling external integrations or remote access.",
        })
    if dev_command or build_command:
        instructions_parts = []
        if install_command:
            instructions_parts.append(f"`{install_command}`")
        if build_command:
            instructions_parts.append(f"`{build_command}`")
        if dev_command:
            instructions_parts.append(f"`{dev_command}`")
        onboarding_checklist.append({
            "task": "Use the documented source workflow",
            "category": "tools",
            "estimated_time": "15 min",
            "why_important": "The repo already defines a preferred build/watch flow; using it avoids chasing the wrong entrypoint.",
            "instructions": "Follow this order: " + " then ".join(instructions_parts) if instructions_parts else "Use the documented source workflow from the README.",
        })
    if contributing_text:
        onboarding_checklist.append({
            "task": "Follow the contributor rules before opening a PR",
            "category": "processes",
            "estimated_time": "10 min",
            "why_important": "The contribution guide has explicit expectations around PR scope, testing, and review follow-through.",
            "instructions": "Check CONTRIBUTING.md for review expectations, screenshot requirements, and the no refactor-only / no test-only known-main-failure rules.",
        })

    gotchas = []
    if package_manager == "pnpm" and ((workspace_path / "pnpm-workspace.yaml").exists() or package_data.get("workspaces")):
        gotchas.append("Use `pnpm` from the repo root. The workspace layout is managed as a monorepo, so ad-hoc per-folder installs can leave the tree in a partial state.")
    if "wsl2" in readme_lower:
        gotchas.append("Windows support is documented as WSL2-first for the recommended onboarding path, so native Windows runs may not match the main setup guide.")
    if "auto-installs ui deps on first run" in readme_lower:
        gotchas.append("`ui:build` also installs UI dependencies on first run, so the first build can take longer and do more work than the command name suggests.")
    if "runs typescript directly" in readme_lower or "via `tsx`" in readme_text.lower():
        gotchas.append("The source workflow can run TypeScript directly via `tsx`, while the normal build emits `dist/`. Use the source-mode commands when you want live development behavior.")
    if "untrusted input" in readme_lower or "pairing" in readme_lower:
        gotchas.append("This project connects to real messaging channels. Review pairing and auth defaults before exposing the gateway or enabling inbound channels.")
    if "env-source precedence" in env_text.lower():
        gotchas.append("Env loading is layered: process env, local `.env`, `~/.openclaw/.env`, then config `env` values. Unexpected behavior can come from a higher-precedence source.")

    def _dedupe(items: list) -> list:
        deduped = []
        seen = set()
        for item in items:
            key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    return {
        "setup_steps": _dedupe(setup_steps)[:6],
        "onboarding_checklist": _dedupe(onboarding_checklist)[:6],
        "gotchas": _dedupe(gotchas)[:6],
    }


def _merge_repo_guidance_into_blueprint(project: Project, blueprint: dict, codebase_context: dict) -> dict:
    blueprint = dict(blueprint or {})
    derived = _derive_repo_guidance(project, codebase_context)
    for field in ("setup_steps", "onboarding_checklist", "gotchas"):
        if derived.get(field) and _guidance_field_needs_refresh(blueprint.get(field), field):
            blueprint[field] = derived[field]
    return blueprint


def _render_blueprint_design_document(project: Project, blueprint: dict, codebase_context: dict, feature_summary: str) -> tuple[str, list[dict]]:
    generated_on = timezone.now().strftime('%Y-%m-%d')
    title = project.name or 'Project'
    services = _blueprint_list(blueprint.get('services'))
    endpoints = _blueprint_list(blueprint.get('api_endpoints'))
    schema = _blueprint_list(blueprint.get('database_schema'))
    key_components = _blueprint_list(blueprint.get('key_components'))
    directories = _blueprint_list(blueprint.get('directory_guide'))
    workflows = _blueprint_list(blueprint.get('common_workflows'))
    setup_steps = _blueprint_list(blueprint.get('setup_steps'))
    env_vars = _blueprint_list(blueprint.get('environment_variables'))
    security = _blueprint_list(blueprint.get('security_considerations'))
    performance = _blueprint_list(blueprint.get('performance_notes'))
    integrations = _blueprint_list(blueprint.get('integration_points'))
    onboarding = _blueprint_list(blueprint.get('onboarding_checklist'))
    concepts = _blueprint_list(blueprint.get('key_concepts'))
    gotchas = _blueprint_list(blueprint.get('gotchas'))
    feature_inventory = _blueprint_list(blueprint.get('feature_inventory'))
    tech_stack_details = _blueprint_list(blueprint.get('tech_stack_details'))
    change_guide = _blueprint_list(blueprint.get('change_guide'))
    sequence_flows = _blueprint_list(blueprint.get('sequence_flows'))
    pipeline = blueprint.get('sdlc_pipeline') or {}
    routes = _blueprint_list(codebase_context.get('routes'))
    data_models = _blueprint_list(codebase_context.get('data_models'))

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
        'body': [
            _blueprint_text(
                blueprint.get('data_flow'),
                'The core request/data flow was not clearly detected from the scanned codebase yet.',
            ),
            '',
            'Known product and workflow signals:',
            *_markdown_bullets([item.get('title') for item in feature_inventory if isinstance(item, dict)], 'No tracked feature inventory yet.'),
        ],
    })

    sections.append({
        'id': 'goals-non-goals',
        'title': 'Goals & Non-Goals',
        'body': [
            'Goals inferred from the current blueprint and change guide:',
            *_markdown_bullets(
                [item.get('notes') for item in change_guide if isinstance(item, dict)],
                'No explicit goals were captured in the blueprint yet.',
            ),
            '',
            'Non-goals or unknowns:',
            *_markdown_bullets(
                gotchas[:6] if gotchas else ['Areas without evidence should be treated as unknown until verified in code.'],
                'Non-goals were not clearly documented.',
            ),
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
        api_body.extend(
            _markdown_bullets(
                [
                    f"{item.get('method', 'UNKNOWN')} {item.get('path', '/unknown')}: {item.get('description') or 'No endpoint description available.'}"
                    for item in endpoints if isinstance(item, dict)
                ],
                'No API endpoints were documented.',
            )
        )
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
            f"- Unit: {_blueprint_text((blueprint.get('testing_strategy') or {}).get('unit'))}",
            f"- Integration: {_blueprint_text((blueprint.get('testing_strategy') or {}).get('integration'))}",
            f"- E2E: {_blueprint_text((blueprint.get('testing_strategy') or {}).get('e2e'))}",
            f"- Run command: {_blueprint_text((blueprint.get('testing_strategy') or {}).get('run_command'))}",
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
    blueprint['readme_excerpt'] = str(codebase_context.get('readme_excerpt') or '')[:4000]
    blueprint['instruction_files'] = _blueprint_list(codebase_context.get('instruction_files'))
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
    ai_design_document = blueprint.get('design_document_markdown')
    ai_design_sections = blueprint.get('design_document_sections')
    ai_markdown_ok = isinstance(ai_design_document, str) and len(ai_design_document.strip()) >= 6000
    ai_sections_ok = isinstance(ai_design_sections, list) and len(ai_design_sections) >= 8
    if not ai_markdown_ok or not ai_sections_ok:
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

    if not os.environ.get('OPENAI_API_KEY'):
        return _fallback_plan(selected_file, file_inventory, request_text)

    try:
        from agents.planner import PlannerAgent

        planner = PlannerAgent(ai_config=_project_ai_config(project))
        plan = planner.create_plan(
            project_name=project.name,
            request_title=request_title,
            request_text=request_text,
            project_memory=project_memory[:12000],
            codebase_summary=codebase_summary[:9000],
            file_inventory=file_inventory[:5000],
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


def _build_supporting_context(project: Project, plan: dict, workspace_path: Path) -> str:
    runtime = detect_runtime(workspace_path)
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        logger.exception("Failed to load codebase context for supporting context in project %s", project.id)
    instruction_context = codebase_context.get('instruction_files') or []
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

        reviewer = ReviewerAgent(ai_config=_project_ai_config(project))
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
    codebase_context = {}
    feature_summary = _render_project_features_summary(project, limit=20)
    try:
        from agents.architect import ArchitectAgent
        from agents.explorer import CodebaseExplorerAgent

        local_scan = ""
        readme = ""
        exploration_report = {}
        repo_map_text = ""
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
                codebase_context = build_blueprint_context(project, workspace_path)
                repo_map_path = workspace_path / DEVHUB_META_DIR / "repo-map.md"
                if repo_map_path.exists():
                    repo_map_text = repo_map_path.read_text(encoding="utf-8", errors="ignore")[:12000]
            except Exception:
                logger.exception("Blueprint context build failed for project %s", project.id)
                codebase_context = {}

        if os.environ.get("OPENAI_API_KEY") and codebase_context:
            try:
                explorer = CodebaseExplorerAgent(ai_config=_project_ai_config(project))
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
                        'important_files': [item.get('path') for item in (codebase_context.get('important_files') or [])[:12]],
                    },
                )
            except Exception:
                logger.exception("Blueprint exploration failed for project %s", project.id)

        architect = ArchitectAgent(ai_config=_project_ai_config(project))
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
                "codebase_fingerprint": codebase_context.get("fingerprint") if isinstance(codebase_context, dict) else None,
                "indexed_files": codebase_context.get("file_count") if isinstance(codebase_context, dict) else None,
                "cached": True if codebase_context else False,
            }
        project.blueprint = blueprint
        project.save()
    except Exception as exc:
        fallback_blueprint = {
            "architecture_overview": f"Blueprint generation failed: {str(exc)}. Set your OPENAI_API_KEY environment variable.",
            "tech_stack_details": [{"tech": t, "purpose": "Core technology"} for t in (project.tech_stack or [])],
            "services": [],
            "setup_steps": [],
            "gotchas": [str(exc)],
        }
        try:
            fallback_blueprint = _enrich_blueprint_document(project, fallback_blueprint, codebase_context, feature_summary)
            fallback_blueprint["_meta"] = {
                "codebase_fingerprint": codebase_context.get("fingerprint") if isinstance(codebase_context, dict) else None,
                "indexed_files": codebase_context.get("file_count") if isinstance(codebase_context, dict) else None,
                "cached": True if codebase_context else False,
            }
        except Exception:
            logger.exception("Blueprint fallback enrichment failed for project %s", project.id)
        project.blueprint = fallback_blueprint
        project.save()


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
    memory_context = build_memory_context(project, request_text, selected_file=selected_file)
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
    agent = CoderAgent(ai_config=_project_ai_config(project))
    attempt_logs = []
    all_applied_files: list[str] = []
    latest_plan = {}
    latest_review = {}
    latest_validation_results: list[dict] = []
    latest_context_files: list[str] = []
    current_request_text = request_text
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        logger.exception("Failed to load cached codebase context for implementation in project %s", project.id)

    for attempt in range(1, 4):
        plan = _create_implementation_plan(
            project=project,
            request_title=request_title,
            request_text=current_request_text,
            workspace_path=workspace_path,
            project_memory=f"{project_memory[:8000]}\n\nProject Instructions:\n{project_instructions[:3000]}\n\n{memory_context_text[:4000]}",
            memory_context_text=memory_context_text,
            selected_file=selected_file,
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
            project_memory=f"{project_memory[:8000]}\n\nProject Instructions:\n{project_instructions[:3000]}",
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
        "context_files": latest_context_files,
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


CHAT_SPECIAL_CONTEXTS = {
    'codebase': 'Whole-project summary and indexed repo context',
    'currentfile': 'The file currently open in the workspace',
    'readme': 'Root docs like README, CONTRIBUTING, SECURITY, and VISION',
    'rules': 'Project instructions and workspace rules',
    'conversation': 'Recent chat history in this project',
    'terminal': 'Runtime status and detected commands',
}


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


def _resolve_chat_context(
    project: Project,
    content: str,
    selected_file: str = '',
    selected_content: str = '',
    context_mentions=None,
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

    for mention in mentions:
        mention_type = mention.get('type')
        value = str(mention.get('value') or '')
        lowered = value.lower()
        if mention_type == 'special' and lowered == 'codebase':
            summary = str((codebase_context or {}).get('compact_summary') or '')
            important_files = list((codebase_context or {}).get('important_files') or [])
            codebase_parts = []
            if summary:
                codebase_parts.append(f"=== PROJECT OVERVIEW ===\n{summary[:4000]}")
            # Include actual file contents from the top important files
            if important_files and workspace_path:
                codebase_parts.append("\n=== KEY SOURCE FILES (read these carefully) ===")
                chars_used = 0
                max_chars = 20000
                files_included = 0
                for file_item in important_files[:15]:
                    if chars_used >= max_chars:
                        break
                    rel_path = file_item.get('path', '')
                    if not rel_path:
                        continue
                    file_content = _safe_read_workspace_file(workspace_path, rel_path, limit=3000)
                    if not file_content:
                        continue
                    file_summary = file_item.get('summary', '')
                    block = f"\n--- FILE: {rel_path} ---\nSummary: {file_summary}\nContent:\n{file_content}\n--- END FILE ---"
                    codebase_parts.append(block)
                    chars_used += len(block)
                    files_included += 1
                    trace['files_accessed'].append({'path': rel_path, 'source': 'codebase_scan', 'reason': f'Top important file included in @codebase context.'})
            if codebase_parts:
                context_blocks.append(f"@codebase\n" + "\n".join(codebase_parts))
                trace['context_sources'].append({'label': '@codebase', 'detail': f'Used indexed repository summary plus contents of {files_included} key source files.'})
        elif mention_type == 'special' and lowered == 'currentfile':
            if selected_file:
                current_content = selected_content or (_safe_read_workspace_file(workspace_path, selected_file) if workspace_path else '')
                if current_content:
                    context_blocks.append(f"@currentFile `{selected_file}`\n{current_content}")
                    trace['files_accessed'].append({'path': selected_file, 'source': 'current_file', 'reason': 'Explicit current file context requested.'})
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
            recent = list(ChatMessage.objects.filter(project=project).order_by('-created_at')[:8].values('role', 'content'))
            recent.reverse()
            if recent:
                history_text = "\n".join(f"{item['role']}: {item['content'][:500]}" for item in recent)
                context_blocks.append(f"@conversation\n{history_text}")
                trace['context_sources'].append({'label': '@conversation', 'detail': 'Loaded recent project chat history.'})
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
            file_content = _safe_read_workspace_file(workspace_path, value, limit=5000)
            if file_content:
                context_blocks.append(f"@{value}\n{file_content}")
                trace['files_accessed'].append({'path': value, 'source': 'file', 'reason': 'Explicit file mention requested.'})

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
    return trace


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
        "review": result.get("review", {}),
        "validation_results": result.get("validation_results", []),
        "context_files": result.get("context_files", []),
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
    ai_suggestions = [
        'Ask DevHub to generate or refine work items from the current blueprint.',
        'Use AI implementation on a work item after reviewing the blueprint and repo map.',
        'Refresh the blueprint after meaningful code changes so onboarding stays current.',
    ]

    runtime_hint = runtime.get('run_command') if isinstance(runtime, dict) else None
    return {
        'source_label': source_label,
        'recommended_start_tab': _recommended_start_tab(project),
        'next_steps': next_steps,
        'ai_suggestions': ai_suggestions,
        'suggested_work_items': _suggested_work_items(project, features_payload),
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
        tech_stack = _normalize_tech_stack(body.get('tech_stack', []))
        if not tech_stack and starter_brief and not github_url and not local_path:
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
                    enriched_blueprint = _merge_repo_guidance_into_blueprint(project, project.blueprint, codebase_context)
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
        blueprint_meta = {
            'available': bool(project.blueprint),
            'generated': bool(project.blueprint),
            'indexed_files': (project.blueprint or {}).get('_meta', {}).get('indexed_files'),
            'cached': (project.blueprint or {}).get('_meta', {}).get('cached'),
        }
        documentation_run = DocumentationRun.objects.filter(project=project).prefetch_related('sections').first()
        documentation = _documentation_run_payload(documentation_run)

        return JsonResponse({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'github_url': project.github_url,
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
            'runtime': runtime,
        })
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except (ValidationError, ValueError):
        return JsonResponse({'error': 'Invalid project ID'}, status=400)
    except Exception as exc:
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
        messages = list(ChatMessage.objects.filter(project=project).order_by('created_at').values('id', 'role', 'content', 'metadata', 'created_at'))
        return JsonResponse({'messages': messages})

    if request.method == 'POST':
        content = ''
        try:
            body = _parse_json_body(request)
            content = str(body.get('content') or '').strip()
            selected_file = str(body.get('selected_file') or '').strip()
            selected_content = str(body.get('selected_content') or '')
            context_mentions = body.get('context_mentions') or []
            apply_changes = body.get('apply_changes')
            if not content:
                return JsonResponse({'error': 'Message is required'}, status=400)

            user_trace = {
                'context_mentions': _dedupe_chat_mentions(
                    _normalize_chat_mentions(context_mentions),
                    _infer_inline_chat_mentions(content),
                ),
                'selected_file': selected_file or None,
            }
            ChatMessage.objects.create(project=project, role='user', content=content, metadata=user_trace)

            should_apply_changes = _looks_like_edit_request(content) if apply_changes is None else bool(apply_changes)
            applied_changes = None
            assistant_trace = {}
            memory_context = build_memory_context(project, content, selected_file=selected_file)
            resolved_context_text, context_trace = _resolve_chat_context(
                project,
                content,
                selected_file=selected_file,
                selected_content=selected_content,
                context_mentions=context_mentions,
            )

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
                    assistant_trace = _build_chat_trace_from_changes(applied_changes, context_trace, memory_context)
                except Exception as exc:
                    logger.exception("Chat code application failed for project %s", project.id)
                    ai_response = f"I understood this as a code-change request, but the edit failed: {str(exc)}"
                    assistant_trace = {
                        'approach': context_trace.get('approach') or 'Tried to apply a code change request.',
                        'context_mentions': context_trace.get('context_mentions') or [],
                        'context_sources': context_trace.get('context_sources') or [],
                        'files_accessed': context_trace.get('files_accessed') or [],
                        'commands_ran': [],
                        'applied_files': [],
                        'error': str(exc),
                    }
            else:
                try:
                    from agents.base import BaseAgent

                    blueprint = project.blueprint or {}
                    arch = json.dumps(blueprint.get('architecture_overview', ''))[:800]
                    tech = ", ".join(project.tech_stack) if project.tech_stack else "Unknown"

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
                    if resolved_context_text:
                        file_context += f"\n\nExplicit context mentions:\n{resolved_context_text[:24000]}"

                    agent = BaseAgent(
                        role="DevHub AI Assistant",
                        system_instruction=f"""You are the DevHub AI assistant for the project "{project.name}".
Tech Stack: {tech}
Architecture: {arch}
Working Memory: {memory_context.get('working_summary', '')[:2000]}
Cached Codebase Summary: {memory_context.get('blueprint_summary', '')[:3000]}
Episodic Memory: {memory_context.get('episodic_summary', '')[:1200]}

Help the developer understand, plan and implement features, debug issues, and reason about the current code.
When @codebase is mentioned, provide thorough, evidence-based answers citing specific file paths, function names, and code patterns you can see in the context.
When relevant, use the active file context and keep answers action-oriented and detailed.""",
                        ai_config=_project_ai_config(project),
                    )
                    ai_response = agent.generate(
                        f"Chat history:\n{history_text}\n\n"
                        f"Semantic recall:\n{memory_context.get('semantic_summary', 'No semantic recall.')}\n\n"
                        f"Active workspace context:\n{file_context}\n\nUser: {content}"
                    )
                    assistant_trace = {
                        'approach': context_trace.get('approach') or 'Answered the question using project memory, semantic recall, and explicit workspace context.',
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
                    ai_response = f"AI agent unavailable ({str(exc)}). Set OPENAI_API_KEY in your environment to enable AI chat."
                    assistant_trace = {
                        'approach': context_trace.get('approach') or 'Tried to answer using workspace context.',
                        'context_mentions': context_trace.get('context_mentions') or [],
                        'context_sources': context_trace.get('context_sources') or [],
                        'files_accessed': context_trace.get('files_accessed') or [],
                        'commands_ran': [],
                        'error': str(exc),
                    }

            try:
                ChatMessage.objects.create(project=project, role='assistant', content=ai_response, metadata=assistant_trace)
            except Exception:
                logger.exception("Failed to persist assistant chat message for project %s", project.id)
            return JsonResponse({
                'user_message': content,
                'assistant_message': ai_response,
                'applied_changes': applied_changes,
                'trace': assistant_trace,
            })
        except Exception as exc:
            logger.exception("Unhandled project_chat failure for project %s", project.id)
            fallback = f"Chat request failed unexpectedly: {str(exc)}"
            if content:
                try:
                    ChatMessage.objects.create(project=project, role='assistant', content=fallback, metadata={'error': str(exc)})
                except Exception:
                    logger.exception("Failed to persist fallback assistant message for project %s", project.id)
            return JsonResponse({
                'user_message': content,
                'assistant_message': fallback,
                'applied_changes': None,
                'trace': {'error': str(exc)},
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
    """SSE endpoint that generates each Blueprint section with a dedicated LLM call.

    Streams progress events as sections complete (Services → API → Database →
    Workflows → Setup → Quality → Knowledge).
    """
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

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def event_stream():
        initial_event = {
            'section_key': 'build_context',
            'section_label': 'Preparing codebase context',
            'status': 'started',
            'progress_pct': 0,
            'total_sections': 7,
            'completed_sections': 0,
            'section_data': {},
        }
        _safe_write_deep_docs_progress(workspace_path, initial_event)
        yield _sse(initial_event)

        try:
            codebase_context = build_blueprint_context(project, workspace_path)
        except Exception as exc:
            logger.exception("Failed to build blueprint context for project %s", project_id)
            failure_event = {
                'section_key': 'build_context',
                'section_label': 'Preparing codebase context',
                'status': 'failed',
                'progress_pct': 0,
                'total_sections': 7,
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
                'total_sections': 7,
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
            'total_sections': 7,
            'completed_sections': 0,
            'section_data': {},
        }
        _safe_write_deep_docs_progress(workspace_path, context_ready_event)
        yield _sse(context_ready_event)

        agent = DeepDocumentationAgent(ai_config=_project_ai_config(project))
        existing_blueprint = project.blueprint or {}

        for event in agent.generate_all_sections(
            project_name=project.name,
            cache=codebase_context,
            workspace_path=workspace_path,
            existing_blueprint=existing_blueprint,
        ):
            if event.get('status') != 'started':
                # Persist each completed section into the project blueprint.
                try:
                    close_old_connections()
                    project.refresh_from_db()
                    current_bp = project.blueprint or {}
                    section_data = event.get('section_data', {})
                    for key, value in section_data.items():
                        if key != '_error':
                            current_bp[key] = value
                    project.blueprint = current_bp
                    project.save()
                except Exception:
                    logger.exception("Failed to persist section %s for project %s", event.get('section_key'), project_id)

            # Send SSE event (without the full blueprint_snapshot to keep payload small)
            sse_payload = {
                'section_key': event.get('section_key'),
                'section_label': event.get('section_label'),
                'section_data': event.get('section_data'),
                'progress_pct': event.get('progress_pct'),
                'status': event.get('status'),
                'total_sections': event.get('total_sections'),
                'completed_sections': event.get('completed_sections'),
            }
            _safe_write_deep_docs_progress(workspace_path, sse_payload)
            yield _sse(sse_payload)

        done_event = {'status': 'done', 'section_key': 'complete', 'section_label': 'Blueprint complete', 'progress_pct': 100, 'total_sections': 7, 'completed_sections': 7, 'section_data': {}}
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
            if current_status.get('running'):
                command_changed = current_status.get('command') != command
                unhealthy_preview = False
                if runtime.get('preview_url'):
                    healthy, _ = _probe_preview_url(runtime['preview_url'])
                    unhealthy_preview = not healthy
                if command_changed or unhealthy_preview:
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
