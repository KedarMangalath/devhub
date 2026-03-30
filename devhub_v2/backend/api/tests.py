import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from api.views import _build_evidence_backed_workflows, _enrich_blueprint_document, _normalize_mermaid_chart, _stable_runtime_port, _write_deep_docs_progress, detect_runtime
from agents.api_reference import build_api_reference_catalog
from agents.architect import ArchitectAgent
from agents.base import BaseAgent, _vertexai_base_url_for_location, ai_config_is_usable, default_ai_config, normalize_ai_config
from agents.deep_documentation import DeepDocumentationAgent
from agents.memory import build_blueprint_context, build_memory_context, compress_recent_activity, index_semantic_memory, record_episode, retrieve_relevant_files, select_files_for_section
from agents.workspace import workspace_manager
from core.models import Changeset, ChatMessage, FileDiff, Project, SemanticMemory, WorkingMemory
from core.models import Feature, FeatureApproval


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class AiConfigDefaultsTests(TestCase):
    def test_default_ai_config_prefers_gemini_vertex_global(self):
        config = default_ai_config()
        self.assertEqual(config["provider"], "gemini")
        self.assertEqual(config["gemini_mode"], "vertexai")
        self.assertEqual(config["model"], "gemini-3.1-pro-preview")
        self.assertEqual(config["vertex_project"], "noted-computing-459609-n2")
        self.assertEqual(config["vertex_location"], "global")

    def test_vertex_ai_config_is_usable_with_project_id(self):
        config = normalize_ai_config(
            {
                "provider": "gemini",
                "gemini_mode": "vertexai",
                "model": "gemini-3.1-pro-preview",
                "vertex_project": "noted-computing-459609-n2",
                "vertex_location": "global",
            }
        )
        self.assertTrue(ai_config_is_usable(config))

    @patch("agents.base.shutil.which", return_value=None)
    def test_legacy_gemini_cli_config_falls_back_to_vertex_defaults(self, _mock_which):
        config = normalize_ai_config(
            {
                "provider": "gemini",
                "model": "gemini-3.1-pro-preview",
                "gemini_mode": "gemini_cli",
                "gemini_cli_command": "gemini",
                "vertex_project": "noted-computing-459609-n2",
                "vertex_location": "us-central1",
            }
        )
        self.assertEqual(config["gemini_mode"], "vertexai")
        self.assertEqual(config["vertex_location"], "global")
        self.assertTrue(ai_config_is_usable(config))

    @patch("agents.base.subprocess.run")
    @patch("agents.base.shutil.which")
    def test_vertex_token_lookup_accepts_windows_gcloud_cmd(self, mock_which, mock_run):
        mock_which.side_effect = lambda candidate: (
            r"C:\\Program Files\\Google\\Cloud SDK\\google-cloud-sdk\\bin\\gcloud.cmd"
            if candidate == "gcloud.cmd"
            else None
        )
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="vertex-token\n", stderr="")

        agent = BaseAgent(
            role="test",
            system_instruction="test",
            ai_config={
                "provider": "gemini",
                "gemini_mode": "vertexai",
                "model": "gemini-3.1-pro-preview",
                "vertex_project": "noted-computing-459609-n2",
                "vertex_location": "global",
            },
        )

        self.assertEqual(agent._resolve_vertex_access_token(), "vertex-token")
        self.assertEqual(mock_run.call_args.args[0][0], r"C:\\Program Files\\Google\\Cloud SDK\\google-cloud-sdk\\bin\\gcloud.cmd")

    def test_global_vertex_endpoint_uses_plain_aiplatform_host(self):
        self.assertEqual(
            _vertexai_base_url_for_location("global"),
            "https://aiplatform.googleapis.com/v1",
        )
        self.assertEqual(
            _vertexai_base_url_for_location("us-central1"),
            "https://us-central1-aiplatform.googleapis.com/v1",
        )


class PromptNeutralityTests(TestCase):
    def test_architect_agent_instruction_is_repo_generic(self):
        agent = ArchitectAgent(ai_config={})
        self.assertNotIn("DevHub platform", agent.system_instruction)

    def test_deep_documentation_prompts_avoid_devhub_specific_examples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "README.md").write_text("# Sample\n", encoding="utf-8")

            agent = DeepDocumentationAgent(ai_config={})
            captured_prompts: list[str] = []

            def fake_generate(prompt, response_schema=False):
                captured_prompts.append(str(prompt))
                if '"key_concepts"' in str(prompt):
                    return '{"key_concepts":[],"faq":[],"gotchas":[]}'
                return '{"sequence_flows":[],"common_workflows":[]}'

            agent.generate = fake_generate  # type: ignore[method-assign]
            cache = {
                "file_count": 1,
                "directory_counts": {"project root": 1},
                "important_files": [],
            }

            agent.generate_workflows("Sample", cache, root)
            agent.generate_knowledge("Sample", cache, root)

        combined = "\n".join(captured_prompts)
        self.assertNotIn("Blueprint Context Cache", combined)
        self.assertNotIn("Agent-based Architecture", combined)
        self.assertNotIn(".devhub/", combined)
        self.assertNotIn("workspace file editing", combined.lower())


class MermaidNormalizationTests(TestCase):
    def test_sequence_diagram_merges_multiline_message_payloads(self):
        chart = "\n".join(
            [
                "sequenceDiagram",
                "participant CodeWorkspace",
                "participant ProcessConsumer",
                "CodeWorkspace->>ProcessConsumer: WS send {input: 'npm run dev",
                "'}",
            ]
        )

        normalized = _normalize_mermaid_chart(chart, "sequence")

        self.assertEqual(
            normalized,
            "\n".join(
                [
                    "sequenceDiagram",
                    "participant CodeWorkspace",
                    "participant ProcessConsumer",
                    "CodeWorkspace->>ProcessConsumer: WS send input npm run dev newline",
                ]
            ),
        )

    def test_sequence_diagram_sanitizes_risky_message_label_characters(self):
        chart = "\n".join(
            [
                "sequenceDiagram",
                "participant CodeWorkspace",
                "participant API",
                "CodeWorkspace->>API: POST /api/workspace/<id>/spawn/ {command: 'cmd.exe'}",
            ]
        )

        normalized = _normalize_mermaid_chart(chart, "sequence")

        self.assertIn("POST api workspace id spawn command cmd exe", normalized)

    def test_graph_diagram_quotes_labels_with_punctuation(self):
        chart = "\n".join(
            [
                "graph TD",
                "  Client[React Frontend] -->|REST API| API[Django Backend API]",
                "  Client -->|WebSocket| WS[Process/Terminal WebSocket]",
                "  ORM --> DB[(Database)]",
                "  WS --> PTY[Pseudo-Terminal / Process Manager]",
                "  API --> AI[AI Agent / LLM Integration]",
            ]
        )

        normalized = _normalize_mermaid_chart(chart, "graph")

        self.assertIn('Client["React Frontend"]', normalized)
        self.assertIn('API["Django Backend API"]', normalized)
        self.assertIn('WS["Process/Terminal WebSocket"]', normalized)
        self.assertIn('DB[("Database")]', normalized)
        self.assertIn('PTY["Pseudo-Terminal / Process Manager"]', normalized)
        self.assertIn('AI["AI Agent / LLM Integration"]', normalized)

    def test_graph_diagram_preserves_existing_quoted_labels(self):
        chart = "\n".join(
            [
                "graph TD",
                '  API["Backend API / Django"] --> DB[("Database")]',
            ]
        )

        normalized = _normalize_mermaid_chart(chart, "graph")

        self.assertEqual(normalized, chart)


