import logging
import threading
from pathlib import Path

from django.db import close_old_connections

from agents.core.base import ai_config_is_usable
from agents.docs.documentation import generate_codebase_reference_sync
from agents.memory.store import build_blueprint_context
from core.models import DocumentationRun, Project

from api.blueprint.builders import _enrich_blueprint_document
from api.codebase.doc_builder import _project_workspace_path
from api.project_utils import DEVHUB_META_DIR, _project_ai_config
from api.workspace.memory import _render_project_features_summary

logger = logging.getLogger(__name__)

def generate_blueprint_sync(project: Project):
    """
    Generate a project blueprint and persist it to ``project.blueprint``.

    Size-based routing uses TOTAL file count (all files, any language) so
    that Go/Rust/Java/Ruby/etc. repos are routed correctly.

      any size w/ workspace → BlueprintQueryAgent (tool-based exploration)
                              agent self-discovers the tech stack via tools
      ≥ 10 000 total files  → BlueprintQueryAgent.generate_parallel()
                              (Coordinator + 3 parallel workers)
      no workspace / no AI  → ArchitectAgent fallback (best-effort)

    All paths enrich the raw blueprint through _enrich_blueprint_document and
    store _meta for UI transparency.
    """
    # ── Thresholds ────────────────────────────────────────────────────────
    PARALLEL_PATH_MIN_FILES = 10_000

    codebase_context: dict = {}
    feature_summary = _render_project_features_summary(project, limit=20)

    try:
        from agents.coding.architect import ArchitectAgent
        from agents.coding.blueprint_agent import BlueprintQueryAgent
        from agents.coding.explorer import CodebaseExplorerAgent
        from agents.memory.store import slim_context_for_llm

        local_scan = ""
        readme = ""
        exploration_report: dict = {}
        repo_map_text = ""
        workspace_path: Path | None = None
        total_file_count = 0

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
                codebase_context = build_blueprint_context(project, workspace_path, force=True)
                repo_map_path = workspace_path / DEVHUB_META_DIR / "repo-map.md"
                if repo_map_path.exists():
                    repo_map_text = repo_map_path.read_text(encoding="utf-8", errors="ignore")[:12000]
            except Exception:
                logger.exception("Blueprint context build failed for project %s", project.id)
                codebase_context = {}

            # Count ALL files (not just indexable) for routing
            total_file_count = _count_total_workspace_files(workspace_path)

        manifest_file_count = int((codebase_context or {}).get('manifest_file_count') or 0)
        ai_config = _project_ai_config(project)
        usable_ai = ai_config_is_usable(ai_config)

        logger.info(
            "Blueprint routing for project %s: total_files=%d manifest_files=%d",
            project.id,
            total_file_count,
            manifest_file_count,
        )

        # ── Route: always use tool-based BlueprintQueryAgent when possible ─
        # The agent self-discovers the tech stack; no hardcoded language assumptions.
        if usable_ai and workspace_path:
            compact_summary = str((codebase_context or {}).get('compact_summary') or '')
            repo_tree = str((codebase_context or {}).get('repo_tree') or repo_map_text or '')
            graph_summary = str((codebase_context or {}).get('graph_summary') or '')
            dir_count = len((codebase_context or {}).get('directory_counts') or {})

            agent = BlueprintQueryAgent(
                workspace_path=workspace_path,
                ai_config=ai_config,
            )

            if total_file_count >= PARALLEL_PATH_MIN_FILES:
                logger.info("Blueprint: parallel coordinator path (%d total files)", total_file_count)
                blueprint = agent.generate_parallel(
                    project_name=project.name,
                    tech_stack=project.tech_stack or [],
                    compact_summary=compact_summary,
                    repo_tree=repo_tree,
                    graph_summary=graph_summary,
                    feature_summary=feature_summary,
                    file_count=total_file_count,
                )
            else:
                logger.info("Blueprint: single-agent tool path (%d total files)", total_file_count)
                blueprint = agent.generate(
                    project_name=project.name,
                    tech_stack=project.tech_stack or [],
                    compact_summary=compact_summary,
                    repo_tree=repo_tree,
                    graph_summary=graph_summary,
                    feature_summary=feature_summary,
                    file_count=total_file_count,
                    dir_count=dir_count,
                )

        # ── Fallback: no workspace or no AI → ArchitectAgent single-call ──
        else:
            if usable_ai and codebase_context:
                try:
                    explorer = CodebaseExplorerAgent(ai_config=ai_config)
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
                            'important_files': [
                                item.get('path')
                                for item in (codebase_context.get('important_files') or [])[:12]
                            ],
                        },
                    )
                except Exception:
                    logger.exception("Blueprint exploration failed for project %s", project.id)

            architect = ArchitectAgent(ai_config=ai_config)
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
                "codebase_fingerprint": (codebase_context or {}).get("fingerprint"),
                "indexed_files": (codebase_context or {}).get("file_count"),
                "total_files": total_file_count,
                "manifest_files": manifest_file_count,
                "generation_path": (
                    "parallel_coordinator" if total_file_count >= PARALLEL_PATH_MIN_FILES
                    else "tool_agent" if workspace_path and usable_ai
                    else "fallback_single_call"
                ),
                "cached": bool(codebase_context),
            }
        project.blueprint = blueprint
        project.save()

    except Exception as exc:
        fallback_blueprint = {
            "architecture_overview": (
                f"Blueprint generation failed: {str(exc)}. "
                "Check the configured DevHub AI provider settings."
            ),
            "tech_stack_details": [
                {"tech": t, "purpose": "Core technology"} for t in (project.tech_stack or [])
            ],
            "services": [],
            "setup_steps": [],
            "gotchas": [str(exc)],
        }
        try:
            fallback_blueprint = _enrich_blueprint_document(
                project, fallback_blueprint, codebase_context, feature_summary
            )
            fallback_blueprint["_meta"] = {
                "codebase_fingerprint": (codebase_context or {}).get("fingerprint"),
                "indexed_files": (codebase_context or {}).get("file_count"),
                "manifest_files": int((codebase_context or {}).get("manifest_file_count") or 0),
                "generation_path": "fallback",
                "cached": bool(codebase_context),
            }
        except Exception:
            logger.exception("Blueprint fallback enrichment failed for project %s", project.id)
        project.blueprint = fallback_blueprint
        project.save()


