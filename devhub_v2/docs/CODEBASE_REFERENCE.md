# DevHub v2 Codebase Reference

## What This Project Is

DevHub v2 is a full-stack AI-assisted project workspace. It lets a user:

- create a new project scaffold, import a GitHub repository, or connect a local folder
- generate a living architecture blueprint from the codebase
- manage work through shared work items / pipeline stages
- edit files in a workspace with a Monaco-based editor
- run setup/runtime commands inside a managed sandbox
- use AI chat and AI implementation flows against the active project

The app is split into:

- a Django backend in `backend/`
- a React + Vite frontend in `frontend/`
- persistent project/workspace data in `data/`

---

## Top-Level Folder Map

### `/backend`

Main Django application. Owns projects, blueprint generation, work items, chat, workspace APIs, sandbox process control, and agent orchestration.

### `/frontend`

React client. Owns the dashboard, project view, blueprint UI, onboarding UI, work items UI, and code workspace.

### `/data`

Runtime data storage. Contains managed projects and workspace metadata used by the workspace manager.

### `/venv`

Python virtual environment for the backend.

---

## Runtime Architecture

### Frontend

- React + React Router
- Monaco editor
- xterm terminal
- Mermaid diagrams
- talks to Django over HTTP and WebSocket

### Backend

- Django 6
- Django Channels + Daphne
- SQLite
- OpenAI-backed agent classes in `backend/agents/`
- custom sandbox process manager in `backend/sandbox/executor.py`

### Data Flow

1. User creates/imports/selects a project in the frontend.
2. Frontend calls Django API endpoints under `/api/...`.
3. Backend stores project/work item state in SQLite.
4. Backend creates a workspace reference for the project path.
5. Frontend reads and writes files through workspace endpoints.
6. Runtime/setup processes are launched by the sandbox manager.
7. AI agents generate blueprint/spec/code using project context and memory.

---

## Frontend Routes

Defined in `frontend/src/App.tsx`.

| Route | Component | Purpose |
| --- | --- | --- |
| `/` | `Dashboard` | Project list, create/import/open flow |
| `/project/:id` | `ProjectView` | Main project workspace with overview, onboarding, blueprint, work items, and code |

---

## HTTP API Reference

Defined in `backend/devhub_backend/urls.py` and `backend/api/urls.py`.

Base prefix: `/api`

### Projects

| Method | URL | View | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/projects/` | `list_projects` | Return all projects for the dashboard |
| `POST` | `/api/projects/create/` | `create_project` | Create starter/imported/local project and initialize workspace |
| `POST` | `/api/projects/suggest/` | `suggest_project_details` | AI-assisted name/description/stack suggestion |
| `POST` | `/api/projects/import/github/inspect/` | `inspect_github_import` | Clone a repo temporarily and inspect stack/shape before import |
| `GET` or `POST` | `/api/projects/import/folder/pick/` | `pick_local_folder` | Open native folder picker and return selected path |
| `POST` | `/api/projects/import/folder/inspect/` | `inspect_folder_import` | Inspect a local folder before attaching it as a project |
| `GET` | `/api/projects/<project_id>/` | `get_project` | Return full project payload including blueprint, work items, runtime, onboarding summary |
| `POST` or `PATCH` | `/api/projects/<project_id>/update/` | `update_project` | Update project metadata and trigger blueprint refresh |
| `DELETE` | `/api/projects/<project_id>/delete/` | `delete_project` | Delete project and associated workspace metadata |

### Work Items / Pipeline

| Method | URL | View | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/projects/<project_id>/features/` | `project_features` | Return project work items |
| `POST` | `/api/projects/<project_id>/features/` | `project_features` | Create a work item and trigger AI spec generation |
| `POST` | `/api/projects/<project_id>/pipeline/action/` | `pipeline_action` | Advance, reject, approve, or AI-implement a work item |

### Chat / Agents

