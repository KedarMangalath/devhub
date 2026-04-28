import logging
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from agents.core.checkpoints import (
    create_workspace_checkpoint,
    delete_workspace_checkpoint,
    restore_workspace_checkpoint,
    snapshot_previous_contents,
)
from agents.core.workspace import workspace_manager
from agents.memory.store import build_memory_context, index_semantic_memory, record_episode, upsert_working_memory
from core.models import Changeset, ChatMessage, Project

from api.chat.handler import (
    CHAT_MODE_AGENT,
    CHAT_MODE_ASK,
    CHAT_MODE_EDIT,
    CHAT_STATE_EDIT_REQUEST,
    CHAT_STATE_GROUNDED_ANSWER,
    CHAT_STATE_NEEDS_CLARIFICATION,
    LEGACY_CHAT_SESSION_ID,
    _build_chat_llm_prompt,
    _build_chat_trace_from_changes,
    _classify_chat_state,
    _dedupe_chat_mentions,
    _group_project_chat_sessions,
    _handle_agent_chat_request,
    _infer_inline_chat_mentions,
    _normalize_chat_mentions,
    _normalize_chat_mode,
    _record_chat_changes,
    _resolve_chat_context,
    _serialize_chat_message,
    _should_apply_changes_for_chat_mode,
    apply_chat_changes,
)
from api.chat.helpers import (
    _changeset_by_id,
    _chat_changeset_trace_metadata,
    _chat_checkpoint_review_payload,
    _chat_request_text,
    _chat_undo_payload_from_review,
    _mark_changeset_undone,
    _normalize_chat_attachments,
    _parse_json_body,
)
from api.project_utils import _project_ai_config
from api.workspace.memory import _update_project_memory
from agents.skills.activation import resolve_skill_activation

logger = logging.getLogger(__name__)

