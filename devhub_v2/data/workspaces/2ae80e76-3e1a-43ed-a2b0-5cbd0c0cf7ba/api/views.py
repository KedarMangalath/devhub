import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from agents.workspace import workspace_manager
from sandbox.executor import sandbox
from core.models import Project
from django.core.exceptions import ValidationError

@csrf_exempt
def workspace_fs(request, workspace_id):
    """Handles file system operations (list, read, write) within a workspace."""
    try:
        if request.method == 'GET':
            # Path can be a file or a directory
            rel_path = request.GET.get('path', '')
            workspace_path = workspace_manager.get_workspace_path(workspace_id)
            target_path = workspace_path / rel_path
            
            # Security check
            target_path.resolve().relative_to(workspace_path.resolve())
            
            if not target_path.exists():
                return JsonResponse({'error': 'Path not found'}, status=404)
                
            if target_path.is_file():
                # Read file
                content = target_path.read_text(encoding='utf-8', errors='replace')
                return JsonResponse({'type': 'file', 'content': content})
            else:
                # List directory
                items = []
                for entry in os.scandir(target_path):
                    if entry.name in ('.git', 'node_modules', '__pycache__', 'venv', '.venv'):
                        continue
                    items.append({
                        'name': entry.name,
                        'type': 'directory' if entry.is_dir() else 'file',
                        'path': os.path.relpath(entry.path, workspace_path).replace('\\', '/')
                    })
                # Sort directories first, then alphabetically
                items.sort(key=lambda x: (x['type'] == 'file', x['name'].lower()))
                return JsonResponse({'type': 'directory', 'items': items})

        elif request.method == 'POST':
            # Write file
            body = json.loads(request.body)
            rel_path = body.get('path')
            content = body.get('content', '')
            
            if not rel_path:
                return JsonResponse({'error': 'Path is required'}, status=400)
                
            workspace_manager.write_file(workspace_id, rel_path, content)
            return JsonResponse({'status': 'success'})
            
    except PermissionError as e:
        return JsonResponse({'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
        
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def workspace_spawn(request, workspace_id):
    """Spawns a process in the workspace."""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            command = body.get('command')
            if not command:
                return JsonResponse({'error': 'Command is required'}, status=400)
                
            workspace_path = workspace_manager.get_workspace_path(workspace_id)
            process_id = f"{workspace_id}_{command.split()[0]}" # Simplistic PID
            
            # Use sandbox to start
            sandbox.run_command(process_id, command, str(workspace_path))
            return JsonResponse({'status': 'success', 'process_id': process_id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def workspace_process_io(request, workspace_id, process_id):
    """Handles terminal input and reading output for a spawned process."""
    if request.method == 'GET':
        # Get pending output
        lines = sandbox.get_output(process_id)
        return JsonResponse({'output': ''.join(lines)})
        
    elif request.method == 'POST':
        # Send input
        try:
            body = json.loads(request.body)
            user_input = body.get('input', '')
            sandbox.send_input(process_id, user_input)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    elif request.method == 'DELETE':
        # Kill the process
        sandbox.kill_process(process_id)
        return JsonResponse({'status': 'killed'})
        
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def get_project(request, project_id):
    """Retrieve project details, creating a workspace if needed."""
    try:
        project = Project.objects.get(id=project_id)
        if not project.workspace_id and project.local_path:
            project.workspace_id = workspace_manager.create_workspace(project.local_path)
            project.save()
            
        return JsonResponse({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'github_url': project.github_url,
            'local_path': project.local_path,
            'workspace_id': project.workspace_id,
            'tech_stack': project.tech_stack,
            'status': project.status,
            'blueprint': project.blueprint
        })
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except ValidationError:
        return JsonResponse({'error': 'Invalid project ID'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def list_projects(request):
    """Retrieve all available projects for the dashboard."""
    try:
        projects = Project.objects.all().values(
            'id', 'name', 'description', 'status', 'tech_stack'
        )
        return JsonResponse({'projects': list(projects)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
