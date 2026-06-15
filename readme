# DevHub V2

DevHub V2 is an AI-assisted engineering workspace built around a single shared project record. It combines project intake, architecture and blueprint generation, work-item tracking, chat-driven coding help, and a browser-based code workspace with runtime controls.

The stack is split between:

- `backend/`: Django API, agent orchestration, workspace/runtime management, memory, and persistence
- `frontend/`: React + TypeScript + Vite application for dashboard, blueprint, onboarding, work items, chat, and code editing

## What It Does

- Create a new starter project from an idea
- Import an existing GitHub repository
- Connect GitHub in the browser and import repos your account can access
- Connect an existing local folder
- Generate blueprint and codebase reference documentation from repository evidence
- Track work items through a shared delivery pipeline
- Edit files, run setup, launch the project runtime, and view previews inside the workspace
- Use project-aware AI chat grounded in the active codebase

## Core Product Surfaces

- `Dashboard`
  Creates or imports projects and manages global AI settings
- `Project View`
  Hosts overview, onboarding, blueprint, work items, chat, and workspace
- `Blueprint`
  Repository-aware architecture wiki with API, database, workflows, setup, quality, and knowledge tabs
- `Workspace`
  Monaco editor, file tree, runtime controls, terminal streaming, and preview

## Local Setup

### Backend

From `backend/`:

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

If your shell already uses a project-level virtual environment, activate that instead of creating a new one.

### Frontend

From `frontend/`:

```bash
npm install
npm run dev
```

The frontend runs on Vite and talks to the backend API at `http://localhost:8000/api`.

### Optional GitHub Connection Setup

To enable the browser-based `Connect GitHub` import flow, configure a GitHub OAuth app for local development and expose these environment variables to the backend:

```bash
DEVHUB_GITHUB_CLIENT_ID=...
DEVHUB_GITHUB_CLIENT_SECRET=...
DEVHUB_GITHUB_SCOPES="repo read:org"
```

Register this callback URL in the GitHub OAuth app:

```text
http://localhost:8000/api/integrations/github/callback/
```

Once configured, users can connect GitHub from the dashboard, browse accessible repos, and keep issues and pull requests linked inside the project view.

## Repository Layout

```text
devhub_v2/
  backend/
    agents/         AI agents, codebase analysis, documentation, memory helpers
    api/            REST endpoints used by the frontend
    core/           Primary Django models such as Project, Feature, Changeset, and memories
    editor/         WebSocket and editor-related backend support
    sandbox/        Process execution and workspace command handling
    integrations/   Third-party integration models and views
    devhub_backend/ Django settings and root URL configuration
  frontend/
    src/
      components/   Blueprint, onboarding, workspace, chat, diagrams, editor UI
      pages/        Dashboard and project-level pages
      types/        Frontend type shims and shared declarations
  docs/             Generated codebase reference output
  data/             Local project/workspace runtime state
  .devhub/          Generated repo metadata, blueprint context, and local documentation state
```

## Important Notes

- `.devhub/`, `data/`, `docs/`, and `backend/db.sqlite3` are local/generated state and are intentionally ignored in git.
- The current backend uses SQLite for local development.
- CORS is open and debug settings are development-friendly by default; this repository is not production-hardened as-is.

## Validation

Frontend:

```bash
npm run build
```

Backend:

```bash
python manage.py test
```

## Current Direction

DevHub is evolving from a public-repo import tool into a deeper project operating layer. The current direction is tighter repository connectivity, richer project health and blueprint guidance, and integrated GitHub context so code, documentation, issues, pull requests, and workspace execution can live in one flow.
