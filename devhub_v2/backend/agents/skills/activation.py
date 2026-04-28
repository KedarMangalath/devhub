from __future__ import annotations

import re
from pathlib import Path

from agents.customization.project_customization import (
    list_project_skills,
    parse_project_skill_invocation,
)
from agents.skills.global_registry import (
    build_skill_injection_prompt,
    detect_skills_for_message,
    get_global_skill,
    list_global_skills,
)


def _dedupe_skills(skills: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for skill in skills:
        slug = str(skill.get("slug") or "").strip().lower()
        if not slug or slug in seen:
            continue
        deduped.append(skill)
        seen.add(slug)
    return deduped


def _slash_token(content: str) -> tuple[str, str]:
    text = str(content or "").strip()
    if not text.startswith("/"):
        return "", ""
    token, _, remainder = text[1:].partition(" ")
    return token.strip().lower(), remainder.strip()


def _format_skill_line(skill: dict) -> str:
    slug = str(skill.get("slug") or skill.get("name") or "skill").strip()
    description = str(skill.get("description") or "").strip()
    if description:
        return f"- `/{slug}` — {description}"
    return f"- `/{slug}`"


def render_skill_catalog_response(workspace_path: Path | None = None, *, query: str = "") -> str:
    query_lower = str(query or "").strip().lower()
    project_skills = list_project_skills(workspace_path) if workspace_path else []
    global_skills = list_global_skills()

    def matches(skill: dict) -> bool:
        if not query_lower:
            return True
        haystack = " ".join(
            [
                str(skill.get("name") or ""),
                str(skill.get("slug") or ""),
                str(skill.get("description") or ""),
            ]
        ).lower()
        return query_lower in haystack

    filtered_project = [skill for skill in project_skills if matches(skill)][:10]
    filtered_global = [skill for skill in global_skills if matches(skill)][:14]

    lines = ["## Available Skills"]
    if query_lower:
        lines.append(f"Filtered by `{query_lower}`.")

    if filtered_global:
        lines.extend(["", "Global skills:"])
        lines.extend(_format_skill_line(skill) for skill in filtered_global)
    else:
        lines.extend(["", "Global skills:", "- No matching global skills found."])

    if workspace_path:
        if filtered_project:
            lines.extend(["", "Project skills:"])
            lines.extend(_format_skill_line(skill) for skill in filtered_project)
        else:
            lines.extend(["", "Project skills:", "- No matching project skills found in `.devhub/skills` yet."])

    lines.extend(
        [
            "",
            "Usage:",
            "- Type `/skills` to see this list again, or `/skills design` to filter it.",
            "- Start a request with a slash command like `/frontend-design redesign the dashboard shell`.",
            "- Pin global skills from the Skills panel to keep them active across messages.",
        ]
    )
    return "\n".join(lines).strip()


def resolve_skill_activation(
    request_text: str,
    *,
    workspace_path: Path | None = None,
    pinned_global_skill_slugs: list[str] | None = None,
) -> dict:
    raw_request_text = str(request_text or "").strip()
    token, remainder = _slash_token(raw_request_text)

    if token == "skills":
        return {
            "request_text": raw_request_text,
            "effective_request_text": "",
            "command_kind": "skills_catalog",
            "command_response": render_skill_catalog_response(workspace_path, query=remainder),
            "active_global_skills": [],
            "active_global_skill_slugs": [],
            "project_skill": None,
            "project_skill_arguments": "",
            "active_skill_names": [],
            "skill_instructions": "",
        }

    project_skill = None
    project_skill_arguments = ""
    if workspace_path:
        project_skill, project_skill_arguments = parse_project_skill_invocation(workspace_path, raw_request_text)

    explicit_global_skill = get_global_skill(token) if token else None

    if (project_skill or explicit_global_skill) and not remainder:
        active_names = [name for name in [
            str((project_skill or {}).get("name") or "").strip(),
            str((explicit_global_skill or {}).get("name") or "").strip(),
        ] if name]
        skill_name = active_names[0] if active_names else token or "skill"
        example_command = f"/{token} describe the change you want"
        return {
            "request_text": raw_request_text,
            "effective_request_text": "",
            "command_kind": "skill_needs_request",
            "command_response": (
                f"`/{skill_name}` is ready. Add the actual task after the command, for example `{example_command}`."
            ),
            "active_global_skills": [explicit_global_skill] if explicit_global_skill else [],
            "active_global_skill_slugs": [str(explicit_global_skill.get("slug") or "")] if explicit_global_skill else [],
            "project_skill": project_skill,
            "project_skill_arguments": "",
            "active_skill_names": active_names,
            "skill_instructions": build_skill_injection_prompt([explicit_global_skill]) if explicit_global_skill else "",
        }

    all_global_skills = list_global_skills()
    auto_global_skills = detect_skills_for_message(raw_request_text, skills=all_global_skills, top_n=3)
    pinned_global_skills = [
        skill
        for slug in (pinned_global_skill_slugs or [])
        for skill in [get_global_skill(slug)]
        if skill
    ]

    # Force-inject frontend-design skill for broad UI overhaul requests.
    # Use generic redesign verbs rather than framework/app-specific page names
    # so this works across any tech stack.
    forced_global_skills: list[dict] = []
    if not explicit_global_skill:
        _ui_redesign_verbs = {
            'redesign', 'overhaul', 'revamp', 'rework', 'redo', 'restyle',
            'rewrite', 'rebuild', 'refactor', 'modernize', 'refresh',
        }
        _ui_scope_words = {
            'ui', 'interface', 'frontend', 'design', 'layout', 'theme',
            'color', 'palette', 'sidebar', 'navbar', 'look', 'style',
            'appearance', 'visual', 'page', 'pages', 'component', 'components',
        }
        msg_words = set(re.findall(r'[a-z][a-z0-9_-]{1,}', raw_request_text.lower()))
        has_redesign_verb = bool(msg_words & _ui_redesign_verbs)
        has_ui_scope = bool(msg_words & _ui_scope_words)
        if has_redesign_verb and has_ui_scope:
            fd_skill = get_global_skill('frontend-design')
            if fd_skill:
                forced_global_skills = [fd_skill]

    active_global_skills = _dedupe_skills(
        ([explicit_global_skill] if explicit_global_skill else [])
        + forced_global_skills
        + pinned_global_skills
        + auto_global_skills
    )

    if workspace_path and not project_skill:
        auto_project_skills = detect_skills_for_message(
            raw_request_text,
            skills=list_project_skills(workspace_path),
            top_n=1,
        )
        if auto_project_skills:
            project_skill = auto_project_skills[0]
            project_skill_arguments = raw_request_text

    effective_request_text = remainder if (project_skill or explicit_global_skill) and remainder else raw_request_text

    active_skill_names = [str(skill.get("name") or skill.get("slug") or "").strip() for skill in active_global_skills]
    if project_skill:
        project_name = str(project_skill.get("name") or project_skill.get("slug") or "").strip()
        if project_name and project_name not in active_skill_names:
            active_skill_names.append(project_name)

    return {
        "request_text": raw_request_text,
        "effective_request_text": effective_request_text,
        "command_kind": "",
        "command_response": "",
        "active_global_skills": active_global_skills,
        "active_global_skill_slugs": [str(skill.get("slug") or "").strip() for skill in active_global_skills if str(skill.get("slug") or "").strip()],
        "project_skill": project_skill,
        "project_skill_arguments": remainder if project_skill and remainder else project_skill_arguments,
        "active_skill_names": active_skill_names,
        "skill_instructions": build_skill_injection_prompt(active_global_skills),
    }
