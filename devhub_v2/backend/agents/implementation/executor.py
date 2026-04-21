import json
import logging
import os
import re
import time
from pathlib import Path

from agents.core.base import ai_config_is_usable
from agents.core.checkpoints import delete_workspace_checkpoint
from agents.memory.store import build_blueprint_context, build_memory_context
from agents.customization.project_customization import (
    build_implementation_customization_bundle,
    build_role_prompt_context,
    implementation_request_text,
)
from core.models import Feature, FeatureHistory, Project

from api.blueprint.generator import generate_blueprint_sync
from api.project_utils import MEMORY_DB_ERRORS, _project_ai_config
from api.workspace.memory import (
    _read_project_instructions,
    _read_project_memory,
    _update_project_memory,
)

from agents.implementation.plan import (
    _build_supporting_context,
    _collect_relevant_files,
    _create_implementation_plan,
    _review_attempt,
    _run_validation_suite,
)

logger = logging.getLogger(__name__)

def generate_feature_spec_sync(feature: Feature, project: Project):
    try:
        from agents.orchestration.feature import FeatureAgent

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
    request_attachments: list[dict] | None = None,
    checkpoint: dict | None = None,
    chat_mode: str | None = None,
    changeset_source: str = 'chat',
) -> dict:
    if not project.workspace_id:
        raise ValueError("No active workspace for this project.")

    from agents.coding.coder import CoderAgent

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
    customization_bundle = build_implementation_customization_bundle(workspace_path, request_text)
    base_request_text = implementation_request_text(customization_bundle, request_text) or request_text
    memory_context = build_memory_context(project, base_request_text, selected_file=selected_file)
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
    attempt_logs = []
    all_applied_files: list[str] = []
    latest_plan = {}
    latest_review = {}
    latest_validation_results: list[dict] = []
    latest_context_files: list[str] = []
    current_request_text = base_request_text
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        logger.exception("Failed to load cached codebase context for implementation in project %s", project.id)

    active_skill = customization_bundle.get("skill") if isinstance(customization_bundle.get("skill"), dict) else {}
    if active_skill:
        spec = {
            **(spec or {}),
            "project_skill": {
                "name": active_skill.get("name"),
                "description": active_skill.get("description"),
                "path": active_skill.get("path"),
                "arguments": customization_bundle.get("skill_arguments") or "",
            },
        }

    agent = CoderAgent(
        ai_config=_project_ai_config(project),
        customization_instruction=build_role_customization_addendum(customization_bundle, "coder"),
    )

    for attempt in range(1, 4):
        plan = _create_implementation_plan(
            project=project,
            request_title=request_title,
            request_text=current_request_text,
            workspace_path=workspace_path,
            project_memory=f"{project_memory[:8000]}\n\nProject Instructions:\n{project_instructions[:3000]}\n\n{memory_context_text[:4000]}",
            memory_context_text=memory_context_text,
            selected_file=selected_file,
            customization_bundle=customization_bundle,
            request_attachments=request_attachments,
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
            _build_supporting_context(project, plan, workspace_path, customization_bundle=customization_bundle)
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
            customization_context=build_role_prompt_context(customization_bundle, "coder")[:10000],
            request_attachments=request_attachments,
        )

        if result.get("status") != "success":
            raise RuntimeError(result.get("error", "Failed to apply changes."))

        applied_files = result.get("files_modified", [])
        for rel_path in applied_files:
            if rel_path not in all_applied_files:
                all_applied_files.append(rel_path)

        latest_validation_results = _run_validation_suite(workspace_path)
        latest_review = _review_attempt(
            project,
            workspace_path,
            baseline_contents,
            all_applied_files,
            latest_validation_results,
            customization_bundle=customization_bundle,
            request_text=current_request_text,
            request_attachments=request_attachments,
        )
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
            base_request_text,
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

    changeset = _record_chat_changes(
        project,
        request_text,
        workspace_path,
        baseline_contents,
        all_applied_files,
        ai_review=_chat_checkpoint_review_payload(
            checkpoint,
            source=changeset_source,
            chat_mode=chat_mode,
            undo_label='Undo Restore' if changeset_source == 'chat_undo' else 'Undo',
        ),
    )
    if checkpoint and not changeset:
        delete_workspace_checkpoint(str(project.id), str(checkpoint.get('id') or ''))
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

    if ai_config_is_usable(_project_ai_config(project)):
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
        "changeset_id": str(changeset.id) if changeset else None,
        "undo": _chat_changeset_trace_metadata(changeset).get('undo') if changeset else None,
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


