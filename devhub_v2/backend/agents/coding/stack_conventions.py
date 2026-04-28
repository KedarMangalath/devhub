"""
Canonical conventions for each supported stack combination.

These are facts, not suggestions. Every LLM call in the pipeline receives
the relevant conventions so it can generate correct code without guessing.
"""
from __future__ import annotations
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Stack detection helpers
# ---------------------------------------------------------------------------

def _has(stack: str, *keywords: str) -> bool:
    s = stack.lower()
    return all(k in s for k in keywords)


def _any(stack: str, *keywords: str) -> bool:
    s = stack.lower()
    return any(k in s for k in keywords)


def detect_stack_key(tech_stack: str) -> str:
    """Return a canonical stack key from a free-form tech_stack string."""
    s = tech_stack.lower()
    frontend_requested = any(token in s for token in ("react", "vite", "next", "vue", "svelte", "frontend", "ui", "web app", "website"))

    frontend = "react_vite"
    if "next" in s:
        frontend = "nextjs"
    elif "vue" in s:
        frontend = "vue_vite"
    elif "svelte" in s:
        frontend = "svelte_vite"
    elif "react" in s:
        frontend = "react_vite"
    elif "html" in s and "javascript" in s and "react" not in s:
        frontend = "vanilla"

    backend = None
    if "fastapi" in s:
        backend = "fastapi"
    elif "flask" in s:
        backend = "flask"
    elif "express" in s or "node" in s:
        backend = "express"
    elif "django" in s:
        backend = "django"
    elif any(token in s for token in ("full stack", "full-stack", "fullstack", "backend", "database", "auth")):
        backend = "fastapi"

    if backend == "fastapi" and not frontend_requested:
        return "fastapi_only"

    # purely frontend stacks
    if frontend in ("react_vite", "vue_vite", "svelte_vite", "vanilla") and backend is None:
        if frontend == "react_vite":
            return "react_vite_mock"
        return f"{frontend}_only"

    return f"{frontend}_{backend}"


# ---------------------------------------------------------------------------
# Convention definitions
# ---------------------------------------------------------------------------

