import json
import logging
import os
import re
import threading
import time
from pathlib import Path

from agents.core.base import ai_config_is_usable
from agents.core.checkpoints import create_workspace_checkpoint, delete_workspace_checkpoint, snapshot_previous_contents
from agents.core.workspace import workspace_manager
from agents.memory.store import (
    build_blueprint_context,
    build_memory_context,
    compress_recent_activity,
    index_semantic_memory,
    record_episode,
    upsert_working_memory,
)
from agents.customization.project_customization import (
    build_implementation_customization_bundle,
    build_role_customization_addendum,
    build_role_prompt_context,
    implementation_request_text,
)
from agents.skills.activation import resolve_skill_activation
from core.models import Feature, FeatureHistory, Project, SemanticMemory
from django.db import close_old_connections

from api.blueprint.generator import generate_blueprint_sync
from api.chat.handler import _record_chat_changes
from api.chat.helpers import _chat_changeset_trace_metadata, _chat_checkpoint_review_payload
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
    _all_validations_passed,
    _review_attempt,
    _run_validation_suite,
    _validation_summary,
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
    skill_activation: dict | None = None,
) -> dict:
    if not project.workspace_id:
        raise ValueError("No active workspace for this project.")

    from agents.coding.coder import CoderAgent
    from agents.customization.prompts import PromptBuilder
    from agents.memory.compaction import ContextCompactor
    from agents.memory.query_engine import QueryEngine
    from agents.tools.registry import ToolRegistry
    from api.chat.handler import _agent_max_turns_for_request, _visual_verification_result

    ai_config = _project_ai_config(project)
    workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
    auto_checkpoint = None
    if not checkpoint:
        try:
            auto_checkpoint = create_workspace_checkpoint(
                str(project.id),
                workspace_path,
                label=(request_title or request_text)[:160],
                source=changeset_source or 'implementation',
            )
            checkpoint = auto_checkpoint
        except Exception:
            logger.debug("Could not create implementation checkpoint for project %s", project.id, exc_info=True)

    try:
        semantic_exists = SemanticMemory.objects.filter(project=project).exists()
    except MEMORY_DB_ERRORS:
        semantic_exists = True
    if not semantic_exists:
        index_semantic_memory(project, workspace_path)

    compressed_summary = compress_recent_activity(project)
    project_memory = _read_project_memory(project, workspace_path)
    project_instructions = _read_project_instructions(project, workspace_path)
    skill_activation = dict(skill_activation or {})
    if not skill_activation:
        try:
            skill_activation = resolve_skill_activation(request_text, workspace_path=workspace_path)
        except Exception:
            logger.debug("Skill activation failed for implementation request in project %s", project.id, exc_info=True)
            skill_activation = {}
    effective_request_text = str(skill_activation.get("effective_request_text") or request_text).strip() or str(request_text or "").strip()
    customization_bundle = build_implementation_customization_bundle(
        workspace_path,
        effective_request_text,
        skill_override=skill_activation.get("project_skill") if isinstance(skill_activation.get("project_skill"), dict) else None,
        skill_arguments=str(skill_activation.get("project_skill_arguments") or ""),
        active_global_skills=list(skill_activation.get("active_global_skills") or []),
    )
    base_request_text = implementation_request_text(customization_bundle, effective_request_text) or effective_request_text
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
    hit_turn_limit = False
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

    use_agentic_loop = ai_config_is_usable(ai_config)
    coder_agent = None
    query_engine = None
    prompt_builder = None
    registry = None
    if use_agentic_loop:
        prompt_builder = PromptBuilder()
        registry = ToolRegistry.default_registry()
        query_engine = QueryEngine(
            tool_registry=registry,
            prompt_builder=prompt_builder,
            compactor=ContextCompactor(),
            ai_config=ai_config,
            workspace_id=project.workspace_id,
            workspace_path=workspace_path,
        )
    else:
        coder_agent = CoderAgent(
            ai_config=ai_config,
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

        tool_log: list[dict] = []
        if use_agentic_loop and query_engine and prompt_builder and registry:
            system_prompt = prompt_builder.build_system_prompt(
                workspace_path=workspace_path,
                tools=registry.all_tools(),
                project_memory=f"{project_memory[:8000]}\n\n{memory_context_text[:4000]}",
                project_instructions=project_instructions[:5000],
                customization_context=build_role_customization_addendum(customization_bundle, "coder")[:12000],
            )
            system_prompt += "\n\n# Implementation Contract\n"
            system_prompt += "This is an execution request, not an answer-only chat.\n"
            system_prompt += "- Inspect the workspace directly before editing.\n"
            system_prompt += "- Apply the requested code changes in files, keeping the project runnable and internally consistent.\n"
            system_prompt += "- Follow the implementation plan and supporting context below.\n"
            system_prompt += "- When the request affects UI, validate the final result visually before finishing.\n"
            system_prompt += "\n\n# Implementation Plan\n" + json.dumps(plan, indent=2)[:12000]
            system_prompt += "\n\n# Supporting Context\n" + supporting_context[:12000]
            if selected_file:
                system_prompt += f"\n\n# Active File\nThe user currently has `{selected_file}` open."
                if selected_content:
                    system_prompt += f"\n\n```text\n{selected_content[:4000]}\n```"

            query_result = query_engine.run(
                user_message=current_request_text,
                attachments=request_attachments,
                system_prompt=system_prompt,
                max_turns=max(24, _agent_max_turns_for_request(current_request_text)),
            )
            if query_result.error:
                raise RuntimeError(query_result.error)
            applied_files = list(query_result.files_modified or [])
            tool_log = list(query_result.tool_calls_log or [])
            hit_turn_limit = query_result.hit_turn_limit
        else:
            result = coder_agent.implement_feature(
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

        latest_validation_results = _run_validation_suite(workspace_path, all_applied_files)
        if use_agentic_loop and tool_log:
            visual_verification = _visual_verification_result(current_request_text, all_applied_files, tool_log)
            if visual_verification:
                latest_validation_results.append(visual_verification)
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
            'tool_calls': tool_log[-40:] if tool_log else [],
            'validation': latest_validation_results,
            'review': latest_review,
        })

        if applied_files and _all_validations_passed(latest_validation_results) and latest_review.get('approved', True):
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
        if not applied_files:
            repair_lines.append("Previous pass did not modify any files. Inspect the workspace and make the required code changes directly in this next pass.")
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

    # If the agent hit the turn limit but made partial progress, surface that
    # as a continuable partial result rather than a hard failure.
    if not all_applied_files:
        if hit_turn_limit:
            return {
                "applied_files": [],
                "count": 0,
                "plan": latest_plan,
                "review": latest_review,
                "validation_results": latest_validation_results,
                "attempts": attempt_logs,
                "context_files": latest_context_files,
                "changeset_id": None,
                "undo": None,
                "partial": True,
                "hit_turn_limit": True,
                "partial_summary": "The agent reached the turn limit before modifying any files. Use Continue to resume.",
            }
        raise RuntimeError("Implementation finished without modifying any files.")

    is_partial = hit_turn_limit and (
        not _all_validations_passed(latest_validation_results) or not latest_review.get('approved', True)
    )
    if not is_partial and not _all_validations_passed(latest_validation_results) and not latest_review.get('approved', True):
        raise RuntimeError(
            "Implementation did not pass the validation/review loop.\n"
            f"{_validation_summary(latest_validation_results)}\n"
            f"Reviewer: {latest_review.get('summary', 'No summary available.')}"
        )

    checkpoint_contents = snapshot_previous_contents(str(project.id), str((checkpoint or {}).get('id') or ''), all_applied_files)
    for rel_path, content in checkpoint_contents.items():
        baseline_contents.setdefault(rel_path, content)

    changeset = _record_chat_changes(
        project,
        request_text,
        workspace_path,
        baseline_contents,
        all_applied_files,
        ai_review=_chat_checkpoint_review_payload(
            checkpoint if chat_mode else None,
            source=changeset_source,
            chat_mode=chat_mode,
            undo_label='Undo Restore' if changeset_source == 'chat_undo' else 'Undo',
        ),
    )
    if checkpoint and not changeset:
        delete_workspace_checkpoint(str(project.id), str(checkpoint.get('id') or ''))
    elif auto_checkpoint and not chat_mode:
        delete_workspace_checkpoint(str(project.id), str(auto_checkpoint.get('id') or ''))
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
        "partial": is_partial,
        "hit_turn_limit": hit_turn_limit,
        "partial_summary": (
            f"Partial completion: {len(all_applied_files)} file(s) modified so far. "
            "The agent reached the turn limit. Use Continue to pick up where it left off."
        ) if is_partial else None,
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


