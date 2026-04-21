from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from api.codebase.scanner import _build_import_inspection, _pick_local_folder, _suggest_project_details
from api.chat.helpers import _parse_json_body
from api.project_utils import _normalize_path, _normalize_tech_stack

@csrf_exempt
def suggest_project_details(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        body = _parse_json_body(request)
        idea = str(body.get('idea') or body.get('name') or '').strip()
        source_type = str(body.get('source_type') or 'starter').strip().lower()
        tech_stack = _normalize_tech_stack(body.get('tech_stack', []))
        return JsonResponse(_suggest_project_details(idea, source_type, tech_stack))
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def inspect_github_import(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    temp_dir = None
    try:
        body = _parse_json_body(request)
        github_url = str(body.get('github_url') or '').strip()
        idea = str(body.get('idea') or '').strip()
        if not github_url:
            return JsonResponse({'error': 'GitHub URL is required'}, status=400)

        temp_dir = Path(tempfile.mkdtemp(prefix='devhub-import-'))
        repo_root = temp_dir / "repo"
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', github_url, str(repo_root)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return JsonResponse({'error': f'git clone failed: {result.stderr.strip() or "unknown git error"}'}, status=400)

        inspection = _build_import_inspection(repo_root, 'github', idea=idea, source_label=github_url)
        inspection['github_url'] = github_url
        return JsonResponse(inspection)
    except subprocess.TimeoutExpired:
        return JsonResponse({'error': 'GitHub inspection timed out'}, status=408)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@csrf_exempt
def pick_local_folder(request):
    if request.method not in {'POST', 'GET'}:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        selected = _pick_local_folder()
        if not selected:
            return JsonResponse({'error': 'Folder selection was cancelled'}, status=400)
        return JsonResponse({'local_path': selected})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
def inspect_folder_import(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        body = _parse_json_body(request)
        local_path = str(body.get('local_path') or '').strip()
        idea = str(body.get('idea') or '').strip()
        if not local_path:
            return JsonResponse({'error': 'Local path is required'}, status=400)

        resolved_path = _normalize_path(local_path)
        if not resolved_path.exists() or not resolved_path.is_dir():
            return JsonResponse({'error': 'Local path does not exist or is not a directory'}, status=400)

        inspection = _build_import_inspection(resolved_path, 'folder', idea=idea, source_label=local_path)
        return JsonResponse(inspection)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


