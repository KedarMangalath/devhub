"""
Global Skill Registry — reads the shared skills/ directory (sibling to devhub_v2/)
and provides auto-detection against user messages.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Path resolution:
# __file__  → .../Agentic/devhub_v2/backend/agents/skills/global_registry.py
# parents[0] → .../agents/skills/
# parents[1] → .../agents/
# parents[2] → .../backend/
# parents[3] → .../devhub_v2/
# parents[4] → .../Agentic/
_AGENTIC_ROOT = Path(__file__).resolve().parents[4]
GLOBAL_SKILLS_ROOT = Path(os.environ.get("DEVHUB_SKILLS_DIR", str(_AGENTIC_ROOT / "skills")))

SKILL_FILE = "SKILL.md"
_MAX_DESCRIPTION_LEN = 500
_BODY_PREVIEW_LIMIT = 32_000
_TRIGGER_KEYS = {"keywords", "triggers", "tags", "hints"}
_STOP_WORDS = {
    "use", "when", "the", "a", "an", "and", "or", "for", "to", "is",
    "in", "of", "this", "that", "with", "any", "if", "it", "on",
    "be", "are", "by", "from", "skill", "user", "wants", "asks",
    "need", "needs", "want", "mention", "mentions", "into", "their",
    "there", "then", "than", "also", "will", "your", "while", "using",
    "used", "make", "build", "create", "edit", "help", "guide",
}


def _safe_read(path: Path, limit: int = _BODY_PREVIEW_LIMIT) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    text = str(text or "")
    if not text.startswith("---\n"):
        return {}, text
    closing = text.find("\n---", 4)
    if closing == -1:
        return {}, text
    fm_text = text[4:closing]
    body = text[closing + 4:].lstrip("\r\n")
    data: dict = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip().strip("'\"")
        if key:
            data[key] = value
    return data, body


def _normalize_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def _split_frontmatter_terms(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;/|]", str(value or "")) if item.strip()]


def _content_preview(content: str, *, max_lines: int = 18, max_chars: int = 1800) -> str:
    snippets: list[str] = []
    for raw_line in str(content or "").splitlines():
        line = raw_line.strip().lstrip("#>*- ").strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        snippets.append(line)
        if len(snippets) >= max_lines or sum(len(item) for item in snippets) >= max_chars:
            break
    return " ".join(snippets)[:max_chars].strip()


def _skill_search_text(skill: dict) -> str:
    parts = [
        str(skill.get("name") or ""),
        str(skill.get("slug") or "").replace("-", " "),
        str(skill.get("description") or ""),
        str(skill.get("rel_path") or ""),
        " ".join(str(item) for item in (skill.get("trigger_terms") or []) if item),
        _content_preview(str(skill.get("content") or "")),
    ]
    return " ".join(part for part in parts if part).lower()


def _extract_trigger_keywords(skill_or_description) -> set[str]:
    """Pull meaningful keywords from a skill blob for matching."""
    if isinstance(skill_or_description, dict):
        text = _skill_search_text(skill_or_description)
    else:
        text = str(skill_or_description or "").lower()
    tokens = set(re.findall(r"[a-z][a-z0-9_-]{2,}", text))
    return tokens - _STOP_WORDS


def _candidate_phrases(skill: dict, limit: int = 10) -> list[str]:
    candidates: list[str] = []
    for raw in (
        str(skill.get("name") or ""),
        str(skill.get("description") or ""),
        *[str(item) for item in (skill.get("trigger_terms") or [])],
    ):
        cleaned = " ".join(raw.lower().split())
        if len(cleaned.split()) >= 2 and cleaned not in candidates:
            candidates.append(cleaned)

    preview = _content_preview(str(skill.get("content") or ""))
    for sentence in re.split(r"[.!?\n]", preview):
        cleaned = " ".join(sentence.lower().split())
        if 2 <= len(cleaned.split()) <= 8 and cleaned not in candidates:
            candidates.append(cleaned)
        if len(candidates) >= limit:
            break
    return candidates[:limit]


def _explicit_skill_token(message: str) -> str:
    match = re.match(r"^\s*/([a-z0-9][a-z0-9-]*)", str(message or "").strip().lower())
    return match.group(1) if match else ""


def list_global_skills(limit: int = 64) -> list[dict]:
    """Return metadata for all skills in the global skills directory."""
    root = GLOBAL_SKILLS_ROOT
    if not root.exists():
        return []

    items: list[dict] = []
    for path in sorted(root.rglob(SKILL_FILE)):
        if len(items) >= limit:
            break
        raw = _safe_read(path)
        if not raw:
            continue
        fm, body = _parse_frontmatter(raw)
        dir_name = path.parent.name.strip() or "skill"
        name = str(fm.get("name") or dir_name).strip()
        description = str(fm.get("description") or "").strip()
        trigger_terms: list[str] = []
        for key in _TRIGGER_KEYS:
            trigger_terms.extend(_split_frontmatter_terms(fm.get(key) or ""))
        items.append({
            "name": name,
            "slug": _normalize_slug(name) or _normalize_slug(dir_name),
            "description": description[:_MAX_DESCRIPTION_LEN],
            "path": str(path),
            "rel_path": str(path.relative_to(root)).replace("\\", "/"),
            "trigger_terms": list(dict.fromkeys(trigger_terms)),
            "content": body.strip(),
        })
    return items


def get_global_skill(name_or_slug: str) -> dict | None:
    target = _normalize_slug(name_or_slug)
    if not target:
        return None
    for item in list_global_skills():
        if _normalize_slug(item.get("name", "")) == target or item.get("slug") == target:
            return item
    return None


def detect_skills_for_message(message: str, skills: list[dict] | None = None, top_n: int = 3) -> list[dict]:
    """
    Score each skill against the user message and return the top matches.
    Returns skills sorted by score descending; only those with score >= threshold.
    """
    if skills is None:
        skills = list_global_skills()
    if not skills:
        return []

    msg_lower = str(message or "").lower()
    msg_words = set(re.findall(r"[a-z][a-z0-9_-]{2,}", msg_lower))
    explicit_token = _explicit_skill_token(message)

    scored: list[tuple[float, dict]] = []
    for skill in skills:
        keywords = _extract_trigger_keywords(skill)
        if not keywords:
            continue

        overlap = msg_words & keywords
        fuzzy_overlap = 0
        for msg_word in msg_words:
            if len(msg_word) < 5:
                continue
            if any(
                keyword.startswith(msg_word)
                or msg_word.startswith(keyword)
                for keyword in keywords
                if len(keyword) >= 5
            ):
                fuzzy_overlap += 1
        base_score = (len(overlap) + min(fuzzy_overlap, 3) * 0.35) / max(min(len(keywords), 18), 1)

        slug_value = str(skill.get("slug") or "")
        slug = slug_value.replace("-", " ")
        name = str(skill.get("name") or "").lower()
        if explicit_token and explicit_token == slug_value:
            base_score += 3.0
        if slug and f"/{slug_value}" in msg_lower:
            base_score += 1.6
        if slug and f" {slug} " in f" {msg_lower} ":
            base_score += 0.9
        if name and name in msg_lower:
            base_score += 1.1

        for phrase in _candidate_phrases(skill):
            if phrase and phrase in msg_lower:
                base_score += 0.45
                break

        ext_map = {
            "pdf": [".pdf", " pdf "],
            "docx": [".docx", " word ", " doc "],
            "xlsx": [".xlsx", " excel ", " spreadsheet "],
            "pptx": [".pptx", " powerpoint ", " slides ", " deck "],
            "slack-gif-creator": [".gif", " gif "],
            "algorithmic-art": ["generative", "p5.js", "flow field"],
            "canvas-design": ["poster", " canvas "],
            "webapp-testing": ["playwright", "e2e", " test "],
        }
        sk = slug_value
        for hints in ext_map.get(sk, []):
            if hints in msg_lower:
                base_score += 0.6

        if base_score >= 0.12:
            scored.append((base_score, skill))

    scored.sort(key=lambda t: -t[0])
    return [s for _, s in scored[:top_n]]


def build_skill_injection_prompt(skills: list[dict]) -> str:
    """Build system prompt text that injects matched skill instructions."""
    if not skills:
        return ""
    sections: list[str] = []
    for skill in skills:
        name = str(skill.get("name") or skill.get("slug") or "skill").strip()
        description = str(skill.get("description") or "").strip()
        content = str(skill.get("content") or "").strip()
        block = [f"## Active Skill: {name}"]
        if description:
            block.append(f"Trigger reason: {description[:200]}")
        if content:
            block.append(content[:12_000])
        sections.append("\n".join(block))

    return (
        "# Activated Skills\n"
        "The following skills are active for this request. Follow their instructions carefully.\n\n"
        + "\n\n---\n\n".join(sections)
    )


def create_global_skill(name: str, description: str, body: str) -> dict:
    """Write a new SKILL.md to the global skills directory."""
    slug = _normalize_slug(name)
    if not slug:
        raise ValueError("Skill name is required.")

    skill_dir = GLOBAL_SKILLS_ROOT / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / SKILL_FILE

    frontmatter = f"---\nname: {name.strip()}\ndescription: {description.strip()}\n---\n\n"
    skill_path.write_text(frontmatter + str(body or "").strip() + "\n", encoding="utf-8")

    return {
        "name": name.strip(),
        "slug": slug,
        "description": description.strip()[:_MAX_DESCRIPTION_LEN],
        "path": str(skill_path),
        "rel_path": f"{slug}/{SKILL_FILE}",
        "content": str(body or "").strip(),
    }


def update_global_skill(slug: str, description: str | None = None, body: str | None = None) -> dict | None:
    skill = get_global_skill(slug)
    if not skill:
        return None
    path = Path(skill["path"])
    fm, existing_body = _parse_frontmatter(_safe_read(path))
    new_description = description.strip() if description is not None else fm.get("description", "")
    new_body = body.strip() if body is not None else existing_body.strip()
    name = fm.get("name", slug)
    frontmatter = f"---\nname: {name}\ndescription: {new_description}\n---\n\n"
    path.write_text(frontmatter + new_body + "\n", encoding="utf-8")
    return get_global_skill(slug)


def delete_global_skill(slug: str) -> bool:
    skill = get_global_skill(slug)
    if not skill:
        return False
    import shutil
    skill_dir = Path(skill["path"]).parent
    if skill_dir.exists() and skill_dir.parent == GLOBAL_SKILLS_ROOT:
        shutil.rmtree(skill_dir)
        return True
    return False