| Method | URL | View | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/projects/<project_id>/chat/` | `project_chat` | Return chat history |
| `POST` | `/api/projects/<project_id>/chat/` | `project_chat` | Ask AI for help or apply AI code changes |
| `POST` | `/api/projects/<project_id>/agent/start/` | `start_agent` | Trigger an agent run, currently mainly blueprint/architect flow |

### Workspace / Files / Runtime

| Method | URL | View | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/workspace/<workspace_id>/fs/` | `workspace_fs` | Read directory listing or file content |
| `POST` | `/api/workspace/<workspace_id>/fs/` | `workspace_fs` | Save file content into the workspace |
| `POST` | `/api/workspace/<workspace_id>/spawn/` | `workspace_spawn` | Spawn a terminal-like process in the workspace |
| `GET` | `/api/workspace/<workspace_id>/process/<process_id>/` | `workspace_process_io` | Poll process output/status |
| `POST` | `/api/workspace/<workspace_id>/process/<process_id>/` | `workspace_process_io` | Send stdin to a running process |
| `DELETE` | `/api/workspace/<workspace_id>/process/<process_id>/` | `workspace_process_io` | Kill a running process |
| `GET` | `/api/workspace/<workspace_id>/runtime/` | `workspace_runtime` | Detect runtime and return runtime status/payload |
| `POST` | `/api/workspace/<workspace_id>/runtime/` | `workspace_runtime` | Start or restart project runtime |
| `DELETE` | `/api/workspace/<workspace_id>/runtime/` | `workspace_runtime` | Stop project runtime |
| `GET` | `/api/workspace/<workspace_id>/setup/` | `workspace_setup` | Return setup-command status |
| `POST` | `/api/workspace/<workspace_id>/setup/` | `workspace_setup` | Run project setup command |
| `DELETE` | `/api/workspace/<workspace_id>/setup/` | `workspace_setup` | Stop setup process |

### Common Request Payloads

These are the main request bodies inferred directly from `backend/api/views.py`.

#### `POST /api/projects/suggest/`

```json
{
  "idea": "AI coding workspace for internal teams",
  "source_type": "starter",
  "tech_stack": ["React", "Django"]
}
```

Returns suggested project metadata such as name, description, and normalized stack.

#### `POST /api/projects/create/`

Starter project:

```json
{
  "name": "DevHub",
  "description": "AI-assisted engineering workspace",
  "tech_stack": ["React", "Django"]
}
```

GitHub import:

```json
{
  "name": "Code Server",
  "description": "Imported repository",
  "github_url": "https://github.com/example/repo",
  "tech_stack": ["TypeScript", "Node.js"]
}
```

Local folder:

```json
{
  "name": "Internal Tool",
  "description": "Connected local project",
  "local_path": "C:/path/to/project",
  "tech_stack": ["React", "FastAPI"]
}
```

Response includes:

- `id`
- `name`
- `description`
- `workspace_id`
- `status`
- `runtime`

#### `POST /api/projects/import/github/inspect/`

```json
{
  "github_url": "https://github.com/example/repo",
  "idea": "Optional import hint"
}
```

Returns an inspection object with:

- `name`
- `description`
- `tech_stack`
- `detected_stack`
- `root_name`
- `structure_preview`
- `source_summary`
- `runtime`

#### `POST /api/projects/import/folder/inspect/`

```json
{
  "local_path": "C:/path/to/project",
  "idea": "Optional import hint"
}
```

Returns the same inspection shape as GitHub import.

#### `POST /api/projects/<project_id>/update/`

```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "github_url": "https://github.com/example/repo",
  "tech_stack": ["React", "Django", "PostgreSQL"]
}
```

#### `POST /api/projects/<project_id>/features/`

```json
{
  "title": "Realtime collaboration",
  "description": "Allow multiple editors to work in the same file",
  "created_by": "Developer"
}
```

Creates a work item and asynchronously generates `Feature.spec`.

#### `POST /api/projects/<project_id>/pipeline/action/`

```json
{
  "feature_id": "uuid",
  "action": "implement",
  "by": "Developer",
  "comment": "Optional note"
}
```

Valid actions:

- `advance`
- `reject`
- `approve`
- `implement`

#### `POST /api/projects/<project_id>/chat/`

