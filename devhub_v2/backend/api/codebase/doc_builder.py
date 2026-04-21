import html
import json
import logging
import os
import posixpath
import re
from pathlib import Path, PurePosixPath
from typing import Any

from agents.core.base import BaseAgent
from agents.docs.documentation import generate_codebase_reference_sync
from agents.memory.store import build_memory_context
from agents.core.workspace import SKIP_DIRS
from core.models import DocumentationRun, Feature, Project

from api.project_utils import DEVHUB_META_DIR, _project_ai_config
from api.workspace.runtime import detect_runtime

logger = logging.getLogger(__name__)

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
        from agents.core.base import BaseAgent
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

