import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from api.views import _stable_runtime_port, _write_deep_docs_progress, detect_runtime
from agents.memory import build_blueprint_context, build_memory_context, compress_recent_activity, index_semantic_memory, record_episode
from agents.workspace import workspace_manager
from core.models import Changeset, ChatMessage, FileDiff, Project, SemanticMemory, WorkingMemory
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

        self.assertEqual(response.status_code, 200)
        chunks = list(response.streaming_content)
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
        (self.project_root / "README.md").write_text("# Demo Repo\nThis project has a React UI.\n", encoding="utf-8")
        (self.project_root / ".env.example").write_text("API_KEY=\nPORT=3000\n", encoding="utf-8")
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


@override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
class ProjectChatTraceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        (self.project_root / "src").mkdir()
        (self.project_root / "README.md").write_text("# Trace Demo\nUse the App component.\n", encoding="utf-8")
        (self.project_root / "src" / "App.tsx").write_text(
            "export default function App() { return <main>Hello trace</main>; }\n",
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

    def test_blueprint_context_is_cached_with_fingerprint(self):
        cache = build_blueprint_context(self.project, self.project_root)
        self.assertTrue(cache["fingerprint"])
        self.assertTrue((self.project_root / ".devhub" / "blueprint-context.json").exists())
        self.assertTrue((self.project_root / ".devhub" / "repo-map.md").exists())
        self.assertIn("src/auth.js", json.dumps(cache))


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