```json
{
  "content": "Add a feature to export blueprint data as markdown",
  "selected_file": "frontend/src/pages/ProjectView.tsx",
  "selected_content": "...optional active file content...",
  "apply_changes": true
}
```

Response includes:

- `user_message`
- `assistant_message`
- `applied_changes`

#### `POST /api/workspace/<workspace_id>/fs/`

```json
{
  "path": "src/App.tsx",
  "content": "full file contents here"
}
```

#### `POST /api/workspace/<workspace_id>/spawn/`

```json
{
  "command": "cmd.exe"
}
```

#### `POST /api/workspace/<workspace_id>/process/<process_id>/`

```json
{
  "input": "npm run dev\n"
}
```

#### `POST /api/workspace/<workspace_id>/runtime/`

Optional custom command:

```json
{
  "command": "npm run dev"
}
```

If omitted, backend uses the detected runtime command.

#### `POST /api/workspace/<workspace_id>/setup/`

Optional custom command:

```json
{
  "command": "npm install"
}
```

If omitted, backend uses the detected setup command.

---

## WebSocket Reference

Defined in `backend/editor/routing.py`.

| URL | Consumer | Purpose |
| --- | --- | --- |
| `ws://localhost:8000/ws/workspace/<workspace_id>/editor/` | `EditorConsumer` | Collaborative file edit broadcast |
| `ws://localhost:8000/ws/workspace/<workspace_id>/process/<process_id>/` | `ProcessConsumer` | Live process output + stdin bridge |

### `EditorConsumer`

File: `backend/editor/consumers.py`

- joins a workspace-specific channel layer group
- accepts `edit` messages with `path` and `content`
- rebroadcasts edits to other listeners in the same workspace

### `ProcessConsumer`

File: `backend/editor/consumers.py`

- attaches to a specific sandbox process
- polls sandbox output in an async loop
- streams process output/status to the browser
- forwards terminal input from the browser to the process stdin

---

## Database Model Reference

Defined mainly in `backend/core/models.py`.

### `Project`

Main top-level record.

Important fields:

- `id`: UUID primary key
- `name`, `description`
- `github_url`: source repo if imported from GitHub
- `local_path`: actual filesystem path for the project
- `workspace_id`: workspace registry key used by the workspace manager
- `tech_stack`: JSON list of stack tags
- `blueprint`: generated architecture wiki JSON
- `status`
- `registered_at`

### `Feature`

Represents a work item in the delivery flow.

Important fields:

- `project`
- `title`, `description`
- `status`: pipeline stage
- `spec`: AI-generated implementation spec
- `suggestions`

### `FeatureHistory`

Audit trail for stage transitions and lifecycle actions.

### `FeatureApproval`

Approval records for a work item.

### `TestResult`

Stores AI-simulated or generated testing output for a feature.

### `Comment`

Simple comments attached to a feature.

### `Changeset`

Represents a tracked AI/user code change batch.

### `FileDiff`

Stores per-file diff content for a changeset.

### `AgentRun`

Tracks long-running or triggered agent executions.

### `ChatMessage`

Stores project chat history.

### `WorkingMemory`

Short-horizon compressed context for a project + scope.

### `EpisodicMemory`

Persistent session/decision history for a project.

### `SemanticMemory`

Chunked codebase memory for retrieval over files/symbols/content.

### Other model files

- `backend/api/models.py`: currently empty placeholder
- `backend/editor/models.py`: currently empty placeholder
- `backend/sandbox/models.py`: currently empty placeholder
- `backend/integrations/models.py`: currently empty placeholder

---

## Backend File Reference

### Core Django Entry / Config

#### `backend/manage.py`

Standard Django management entry point.

#### `backend/devhub_backend/settings.py`

Main Django settings:

- loads `.env`
- uses SQLite
- enables Channels/Daphne
- enables CORS for local frontend development
- registers apps: `core`, `editor`, `agents`, `sandbox`, `integrations`, `api`

#### `backend/devhub_backend/urls.py`

Top-level URL configuration. Mounts:

- `/admin/`
- `/api/`

#### `backend/devhub_backend/asgi.py`

ASGI entry point for Channels/Daphne usage.

