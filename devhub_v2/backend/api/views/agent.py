import logging

from django.db import close_old_connections
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from agents.memory.store import build_blueprint_context
from core.models import AgentRun, Project

from api.blueprint.builders import _enrich_blueprint_document
from api.blueprint.generator import generate_blueprint_sync
from api.workspace.memory import (
    BLUEPRINT_SECTION_FIELDS,
    BLUEPRINT_SECTION_LABELS,
    TOKEN_FREE_BLUEPRINT_SECTION_KEYS,
    _persist_blueprint_state,
    _read_deep_docs_progress,
    _render_project_features_summary,
    _safe_write_deep_docs_progress,
    _slice_blueprint_section,
)
from api.chat.helpers import _parse_json_body
from api.project_utils import _project_ai_config

logger = logging.getLogger(__name__)

@csrf_exempt
def start_agent(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
        body = _parse_json_body(request)
        agent_type = body.get('agent_type', 'architect')

        agent_run = AgentRun.objects.create(project=project, agent_type=agent_type, status='running', logs=[{'step': 'started', 'message': f'{agent_type} agent initiated'}])

        if agent_type == 'architect':
            generate_blueprint_sync(project)
            agent_run.status = 'completed'
            agent_run.logs.append({'step': 'completed', 'message': 'Blueprint generated successfully'})
        elif agent_type == 'documentation':
            documentation_run = generate_codebase_reference_sync(project)
            if documentation_run.status == 'failed':
                agent_run.status = 'failed'
                agent_run.logs.append({'step': 'failed', 'message': documentation_run.error or 'Documentation generation failed'})
            else:
                agent_run.status = 'completed'
                agent_run.logs.append({'step': 'completed', 'message': 'Documentation generated successfully'})
        else:
            agent_run.status = 'completed'
            agent_run.logs.append({'step': 'completed', 'message': f'{agent_type} agent finished'})

        agent_run.save()

        return JsonResponse({'id': str(agent_run.id), 'agent_type': agent_run.agent_type, 'status': agent_run.status, 'logs': agent_run.logs})
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def deep_documentation_progress(request, project_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)

    workspace_path = Path(project.local_path) if project.local_path else None
    if not workspace_path or not workspace_path.is_dir():
        return JsonResponse({'error': 'Project has no valid workspace path'}, status=400)

    payload = _read_deep_docs_progress(workspace_path) or {
        'section_key': 'idle',
        'section_label': 'Idle',
        'status': 'idle',
        'progress_pct': 0,
        'total_sections': 7,
        'completed_sections': 0,
        'section_data': {},
    }
    return JsonResponse(payload)


@csrf_exempt
def deep_documentation_stream(request, project_id):
    """SSE endpoint that generates either the full Blueprint or one requested section."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)

    from django.http import StreamingHttpResponse
    from agents.docs.deep_documentation import DeepDocumentationAgent

    workspace_path = Path(project.local_path) if project.local_path else None
    if not workspace_path or not workspace_path.is_dir():
        return JsonResponse({'error': 'Project has no valid workspace path'}, status=400)

    body = _parse_json_body(request)
    requested_section = str(body.get('section_key') or '').strip().lower()
    if requested_section and requested_section not in BLUEPRINT_SECTION_FIELDS:
        return JsonResponse({'error': f'Unsupported Blueprint section: {requested_section}'}, status=400)

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def event_stream():
        total_sections = 1 if requested_section else 7
        completion_label = (
            f"{BLUEPRINT_SECTION_LABELS.get(requested_section, requested_section)} complete"
            if requested_section
            else 'Blueprint complete'
        )
        initial_event = {
            'section_key': 'build_context',
            'section_label': 'Preparing codebase context',
            'status': 'started',
            'progress_pct': 0,
            'total_sections': total_sections,
            'completed_sections': 0,
            'section_data': {},
        }
        _safe_write_deep_docs_progress(workspace_path, initial_event)
        yield _sse(initial_event)

        try:
            codebase_context = build_blueprint_context(project, workspace_path, force=True)
        except Exception as exc:
            logger.exception("Failed to build blueprint context for project %s", project_id)
            failure_event = {
                'section_key': 'build_context',
                'section_label': 'Preparing codebase context',
                'status': 'failed',
                'progress_pct': 0,
                'total_sections': total_sections,
                'completed_sections': 0,
                'section_data': {'_error': str(exc)},
                'error': str(exc),
            }
            _safe_write_deep_docs_progress(workspace_path, failure_event)
            yield _sse(failure_event)
            return

        if not codebase_context:
            message = 'Could not build codebase context. Ensure the project has indexed files.'
            failure_event = {
                'section_key': 'build_context',
                'section_label': 'Preparing codebase context',
                'status': 'failed',
                'progress_pct': 0,
                'total_sections': total_sections,
                'completed_sections': 0,
                'section_data': {'_error': message},
                'error': message,
            }
            _safe_write_deep_docs_progress(workspace_path, failure_event)
            yield _sse(failure_event)
            return

        context_ready_event = {
            'section_key': 'build_context',
            'section_label': 'Codebase context ready',
            'status': 'completed',
            'progress_pct': 1,
            'total_sections': total_sections,
            'completed_sections': 0,
            'section_data': {},
        }
        _safe_write_deep_docs_progress(workspace_path, context_ready_event)
        yield _sse(context_ready_event)

        import queue as _queue_mod
        from agents.core.observability import AgentObserver
        _live_queue: _queue_mod.Queue = _queue_mod.Queue()
        observer = AgentObserver(str(project_id), live_queue=_live_queue)
        agent = DeepDocumentationAgent(ai_config=_project_ai_config(project), observer=observer)
        feature_summary = _render_project_features_summary(project, limit=20)

        def _persist_section_update(section_key: str, section_data: dict[str, Any]) -> dict[str, Any]:
            close_old_connections()
            project.refresh_from_db()
            current_bp = dict(project.blueprint or {})
            for key, value in section_data.items():
                if key != '_error':
                    current_bp[key] = value
            refreshed = _enrich_blueprint_document(project, current_bp, codebase_context, feature_summary)
            if isinstance(refreshed, dict):
                refreshed["_meta"] = {
                    "codebase_fingerprint": codebase_context.get("fingerprint") if isinstance(codebase_context, dict) else None,
                    "indexed_files": codebase_context.get("file_count") if isinstance(codebase_context, dict) else None,
                    "cached": True if codebase_context else False,
                }
            _persist_blueprint_state(project, refreshed)
            if section_key in BLUEPRINT_SECTION_FIELDS:
                return _slice_blueprint_section(refreshed, section_key)
            return dict(section_data or {})

        if requested_section:
            started_event = {
                'section_key': requested_section,
                'section_label': BLUEPRINT_SECTION_LABELS.get(requested_section, requested_section),
                'section_data': {},
                'progress_pct': 5,
                'status': 'started',
                'total_sections': total_sections,
                'completed_sections': 0,
            }
            _safe_write_deep_docs_progress(workspace_path, started_event)
            yield _sse(started_event)

            try:
                project.refresh_from_db()
                current_bp = dict(project.blueprint or {})
                if requested_section in TOKEN_FREE_BLUEPRINT_SECTION_KEYS:
                    refreshed = _enrich_blueprint_document(project, current_bp, codebase_context, feature_summary)
                    if isinstance(refreshed, dict):
                        refreshed["_meta"] = {
                            "codebase_fingerprint": codebase_context.get("fingerprint") if isinstance(codebase_context, dict) else None,
                            "indexed_files": codebase_context.get("file_count") if isinstance(codebase_context, dict) else None,
                            "cached": True if codebase_context else False,
                        }
                    _persist_blueprint_state(project, refreshed)
                    section_data = _slice_blueprint_section(refreshed, requested_section)
                else:
                    section_data = agent.generate_section(
                        requested_section,
                        project.name,
                        codebase_context,
                        workspace_path,
                        existing_blueprint=current_bp,
                    )
                    section_data = _persist_section_update(requested_section, section_data)
            except Exception as exc:
                logger.exception("Failed to generate section %s for project %s", requested_section, project_id)
                failed_event = {
                    'section_key': requested_section,
                    'section_label': BLUEPRINT_SECTION_LABELS.get(requested_section, requested_section),
                    'section_data': {'_error': str(exc)},
                    'progress_pct': 100,
                    'status': 'failed',
                    'total_sections': total_sections,
                    'completed_sections': 1,
                    'error': str(exc),
                }
                _safe_write_deep_docs_progress(workspace_path, failed_event)
                yield _sse(failed_event)
                return

            completed_event = {
                'section_key': requested_section,
                'section_label': BLUEPRINT_SECTION_LABELS.get(requested_section, requested_section),
                'section_data': section_data,
                'progress_pct': 100,
                'status': 'completed',
                'total_sections': total_sections,
                'completed_sections': 1,
            }
            _safe_write_deep_docs_progress(workspace_path, completed_event)
            yield _sse(completed_event)
        else:
            import concurrent.futures as _cf
            import queue as _queue
            from agents.docs.deep_documentation import SECTION_ORDER as _SECTION_ORDER, SECTION_LABELS as _SECTION_LABELS

            _existing_bp = dict(project.blueprint or {})
            _results: dict[str, dict] = {}
            _result_q: _queue.Queue = _queue.Queue()
            _total = len(_SECTION_ORDER)

            def _run_one(sk: str, idx: int):
                try:
                    data = agent.generate_section(
                        sk, project.name, codebase_context, workspace_path, existing_blueprint=_existing_bp
                    )
                    if isinstance(data, dict) and data.get('_error'):
                        status = 'failed'
                    else:
                        data = agent._run_validators(sk, data, workspace_path, cache=codebase_context)
                        status = 'completed'
                except Exception as exc:
                    data = {'_error': str(exc)}
                    status = 'failed'
                _result_q.put({
                    'section_key': sk,
                    'section_label': _SECTION_LABELS.get(sk, sk),
                    'section_data': data,
                    'progress_pct': int(((idx + 1) / _total) * 100),
                    'status': status,
                    'total_sections': _total,
                    'agent_events': agent.observer.events_for_section(sk) if agent.observer else [],
                })

            # Emit started events for all sections first
            for idx, sk in enumerate(_SECTION_ORDER):
                started_evt = {
                    'section_key': sk, 'section_label': _SECTION_LABELS.get(sk, sk),
                    'section_data': {}, 'progress_pct': int((idx / _total) * 100),
                    'status': 'started', 'total_sections': _total, 'completed_sections': idx,
                }
                yield _sse(started_evt)

            with _cf.ThreadPoolExecutor(max_workers=min(len(_SECTION_ORDER), 4)) as pool:
                futs = [pool.submit(_run_one, sk, idx) for idx, sk in enumerate(_SECTION_ORDER)]
                completed_count = 0
                while completed_count < len(futs):
                    # Drain live observer events first — stream them immediately to the client
                    while True:
                        try:
                            live_evt = _live_queue.get_nowait()
                            yield _sse({'type': 'agent_event', 'event': live_evt})
                        except _queue.Empty:
                            break

                    # Check for a completed section (short timeout to keep live events flowing)
                    try:
                        event = _result_q.get(timeout=0.3)
                    except _queue.Empty:
                        continue
                    completed_count += 1
                    section_data = dict(event.get('section_data') or {})
                    sk = str(event.get('section_key') or '')
                    if event.get('status') != 'started':
                        try:
                            section_data = _persist_section_update(sk, section_data)
                        except Exception:
                            logger.exception("Failed to persist section %s for project %s", sk, project_id)
                    sse_payload = {
                        'section_key': sk,
                        'section_label': event.get('section_label'),
                        'section_data': section_data,
                        'progress_pct': event.get('progress_pct'),
                        'status': event.get('status'),
                        'total_sections': _total,
                        'completed_sections': completed_count,
                        'agent_events': event.get('agent_events') or [],
                    }
                    _safe_write_deep_docs_progress(workspace_path, sse_payload)
                    yield _sse(sse_payload)

        done_event = {
            'status': 'done',
            'section_key': 'complete',
            'section_label': completion_label,
            'progress_pct': 100,
            'total_sections': total_sections,
            'completed_sections': total_sections,
            'section_data': {},
        }
        _safe_write_deep_docs_progress(workspace_path, done_event)
        yield _sse(done_event)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Access-Control-Allow-Origin'] = '*'
    return response



