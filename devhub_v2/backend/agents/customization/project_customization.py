import re
from pathlib import Path

from agents.skills.global_registry import build_skill_injection_prompt, detect_skills_for_message

DEVHUB_META_DIR = ".devhub"
PROJECT_SKILLS_DIR = "skills"
PROJECT_PROMPTS_DIR = "prompts"
KNOWN_PROMPT_OVERRIDES = ("chat", "planner", "coder", "reviewer", "implementation")
SKILL_FILE_NAME = "SKILL.md"
SKILL_TRIGGER_KEYS = ("keywords", "triggers", "tags", "hints")
ROLE_PROMPT_OVERRIDES = {
    "chat": ("chat",),
    "planner": ("implementation", "planner"),
    "coder": ("implementation", "coder"),
    "reviewer": ("implementation", "reviewer"),
}
STARTER_PROMPT_OVERRIDES = {
    "implementation": """Keep code changes focused, repository-native, and easy to review.

- Prefer the smallest coherent implementation that fully solves the request.
- Reuse existing files, runtime conventions, and project structure before introducing new abstractions.
- When behavior changes, keep related UI, logic, validation, and tests aligned.
- Preserve local run commands and setup flow unless the request explicitly asks for a migration.
""",
    "coder": """Write code that matches the existing codebase style and framework patterns.

- Keep patches surgical and avoid unrelated refactors.
- Prefer readable, durable fixes over clever shortcuts.
- Leave nearby code a little clearer when it materially helps maintainability.
- Call out any risk or missing validation when the request cannot be fully verified.
""",
}
STARTER_SKILLS = {
    "debugging": """---
name: debugging
description: Trace failures to the real root cause before patching.
---
# Debugging

- Start by reproducing the issue from logs, runtime output, or the relevant request flow.
- Confirm the failure point before editing code.
- Prefer fixes that remove the cause, not just the visible symptom.
- After the patch, re-check the same execution path that originally failed.
""",
    "cleanup": """---
name: cleanup
description: Tighten existing code without changing requested behavior.
---
# Cleanup

- Simplify noisy logic while preserving current behavior.
- Remove duplication only when the abstraction is clearly local and improves readability.
- Keep naming, file layout, and patterns consistent with the surrounding code.
- Do not broaden scope into speculative refactors.
""",
}
STARTER_SUGGESTED_FILES = [
    ".devhub/prompts/implementation.md",
    ".devhub/prompts/coder.md",
    ".devhub/skills/debugging/SKILL.md",
    ".devhub/skills/cleanup/SKILL.md",
]


