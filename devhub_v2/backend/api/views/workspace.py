import os
import socket
import threading
from pathlib import Path
import time
import uuid
from urllib.parse import urlparse

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from agents.core.workspace import SKIP_DIRS, workspace_manager

from api.chat.helpers import _parse_json_body
from api.workspace.runtime import (
    _probe_preview_url,
    _runtime_response_payload,
    _runtime_with_process_status,
    detect_runtime,
    runtime_process_id,
    setup_process_id,
)


def _port_in_use(port: int) -> bool:
    for host in ("127.0.0.1", "localhost"):
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except OSError:
            pass
    return False


def _kill_process_on_port(port: int) -> None:
    """Kill whatever process is listening on the given port (orphan cleanup)."""
    import subprocess as _sp
    try:
        if os.name == "nt":
            result = _sp.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) > 0:
                        _sp.run(
                            ["powershell", "-Command", f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"],
                            capture_output=True, timeout=5,
                        )
        else:
            _sp.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, timeout=5)
    except Exception:
        pass


def _get_project_blueprint(workspace_id: str) -> dict | None:
    try:
        from core.models import Project  # noqa: PLC0415
        project = Project.objects.filter(workspace_id=workspace_id).first()
        return project.blueprint if project else None
    except Exception:
        return None


def _port_env_from_url(preview_url: str | None) -> dict:
    if not preview_url:
        return {}
    try:
        port = urlparse(preview_url).port
        if not port:
            return {}
        return {
            "PORT": str(port),
            "HOST": "127.0.0.1",
            "BROWSER": "none",
        }
    except Exception:
        return {}

MAX_TEXT_PREVIEW_BYTES = 512 * 1024
RUNTIME_HEAL_STATE_TTL_SECONDS = 15 * 60
RUNTIME_HEAL_EVENT_LIMIT = 80
RUNTIME_HEAL_ACTIVE_STATUSES = {
    'agent_started',
    'agent_running',
    'installing',
    'restarting',
}
_runtime_heal_states: dict[str, dict] = {}
_runtime_heal_lock = threading.Lock()


def _set_runtime_heal_state(workspace_id: str, state: dict | None) -> dict | None:
    if not state:
        return None
    payload = dict(state)
    if isinstance(payload.get('events'), list):
        payload['events'] = [dict(item) for item in payload['events'] if isinstance(item, dict)][-RUNTIME_HEAL_EVENT_LIMIT:]
    if isinstance(payload.get('tool_events'), list):
        payload['tool_events'] = [dict(item) for item in payload['tool_events'] if isinstance(item, dict)][-RUNTIME_HEAL_EVENT_LIMIT:]
    if isinstance(payload.get('files_accessed'), list):
        payload['files_accessed'] = [str(item) for item in payload['files_accessed'] if str(item).strip()]
    payload['updated_at'] = time.time()
    with _runtime_heal_lock:
        _runtime_heal_states[workspace_id] = payload
    return dict(payload)


def _get_runtime_heal_state(workspace_id: str) -> dict | None:
    with _runtime_heal_lock:
        state = _runtime_heal_states.get(workspace_id)
        if not state:
            return None
        status = state.get('status')
        updated_at = float(state.get('updated_at') or 0)
        if status not in RUNTIME_HEAL_ACTIVE_STATUSES and time.time() - updated_at > RUNTIME_HEAL_STATE_TTL_SECONDS:
            _runtime_heal_states.pop(workspace_id, None)
            return None
        return dict(state)


def _clear_runtime_heal_state(workspace_id: str) -> None:
    with _runtime_heal_lock:
        _runtime_heal_states.pop(workspace_id, None)


def _attach_runtime_heal_state(payload: dict, workspace_id: str, heal_info: dict | None = None) -> dict:
    heal_state = heal_info or _get_runtime_heal_state(workspace_id)
    if heal_state:
        payload['heal'] = heal_state
    return payload


NON_TEXT_PREVIEW_EXTENSIONS = {
    '.db', '.sqlite', '.sqlite3',
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.bmp',
    '.pdf', '.zip', '.tar', '.gz', '.rar', '.7z',
    '.exe', '.dll', '.so', '.dylib', '.bin',
    '.pyc', '.pyd',
}


