"""
SSE streaming endpoint for agent-mode chat.

Runs the QueryEngine in a background thread and pushes events to the
client in real time: thoughts (narrate tool), tool_start, tool_end,
and a final done event with the assistant response + trace.
"""

import asyncio
import datetime
import json
import logging
import queue
import threading
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from core.models import ChatMessage, Project
from agents.skills.activation import resolve_skill_activation

logger = logging.getLogger(__name__)


class AsyncSseResponse(StreamingHttpResponse):
    """StreamingHttpResponse that properly handles async generators in Django ASGI."""

    async def __aiter__(self):
        async for chunk in self._iterator:
            yield self.make_bytes(chunk)


def _json_default(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _sanitize_for_pg(obj):
    """Strip null bytes (\\u0000) that PostgreSQL rejects in text/JSON fields."""
    if isinstance(obj, str):
        return obj.replace("\x00", "")
    if isinstance(obj, dict):
        return {k: _sanitize_for_pg(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_pg(i) for i in obj]
    return obj


def _args_summary(tool_name: str, args: dict) -> dict:
    """Extract the most relevant arg(s) to show per tool type."""
    if tool_name == "file_read":
        path = args.get("path", "")
        start = args.get("start_line")
        end = args.get("end_line")
        label = path
        if start and end:
            label = f"{path}:{start}-{end}"
        elif start:
            label = f"{path}:{start}"
        return {"path": path, "label": label}
    if tool_name in ("file_edit", "file_write"):
        return {"path": args.get("path", ""), "label": args.get("path", "")}
    if tool_name == "grep":
        pattern = args.get("pattern", "")
        include = args.get("include", "")
        label = f'"{pattern}"'
        if include:
            label += f" in {include}"
        return {"pattern": pattern, "include": include, "label": label}
    if tool_name == "glob":
        pattern = args.get("pattern", "")
        return {"pattern": pattern, "label": pattern}
    if tool_name == "bash":
        cmd = args.get("command", "")
        return {"command": cmd, "label": cmd[:80]}
    if tool_name == "list_dir":
        path = args.get("path", "")
        return {"path": path, "label": path or "."}
    return {"label": str(list(args.values())[0])[:60] if args else ""}


def _run_agent_and_emit(
    *,
    project: Project,
    content: str,
    request_text: str,
    selected_file: str,
    selected_content: str,
    attachments: list,
    session_id: str,
    event_queue: "queue.Queue[dict]",
    skill_activation: dict | None = None,
) -> None:
    """
    Runs in a background thread. Executes the agent loop and pushes
    events to event_queue as they happen. Saves ChatMessage to DB,
    then pushes a 'done' event.
    """
    from agents.core.checkpoints import create_workspace_checkpoint, snapshot_previous_contents
    from agents.implementation.plan import _review_attempt, _run_validation_suite, _validation_summary
    from agents.core.workspace import workspace_manager
    from agents.memory.compaction import ContextCompactor
    from agents.memory.query_engine import QueryEngine
    from agents.memory.store import (
        build_memory_context,
        index_semantic_memory,
        record_episode,
        upsert_working_memory,
    )
    from agents.customization.prompts import PromptBuilder
    from agents.tools.registry import ToolRegistry

    from api.chat.handler import (
        CHAT_MODE_AGENT,
        CHAT_STATE_AGENT_REQUEST,
        _agent_max_turns_for_request,
        _agent_execution_prompt_addendum,
        _agent_project_memory_text,
        _agent_result_summary,
        _chat_workspace_path,
        _group_project_chat_sessions,
        _record_chat_changes,
        _visual_verification_result,
    )
    from api.chat.helpers import (
        _chat_changeset_trace_metadata,
        _chat_checkpoint_review_payload,
        _chat_message_attachments,
        _chat_request_text,
    )
    from api.project_utils import _project_ai_config
    from api.workspace.memory import _read_project_instructions, _update_project_memory

    workspace_path = _chat_workspace_path(project)
    if not project.workspace_id or not workspace_path:
        event_queue.put({
            "type": "done",
            "response": "Agent mode needs a connected workspace before it can edit files.",
            "trace": {"chat_mode": CHAT_MODE_AGENT, "session_id": session_id},
            "session_id": session_id,
        })
        return

    try:
        ai_config = _project_ai_config(project)
        registry = ToolRegistry.default_registry()
        compactor = ContextCompactor()
        prompt_builder = PromptBuilder()

        # Conversation history
        conversation_history = []
        try:
            grouped, _ = _group_project_chat_sessions(project)
            for msg in grouped.get(session_id, [])[-10:]:
                role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "role", "user")
                msg_content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                msg_attachments = _chat_message_attachments(
                    msg if isinstance(msg, dict) else {"metadata": getattr(msg, "metadata", {})}
                )
                gemini_role = "model" if role == "assistant" else "user"
                conversation_history.append({
                    "role": gemini_role,
                    "content": _chat_request_text(str(msg_content), msg_attachments, include_attachment_inventory=True),
                })
        except Exception:
            logger.debug("Could not load chat history for session %s", session_id)

        # Memory + system prompt
        memory_context = build_memory_context(project, request_text, selected_file=selected_file)
        project_memory_text = _agent_project_memory_text(memory_context)
        project_instructions_text = ""
        try:
            project_instructions_text = _read_project_instructions(project, workspace_path)
        except Exception:
            pass

        customization_ctx = ""
        try:
            from agents.customization.project_customization import build_project_customization_summary
            customization_ctx = build_project_customization_summary(workspace_path)
        except Exception:
            pass

        # Skill detection — mirrors what chat.py does for non-streaming mode
        active_skill_names = list((skill_activation or {}).get("active_skill_names") or [])
        skill_instructions = str((skill_activation or {}).get("skill_instructions") or "")
        pinned_skill_slugs = list((skill_activation or {}).get("active_global_skill_slugs") or [])
        try:
            from agents.skills.global_registry import (
                build_skill_injection_prompt,
                detect_skills_for_message,
                get_global_skill,
                list_global_skills,
            )
            all_skills = list_global_skills()
            auto_skills = detect_skills_for_message(request_text, skills=all_skills, top_n=2)
            pinned_skills = [s for slug in (pinned_skill_slugs or []) for s in [get_global_skill(slug)] if s]
            seen = {s["slug"] for s in auto_skills}
            for ps in pinned_skills:
                if ps["slug"] not in seen:
                    auto_skills.append(ps)
                    seen.add(ps["slug"])
            skill_instructions = build_skill_injection_prompt(auto_skills)
            active_skill_names = [s["name"] for s in auto_skills]
        except Exception:
            logger.debug("Skill detection failed in stream path — continuing without skills", exc_info=True)

        project_skill = (skill_activation or {}).get("project_skill") if isinstance(skill_activation, dict) else None
        project_skill_name = str((project_skill or {}).get("name") or "").strip() if isinstance(project_skill, dict) else ""
        if project_skill_name and project_skill_name not in active_skill_names:
            active_skill_names.append(project_skill_name)

        system_prompt = prompt_builder.build_system_prompt(
            workspace_path=workspace_path,
            tools=registry.all_tools(),
            project_memory=project_memory_text,
            project_instructions=project_instructions_text,
            customization_context=customization_ctx,
        )
        system_prompt += "\n\n" + _agent_execution_prompt_addendum(
            should_apply_changes=True,
            selected_file=selected_file,
        )
        if skill_instructions:
            system_prompt += "\n\n" + skill_instructions
        if selected_file:
            file_context = f"\n\n## Active File Context\nThe user has `{selected_file}` open."
            if selected_content:
                file_context += f"\nContent:\n```\n{selected_content[:4000]}\n```"
            system_prompt += file_context

        # Event callbacks — bridge into SSE queue
        tool_events: list[dict] = []

        def on_tool_start(name: str, args: dict) -> None:
            summary = _args_summary(name, args)
            if name == "narrate":
                ev = {"type": "thought", "text": args.get("thought", "")}
            else:
                ev = {"type": "tool_start", "tool": name, "summary": summary}
            tool_events.append({
                "type": "tool_start",
                "tool": name,
                "args_preview": {k: str(v)[:100] for k, v in args.items()},
            })
            event_queue.put(ev)

        def on_tool_end(name: str, result) -> None:
            tool_events.append({
                "type": "tool_end",
                "tool": name,
                "success": result.success,
                "preview": (result.output or "")[:200],
            })
            if name == "narrate":
                return  # thought already emitted in on_tool_start
            ev = {
                "type": "tool_end",
                "tool": name,
                "success": result.success,
                "preview": (result.output or "")[:200],
            }
            event_queue.put(ev)

        engine = QueryEngine(
            tool_registry=registry,
            prompt_builder=prompt_builder,
            compactor=compactor,
            ai_config=ai_config,
            workspace_id=project.workspace_id,
            workspace_path=workspace_path,
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
        )

        prompt_text = _chat_request_text(content, attachments, include_attachment_inventory=True)
        qr = engine.run(
            user_message=prompt_text,
            attachments=attachments,
            conversation_history=conversation_history,
            system_prompt=system_prompt,
            max_turns=_agent_max_turns_for_request(request_text),
        )

        # Build trace + handle changeset
        applied_files = list(qr.files_modified)
        workspace_actions = [
            {
                "type": tc.get("tool", "tool_call"),
                "status": "completed" if tc.get("success") else "failed",
                "command": str(tc.get("args", {}).get("command", ""))[:200]
                if tc.get("tool") == "bash" else "",
                "detail": tc.get("output_preview", "")[:200],
            }
            for tc in qr.tool_calls_log
        ]

        assistant_trace = {
            "approach": f"Agent used {len(qr.tool_calls_log)} tool calls across {qr.turns_used} turns.",
            "chat_state": CHAT_STATE_AGENT_REQUEST,
            "chat_mode": CHAT_MODE_AGENT,
            "state_reason": "Agentic tool-calling loop completed.",
            "session_id": session_id,
            "context_mentions": [],
            "context_sources": [],
            "files_accessed": [{"path": p, "reason": "Read by agent"} for p in qr.files_read[:12]],
            "commands_ran": [
                {
                    "command": tc.get("args", {}).get("command", tc.get("tool", "")),
                    "status": "passed" if tc.get("success") else "failed",
                    "detail": tc.get("output_preview", "")[:200],
                }
                for tc in qr.tool_calls_log if tc.get("tool") == "bash"
            ],
            "workspace_actions": workspace_actions,
            "applied_files": applied_files,
            "tool_events": tool_events[-40:],
            "turns_used": qr.turns_used,
            "compacted": qr.compacted,
            "duration_ms": qr.total_duration_ms,
            "active_skills": active_skill_names,
        }

        applied_changes = None
        chat_checkpoint = None
        validation_results: list[dict] = []
        review_result: dict = {}

        if applied_files:
            try:
                chat_checkpoint = create_workspace_checkpoint(
                    str(project.id),
                    workspace_path,
                    label=content[:160],
                    source="chat_agent",
                )
            except Exception:
                logger.debug("Could not create workspace checkpoint for project %s", project.id)

            previous_contents = snapshot_previous_contents(
                str(project.id),
                str((chat_checkpoint or {}).get("id") or ""),
                applied_files,
            )
            try:
                validation_results = _run_validation_suite(workspace_path, applied_files)
                visual_verification = _visual_verification_result(request_text, applied_files, qr.tool_calls_log)
                if visual_verification:
                    validation_results.append(visual_verification)
                review_result = _review_attempt(
                    project,
                    workspace_path,
                    previous_contents,
                    applied_files,
                    validation_results,
                    request_text=request_text,
                    request_attachments=attachments,
                )
            except Exception:
                logger.exception("Structured validation/review failed for streaming agent execution in project %s", project.id)

            assistant_trace["commands_ran"].extend([
                {
                    "command": result.get("command"),
                    "status": "passed" if result.get("success") else "failed",
                    "detail": str(result.get("stderr") or result.get("stdout") or "")[:280],
                }
                for result in validation_results
                if result.get("command")
            ])
            if review_result:
                assistant_trace["review"] = review_result
            if validation_results and (not all(result.get("success") for result in validation_results) or not review_result.get("approved", True)):
                assistant_trace["state_reason"] = "Agentic tool-calling loop completed, then structured validation/review flagged follow-up issues."

            changeset = _record_chat_changes(
                project,
                content,
                workspace_path,
                previous_contents,
                applied_files,
                ai_review=_chat_checkpoint_review_payload(
                    chat_checkpoint,
                    source="chat_agent",
                    chat_mode=CHAT_MODE_AGENT,
                    undo_label="Undo",
                ),
            )
            if changeset:
                applied_changes = {
                    "applied_files": applied_files,
                    "count": len(applied_files),
                    "changeset_id": str(changeset.id),
                    "undo": _chat_changeset_trace_metadata(changeset).get("undo"),
                    "validation_results": validation_results,
                    "review": review_result,
                }
                assistant_trace.update(_chat_changeset_trace_metadata(changeset))
                try:
                    _update_project_memory(project, workspace_path, content, applied_files, [])
                    index_semantic_memory(project, workspace_path, changed_paths=applied_files)
                    record_episode(
                        project=project,
                        memory_type="implementation",
                        title="Workspace agent execution",
                        summary=f"Agent applied changes for '{request_text[:120]}'. Files: {', '.join(applied_files)}.",
                        related_files=applied_files,
                        metadata={"source": "chat_agent"},
                    )
                    upsert_working_memory(
                        project,
                        "implementation",
                        (
                            f"Latest implementation request: {request_text[:240]}\n"
                            f"Files touched: {', '.join(applied_files)}\n"
                            f"Validation summary:\n{_validation_summary(validation_results)}\n"
                            f"Reviewer summary: {review_result.get('summary', 'No reviewer summary.')}"
                        ),
                        {"latest_request": request_text[:240], "files": applied_files, "source": "chat_agent"},
                    )
                except Exception:
                    logger.exception("Memory update failed for project %s", project.id)

        ai_response = _agent_result_summary(qr, applied_files)

        # Persist assistant message
        try:
            assistant_metadata = dict(assistant_trace)
            assistant_metadata["session_id"] = session_id
            ChatMessage.objects.create(
                project=project,
                role="assistant",
                content=_sanitize_for_pg(ai_response),
                metadata=_sanitize_for_pg(assistant_metadata),
            )
        except Exception:
            logger.exception("Failed to persist assistant message for project %s", project.id)

        from api.chat.handler import _group_project_chat_sessions
        _, sessions = _group_project_chat_sessions(project)

        # Build a plain-text summary of what was done so the Continue button
        # can inject it as context in the next request.
        partial_summary: str | None = None
        if qr.hit_turn_limit:
            done_files = ", ".join(applied_files[:12]) or "none"
            partial_summary = (
                f"The agent reached the turn limit after {qr.turns_used} turns. "
                f"Files modified so far: {done_files}. "
                "The original task may not be fully complete. "
                "Continuing from where it left off."
            )

        event_queue.put({
            "type": "done",
            "response": ai_response,
            "applied_changes": applied_changes,
            "workspace_actions": workspace_actions,
            "trace": assistant_trace,
            "session_id": session_id,
            "sessions": sessions,
            "active_skills": active_skill_names,
            "hit_turn_limit": qr.hit_turn_limit,
            "partial_summary": partial_summary,
        })

    except Exception as exc:
        logger.exception("Agent streaming run failed for project %s", project.id)
        event_queue.put({"type": "error", "error": str(exc)})


@csrf_exempt
def project_chat_agent_stream(request, project_id):
    """POST → SSE stream of agent step events for agent-mode chat."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValidationError, ValueError):
        return JsonResponse({"error": "Project not found"}, status=404)

    from api.chat.handler import (
        CHAT_MODE_AGENT,
        _dedupe_chat_mentions,
        _infer_inline_chat_mentions,
        _normalize_chat_mentions,
    )
    from api.chat.helpers import _normalize_chat_attachments, _parse_json_body, _chat_request_text

    try:
        body = _parse_json_body(request)
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    content = str(body.get("content") or "").strip()
    selected_file = str(body.get("selected_file") or "").strip()
    selected_content = str(body.get("selected_content") or "")
    context_mentions = body.get("context_mentions") or []
    session_id = str(body.get("session_id") or "").strip() or str(uuid.uuid4())
    pinned_skill_slugs = [str(s) for s in (body.get("active_skills") or []) if s]

    try:
        attachments = _normalize_chat_attachments(body.get("attachments"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if not content and not attachments:
        return JsonResponse({"error": "Message or attachment required"}, status=400)

    request_text = _chat_request_text(content, attachments)
    workspace_path = None
    if project.workspace_id:
        try:
            from agents.core.workspace import workspace_manager
            workspace_path = workspace_manager.get_workspace_path(project.workspace_id)
        except Exception:
            workspace_path = None
    elif project.local_path:
        candidate = Path(str(project.local_path))
        workspace_path = candidate if candidate.exists() else None

    skill_activation = {
        "effective_request_text": request_text,
        "skill_instructions": "",
        "active_skill_names": [],
    }
    try:
        skill_activation = resolve_skill_activation(
            request_text,
            workspace_path=workspace_path,
            pinned_global_skill_slugs=pinned_skill_slugs,
        )
    except Exception:
        logger.debug("Skill activation failed for stream request", exc_info=True)

    effective_request_text = str(skill_activation.get("effective_request_text") or request_text).strip()

    # Persist user message immediately
    user_trace = {
        "context_mentions": _dedupe_chat_mentions(
            _normalize_chat_mentions(context_mentions),
            _infer_inline_chat_mentions(content),
        ),
        "selected_file": selected_file or None,
        "session_id": session_id,
        "chat_mode": CHAT_MODE_AGENT,
        "attachments": attachments,
    }
    ChatMessage.objects.create(project=project, role="user", content=content, metadata=user_trace)

    command_response = str(skill_activation.get("command_response") or "").strip()
    if command_response:
        assistant_trace = {
            "approach": "Handled the request through the workspace skill command router.",
            "chat_mode": CHAT_MODE_AGENT,
            "state_reason": "Recognized a slash skill command before invoking the streaming agent.",
            "session_id": session_id,
            "context_mentions": user_trace["context_mentions"],
            "context_sources": [{"label": "@skills", "detail": "Returned skill usage guidance or the current skill catalog."}],
            "files_accessed": [],
            "commands_ran": [],
            "active_skills": list(skill_activation.get("active_skill_names") or []),
        }
        assistant_metadata = dict(assistant_trace)
        assistant_metadata["session_id"] = session_id
        ChatMessage.objects.create(project=project, role="assistant", content=command_response, metadata=assistant_metadata)
        from api.chat.handler import _group_project_chat_sessions
        _, sessions = _group_project_chat_sessions(project)

        def _sse(payload: dict) -> str:
            return f"data: {json.dumps(payload, default=_json_default)}\n\n"

        async def instant_stream():
            yield _sse(
                {
                    "type": "done",
                    "response": command_response,
                    "applied_changes": None,
                    "workspace_actions": [],
                    "trace": assistant_trace,
                    "session_id": session_id,
                    "sessions": sessions,
                    "active_skills": list(skill_activation.get("active_skill_names") or []),
                }
            )

        response = AsyncSseResponse(instant_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    ev_queue: "queue.Queue[dict]" = queue.Queue()

    def run():
        close_old_connections()
        try:
            _run_agent_and_emit(
                project=project,
                content=content,
                request_text=effective_request_text,
                selected_file=selected_file,
                selected_content=selected_content,
                attachments=attachments,
                session_id=session_id,
                event_queue=ev_queue,
                skill_activation=skill_activation,
            )
        except Exception as exc:
            logger.exception("Agent stream thread crashed for project %s", project_id)
            ev_queue.put({"type": "error", "error": str(exc)})

    threading.Thread(target=run, daemon=True).start()

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload, default=_json_default)}\n\n"

    async def stream():
        loop = asyncio.get_event_loop()
        while True:
            try:
                event = await loop.run_in_executor(None, lambda: ev_queue.get(timeout=25))
                yield _sse(event)
                if event.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield _sse({"type": "keepalive"})

    response = AsyncSseResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