#### `backend/devhub_backend/wsgi.py`

WSGI entry point.

### API Layer

#### `backend/api/urls.py`

Public HTTP API registry for projects, work items, chat, workspace, runtime, and imports.

#### `backend/api/views.py`

The main backend orchestration file. This is the most important backend file in the project.

It contains:

- project create/import/update/delete flows
- work item create/list/pipeline actions
- chat endpoint
- blueprint generation trigger
- runtime detection and runtime control
- workspace filesystem/process endpoints
- scaffold generation helpers
- runtime URL detection helpers
- onboarding/work-item summary builders
- memory-aware implementation orchestration

Key public views inside this file:

- `suggest_project_details`
- `inspect_github_import`
- `pick_local_folder`
- `inspect_folder_import`
- `list_projects`
- `create_project`
- `get_project`
- `update_project`
- `delete_project`
- `project_features`
- `pipeline_action`
- `project_chat`
- `start_agent`
- `workspace_fs`
- `workspace_spawn`
- `workspace_process_io`
- `workspace_runtime`
- `workspace_setup`

Important internal helper areas:

- scaffold builders:
  - `_static_scaffold_files`
  - `_react_scaffold_files`
  - `_fastapi_scaffold_files`
  - `_django_scaffold_files`
- calculator-specific starter:
  - `_is_calculator_project`
  - `_react_calculator_app_source`
  - `_react_calculator_styles_source`
- runtime detection:
  - `detect_runtime`
  - `_preview_url_for_command`
  - `_vite_config_preview_url`
  - `_node_preview_url`
  - `_runtime_response_payload`
- blueprint/document building:
  - `generate_blueprint_sync`
  - `_build_repository_map_from_context`
  - `_build_directory_guide_from_context`
  - `_build_file_structure_visualizer`
  - `_build_change_guide`
  - `_enrich_blueprint_document`
- implementation pipeline:
  - `_create_implementation_plan`
  - `_collect_relevant_files`
  - `_run_validation_suite`
  - `_review_attempt`
  - `_run_multi_agent_implementation`
  - `implement_feature_sync`
  - `apply_chat_changes`

#### `backend/api/tests.py`

Regression coverage for API flows.

#### `backend/api/admin.py`, `backend/api/apps.py`

Django app boilerplate.

### Core App

#### `backend/core/models.py`

Primary persistence layer for project/work item/chat/memory models.

#### `backend/core/migrations/0001_initial.py`

Initial schema.

#### `backend/core/migrations/0002_project_workspace_id.py`

Adds workspace linkage to `Project`.

#### `backend/core/migrations/0003_agent_memory_models.py`

Adds working/episodic/semantic memory tables.

#### `backend/core/admin.py`, `backend/core/apps.py`, `backend/core/tests.py`, `backend/core/views.py`

Mostly standard Django app scaffolding; current business logic is not centered here.

### Agents App

#### `backend/agents/base.py`

Base wrapper around the OpenAI client.

Responsibilities:

- create chat completions
- maintain lightweight chat history
- parse JSON responses safely

#### `backend/agents/architect.py`

Generates the project blueprint / internal wiki from repo evidence, summaries, and explorer context.

#### `backend/agents/planner.py`

Creates structured implementation plans before code changes.

#### `backend/agents/coder.py`

Writes actual file modifications into the workspace based on plan + context.

#### `backend/agents/feature.py`

Generates work item technical specs and fallback implementation payloads.

#### `backend/agents/memory.py`

Project memory and repo indexing layer.

Responsibilities:

- codebase scanning
- repo fingerprinting
- repo tree generation
- repository map cache
- semantic chunk indexing
- working/episodic memory compression
- instruction-file loading (`DEVHUB.md`, `AGENTS.md`, etc.)

#### `backend/agents/workspace.py`

Workspace registry / file access abstraction.

Responsibilities:

- register workspaces
- resolve workspace path from `workspace_id`
- read/write files securely inside workspace boundaries
- delete managed workspaces

#### `backend/agents/explorer.py`

Codebase exploration agent used to ground blueprint generation.

#### `backend/agents/reviewer.py`