def _file_preview_unavailable(path, reason: str, size: int) -> JsonResponse:
    return JsonResponse({
        'type': 'file',
        'content': f'Preview unavailable: {reason}.',
        'path': str(path),
        'size': size,
        'preview_unavailable': True,
    })


def _secondary_runtime_process_id(workspace_id: str, index: int = 0) -> str:
    return f"{workspace_id}_runtime_secondary_{index}"


def _runtime_payload_with_secondary_status(runtime: dict, process_id: str, sandbox, *, wait_for_preview: bool = False) -> dict:
    payload = _runtime_response_payload(runtime, process_id, sandbox, wait_for_preview=wait_for_preview)
    secondary_statuses = []
    for index, secondary_runtime in enumerate(runtime.get('secondary_runtimes') or []):
        secondary_process_id = _secondary_runtime_process_id(process_id.rsplit('_runtime', 1)[0], index)
        secondary_statuses.append({
            **secondary_runtime,
            'process_id': secondary_process_id,
            'status': sandbox.get_status(secondary_process_id),
        })
    if secondary_statuses:
        payload['secondary_statuses'] = secondary_statuses
    return payload


@csrf_exempt
def workspace_fs(request, workspace_id):
    try:
        workspace_path = workspace_manager.get_workspace_path(workspace_id)
        if request.method == 'GET':
            rel_path = request.GET.get('path', '')
            target_path = workspace_path / rel_path
            target_path.resolve().relative_to(workspace_path.resolve())
            if not target_path.exists():
                return JsonResponse({'error': 'Path not found'}, status=404)
            if target_path.is_file():
                stat = target_path.stat()
                suffix = target_path.suffix.lower()
                if suffix in NON_TEXT_PREVIEW_EXTENSIONS:
                    return _file_preview_unavailable(
                        target_path.name,
                        f'{target_path.name} is not a text file',
                        stat.st_size,
                    )
                if stat.st_size > MAX_TEXT_PREVIEW_BYTES:
                    return _file_preview_unavailable(
                        target_path.name,
                        f'{target_path.name} is too large to preview ({stat.st_size} bytes)',
                        stat.st_size,
                    )
                content = target_path.read_text(encoding='utf-8', errors='replace')
                return JsonResponse({'type': 'file', 'content': content})

            items = []
            for entry in os.scandir(target_path):
                if entry.name in SKIP_DIRS or entry.name == '.env':
                    continue
                items.append({
                    'name': entry.name,
                    'type': 'directory' if entry.is_dir() else 'file',
                    'path': os.path.relpath(entry.path, workspace_path).replace('\\', '/'),
                })
            items.sort(key=lambda item: (item['type'] == 'file', item['name'].lower()))
            return JsonResponse({'type': 'directory', 'items': items})

        if request.method == 'POST':
            body = _parse_json_body(request)
            rel_path = body.get('path')
            content = body.get('content', '')
            if not rel_path:
                return JsonResponse({'error': 'Path is required'}, status=400)
            workspace_manager.write_file(workspace_id, rel_path, content)
            return JsonResponse({'status': 'success'})
    except PermissionError as exc:
        return JsonResponse({'error': str(exc)}, status=403)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def workspace_spawn(request, workspace_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        from sandbox.executor import sandbox

        body = _parse_json_body(request)
        command = body.get('command')
        if not command:
            return JsonResponse({'error': 'Command is required'}, status=400)
        workspace_path = workspace_manager.get_workspace_path(workspace_id)
        requested_process_id = str(body.get('process_id') or '').strip()
        process_id = requested_process_id or f"{workspace_id}_term_{uuid.uuid4().hex[:10]}"
        sandbox.run_command(process_id, command, str(workspace_path), kind='terminal')
        return JsonResponse({
            'status': 'success',
            'process_id': process_id,
            'command': command,
            'sandbox': sandbox.details(),
        })
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def workspace_process_io(request, workspace_id, process_id):
    from sandbox.executor import sandbox

    if request.method == 'GET':
        lines = sandbox.get_output(process_id)
        return JsonResponse({'output': ''.join(lines), 'status': sandbox.get_status(process_id)})

    if request.method == 'POST':
        try:
            body = _parse_json_body(request)
            sandbox.send_input(process_id, body.get('input', ''))
            return JsonResponse({'status': 'success'})
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)

    if request.method == 'DELETE':
        sandbox.kill_process(process_id)
        return JsonResponse({'status': 'killed'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


def _write_setup_marker(runtime_root_str: str | None, workspace_path) -> None:
    """Write .devhub/python-setup-complete into the runtime root (or workspace root as fallback)."""
    from pathlib import Path as _Path
    root = _Path(runtime_root_str) if runtime_root_str else workspace_path
    try:
        marker_dir = root / '.devhub'
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / 'python-setup-complete').write_text('ok', encoding='utf-8')
    except Exception:
        pass


def _run_setup_blocking(sandbox, workspace_id: str, setup_cmd: str, work_dir: str, workspace_path, timeout: int = 600, runtime_root: str | None = None) -> int:
    """Run setup synchronously, stream output into the setup panel, write completion marker on success."""
    import time as _time
    pid = setup_process_id(workspace_id)
    if sandbox.get_status(pid).get('running'):
        sandbox.kill_process(pid)
    sandbox.run_command(pid, setup_cmd, work_dir, kind='setup')
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        if not sandbox.get_status(pid).get('running'):
            break
        _time.sleep(0.5)
    rc = sandbox.get_status(pid).get('returncode')
    if rc == 0:
        _write_setup_marker(runtime_root, workspace_path)
    return rc if rc is not None else -1


def _restart_runtime(sandbox, process_id: str, detected_runtime: dict, workspace_path) -> None:
    command = detected_runtime.get('run_command')
    preview_url = detected_runtime.get('preview_url')
    if command:
        sandbox.kill_process(process_id)
        sandbox.run_command(
            process_id, command, str(workspace_path),
            env=_port_env_from_url(preview_url), kind='runtime', preview_url=preview_url,
        )


def _restart_runtime_and_verify(sandbox, process_id: str, detected_runtime: dict, workspace_path) -> tuple[bool, str | None]:
    _restart_runtime(sandbox, process_id, detected_runtime, workspace_path)
    preview_url = detected_runtime.get('preview_url')
    if preview_url:
        payload = _runtime_response_payload(detected_runtime, process_id, sandbox, wait_for_preview=True)
        if payload.get('status', {}).get('running') and payload.get('ready'):
            return True, None
        return False, payload.get('preview_error') or sandbox.get_recent_output(process_id) or 'Restarted process did not become ready.'

    time.sleep(0.75)
    status = sandbox.get_status(process_id)
    if status.get('running'):
        return True, None
    return False, sandbox.get_recent_output(process_id) or 'Restarted process exited immediately.'


def _runtime_has_startup_failure(current_status: dict, preview_error: str | None, recent_output: str, error_class: str) -> bool:
    if not current_status.get('exists') or not recent_output:
        return False

    if not current_status.get('running'):
        return current_status.get('returncode') not in (0, None) and error_class in {"code", "installable"}

    if not preview_error or error_class not in {"code", "installable"}:
        return False

    fatal_markers = (
        "Traceback (most recent call last):",
        "Exception in thread",
        "ModuleNotFoundError:",
        "ImportError:",
        "AttributeError:",
        "SyntaxError:",
        "NameError:",
    )
    return any(marker in recent_output for marker in fatal_markers)


def _maybe_heal_and_restart(
    sandbox,
    workspace_id: str,
    process_id: str,
    detected_runtime: dict,
    workspace_path,
    current_status: dict,
    preview_error: str | None = None,
) -> dict | None:
    """Route crashed runtime to the right healer:
    - Code-level error (moved imports, API changes) → CoderAgent auto-fix in background
    - Missing installable package → dependency_healer (pip/npm install) + restart
    """
    recent = sandbox.get_recent_output(process_id)
    from api.workspace.runtime_autofix import classify_error, is_autofix_running, run_autofix_background
    error_class = classify_error(recent)
    if not _runtime_has_startup_failure(current_status, preview_error, recent, error_class):
        return None

    existing_heal = _get_runtime_heal_state(workspace_id)
    if existing_heal:
        existing_status = str(existing_heal.get('status') or '')
        updated_at = float(existing_heal.get('updated_at') or 0)
        if existing_status in RUNTIME_HEAL_ACTIVE_STATUSES:
            return existing_heal
        if existing_status in {
            'failed',
            'agent_error',
            'no_files_found',
            'no_changes',
            'rate_limited',
            'restart_failed',
            'heal-rate-limit-exceeded',
        } and time.time() - updated_at < 30:
            return existing_heal

    if error_class == "code":
        if is_autofix_running(workspace_id):
            return _set_runtime_heal_state(workspace_id, {
                "heal_type": "code_fix",
                "status": "agent_running",
                "message": "AI agent is still fixing the runtime error.",
            })

        run_id = f"runtime-heal-{int(time.time() * 1000)}"

        def _on_agent_event(event: dict) -> None:
            current = _get_runtime_heal_state(workspace_id) or {}
            events = list(current.get("events") or [])
            if isinstance(event, dict):
                events.append(dict(event))
            _set_runtime_heal_state(workspace_id, {
                **current,
                "heal_type": "code_fix",
                "run_id": current.get("run_id") or run_id,
                "status": "agent_running",
                "message": "AI fixing runtime code error",
                "events": events,
            })

        def _on_agent_done(result: dict) -> None:
            current = _get_runtime_heal_state(workspace_id) or {}
            heal_result = {
                **current,
                "heal_type": "code_fix",
                "run_id": current.get("run_id") or run_id,
                **(result or {}),
            }
            if not heal_result.get("events"):
                heal_result["events"] = current.get("events") or []
            if not heal_result.get("files_accessed"):
                heal_result["files_accessed"] = current.get("files_accessed") or []
            if not heal_result.get("workspace_actions"):
                heal_result["workspace_actions"] = current.get("workspace_actions") or []
            if not heal_result.get("tool_events"):
                heal_result["tool_events"] = current.get("tool_events") or []
            if heal_result.get("status") == "success" and heal_result.get("files_modified"):
                heal_result["status"] = "restarting"
                _set_runtime_heal_state(workspace_id, heal_result)
                try:
                    restarted, restart_error = _restart_runtime_and_verify(sandbox, process_id, detected_runtime, workspace_path)
                except Exception as exc:
                    heal_result["status"] = "restart_failed"
                    heal_result["error"] = str(exc)
                else:
                    if restarted:
                        heal_result["status"] = "restarted"
                        heal_result["restarted"] = True
                    else:
                        heal_result["status"] = "restart_failed"
                        heal_result["error"] = restart_error or 'Restarted process did not become ready.'
            elif heal_result.get("status") == "success":
                heal_result["status"] = "no_changes"
            elif heal_result.get("error") and not heal_result.get("status"):
                heal_result["status"] = "failed"
            _set_runtime_heal_state(workspace_id, heal_result)

        started = run_autofix_background(
            workspace_id=workspace_id,
            workspace_path=workspace_path,
            error_text=recent,
            runtime_type=detected_runtime.get('runtime_type', 'unknown'),
            on_complete=_on_agent_done,
            on_event=_on_agent_event,
        )
        if started:
            return _set_runtime_heal_state(workspace_id, {
                "heal_type": "code_fix",
                "run_id": run_id,
                "status": "agent_started",
                "message": "AI agent started fixing the runtime error.",
                "events": [
                    {
                        "type": "thought",
                        "text": "Runtime recovery started. Inspecting the crash and preparing a fix.",
                    },
                ],
            })
        return _get_runtime_heal_state(workspace_id) or _set_runtime_heal_state(workspace_id, {
            "heal_type": "code_fix",
            "run_id": run_id,
            "status": "rate_limited",
            "message": "Auto-fix could not start.",
        })

    if error_class == "installable":
        from api.workspace.dependency_healer import try_heal_runtime
        _set_runtime_heal_state(workspace_id, {
            "heal_type": "dependency",
            "status": "installing",
            "message": "Installing a missing runtime dependency.",
        })
        result = try_heal_runtime(
            workspace_id=workspace_id,
            process_id=process_id,
            work_dir=str(workspace_path),
            recent_output=recent,
            runtime_type=detected_runtime.get('runtime_type'),
            runtime_root=detected_runtime.get('runtime_root'),
        )
        if not result:
            return None
        result = {"heal_type": "dependency", **result}
        if result and result.get('healed'):
            result['status'] = 'restarting'
            _set_runtime_heal_state(workspace_id, result)
            try:
                restarted, restart_error = _restart_runtime_and_verify(sandbox, process_id, detected_runtime, workspace_path)
            except Exception as exc:
                result['status'] = 'restart_failed'
                result['error'] = str(exc)
            else:
                if restarted:
                    result['status'] = 'restarted'
                    result['restarted'] = True
                else:
                    result['status'] = 'restart_failed'
                    result['error'] = restart_error or 'Restarted process did not become ready.'
        else:
            result['status'] = result.get('reason') or 'failed'
        return _set_runtime_heal_state(workspace_id, result)

    return None


@csrf_exempt
def workspace_runtime(request, workspace_id):
    from sandbox.executor import sandbox

    try:
        workspace_path = workspace_manager.get_workspace_path(workspace_id)
        blueprint = _get_project_blueprint(workspace_id)
        detected_runtime = detect_runtime(workspace_path, blueprint=blueprint)
        process_id = runtime_process_id(workspace_id)
        current_status = sandbox.get_status(process_id)
        runtime = _runtime_with_process_status(detected_runtime, current_status)

        if request.method == 'GET':
            # If sandbox lost the process (server reload) but the port is still occupied,
            # synthesize a running status so the UI shows the preview rather than "not running".
            if not current_status.get('running'):
                preview_url = detected_runtime.get('preview_url') or ''
                try:
                    port = urlparse(preview_url).port
                except Exception:
                    port = None
                if port and _port_in_use(port):
                    current_status = {
                        'exists': True,
                        'running': True,
                        'command': detected_runtime.get('run_command', ''),
                        'preview_url': preview_url,
                        'backend': 'local',
                        'uptime_seconds': 0,
                        'returncode': None,
                        '_recovered': True,
                    }
                    runtime = _runtime_with_process_status(detected_runtime, current_status)

            heal_info = _maybe_heal_and_restart(
                sandbox, workspace_id, process_id, detected_runtime, workspace_path, current_status,
            )
            payload = _runtime_payload_with_secondary_status(runtime, process_id, sandbox)
            if current_status.get('_recovered'):
                payload['status'] = current_status
                payload['ready'] = True
            return JsonResponse(_attach_runtime_heal_state(payload, workspace_id, heal_info))

        if request.method == 'POST':
            body = _parse_json_body(request)
            command = body.get('command') or detected_runtime.get('run_command')
            if not command:
                return JsonResponse({'error': 'No runtime command detected for this project'}, status=400)

            # Auto-run setup before runtime when deps are missing/incomplete.
            setup_cmd = detected_runtime.get('setup_command')
            if setup_cmd and detected_runtime.get('install_required') and not body.get('skip_setup'):
                rc = _run_setup_blocking(sandbox, workspace_id, setup_cmd, str(workspace_path), workspace_path, runtime_root=detected_runtime.get('runtime_root'))
                if rc != 0:
                    return JsonResponse({
                        'error': 'Dependency installation failed — check the Setup panel for details.',
                        'setup_exit_code': rc,
                        'setup_process_id': setup_process_id(workspace_id),
                    }, status=500)
                detected_runtime = detect_runtime(workspace_path, blueprint=blueprint)
                command = body.get('command') or detected_runtime.get('run_command')

            for index, secondary_runtime in enumerate(detected_runtime.get('secondary_runtimes') or []):
                secondary_command = secondary_runtime.get('run_command')
                if not secondary_command:
                    continue
                secondary_process_id = _secondary_runtime_process_id(workspace_id, index)
                secondary_status = sandbox.get_status(secondary_process_id)
                if secondary_status.get('running') and secondary_status.get('command') != secondary_command:
                    sandbox.kill_process(secondary_process_id)
                    secondary_status = sandbox.get_status(secondary_process_id)
                if not secondary_status.get('running'):
                    sandbox.run_command(
                        secondary_process_id,
                        secondary_command,
                        str(workspace_path),
                        kind='runtime',
                        preview_url=secondary_runtime.get('preview_url'),
                    )
            current_status = sandbox.get_status(process_id)
            if current_status.get('running'):
                command_changed = current_status.get('command') != command
                preview_changed = current_status.get('preview_url') != detected_runtime.get('preview_url')
                unhealthy_preview = False
                if detected_runtime.get('preview_url') and not (command_changed or preview_changed):
                    healthy, _ = _probe_preview_url(detected_runtime['preview_url'])
                    unhealthy_preview = not healthy
                if command_changed or preview_changed or unhealthy_preview:
                    sandbox.kill_process(process_id)
            preview_url = detected_runtime.get('preview_url')
            _clear_runtime_heal_state(workspace_id)
            spawn_env = _port_env_from_url(preview_url)
            django_settings_override = detected_runtime.get('django_settings_override')
            if django_settings_override:
                from api.workspace.runtime import _write_devhub_settings, _django_settings_module  # noqa: PLC0415
                runtime_root_path = Path(detected_runtime['runtime_root']) if detected_runtime.get('runtime_root') else workspace_path
                orig = _django_settings_module(runtime_root_path)
                if orig:
                    _write_devhub_settings(runtime_root_path, orig)
                spawn_env['DJANGO_SETTINGS_MODULE'] = django_settings_override
            sandbox.run_command(
                process_id,
                command,
                str(workspace_path),
                env=spawn_env,
                kind='runtime',
                preview_url=preview_url,
            )
            payload = _runtime_payload_with_secondary_status(detected_runtime, process_id, sandbox, wait_for_preview=True)
            heal_info = _maybe_heal_and_restart(
                sandbox,
                workspace_id,
                process_id,
                detected_runtime,
                workspace_path,
                payload.get('status') or sandbox.get_status(process_id),
                payload.get('preview_error'),
            )
            if heal_info and heal_info.get('restarted'):
                refreshed = _runtime_payload_with_secondary_status(detected_runtime, process_id, sandbox)
                if payload.get('preview_error'):
                    refreshed['preview_error'] = payload.get('preview_error')
                payload = refreshed
            return JsonResponse(_attach_runtime_heal_state(payload, workspace_id, heal_info), status=200)

        if request.method == 'DELETE':
            sandbox.kill_process(process_id)
            for index, _secondary_runtime in enumerate(detected_runtime.get('secondary_runtimes') or []):
                sandbox.kill_process(_secondary_runtime_process_id(workspace_id, index))
            # Kill orphaned processes (sandbox lost handle after reload) by port
            preview_url = detected_runtime.get('preview_url') or ''
            try:
                orphan_port = urlparse(preview_url).port
            except Exception:
                orphan_port = None
            if orphan_port and _port_in_use(orphan_port):
                _kill_process_on_port(orphan_port)
            _clear_runtime_heal_state(workspace_id)
            return JsonResponse({'status': 'stopped', 'process_id': process_id})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def workspace_setup(request, workspace_id):
    from sandbox.executor import sandbox

    try:
        workspace_path = workspace_manager.get_workspace_path(workspace_id)
        blueprint = _get_project_blueprint(workspace_id)
        runtime = detect_runtime(workspace_path, blueprint=blueprint)
        process_id = setup_process_id(workspace_id)

        if request.method == 'GET':
            status = sandbox.get_status(process_id)
            # Write completion marker for the primary runtime root AND all secondary
            # runtime roots (e.g. backend in a fullstack frontend+backend project).
            # Without this, _python_install_required keeps returning True for the backend
            # even after setup completes, because the combined runtime's runtime_root
            # points to the frontend directory.
            if not status.get('running') and status.get('returncode') == 0:
                _write_setup_marker(runtime.get('runtime_root'), workspace_path)
                for secondary in (runtime.get('secondary_runtimes') or []):
                    if isinstance(secondary, dict):
                        _write_setup_marker(secondary.get('runtime_root'), workspace_path)
            return JsonResponse({
                'process_id': process_id,
                'command': runtime.get('setup_command'),
                'status': status,
                'sandbox': sandbox.details(),
            })

        if request.method == 'POST':
            body = _parse_json_body(request)
            command = body.get('command') or runtime.get('setup_command')
            if not command:
                return JsonResponse({'error': 'No setup command detected for this project'}, status=400)
            sandbox.run_command(process_id, command, str(workspace_path), kind='setup')
            return JsonResponse({
                'process_id': process_id,
                'command': command,
                'status': sandbox.get_status(process_id),
                'sandbox': sandbox.details(),
            })

        if request.method == 'DELETE':
            sandbox.kill_process(process_id)
            return JsonResponse({'status': 'stopped', 'process_id': process_id})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)
