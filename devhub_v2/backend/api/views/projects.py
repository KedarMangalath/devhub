import logging
import json
import shutil
import subprocess
import threading
from pathlib import Path

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from agents.core.base import ai_config_is_usable
from agents.memory.store import _blueprint_cache_path, build_blueprint_context, compress_recent_activity, index_semantic_memory
from agents.customization.project_customization import (
    bootstrap_project_customization,
    build_project_customization_summary,
    list_project_prompt_overrides,
    list_project_skills,
    suggested_project_customization_files,
)
from agents.core.workspace import PROJECTS_DIR, workspace_manager
from core.models import DocumentationRun, Feature, FeatureApproval, FeatureHistory, Project, TestResult, WorkingMemory
from integrations.github import (
    GitHubIntegrationError,
    clone_repository_with_token,
    get_user_repository,
    github_oauth_config,
)
from integrations.models import GitHubConnection

from agents.implementation.executor import generate_feature_spec_sync, implement_feature_sync
from api.blueprint.generator import (
    _schedule_project_context_generation,
    generate_blueprint_sync,
    generate_codebase_reference_sync,
)
from api.blueprint.overview import (
    _derive_onboarding_summary,
    _project_features_payload,
    _project_flow_payload,
    _project_source_type,
    _recommended_start_tab,
    _work_items_summary,
)
from api.codebase.doc_builder import (
    _build_codebase_doc_payload,
    _project_workspace_path,
)
from api.chat.handler import run_ai_test_simulation
from api.chat.helpers import _parse_json_body
from api.project_utils import (
    MEMORY_DB_ERRORS,
    PIPELINE_STAGES,
    _github_integration_payload,
    _managed_project_root,
    _normalize_path,
    _normalize_tech_stack,
    _suggested_stack_from_text,
    _upsert_project_github_link,
)
from api.scaffold.builder import has_project_source_files, scaffold_project
from api.workspace.memory import (
    _read_scaffold_progress,
    _read_project_instructions,
    _read_project_memory,
    _render_project_features_summary,
    _safe_write_scaffold_progress,
)
from api.workspace.runtime import detect_runtime

logger = logging.getLogger(__name__)


SCAFFOLD_TASKS = [
    ("spec", "Shape the product brief"),
    ("plan", "Plan files and data model"),
    ("code", "Generate the frontend"),
    ("validate", "Validate and repair"),
    ("context", "Index workspace context"),
]


def _scaffold_progress_payload(project: Project, status: str, message: str, events: list[dict] | None = None) -> dict:
    events = list(events or [])
    event_types = {str(event.get("type") or "") for event in events}

    def task_status(task_id: str) -> str:
        if status == "failed":
            if task_id == "context":
                return "pending"
            return "failed" if task_id in {"spec", "plan", "code", "validate"} else "pending"
        if status == "done":
            return "completed"
        if task_id == "spec":
            if "spec_ready" in event_types:
                return "completed"
            return "running"
        if task_id == "plan":
            if "plan_ready" in event_types:
                return "completed"
            return "running" if "spec_ready" in event_types else "pending"
        if task_id == "code":
            if "codegen_done" in event_types:
                return "completed"
            return "running" if "plan_ready" in event_types or "file_start" in event_types else "pending"
        if task_id == "validate":
            if "validate_ok" in event_types:
                return "completed"
            return "running" if any(t.startswith("validate") for t in event_types) else "pending"
        if task_id == "context":
            return "running" if "validate_ok" in event_types or "codegen_done" in event_types else "pending"
        return "pending"

    tasks = [
        {
            "id": task_id,
            "label": label,
            "status": task_status(task_id),
        }
        for task_id, label in SCAFFOLD_TASKS
    ]
    completed = sum(1 for task in tasks if task["status"] == "completed")
    running_index = next((idx for idx, task in enumerate(tasks) if task["status"] == "running"), None)
    progress_pct = 100 if status == "done" else min(96, completed * 20 + (8 if running_index is not None else 0))

    return {
        "status": status,
        "title": f"Building {project.name}",
        "message": message,
        "progress_pct": progress_pct,
        "tasks": tasks,
        "events": events[-24:],
    }