_CONVENTIONS: dict[str, dict] = {

    "fastapi_only": {
        "label": "FastAPI backend only",
        "frontend_framework": "None",
        "backend_framework": "FastAPI with Pydantic v2 and Uvicorn",
        "frontend_dir": None,
        "backend_dir": ".",
        "frontend_port": None,
        "backend_port": 8001,
        "frontend_entry": None,
        "backend_entry": "main.py",
        "frontend_run": None,
        "backend_run": "uvicorn main:app --reload --port 8001",
        "install_frontend": None,
        "install_backend": "pip install -r requirements.txt",
        "syntax_check_backend": "python -m py_compile *.py",
        "startup_check_backend": "python -c \"from main import app; print('OK')\"",
        "vite_proxy": False,
        "api_prefix": "/api/",
        "import_style": "flat",
        "backend_import_note": "Backend runs as `uvicorn main:app --port 8001` from the project root. Use flat imports between local files.",
        "frontend_import_note": None,
        "file_extensions": {"components": ".jsx", "pages": ".jsx", "hooks": ".js", "utils": ".js"},
        "required_files": ["requirements.txt", "main.py"],
        "package_json_scripts": {},
        "vite_version": None,
        "notes": "Backend-only API project. Do not generate frontend files.",
    },

    # ─── React (Vite) + Django ──────────────────────────────────────────────
    "react_vite_django": {
        "label": "React + Vite + Django REST Framework",
        "frontend_framework": "React 18 with Vite 4, React Router v6, Tailwind CSS, Axios",
        "backend_framework": "Django 4 with Django REST Framework",
        "frontend_dir": "frontend",
        "backend_dir": "backend",
        "frontend_port": 5173,
        "backend_port": 8000,
        "frontend_entry": "frontend/src/main.jsx",
        "backend_entry": "backend/manage.py",
        "frontend_run": "cd frontend && npm run dev",
        "backend_run": "cd backend && python manage.py runserver 8000",
        "install_frontend": "cd frontend && npm install",
        "install_backend": "cd backend && pip install -r requirements.txt && python manage.py migrate && python seed.py",
        "syntax_check_backend": "cd backend && python -m py_compile $(find . -name '*.py' -not -path './.venv/*' | tr '\\n' ' ')",
        "startup_check_backend": "cd backend && python manage.py check --deploy 2>&1 || python manage.py check 2>&1",
        "vite_proxy": True,
        "api_prefix": "/api/",
        "import_style": "django_apps",
        "backend_import_note": "Backend uses Django app structure. Views import from local app modules: `from .models import X`, `from .serializers import X`. Never use absolute package paths like `from backend.api.models import X` unless crossing app boundaries.",
        "frontend_import_note": "Frontend API calls use relative paths like `/api/doctors/` (no hostname). Vite proxies `/api` to localhost:8000. Never hardcode `http://localhost:8000` in components.",
        "file_extensions": {"components": ".jsx", "pages": ".jsx", "hooks": ".js", "utils": ".js"},
        "required_files": [
            "frontend/package.json",
            "frontend/vite.config.js",
            "frontend/src/main.jsx",
            "frontend/src/App.jsx",
            "backend/manage.py",
            "backend/requirements.txt",
        ],
        "package_json_scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
        "vite_version": "^4.5.2",
        "notes": "Use Vite 4.x NOT 5.x on Windows (Rollup 4 native binary issue). Use JSX files not TSX. Django views are class-based or DRF ViewSets. Run migrations before seed.",
    },

    # ─── React (Vite) + FastAPI ─────────────────────────────────────────────
    "react_vite_fastapi": {
        "label": "React + Vite + FastAPI",
        "frontend_framework": "React 18 with Vite 4, React Router v6, Tailwind CSS, Axios",
        "backend_framework": "FastAPI with SQLAlchemy + SQLite, Pydantic v2, Uvicorn",
        "frontend_dir": "frontend",
        "backend_dir": "backend",
        "frontend_port": 5173,
        "backend_port": 8001,
        "frontend_entry": "frontend/src/main.jsx",
        "backend_entry": "backend/main.py",
        "frontend_run": "cd frontend && npm run dev",
        "backend_run": "cd backend && uvicorn main:app --reload --port 8001",
        "install_frontend": "cd frontend && npm install",
        "install_backend": "cd backend && pip install -r requirements.txt && python seed.py",
        "syntax_check_backend": "cd backend && python -m py_compile $(find . -name '*.py' -not -path './.venv/*' | tr '\\n' ' ')",
        "startup_check_backend": "cd backend && python -c \"from main import app; print('OK')\"",
        "vite_proxy": True,
        "api_prefix": "/api/",
        "import_style": "flat",
        "backend_import_note": "CRITICAL: Backend runs as `uvicorn main:app --port 8001` from inside the `backend/` directory. All Python imports must be FLAT (no package prefix). Use `from database import engine` NOT `from backend.database import engine`. Use `from models import User` NOT `from backend.models import User`. Routers import from their siblings: `from database import get_db`, `from models import Doctor`, `from schemas import DoctorResponse`.",
        "frontend_import_note": "Frontend API calls use relative paths like `/api/doctors` (no hostname). Vite proxies `/api` to localhost:8001. Never hardcode `http://localhost:8001` in components.",
        "file_extensions": {"components": ".jsx", "pages": ".jsx", "hooks": ".js", "utils": ".js"},
        "required_files": [
            "frontend/package.json",
            "frontend/vite.config.js",
            "frontend/src/main.jsx",
            "frontend/src/App.jsx",
            "backend/main.py",
            "backend/requirements.txt",
            "backend/database.py",
        ],
        "package_json_scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
        "vite_version": "^4.5.2",
        "notes": "Use Vite 4.x NOT 5.x on Windows. Use JSX not TSX. FastAPI routers use flat imports. SQLAlchemy sessions via Depends(get_db). Run `python seed.py` from inside backend/ dir.",
    },

    # ─── Next.js + Django ───────────────────────────────────────────────────
    "nextjs_django": {
        "label": "Next.js 14 App Router + Django REST Framework",
        "frontend_framework": "Next.js 14 with App Router, Tailwind CSS, TypeScript",
        "backend_framework": "Django 4 with Django REST Framework",
        "frontend_dir": "frontend",
        "backend_dir": "backend",
        "frontend_port": 3000,
        "backend_port": 8000,
        "frontend_entry": "frontend/src/app/layout.tsx",
        "backend_entry": "backend/manage.py",
        "frontend_run": "cd frontend && npm run dev",
        "backend_run": "cd backend && python manage.py runserver 8000",
        "install_frontend": "cd frontend && npm install",
        "install_backend": "cd backend && pip install -r requirements.txt && python manage.py migrate && python seed.py",
        "syntax_check_backend": "cd backend && python -m py_compile $(find . -name '*.py' -not -path './.venv/*' | tr '\\n' ' ')",
        "startup_check_backend": "cd backend && python manage.py check 2>&1",
        "vite_proxy": False,
        "api_prefix": "http://localhost:8000/api/",
        "import_style": "django_apps",
        "backend_import_note": "Django app structure. Use `from .models import X` within app.",
        "frontend_import_note": "Next.js fetches from `http://localhost:8000/api/` in server components or uses env var NEXT_PUBLIC_API_URL. Use `'use client'` directive for interactive components.",
        "file_extensions": {"components": ".tsx", "pages": ".tsx", "hooks": ".ts", "utils": ".ts"},
        "required_files": [
            "frontend/package.json",
            "frontend/src/app/layout.tsx",
            "frontend/src/app/page.tsx",
            "backend/manage.py",
            "backend/requirements.txt",
        ],
        "package_json_scripts": {"dev": "next dev", "build": "next build", "start": "next start"},
        "vite_version": None,
        "notes": "Next.js 14 App Router. Files in src/app/ are server components by default. Add 'use client' for hooks/state. TSX for all React files.",
    },

    # ─── Next.js + FastAPI ──────────────────────────────────────────────────
    "nextjs_fastapi": {
        "label": "Next.js 14 App Router + FastAPI",
        "frontend_framework": "Next.js 14 with App Router, Tailwind CSS, TypeScript",
        "backend_framework": "FastAPI with SQLAlchemy + SQLite, Pydantic v2, Uvicorn",
        "frontend_dir": "frontend",
        "backend_dir": "backend",
        "frontend_port": 3000,
        "backend_port": 8000,
        "frontend_entry": "frontend/src/app/layout.tsx",
        "backend_entry": "backend/main.py",
        "frontend_run": "cd frontend && npm run dev",
        "backend_run": "cd backend && uvicorn main:app --reload --port 8000",
        "install_frontend": "cd frontend && npm install",
        "install_backend": "cd backend && pip install -r requirements.txt && python seed.py",
        "syntax_check_backend": "cd backend && python -c \"from main import app; print('OK')\"",
        "startup_check_backend": "cd backend && python -c \"from main import app; print('OK')\"",
        "vite_proxy": False,
        "api_prefix": "http://localhost:8000/api/",
        "import_style": "flat",
        "backend_import_note": "CRITICAL: Flat imports. `from database import get_db` NOT `from backend.database import get_db`.",
        "frontend_import_note": "API calls to `http://localhost:8000/api/`. In Server Components use fetch(). In Client Components use axios with full URL.",
        "file_extensions": {"components": ".tsx", "pages": ".tsx", "hooks": ".ts", "utils": ".ts"},
        "required_files": ["frontend/package.json", "frontend/src/app/layout.tsx", "backend/main.py", "backend/requirements.txt"],
        "package_json_scripts": {"dev": "next dev", "build": "next build"},
        "vite_version": None,
        "notes": "Flat imports in backend. TSX for all React files.",
    },

    # ─── React (Vite) + Flask ───────────────────────────────────────────────
    "react_vite_flask": {
        "label": "React + Vite + Flask",
        "frontend_framework": "React 18 with Vite 4, React Router v6, Tailwind CSS, Axios",
        "backend_framework": "Flask with Flask-SQLAlchemy + SQLite, Flask-CORS",
        "frontend_dir": "frontend",
        "backend_dir": "backend",
        "frontend_port": 5173,
        "backend_port": 5000,
        "frontend_entry": "frontend/src/main.jsx",
        "backend_entry": "backend/app.py",
        "frontend_run": "cd frontend && npm run dev",
        "backend_run": "cd backend && python app.py",
        "install_frontend": "cd frontend && npm install",
        "install_backend": "cd backend && pip install -r requirements.txt && python seed.py",
        "syntax_check_backend": "cd backend && python -m py_compile $(find . -name '*.py' | tr '\\n' ' ')",
        "startup_check_backend": "cd backend && python -c \"from app import app; print('OK')\"",
        "vite_proxy": True,
        "api_prefix": "/api/",
        "import_style": "flat",
        "backend_import_note": "Flat imports. `from models import db, User`. All backend files in backend/ root.",
        "frontend_import_note": "Vite proxies `/api` to localhost:5000. Use `/api/` paths.",
        "file_extensions": {"components": ".jsx", "pages": ".jsx", "hooks": ".js", "utils": ".js"},
        "required_files": ["frontend/package.json", "frontend/vite.config.js", "backend/app.py", "backend/requirements.txt"],
        "package_json_scripts": {"dev": "vite", "build": "vite build"},
        "vite_version": "^4.5.2",
        "notes": "Flask on port 5000. Vite proxies /api to :5000. JSX not TSX.",
    },

    # ─── React (Vite) only (no backend) ────────────────────────────────────
    "react_vite_only": {
        "label": "React + Vite (frontend only)",
        "frontend_framework": "React 18 with Vite 4, React Router v6, Tailwind CSS",
        "backend_framework": None,
        "frontend_dir": ".",
        "backend_dir": None,
        "frontend_port": 5173,
        "backend_port": None,
        "frontend_entry": "src/main.jsx",
        "backend_entry": None,
        "frontend_run": "npm run dev",
        "backend_run": None,
        "install_frontend": "npm install",
        "install_backend": None,
        "syntax_check_backend": None,
        "startup_check_backend": None,
        "vite_proxy": False,
        "api_prefix": None,
        "import_style": None,
        "backend_import_note": None,
        "frontend_import_note": "No backend. Use localStorage, mock data, or external APIs directly.",
        "file_extensions": {"components": ".jsx", "pages": ".jsx"},
        "required_files": ["package.json", "vite.config.js", "src/main.jsx"],
        "package_json_scripts": {"dev": "vite", "build": "vite build"},
        "vite_version": "^4.5.2",
        "notes": "Frontend only. All data is mocked or from external APIs.",
    },

    # React frontend MVP with an explicit mock data layer.
    "react_vite_mock": {
        "label": "React + Vite (frontend-only mock data MVP)",
        "frontend_framework": "React 18 with Vite 4, React Router v6, Tailwind CSS, lucide-react",
        "backend_framework": None,
        "frontend_dir": ".",
        "backend_dir": None,
        "frontend_port": 5173,
        "backend_port": None,
        "frontend_entry": "src/main.jsx",
        "backend_entry": None,
        "frontend_run": "npm run dev",
        "backend_run": None,
        "install_frontend": "npm install",
        "install_backend": None,
        "syntax_check_backend": None,
        "startup_check_backend": None,
        "vite_proxy": False,
        "api_prefix": None,
        "import_style": "frontend_mock",
        "backend_import_note": None,
        "frontend_import_note": "No backend. Do not use fetch, axios, API clients, proxy config, or localhost URLs. Put rich realistic demo data in src/mockData.js and import it directly.",
        "file_extensions": {"components": ".jsx", "pages": ".jsx", "hooks": ".js", "utils": ".js"},
        "required_files": [
            "package.json",
            "vite.config.js",
            "src/main.jsx",
            "src/App.jsx",
            "src/mockData.js",
        ],
        "package_json_scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
        "vite_version": "^4.5.2",
        "notes": "Frontend-only MVP. Use rich hardcoded demo data from src/mockData.js so the app works instantly with zero network calls.",
    },
}