def _safe_read_text(path: Path, limit: int = 32000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""


def _parse_frontmatter(markdown: str) -> tuple[dict, str]:
    text = str(markdown or "")
    if not text.startswith("---\n"):
        return {}, text

    closing = text.find("\n---", 4)
    if closing == -1:
        return {}, text

    frontmatter_text = text[4:closing]
    body = text[closing + 4 :].lstrip("\r\n")
    data = {}
    for line in frontmatter_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip().strip("'").strip('"')
        if key:
            data[key] = value
    return data, body


def _first_meaningful_line(markdown_body: str) -> str:
    for raw_line in str(markdown_body or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line
    return ""


def _split_trigger_terms(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;/|]", str(value or "")) if item.strip()]


def _meta_dir(workspace_path: Path) -> Path:
    return workspace_path / DEVHUB_META_DIR


def _skills_dir(workspace_path: Path) -> Path:
    return _meta_dir(workspace_path) / PROJECT_SKILLS_DIR


def _prompts_dir(workspace_path: Path) -> Path:
    return _meta_dir(workspace_path) / PROJECT_PROMPTS_DIR


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def list_project_skills(workspace_path: Path, limit: int = 32) -> list[dict]:
    skills_root = _skills_dir(workspace_path)
    if not skills_root.exists():
        return []

    items: list[dict] = []
    for path in sorted(skills_root.rglob(SKILL_FILE_NAME)):
        if len(items) >= limit:
            break
        raw = _safe_read_text(path, limit=24000)
        if not raw:
            continue

        frontmatter, body = _parse_frontmatter(raw)
        directory_name = path.parent.name.strip() or "skill"
        skill_name = str(frontmatter.get("name") or directory_name).strip()
        description = str(frontmatter.get("description") or _first_meaningful_line(body) or f"Project skill: {skill_name}").strip()
        rel_path = str(path.relative_to(workspace_path)).replace("\\", "/")
        trigger_terms: list[str] = []
        for key in SKILL_TRIGGER_KEYS:
            trigger_terms.extend(_split_trigger_terms(frontmatter.get(key) or ""))
        items.append(
            {
                "name": skill_name,
                "slug": _normalize_key(skill_name) or _normalize_key(directory_name),
                "description": description[:280],
                "path": rel_path,
                "trigger_terms": list(dict.fromkeys(trigger_terms)),
                "content": body.strip(),
            }
        )
    return items


def get_project_skill(workspace_path: Path, skill_name: str) -> dict | None:
    normalized_target = _normalize_key(skill_name)
    if not normalized_target:
        return None

    for item in list_project_skills(workspace_path):
        candidates = {
            _normalize_key(item.get("name") or ""),
            _normalize_key(Path(str(item.get("path") or "")).parent.name),
            _normalize_key(str(item.get("slug") or "")),
        }
        if normalized_target in candidates:
            return item
    return None


def parse_project_skill_invocation(workspace_path: Path, content: str) -> tuple[dict | None, str]:
    text = str(content or "").strip()
    if not text.startswith("/"):
        return None, ""

    token, _, remainder = text[1:].partition(" ")
    skill = get_project_skill(workspace_path, token)
    if not skill:
        return None, ""
    return skill, remainder.strip()


def build_skill_execution_prompt(skill: dict | None, arguments: str = "") -> str:
    if not skill:
        return ""

    name = str(skill.get("name") or skill.get("slug") or "skill").strip()
    description = str(skill.get("description") or "").strip()
    content = str(skill.get("content") or "").strip()
    lines = [
        f"Project Skill: /{name}",
    ]
    if description:
        lines.append(f"Description: {description}")
    if content:
        lines.extend(["Skill Instructions:", content[:12000]])
    if arguments:
        lines.extend(["User Arguments:", arguments.strip()])
    return "\n".join(lines).strip()


def read_project_prompt_override(workspace_path: Path, name: str, limit: int = 12000) -> str:
    normalized = _normalize_key(name)
    if not normalized:
        return ""

    prompt_path = _prompts_dir(workspace_path) / f"{normalized}.md"
    return _safe_read_text(prompt_path, limit=limit).strip()


def list_project_prompt_overrides(workspace_path: Path) -> list[dict]:
    prompts_root = _prompts_dir(workspace_path)
    if not prompts_root.exists():
        return []

    items: list[dict] = []
    seen: set[str] = set()

    for name in KNOWN_PROMPT_OVERRIDES:
        raw = read_project_prompt_override(workspace_path, name)
        if not raw:
            continue
        seen.add(name)
        items.append(
            {
                "name": name,
                "path": f"{DEVHUB_META_DIR}/{PROJECT_PROMPTS_DIR}/{name}.md",
                "summary": _first_meaningful_line(_parse_frontmatter(raw)[1] or raw)[:240] or f"Custom {name} prompt override.",
            }
        )

    for path in sorted(prompts_root.glob("*.md")):
        stem = _normalize_key(path.stem)
        if stem in seen:
            continue
        raw = _safe_read_text(path, limit=8000)
        if not raw:
            continue
        items.append(
            {
                "name": stem,
                "path": str(path.relative_to(workspace_path)).replace("\\", "/"),
                "summary": _first_meaningful_line(_parse_frontmatter(raw)[1] or raw)[:240] or f"Custom {stem} prompt override.",
            }
        )

    return items


def build_project_customization_summary(workspace_path: Path) -> str:
    skills = list_project_skills(workspace_path, limit=10)
    prompts = list_project_prompt_overrides(workspace_path)
    lines: list[str] = []

    if skills:
        lines.append("Project Skills:")
        for item in skills:
            lines.append(f"- /{item.get('name')}: {item.get('description')}")

    if prompts:
        if lines:
            lines.append("")
        lines.append("Prompt Overrides:")
        for item in prompts:
            lines.append(f"- {item.get('name')}: {item.get('summary')}")

    return "\n".join(lines).strip()


def _join_sections(sections: list[str], limit: int = 16000) -> str:
    parts = [str(section or "").strip() for section in sections if str(section or "").strip()]
    if not parts:
        return ""
    return "\n\n".join(parts)[:limit].strip()


def suggested_project_customization_files() -> list[str]:
    return list(STARTER_SUGGESTED_FILES)


def bootstrap_project_customization(workspace_path: Path) -> dict:
    created: list[str] = []
    existing: list[str] = []

    prompts_dir = _prompts_dir(workspace_path)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for name, content in STARTER_PROMPT_OVERRIDES.items():
        target = prompts_dir / f"{_normalize_key(name)}.md"
        rel_path = str(target.relative_to(workspace_path)).replace("\\", "/")
        if target.exists():
            existing.append(rel_path)
            continue
        target.write_text(str(content).strip() + "\n", encoding="utf-8")
        created.append(rel_path)

    skills_dir = _skills_dir(workspace_path)
    skills_dir.mkdir(parents=True, exist_ok=True)
    for slug, content in STARTER_SKILLS.items():
        target_dir = skills_dir / _normalize_key(slug)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / SKILL_FILE_NAME
        rel_path = str(target.relative_to(workspace_path)).replace("\\", "/")
        if target.exists():
            existing.append(rel_path)
            continue
        target.write_text(str(content).strip() + "\n", encoding="utf-8")
        created.append(rel_path)

    return {
        "created": created,
        "existing": existing,
        "suggested_files": suggested_project_customization_files(),
    }


def build_implementation_customization_bundle(
    workspace_path: Path,
    request_text: str = "",
    *,
    skill_override: dict | None = None,
    skill_arguments: str = "",
    active_global_skills: list[dict] | None = None,
) -> dict:
    request_text = str(request_text or "").strip()
    skill = skill_override
    skill_args = str(skill_arguments or "").strip() if skill_override else ""
    skill_source = "override" if skill_override else ""

    if not skill:
        skill, skill_args = parse_project_skill_invocation(workspace_path, request_text)
        if skill:
            skill_source = "explicit"

    if not skill and request_text:
        auto_project_skills = detect_skills_for_message(
            request_text,
            skills=list_project_skills(workspace_path),
            top_n=1,
        )
        if auto_project_skills:
            skill = auto_project_skills[0]
            skill_args = request_text
            skill_source = "auto"

    prompt_overrides = {}
    for name in KNOWN_PROMPT_OVERRIDES:
        raw = read_project_prompt_override(workspace_path, name)
        if raw:
            prompt_overrides[name] = raw

    effective_request_text = request_text
    if skill_source in {"explicit", "override"} and skill and skill_args:
        effective_request_text = skill_args

    return {
        "request_text": request_text,
        "effective_request_text": effective_request_text,
        "summary": build_project_customization_summary(workspace_path),
        "prompt_overrides": prompt_overrides,
        "skill": skill,
        "skill_source": skill_source,
        "skill_arguments": skill_args,
        "skill_prompt": build_skill_execution_prompt(skill, skill_args),
        "global_skills": list(active_global_skills or []),
        "global_skill_prompt": build_skill_injection_prompt(list(active_global_skills or [])),
    }


def implementation_request_text(bundle: dict | None, fallback: str = "") -> str:
    if not isinstance(bundle, dict):
        return str(fallback or "").strip()
    return str(bundle.get("effective_request_text") or fallback or "").strip()


def _role_prompt_override_names(role: str) -> tuple[str, ...]:
    return ROLE_PROMPT_OVERRIDES.get(str(role or "").strip().lower(), ())


def build_role_customization_addendum(bundle: dict | None, role: str) -> str:
    if not isinstance(bundle, dict):
        return ""

    sections: list[str] = []
    summary = str(bundle.get("summary") or "").strip()
    if summary:
        sections.append(f"# Project Customization\n{summary[:6000]}")

    prompt_overrides = bundle.get("prompt_overrides") if isinstance(bundle.get("prompt_overrides"), dict) else {}
    for name in _role_prompt_override_names(role):
        override = str(prompt_overrides.get(name) or "").strip()
        if not override:
            continue
        title = "Shared Implementation Override" if name == "implementation" else f"{name.title()} Prompt Override"
        sections.append(f"# {title}\n{override[:10000]}")

    skill_prompt = str(bundle.get("skill_prompt") or "").strip()
    if skill_prompt:
        sections.append(
            "# Active Project Skill\n"
            f"{skill_prompt[:10000]}\n\n"
            "Honor the active project skill while still following the current request, repository evidence, and safety constraints."
        )

    global_skill_prompt = str(bundle.get("global_skill_prompt") or "").strip()
    if global_skill_prompt:
        sections.append(f"# Active Global Skills\n{global_skill_prompt[:12000]}")

    return _join_sections(sections, limit=24000)


def build_role_prompt_context(bundle: dict | None, role: str) -> str:
    if not isinstance(bundle, dict):
        return ""

    sections: list[str] = []
    summary = str(bundle.get("summary") or "").strip()
    if summary:
        sections.append(f"Project customization summary:\n{summary[:4000]}")

    prompt_overrides = bundle.get("prompt_overrides") if isinstance(bundle.get("prompt_overrides"), dict) else {}
    for name in _role_prompt_override_names(role):
        override = str(prompt_overrides.get(name) or "").strip()
        if not override:
            continue
        title = "Shared implementation override" if name == "implementation" else f"{name.title()} prompt override"
        sections.append(f"{title}:\n{override[:8000]}")

    skill_prompt = str(bundle.get("skill_prompt") or "").strip()
    if skill_prompt:
        skill_name = str(((bundle.get("skill") or {}) if isinstance(bundle.get("skill"), dict) else {}).get("name") or "").strip()
        heading = f"Active project skill: /{skill_name}" if skill_name else "Active project skill"
        sections.append(f"{heading}\n{skill_prompt[:10000]}")

    global_skill_prompt = str(bundle.get("global_skill_prompt") or "").strip()
    if global_skill_prompt:
        sections.append(f"Active global skills:\n{global_skill_prompt[:10000]}")

    return _join_sections(sections, limit=20000)
