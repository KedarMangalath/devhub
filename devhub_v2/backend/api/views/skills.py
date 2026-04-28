import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from agents.skills.global_registry import (
    create_global_skill,
    delete_global_skill,
    get_global_skill,
    list_global_skills,
    update_global_skill,
)

logger = logging.getLogger(__name__)


def _parse_body(request) -> dict:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


@csrf_exempt
def skills_list(request):
    """GET /api/skills/  — list all global skills
       POST /api/skills/ — create a new skill"""

    if request.method == "GET":
        skills = list_global_skills()
        # Strip full content from list view to keep payload small
        summary = [
            {
                "name": s["name"],
                "slug": s["slug"],
                "description": s["description"],
                "rel_path": s["rel_path"],
            }
            for s in skills
        ]
        return JsonResponse({"skills": summary})

    if request.method == "POST":
        body = _parse_body(request)
        name = str(body.get("name") or "").strip()
        description = str(body.get("description") or "").strip()
        skill_body = str(body.get("body") or "").strip()

        if not name:
            return JsonResponse({"error": "name is required"}, status=400)
        if not description:
            return JsonResponse({"error": "description is required"}, status=400)

        # Check for duplicates
        existing = get_global_skill(name)
        if existing:
            return JsonResponse({"error": f"Skill '{name}' already exists."}, status=409)

        try:
            skill = create_global_skill(name, description, skill_body)
            return JsonResponse({"skill": skill}, status=201)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Failed to create skill %s", name)
            return JsonResponse({"error": f"Failed to create skill: {exc}"}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def skill_detail(request, slug: str):
    """GET  /api/skills/<slug>/  — fetch full skill content
       PUT  /api/skills/<slug>/  — update skill
       DELETE /api/skills/<slug>/ — remove skill"""

    if request.method == "GET":
        skill = get_global_skill(slug)
        if not skill:
            return JsonResponse({"error": "Skill not found"}, status=404)
        return JsonResponse({"skill": skill})

    if request.method == "PUT":
        skill = get_global_skill(slug)
        if not skill:
            return JsonResponse({"error": "Skill not found"}, status=404)
        body = _parse_body(request)
        description = body.get("description")
        skill_body = body.get("body")
        updated = update_global_skill(slug, description=description, body=skill_body)
        if not updated:
            return JsonResponse({"error": "Update failed"}, status=500)
        return JsonResponse({"skill": updated})

    if request.method == "DELETE":
        skill = get_global_skill(slug)
        if not skill:
            return JsonResponse({"error": "Skill not found"}, status=404)
        ok = delete_global_skill(slug)
        if not ok:
            return JsonResponse({"error": "Delete failed"}, status=500)
        return JsonResponse({"deleted": slug})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
@require_http_methods(["POST"])
def detect_skills(request):
    """POST /api/skills/detect/  — detect relevant skills for a message
       Body: { "message": "..." }
       Returns: { "skills": [...] }"""
    from agents.skills.global_registry import detect_skills_for_message

    body = _parse_body(request)
    message = str(body.get("message") or "").strip()
    if not message:
        return JsonResponse({"skills": []})

    matched = detect_skills_for_message(message)
    summary = [
        {
            "name": s["name"],
            "slug": s["slug"],
            "description": s["description"],
        }
        for s in matched
    ]
    return JsonResponse({"skills": summary})
