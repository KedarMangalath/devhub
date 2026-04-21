from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from agents.core.workspace import SKIP_DIRS, workspace_manager

from api.chat.helpers import _parse_json_body
from api.workspace.runtime import (
    _runtime_response_payload,
    detect_runtime,
    runtime_process_id,
    setup_process_id,
)

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
        runtime = detect_runtime(workspace_path)
        process_id = runtime_process_id(workspace_id)

        if request.method == 'GET':
            return JsonResponse(_runtime_response_payload(runtime, process_id, sandbox))

        if request.method == 'POST':
            body = _parse_json_body(request)
            command = body.get('command') or runtime.get('run_command')
            if not command:
                return JsonResponse({'error': 'No runtime command detected for this project'}, status=400)
            current_status = sandbox.get_status(process_id)
            if current_status.get('running'):
                command_changed = current_status.get('command') != command
                unhealthy_preview = False
                if runtime.get('preview_url'):
                    healthy, _ = _probe_preview_url(runtime['preview_url'])
                    unhealthy_preview = not healthy
                if command_changed or unhealthy_preview:
                    sandbox.kill_process(process_id)
            sandbox.run_command(
                process_id,
                command,
                str(workspace_path),
                kind='runtime',
                preview_url=runtime.get('preview_url'),
            )
            payload = _runtime_response_payload(runtime, process_id, sandbox, wait_for_preview=True)
            return JsonResponse(payload, status=200)

        if request.method == 'DELETE':
            sandbox.kill_process(process_id)
            return JsonResponse({'status': 'stopped', 'process_id': process_id})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def workspace_setup(request, workspace_id):
    from sandbox.executor import sandbox

    try:
        workspace_path = workspace_manager.get_workspace_path(workspace_id)
        runtime = detect_runtime(workspace_path)
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