class WorkflowEvidenceTests(TestCase):
    def test_evidence_backed_workflows_skip_non_devhub_repositories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "frontend/src").mkdir(parents=True, exist_ok=True)
            (root / "backend/api").mkdir(parents=True, exist_ok=True)

            (root / "frontend/src/App.tsx").write_text(
                "\n".join(
                    [
                        "const loadOrders = async () => fetch('/api/orders');",
                        "const saveOrder = async () => fetch('/api/orders', { method: 'POST' });",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "backend/api/views.py").write_text(
                "\n".join(
                    [
                        "def list_orders(request): pass",
                        "def create_order(request): pass",
                    ]
                ),
                encoding="utf-8",
            )

            sequence_flows, common_workflows = _build_evidence_backed_workflows(root)

        self.assertEqual(sequence_flows, [])
        self.assertEqual(common_workflows, [])

    def test_evidence_backed_workflows_prefer_verified_devhub_flows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "frontend/src/components").mkdir(parents=True, exist_ok=True)
            (root / "frontend/src/pages").mkdir(parents=True, exist_ok=True)
            (root / "backend/api").mkdir(parents=True, exist_ok=True)
            (root / "backend/editor").mkdir(parents=True, exist_ok=True)
            (root / "backend/sandbox").mkdir(parents=True, exist_ok=True)
            (root / "backend/agents").mkdir(parents=True, exist_ok=True)

            (root / "frontend/src/components/CodeWorkspace.tsx").write_text(
                "\n".join(
                    [
                        "const fetchRuntime = () => fetch(`${API}/workspace/${workspaceId}/runtime/`);",
                        "const loadFile = async () => fetch(`${API}/workspace/${workspaceId}/fs/?path=${encodeURIComponent(path)}`);",
                        "const saveFile = async () => fetch(`${API}/workspace/${workspaceId}/fs/`, { method: 'POST' });",
                        "fetch(`${API}/workspace/${workspaceId}/spawn/`, { method: 'POST', body: JSON.stringify({ command: 'cmd.exe' }) });",
                        "const socket = new WebSocket(`ws://localhost:8000/ws/workspace/${workspaceId}/process/${pid}/`);",
                        "socketsRef.current[termPid].send(JSON.stringify({ input: data }));",
                        "const runProject = async () => fetch(`${API}/workspace/${workspaceId}/runtime/`, { method: 'POST' });",
                        "const stopProject = async () => fetch(`${API}/workspace/${workspaceId}/runtime/`, { method: 'DELETE' });",
                        "connectSocket(runtime.process_id, (data) => setRuntimeOutput((current) => current + data.output));",
                        "const runSetup = async () => fetch(`${API}/workspace/${workspaceId}/setup/`, { method: 'POST' });",
                        "setSetupRunning(true);",
                        "connectSocket(`${workspaceId}_setup`, (data) => setSetupOutput((current) => current + data.output));",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "frontend/src/components/ProjectChatPanel.tsx").write_text(
                "\n".join(
                    [
                        "const sendChat = async () => {",
                        "  const response = await fetch(`${API}/projects/${projectId}/chat/`, { method: 'POST' });",
                        "  if (data.applied_changes?.applied_files?.length && onCodeApplied) onCodeApplied(data.applied_changes.applied_files);",
                        "};",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "frontend/src/components/DocumentationPanel.tsx").write_text(
                "\n".join(
                    [
                        "export default function DocumentationPanel({ onGenerate }) {",
                        "  return <button onClick={onGenerate}>Generate Codebase Reference</button>;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "frontend/src/pages/ProjectView.tsx").write_text(
                "\n".join(
                    [
                        "const createFeature = async () => fetch(`${API}/projects/${id}/features/`, { method: 'POST' });",
                        "const pipelineAction = async () => fetch(`${API}/projects/${id}/pipeline/action/`, { method: 'POST' });",
                        "const generateDocumentation = async () => fetch(`${API}/projects/${id}/documentation/`, { method: 'POST' });",
                        "fetch(`${API}/projects/${id}/features/`, { method: 'POST' });",
                        "fetch(`${API}/projects/${id}/pipeline/action/`, { method: 'POST' });",
                        "setImplementationRun({ featureId, baselineCount: 0, startedSeen: false });",
                        "implementationPollRef.current = window.setInterval(() => { fetchProject(); }, 2500);",
                        "window.setInterval(() => { fetchProject(); }, 2500);",
                        "const startAgent = async () => {};",
                        "fetch(`${API}/projects/${id}/agent/deep-docs/`, { method: 'POST' });",
                        "fetch(`${API}/projects/${id}/agent/deep-docs/progress/`);",
                        "applyDeepDocsProgressEvent(event);",
                        "const reader = response.body?.getReader();",
                        "buffer.split('\\n');",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "frontend/src/pages/Dashboard.tsx").write_text(
                "\n".join(
                    [
                        "const handleCreate = async () => fetch(`${API}/projects/create/`, { method: 'POST' });",
                        "fetch(`${API}/projects/suggest/`, { method: 'POST' });",
                        "fetch(`${API}/projects/import/github/inspect/`, { method: 'POST' });",
                        "fetch(`${API}/projects/import/folder/inspect/`, { method: 'POST' });",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "backend/api/views.py").write_text(
                "\n".join(
                    [
                        "def workspace_fs(request, workspace_id):",
                        "    workspace_manager.write_file(workspace_id, rel_path, content)",
                        "def workspace_spawn(request, workspace_id): pass",
                        "def workspace_runtime(request, workspace_id):",
                        "    runtime_process_id(workspace_id)",
                        "    detect_runtime(workspace_path)",
                        "    _runtime_response_payload(runtime, process_id, sandbox)",
                        "    sandbox.run_command(process_id, command, str(workspace_path))",
                        "def workspace_setup(request, workspace_id):",
                        "    setup_process_id(workspace_id)",
                        "    sandbox.run_command(process_id, command, str(workspace_path))",
                        "def create_project(request):",
                        "    scaffold_project(project, project_root)",
                        "    workspace_manager.create_workspace('x', managed=True)",
                        "    _schedule_project_context_generation(project)",
                        "def suggest_project_details(request): pass",
                        "def inspect_github_import(request): pass",
                        "def inspect_folder_import(request): pass",
                        "def project_features(request, project_id): pass",
                        "def pipeline_action(request, project_id): pass",
                        "def implement_feature_sync(feature, project): pass",
                        "    thread = threading.Thread(target=implement_feature_sync, args=(feature, project))",
                        "    FeatureHistory.objects.create(feature=feature, stage='development', action='implementation_started', by='AI Coder')",
                        "def deep_documentation_stream(request, project_id):",
                        "    StreamingHttpResponse(event_stream(), content_type='text/event-stream')",
                        "    _safe_write_deep_docs_progress(workspace_path, event)",
                        "def deep_documentation_progress(request, project_id): pass",
                        "def project_documentation(request, project_id):",
                        "    run = generate_codebase_reference_sync(project)",
                        "    _documentation_run_payload(run)",
                        "def project_chat(request, project_id):",
                        "    build_memory_context(project, content)",
                        "    _resolve_chat_context(project, content)",
                        "    apply_chat_changes(project, content)",
                        "    ChatMessage.objects.create(project=project, role='user', content=content)",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "backend/api/urls.py").write_text(
                "\n".join(
                    [
                        "path('projects/create/', views.create_project)",
                        "path('projects/<str:project_id>/documentation/', views.project_documentation)",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "backend/editor/routing.py").write_text("re_path(r'ws/workspace/(?P<workspace_id>[\\w\\-]+)/process/(?P<process_id>[\\w\\-.]+)/$', consumers.ProcessConsumer.as_asgi())", encoding="utf-8")
            (root / "backend/editor/consumers.py").write_text(
                "\n".join(
                    [
                        "class ProcessConsumer:",
                        "    async def poll_process_output(self): pass",
                        "    sandbox.get_status(self.process_id)",
                        "    sandbox.get_output(self.process_id)",
                        "    sandbox.send_input(self.process_id, input_data)",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "backend/sandbox/executor.py").write_text(
                "\n".join(
                    [
                        "def run_command(): pass",
                        "def send_input(): pass",
                        "def get_output(): pass",
                        "def get_status(): pass",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "backend/agents/deep_documentation.py").write_text(
                "\n".join(
                    [
                        "class DeepDocumentationAgent:",
                        "    def generate_all_sections(self): pass",
                        "    def generate_section(self): pass",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "backend/agents/workspace.py").write_text("class WorkspaceManager: pass", encoding="utf-8")

            sequence_flows, common_workflows = _build_evidence_backed_workflows(root)

        sequence_titles = {item["title"] for item in sequence_flows}
        workflow_titles = {item["title"] for item in common_workflows}

        self.assertIn("Terminal Process Execution and I/O Streaming", sequence_titles)
        self.assertIn("Workspace File Read and Save", sequence_titles)
        self.assertIn("Project Runtime Execution and Preview Streaming", sequence_titles)
        self.assertIn("Workspace Setup Command Execution", sequence_titles)
        self.assertIn("Feature Implementation and Progress Tracking", sequence_titles)
        self.assertIn("AI Deep Documentation Generation", sequence_titles)
        self.assertIn("Codebase Reference Documentation Generation", sequence_titles)
        self.assertIn("Project Creation and Scaffolding", sequence_titles)
        self.assertIn("Workspace Chat Requests and Direct Code Application", sequence_titles)
        self.assertNotIn("Real-time Collaborative File Editing", sequence_titles)
        self.assertIn("Editing a File in the Workspace", workflow_titles)
        self.assertIn("Running the Project Preview", workflow_titles)
        self.assertIn("Running Workspace Setup", workflow_titles)
        self.assertIn("Regenerating Blueprint Documentation", workflow_titles)
        self.assertIn("Generating the Codebase Reference", workflow_titles)
        self.assertIn("Creating, Importing, or Connecting a Project", workflow_titles)
        self.assertIn("Using Workspace Chat to Explain or Change Code", workflow_titles)

        file_flow = next(item for item in sequence_flows if item["title"] == "Workspace File Read and Save")
        self.assertIn("API->>API: resolve workspace path and read file or directory", file_flow["mermaid_sequence"])
        self.assertNotIn("API->>WorkspaceManager: read file from workspace", file_flow["mermaid_sequence"])

        chat_flow = next(item for item in sequence_flows if item["title"] == "Workspace Chat Requests and Direct Code Application")
        self.assertIn("alt Edit style request and workspace available", chat_flow["mermaid_sequence"])
        self.assertIn("else Explain or planning request", chat_flow["mermaid_sequence"])


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ProjectCreationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def tearDown(self):
        for project in Project.objects.all():
            if project.workspace_id:
                try:
                    workspace_manager.delete_workspace(project.workspace_id)
                except Exception:
                    pass

    def test_create_project_builds_react_scaffold(self):
        response = self.client.post(
            "/api/projects/create/",
            data=json.dumps(
                {
                    "name": "Starter UI",
                    "description": "A generated React app",
                    "tech_stack": ["React"],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        project = Project.objects.get(id=payload["id"])
        project_root = Path(project.local_path)

        self.assertTrue((project_root / "package.json").exists())
        self.assertTrue((project_root / "src" / "App.jsx").exists())
        self.assertEqual(payload["runtime"]["runtime_type"], "node")
        self.assertEqual(payload["runtime"]["run_command"], "npm run dev")

    def test_create_project_infers_react_scaffold_from_description(self):
        response = self.client.post(
            "/api/projects/create/",
            data=json.dumps(
                {
                    "name": "Calculator UI",
                    "description": "Build a react based calculator app with a modern interface",
                    "tech_stack": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        project = Project.objects.get(id=payload["id"])
        project_root = Path(project.local_path)

        self.assertTrue((project_root / "package.json").exists())
        self.assertEqual(payload["runtime"]["runtime_type"], "node")

    def test_create_project_uses_idea_to_build_working_planner_starter(self):
        response = self.client.post(
            "/api/projects/create/",
            data=json.dumps(
                {
                    "name": "Sprint Planner",
                    "idea": "A kanban style task manager for a small product team",
                    "description": "",
                    "tech_stack": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        project = Project.objects.get(id=payload["id"])
        project_root = Path(project.local_path)
        app_source = (project_root / "src" / "App.jsx").read_text(encoding="utf-8")

        self.assertEqual(payload["runtime"]["runtime_type"], "node")
        self.assertIn("Add Work Item", app_source)
        self.assertIn("Backlog", app_source)

    def test_create_project_builds_expense_tracker_from_brief(self):
        response = self.client.post(
            "/api/projects/create/",
            data=json.dumps(
                {
                    "name": "Budget Pilot",
                    "idea": "An expense tracker for startup operating costs",
                    "description": "",
                    "tech_stack": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        project = Project.objects.get(id=payload["id"])
        project_root = Path(project.local_path)
        app_source = (project_root / "src" / "App.jsx").read_text(encoding="utf-8")

        self.assertEqual(payload["runtime"]["runtime_type"], "node")
        self.assertIn("Add Expense", app_source)
        self.assertIn("Total Spend", app_source)

    @patch("api.views._schedule_project_context_generation")
    def test_create_project_auto_starts_context_generation_for_connected_folder(self, mock_schedule):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text(json.dumps({"name": "imported-demo"}), encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "index.ts").write_text("console.log('hello');\n", encoding="utf-8")

            response = self.client.post(
                "/api/projects/create/",
                data=json.dumps(
                    {
                        "name": "Imported Folder",
                        "description": "Existing local codebase",
                        "local_path": str(root),
                        "tech_stack": ["TypeScript"],
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["context_initializing"])
        scheduled_project = mock_schedule.call_args.args[0]
        self.assertEqual(scheduled_project.name, "Imported Folder")
        self.assertTrue(mock_schedule.call_args.kwargs["include_documentation"])


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ProjectChatEditTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        (self.project_root / "index.html").write_text("<h1>Old heading</h1>", encoding="utf-8")
        workspace_id = workspace_manager.create_workspace(str(self.project_root), managed=False)
        self.project = Project.objects.create(
            name="Chat Editable App",
            description="A project used for chat edit tests",
            local_path=str(self.project_root),
            workspace_id=workspace_id,
            tech_stack=["html", "css", "javascript"],
        )

    def tearDown(self):
        if self.project.workspace_id:
            try:
                workspace_manager.delete_workspace(self.project.workspace_id)
            except Exception:
                pass
        self.temp_dir.cleanup()

    def test_chat_edit_request_writes_files_and_tracks_changes(self):
        def fake_implement_feature(self, workspace_id, feature_title, feature_desc, spec, files_context, **kwargs):
            workspace_manager.write_file(
                workspace_id,
                "index.html",
                "<h1>Updated heading</h1><p>Applied from chat.</p>",
            )
            return {"status": "success", "files_modified": ["index.html"]}

        with patch("agents.coder.CoderAgent.implement_feature", new=fake_implement_feature):
            response = self.client.post(
                f"/api/projects/{self.project.id}/chat/",
                data=json.dumps({"content": "Update the heading and landing page copy"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["applied_changes"]["applied_files"], ["index.html"])
        self.assertIn("Applied the requested update", payload["assistant_message"])
        self.assertIn("Updated heading", (self.project_root / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(Changeset.objects.filter(project=self.project).count(), 1)
        self.assertEqual(FileDiff.objects.filter(changeset__project=self.project).count(), 1)

    def test_chat_edit_failure_returns_assistant_message_instead_of_500(self):
        def fake_implement_feature(self, workspace_id, feature_title, feature_desc, spec, files_context, **kwargs):
            raise RuntimeError("simulated coder failure")

        with patch("agents.coder.CoderAgent.implement_feature", new=fake_implement_feature):
            response = self.client.post(
                f"/api/projects/{self.project.id}/chat/",
                data=json.dumps({"content": "Update the UI colors"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("edit failed", payload["assistant_message"])


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class PipelineActionTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")
        self.project = Project.objects.create(
            name="Pipeline Test Project",
            description="Pipeline state feedback",
            tech_stack=["html"],
        )
        self.feature = Feature.objects.create(
            project=self.project,
            title="Demo feature",
            description="Used for pipeline action tests",
        )

    def test_approve_returns_feedback_message(self):
        response = self.client.post(
            f"/api/projects/{self.project.id}/pipeline/action/",
            data=json.dumps({"feature_id": str(self.feature.id), "action": "approve"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("Approval recorded", payload["message"])
        self.assertEqual(FeatureApproval.objects.filter(feature=self.feature).count(), 1)

    def test_implement_moves_feature_to_development_immediately(self):
        response = self.client.post(
            f"/api/projects/{self.project.id}/pipeline/action/",
            data=json.dumps({"feature_id": str(self.feature.id), "action": "implement"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.feature.refresh_from_db()
        self.assertEqual(self.feature.status, "development")
        self.assertIn("implementation started", payload["message"].lower())


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ProjectMetadataTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.project = Project.objects.create(
            name="Metadata Project",
            description="Initial description",
            tech_stack=["React"],
        )

    def test_project_suggestion_returns_editable_fields(self):
        response = self.client.post(
            "/api/projects/suggest/",
            data=json.dumps({"idea": "an AI code workspace for imported repos", "source_type": "starter", "tech_stack": ["React"]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["name"])
        self.assertTrue(payload["description"])
        self.assertTrue(isinstance(payload["tech_stack"], list))

    def test_project_update_changes_metadata(self):
        response = self.client.post(
            f"/api/projects/{self.project.id}/update/",
            data=json.dumps(
                {
                    "name": "Metadata Project Updated",
                    "description": "Updated description",
                    "github_url": "https://github.com/example/repo.git",
                    "tech_stack": ["React", "Django"],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Metadata Project Updated")
        self.assertEqual(self.project.description, "Updated description")
        self.assertEqual(self.project.github_url, "https://github.com/example/repo.git")
        self.assertEqual(self.project.tech_stack, ["React", "Django"])


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class DeepDocumentationStreamTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        (self.project_root / "README.md").write_text("# Demo\n", encoding="utf-8")
        workspace_id = workspace_manager.create_workspace(str(self.project_root), managed=False)
        self.project = Project.objects.create(
            name="Deep Docs Project",
            description="Used for stream progress tests",
            local_path=str(self.project_root),
            workspace_id=workspace_id,
            tech_stack=["React"],
        )

    def tearDown(self):
        if self.project.workspace_id:
            try:
                workspace_manager.delete_workspace(self.project.workspace_id)
            except Exception:
                pass
        self.temp_dir.cleanup()

    def test_deep_docs_stream_emits_context_event_before_sections(self):
        def fake_generate_all_sections(self, project_name, cache, workspace_path, existing_blueprint=None):
            yield {
                "section_key": "services",
                "section_data": {},
                "progress_pct": 0,
                "status": "started",
                "total_sections": 7,
                "completed_sections": 0,
            }
            yield {
                "section_key": "services",
                "section_data": {"services": [{"name": "API"}]},
                "progress_pct": 14,
                "status": "completed",
                "total_sections": 7,
                "completed_sections": 1,
            }

        with patch("api.views.build_blueprint_context", return_value={"important_files": [], "directory_counts": {}, "file_count": 1}), patch(
            "agents.deep_documentation.DeepDocumentationAgent.generate_all_sections",
            new=fake_generate_all_sections,
        ):
            response = self.client.post(
                f"/api/projects/{self.project.id}/agent/deep-docs/",
                data=json.dumps({}),
                content_type="application/json",
            )
            chunks = list(response.streaming_content)

        self.assertEqual(response.status_code, 200)
        body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in chunks)

        self.assertIn('"section_key": "build_context"', body)
        self.assertIn('"section_label": "Preparing codebase context"', body)
        self.assertIn('"section_key": "services"', body)
        self.assertLess(body.index('"section_key": "build_context"'), body.index('"section_key": "services"'))

        progress_response = self.client.get(
            f"/api/projects/{self.project.id}/agent/deep-docs/progress/",
        )
        self.assertEqual(progress_response.status_code, 200)
        progress_payload = progress_response.json()
        self.assertEqual(progress_payload["status"], "done")
        self.assertEqual(progress_payload["section_key"], "complete")

    def test_deep_docs_stream_continues_when_progress_write_fails(self):
        def fake_generate_all_sections(self, project_name, cache, workspace_path, existing_blueprint=None):
            yield {
                "section_key": "services",
                "section_data": {},
                "progress_pct": 0,
                "status": "started",
                "total_sections": 7,
                "completed_sections": 0,
            }
            yield {
                "section_key": "services",
                "section_data": {"services": [{"name": "API"}]},
                "progress_pct": 14,
                "status": "completed",
                "total_sections": 7,
                "completed_sections": 1,
            }

        with patch("api.views.build_blueprint_context", return_value={"important_files": [], "directory_counts": {}, "file_count": 1}), patch(
            "agents.deep_documentation.DeepDocumentationAgent.generate_all_sections",
            new=fake_generate_all_sections,
        ), patch(
            "api.views._write_deep_docs_progress",
            side_effect=PermissionError("locked"),
        ), patch(
            "api.views.logger.exception",
        ):
            response = self.client.post(
                f"/api/projects/{self.project.id}/agent/deep-docs/",
                data=json.dumps({}),
                content_type="application/json",
            )
            chunks = list(response.streaming_content)

        self.assertEqual(response.status_code, 200)
        body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in chunks)

        self.assertIn('"section_key": "build_context"', body)
        self.assertIn('"section_key": "services"', body)
        self.assertIn('"status": "done"', body)

        progress_response = self.client.get(
            f"/api/projects/{self.project.id}/agent/deep-docs/progress/",
        )
        self.assertEqual(progress_response.status_code, 200)
        self.assertEqual(progress_response.json()["status"], "idle")

    def test_deep_docs_stream_can_regenerate_single_llm_section(self):
        test_case = self

        def fake_generate_section(self, section_key, project_name, cache, workspace_path, existing_blueprint=None):
            test_case.assertEqual(section_key, "services")
            return {"services": [{"name": "API Service"}]}

        def passthrough_enrich(project, blueprint, codebase_context, feature_summary):
            return dict(blueprint)

        with patch("api.views.build_blueprint_context", return_value={"important_files": [], "directory_counts": {}, "file_count": 1}), patch(
            "agents.deep_documentation.DeepDocumentationAgent.generate_section",
            new=fake_generate_section,
        ), patch(
            "api.views._enrich_blueprint_document",
            new=passthrough_enrich,
        ):
            response = self.client.post(
                f"/api/projects/{self.project.id}/agent/deep-docs/",
                data=json.dumps({"section_key": "services"}),
                content_type="application/json",
            )
            body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in response.streaming_content)

        self.assertEqual(response.status_code, 200)
        self.assertIn('"section_key": "services"', body)
        self.assertIn('"total_sections": 1', body)
        self.assertIn('"section_label": "Services & Components"', body)

        self.project.refresh_from_db()
        self.assertEqual(self.project.blueprint.get("services"), [{"name": "API Service"}])

    def test_deep_docs_stream_returns_enriched_section_payload_for_single_workflows_section(self):
        test_case = self

        def fake_generate_section(self, section_key, project_name, cache, workspace_path, existing_blueprint=None):
            test_case.assertEqual(section_key, "workflows")
            return {
                "sequence_flows": [
                    {
                        "title": "Real-time Collaborative File Editing",
                        "mermaid_sequence": "sequenceDiagram\n  participant EditorA\n  participant EditorConsumer",
                    }
                ],
                "common_workflows": [{"title": "Speculative Workflow", "steps": ["Step 1: guess"]}],
            }

        def fake_enrich(project, blueprint, codebase_context, feature_summary):
            updated = dict(blueprint)
            updated["sequence_flows"] = [
                {
                    "title": "Workspace File Read and Save",
                    "description": "Verified flow",
                    "mermaid_sequence": "sequenceDiagram\n  participant CodeWorkspace\n  participant API",
                    "touchpoints": ["frontend/src/components/CodeWorkspace.tsx"],
                }
            ]
            updated["common_workflows"] = [
                {
                    "title": "Editing a File in the Workspace",
                    "steps": ["Step 1: Verified step"],
                }
            ]
            return updated

        with patch("api.views.build_blueprint_context", return_value={"important_files": [], "directory_counts": {}, "file_count": 1}), patch(
            "agents.deep_documentation.DeepDocumentationAgent.generate_section",
            new=fake_generate_section,
        ), patch(
            "api.views._enrich_blueprint_document",
            new=fake_enrich,
        ):
            response = self.client.post(
                f"/api/projects/{self.project.id}/agent/deep-docs/",
                data=json.dumps({"section_key": "workflows"}),
                content_type="application/json",
            )
            body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in response.streaming_content)

        self.assertEqual(response.status_code, 200)
        self.assertIn('"Workspace File Read and Save"', body)
        self.assertIn('"Editing a File in the Workspace"', body)
        self.assertNotIn('"Real-time Collaborative File Editing"', body)
        self.assertNotIn('"Speculative Workflow"', body)

        self.project.refresh_from_db()
        self.assertEqual(self.project.blueprint.get("sequence_flows")[0]["title"], "Workspace File Read and Save")

    def test_deep_docs_stream_returns_enriched_section_payloads_during_full_regeneration(self):
        def fake_generate_all_sections(self, project_name, cache, workspace_path, existing_blueprint=None):
            yield {
                "section_key": "workflows",
                "section_data": {},
                "progress_pct": 0,
                "status": "started",
                "total_sections": 7,
                "completed_sections": 0,
            }
            yield {
                "section_key": "workflows",
                "section_data": {
                    "sequence_flows": [
                        {
                            "title": "Real-time Collaborative File Editing",
                            "mermaid_sequence": "sequenceDiagram\n  participant EditorA\n  participant EditorConsumer",
                        }
                    ],
                    "common_workflows": [{"title": "Speculative Workflow", "steps": ["Step 1: guess"]}],
                },
                "progress_pct": 72,
                "status": "completed",
                "total_sections": 7,
                "completed_sections": 5,
            }

        def fake_enrich(project, blueprint, codebase_context, feature_summary):
            updated = dict(blueprint)
            updated["sequence_flows"] = [
                {
                    "title": "Terminal Process Execution and I/O Streaming",
                    "description": "Verified flow",
                    "mermaid_sequence": "sequenceDiagram\n  participant CodeWorkspace\n  participant API",
                    "touchpoints": ["frontend/src/components/CodeWorkspace.tsx"],
                }
            ]
            updated["common_workflows"] = [
                {
                    "title": "Interacting with the Workspace Terminal",
                    "steps": ["Step 1: Verified step"],
                }
            ]
            return updated

        with patch("api.views.build_blueprint_context", return_value={"important_files": [], "directory_counts": {}, "file_count": 1}), patch(
            "agents.deep_documentation.DeepDocumentationAgent.generate_all_sections",
            new=fake_generate_all_sections,
        ), patch(
            "api.views._enrich_blueprint_document",
            new=fake_enrich,
        ):
            response = self.client.post(
                f"/api/projects/{self.project.id}/agent/deep-docs/",
                data=json.dumps({}),
                content_type="application/json",
            )
            body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in response.streaming_content)

        self.assertEqual(response.status_code, 200)
        self.assertIn('"Terminal Process Execution and I/O Streaming"', body)
        self.assertIn('"Interacting with the Workspace Terminal"', body)
        self.assertNotIn('"Real-time Collaborative File Editing"', body)
        self.assertNotIn('"Speculative Workflow"', body)

        self.project.refresh_from_db()
        self.assertEqual(self.project.blueprint.get("sequence_flows")[0]["title"], "Terminal Process Execution and I/O Streaming")

    def test_deep_docs_stream_can_regenerate_single_token_free_section(self):
        def fake_enrich(project, blueprint, codebase_context, feature_summary):
            updated = dict(blueprint)
            updated["repo_tree"] = "demo/\n  backend/"
            updated["repo_tree_nodes"] = [{"name": "demo", "path": "", "type": "directory", "children": []}]
            updated["repository_map"] = [{"area": "backend/", "description": "Backend area"}]
            updated["directory_guide"] = [{"path": "backend/", "purpose": "Backend area"}]
            updated["readme_excerpt"] = "README excerpt"
            updated["instruction_files"] = []
            updated["file_structure_visualizer"] = []
            updated["change_guide"] = []
            updated["design_document_markdown"] = "Design doc"
            updated["design_document_sections"] = [{"id": "intro", "title": "Intro", "markdown": "Hello"}]
            return updated

        with patch("api.views.build_blueprint_context", return_value={"important_files": [], "directory_counts": {}, "file_count": 1}), patch(
            "api.views._enrich_blueprint_document",
            new=fake_enrich,
        ):
            response = self.client.post(
                f"/api/projects/{self.project.id}/agent/deep-docs/",
                data=json.dumps({"section_key": "repository"}),
                content_type="application/json",
            )
            body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in response.streaming_content)

        self.assertEqual(response.status_code, 200)
        self.assertIn('"section_key": "repository"', body)
        self.assertIn('"section_label": "Repository"', body)
        self.assertIn('"total_sections": 1', body)

        self.project.refresh_from_db()
        self.assertEqual(self.project.blueprint.get("repo_tree"), "demo/\n  backend/")
        self.assertEqual(self.project.blueprint.get("repository_map"), [{"area": "backend/", "description": "Backend area"}])


class DeepDocumentationProgressWriteTests(TestCase):
    def test_write_deep_docs_progress_falls_back_when_replace_is_locked(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "api.views.os.replace",
            side_effect=PermissionError("locked"),
        ) as replace_mock, patch(
            "api.views.time.sleep",
            return_value=None,
        ):
            workspace_path = Path(temp_dir)
            _write_deep_docs_progress(
                workspace_path,
                {
                    "status": "started",
                    "section_key": "build_context",
                    "section_label": "Preparing codebase context",
                    "progress_pct": 0,
                    "section_data": {},
                },
            )

            progress_path = workspace_path / ".devhub" / "deep-docs-progress.json"
            self.assertTrue(progress_path.exists())
            payload = json.loads(progress_path.read_text(encoding="utf-8"))

        self.assertEqual(replace_mock.call_count, 5)
        self.assertEqual(payload["status"], "started")
        self.assertEqual(payload["section_key"], "build_context")
        self.assertIn("updated_at", payload)


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ProjectImportInspectionTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_folder_inspection_returns_detected_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "name": "imported-ui",
                        "scripts": {"dev": "vite --host 127.0.0.1 --port 4173"},
                        "dependencies": {"react": "^18.0.0"},
                        "devDependencies": {"vite": "^5.0.0"},
                    }
                ),
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "App.jsx").write_text("export default function App(){ return <div>Hello</div>; }", encoding="utf-8")

            response = self.client.post(
                "/api/projects/import/folder/inspect/",
                data=json.dumps({"local_path": str(root), "idea": "Import this React app"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resolved_path"], str(root))
        self.assertIn("React", payload["detected_stack"])
        self.assertEqual(payload["runtime"]["runtime_type"], "node")

    @patch("api.views._pick_local_folder", return_value="C:\\Users\\USER\\Desktop\\Agentic\\example-project")
    def test_folder_picker_returns_selected_path(self, _mock_picker):
        response = self.client.post("/api/projects/import/folder/pick/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["local_path"], "C:\\Users\\USER\\Desktop\\Agentic\\example-project")

    @patch("api.views._build_import_inspection")
    @patch("api.views.subprocess.run")
    def test_github_inspection_clones_and_returns_metadata(self, mock_run, mock_build_inspection):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        mock_build_inspection.return_value = {
            "name": "Imported Repo",
            "description": "Imported repo description",
            "tech_stack": ["React"],
            "detected_stack": ["React"],
            "resolved_path": "C:\\temp\\repo",
            "root_name": "repo",
            "runtime": {"runtime_type": "node"},
            "structure_preview": "repo/",
            "source_summary": "repo/",
        }

        response = self.client.post(
            "/api/projects/import/github/inspect/",
            data=json.dumps({"github_url": "https://github.com/example/repo.git", "idea": "Map the repo"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["github_url"], "https://github.com/example/repo.git")
        self.assertEqual(payload["name"], "Imported Repo")
        self.assertTrue(mock_run.called)
        self.assertTrue(mock_build_inspection.called)


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ProjectBlueprintGuidanceBackfillTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        (self.project_root / "src").mkdir()
        (self.project_root / "extensions").mkdir()
        (self.project_root / "ui").mkdir()
        (self.project_root / "docs").mkdir()
        (self.project_root / "src" / "index.ts").write_text("export const gateway = true;\n", encoding="utf-8")
        (self.project_root / "extensions" / "discord.ts").write_text("export const extension = 'discord';\n", encoding="utf-8")
        (self.project_root / "ui" / "app.ts").write_text("export const ui = true;\n", encoding="utf-8")
        (self.project_root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
        (self.project_root / "pnpm-workspace.yaml").write_text("packages:\n  - .\n", encoding="utf-8")
        (self.project_root / "package.json").write_text(
            json.dumps(
                {
                    "name": "openclaw",
                    "packageManager": "pnpm@10.32.1",
                    "engines": {"node": ">=22.16.0"},
                    "scripts": {
                        "ui:build": "node scripts/ui.js build",
                        "build": "node scripts/build.mjs",
                        "gateway:watch": "node scripts/watch-node.mjs gateway --force",
                        "check": "pnpm lint && pnpm test:fast",
                        "test": "vitest run",
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.project_root / "README.md").write_text(
            "\n".join(
                [
                    "# OpenClaw",
                    "Preferred setup: run `openclaw onboard` in your terminal.",
                    "Works on Windows (via WSL2; strongly recommended).",
                    "```bash",
                    "pnpm install",
                    "pnpm ui:build # auto-installs UI deps on first run",
                    "pnpm build",
                    "pnpm openclaw onboard --install-daemon",
                    "pnpm gateway:watch",
                    "```",
                    "Note: `pnpm openclaw ...` runs TypeScript directly (via `tsx`). `pnpm build` produces `dist/`.",
                    "Treat inbound DMs as untrusted input and review pairing defaults before exposing the gateway.",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "CONTRIBUTING.md").write_text(
            "Run tests: `pnpm build && pnpm check && pnpm test`\nDo not submit refactor-only PRs.\n",
            encoding="utf-8",
        )
        (self.project_root / ".env.example").write_text(
            "\n".join(
                [
                    "# Quick start",
                    "# Copy this file to `.env` or `~/.openclaw/.env`.",
                    "# Env-source precedence for environment variables (highest -> lowest):",
                    "OPENCLAW_GATEWAY_TOKEN=change-me",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "SECURITY.md").write_text("# Security\nReview gateway auth before exposing it.\n", encoding="utf-8")
        workspace_id = workspace_manager.create_workspace(str(self.project_root), managed=False)
        self.project = Project.objects.create(
            name="OpenClaw",
            description="Imported repo",
            github_url="https://github.com/openclaw/openclaw",
            local_path=str(self.project_root),
            workspace_id=workspace_id,
            tech_stack=["Node.js", "TypeScript"],
            blueprint={
                "setup_steps": [
                    {"step": "Install Dependencies", "command": "npm install", "explanation": "Installs all necessary packages for the project."},
                    {"step": "Run Onboarding", "command": "openclaw onboard", "explanation": "Guides through the setup process for the gateway and channels."},
                    {"step": "Set up development environment", "command": "", "explanation": "Necessary for running and testing the application."},
                ],
                "onboarding_checklist": [
                    {"task": "Read the repo map", "category": "codebase", "estimated_time": "10 min", "why_important": "It gives a fast overview of the project structure.", "instructions": "Open .devhub/repo-map.md in the workspace."},
                    {"task": "Inspect runtime entrypoints", "category": "environment", "estimated_time": "10 min", "why_important": "You need to know how the app starts before making changes.", "instructions": "Review the detected runtime config, README, and important files."},
                ],
                "gotchas": ["Areas without evidence should be treated as unknown until verified in code."],
            },
        )

    def tearDown(self):
        if self.project.workspace_id:
            try:
                workspace_manager.delete_workspace(self.project.workspace_id)
            except Exception:
                pass
        self.temp_dir.cleanup()

    def test_get_project_backfills_repo_specific_guidance_for_generic_blueprint(self):
        response = self.client.get(f"/api/projects/{self.project.id}/")

        self.assertEqual(response.status_code, 200)
        blueprint = response.json()["blueprint"]

        setup_commands = " | ".join(
            item.get("command", "")
            for item in blueprint.get("setup_steps", [])
            if isinstance(item, dict)
        )
        self.assertIn("pnpm install", setup_commands)
        self.assertIn("pnpm ui:build && pnpm build", setup_commands)
        self.assertIn("pnpm openclaw onboard --install-daemon", setup_commands)
        self.assertIn("pnpm build && pnpm check && pnpm test", setup_commands)

        onboarding_text = json.dumps(blueprint.get("onboarding_checklist", []))
        self.assertIn("README.md", onboarding_text)
        self.assertIn("CONTRIBUTING.md", onboarding_text)
        self.assertIn("src/", onboarding_text)
        self.assertIn("extensions/", onboarding_text)

        gotchas_text = " ".join(str(item) for item in blueprint.get("gotchas", []))
        self.assertIn("WSL2", gotchas_text)
        self.assertIn("pnpm", gotchas_text)
        self.assertIn(".env", gotchas_text)


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ProjectCodebaseDocTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        (self.project_root / "src").mkdir()
        (self.project_root / "docs").mkdir()
        (self.project_root / "backend").mkdir()
        (self.project_root / ".devhub").mkdir()
        (self.project_root / "README.md").write_text("# Demo Repo\nThis project has a React UI.\n", encoding="utf-8")
        (self.project_root / "DEVHUB.md").write_text("# Project Instructions\nUse existing architecture.\n", encoding="utf-8")
        (self.project_root / ".devhub" / "DEVHUB.md").write_text("# DevHub Instructions\nTemplate placeholder.\n", encoding="utf-8")
        (self.project_root / ".env.example").write_text("API_KEY=\nPORT=3000\n", encoding="utf-8")
        (self.project_root / "docs" / "setup.md").write_text(
            "\n".join(
                [
                    "# Setup",
                    "",
                    "npm install",
                    "npm run dev",
                    "python -m venv .venv",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "package.json").write_text(
            json.dumps(
                {
                    "name": "demo-repo",
                    "scripts": {
                        "dev": "vite",
                        "test": "vitest",
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.project_root / "src" / "App.tsx").write_text(
            "\n".join(
                [
                    "import { useState } from 'react';",
                    "import { AppConfig } from './types';",
                    "",
                    "export default function App() {",
                    "  const [count, setCount] = useState(0);",
                    "  const config: AppConfig = { name: 'demo' };",
                    "  return <button onClick={() => setCount(count + 1)}>Count {count}</button>;",
                    "}",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "src" / "types.ts").write_text(
            "export interface AppConfig { name: string }\n",
            encoding="utf-8",
        )
        (self.project_root / "src" / "server.ts").write_text(
            "app.get('/health', () => ({ ok: true }))\n",
            encoding="utf-8",
        )
        (self.project_root / "backend" / "noisy.py").write_text(
            "\n".join(
                [
                    'gotchas_text = ", ".join(str(item) for item in blueprint.get("gotchas", []))',
                    "python_paths = []",
                    "shutil.rmtree(path)",
                    "shell=True",
                    "Python virtual environment for the backend.",
                ]
            ),
            encoding="utf-8",
        )
        workspace_id = workspace_manager.create_workspace(str(self.project_root), managed=False)
        self.project = Project.objects.create(
            name="Doc Demo",
            description="Project for codebase doc tests",
            local_path=str(self.project_root),
            workspace_id=workspace_id,
            tech_stack=["React", "TypeScript"],
        )

    def tearDown(self):
        if self.project.workspace_id:
            try:
                workspace_manager.delete_workspace(self.project.workspace_id)
            except Exception:
                pass
        self.temp_dir.cleanup()

    def test_codebase_doc_returns_directory_and_file_level_docs(self):
        root_response = self.client.get(f"/api/projects/{self.project.id}/codebase/doc/")
        self.assertEqual(root_response.status_code, 200)
        root_doc = root_response.json()["doc"]
        self.assertEqual(root_doc["kind"], "directory")
        self.assertTrue(any(item["path"] == "README.md" for item in root_doc.get("docs", [])))
        self.assertIn("dependency_graph", root_doc)
        self.assertTrue(root_doc["dependency_graph"]["mermaid"].startswith("graph"))
        self.assertTrue(any(item["name"] == "AppConfig" for item in root_doc.get("all_models", [])))
        self.assertTrue(any(item["path"] == "/health" for item in root_doc.get("all_routes", [])))
        self.assertIn(".env.example", root_doc.get("prerequisites", {}).get("environment_files", []))

        file_response = self.client.get(f"/api/projects/{self.project.id}/codebase/doc/?path=src/App.tsx")
        self.assertEqual(file_response.status_code, 200)
        file_doc = file_response.json()["doc"]
        self.assertEqual(file_doc["kind"], "file")
        self.assertEqual(file_doc["path"], "src/App.tsx")
        self.assertIn("Top-Level Symbols", file_doc["markdown"])
        self.assertIn("Exports", file_doc["markdown"])
        self.assertTrue(any(item["path"] == "src/App.tsx" for item in file_doc["trace"]["files_accessed"]))

    def test_codebase_doc_prerequisites_filter_internal_templates_and_bogus_commands(self):
        root_response = self.client.get(f"/api/projects/{self.project.id}/codebase/doc/")
        self.assertEqual(root_response.status_code, 200)
        prerequisites = root_response.json()["doc"].get("prerequisites", {})

        instruction_paths = [item.get("path") for item in prerequisites.get("instruction_files", [])]
        self.assertIn("DEVHUB.md", instruction_paths)
        self.assertNotIn(".devhub/DEVHUB.md", instruction_paths)

        commands = prerequisites.get("commands", [])
        self.assertIn("npm run dev", commands)
        self.assertIn("npm run test", commands)
        self.assertIn("npm install", commands)
        self.assertIn("python -m venv .venv", commands)
        self.assertNotIn('gotchas_text = ", ".join(str(item) for item in blueprint.get("gotchas", []))', commands)
        self.assertNotIn("python_paths = []", commands)
        self.assertNotIn("shutil.rmtree(path)", commands)
        self.assertNotIn("shell=True", commands)
        self.assertNotIn("Python virtual environment for the backend.", commands)

        required_tools = prerequisites.get("required_tools", [])
        self.assertIn("npm", required_tools)
        self.assertIn("python", required_tools)
        self.assertNotIn("gotchas_text", required_tools)
        self.assertNotIn("python_paths", required_tools)


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ProjectInitializationStateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        (self.project_root / "README.md").write_text("# Imported\n", encoding="utf-8")
        workspace_id = workspace_manager.create_workspace(str(self.project_root), managed=False)
        self.project = Project.objects.create(
            name="Imported Ready",
            description="Imported project with blueprint ready",
            local_path=str(self.project_root),
            workspace_id=workspace_id,
            github_url="https://github.com/example/repo.git",
            tech_stack=["TypeScript"],
            blueprint={"project_summary": "Ready"},
        )

    def tearDown(self):
        if self.project.workspace_id:
            try:
                workspace_manager.delete_workspace(self.project.workspace_id)
            except Exception:
                pass
        self.temp_dir.cleanup()

    def test_get_project_does_not_report_initializing_when_blueprint_exists_and_docs_are_idle(self):
        response = self.client.get(f"/api/projects/{self.project.id}/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["context_initializing"])


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ProjectChatTraceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        (self.project_root / "src").mkdir()
        (self.project_root / "backend").mkdir()
        (self.project_root / "backend" / "agents").mkdir()
        (self.project_root / "README.md").write_text("# Trace Demo\nUse the App component.\n", encoding="utf-8")
        (self.project_root / "src" / "App.tsx").write_text(
            "export default function App() { return <main>Hello trace</main>; }\n",
            encoding="utf-8",
        )
        (self.project_root / "backend" / "agents" / "architect.py").write_text(
            "class ArchitectAgent:\n    pass\n",
            encoding="utf-8",
        )
        (self.project_root / "backend" / "agents" / "memory.py").write_text(
            "def build_memory_context():\n    return {}\n",
            encoding="utf-8",
        )
        (self.project_root / "src" / "vendor.min.js").write_text(
            "const data='" + ("x" * 2400) + "';\n",
            encoding="utf-8",
        )
        workspace_id = workspace_manager.create_workspace(str(self.project_root), managed=False)
        self.project = Project.objects.create(
            name="Trace Demo",
            description="Project for chat trace tests",
            local_path=str(self.project_root),
            workspace_id=workspace_id,
            tech_stack=["React", "TypeScript"],
        )

    def tearDown(self):
        if self.project.workspace_id:
            try:
                workspace_manager.delete_workspace(self.project.workspace_id)
            except Exception:
                pass
        self.temp_dir.cleanup()

    def test_chat_trace_records_explicit_file_and_readme_context(self):
        with patch("agents.base.BaseAgent.generate", return_value="This is the grounded answer."):
            response = self.client.post(
                f"/api/projects/{self.project.id}/chat/",
                data=json.dumps(
                    {
                        "content": "Explain @readme and @src/App.tsx",
                        "context_mentions": [
                            {"type": "special", "value": "readme"},
                            {"type": "file", "value": "src/App.tsx"},
                        ],
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assistant_message"], "This is the grounded answer.")
        trace_files = {item.get("path") for item in payload["trace"].get("files_accessed", [])}
        self.assertIn("README.md", trace_files)
        self.assertIn("src/App.tsx", trace_files)

        assistant_message = ChatMessage.objects.filter(project=self.project, role="assistant").latest("created_at")
        self.assertIn("files_accessed", assistant_message.metadata)
        self.assertTrue(any(item.get("path") == "src/App.tsx" for item in assistant_message.metadata.get("files_accessed", [])))

    def test_chat_sessions_are_separated_and_filterable(self):
        ChatMessage.objects.create(
            project=self.project,
            role="user",
            content="First thread question",
            metadata={"session_id": "session-a"},
        )
        ChatMessage.objects.create(
            project=self.project,
            role="assistant",
            content="First thread answer",
            metadata={"session_id": "session-a"},
        )
        ChatMessage.objects.create(
            project=self.project,
            role="user",
            content="Second thread question",
            metadata={"session_id": "session-b"},
        )
        ChatMessage.objects.create(
            project=self.project,
            role="assistant",
            content="Second thread answer",
            metadata={"session_id": "session-b"},
        )

        response = self.client.get(
            f"/api/projects/{self.project.id}/chat/?session_id=session-b",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["active_session_id"], "session-b")
        self.assertEqual([item["content"] for item in payload["messages"]], ["Second thread question", "Second thread answer"])
        self.assertEqual(payload["messages"][0]["session_id"], "session-b")
        self.assertEqual(len(payload["sessions"]), 2)

    def test_chat_can_lazy_load_explicit_file_that_blueprint_index_skipped(self):
        cache = build_blueprint_context(self.project, self.project_root, force=True)
        indexed_paths = {item.get("path") for item in cache.get("all_file_summaries", [])}
        self.assertNotIn("src/vendor.min.js", indexed_paths)

        with patch("agents.base.BaseAgent.generate", return_value="Lazy file answer."):
            response = self.client.post(
                f"/api/projects/{self.project.id}/chat/",
                data=json.dumps(
                    {
                        "content": "Explain @src/vendor.min.js",
                        "context_mentions": [
                            {"type": "file", "value": "src/vendor.min.js"},
                        ],
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assistant_message"], "Lazy file answer.")
        trace_files = payload["trace"].get("files_accessed", [])
        self.assertTrue(any(item.get("path") == "src/vendor.min.js" and item.get("source") == "lazy_file" for item in trace_files))

    def test_chat_plans_manifest_backed_reads_without_explicit_mentions(self):
        build_blueprint_context(self.project, self.project_root, force=True)

        with patch("agents.base.BaseAgent.generate", return_value="Planned answer."):
            response = self.client.post(
                f"/api/projects/{self.project.id}/chat/",
                data=json.dumps(
                    {
                        "content": "How does the App component work in this project?",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assistant_message"], "Planned answer.")
        self.assertTrue(any(item.get("path") == "src/App.tsx" for item in payload["trace"].get("files_accessed", [])))
        self.assertTrue(any(item.get("label") == "@codebase-planned" for item in payload["trace"].get("context_sources", [])))

    def test_chat_broad_folder_question_materializes_multiple_related_files(self):
        build_blueprint_context(self.project, self.project_root, force=True)

        with patch("agents.base.BaseAgent.generate", return_value="Folder answer."):
            response = self.client.post(
                f"/api/projects/{self.project.id}/chat/",
                data=json.dumps(
                    {
                        "content": "@codebase tell me about all the individual files in agents",
                        "context_mentions": [
                            {"type": "special", "value": "codebase"},
                        ],
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        trace_paths = {item.get("path") for item in payload["trace"].get("files_accessed", [])}
        self.assertIn("backend/agents/architect.py", trace_paths)
        self.assertIn("backend/agents/memory.py", trace_paths)


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class MemoryArchitectureTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        (self.project_root / "src").mkdir()
        (self.project_root / "src" / "auth.js").write_text(
            "export function loginUser(email, password) { return `${email}:${password}`; }\n",
            encoding="utf-8",
        )
        (self.project_root / "package-lock.json").write_text(json.dumps({"lockfileVersion": 3, "packages": {}}), encoding="utf-8")
        (self.project_root / "src" / "bundle.min.js").write_text("const packed='" + ("y" * 3200) + "';\n", encoding="utf-8")
        self.project = Project.objects.create(
            name="Memory Project",
            description="Project for testing memory architecture",
            local_path=str(self.project_root),
            tech_stack=["react"],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_memory_layers_store_and_recall_context(self):
        record_episode(
            project=self.project,
            memory_type="decision",
            title="Auth strategy",
            summary="JWT was chosen for authentication flows.",
            related_files=["src/auth.js"],
        )
        compress_recent_activity(self.project)
        index_semantic_memory(self.project, self.project_root)
        memory_context = build_memory_context(self.project, "find the auth function for jwt login", selected_file="src/auth.js")

        self.assertTrue(WorkingMemory.objects.filter(project=self.project, scope="implementation").exists())
        self.assertTrue(SemanticMemory.objects.filter(project=self.project, file_path="src/auth.js").exists())
        self.assertIn("JWT", memory_context["episodic_summary"])
        self.assertIn("src/auth.js", memory_context["semantic_summary"])

    def test_blueprint_context_is_cached_with_fingerprint(self):
        cache = build_blueprint_context(self.project, self.project_root)
        self.assertTrue(cache["fingerprint"])
        self.assertTrue((self.project_root / ".devhub" / "blueprint-context.json").exists())
        self.assertTrue((self.project_root / ".devhub" / "manifest.json").exists())
        self.assertTrue((self.project_root / ".devhub" / "dependency-graph.json").exists())
        self.assertTrue((self.project_root / ".devhub" / "repo-map.md").exists())
        self.assertIn("src/auth.js", json.dumps(cache))
        indexed_paths = {item.get("path") for item in cache.get("all_file_summaries", [])}
        self.assertNotIn("package-lock.json", indexed_paths)
        self.assertNotIn("src/bundle.min.js", indexed_paths)
        manifest_map = {item.get("path"): item for item in cache.get("manifest", [])}
        self.assertEqual(manifest_map["package-lock.json"]["tier"], 3)
        self.assertEqual(manifest_map["src/bundle.min.js"]["tier"], 3)
        self.assertEqual(manifest_map["src/auth.js"]["tier"], 2)

    def test_blueprint_context_extracts_real_django_schema_and_ignores_frontend_types(self):
        (self.project_root / "backend" / "core").mkdir(parents=True, exist_ok=True)
        (self.project_root / "frontend" / "src").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "core" / "models.py").write_text(
            "\n".join(
                [
                    "from django.db import models",
                    "",
                    "class Project(models.Model):",
                    "    id = models.UUIDField(primary_key=True)",
                    "    name = models.CharField(max_length=255)",
                    "    workspace_id = models.CharField(max_length=255, null=True, blank=True)",
                    "",
                    "class Feature(models.Model):",
                    "    project = models.ForeignKey(Project, related_name='features', on_delete=models.CASCADE)",
                    "    title = models.CharField(max_length=255)",
                    "    created_at = models.DateTimeField(auto_now_add=True)",
                    "",
                    "class WorkingMemory(models.Model):",
                    "    project = models.ForeignKey(Project, related_name='working_memories', on_delete=models.CASCADE)",
                    "    scope = models.CharField(max_length=100, default='implementation')",
                    "",
                    "    class Meta:",
                    "        unique_together = ('project', 'scope')",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "src" / "Dashboard.tsx").write_text(
            "\n".join(
                [
                    "interface ProjectInspection {",
                    "  name: string;",
                    "  runtime: object;",
                    "}",
                    "",
                    "interface RuntimeState {",
                    "  run_command?: string;",
                    "}",
                ]
            ),
            encoding="utf-8",
        )

        cache = build_blueprint_context(self.project, self.project_root, force=True)

        table_names = {item.get("table") for item in cache.get("database_schema", [])}
        self.assertIn("Project", table_names)
        self.assertIn("Feature", table_names)
        self.assertIn("WorkingMemory", table_names)
        self.assertNotIn("ProjectInspection", table_names)
        self.assertEqual(cache.get("database_source_files"), ["backend/core/models.py"])
        self.assertIn("Project ||--o{ Feature : project", cache.get("database_mermaid_erd", ""))

        working_memory = next(item for item in cache.get("database_schema", []) if item.get("table") == "WorkingMemory")
        self.assertIn("unique_together=('project', 'scope')", working_memory.get("indexes", []))

    def test_blueprint_context_builds_api_reference_from_real_django_routes(self):
        (self.project_root / "backend" / "devhub_backend").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "api").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "devhub_backend" / "urls.py").write_text(
            "\n".join(
                [
                    "from django.urls import include, path",
                    "",
                    "urlpatterns = [",
                    "    path('api/', include('api.urls')),",
                    "]",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "api" / "urls.py").write_text(
            "\n".join(
                [
                    "from django.urls import path",
                    "from . import views",
                    "",
                    "urlpatterns = [",
                    "    path('projects/', views.list_projects, name='list_projects'),",
                    "    path('projects/<str:project_id>/chat/', views.project_chat, name='project_chat'),",
                    "    path('workspace/<str:workspace_id>/runtime/', views.workspace_runtime, name='workspace_runtime'),",
                    "]",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "api" / "views.py").write_text(
            "\n".join(
                [
                    "from django.http import JsonResponse",
                    "",
                    "def list_projects(request):",
                    "    return JsonResponse({'projects': []})",
                    "",
                    "def project_chat(request, project_id):",
                    "    if request.method == 'GET':",
                    "        session_id = request.GET.get('session_id', '')",
                    "        return JsonResponse({'messages': [], 'active_session_id': session_id})",
                    "",
                    "    if request.method == 'POST':",
                    "        body = {'content': ''}",
                    "        content = body.get('content', '').strip()",
                    "        if not content:",
                    "            return JsonResponse({'error': 'Message is required'}, status=400)",
                    "        return JsonResponse({'assistant_message': 'ok'})",
                    "",
                    "    return JsonResponse({'error': 'Method not allowed'}, status=405)",
                    "",
                    "def _runtime_response_payload():",
                    "    return {'status': {'running': True}, 'preview_url': 'http://127.0.0.1:3000', 'ready': True, 'process_id': 'proc_1', 'preview_error': None}",
                    "",
                    "def workspace_runtime(request, workspace_id):",
                    "    if request.method == 'GET':",
                    "        return JsonResponse(_runtime_response_payload())",
                    "    if request.method == 'POST':",
                    "        body = {'command': 'npm run dev'}",
                    "        return JsonResponse(_runtime_response_payload())",
                    "    return JsonResponse({'error': 'Method not allowed'}, status=405)",
                ]
            ),
            encoding="utf-8",
        )

        api_reference = build_api_reference_catalog(self.project_root)
        signatures = {(item.get("method"), item.get("path")): item for item in api_reference}

        self.assertIn(("GET", "/api/projects/"), signatures)
        self.assertIn(("GET", "/api/projects/<str:project_id>/chat/"), signatures)
        self.assertIn(("POST", "/api/projects/<str:project_id>/chat/"), signatures)
        self.assertIn(("GET", "/api/workspace/<str:workspace_id>/runtime/"), signatures)
        self.assertIn(("POST", "/api/workspace/<str:workspace_id>/runtime/"), signatures)
        self.assertEqual(signatures[("GET", "/api/projects/<str:project_id>/chat/")]["query_params"][0]["name"], "session_id")
        self.assertEqual(signatures[("POST", "/api/projects/<str:project_id>/chat/")]["request_fields"][0]["name"], "content")
        self.assertEqual(
            signatures[("GET", "/api/workspace/<str:workspace_id>/runtime/")]["response_keys"],
            ["status", "preview_url", "ready", "process_id", "preview_error"],
        )
        self.assertEqual(signatures[("POST", "/api/workspace/<str:workspace_id>/runtime/")]["status_codes"], [200, 405])
        api_text = json.dumps(api_reference)
        self.assertNotIn("DevHub", api_text)
        self.assertNotIn("Blueprint screen", api_text)

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        enriched = _enrich_blueprint_document(self.project, {"api_endpoints": [{"path": "/wrong/"}]}, cache, "")
        enriched_signatures = {(item.get("method"), item.get("path")) for item in enriched.get("api_endpoints", [])}

        self.assertIn(("GET", "/api/projects/"), enriched_signatures)
        self.assertIn(("POST", "/api/projects/<str:project_id>/chat/"), enriched_signatures)
        self.assertNotIn((None, "/wrong/"), enriched_signatures)

    def test_enrich_blueprint_derives_setup_quality_and_knowledge_from_repo_evidence(self):
        (self.project_root / "backend" / "devhub_backend").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "api").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "core").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "sandbox").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "editor").mkdir(parents=True, exist_ok=True)
        (self.project_root / "frontend" / "src").mkdir(parents=True, exist_ok=True)
        (self.project_root / "README.md").write_text(
            "\n".join(
                [
                    "# Split Stack App",
                    "",
                    "Backend lives in `backend/` and frontend lives in `frontend/`.",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / ".env.example").write_text(
            "\n".join(
                [
                    "OPENAI_API_KEY=",
                    "VITE_API_BASE_URL=http://127.0.0.1:8000",
                    "DJANGO_DEBUG=True",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "manage.py").write_text(
            "\n".join(
                [
                    "import os",
                    "import sys",
                    "",
                    "def main():",
                    "    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'devhub_backend.settings')",
                    "    from django.core.management import execute_from_command_line",
                    "    execute_from_command_line(sys.argv)",
                    "",
                    "if __name__ == '__main__':",
                    "    main()",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "requirements.txt").write_text(
            "Django>=5.0\nchannels>=4.0\n",
            encoding="utf-8",
        )
        (self.project_root / "backend" / "devhub_backend" / "urls.py").write_text(
            "\n".join(
                [
                    "from django.urls import include, path",
                    "",
                    "urlpatterns = [",
                    "    path('api/', include('api.urls')),",
                    "]",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "devhub_backend" / "settings.py").write_text(
            "\n".join(
                [
                    "import os",
                    "",
                    "SECRET_KEY = 'hardcoded-dev-secret'",
                    "DEBUG = True",
                    "CORS_ALLOW_ALL_ORIGINS = True",
                    "OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')",
                    "DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'db.sqlite3'}}",
                    "CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "api" / "urls.py").write_text(
            "\n".join(
                [
                    "from django.urls import path",
                    "from . import views",
                    "",
                    "urlpatterns = [",
                    "    path('projects/<str:project_id>/chat/', views.project_chat, name='project_chat'),",
                    "    path('workspace/<str:workspace_id>/runtime/', views.workspace_runtime, name='workspace_runtime'),",
                    "]",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "api" / "views.py").write_text(
            "\n".join(
                [
                    "from django.http import JsonResponse",
                    "from django.views.decorators.csrf import csrf_exempt",
                    "",
                    "@csrf_exempt",
                    "def project_chat(request, project_id):",
                    "    if request.method == 'GET':",
                    "        return JsonResponse({'messages': []})",
                    "    if request.method == 'POST':",
                    "        return JsonResponse({'assistant_message': 'ok'})",
                    "    return JsonResponse({'error': 'Method not allowed'}, status=405)",
                    "",
                    "@csrf_exempt",
                    "def workspace_runtime(request, workspace_id):",
                    "    if request.method == 'GET':",
                    "        return JsonResponse({'status': {'running': True}, 'preview_url': 'http://127.0.0.1:3000', 'ready': True, 'process_id': 'proc_1'})",
                    "    if request.method == 'POST':",
                    "        return JsonResponse({'status': {'running': True}, 'preview_url': 'http://127.0.0.1:3000', 'ready': True, 'process_id': 'proc_1'})",
                    "    return JsonResponse({'error': 'Method not allowed'}, status=405)",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "api" / "tests.py").write_text(
            "\n".join(
                [
                    "from django.test import TestCase",
                    "",
                    "class ApiTests(TestCase):",
                    "    def test_chat(self):",
                    "        self.assertTrue(True)",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "core" / "models.py").write_text(
            "\n".join(
                [
                    "from django.db import models",
                    "",
                    "class Project(models.Model):",
                    "    name = models.CharField(max_length=255)",
                    "",
                    "class Feature(models.Model):",
                    "    project = models.ForeignKey(Project, related_name='features', on_delete=models.CASCADE)",
                    "    title = models.CharField(max_length=255)",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "sandbox" / "executor.py").write_text(
            "\n".join(
                [
                    "import subprocess",
                    "",
                    "def run_command(command):",
                    "    return subprocess.Popen(command, shell=True)",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "editor" / "consumers.py").write_text(
            "\n".join(
                [
                    "import asyncio",
                    "",
                    "async def stream_output():",
                    "    while True:",
                    "        await asyncio.sleep(0.1)",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "package.json").write_text(
            json.dumps(
                {
                    "name": "frontend-app",
                    "scripts": {
                        "dev": "vite",
                        "build": "vite build",
                        "lint": "eslint .",
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "eslint.config.js").write_text(
            "export default [];\n",
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "tsconfig.json").write_text(
            json.dumps({"compilerOptions": {"jsx": "react-jsx"}}),
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "src" / "api.ts").write_text(
            "\n".join(
                [
                    "export const apiBase = import.meta.env.VITE_API_BASE_URL;",
                    "export async function loadRuntime() {",
                    "  return fetch(`${apiBase}/api/workspace/demo/runtime/`);",
                    "}",
                ]
            ),
            encoding="utf-8",
        )

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        enriched = _enrich_blueprint_document(self.project, {}, cache, "")

        setup_commands = "\n".join(str(item.get("command") or "") for item in enriched.get("setup_steps", []) if isinstance(item, dict))
        self.assertIn("cd backend && python -m pip install -r requirements.txt", setup_commands)
        self.assertIn("cd backend && python manage.py migrate", setup_commands)
        self.assertIn("cd backend && python manage.py runserver", setup_commands)
        self.assertIn("cd frontend && npm install", setup_commands)
        self.assertIn("cd frontend && npm run dev", setup_commands)

        env_names = {item.get("name") for item in enriched.get("environment_variables", []) if isinstance(item, dict)}
        self.assertIn("OPENAI_API_KEY", env_names)
        self.assertIn("VITE_API_BASE_URL", env_names)

        security_areas = {item.get("area") for item in enriched.get("security_considerations", []) if isinstance(item, dict)}
        self.assertIn("Shell-based command execution", security_areas)
        self.assertIn("Development settings exposed", security_areas)
        self.assertIn("Mutating routes without explicit auth markers", security_areas)

        performance_areas = {item.get("area") for item in enriched.get("performance_notes", []) if isinstance(item, dict)}
        self.assertIn("In-memory channel layer", performance_areas)
        self.assertIn("Polling-based process or websocket loops", performance_areas)

        self.assertIn("python manage.py test", str((enriched.get("testing_strategy") or {}).get("run_command") or ""))

        quality_tools = {item.get("tool") for item in enriched.get("code_quality_standards", []) if isinstance(item, dict)}
        self.assertIn("ESLint", quality_tools)
        self.assertIn("TypeScript", quality_tools)

        overview_health = [item for item in enriched.get("overview_project_health", []) if isinstance(item, dict)]
        self.assertTrue(overview_health)
        self.assertTrue(any(item.get("label") == "Runtime" for item in overview_health))

        runtime_entrypoints = [item for item in enriched.get("overview_runtime_entrypoints", []) if isinstance(item, dict)]
        runtime_paths = {item.get("path") for item in runtime_entrypoints}
        runtime_commands = "\n".join(str(item.get("command") or "") for item in runtime_entrypoints)
        self.assertIn("backend/manage.py", runtime_paths)
        self.assertIn("frontend/package.json", runtime_paths)
        self.assertIn("cd backend && python manage.py runserver", runtime_commands)
        self.assertIn("cd frontend && npm run dev", runtime_commands)

        read_first_paths = {item.get("path") for item in enriched.get("overview_read_first", []) if isinstance(item, dict)}
        self.assertIn("README.md", read_first_paths)

        next_steps = [item for item in enriched.get("overview_next_steps", []) if isinstance(item, dict)]
        self.assertTrue(next_steps)

        concepts = [item for item in enriched.get("key_concepts", []) if isinstance(item, dict)]
        self.assertTrue(concepts)
        self.assertTrue(all(item.get("concept") and item.get("explanation") for item in concepts))
        self.assertTrue(any(item.get("related_code") for item in concepts))

        faq = [item for item in enriched.get("faq", []) if isinstance(item, dict)]
        self.assertTrue(any("run the project" in str(item.get("question") or "").lower() for item in faq))
        self.assertTrue(enriched.get("gotchas"))
        knowledge_text = json.dumps({
            "faq": enriched.get("faq"),
            "gotchas": enriched.get("gotchas"),
            "onboarding": enriched.get("onboarding_checklist"),
        })
        self.assertNotIn("Dashboard > AI Settings", knowledge_text)
        self.assertNotIn("How does DevHub", knowledge_text)

    def test_enrich_blueprint_collapses_low_signal_ai_override_envs_without_template(self):
        (self.project_root / "backend" / "devhub_backend").mkdir(parents=True, exist_ok=True)
        (self.project_root / "frontend" / "src").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "devhub_backend" / "settings.py").write_text(
            "\n".join(
                [
                    "import os",
                    "OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')",
                    "ANTHROPIC_BASE_URL = os.getenv('ANTHROPIC_BASE_URL', '')",
                    "DEVHUB_API_KEY = os.getenv('DEVHUB_API_KEY', '')",
                    "DEVHUB_BLUEPRINT_MODEL = os.getenv('DEVHUB_BLUEPRINT_MODEL', '')",
                    "DEVHUB_CLAUDE_MODEL = os.getenv('DEVHUB_CLAUDE_MODEL', '')",
                    "DEVHUB_DEFAULT_PROVIDER = os.getenv('DEVHUB_DEFAULT_PROVIDER', '')",
                    "GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', '')",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "src" / "api.ts").write_text(
            "export const apiBase = import.meta.env.VITE_API_BASE_URL;\n",
            encoding="utf-8",
        )

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        enriched = _enrich_blueprint_document(self.project, {}, cache, "")
        env_names = {item.get("name") for item in enriched.get("environment_variables", []) if isinstance(item, dict)}

        self.assertIn("AI provider configuration", env_names)
        self.assertIn("VITE_API_BASE_URL", env_names)
        self.assertNotIn("DEVHUB_BLUEPRINT_MODEL", env_names)
        self.assertNotIn("DEVHUB_CLAUDE_MODEL", env_names)
        self.assertNotIn("DEVHUB_DEFAULT_PROVIDER", env_names)

    def test_database_section_selection_and_enrichment_prefer_structured_backend_schema(self):
        (self.project_root / "backend" / "core").mkdir(parents=True, exist_ok=True)
        (self.project_root / "frontend" / "src").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "core" / "models.py").write_text(
            "\n".join(
                [
                    "from django.db import models",
                    "",
                    "class Project(models.Model):",
                    "    name = models.CharField(max_length=255)",
                    "",
                    "class Feature(models.Model):",
                    "    project = models.ForeignKey(Project, related_name='features', on_delete=models.CASCADE)",
                    "    title = models.CharField(max_length=255)",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "src" / "Dashboard.tsx").write_text(
            "interface ProjectInspection { name: string; }\n",
            encoding="utf-8",
        )

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        selected_paths = [item.get("path") for item in select_files_for_section(cache, "database", self.project_root)]
        self.assertIn("backend/core/models.py", selected_paths)
        self.assertNotIn("frontend/src/Dashboard.tsx", selected_paths)

        enriched = _enrich_blueprint_document(
            self.project,
            {
                "database_schema": [{"table": "ProjectInspection", "description": "Frontend type"}],
                "mermaid_erd": "erDiagram\n  ProjectInspection {}",
            },
            cache,
            "",
        )
        enriched_tables = {item.get("table") for item in enriched.get("database_schema", [])}
        self.assertIn("Project", enriched_tables)
        self.assertIn("Feature", enriched_tables)
        self.assertNotIn("ProjectInspection", enriched_tables)

    def test_enrich_blueprint_hides_internal_devhub_instruction_files(self):
        (self.project_root / "DEVHUB.md").write_text("# Project Instructions\nReal repo guidance.\n", encoding="utf-8")
        (self.project_root / ".devhub").mkdir(parents=True, exist_ok=True)
        (self.project_root / ".devhub" / "DEVHUB.md").write_text("# DevHub Instructions\nTemplate placeholder.\n", encoding="utf-8")

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        enriched = _enrich_blueprint_document(self.project, {}, cache, "")
        instruction_paths = [item.get("path") for item in enriched.get("instruction_files", [])]

        self.assertIn("DEVHUB.md", instruction_paths)
        self.assertNotIn(".devhub/DEVHUB.md", instruction_paths)

    def test_enrich_blueprint_design_doc_rerenders_and_filters_template_content(self):
        (self.project_root / "README.md").write_text(
            "\n".join(
                [
                    "# Memory Project",
                    "",
                    "## Setup",
                    "npm install",
                    "npm run dev",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "package.json").write_text(
            json.dumps(
                {
                    "name": "memory-project",
                    "scripts": {
                        "dev": "vite",
                        "test": "vitest",
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.project_root / "manage.py").write_text("print('manage')\n", encoding="utf-8")
        (self.project_root / "backend").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "api").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "api" / "tests.py").write_text(
            "def test_api_health():\n    assert True\n",
            encoding="utf-8",
        )

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        enriched = _enrich_blueprint_document(
            self.project,
            {
                "integration_points": [
                    {
                        "name": "External API",
                        "description": "Integrates with third-party services for additional functionalities.",
                    }
                ],
                "setup_steps": [
                    {"step": "Clone the repository", "command": "git clone <repository-url>"},
                    {"step": "Run migrations", "command": "python manage.py migrate"},
                ],
                "environment_variables": [
                    {
                        "name": "DJANGO_SETTINGS_MODULE",
                        "description": "Specifies the settings module for Django.",
                    }
                ],
                "testing_strategy": {
                    "unit": "Use pytest for unit testing backend components.",
                    "integration": "Test API endpoints using Django's test client.",
                    "e2e": "Utilize Cypress for end-to-end testing of the frontend.",
                    "run_command": "pytest",
                },
                "security_considerations": [
                    {
                        "area": "Authentication",
                        "description": "Ensure secure handling of user credentials and tokens.",
                    }
                ],
                "performance_notes": [
                    {
                        "area": "Caching",
                        "description": "Consider implementing caching strategies for frequently accessed data.",
                    }
                ],
                "key_concepts": [
                    {
                        "concept": "REST API",
                        "explanation": "The application uses RESTful principles for API design.",
                    }
                ],
                "gotchas": [
                    "Ensure to run migrations after pulling new changes to avoid database inconsistencies.",
                ],
                "design_document_markdown": "x" * 7000,
                "design_document_sections": [
                    {"id": f"section-{index}", "title": f"Section {index}", "markdown": "stale"}
                    for index in range(8)
                ],
            },
            cache,
            "",
        )

        markdown = enriched.get("design_document_markdown", "")
        self.assertNotEqual(markdown, "x" * 7000)
        self.assertNotIn("third-party services", markdown.lower())
        self.assertNotIn("<repository-url>", markdown)
        self.assertNotIn("python manage.py migrate", markdown)
        self.assertNotIn("django_settings_module", markdown.lower())
        self.assertNotIn("django's test client", markdown.lower())
        self.assertNotIn("cypress", markdown.lower())
        self.assertNotIn("restful principles", markdown.lower())
        self.assertNotIn("database inconsistencies", markdown.lower())
        self.assertIn("backend/api/tests.py", markdown)
        self.assertIn("npm run test", markdown)

    def test_retrieval_boosts_generic_infrastructure_queries(self):
        (self.project_root / "backend").mkdir()
        (self.project_root / "backend" / "sandbox").mkdir()
        (self.project_root / "backend" / "agents").mkdir()
        (self.project_root / "backend" / "sandbox" / "executor.py").write_text(
            "\n".join(
                [
                    "class SandboxManager:",
                    "    def run_command(self, process_id, cmd, work_dir):",
                    "        return {'process_id': process_id, 'cmd': cmd, 'work_dir': work_dir}",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "agents" / "workspace.py").write_text(
            "\n".join(
                [
                    "class WorkspaceManager:",
                    "    def get_workspace_path(self, workspace_id):",
                    "        return workspace_id",
                ]
            ),
            encoding="utf-8",
        )

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        retrieval = retrieve_relevant_files(
            cache,
            self.project_root,
            "How is sandboxing and terminal process execution implemented?",
            max_files=6,
            include_neighbors=True,
        )
        retrieved_paths = {item.get("path") for item in retrieval.get("files", [])}

        self.assertIn("backend/sandbox/executor.py", retrieved_paths)
        self.assertIn("backend/agents/workspace.py", retrieved_paths)

    def test_retrieval_discovers_files_from_content_before_summary_scoring(self):
        (self.project_root / "backend").mkdir()
        (self.project_root / "backend" / "core").mkdir()
        (self.project_root / "backend" / "core" / "bridge.py").write_text(
            "\n".join(
                [
                    "def handle_bridge(payload, process):",
                    "    stdout_line = process.stdout.readline()",
                    "    stderr_line = process.stderr.readline()",
                    "    incoming = payload.get('stdin')",
                    "    if incoming:",
                    "        process.stdin.write(incoming)",
                    "    return {'stdout': stdout_line, 'stderr': stderr_line}",
                ]
            ),
            encoding="utf-8",
        )

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        retrieval = retrieve_relevant_files(
            cache,
            self.project_root,
            "Which file handles stdout stderr and stdin piping for terminal processes?",
            max_files=4,
            include_neighbors=False,
        )
        retrieved_paths = {item.get("path") for item in retrieval.get("files", [])}
        retrieval_trace = retrieval.get("trace", [])

        self.assertIn("backend/core/bridge.py", retrieved_paths)
        self.assertTrue(
            any(
                item.get("path") == "backend/core/bridge.py" and item.get("source") == "discovery_content"
                for item in retrieval_trace
            )
        )

    def test_retrieval_covers_frontend_and_backend_for_system_explanation_queries(self):
        (self.project_root / "backend").mkdir()
        (self.project_root / "backend" / "sandbox").mkdir()
        (self.project_root / "frontend").mkdir()
        (self.project_root / "frontend" / "src").mkdir()
        (self.project_root / "backend" / "sandbox" / "executor.py").write_text(
            "\n".join(
                [
                    "class ProcessHandle:",
                    "    def spawn(self, command):",
                    "        return {'command': command, 'stdout': True, 'stderr': True}",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "src" / "Terminal.tsx").write_text(
            "\n".join(
                [
                    "export function Terminal() {",
                    "  return <section>Connected to sandboxed terminal runtime</section>;",
                    "}",
                ]
            ),
            encoding="utf-8",
        )

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        retrieval = retrieve_relevant_files(
            cache,
            self.project_root,
            "Tell me about my sandboxing code, how does it work end to end?",
            max_files=8,
            include_neighbors=True,
        )
        retrieved_paths = {item.get("path") for item in retrieval.get("files", [])}

        self.assertIn("backend/sandbox/executor.py", retrieved_paths)
        self.assertIn("frontend/src/Terminal.tsx", retrieved_paths)

    def test_retrieval_prefers_frontend_navigation_files_for_style_queries(self):
        (self.project_root / "frontend").mkdir()
        (self.project_root / "frontend" / "src").mkdir()
        (self.project_root / "frontend" / "src" / "pages").mkdir(parents=True, exist_ok=True)
        (self.project_root / "frontend" / "src" / "components").mkdir(parents=True, exist_ok=True)
        (self.project_root / "frontend" / "src" / "pages" / "ProjectView.tsx").write_text(
            "\n".join(
                [
                    "export default function ProjectView() {",
                    "  return <button className={activeTab === tab.id ? 'bg-black text-white' : 'hover:bg-white'}>Item</button>;",
                    "}",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "frontend" / "src" / "components" / "Sidebar.tsx").write_text(
            "\n".join(
                [
                    "export function Sidebar() {",
                    "  return <nav className='text-slate-600 hover:bg-slate-50'>Sidebar</nav>;",
                    "}",
                ]
            ),
            encoding="utf-8",
        )
        (self.project_root / "backend" / "api").mkdir(parents=True, exist_ok=True)
        (self.project_root / "backend" / "api" / "urls.py").write_text(
            "urlpatterns = []\n",
            encoding="utf-8",
        )

        cache = build_blueprint_context(self.project, self.project_root, force=True)
        retrieval = retrieve_relevant_files(
            cache,
            self.project_root,
            "I just want to change the highlight color for the sidebar items in the frontend",
            max_files=6,
            include_neighbors=True,
        )
        retrieved_paths = {item.get("path") for item in retrieval.get("files", [])}

        self.assertIn("frontend/src/pages/ProjectView.tsx", retrieved_paths)
        self.assertIn("frontend/src/components/Sidebar.tsx", retrieved_paths)


class RuntimeDetectionTests(TestCase):
    def test_static_runtime_uses_project_specific_port(self):
        with tempfile.TemporaryDirectory() as temp_one, tempfile.TemporaryDirectory() as temp_two:
            first_root = Path(temp_one)
            second_root = Path(temp_two)
            (first_root / "index.html").write_text("<h1>one</h1>", encoding="utf-8")
            (second_root / "index.html").write_text("<h1>two</h1>", encoding="utf-8")

            first_runtime = detect_runtime(first_root)
            second_runtime = detect_runtime(second_root)

            first_port = _stable_runtime_port(first_root, start=4173)
            second_port = _stable_runtime_port(second_root, start=4173)

            self.assertEqual(first_runtime["runtime_type"], "static")
            self.assertEqual(second_runtime["runtime_type"], "static")
            self.assertIn(str(first_port), first_runtime["run_command"])
            self.assertIn(str(first_port), first_runtime["preview_url"])
            self.assertIn(str(second_port), second_runtime["run_command"])
            self.assertIn(str(second_port), second_runtime["preview_url"])