Post-change review pass used inside the multi-agent implementation loop.

#### `backend/agents/scaffolder.py`

Optional AI scaffold generator used when API key is available.

#### `backend/agents/models.py`, `backend/agents/views.py`, `backend/agents/tests.py`, `backend/agents/admin.py`, `backend/agents/apps.py`

Mostly Django app support files. Core behavior is in the agent modules listed above.

### Editor App

#### `backend/editor/routing.py`

Defines workspace/process WebSocket routes.

#### `backend/editor/consumers.py`

Implements:

- `EditorConsumer`
- `ProcessConsumer`

#### `backend/editor/views.py`

Currently placeholder.

#### `backend/editor/models.py`

Currently placeholder.

### Sandbox App

#### `backend/sandbox/executor.py`

Custom process manager for runtime/setup/terminal execution.

Key classes:

- `ProcessHandle`
- `SandboxManager`

Capabilities:

- start background commands
- capture stdout/stderr
- query live status
- send stdin
- kill process trees

#### `backend/sandbox/views.py`, `backend/sandbox/models.py`

Currently placeholders; real sandbox behavior lives in `executor.py`.

### Integrations App

#### `backend/integrations/views.py`, `backend/integrations/models.py`

Currently placeholders for future integration work.

---

## Frontend File Reference

### Entry / App Shell

#### `frontend/src/main.tsx`

React entry point. Mounts `App` and imports global CSS.

#### `frontend/src/App.tsx`

Top-level router.

Routes:

- `Dashboard`
- `ProjectView`

#### `frontend/src/index.css`

Global styling / app-wide baseline styles.

#### `frontend/src/App.css`

Additional app styling.

### Pages

#### `frontend/src/pages/Dashboard.tsx`

Project creation/import/open landing page.

Responsibilities:

- load project list
- show create/import modal
- handle:
  - starter flow
  - GitHub inspect/import flow
  - local folder pick/inspect flow
- call project suggestion/import APIs
- navigate into a project

#### `frontend/src/pages/ProjectView.tsx`

Main product surface after a project is opened.

Responsibilities:

- fetch project payload
- choose active tab using backend `recommended_start_tab`
- render:
  - overview
  - onboarding
  - blueprint
  - work items
  - workspace
- create work items
- trigger pipeline actions
- trigger blueprint regeneration
- edit/delete project
- show implementation progress/completion UI

### Components

#### `frontend/src/components/CodeWorkspace.tsx`

The most important frontend component after `ProjectView`.

Responsibilities:

- file tree explorer
- file load/save
- preview pane
- runtime start/stop/setup
- embedded terminal
- embedded project chat
- WebSocket connections for process streams

Uses:

- `Editor.tsx`
- `Terminal.tsx`

#### `frontend/src/components/Editor.tsx`

Thin Monaco wrapper.

Responsibilities:

- configure editor theme
- render file editor
- expose content change handler

#### `frontend/src/components/Terminal.tsx`

Thin xterm wrapper.

Responsibilities:

- render terminal UI
- expose `write()` via ref
- send keyboard input back to workspace process

#### `frontend/src/components/BlueprintPanel.tsx`

Renders the generated blueprint / project wiki.

Sections include:

- overview
- repository
- services
- API
- database
- workflows
- setup
- quality
- knowledge

#### `frontend/src/components/OnboardingPanel.tsx`

Renders onboarding guidance connected to blueprint + work items + workspace.

Responsibilities:

- explain project entry path
- show AI suggestions
- show suggested work items
- connect user to blueprint/workspace/work items

#### `frontend/src/components/MermaidDiagram.tsx`

Mermaid rendering wrapper with diagram normalization and fallback/error handling.

#### `frontend/src/components/tsc_out.txt`

Generated artifact / helper output file; not part of product logic.

### Assets

#### `frontend/src/assets/hero.png`

Dashboard/marketing-style visual asset.

#### `frontend/src/assets/react.svg`, `frontend/src/assets/vite.svg`

Framework logos/assets.

---

## File/Folder Purpose Summary By Area

### `backend/api/`

Public HTTP contract and the main orchestration layer.

