from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from agents.core.base import normalize_ai_config

from api.chat.helpers import _parse_json_body
from api.project_utils import _global_ai_config, _load_devhub_settings, _save_devhub_settings

@csrf_exempt
def devhub_ai_settings(request):
    if request.method == 'GET':
        return JsonResponse({'ai_config': _global_ai_config()})

    if request.method in {'POST', 'PATCH'}:
        try:
            body = _parse_json_body(request)
            ai_config = normalize_ai_config(body.get('ai_config'))
            settings = _load_devhub_settings()
            settings['ai_config'] = ai_config
            _save_devhub_settings(settings)
            return JsonResponse({'ai_config': ai_config})
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


