import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from api.views import _stable_runtime_port, detect_runtime
from agents.memory import build_memory_context, compress_recent_activity, index_semantic_memory, record_episode
from agents.workspace import workspace_manager
from core.models import Changeset, FileDiff, Project, SemanticMemory, WorkingMemory
from core.models import Feature, FeatureApproval


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
class MemoryArchitectureTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        (self.project_root / "src").mkdir()
        (self.project_root / "src" / "auth.js").write_text(
            "export function loginUser(email, password) { return `${email}:${password}`; }\n",
            encoding="utf-8",
        )
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