@csrf_exempt
def project_chat(request, project_id):
    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValidationError, ValueError):
        return JsonResponse({'error': 'Project not found'}, status=404)

    if request.method == 'GET':
        requested_session_id = str(request.GET.get('session_id') or '').strip()
        fresh_session = str(request.GET.get('fresh') or '').strip().lower() in {'1', 'true', 'yes'}
        grouped_sessions, sessions = _group_project_chat_sessions(project)
        if fresh_session:
            active_session_id = ''
            active_messages = []
        else:
            active_session_id = requested_session_id or (sessions[0]['session_id'] if sessions else '')
            active_messages = [_serialize_chat_message(project, item) for item in grouped_sessions.get(active_session_id, [])]
        return JsonResponse(
            {
                'messages': active_messages,
                'sessions': sessions,
                'active_session_id': active_session_id or None,
            }
        )

    if request.method == 'POST':
        content = ''
        session_id = ''
        chat_checkpoint = None
        try:
            body = _parse_json_body(request)
            content = str(body.get('content') or '').strip()
            selected_file = str(body.get('selected_file') or '').strip()
            selected_content = str(body.get('selected_content') or '')
            context_mentions = body.get('context_mentions') or []
            try:
                attachments = _normalize_chat_attachments(body.get('attachments'))
            except ValueError as exc:
                return JsonResponse({'error': str(exc)}, status=400)
            apply_changes = body.get('apply_changes')
            explicit_chat_mode = _normalize_chat_mode(body.get('mode'))
            session_id = str(body.get('session_id') or '').strip() or str(uuid.uuid4())
            if not content and not attachments:
                return JsonResponse({'error': 'Message or image attachment is required'}, status=400)
            request_text = _chat_request_text(content, attachments)

            # --- Auto-detect relevant global skills ---
            pinned_skill_slugs = [str(s) for s in (body.get('active_skills') or []) if s]
            workspace_path = None
            if project.workspace_id:
                try:
                    workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
                except Exception:
                    workspace_path = None
            elif project.local_path:
                local_candidate = Path(str(project.local_path))
                workspace_path = local_candidate if local_candidate.exists() else None
            skill_activation = {
                'effective_request_text': request_text,
                'skill_instructions': '',
                'active_skill_names': [],
            }
            effective_request_text = request_text
            skill_instructions = ''
            active_skill_names = []
            try:
                skill_activation = resolve_skill_activation(
                    request_text,
                    workspace_path=workspace_path,
                    pinned_global_skill_slugs=pinned_skill_slugs,
                )
                effective_request_text = str(skill_activation.get('effective_request_text') or request_text).strip()
                skill_instructions = str(skill_activation.get('skill_instructions') or '')
                active_skill_names = list(skill_activation.get('active_skill_names') or [])
            except Exception:
                logger.debug("Skill detection failed — continuing without skills", exc_info=True)
                skill_instructions = ''
                active_skill_names = []

            user_trace = {
                'context_mentions': _dedupe_chat_mentions(
                    _normalize_chat_mentions(context_mentions),
                    _infer_inline_chat_mentions(content),
                ),
                'selected_file': selected_file or None,
                'session_id': session_id,
                'chat_mode': explicit_chat_mode or 'auto',
                'attachments': attachments,
            }
            ChatMessage.objects.create(project=project, role='user', content=content, metadata=user_trace)

            command_response = str(skill_activation.get('command_response') or '').strip()
            if command_response:
                assistant_trace = {
                    'approach': 'Handled the request through the workspace skill command router.',
                    'chat_state': CHAT_STATE_GROUNDED_ANSWER,
                    'chat_mode': explicit_chat_mode or CHAT_MODE_ASK,
                    'state_reason': 'Recognized a slash skill command before invoking the coding pipeline.',
                    'session_id': session_id,
                    'context_mentions': user_trace['context_mentions'],
                    'context_sources': [{'label': '@skills', 'detail': 'Returned skill usage guidance or the current skill catalog.'}],
                    'files_accessed': [],
                    'commands_ran': [],
                    'active_skills': active_skill_names,
                }
                assistant_metadata = dict(assistant_trace)
                assistant_metadata['session_id'] = session_id
                ChatMessage.objects.create(project=project, role='assistant', content=command_response, metadata=assistant_metadata)
                _, sessions = _group_project_chat_sessions(project)
                return JsonResponse({
                    'user_message': content,
                    'assistant_message': command_response,
                    'applied_changes': None,
                    'workspace_actions': [],
                    'trace': assistant_trace,
                    'session_id': session_id,
                    'sessions': sessions,
                    'active_skills': active_skill_names,
                })

            should_apply_changes = _should_apply_changes_for_chat_mode(explicit_chat_mode, effective_request_text, apply_changes)
            applied_changes = None
            assistant_trace = {}
            workspace_actions = []
            chat_checkpoint = None
            memory_context = build_memory_context(project, effective_request_text, selected_file=selected_file)
            resolved_context_text, context_trace = _resolve_chat_context(
                project,
                effective_request_text,
                selected_file=selected_file,
                selected_content=selected_content,
                context_mentions=context_mentions,
                session_id=session_id,
            )
            chat_decision = _classify_chat_state(
                project,
                effective_request_text,
                selected_file,
                context_mentions,
                context_trace,
                should_apply_changes,
            )
            chat_state = str(chat_decision.get('state') or CHAT_STATE_GROUNDED_ANSWER)
            if explicit_chat_mode == CHAT_MODE_EDIT:
                chat_state = CHAT_STATE_EDIT_REQUEST
                chat_decision = {
                    'state': CHAT_STATE_EDIT_REQUEST,
                    'reason': 'Explicit edit mode was selected.',
                    'response_contract': (
                        "Apply the requested change directly to the codebase and summarize which files changed."
                    ),
                }
            elif explicit_chat_mode == CHAT_MODE_AGENT:
                if should_apply_changes and project.workspace_id:
                    workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
                    chat_checkpoint = create_workspace_checkpoint(
                        str(project.id),
                        workspace_path,
                        label=(content or request_text)[:160],
                        source='chat_agent',
                    )
                agent_result = _handle_agent_chat_request(
                    project,
                    effective_request_text,
                    selected_file=selected_file,
                    selected_content=selected_content,
                    attachments=attachments,
                    session_id=session_id,
                    should_apply_changes=should_apply_changes,
                    context_trace=context_trace,
                    memory_context=memory_context,
                    checkpoint=chat_checkpoint,
                    skill_instructions=skill_instructions,
                    skill_activation=skill_activation,
                )
                if agent_result.get('handled'):
                    applied_changes = agent_result.get('applied_changes')
                    workspace_actions = list(agent_result.get('workspace_actions') or [])
                    ai_response = str(agent_result.get('assistant_message') or '')
                    assistant_trace = dict(agent_result.get('assistant_trace') or {})
                    assistant_trace['session_id'] = session_id
                    assistant_trace['chat_mode'] = CHAT_MODE_AGENT
                    assistant_trace.setdefault('active_skills', active_skill_names)
                    if workspace_actions:
                        assistant_trace['workspace_actions'] = workspace_actions

                    try:
                        assistant_metadata = dict(assistant_trace or {})
                        assistant_metadata['session_id'] = session_id
                        ChatMessage.objects.create(project=project, role='assistant', content=ai_response, metadata=assistant_metadata)
                    except Exception:
                        logger.exception("Failed to persist assistant chat message for project %s", project.id)
                    _, sessions = _group_project_chat_sessions(project)
                    return JsonResponse({
                        'user_message': content,
                        'assistant_message': ai_response,
                        'applied_changes': applied_changes,
                        'workspace_actions': workspace_actions,
                        'trace': assistant_trace,
                        'session_id': session_id,
                        'sessions': sessions,
                        'active_skills': active_skill_names,
                    })

            if chat_state == CHAT_STATE_EDIT_REQUEST and project.workspace_id:
                if should_apply_changes and not chat_checkpoint:
                    workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
                    chat_checkpoint = create_workspace_checkpoint(
                        str(project.id),
                        workspace_path,
                        label=(content or request_text)[:160],
                        source='chat_edit',
                    )
                try:
                    applied_changes = apply_chat_changes(
                        project,
                        effective_request_text,
                        selected_file=selected_file,
                        selected_content=selected_content,
                        request_attachments=attachments,
                        checkpoint=chat_checkpoint,
                        chat_mode=explicit_chat_mode or CHAT_MODE_EDIT,
                        changeset_source='chat',
                        skill_activation=skill_activation,
                    )
                    applied_list = applied_changes['applied_files']
                    ai_response = (
                        "Applied the requested update directly to the project."
                        if not applied_list
                        else f"Applied the requested update to {len(applied_list)} file(s): {', '.join(applied_list)}."
                    )
                    assistant_trace = _build_chat_trace_from_changes(applied_changes, context_trace, memory_context)
                    assistant_trace['session_id'] = session_id
                    assistant_trace['chat_state'] = chat_state
                    assistant_trace['chat_mode'] = explicit_chat_mode or CHAT_MODE_EDIT
                    assistant_trace['state_reason'] = chat_decision.get('reason')
                except Exception as exc:
                    if chat_checkpoint:
                        delete_workspace_checkpoint(str(project.id), str(chat_checkpoint.get('id') or ''))
                        chat_checkpoint = None
                    logger.exception("Chat code application failed for project %s", project.id)
                    ai_response = f"I understood this as a code-change request, but the edit failed: {str(exc)}"
                    assistant_trace = {
                        'approach': context_trace.get('approach') or 'Tried to apply a code change request.',
                        'chat_state': chat_state,
                        'chat_mode': explicit_chat_mode or CHAT_MODE_EDIT,
                        'state_reason': chat_decision.get('reason'),
                        'session_id': session_id,
                        'context_mentions': context_trace.get('context_mentions') or [],
                        'context_sources': context_trace.get('context_sources') or [],
                        'files_accessed': context_trace.get('files_accessed') or [],
                        'commands_ran': [],
                        'applied_files': [],
                        'error': str(exc),
                    }
            else:
                try:
                    if chat_state == CHAT_STATE_NEEDS_CLARIFICATION and chat_decision.get('response'):
                        ai_response = str(chat_decision.get('response') or '')
                        assistant_trace = {
                            'approach': 'Paused for human clarification because the requested UI surface was ambiguous.',
                            'chat_state': chat_state,
                            'chat_mode': explicit_chat_mode or CHAT_MODE_ASK,
                            'state_reason': chat_decision.get('reason'),
                            'session_id': session_id,
                            'context_mentions': context_trace.get('context_mentions') or [],
                            'context_sources': list(context_trace.get('context_sources') or []) + [
                                {'label': '@clarification-needed', 'detail': 'Asked the user to clarify which UI surface they want to change before suggesting edits.'}
                            ],
                            'files_accessed': context_trace.get('files_accessed') or [],
                            'commands_ran': [],
                            'awaiting_clarification': True,
                            'semantic_hits': [
                                {
                                    'path': item.get('file_path'),
                                    'symbol': item.get('symbol'),
                                }
                                for item in (memory_context.get('semantic_hits') or [])[:8]
                            ],
                        }
                    elif chat_state == CHAT_STATE_GROUNDED_ANSWER and chat_decision.get('mode') == 'deterministic_ui_style' and chat_decision.get('response'):
                        ai_response = str(chat_decision.get('response') or '')
                        assistant_trace = {
                            'approach': 'Answered directly from deterministic UI style evidence extracted from retrieved files.',
                            'chat_state': chat_state,
                            'chat_mode': explicit_chat_mode or CHAT_MODE_ASK,
                            'state_reason': chat_decision.get('reason'),
                            'session_id': session_id,
                            'context_mentions': context_trace.get('context_mentions') or [],
                            'context_sources': list(context_trace.get('context_sources') or []) + [
                                {'label': '@ui-style-evidence', 'detail': 'Extracted exact class strings for the requested UI styling question.'}
                            ],
                            'files_accessed': context_trace.get('files_accessed') or [],
                            'commands_ran': [],
                            'semantic_hits': [
                                {
                                    'path': item.get('file_path'),
                                    'symbol': item.get('symbol'),
                                }
                                for item in (memory_context.get('semantic_hits') or [])[:8]
                            ],
                        }
                    else:
                        from agents.core.base import BaseAgent

                        system_instruction, prompt = _build_chat_llm_prompt(
                            project,
                            effective_request_text,
                            attachments,
                            selected_file,
                            selected_content,
                            session_id,
                            context_trace,
                            memory_context,
                            resolved_context_text,
                            explicit_chat_mode,
                            chat_state,
                            str(chat_decision.get('response_contract') or ''),
                            skill_instructions=skill_instructions,
                        )
                        agent = BaseAgent(
                            role="DevHub AI Assistant",
                            system_instruction=system_instruction,
                            ai_config=_project_ai_config(project),
                        )
                        ai_response = agent.generate_with_attachments(prompt, attachments) if attachments else agent.generate(prompt)
                        assistant_trace = {
                            'approach': context_trace.get('approach') or 'Answered the question using project memory, semantic recall, and explicit workspace context.',
                            'chat_state': chat_state,
                            'chat_mode': explicit_chat_mode or CHAT_MODE_ASK,
                            'state_reason': chat_decision.get('reason'),
                            'session_id': session_id,
                            'context_mentions': context_trace.get('context_mentions') or [],
                            'context_sources': context_trace.get('context_sources') or [],
                            'files_accessed': context_trace.get('files_accessed') or [],
                            'commands_ran': [],
                            'active_skills': active_skill_names,
                            'semantic_hits': [
                                {
                                    'path': item.get('file_path'),
                                    'symbol': item.get('symbol'),
                                }
                                for item in (memory_context.get('semantic_hits') or [])[:8]
                            ],
                        }
                except Exception as exc:
                    logger.exception("Chat assistant response failed for project %s", project.id)
                    ai_response = f"AI agent unavailable ({str(exc)}). Check the configured DevHub AI provider settings to enable chat."
                    assistant_trace = {
                        'approach': context_trace.get('approach') or 'Tried to answer using workspace context.',
                        'chat_state': chat_state,
                        'chat_mode': explicit_chat_mode or CHAT_MODE_ASK,
                        'state_reason': chat_decision.get('reason'),
                        'session_id': session_id,
                        'context_mentions': context_trace.get('context_mentions') or [],
                        'context_sources': context_trace.get('context_sources') or [],
                        'files_accessed': context_trace.get('files_accessed') or [],
                        'commands_ran': [],
                        'error': str(exc),
                    }

            try:
                assistant_metadata = dict(assistant_trace or {})
                assistant_metadata['session_id'] = session_id
                ChatMessage.objects.create(project=project, role='assistant', content=ai_response, metadata=assistant_metadata)
            except Exception:
                logger.exception("Failed to persist assistant chat message for project %s", project.id)
            _, sessions = _group_project_chat_sessions(project)
            return JsonResponse({
                'user_message': content,
                'assistant_message': ai_response,
                'applied_changes': applied_changes,
                'workspace_actions': workspace_actions,
                'trace': assistant_trace,
                'session_id': session_id,
                'sessions': sessions,
                'active_skills': active_skill_names,
            })
        except Exception as exc:
            if chat_checkpoint:
                delete_workspace_checkpoint(str(project.id), str(chat_checkpoint.get('id') or ''))
            logger.exception("Unhandled project_chat failure for project %s", project.id)
            fallback = f"Chat request failed unexpectedly: {str(exc)}"
            if content:
                try:
                    ChatMessage.objects.create(project=project, role='assistant', content=fallback, metadata={'error': str(exc), 'session_id': session_id or LEGACY_CHAT_SESSION_ID})
                except Exception:
                    logger.exception("Failed to persist fallback assistant message for project %s", project.id)
            return JsonResponse({
                'user_message': content,
                'assistant_message': fallback,
                'applied_changes': None,
                'trace': {'error': str(exc), 'session_id': session_id or None},
                'session_id': session_id or None,
            })

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def project_chat_undo(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValidationError, ValueError):
        return JsonResponse({'error': 'Project not found'}, status=404)

    if not project.workspace_id:
        return JsonResponse({'error': 'Project has no active workspace'}, status=400)

    checkpoint_to_cleanup = None
    try:
        body = _parse_json_body(request)
        session_id = str(body.get('session_id') or '').strip() or str(uuid.uuid4())
        changeset_id = str(body.get('changeset_id') or '').strip()
        if not changeset_id:
            return JsonResponse({'error': 'changeset_id is required'}, status=400)

        target_changeset = _changeset_by_id(project, changeset_id)
        if not target_changeset:
            return JsonResponse({'error': 'Changeset not found'}, status=404)

        target_source = str((target_changeset.ai_review or {}).get('source') or '')
        if not target_source.startswith('chat'):
            return JsonResponse({'error': 'Only chat-driven changes can be undone from workspace chat.'}, status=400)

        undo_payload = _chat_undo_payload_from_review(str(target_changeset.id), target_changeset.ai_review)
        if not undo_payload or not undo_payload.get('checkpoint_id'):
            return JsonResponse({'error': 'This changeset does not have a stored checkpoint.'}, status=400)
        if not undo_payload.get('available'):
            return JsonResponse({'error': 'Undo is no longer available for this changeset.'}, status=400)

        workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
        checkpoint_to_cleanup = create_workspace_checkpoint(
            str(project.id),
            workspace_path,
            label=f"Undo restore for {target_changeset.title}"[:160],
            source='chat_undo',
        )
        restore_result = restore_workspace_checkpoint(
            str(project.id),
            workspace_path,
            str(undo_payload.get('checkpoint_id') or ''),
        )
        restored_files = list(restore_result.get('restored_files') or [])

        workspace_actions = [
            {
                'type': 'undo_restore',
                'status': 'completed',
                'detail': (
                    'Restored the workspace to the checkpoint captured before the selected chat execution.'
                    if restored_files
                    else 'The workspace already matched the selected checkpoint.'
                ),
            }
        ]

        if restored_files:
            undo_changeset = _record_chat_changes(
                project,
                f"Undo chat execution: {target_changeset.title}",
                workspace_path,
                snapshot_previous_contents(str(project.id), str(checkpoint_to_cleanup.get('id') or ''), restored_files),
                restored_files,
                ai_review=_chat_checkpoint_review_payload(
                    checkpoint_to_cleanup,
                    source='chat_undo',
                    chat_mode=str((target_changeset.ai_review or {}).get('chat_mode') or CHAT_MODE_EDIT),
                    undo_label='Undo Restore',
                ),
            )
            _mark_changeset_undone(target_changeset, undo_changeset)
            _update_project_memory(project, workspace_path, f"Undo chat execution: {target_changeset.title}", restored_files, ['Restored the workspace to the pre-change checkpoint.'])
            index_semantic_memory(project, workspace_path, changed_paths=restored_files)
            record_episode(
                project=project,
                memory_type='implementation',
                title='Undo workspace chat execution',
                summary=f"Restored the workspace to the checkpoint for '{target_changeset.title}'. Files: {', '.join(restored_files)}.",
                related_files=restored_files,
                metadata={'source': 'chat_undo', 'target_changeset_id': str(target_changeset.id)},
            )
            upsert_working_memory(
                project,
                'implementation',
                (
                    f"Latest implementation request: Undo chat execution: {target_changeset.title}\n"
                    f"Files touched: {', '.join(restored_files)}\n"
                    "Validation summary:\nRestored from a stored workspace checkpoint.\n"
                    "Reviewer summary: Undo completed successfully."
                ),
                {'latest_request': f"Undo chat execution: {target_changeset.title}", 'files': restored_files, 'source': 'chat_undo'},
            )
            applied_changes = {
                'applied_files': restored_files,
                'count': len(restored_files),
                'changeset_id': str(undo_changeset.id) if undo_changeset else None,
                'undo': _chat_changeset_trace_metadata(undo_changeset).get('undo') if undo_changeset else None,
            }
            assistant_trace = {
                'approach': 'Restored the workspace to the checkpoint captured immediately before the selected chat execution.',
                'chat_state': 'undo_restore',
                'chat_mode': str((target_changeset.ai_review or {}).get('chat_mode') or CHAT_MODE_EDIT),
                'state_reason': 'Undo restored the workspace from the pre-change checkpoint.',
                'session_id': session_id,
                'context_mentions': [],
                'context_sources': [],
                'files_accessed': [{'path': item, 'reason': 'Restored from checkpoint'} for item in restored_files[:12]],
                'commands_ran': [],
                'workspace_actions': workspace_actions,
                'applied_files': restored_files,
            }
            if undo_changeset:
                assistant_trace.update(_chat_changeset_trace_metadata(undo_changeset))
            assistant_message = (
                f"Restored the workspace to the checkpoint before that chat change, reverting {len(restored_files)} file(s): "
                f"{', '.join(restored_files[:6])}."
            )
        else:
            _mark_changeset_undone(target_changeset, None)
            delete_workspace_checkpoint(str(project.id), str(checkpoint_to_cleanup.get('id') or ''))
            checkpoint_to_cleanup = None
            applied_changes = None
            assistant_trace = {
                'approach': 'Compared the current workspace against the stored pre-change checkpoint and found no differences to restore.',
                'chat_state': 'undo_restore',
                'chat_mode': str((target_changeset.ai_review or {}).get('chat_mode') or CHAT_MODE_EDIT),
                'state_reason': 'Undo checkpoint matched the current workspace already.',
                'session_id': session_id,
                'context_mentions': [],
                'context_sources': [],
                'files_accessed': [],
                'commands_ran': [],
                'workspace_actions': workspace_actions,
                'applied_files': [],
            }
            assistant_message = 'The workspace already matches that checkpoint, so there was nothing to restore.'

        assistant_metadata = dict(assistant_trace or {})
        assistant_metadata['session_id'] = session_id
        ChatMessage.objects.create(project=project, role='assistant', content=assistant_message, metadata=assistant_metadata)
        _, sessions = _group_project_chat_sessions(project)
        return JsonResponse({
            'assistant_message': assistant_message,
            'applied_changes': applied_changes,
            'workspace_actions': workspace_actions,
            'trace': assistant_trace,
            'session_id': session_id,
            'sessions': sessions,
        })
    except Exception as exc:
        if checkpoint_to_cleanup:
            delete_workspace_checkpoint(str(project.id), str(checkpoint_to_cleanup.get('id') or ''))
        logger.exception("Chat undo failed for project %s", project.id)
        return JsonResponse({'error': str(exc)}, status=500)