def _generate_blueprint_for_project_id(project_id: str) -> None:
    close_old_connections()
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return
    except OperationalError:
        logger.warning("Skipped background blueprint generation for project %s because the database was busy.", project_id)
        return
    try:
        generate_blueprint_sync(project)
    except Exception:
        logger.exception("Background blueprint generation failed for project %s", project_id)
    finally:
        close_old_connections()


def _generate_documentation_for_project_id(project_id: str) -> None:
    close_old_connections()
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return
    except OperationalError:
        logger.warning("Skipped background documentation generation for project %s because the database was busy.", project_id)
        return
    try:
        generate_codebase_reference_sync(project)
    except Exception:
        logger.exception("Background documentation generation failed for project %s", project_id)
    finally:
        close_old_connections()


def _schedule_project_context_generation(
    project: Project,
    *,
    include_documentation: bool = False,
    include_blueprint: bool = True,
) -> None:
    if include_blueprint:
        logger.info("Scheduling background blueprint generation for project %s", project.id)
        blueprint_thread = threading.Thread(target=_generate_blueprint_for_project_id, args=(str(project.id),))
        blueprint_thread.daemon = True
        blueprint_thread.start()

    if not include_documentation:
        return

    if DocumentationRun.objects.filter(project=project, status__in=['pending', 'running']).exists():
        return

    logger.info("Scheduling background documentation generation for project %s", project.id)
    documentation_thread = threading.Thread(target=_generate_documentation_for_project_id, args=(str(project.id),))
    documentation_thread.daemon = True
    documentation_thread.start()