def _run_scaffold_background(project_id: str, project_root: Path, starter_brief: str) -> None:
    """Run scaffold pipeline in a background thread, then initialize project context."""
    from django.db import connection as _db_conn
    progress_events: list[dict] = []

    def _record_progress(event: dict) -> None:
        event_payload = dict(event or {})
        event_payload["created_at"] = timezone.now().isoformat()
        progress_events.append(event_payload)
        try:
            project_for_progress = Project.objects.get(id=project_id)
        except Exception:
            return
        _safe_write_scaffold_progress(
            project_root,
            _scaffold_progress_payload(
                project_for_progress,
                "running",
                event_payload.get("message") or "Generating starter project...",
                progress_events,
            ),
        )

    try:
        project = Project.objects.get(id=project_id)
        _safe_write_scaffold_progress(
            project_root,
            _scaffold_progress_payload(project, "running", "Starting project generation...", progress_events),
        )
        scaffold_result = scaffold_project(project, project_root, starter_brief=starter_brief, on_event=_record_progress)
        generated_files = scaffold_result.get("files") if isinstance(scaffold_result, dict) else []
        if not generated_files or not has_project_source_files(project_root):
            raise RuntimeError("Scaffolding finished without writing project source files.")

        project.refresh_from_db()
        project.status = "active"
        project.save(update_fields=['status'])
        _safe_write_scaffold_progress(
            project_root,
            _scaffold_progress_payload(project, "running", "Indexing the generated workspace...", progress_events),
        )

        workspace_path = project_root
        try:
            index_semantic_memory(project, workspace_path)
            compress_recent_activity(project)
            _read_project_memory(project, workspace_path)
            _read_project_instructions(project, workspace_path)
            build_blueprint_context(project, workspace_path)
        except MEMORY_DB_ERRORS:
            logger.warning("Memory tables not ready for project %s", project_id)
        except Exception:
            logger.exception("Failed to init project memory for project %s", project_id)

        try:
            project.refresh_from_db(fields=['blueprint'])
            if not project.blueprint:
                generate_blueprint_sync(project)
        except MEMORY_DB_ERRORS:
            logger.warning("Skipped blueprint seed for project %s", project_id)
        except Exception:
            logger.exception("Failed blueprint seed for project %s", project_id)

        project.refresh_from_db(fields=['blueprint'])
        _schedule_project_context_generation(
            project,
            include_documentation=False,
            include_blueprint=not bool(project.blueprint),
        )
        _safe_write_scaffold_progress(
            project_root,
            _scaffold_progress_payload(project, "done", "Starter project is ready.", progress_events),
        )
    except Exception:
        logger.exception("Scaffold background thread failed for project %s", project_id)
        try:
            failed_project = Project.objects.get(id=project_id)
            Project.objects.filter(id=project_id).update(status="failed")
            _safe_write_scaffold_progress(
                project_root,
                _scaffold_progress_payload(failed_project, "failed", "Scaffolding failed before files were created. Check backend logs for details.", progress_events),
            )
        except Exception:
            pass
    finally:
        _db_conn.close()


def _read_cached_blueprint_context(workspace_path: Path) -> dict:
    try:
        cache_path = _blueprint_cache_path(workspace_path)
        if not cache_path.exists():
            return {}
        cached = json.loads(cache_path.read_text(encoding='utf-8', errors='ignore'))
        return cached if isinstance(cached, dict) else {}
    except Exception:
        logger.debug("Unable to read cached blueprint context for %s", workspace_path, exc_info=True)
        return {}