# Default fallback
_CONVENTIONS["react_vite_only"] = _CONVENTIONS["react_vite_only"]
_DEFAULT_KEY = "react_vite_mock"


def get_conventions(tech_stack: str) -> dict:
    """Return the conventions dict for a given tech_stack string."""
    key = detect_stack_key(tech_stack)
    return _CONVENTIONS.get(key, _CONVENTIONS[_DEFAULT_KEY])


def build_constraint_block(tech_stack: str) -> str:
    """
    Returns a string to inject into every LLM system/user prompt.
    This is NOT a suggestion — it overrides any LLM preference.
    """
    c = get_conventions(tech_stack)
    lines = [
        "===============================================",
        "HARD ARCHITECTURAL CONSTRAINTS - DO NOT DEVIATE",
        "===============================================",
        f"Stack:          {c['label']}",
        f"Frontend:       {c['frontend_framework']}",
    ]
    if c.get("backend_framework"):
        lines.append(f"Backend:        {c['backend_framework']}")
    lines += [
        f"Frontend port:  {c['frontend_port']}",
    ]
    if c.get("backend_port"):
        lines.append(f"Backend port:   {c['backend_port']}")
    if c.get("backend_import_note"):
        lines.append(f"Import rule:    {c['backend_import_note']}")
    if c.get("frontend_import_note"):
        lines.append(f"API rule:       {c['frontend_import_note']}")
    if c.get("vite_version"):
        lines.append(f"Vite version:   {c['vite_version']} (NOT 5.x)")
    if "react" in str(c.get("frontend_framework", "")).lower():
        lines.append("Icons:          Use ONLY lucide-react. Never use @heroicons/react or @mui/icons-material.")
        lines.append("Images:         Prefer Unsplash image URLs for hero/detail imagery; use https://picsum.photos/seed/{stable-id}/300/200 only as fallback.")
        lines.append("Frontend UX:    Must be frontend-first and fully populated on first load. Generate/import rich local mock data even for backend stacks.")
        lines.append("No blank UI:     React pages must not depend on live API data for initial content. No permanent spinners, empty grids, or login walls in the starter demo.")
        lines.append("Design:         Avoid generic blue-gray admin styling. Use a domain-specific design system with display/body typography, palette, rich sections, and polished responsive layouts.")
        lines.append("Interactions:   Include local state for search, filters, tabs, selected cards, forms/workflows, confirmations, and dashboard panels.")
    lines.append(f"File exts:      {c['file_extensions']}")
    if c.get("notes"):
        lines.append(f"Notes:          {c['notes']}")
    lines.append("===============================================")
    return "\n".join(lines)