### `backend/core/`

Persistent database models for the project domain.

### `backend/agents/`

AI logic, memory, planning, coding, blueprint generation, and workspace abstractions.

### `backend/editor/`

WebSocket transport for collaborative editing and live process output.

### `backend/sandbox/`

Process execution and runtime management.

### `frontend/src/pages/`

Route-level UI.

### `frontend/src/components/`

Reusable high-value UI modules: blueprint, onboarding, editor, terminal, workspace.

### `data/projects/`

Managed project folders created or cloned by DevHub.

### `data/workspaces/`

Workspace metadata files keyed by workspace ID.

---

## Important Operational Behavior

### Project Creation Modes

The backend supports 3 project sources:

- starter scaffold
- GitHub import
- local folder attach

This logic lives mainly in `backend/api/views.py -> create_project`.

### Blueprint Generation

Blueprint generation is asynchronous and started in a background thread after project creation/update.

Main flow:

1. index codebase/memory
2. build codebase context
3. explore repo
4. generate architect blueprint
5. enrich deterministic sections
6. save into `Project.blueprint`

### Work Items / Pipeline

Frontend now treats Features + Pipeline as one shared work surface:

- list view
- board view

The backend still persists them through `Feature` + `FeatureHistory`.

### Workspace Runtime

Runtime and setup processes are controlled by:

- `workspace_runtime`
- `workspace_setup`
- `SandboxManager`

Preview readiness is derived from runtime detection and preview URL probing.

### AI Chat

`project_chat` can work in two modes:

- normal assistant response mode
- code-application mode for edit-like requests

When edit mode is triggered, backend attempts to:

- gather context
- plan change
- apply code changes
- record diffs/changesets

---

## Known Thin / Placeholder Areas

These files/apps exist but currently contain little or no business logic:

- `backend/api/models.py`
- `backend/core/views.py`
- `backend/editor/views.py`
- `backend/editor/models.py`
- `backend/sandbox/views.py`
- `backend/sandbox/models.py`
- `backend/integrations/views.py`
- `backend/integrations/models.py`

This means the actual behavior is more centralized than a typical Django app split; most important runtime behavior is concentrated in:

- `backend/api/views.py`
- `backend/core/models.py`
- `backend/agents/*.py`
- `backend/sandbox/executor.py`
- `frontend/src/pages/ProjectView.tsx`
- `frontend/src/components/CodeWorkspace.tsx`

---

## If You Need To Change Something, Start Here

### Add or change a public backend API

Edit:

- `backend/api/urls.py`
- `backend/api/views.py`

### Change database structure

Edit:

- `backend/core/models.py`
- create/update migrations in `backend/core/migrations/`

### Improve blueprint generation

Edit:

- `backend/agents/architect.py`
- `backend/agents/explorer.py`
- `backend/agents/memory.py`
- `backend/api/views.py`

### Improve AI coding / implementation

Edit:

- `backend/agents/planner.py`
- `backend/agents/coder.py`
- `backend/agents/reviewer.py`
- `backend/api/views.py`

### Change workspace file explorer / editor / preview behavior

Edit:

- `frontend/src/components/CodeWorkspace.tsx`
- `backend/api/views.py`
- `backend/sandbox/executor.py`
- `backend/editor/consumers.py`

### Change project navigation or tab flow

Edit:

- `frontend/src/pages/ProjectView.tsx`

### Change onboarding experience

Edit:

- `frontend/src/components/OnboardingPanel.tsx`
- `backend/api/views.py` for onboarding summary generation

### Change dashboard create/import flow

Edit:

- `frontend/src/pages/Dashboard.tsx`
- `backend/api/views.py`

---

## Suggested Next Docs To Add

This document is the codebase reference. The next useful docs would be:

- `docs/API_EXAMPLES.md`: example request/response bodies for every API
- `docs/WORKSPACE_RUNTIME.md`: runtime/setup/workspace lifecycle details
- `docs/AI_PIPELINE.md`: planner -> coder -> reviewer -> memory flow
- `docs/DB_SCHEMA.md`: table-by-table schema with relationships and sample rows
