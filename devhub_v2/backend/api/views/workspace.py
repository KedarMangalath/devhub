import os
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
        process_id = f"{workspace_id}_{command.split()[0]}"
        sandbox.run_command(process_id, command, str(workspace_path), kind='terminal')
        return JsonResponse({'status': 'success', 'process_id': process_id, 'sandbox': sandbox.details()})
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
            return JsonResponse(_runtime_payload_with_secondary_status(runtime, process_id, sandbox))

        if request.method == 'POST':
            body = _parse_json_body(request)
            command = body.get('command') or detected_runtime.get('run_command')
            if not command:
                return JsonResponse({'error': 'No runtime command detected for this project'}, status=400)
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
            sandbox.run_command(
                process_id,
                command,
                str(workspace_path),
                env=_port_env_from_url(preview_url),
                kind='runtime',
                preview_url=preview_url,
            )
            payload = _runtime_payload_with_secondary_status(detected_runtime, process_id, sandbox, wait_for_preview=True)
            return JsonResponse(payload, status=200)

        if request.method == 'DELETE':
            sandbox.kill_process(process_id)
            for index, _secondary_runtime in enumerate(detected_runtime.get('secondary_runtimes') or []):
                sandbox.kill_process(_secondary_runtime_process_id(workspace_id, index))
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
            return JsonResponse({
                'process_id': process_id,
                'command': runtime.get('setup_command'),
                'status': sandbox.get_status(process_id),
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