def get_vite_config(backend_port: int | None, frontend_port: int = 5173) -> str:
    """Returns a correct vite.config.js for React+Vite projects."""
    if backend_port:
        proxy_block = f"""
  server: {{
    port: {frontend_port},
    proxy: {{
      '/api': {{
        target: 'http://localhost:{backend_port}',
        changeOrigin: true,
      }},
    }},
  }},"""
    else:
        proxy_block = f"\n  server: {{ port: {frontend_port} }},"

    return f"""import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({{
  plugins: [react()],{proxy_block}
}})
"""


def get_react_tailwind_config() -> str:
    """Returns a richer default Tailwind config for generated React apps."""
    return """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        ink: "#10251f",
        cream: "#f8f3ea",
        paper: "#fffdf8",
        sage: "#b9cfad",
        clay: "#f18455",
        lagoon: "#11675d",
        mist: "#e8eee7",
      },
      boxShadow: {
        soft: "0 18px 50px rgba(16, 37, 31, 0.10)",
        lift: "0 10px 26px rgba(16, 37, 31, 0.14)",
      },
      borderRadius: {
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
    },
  },
  plugins: [],
}
"""


def get_react_index_css() -> str:
    """Returns polished base CSS and reusable component classes for React apps."""
    return """@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,650;9..144,750&family=Inter:wght@400;500;600;700;800&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    color-scheme: light;
    --app-bg: #f8f3ea;
    --app-ink: #10251f;
    --app-muted: #5a6c64;
    --app-line: rgba(16, 37, 31, 0.14);
  }

  html {
    scroll-behavior: smooth;
  }

  body {
    margin: 0;
    min-height: 100vh;
    background:
      radial-gradient(circle at top right, rgba(185, 207, 173, 0.32), transparent 34rem),
      linear-gradient(180deg, #fffdf8 0%, var(--app-bg) 100%);
    color: var(--app-ink);
    font-family: Inter, ui-sans-serif, system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
    text-rendering: geometricPrecision;
  }

  h1, h2, h3, .font-display {
    font-family: Fraunces, Georgia, serif;
    letter-spacing: 0;
  }

  button, input, textarea, select {
    font: inherit;
  }
}

@layer components {
  .page-shell {
    @apply min-h-screen bg-cream text-ink;
  }

  .section-wrap {
    @apply mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8;
  }

  .surface-card {
    @apply rounded-2xl border border-ink/10 bg-paper shadow-soft;
  }

  .pill {
    @apply inline-flex items-center gap-2 rounded-full border border-ink/10 bg-paper px-4 py-2 text-sm font-semibold text-ink shadow-sm;
  }

  .btn-primary {
    @apply inline-flex items-center justify-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-bold text-white shadow-lift transition hover:-translate-y-0.5 hover:bg-lagoon;
  }

  .btn-secondary {
    @apply inline-flex items-center justify-center gap-2 rounded-full border border-ink/10 bg-paper px-5 py-3 text-sm font-bold text-ink transition hover:-translate-y-0.5 hover:border-ink/25;
  }

  .eyebrow {
    @apply text-xs font-bold uppercase text-lagoon/80;
  }

  .muted-copy {
    @apply text-base leading-7 text-ink/65;
  }
}
"""