def list_projects(request):
    projects = []
    for project in Project.objects.all().order_by('-registered_at'):
        workspace_path = Path(project.local_path) if project.local_path else None
        scaffold_progress = _read_scaffold_progress(workspace_path) if workspace_path else None
        progress_status = str((scaffold_progress or {}).get('status') or '').lower()
        source_ready = has_project_source_files(workspace_path) if workspace_path else False
        if progress_status == "done" and not source_ready:
            progress_status = "failed"
            scaffold_progress = {
                **(scaffold_progress or {}),
                "status": "failed",
                "message": "Scaffolding reported done, but no project files were created.",
                "progress_pct": 100,
            }
        documentation_status = str(
            DocumentationRun.objects.filter(project=project).values_list('status', flat=True).first() or ''
        ).lower()
        context_initializing = (
            project.status == "scaffolding"
            or progress_status == "running"
            or documentation_status in {'pending', 'running'}
        )
        visible_status = "scaffolding" if progress_status == "running" else ("failed" if progress_status == "failed" else project.status)
        projects.append({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'status': visible_status,
            'raw_status': project.status,
            'tech_stack': project.tech_stack,
            'registered_at': project.registered_at,
            'local_path': project.local_path,
            'github_url': project.github_url,
            'github_integration': _github_integration_payload(project),
            'source_type': _project_source_type(project),
            'context_initializing': context_initializing,
            'scaffold_progress': scaffold_progress,
            'documentation_status': documentation_status,
        })
    return JsonResponse({'projects': list(projects)})


@csrf_exempt
def create_project(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        scaffold_meta: dict | None = None
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
            project_root.mkdir(parents=True, exist_ok=True)
            project.local_path = str(project_root)
            project.workspace_id = workspace_manager.create_workspace(str(project_root), managed=True)
            project.status = "scaffolding"
            project.save()
            thread = threading.Thread(
                target=_run_scaffold_background,
                args=(str(project.id), project_root, starter_brief),
                daemon=True,
            )
            thread.start()
            return JsonResponse({
                'id': str(project.id),
                'name': project.name,
                'description': project.description,
                'workspace_id': project.workspace_id,
                'status': 'scaffolding',
                'blueprint': {},
                'documentation': {},
                'context_initializing': True,
                'github_integration': _github_integration_payload(project),
                'runtime': None,
                'scaffold': None,
                'scaffold_progress': _scaffold_progress_payload(project, "running", "Starting project generation...", []),
            }, status=201)

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
        scaffold_progress = _read_scaffold_progress(Path(project.local_path)) if project.local_path else None
        scaffold_status = str((scaffold_progress or {}).get('status') or '').lower()
        context_initializing = (
            project.status == "scaffolding"
            or scaffold_status == "running"
            or (not bool(project.blueprint))
            or documentation_status in {'pending', 'running'}
        )

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
            'scaffold': scaffold_meta,
            'scaffold_progress': scaffold_progress,
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
        "slash_commands": ["/skills", *[f"/{item.get('slug') or item.get('name')}" for item in skills[:12]]],
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
        scaffold_progress = None
        features_payload = _project_features_payload(project)
        source_ready = False
        if project.local_path and Path(project.local_path).is_dir():
            workspace_path = Path(project.local_path)
            source_ready = has_project_source_files(workspace_path)
            runtime = detect_runtime(workspace_path)
            scaffold_progress = _read_scaffold_progress(workspace_path)
            scaffold_status = str((scaffold_progress or {}).get('status') or '').lower()
            if scaffold_status == "done" and not source_ready:
                project.status = "scaffolding"
                project.save(update_fields=['status'])
                scaffold_progress = _scaffold_progress_payload(
                    project,
                    "running",
                    "Retrying scaffold because no project files were created.",
                    [],
                )
                _safe_write_scaffold_progress(workspace_path, scaffold_progress)
                retry_thread = threading.Thread(
                    target=_run_scaffold_background,
                    args=(str(project.id), workspace_path, project.description or project.name),
                    daemon=True,
                )
                retry_thread.start()
                scaffold_status = "running"
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
                    _read_cached_blueprint_context(workspace_path)
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
        scaffold_status = str((scaffold_progress or {}).get('status') or '').lower()
        context_initializing = (
            project.status == "scaffolding"
            or scaffold_status == "running"
            or (not source_ready and scaffold_status not in {"failed", "done"})
            or (source_ready and not bool(project.blueprint))
            or documentation_status in {'pending', 'running'}
        )
        visible_status = "scaffolding" if scaffold_status == "running" else ("failed" if scaffold_status == "failed" else project.status)

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
            'status': visible_status,
            'raw_status': project.status,
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
            'scaffold_progress': scaffold_progress,
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


