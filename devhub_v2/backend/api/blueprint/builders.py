import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from django.utils import timezone

from core.models import ChatMessage, Feature, Project

from api.codebase.doc_builder import (
    _blueprint_list,
    _blueprint_text,
    _markdown_bullets,
    _project_workspace_path,
    _read_workspace_excerpt,
)
from api.workspace.memory import _normalize_mermaid_chart

logger = logging.getLogger(__name__)

def _detect_workspace_package_manager(workspace_path: Path | None, package_data: dict) -> str:
    package_manager = str(package_data.get("packageManager") or "").strip().lower()
    if package_manager:
        return package_manager.split("@", 1)[0]
    if workspace_path and (workspace_path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if workspace_path and (workspace_path / "pnpm-workspace.yaml").exists():
        return "pnpm"
    if workspace_path and (workspace_path / "yarn.lock").exists():
        return "yarn"
    if workspace_path and ((workspace_path / "bun.lock").exists() or (workspace_path / "bun.lockb").exists()):
        return "bun"
    if workspace_path and (workspace_path / "package-lock.json").exists():
        return "npm"
    return "npm" if package_data else ""


def _run_script_command(package_manager: str, script_name: str) -> str:
    script = str(script_name or "").strip()
    if not script:
        return ""
    if package_manager == "npm":
        return f"npm run {script}"
    if package_manager in {"pnpm", "yarn", "bun"}:
        return f"{package_manager} {script}"
    return script


def _extract_shell_commands(text: str) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    in_block = False
    command_prefix = re.compile(
        r"^(pnpm|npm|yarn|bun|openclaw|python|pip|uv|poetry|docker|cargo|go|make|swift|xcodebuild|adb|bash|sh|\./)",
        re.IGNORECASE,
    )

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_block = not in_block
            continue

        candidates: list[str] = []
        if in_block:
            candidate = line.split("#", 1)[0].strip()
            if candidate:
                candidates.append(candidate)
        else:
            for match in re.finditer(r"`([^`]+)`", raw_line):
                candidate = match.group(1).strip()
                if candidate:
                    candidates.append(candidate)

        for candidate in candidates:
            if not command_prefix.match(candidate):
                continue
            if candidate not in seen:
                seen.add(candidate)
                commands.append(candidate)

    return commands


def _pick_command(commands: list[str], *keywords: str) -> str:
    wanted = [keyword.lower() for keyword in keywords if keyword]
    matches = []
    for command in commands:
        lowered = command.lower()
        if all(keyword in lowered for keyword in wanted):
            matches.append(command)
    if not matches:
        return ""
    matches.sort(key=lambda item: (len(item.split()), len(item)), reverse=True)
    return matches[0]


def _top_repository_areas(codebase_context: dict, limit: int = 5) -> list[str]:
    directories = []
    for directory, _count in sorted((codebase_context.get("directory_counts") or {}).items(), key=lambda item: (-item[1], item[0])):
        name = str(directory or "").strip()
        if not name or name in {".", ".git", ".devhub", ".claude", ".claude-backup2", ".code-review-graph", "node_modules", "__pycache__", "data"}:
            continue
        directories.append(f"{name}/")
        if len(directories) >= limit:
            break
    return directories


def _guidance_item_text(item) -> str:
    if isinstance(item, dict):
        return " ".join(
            str(item.get(key) or "")
            for key in ("step", "task", "command", "instructions", "why_important", "explanation", "os_note", "category")
        ).strip().lower()
    return str(item or "").strip().lower()


def _guidance_field_needs_refresh(value, field_name: str) -> bool:
    items = _blueprint_list(value)
    if not items:
        return True

    markers = {
        "setup_steps": {
            "clone the repository",
            "install dependencies",
            "run migrations",
            "start the server",
            "python manage.py migrate",
            "python manage.py runserver",
            "run onboarding",
            "set up development environment",
            "review repository map",
            "read local setup docs",
            "run the project",
        },
        "onboarding_checklist": {
            "read the repo map",
            "inspect runtime entrypoints",
            "review onboarding first",
            "open the blueprint",
            "inspect architecture",
        },
        "gotchas": {
            "areas without evidence should be treated as unknown",
            "ai blueprint generation failed",
            "use .devhub/repo-map.md",
            "no gotchas were documented",
        },
    }.get(field_name, set())

    texts = [_guidance_item_text(item) for item in items]
    generic_hits = sum(1 for text in texts if any(marker in text for marker in markers))
    if generic_hits == len(texts):
        return True
    if len(texts) <= 3 and generic_hits >= max(1, len(texts) - 1):
        return True
    return False


DESIGN_DOC_TEMPLATE_MARKERS = {
    "third-party services",
    "additional functionalities",
    "<repository-url>",
    "specifies the settings module for django",
    "use pytest for unit testing",
    "django's test client",
    "utilize cypress",
    "ensure secure handling of user credentials and tokens",
    "consider implementing caching strategies",
    "restful principles for api design",
    "avoid database inconsistencies",
    "no tracked features yet",
}


def _normalize_design_doc_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _looks_like_design_doc_template(value) -> bool:
    normalized = _normalize_design_doc_text(value)
    if not normalized:
        return False
    return any(marker in normalized for marker in DESIGN_DOC_TEMPLATE_MARKERS)


def _filter_design_doc_dict_items(items: list, text_keys: tuple[str, ...]) -> list[dict]:
    filtered: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        combined = " ".join(str(item.get(key) or "") for key in text_keys).strip()
        if not combined or _looks_like_design_doc_template(combined):
            continue
        filtered.append(item)
    return filtered


def _filter_design_doc_strings(items: list) -> list[str]:
    filtered: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or _looks_like_design_doc_template(text):
            continue
        filtered.append(text)
    return filtered


def _dedupe_json_items(items: list) -> list:
    deduped = []
    seen = set()
    for item in items:
        key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _manifest_paths(codebase_context: dict) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for item in codebase_context.get("manifest") or []:
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if not path or path in seen or _is_devhub_internal_path(path):
            continue
        seen.add(path)
        paths.append(path)
    return paths


def _normalize_rel_dir(value: str) -> str:
    normalized = str(value or "").replace("\\", "/").strip().strip("/")
    return "" if normalized in {"", "."} else normalized


def _format_path_list(paths: list[str], max_paths: int = 3) -> str:
    unique = []
    seen = set()
    for path in paths:
        normalized = str(path or "").replace("\\", "/").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(f"`{normalized}`")
    if not unique:
        return ""
    shown = unique[:max_paths]
    if len(shown) == 1:
        return shown[0]
    if len(shown) == 2:
        return f"{shown[0]} and {shown[1]}"
    return f"{', '.join(shown[:-1])}, and {shown[-1]}"


def _prefix_command_for_dir(rel_dir: str, command: str) -> str:
    normalized = _normalize_rel_dir(rel_dir)
    command_text = str(command or "").strip()
    if not command_text:
        return ""
    if not normalized:
        return command_text
    target = f"\"{normalized}\"" if " " in normalized else normalized
    return f"cd {target} && {command_text}"


def _workspace_package_manifests(workspace_path: Path, codebase_context: dict) -> list[dict]:
    manifests: list[dict] = []
    for rel_path in _manifest_paths(codebase_context):
        if PurePosixPath(rel_path).name.lower() != "package.json":
            continue
        file_path = workspace_path / rel_path
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        rel_dir = _normalize_rel_dir(PurePosixPath(rel_path).parent.as_posix())
        scripts = payload.get("scripts") if isinstance(payload.get("scripts"), dict) else {}
        manifests.append({
            "path": rel_path,
            "rel_dir": rel_dir,
            "name": str(payload.get("name") or PurePosixPath(rel_path).parent.name or "package").strip(),
            "package_manager": _detect_workspace_package_manager(file_path.parent, payload) or "npm",
            "scripts": scripts,
            "workspaces": bool(payload.get("workspaces")) or (rel_dir == "" and (workspace_path / "pnpm-workspace.yaml").exists()),
        })
    manifests.sort(key=lambda item: (item.get("rel_dir") != "", str(item.get("rel_dir") or ""), str(item.get("path") or "")))
    return manifests


def _workspace_python_roots(workspace_path: Path, codebase_context: dict) -> list[dict]:
    roots: dict[str, dict] = {}
    manifest_paths = _manifest_paths(codebase_context)
    for rel_path in manifest_paths:
        name = PurePosixPath(rel_path).name.lower()
        if name not in {"manage.py", "requirements.txt", "requirements-dev.txt", "pyproject.toml", "pipfile", "poetry.lock", "uv.lock"}:
            continue
        rel_dir = _normalize_rel_dir(PurePosixPath(rel_path).parent.as_posix())
        entry = roots.setdefault(rel_dir, {
            "rel_dir": rel_dir,
            "manage_py": "",
            "requirements": "",
            "pyproject": "",
            "tooling": [],
            "framework": "",
        })
        if name == "manage.py":
            entry["manage_py"] = rel_path
            manage_text = _read_workspace_excerpt(workspace_path, rel_path, limit=4000).lower()
            if "django" in manage_text or "settings" in manage_text:
                entry["framework"] = "django"
        elif name == "requirements.txt" or (name == "requirements-dev.txt" and not entry.get("requirements")):
            entry["requirements"] = rel_path
        elif name == "pyproject.toml":
            entry["pyproject"] = rel_path
        else:
            entry.setdefault("tooling", []).append(rel_path)

    for rel_dir, entry in roots.items():
        if entry.get("framework"):
            continue
        prefix = f"{rel_dir}/" if rel_dir else ""
        if any(path.startswith(prefix) and PurePosixPath(path).name.lower() == "settings.py" for path in manifest_paths):
            entry["framework"] = "django"

    ordered = list(roots.values())
    ordered.sort(
        key=lambda item: (
            item.get("rel_dir") != "",
            str(item.get("rel_dir") or ""),
            0 if item.get("manage_py") else 1,
            0 if item.get("requirements") else 1,
        )
    )
    return ordered


def _env_template_paths(workspace_path: Path, codebase_context: dict) -> list[str]:
    candidates: list[str] = []
    for item in _codebase_summary_pool(codebase_context):
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if not path:
            continue
        file_kind = str(item.get("file_kind") or "").strip().lower()
        file_name = PurePosixPath(path).name.lower()
        if file_kind == "env-template" or file_name in {".env.example", ".env.sample", ".env.template", ".env.local.example", ".env.development.example"}:
            candidates.append(path)
    if not candidates:
        for rel_path in _manifest_paths(codebase_context):
            file_name = PurePosixPath(rel_path).name.lower()
            if file_name in {".env.example", ".env.sample", ".env.template", ".env.local.example", ".env.development.example"}:
                candidates.append(rel_path)
    return _dedupe_json_items(candidates)[:12]


def _sanitize_env_value(value: str) -> str:
    text = str(value or "").strip().strip('"').strip("'")
    if not text:
        return ""
    lowered = text.lower()
    if any(token in lowered for token in ("<", ">", "changeme", "replace", "your-", "your_", "example", "sample", "placeholder", "dummy")):
        return text
    if re.match(r"^(sk-|ghp_|AIza|ya29\.)", text):
        return "<configured secret>"
    if len(text) >= 24 and not re.match(r"^(https?://|[A-Za-z]:/|/|\.{0,2}/)", text) and not re.fullmatch(r"[0-9.]+", text):
        return "<configured value>"
    return text


def _infer_env_category(name: str) -> str:
    upper = str(name or "").upper()
    if upper.startswith(("VITE_", "NEXT_PUBLIC_", "PUBLIC_")):
        return "frontend"
    if any(token in upper for token in ("OPENAI", "ANTHROPIC", "GEMINI", "VERTEX", "MODEL", "LLM", "AI_")):
        return "ai"
    if any(token in upper for token in ("SECRET", "TOKEN", "KEY", "PASSWORD", "CREDENTIAL")):
        return "secret"
    if any(token in upper for token in ("DB_", "DATABASE", "POSTGRES", "MYSQL", "SQLITE", "REDIS", "MONGO")):
        return "database"
    if any(token in upper for token in ("AUTH", "JWT", "SESSION", "CSRF", "CORS", "ALLOWED_HOSTS")):
        return "auth"
    if any(token in upper for token in ("S3", "BUCKET", "STORAGE", "UPLOAD", "MEDIA")):
        return "storage"
    if any(token in upper for token in ("URL", "HOST", "PORT", "ORIGIN", "BASE_URL", "API_BASE")):
        return "runtime"
    return "config"


def _is_ai_related_env(name: str) -> bool:
    upper = str(name or "").upper()
    return any(token in upper for token in ("OPENAI", "OPENROUTER", "ANTHROPIC", "CLAUDE", "GEMINI", "VERTEX", "GOOGLE_API", "GOOGLE_CLOUD", "MODEL", "LLM", "AI_"))


def _is_ai_override_env(name: str) -> bool:
    upper = str(name or "").upper()
    if not _is_ai_related_env(upper):
        return False
    return any(
        token in upper
        for token in ("MODEL", "BASE_URL", "PROVIDER", "MODE", "LOCATION", "PROJECT", "CLI_COMMAND")
    )


def _env_family_prefix(name: str) -> str:
    upper = str(name or "").upper()
    if "_" not in upper:
        return ""
    prefix = upper.split("_", 1)[0].strip()
    return prefix if prefix and prefix not in {"VITE", "NEXT", "PUBLIC", "DATABASE", "DJANGO", "NODE"} else ""


def _is_ai_family_env(name: str, ai_prefixes: set[str]) -> bool:
    upper = str(name or "").upper()
    if _is_ai_related_env(upper):
        return True
    prefix = _env_family_prefix(upper)
    if not prefix or prefix not in ai_prefixes:
        return False
    return any(
        upper.endswith(suffix)
        for suffix in ("_API_KEY", "_MODEL", "_BASE_URL", "_PROVIDER", "_MODE", "_LOCATION", "_PROJECT", "_CLI_COMMAND", "_ACCESS_TOKEN")
    )


def _summarize_ai_env_entry(variable_names: list[str]) -> dict:
    credential_candidates = [
        name for name in variable_names
        if name in {
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENROUTER_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
        }
    ]
    extra_candidates = [
        name for name in variable_names
        if _is_ai_override_env(name)
    ]
    examples = credential_candidates[:4] + [name for name in extra_candidates[:2] if name not in credential_candidates[:4]]
    description = "Multiple AI or model-provider variables were detected. Credentials are usually the actionable values to set locally, while provider, model, base URL, or location fields are often optional overrides."
    if examples:
        description = f"{description} Common variables include {', '.join(f'`{name}`' for name in examples)}."
    return {
        "name": "AI provider configuration",
        "required": False,
        "default": "No default detected",
        "example": " / ".join(examples[:3]) if examples else "Provider-specific credential env vars",
        "category": "ai",
        "description": description,
    }


def _env_display_score(name: str, item: dict, references: list[str], from_template: bool) -> int:
    upper = str(name or "").upper()
    score = 0
    if from_template:
        score += 10
    score += min(8, len(references) * 2)
    if upper.startswith(("VITE_", "NEXT_PUBLIC_", "PUBLIC_")):
        score += 8
    if upper in {"DATABASE_URL", "SECRET_KEY", "DJANGO_SETTINGS_MODULE", "PORT", "HOST"}:
        score += 6
    if upper in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"}:
        score += 5
    if any(path.lower().endswith("settings.py") for path in references):
        score += 4
    if any("/frontend/" in path.lower() or path.lower().startswith("frontend/") for path in references):
        score += 3
    if _is_ai_override_env(upper) and not from_template:
        score -= 6
    if item.get("category") == "secret":
        score += 2
    if not references and not from_template:
        score -= 2
    return score


def _normalized_loose_tokens(value: str) -> set[str]:
    tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", str(value or "").lower())
        if token and token not in {"the", "a", "an", "and", "or", "to", "of", "for", "in", "is", "are", "be", "by", "with", "this", "that", "it", "from"}
    }
    return tokens


def _dedupe_similar_strings(items: list[str], similarity_threshold: float = 0.72) -> list[str]:
    deduped: list[str] = []
    token_sets: list[set[str]] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        current_tokens = _normalized_loose_tokens(text)
        normalized_text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        duplicate = False
        for existing, existing_tokens in zip(deduped, token_sets):
            existing_normalized = re.sub(r"[^a-z0-9]+", " ", str(existing).lower()).strip()
            if not current_tokens or not existing_tokens:
                if normalized_text == existing_normalized:
                    duplicate = True
                    break
                continue
            overlap = len(current_tokens & existing_tokens) / max(1, len(current_tokens | existing_tokens))
            if overlap >= similarity_threshold or normalized_text in existing_normalized or existing_normalized in normalized_text:
                duplicate = True
                break
        if duplicate:
            continue
        deduped.append(text)
        token_sets.append(current_tokens)
    return deduped


def _scan_environment_variable_usage(workspace_path: Path, codebase_context: dict, variable_names: list[str]) -> dict[str, list[str]]:
    if not variable_names:
        return {}
    usage = {name: [] for name in variable_names}
    candidate_paths: list[str] = []
    for item in _codebase_summary_pool(codebase_context, limit=240):
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if not path:
            continue
        file_kind = str(item.get("file_kind") or "").strip().lower()
        lowered_path = path.lower()
        if file_kind == "env-template":
            continue
        if file_kind in {"config", "build-config", "api-module", "routing-module", "package-manifest", "container-config", "script"} or any(
            token in lowered_path for token in ("settings", "config", "runtime", "process", "consumer", "executor", "sandbox", "workspace", "views", "urls", "docker", "compose", "vite", "next")
        ):
            candidate_paths.append(path)
    if not candidate_paths:
        candidate_paths = _manifest_paths(codebase_context)[:80]

    for rel_path in _dedupe_json_items(candidate_paths)[:80]:
        text = _read_workspace_excerpt(workspace_path, rel_path, limit=18000)
        if not text:
            continue
        for name in variable_names:
            if name in text and rel_path not in usage[name]:
                usage[name].append(rel_path)
    return usage


def _derive_environment_variables(workspace_path: Path, codebase_context: dict) -> list[dict]:
    parsed: dict[str, dict] = {}
    template_paths = _env_template_paths(workspace_path, codebase_context)
    parsed_from_template = bool(template_paths)

    for rel_path in template_paths:
        content = _read_workspace_excerpt(workspace_path, rel_path, limit=16000)
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            if stripped.lower().startswith("export "):
                stripped = stripped[7:].strip()
            name, raw_value = stripped.split("=", 1)
            env_name = name.strip()
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", env_name):
                continue
            sanitized = _sanitize_env_value(raw_value)
            entry = parsed.setdefault(env_name, {
                "name": env_name,
                "required": False,
                "default": "",
                "example": "",
                "category": _infer_env_category(env_name),
            })
            if sanitized and not entry.get("default"):
                entry["default"] = sanitized
            if sanitized and not entry.get("example"):
                entry["example"] = sanitized
            placeholder = not sanitized or any(token in sanitized.lower() for token in ("<", ">", "changeme", "replace", "your-", "your_", "placeholder", "dummy"))
            entry["required"] = bool(entry.get("required")) or placeholder or entry["category"] == "secret"

    if not parsed:
        pattern_hits: dict[str, dict] = {}
        patterns = [
            r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]",
            r"os\.environ(?:\.get)?\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\]",
            r"os\.environ\.get\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]",
            r"process\.env\.([A-Z][A-Z0-9_]*)",
            r"import\.meta\.env\.([A-Z][A-Z0-9_]*)",
        ]
        for rel_path in _manifest_paths(codebase_context)[:500]:
            text = _read_workspace_excerpt(workspace_path, rel_path, limit=16000)
            if not text:
                continue
            for pattern in patterns:
                for match in re.findall(pattern, text):
                    if match not in pattern_hits:
                        pattern_hits[match] = {
                            "name": match,
                            "required": True,
                            "default": "",
                            "example": "",
                            "category": _infer_env_category(match),
                        }
        parsed = pattern_hits

    usage = _scan_environment_variable_usage(workspace_path, codebase_context, sorted(parsed.keys()))
    env_vars: list[dict] = []
    ai_related_names: list[str] = []
    scored_items: list[tuple[int, dict]] = []
    ai_prefixes = {
        _env_family_prefix(name)
        for name in parsed.keys()
        if _env_family_prefix(name) and _is_ai_related_env(name)
    }

    for name in sorted(parsed.keys()):
        item = dict(parsed[name])
        category = str(item.get("category") or _infer_env_category(name))
        references = usage.get(name) or []
        ai_family_env = _is_ai_family_env(name, ai_prefixes)
        description_prefix = {
            "frontend": "Frontend-facing setting that affects the client bundle or browser runtime.",
            "ai": "AI or model-provider configuration referenced by the application runtime.",
            "secret": "Credential or secret that should be supplied per environment rather than committed into source.",
            "database": "Database connection or persistence setting used by the application runtime.",
            "auth": "Authentication, session, or trust-boundary setting that changes request security behavior.",
            "storage": "Storage or upload configuration used to locate buckets, files, or media backends.",
            "runtime": "Runtime or network setting that changes host, port, origin, or base URL behavior.",
            "config": "Environment-driven configuration that changes how the application boots or behaves.",
        }.get(category, "Environment-driven configuration used by the project at runtime.")
        if references:
            description = f"{description_prefix} Referenced in {_format_path_list(references, max_paths=2)}."
        elif template_paths:
            description = f"{description_prefix} Declared in {_format_path_list(template_paths[:2], max_paths=2)}."
        else:
            description = description_prefix
        if ai_family_env and category == "secret":
            category = "ai"
        item["category"] = category
        item["description"] = description
        if ai_family_env:
            ai_related_names.append(name)
        score = _env_display_score(name, item, references, parsed_from_template)
        if ai_family_env and not parsed_from_template and _is_ai_override_env(name):
            score -= 2
        item["_score"] = score
        scored_items.append((score, item))

    collapse_ai_settings = not parsed_from_template and len(ai_related_names) >= 8
    if collapse_ai_settings:
        env_vars.append(_summarize_ai_env_entry(sorted(ai_related_names)))

    for score, item in sorted(scored_items, key=lambda pair: (-pair[0], str(pair[1].get("name") or ""))):
        name = str(item.get("name") or "")
        if collapse_ai_settings and _is_ai_family_env(name, ai_prefixes):
            continue
        if score < (3 if parsed_from_template else 0) and env_vars:
            continue
        cleaned = {key: value for key, value in item.items() if key != "_score"}
        env_vars.append(cleaned)

    return _dedupe_json_items(env_vars)[:30]


def _detect_coverage_target(workspace_path: Path, codebase_context: dict) -> str:
    config_names = {
        "package.json",
        "pyproject.toml",
        "pytest.ini",
        "mypy.ini",
        "tox.ini",
        "setup.cfg",
        "vitest.config.ts",
        "vitest.config.js",
        "jest.config.js",
        "jest.config.ts",
    }
    patterns = [
        r"coverageThreshold[^0-9]{0,80}(\d+)",
        r"fail_under\s*=\s*(\d+)",
        r"--cov-fail-under(?:=|\s+)(\d+)",
    ]
    for rel_path in _manifest_paths(codebase_context):
        if PurePosixPath(rel_path).name.lower() not in config_names:
            continue
        text = _read_workspace_excerpt(workspace_path, rel_path, limit=18000)
        if not text:
            continue
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return f"{match.group(1)}% minimum coverage detected in `{rel_path}`."
    return "No numeric coverage threshold was detected in the indexed test config."


def _derive_testing_strategy(project: Project, codebase_context: dict) -> dict:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return {}

    manifest_paths = _manifest_paths(codebase_context)
    python_test_paths = [path for path in manifest_paths if re.search(r"(^|/)(test_.*\.py|tests\.py)$", path, re.IGNORECASE) or "/tests/" in path.lower()]
    js_test_paths = [path for path in manifest_paths if re.search(r"(\.test|\.spec)\.(js|jsx|ts|tsx)$", path, re.IGNORECASE)]
    e2e_paths = [path for path in manifest_paths if any(token in path.lower() for token in ("cypress/", "playwright/", "/e2e/", "e2e."))]
    integration_paths = [path for path in manifest_paths if any(token in path.lower() for token in ("/integration/", "integration_test", "/api/tests", "/tests/api"))]

    run_commands: list[str] = []
    for root in _workspace_python_roots(workspace_path, codebase_context):
        rel_dir = str(root.get("rel_dir") or "")
        if root.get("manage_py") and any(path.startswith(f"{rel_dir}/") if rel_dir else True for path in python_test_paths):
            run_commands.append(_prefix_command_for_dir(rel_dir, "python manage.py test"))
        elif root.get("pyproject") or any(PurePosixPath(path).name.lower() == "pytest.ini" and path.startswith(f"{rel_dir}/") for path in manifest_paths):
            run_commands.append(_prefix_command_for_dir(rel_dir, "pytest"))

    for manifest in _workspace_package_manifests(workspace_path, codebase_context):
        scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
        if scripts.get("test"):
            run_commands.append(_prefix_command_for_dir(str(manifest.get("rel_dir") or ""), _run_script_command(str(manifest.get("package_manager") or "npm"), "test")))

    run_command = "\n".join(_dedupe_json_items(run_commands)[:4]).strip()
    if python_test_paths and js_test_paths:
        unit = f"Backend tests live in {_format_path_list(python_test_paths, max_paths=1)} and frontend/unit specs also exist in {_format_path_list(js_test_paths, max_paths=1)}."
    elif python_test_paths:
        unit = f"Python test modules are present in {_format_path_list(python_test_paths, max_paths=2)}."
    elif js_test_paths:
        unit = f"JavaScript or TypeScript test files are present in {_format_path_list(js_test_paths, max_paths=2)}."
    else:
        unit = "No dedicated unit-test files were detected from the indexed repository paths."

    if integration_paths:
        integration = f"Integration-style coverage appears in {_format_path_list(integration_paths, max_paths=2)}."
    elif any("/api/tests" in path.lower() for path in python_test_paths):
        integration = f"API-oriented test coverage appears to live alongside backend tests in {_format_path_list([path for path in python_test_paths if '/api/tests' in path.lower()], max_paths=1)}."
    else:
        integration = "No separate integration-test directory was detected from indexed files."

    if e2e_paths:
        e2e = f"Browser or end-to-end coverage is present in {_format_path_list(e2e_paths, max_paths=2)}."
    else:
        e2e = "No dedicated browser-level or end-to-end suite was detected from the indexed repository."

    return {
        "unit": unit,
        "integration": integration,
        "e2e": e2e,
        "coverage_target": _detect_coverage_target(workspace_path, codebase_context),
        "run_command": run_command,
    }


def _scan_workspace_pattern_hits(workspace_path: Path, codebase_context: dict) -> dict[str, list[str]]:
    hits = {
        "shell_true": [],
        "csrf_exempt": [],
        "debug_true": [],
        "cors_allow_all": [],
        "secret_key_literal": [],
        "inmemory_channel_layer": [],
        "polling_loop": [],
        "sqlite": [],
    }
    candidate_paths: list[str] = []
    allowed_suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yml", ".yaml", ".ini", ".cfg"}
    for rel_path in _manifest_paths(codebase_context):
        lowered = rel_path.lower()
        file_name = PurePosixPath(rel_path).name.lower()
        suffix = PurePosixPath(rel_path).suffix.lower()
        if file_name not in {"manage.py", "package.json"} and suffix not in allowed_suffixes:
            continue
        if any(token in lowered for token in ("settings", "config", "consumer", "executor", "sandbox", "workspace", "runtime", "process", "channel", "views", "urls", "auth", "manage.py", "package.json", "pyproject.toml", "pytest.ini", "eslint", "tsconfig", "prettier", "mypy", "ruff")):
            candidate_paths.append(rel_path)
    if not candidate_paths:
        candidate_paths = _manifest_paths(codebase_context)[:120]

    for rel_path in _dedupe_json_items(candidate_paths)[:120]:
        text = _read_workspace_excerpt(workspace_path, rel_path, limit=20000)
        if not text:
            continue
        lowered = text.lower()
        if re.search(r"shell\s*=\s*True", text):
            hits["shell_true"].append(rel_path)
        if re.search(r"@csrf_exempt\b|csrf_exempt\(", text):
            hits["csrf_exempt"].append(rel_path)
        if re.search(r"(?m)^\s*DEBUG\s*=\s*True\b", text):
            hits["debug_true"].append(rel_path)
        if re.search(r"(?m)^\s*CORS_ALLOW_ALL_ORIGINS\s*=\s*True\b", text):
            hits["cors_allow_all"].append(rel_path)
        if re.search(r"(?m)^\s*SECRET_KEY\s*=\s*['\"][^'\"]+['\"]", text):
            hits["secret_key_literal"].append(rel_path)
        if "inmemorychannellayer" in lowered:
            hits["inmemory_channel_layer"].append(rel_path)
        if ("while true" in lowered or "for (;;)" in lowered) and ("asyncio.sleep" in lowered or "sleep(" in lowered or "setinterval(" in lowered):
            hits["polling_loop"].append(rel_path)
        if "db.sqlite3" in lowered or "sqlite3" in lowered:
            hits["sqlite"].append(rel_path)

    return {key: _dedupe_json_items(value) for key, value in hits.items()}


def _derive_code_quality_standards(workspace_path: Path, codebase_context: dict) -> list[dict]:
    standards: list[dict] = []

    def add(tool: str, purpose: str, config_file: str) -> None:
        if not tool or not config_file:
            return
        standards.append({
            "tool": tool,
            "purpose": purpose,
            "config_file": config_file,
        })

    manifest_paths = _manifest_paths(codebase_context)
    package_manifests = _workspace_package_manifests(workspace_path, codebase_context)

    for rel_path in manifest_paths:
        file_name = PurePosixPath(rel_path).name.lower()
        if file_name in {"eslint.config.js", "eslint.config.cjs", ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json"}:
            add("ESLint", "Lint rules for JavaScript or TypeScript source are configured here.", rel_path)
        elif file_name.startswith("tsconfig") and file_name.endswith(".json"):
            add("TypeScript", "Compiler settings here control type-checking, module resolution, and editor/tooling expectations.", rel_path)
        elif file_name in {".prettierrc", ".prettierrc.json", ".prettierrc.js", "prettier.config.js", "prettier.config.cjs"}:
            add("Prettier", "Formatting rules are defined here to keep source files and generated diffs consistent.", rel_path)
        elif file_name in {"pytest.ini", "tox.ini"}:
            add("Pytest", "Python test discovery and execution settings are configured here.", rel_path)
        elif file_name in {"mypy.ini"}:
            add("MyPy", "Static type-checking rules for Python modules are configured here.", rel_path)
        elif file_name in {"ruff.toml", ".ruff.toml"}:
            add("Ruff", "Python linting and formatting rules are configured here.", rel_path)

    for rel_path in manifest_paths:
        if PurePosixPath(rel_path).name.lower() not in {"pyproject.toml", "setup.cfg"}:
            continue
        text = _read_workspace_excerpt(workspace_path, rel_path, limit=16000)
        if not text:
            continue
        lowered = text.lower()
        if "[tool.ruff" in lowered or "[ruff" in lowered:
            add("Ruff", "Python linting or formatting rules are defined in this shared tool config.", rel_path)
        if "[tool.black" in lowered:
            add("Black", "Python formatting expectations are defined here.", rel_path)
        if "[tool.mypy" in lowered or "[mypy" in lowered:
            add("MyPy", "Python type-checking rules are defined here.", rel_path)
        if "[tool.pytest" in lowered or "[tool.pytest.ini_options" in lowered or "[pytest" in lowered:
            add("Pytest", "Python test discovery and execution settings are defined here.", rel_path)

    for manifest in package_manifests:
        scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
        path = str(manifest.get("path") or "")
        package_manager = str(manifest.get("package_manager") or "npm")
        if scripts.get("lint") and not any(item.get("tool") == "ESLint" for item in standards):
            add("Lint script", f"The package manifest exposes `{_run_script_command(package_manager, 'lint')}` as the repo's JavaScript/TypeScript lint entrypoint.", path)
        if scripts.get("typecheck") and not any(item.get("tool") == "TypeScript" for item in standards):
            add("Type checking", f"The package manifest exposes `{_run_script_command(package_manager, 'typecheck')}` for static type validation.", path)
        if scripts.get("format") and not any(item.get("tool") == "Prettier" for item in standards):
            add("Format script", f"The package manifest exposes `{_run_script_command(package_manager, 'format')}` for source formatting.", path)

    return _dedupe_json_items(standards)[:10]


def _derive_quality_guidance(project: Project, codebase_context: dict) -> dict:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return {
            "security_considerations": [],
            "performance_notes": [],
            "testing_strategy": {},
            "code_quality_standards": [],
        }

    hits = _scan_workspace_pattern_hits(workspace_path, codebase_context)
    api_reference = _blueprint_list(codebase_context.get("api_reference"))
    mutating_public = [
        f"{item.get('method')} {item.get('path')}"
        for item in api_reference
        if str(item.get("method") or "").upper() in {"POST", "PUT", "PATCH", "DELETE"} and not item.get("auth_required")
    ]
    csrf_exempt_public = [
        f"{item.get('method')} {item.get('path')}"
        for item in api_reference
        if str(item.get("method") or "").upper() in {"POST", "PUT", "PATCH", "DELETE"} and "csrf is exempted" in str(item.get("access") or "").lower()
    ]

    security: list[dict] = []
    if hits.get("shell_true"):
        security.append({
            "area": "Shell-based command execution",
            "severity": "high",
            "description": f"{_format_path_list(hits.get('shell_true') or [], max_paths=2)} uses subprocess calls with `shell=True`, so command text is expanded by the shell instead of running as structured argv.",
        })
    if hits.get("debug_true") or hits.get("cors_allow_all") or hits.get("secret_key_literal"):
        exposed_settings = []
        if hits.get("debug_true"):
            exposed_settings.append("`DEBUG = True`")
        if hits.get("cors_allow_all"):
            exposed_settings.append("`CORS_ALLOW_ALL_ORIGINS = True`")
        if hits.get("secret_key_literal"):
            exposed_settings.append("a literal `SECRET_KEY`")
        settings_paths = (hits.get("debug_true") or []) + (hits.get("cors_allow_all") or []) + (hits.get("secret_key_literal") or [])
        security.append({
            "area": "Development settings exposed",
            "severity": "high",
            "description": f"{_format_path_list(settings_paths, max_paths=2)} enables {', '.join(exposed_settings)}. Those defaults are convenient locally but should not be treated as production-safe runtime config.",
        })
    if mutating_public:
        severity = "high" if csrf_exempt_public else "medium"
        description = f"The routed API catalog shows mutating operations without explicit auth or permission markers, including {', '.join(f'`{item}`' for item in mutating_public[:3])}."
        if csrf_exempt_public:
            description += f" CSRF-exempt handlers were also detected for {', '.join(f'`{item}`' for item in csrf_exempt_public[:2])}."
        security.append({
            "area": "Mutating routes without explicit auth markers",
            "severity": severity,
            "description": description,
        })

    performance: list[dict] = []
    if hits.get("inmemory_channel_layer"):
        performance.append({
            "area": "In-memory channel layer",
            "impact": "high",
            "description": f"{_format_path_list(hits.get('inmemory_channel_layer') or [], max_paths=1)} uses `InMemoryChannelLayer`, which is fine for local development but does not support multi-process or horizontally scaled websocket delivery.",
        })
    if hits.get("polling_loop"):
        performance.append({
            "area": "Polling-based process or websocket loops",
            "impact": "medium",
            "description": f"{_format_path_list(hits.get('polling_loop') or [], max_paths=2)} contains long-running polling loops with sleep calls, which can become chatty under many concurrent sessions.",
        })
    if hits.get("sqlite"):
        performance.append({
            "area": "SQLite-backed local state",
            "impact": "medium",
            "description": f"{_format_path_list(hits.get('sqlite') or [], max_paths=1)} references SQLite-style local persistence, which is convenient for development but can become a bottleneck for concurrent write-heavy workloads.",
        })

    return {
        "security_considerations": _dedupe_json_items(security)[:6],
        "performance_notes": _dedupe_json_items(performance)[:6],
        "testing_strategy": _derive_testing_strategy(project, codebase_context),
        "code_quality_standards": _derive_code_quality_standards(workspace_path, codebase_context),
    }


def _summary_path_with_tokens(codebase_context: dict, *tokens: str) -> str:
    wanted = [str(token or "").strip().lower() for token in tokens if str(token or "").strip()]
    best_path = ""
    best_score = 0
    for item in _codebase_summary_pool(codebase_context, limit=200):
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if not path:
            continue
        haystack = " ".join(
            str(value)
            for value in [
                path,
                item.get("summary"),
                item.get("purpose"),
                item.get("why"),
                item.get("how"),
                " ".join(item.get("routes") or []),
                " ".join(item.get("data_models") or []),
                " ".join(item.get("role_hints") or []),
                item.get("file_kind"),
            ]
            if value
        ).lower()
        score = sum(1 for token in wanted if token in haystack)
        if score > best_score:
            best_score = score
            best_path = path
    return best_path


def _setup_commands_by_kind(setup_steps: list[dict], *kinds: str) -> list[str]:
    wanted = {str(kind or "").strip().lower() for kind in kinds if str(kind or "").strip()}
    commands: list[str] = []
    for item in setup_steps:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        command = str(item.get("command") or "").strip()
        if wanted and kind not in wanted:
            continue
        if command and command not in commands:
            commands.append(command)
    return commands


def _derive_knowledge_guidance(project: Project, codebase_context: dict, setup_guidance: dict, quality_guidance: dict) -> dict:
    api_reference = _blueprint_list(codebase_context.get("api_reference"))
    database_schema = _blueprint_list(codebase_context.get("database_schema"))
    database_sources = _blueprint_list(codebase_context.get("database_source_files"))
    top_areas = _top_repository_areas(codebase_context)
    summary_pool = _codebase_summary_pool(codebase_context, limit=220)
    summary_paths = [str(item.get("path") or "").replace("\\", "/").strip() for item in summary_pool if str(item.get("path") or "").strip()]
    setup_steps = _blueprint_list(setup_guidance.get("setup_steps"))
    testing_strategy = quality_guidance.get("testing_strategy") if isinstance(quality_guidance.get("testing_strategy"), dict) else {}
    table_names = {str(item.get("table") or "").strip() for item in database_schema if str(item.get("table") or "").strip()}
    workspace_ops = [item for item in api_reference if "/workspace/" in str(item.get("path") or "")]
    route_paths = {str(item.get("path") or "").strip() for item in api_reference}
    has_workspace_runtime = bool(workspace_ops) and any(any(token in path.lower() for token in ("sandbox", "executor", "workspace", "consumer")) for path in summary_paths)
    has_feature_pipeline = (
        "/api/projects/<project_id>/pipeline/action/" in route_paths
        or {"Feature", "FeatureHistory", "FeatureApproval"} <= table_names
        or any(any(token in path.lower() for token in ("feature", "pipeline")) for path in summary_paths)
    )
    has_chat_memory = (
        any("/chat/" in path for path in route_paths)
        and ({"ChatMessage", "WorkingMemory", "EpisodicMemory", "SemanticMemory"} & table_names
             or any(any(token in path.lower() for token in ("memory.py", "project_chat", "chat")) for path in summary_paths))
    )
    has_blueprint_pipeline = (
        any(any(token in str(item.get("path") or "") for token in ("/documentation/", "/agent/deep-docs", "/documentation/runs/")) for item in api_reference)
        or any(any(token in path.lower() for token in ("deep_documentation.py", "architect.py", "documentation.py")) for path in summary_paths)
    )

    concepts: list[dict] = []

    def add_concept(concept: str, explanation: str, why_important: str, related_code: str = "", related_concepts: list[str] | None = None) -> None:
        if not concept or not explanation:
            return
        concepts.append({
            "concept": concept,
            "explanation": explanation,
            "why_important": why_important,
            "related_code": related_code,
            "related_concepts": related_concepts or [],
        })

    if has_workspace_runtime:
        add_concept(
            "Managed workspace execution",
            "The codebase exposes workspace-oriented APIs for filesystem access, process I/O, or runtime control, so project execution is mediated by backend handlers rather than only by direct local commands.",
            "Changes to terminals, preview flows, editors, or runtime state usually cross both client code and backend workspace or process-management modules.",
            _summary_path_with_tokens(codebase_context, "workspace", "executor", "sandbox"),
            ["Process IO", "Runtime control"],
        )

    if has_feature_pipeline:
        add_concept(
            "Tracked delivery workflow",
            "The repository models work items or pipeline stages explicitly, with backend routes and persisted records coordinating approval, implementation, or status changes.",
            "When work-item behavior changes, the source of truth is usually shared between API handlers, workflow models, and any UI that reflects those stages.",
            _summary_path_with_tokens(codebase_context, "Feature", "pipeline", "approval"),
            ["Feature lifecycle", "Background implementation"],
        )

    if has_blueprint_pipeline:
        add_concept(
            "Generated documentation pipeline",
            "Repository reference or documentation sections are assembled from indexed codebase evidence and generation steps, instead of living only as hand-maintained markdown.",
            "When generated docs look wrong, the fix is usually in indexing, extraction, or enrichment logic before it is in the rendering layer.",
            _summary_path_with_tokens(codebase_context, "deep_documentation", "architect", "documentation"),
            ["Repository indexing", "Documentation runs"],
        )

    if has_chat_memory:
        add_concept(
            "Persistent conversational context",
            "The project stores chat or memory state in backend models, which lets assistant-style flows reuse earlier context instead of treating each interaction as isolated.",
            "Changes to assistant behavior often involve both request handling and the persistence or retrieval layer that supplies context.",
            _summary_path_with_tokens(codebase_context, "project_chat", "memory", "ChatMessage"),
            ["Chat sessions", "Semantic retrieval"],
        )

    if database_schema and len(concepts) < 5:
        add_concept(
            "Backend data model",
            f"Structured backend records are defined for entities such as {', '.join(sorted(table_names)[:4])}.",
            "Those models tell you what the system persists for projects, work items, chat, and long-lived context, so they are the safest starting point before changing request payloads or workflows.",
            str(database_sources[0] or "") if database_sources else _summary_path_with_tokens(codebase_context, "models", "data-model"),
            ["Persistence", "API contracts"],
        )

    if api_reference and len(concepts) < 4:
        groups = []
        for item in api_reference:
            group = str(item.get("group") or "").strip()
            if group and group not in groups:
                groups.append(group)
        first_source = (api_reference[0].get("source") or {}) if isinstance(api_reference[0], dict) else {}
        route_source = str(first_source.get("url_file") or first_source.get("view_file") or "") if isinstance(first_source, dict) else ""
        add_concept(
            "Routed API surface",
            f"The backend exposes {len(api_reference)} routed API operations grouped into areas such as {', '.join(groups[:4]) or 'the detected route groups'}.",
            "This is the fastest way to map URL shape to handler ownership before changing backend behavior or frontend fetch calls.",
            route_source or _summary_path_with_tokens(codebase_context, "urls", "api"),
            ["Request handling", "Backend services"],
        )

    if top_areas and len(concepts) < 4:
        add_concept(
            "Repository surface areas",
            f"The repository is split across top-level areas such as {', '.join(top_areas[:4])}.",
            "Reading the repo as distinct surfaces makes it much easier to find the right runtime, config, and ownership boundary before editing.",
            _summary_path_with_tokens(codebase_context, "readme", "package", "config"),
            ["Local development", "Code ownership"],
        )

    if not concepts:
        for item in _codebase_summary_pool(codebase_context, limit=12):
            path = str(item.get("path") or "")
            purpose = str(item.get("purpose") or "").strip()
            why = str(item.get("why") or "").strip()
            if not path or not purpose or not why:
                continue
            concept_name = str(item.get("symbol") or PurePosixPath(path).stem.replace("_", " ").replace("-", " ").title()).strip()
            add_concept(concept_name, purpose, why, path, [str(item.get("file_kind") or "source")])
            if len(concepts) >= 4:
                break

    faq: list[dict] = []
    install_commands = _setup_commands_by_kind(setup_steps, "install")
    migrate_commands = _setup_commands_by_kind(setup_steps, "migrate")
    runtime_commands = _setup_commands_by_kind(setup_steps, "runtime")
    validate_commands = _setup_commands_by_kind(setup_steps, "validate")

    if install_commands or runtime_commands:
        run_parts: list[str] = []
        if install_commands:
            run_parts.append(f"install dependencies with {' and '.join(f'`{command}`' for command in install_commands[:2])}")
        if migrate_commands:
            run_parts.append(f"apply migrations with {' and '.join(f'`{command}`' for command in migrate_commands[:1])}")
        if len(runtime_commands) > 1:
            run_parts.append(
                "run the main app processes in separate terminals using "
                + " and ".join(f"`{command}`" for command in runtime_commands[:2])
            )
        elif runtime_commands:
            run_parts.append(f"start the main runtime with `{runtime_commands[0]}`")
        faq.append({
            "question": "How do I run the project locally?",
            "answer": "Start by " + ", then ".join(run_parts) + "." if run_parts else "Follow the setup steps captured from the repo manifests, env templates, and runtime entrypoints.",
        })
    if has_workspace_runtime:
        faq.append({
            "question": "How does project execution work?",
            "answer": "The client-facing runtime features route through workspace or process-management APIs, while backend modules handle file access, process I/O, and runtime state changes.",
        })
    if has_blueprint_pipeline:
        faq.append({
            "question": "How are generated docs or repository references produced?",
            "answer": "They are assembled from indexed repository context and generation logic, then merged into the stored project documentation state. If a section looks wrong, inspect extraction and enrichment before only changing display copy.",
        })
    if has_feature_pipeline:
        faq.append({
            "question": "How do tracked work items move through the system?",
            "answer": "Work items flow through explicit pipeline or status transitions backed by routes and persisted records, so workflow behavior usually spans both API handlers and data models.",
        })
    if testing_strategy:
        run_command = str(testing_strategy.get("run_command") or "").strip()
        faq.append({
            "question": "How should I validate changes before merging?",
            "answer": f"{testing_strategy.get('unit') or 'Review the detected test layout.'} Use `{run_command}` as the primary validation command." if run_command else str(testing_strategy.get("unit") or "Review the detected test layout before merging."),
        })
    if api_reference:
        source_files = []
        for item in api_reference[:6]:
            source = item.get("source") or {}
            if isinstance(source, dict):
                for key in ("url_file", "view_file"):
                    value = str(source.get(key) or "").strip()
                    if value and value not in source_files:
                        source_files.append(value)
        faq.append({
            "question": "Where are the API routes and handlers defined?",
            "answer": f"Start with the routed API catalog and the source files behind it, such as {_format_path_list(source_files, max_paths=2)}. The URL wiring tells you which backend module actually owns each endpoint.",
        })
    elif database_schema:
        faq.append({
            "question": "Where are the main data models defined?",
            "answer": f"The structured backend schema currently comes from {_format_path_list([str(path) for path in database_sources], max_paths=2) or 'the detected model files'}. Start there before changing API payloads or persistence behavior.",
        })

    gotchas: list[str] = list(setup_guidance.get("gotchas") or [])
    if len(runtime_commands) > 1:
        gotchas.append("Full local development usually requires more than one long-running process, so backend and frontend changes may not appear until both runtimes are up.")
    if quality_guidance.get("security_considerations"):
        public_route_note = next(
            (
                item for item in quality_guidance.get("security_considerations") or []
                if "auth" in str(item.get("area") or "").lower() or "route" in str(item.get("area") or "").lower()
            ),
            None,
        )
        if public_route_note:
            gotchas.append("Several mutating backend routes do not advertise explicit auth decorators, so do not assume the local API surface is hardened for untrusted exposure.")
    if quality_guidance.get("performance_notes"):
        scale_note = next(
            (
                item for item in quality_guidance.get("performance_notes") or []
                if "channel layer" in str(item.get("area") or "").lower() or "polling" in str(item.get("area") or "").lower()
            ),
            None,
        )
        if scale_note:
            gotchas.append("Realtime or terminal streaming behavior is tuned for local, single-process development first, so scale assumptions can break before the UI makes that obvious.")
    if testing_strategy and "no dedicated browser-level" in str(testing_strategy.get("e2e") or "").lower():
        gotchas.append("No dedicated browser-level or end-to-end suite was detected, so UI regressions may still rely on manual verification.")

    return {
        "key_concepts": _dedupe_json_items(concepts)[:6],
        "faq": _dedupe_json_items(faq)[:6],
        "gotchas": _filter_design_doc_strings(_dedupe_similar_strings(_dedupe_json_items(gotchas)[:8])[:5]),
    }


def _testing_strategy_lines_for_design_doc(project: Project, blueprint: dict, codebase_context: dict) -> list[str]:
    strategy = blueprint.get("testing_strategy")
    strategy = strategy if isinstance(strategy, dict) else {}
    derived = _derive_testing_strategy(project, codebase_context)
    merged = dict(derived)
    merged.update({key: value for key, value in strategy.items() if value})

    def cleaned(value) -> str:
        text = str(value or "").strip()
        if not text or _looks_like_design_doc_template(text):
            return ""
        return text

    lines: list[str] = []
    unit = cleaned(merged.get("unit"))
    integration = cleaned(merged.get("integration"))
    e2e = cleaned(merged.get("e2e"))
    run_command = cleaned(merged.get("run_command"))
    if unit:
        lines.append(f"- Unit: {unit}")
    if integration:
        lines.append(f"- Integration: {integration}")
    if e2e:
        lines.append(f"- E2E: {e2e}")
    if run_command:
        lines.append(f"- Run command: `{run_command}`")
    if not lines:
        lines.append("- No evidence-backed testing strategy was detected from the indexed repository yet.")
    return lines


def _derive_repo_guidance(project: Project, codebase_context: dict) -> dict:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return {
            "setup_steps": [],
            "environment_variables": [],
            "onboarding_checklist": [],
            "gotchas": [],
        }

    readme_text = _read_workspace_excerpt(workspace_path, "README.md", "readme.md")
    contributing_text = _read_workspace_excerpt(workspace_path, "CONTRIBUTING.md", "contributing.md")
    security_text = _read_workspace_excerpt(workspace_path, "SECURITY.md", "security.md", limit=6000)
    command_evidence = _extract_shell_commands("\n".join([readme_text, contributing_text, security_text]))
    top_areas = _top_repository_areas(codebase_context)
    env_template_paths = _env_template_paths(workspace_path, codebase_context)
    environment_variables = _derive_environment_variables(workspace_path, codebase_context)
    package_manifests = _workspace_package_manifests(workspace_path, codebase_context)
    python_roots = _workspace_python_roots(workspace_path, codebase_context)
    testing_strategy = _derive_testing_strategy(project, codebase_context)
    setup_steps: list[dict] = []

    if env_template_paths:
        copy_commands = []
        for rel_path in env_template_paths[:3]:
            rel_dir = _normalize_rel_dir(PurePosixPath(rel_path).parent.as_posix())
            file_name = PurePosixPath(rel_path).name
            copy_commands.append(_prefix_command_for_dir(rel_dir, f"cp {file_name} .env"))
        setup_steps.append({
            "kind": "config",
            "step": "Create local environment files",
            "command": "\n".join(_dedupe_json_items(copy_commands)),
            "explanation": "The repo declares environment templates that should be copied or mirrored into local `.env` files before you start the runtime.",
            "os_note": "If `cp` is unavailable in your shell, use the platform equivalent copy command instead.",
        })
    elif environment_variables:
        setup_steps.append({
            "kind": "config",
            "step": "Review runtime configuration inputs",
            "command": "",
            "explanation": "No checked-in env template was detected, but the codebase references environment-driven configuration that should be reviewed before first run.",
            "os_note": "Use the detected environment variables and config files to decide which local values need to be supplied.",
        })

    for root in python_roots[:4]:
        rel_dir = str(root.get("rel_dir") or "")
        area = f"`{rel_dir}/`" if rel_dir else "the project root"
        if root.get("requirements"):
            setup_steps.append({
                "kind": "install",
                "step": f"Install Python dependencies for {area}",
                "command": _prefix_command_for_dir(rel_dir, f"python -m pip install -r {PurePosixPath(str(root.get('requirements'))).name}"),
                "explanation": "This repository section has an explicit Python requirements file that defines its runtime dependencies.",
                "os_note": "",
            })
        elif root.get("pyproject"):
            setup_steps.append({
                "kind": "install",
                "step": f"Install Python package metadata for {area}",
                "command": _prefix_command_for_dir(rel_dir, "python -m pip install -e ."),
                "explanation": "The Python project metadata is managed through `pyproject.toml`, so an editable install keeps local code and the environment aligned.",
                "os_note": "",
            })
        if root.get("manage_py") and str(root.get("framework") or "").lower() == "django":
            setup_steps.append({
                "kind": "migrate",
                "step": f"Apply Django migrations for {area}",
                "command": _prefix_command_for_dir(rel_dir, "python manage.py migrate"),
                "explanation": "A Django `manage.py` entrypoint was detected here, so migrations are part of the normal local boot sequence.",
                "os_note": "",
            })

    root_workspace_manifest = next((item for item in package_manifests if not item.get("rel_dir") and item.get("workspaces")), None)
    for manifest in package_manifests[:6]:
        rel_dir = str(manifest.get("rel_dir") or "")
        if root_workspace_manifest and rel_dir and manifest.get("path") != root_workspace_manifest.get("path"):
            continue
        package_manager = str(manifest.get("package_manager") or "npm")
        install_command = {
            "pnpm": "pnpm install",
            "yarn": "yarn install",
            "bun": "bun install",
            "npm": "npm install",
        }.get(package_manager, "npm install")
        area = f"`{rel_dir}/`" if rel_dir else "the project root"
        setup_steps.append({
            "kind": "install",
            "step": f"Install Node dependencies for {area}",
            "command": _prefix_command_for_dir(rel_dir, install_command),
            "explanation": "A package manifest was detected for this repo surface, so install the declared dependencies before running scripts from it.",
            "os_note": "",
        })

    dev_steps: list[dict] = []
    for root in python_roots[:4]:
        rel_dir = str(root.get("rel_dir") or "")
        area = f"`{rel_dir}/`" if rel_dir else "the project root"
        if root.get("manage_py") and str(root.get("framework") or "").lower() == "django":
            dev_steps.append({
                "kind": "runtime",
                "step": f"Start the Django runtime for {area}",
                "command": _prefix_command_for_dir(rel_dir, "python manage.py runserver"),
                "explanation": "The detected Python entrypoint is a Django management command, so `runserver` is the local application runtime.",
                "os_note": "",
            })

    for manifest in package_manifests[:6]:
        scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
        package_manager = str(manifest.get("package_manager") or "npm")
        rel_dir = str(manifest.get("rel_dir") or "")
        area = f"`{rel_dir}/`" if rel_dir else "the project root"
        chosen_script = ""
        for key in ("dev", "start", "serve", "preview", "watch"):
            if scripts.get(key):
                chosen_script = key
                break
        if not chosen_script:
            for key in ("build", "compile"):
                if scripts.get(key):
                    chosen_script = key
                    break
        if chosen_script:
            dev_steps.append({
                "kind": "runtime",
                "step": f"Run the main package script for {area}",
                "command": _prefix_command_for_dir(rel_dir, _run_script_command(package_manager, chosen_script)),
                "explanation": "This command comes from the detected package manifest scripts and is the best evidence-backed entrypoint for that repo surface.",
                "os_note": "",
            })

    if not setup_steps and command_evidence:
        install_command = _pick_command(command_evidence, "install") or _pick_command(command_evidence, "setup")
        if install_command:
            setup_steps.append({
                "kind": "install",
                "step": "Install dependencies",
                "command": install_command,
                "explanation": "This command was extracted directly from the repository documentation or setup notes.",
                "os_note": "",
            })
    if not dev_steps and command_evidence:
        dev_command = _pick_command(command_evidence, "dev") or _pick_command(command_evidence, "start") or _pick_command(command_evidence, "run")
        if dev_command:
            dev_steps.append({
                "kind": "runtime",
                "step": "Start the local runtime",
                "command": dev_command,
                "explanation": "This command was extracted directly from the repository documentation or onboarding notes.",
                "os_note": "",
            })

    setup_steps.extend(dev_steps[:4])

    docs_to_read = []
    for filename in ("README.md", "CONTRIBUTING.md", "VISION.md", "AGENTS.md", "SECURITY.md"):
        if (workspace_path / filename).exists():
            docs_to_read.append(filename)
    for item in _public_instruction_files(codebase_context):
        path = str(item.get("path") or "").replace("\\", "/").strip()
        if path and path not in docs_to_read:
            docs_to_read.append(path)

    onboarding_checklist: list[dict] = []
    if docs_to_read:
        onboarding_checklist.append({
            "task": "Read the root project docs first",
            "category": "codebase",
            "estimated_time": "15 min",
            "why_important": "Top-level docs and instruction files usually explain product context, contribution rules, and setup order faster than reading source files cold.",
            "instructions": f"Start with {', '.join(docs_to_read[:4])}.",
        })
    if top_areas:
        onboarding_checklist.append({
            "task": "Map the major repo areas",
            "category": "codebase",
            "estimated_time": "10 min",
            "why_important": "The indexed repository spans multiple top-level surfaces, so it helps to understand the boundaries before choosing where to edit.",
            "instructions": f"Begin with {', '.join(top_areas[:5])} and then open the repo map for file-level detail.",
        })
    if environment_variables or security_text:
        onboarding_checklist.append({
            "task": "Review environment and security defaults",
            "category": "environment",
            "estimated_time": "10 min",
            "why_important": "The repo declares environment-driven configuration and may include local-only security defaults that should be understood before first run.",
            "instructions": "Compare the detected env templates with SECURITY.md or settings files before enabling external integrations or remote access.",
        })
    if setup_steps:
        instructions_parts = [
            f"`{command}`"
            for command in (
                _setup_commands_by_kind(setup_steps, "install")[:2]
                + _setup_commands_by_kind(setup_steps, "migrate")[:1]
                + _setup_commands_by_kind(setup_steps, "runtime")[:2]
            )
            if command
        ]
        onboarding_checklist.append({
            "task": "Use the documented source workflow",
            "category": "tools",
            "estimated_time": "15 min",
            "why_important": "Following the detected setup sequence keeps local installs, migrations, and runtime entrypoints aligned with the repo's actual manifests and scripts.",
            "instructions": "Follow this order: " + " then ".join(instructions_parts) if instructions_parts else "Use the documented source workflow from the README.",
        })
    if testing_strategy:
        run_command = str(testing_strategy.get("run_command") or "").strip()
        onboarding_checklist.append({
            "task": "Learn the validation command early",
            "category": "processes",
            "estimated_time": "10 min",
            "why_important": "Knowing the test or validation entrypoint up front makes it easier to work in smaller safe changes.",
            "instructions": f"Use `{run_command}` before opening a PR." if run_command else str(testing_strategy.get("unit") or "Review the detected test layout before opening a PR."),
        })
    if contributing_text:
        onboarding_checklist.append({
            "task": "Follow the contributor rules before opening a PR",
            "category": "processes",
            "estimated_time": "10 min",
            "why_important": "The contribution guide usually captures repo-specific expectations around testing, review, and change scope.",
            "instructions": "Check CONTRIBUTING.md for the review and validation expectations before shipping changes.",
        })

    gotchas: list[str] = []
    if root_workspace_manifest:
        gotchas.append("The repository appears to use a workspace-aware package manager at the root, so running isolated installs inside child packages can leave the dependency graph out of sync.")
    if len(env_template_paths) > 1:
        gotchas.append(f"Configuration is split across multiple env templates: {_format_path_list(env_template_paths, max_paths=3)}.")
    if python_roots and package_manifests:
        gotchas.append("This repository mixes Python and Node-based surfaces, so setup and validation span more than one toolchain.")
    if len(dev_steps) > 1:
        gotchas.append("Local development appears to require multiple long-running commands or services, so one terminal session may not be enough for the full stack.")
    if "wsl2" in readme_text.lower():
        gotchas.append("The README references WSL2 for Windows setup, so native Windows commands may not exactly match the documented path.")

    return {
        "setup_steps": _dedupe_json_items(setup_steps)[:8],
        "environment_variables": _dedupe_json_items(environment_variables)[:30],
        "onboarding_checklist": _dedupe_json_items(onboarding_checklist)[:6],
        "gotchas": _filter_design_doc_strings(_dedupe_similar_strings(_dedupe_json_items(gotchas)[:8])[:6]),
    }


def _merge_by_key(llm_items, pipeline_items, key_fn, prefer='llm'):
    """Union two lists of dicts, deduplicating by key_fn.

    On same-key conflict: merge subfields so the secondary source only fills
    gaps in the preferred entry.
    """
    primary_items = llm_items if prefer == 'llm' else pipeline_items
    secondary_items = pipeline_items if prefer == 'llm' else llm_items
    by_key: dict[Any, dict] = {}

    for item in (primary_items or []):
        if not isinstance(item, dict):
            continue
        key = key_fn(item)
        if key:
            by_key[key] = dict(item)

    for item in (secondary_items or []):
        if not isinstance(item, dict):
            continue
        key = key_fn(item)
        if not key:
            continue
        if key not in by_key:
            by_key[key] = dict(item)
            continue
        existing = by_key[key]
        for sub_key, sub_val in item.items():
            if sub_key not in existing or not existing[sub_key]:
                existing[sub_key] = sub_val

    return list(by_key.values())


def _merge_repo_guidance_into_blueprint(project: Project, blueprint: dict, codebase_context: dict) -> dict:
    blueprint = dict(blueprint or {})
    setup_guidance = _derive_repo_guidance(project, codebase_context)
    quality_guidance = _derive_quality_guidance(project, codebase_context)
    knowledge_guidance = _derive_knowledge_guidance(project, codebase_context, setup_guidance, quality_guidance)

    blueprint['environment_variables'] = _merge_by_key(
        blueprint.get('environment_variables') or [],
        setup_guidance.get('environment_variables') or [],
        key_fn=lambda x: x.get('name', '').upper() if isinstance(x, dict) else '',
        prefer='llm',
    )

    blueprint['setup_steps'] = _merge_by_key(
        blueprint.get('setup_steps') or [],
        setup_guidance.get('setup_steps') or [],
        key_fn=lambda x: (x.get('kind', '') + ':' + x.get('command', '')[:60]).lower() if isinstance(x, dict) else '',
        prefer='llm',
    )

    for field in ("onboarding_checklist",):
        llm_val = blueprint.get(field)
        pipeline_val = setup_guidance.get(field)
        if llm_val:
            pass
        elif pipeline_val:
            blueprint[field] = pipeline_val

    for field in ("security_considerations", "performance_notes", "code_quality_standards"):
        llm_val = blueprint.get(field)
        pipeline_val = quality_guidance.get(field)
        if llm_val:
            pass
        elif pipeline_val:
            blueprint[field] = pipeline_val

    llm_testing = blueprint.get('testing_strategy')
    pipeline_testing = quality_guidance.get('testing_strategy')
    if isinstance(llm_testing, dict) and isinstance(pipeline_testing, dict):
        for sub_key in ('unit', 'integration', 'e2e', 'coverage_target', 'run_command'):
            if not llm_testing.get(sub_key) and pipeline_testing.get(sub_key):
                llm_testing[sub_key] = pipeline_testing[sub_key]
    elif not llm_testing and pipeline_testing:
        blueprint['testing_strategy'] = pipeline_testing

    for field in ("key_concepts", "faq", "gotchas"):
        llm_val = blueprint.get(field)
        pipeline_val = knowledge_guidance.get(field)
        if llm_val:
            pass
        elif pipeline_val:
            blueprint[field] = pipeline_val
    return blueprint


def _resolve_blueprint_path(workspace_path: Path | None, raw_path: str, expect_dir: bool = False) -> Path | None:
    if not workspace_path:
        return None

    raw = str(raw_path or "").strip()
    if raw in {".", "./", ".//"}:
        return workspace_path.resolve() if (workspace_path.is_dir() or expect_dir) else None
    if not raw:
        return None

    candidates: list[Path] = []
    path_obj = Path(raw)
    if path_obj.is_absolute():
        candidates.append(path_obj)

    normalized = raw.replace("\\", "/").strip()
    variants = [normalized]
    if normalized.startswith("./"):
        variants.append(normalized[2:])
    for variant in variants:
        if not variant:
            continue
        candidates.append(workspace_path / variant)
        if variant.startswith(f"{workspace_path.name}/"):
            candidates.append(workspace_path / variant[len(workspace_path.name) + 1 :])

    workspace_root = workspace_path.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(workspace_root)
        except Exception:
            continue
        if expect_dir and resolved.is_dir():
            return resolved
        if not expect_dir and resolved.exists():
            return resolved
    return None


def _is_valid_env_var_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]*", str(name or "").strip()))


def _placeholder_environment_variable(name: str) -> dict[str, Any]:
    category = _infer_env_category(name)
    description_prefix = {
        "frontend": "Frontend-facing environment variable referenced by the client bundle or browser runtime.",
        "ai": "AI or model-provider configuration referenced in the codebase.",
        "secret": "Credential or secret referenced in the codebase.",
        "database": "Database or persistence configuration referenced in the codebase.",
        "auth": "Authentication or trust-boundary setting referenced in the codebase.",
        "storage": "Storage or upload configuration referenced in the codebase.",
        "runtime": "Runtime or network setting referenced in the codebase.",
        "config": "Environment-driven configuration referenced in the codebase.",
    }.get(category, "Environment-driven configuration referenced in the codebase.")
    return {
        "name": name,
        "description": f"{description_prefix} Detailed usage was not fully resolved from the scanned evidence.",
        "required": False,
        "default": "No default detected",
        "example": "",
        "category": category,
    }


def _finalize_blueprint_environment_variables(workspace_path: Path | None, blueprint: dict, codebase_context: dict) -> list[dict]:
    llm_items: list[dict] = []
    for item in _blueprint_list(blueprint.get("environment_variables")):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().upper()
        if not _is_valid_env_var_name(name):
            continue
        cleaned = dict(item)
        cleaned["name"] = name
        cleaned["category"] = str(cleaned.get("category") or _infer_env_category(name))
        llm_items.append(cleaned)

    pipeline_items: list[dict] = []
    if workspace_path:
        for item in _derive_environment_variables(workspace_path, codebase_context):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip().upper()
            if not _is_valid_env_var_name(name):
                continue
            cleaned = dict(item)
            cleaned["name"] = name
            cleaned["category"] = str(cleaned.get("category") or _infer_env_category(name))
            pipeline_items.append(cleaned)

    merged = _merge_by_key(
        llm_items,
        pipeline_items,
        key_fn=lambda item: str(item.get("name") or "").strip().upper() if isinstance(item, dict) else "",
        prefer="llm",
    )

    seen = {
        str(item.get("name") or "").strip().upper()
        for item in merged
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }
    for raw_name in codebase_context.get("env_var_names") or []:
        name = str(raw_name or "").strip().upper()
        if not _is_valid_env_var_name(name) or name in seen:
            continue
        seen.add(name)
        merged.append(_placeholder_environment_variable(name))

    return _dedupe_json_items(merged)[:60]


def _setup_step_semantic_key(item: dict) -> str:
    command = re.sub(r"\s+", " ", str(item.get("command") or "").strip().lower())
    step = re.sub(r"\s+", " ", str(item.get("step") or "").strip().lower())
    kind = str(item.get("kind") or "").strip().lower()

    if "python -m venv" in command or "uv venv" in command:
        return "create-venv"
    if "activate" in command and ("venv" in command or ".venv" in command):
        return "activate-venv"
    if re.search(r"\b(python\s+-m\s+pip|pip|poetry|uv\s+pip)\s+install\b", command):
        return "python-install"
    if re.search(r"\b(npm|pnpm|yarn)\s+install\b", command):
        return "node-install"
    if "manage.py migrate" in command:
        return "django-migrate"
    if "manage.py runserver" in command:
        return "django-runserver"
    if re.search(r"\b(npm|pnpm|yarn)\s+(run\s+)?dev\b", command):
        return "node-dev"
    if re.search(r"\b(npm|pnpm|yarn)\s+(run\s+)?test\b", command) or "manage.py test" in command or "pytest" in command:
        return "validate"
    if kind and command:
        return f"{kind}:{command[:80]}"
    if command:
        return command[:80]
    if step:
        return f"step:{step[:80]}"
    return ""


def _setup_step_score(item: dict, readme_excerpt: str) -> int:
    score = 0
    command = re.sub(r"\s+", " ", str(item.get("command") or "").strip().lower())
    readme_lower = str(readme_excerpt or "").lower()

    if not str(item.get("kind") or "").strip():
        score += 3
    if command and command in readme_lower:
        score += 3
    if str(item.get("explanation") or "").strip():
        score += 1
    if str(item.get("step") or "").strip():
        score += 1
    if command == "python -m pip install -e ." and "python -m pip install -e ." not in readme_lower:
        score -= 3
    return score


def _normalize_setup_steps_for_blueprint(setup_steps: list[dict], readme_excerpt: str) -> list[dict]:
    winners: dict[str, tuple[int, dict]] = {}
    order: list[str] = []

    for raw_item in setup_steps or []:
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        if not str(item.get("command") or "").strip() and not str(item.get("step") or "").strip():
            continue
        key = _setup_step_semantic_key(item)
        if not key:
            continue
        score = _setup_step_score(item, readme_excerpt)
        existing = winners.get(key)
        if existing is None:
            winners[key] = (score, item)
            order.append(key)
            continue
        existing_score, existing_item = existing
        if score > existing_score:
            winners[key] = (score, item)
            continue
        if score == existing_score and len(json.dumps(item, sort_keys=True)) > len(json.dumps(existing_item, sort_keys=True)):
            winners[key] = (score, item)

    normalized: list[dict] = []
    seen_entries: set[tuple[str, str]] = set()
    for key in order:
        item = winners[key][1]
        dedupe_key = (
            re.sub(r"\s+", " ", str(item.get("command") or "").strip().lower()),
            re.sub(r"\s+", " ", str(item.get("step") or "").strip().lower()),
        )
        if dedupe_key in seen_entries:
            continue
        seen_entries.add(dedupe_key)
        normalized.append(item)
    return normalized[:12]


def _normalize_repository_map_entries(items: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        area = str(cleaned.get("area") or "").replace("\\", "/").strip()
        if area in {".", "./", ".//", "Project Root/", "Project Root"}:
            cleaned["area"] = "Project Root"
        elif area:
            cleaned["area"] = f"{area.rstrip('/')}/"
        normalized.append(cleaned)
    return normalized


def _finalize_blueprint_document(project: Project, blueprint: dict, codebase_context: dict) -> dict:
    finalized = dict(blueprint or {})
    workspace_path = _project_workspace_path(project)

    key_components: list[dict] = []
    for item in _blueprint_list(finalized.get("key_components")):
        if not isinstance(item, dict):
            continue
        if workspace_path and not _resolve_blueprint_path(workspace_path, str(item.get("file_path") or "")):
            continue
        key_components.append(item)
    finalized["key_components"] = key_components

    services: list[dict] = []
    for item in _blueprint_list(finalized.get("services")):
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        key_files: list[str] = []
        for raw_path in item.get("key_files") or []:
            if not isinstance(raw_path, str):
                continue
            for separator in (" - ", " – ", " — ", " : "):
                if separator in raw_path:
                    raw_path = raw_path.split(separator)[0].strip()
                    break
            path_part = raw_path.strip()
            basename = path_part.replace("\\", "/").split("/")[-1] if path_part else ""
            looks_like_path = bool(path_part) and ("/" in path_part or "\\" in path_part or "." in basename)
            if not looks_like_path:
                continue
            if workspace_path and not _resolve_blueprint_path(workspace_path, path_part):
                continue
            key_files.append(path_part.replace("\\", "/"))
        cleaned["key_files"] = key_files
        services.append(cleaned)
    finalized["services"] = services

    directory_guide: list[dict] = []
    for item in _blueprint_list(finalized.get("directory_guide")):
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        raw_path = str(cleaned.get("path") or "").replace("\\", "/").strip()
        if raw_path in {".", "./", ".//", ""}:
            normalized_path = "./"
        else:
            normalized_path = f"{raw_path.rstrip('/')}/"
        if workspace_path and not _resolve_blueprint_path(workspace_path, normalized_path, expect_dir=True):
            continue
        cleaned["path"] = normalized_path
        directory_guide.append(cleaned)
    finalized["directory_guide"] = directory_guide

    finalized["repository_map"] = _normalize_repository_map_entries(_blueprint_list(finalized.get("repository_map")))
    finalized["environment_variables"] = _finalize_blueprint_environment_variables(workspace_path, finalized, codebase_context)
    finalized["setup_steps"] = _normalize_setup_steps_for_blueprint(
        _blueprint_list(finalized.get("setup_steps")),
        str(finalized.get("readme_excerpt") or codebase_context.get("readme_excerpt") or ""),
    )

    api_endpoints: list[dict] = []
    seen_endpoints: set[tuple[str, str]] = set()
    for item in _blueprint_list(finalized.get("api_endpoints")):
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        params = cleaned.get("path_params")
        if isinstance(params, list):
            seen_params: set[str] = set()
            deduped_params: list[Any] = []
            for param in params:
                if isinstance(param, dict):
                    param_key = str(param.get("name") or "").strip().lower()
                else:
                    param_key = str(param or "").strip().lower()
                if not param_key or param_key in seen_params:
                    continue
                seen_params.add(param_key)
                deduped_params.append(param)
            cleaned["path_params"] = deduped_params
        path = str(cleaned.get("path") or "").strip()
        norm_path = path.rstrip("/") if len(path) > 1 else path
        endpoint_key = (str(cleaned.get("method") or "GET").upper(), norm_path)
        if endpoint_key in seen_endpoints:
            continue
        seen_endpoints.add(endpoint_key)
        api_endpoints.append(cleaned)
    finalized["api_endpoints"] = api_endpoints

    repo_tree = str(finalized.get("repo_tree") or "")
    if repo_tree:
        finalized["repo_tree"] = repo_tree.replace("project root/", "./").replace(".//", "./")

    return finalized


def _first_sentence(text: str, fallback: str = "") -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized:
        return fallback
    parts = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)
    return (parts[0] or normalized).strip()


def _confirmed_overview_doc_paths(blueprint: dict, codebase_context: dict, limit: int = 8) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        normalized = str(path or "").replace("\\", "/").strip()
        if not normalized or normalized in seen or _is_devhub_internal_path(normalized):
            return
        seen.add(normalized)
        paths.append(normalized)

    if str(blueprint.get('readme_excerpt') or '').strip():
        add('README.md')
    for item in _blueprint_list(blueprint.get('instruction_files')):
        if isinstance(item, dict):
            add(str(item.get('path') or ''))
    for item in _blueprint_list(codebase_context.get('manifest')):
        path = str(item.get('path') or '').replace("\\", "/").strip()
        lower = path.lower()
        if not path:
            continue
        if lower.startswith('docs/') or '/docs/' in lower:
            add(path)
            continue
        if lower in {'readme.md', 'contributing.md', 'security.md', 'vision.md', 'agents.md'}:
            add(path)
    return paths[:limit]


def _is_speculative_risk_text(text: str) -> bool:
    lowered = str(text or '').strip().lower()
    if not lowered:
        return True
    return any(token in lowered for token in ('not confirmed', 'might ', 'may ', 'could ', 'appears ', 'seems '))


def _design_doc_problem_statement(project: Project, blueprint: dict) -> list[str]:
    # Use the full project_summary (not just first sentence) for the opening description
    full_summary = str(blueprint.get('project_summary') or '').strip()
    description = str(project.description or '').strip()

    # Prefer project description if it reads as a product description (not a workflow step)
    # Heuristic: workflow text starts with verbs like "When", "After", "First", "Click"
    workflow_starters = ('when ', 'after ', 'first ', 'click', 'submit', 'upload', 'navigate', 'go to', 'step')
    desc_is_workflow = any(description.lower().startswith(s) for s in workflow_starters)

    if description and not desc_is_workflow:
        opening = description
        if full_summary and full_summary.lower() not in description.lower() and len(full_summary) > 40:
            opening = f"{description}\n\n{full_summary}"
    else:
        opening = full_summary or 'The blueprint does not yet contain a grounded product problem statement.'

    services = [item for item in _blueprint_list(blueprint.get('services')) if isinstance(item, dict)]
    endpoints = [item for item in _blueprint_list(blueprint.get('api_endpoints')) if isinstance(item, dict)]
    schema = [item for item in _blueprint_list(blueprint.get('database_schema')) if isinstance(item, dict)]

    bullets: list[str] = []
    service_names = [str(item.get('name') or '').strip() for item in services if str(item.get('name') or '').strip()]
    if service_names:
        bullets.append(f"Implemented as: {', '.join(service_names[:4])}.")
    if endpoints:
        auth_count = sum(1 for ep in endpoints if ep.get('auth_required'))
        bullets.append(f"Backend exposes {len(endpoints)} API endpoints, {auth_count} of which require authentication.")
    if schema:
        model_names = [str(item.get('name') or '').strip() for item in schema[:6] if str(item.get('name') or '').strip()]
        if model_names:
            bullets.append(f"Core data models include: {', '.join(model_names)}.")
    return [opening, '', *(_markdown_bullets(bullets, 'No grounded problem signals were extracted beyond the repository structure.'))]


def _design_doc_goal_lines(blueprint: dict) -> tuple[list[str], list[str]]:
    goals: list[str] = []
    non_goals: list[str] = []

    # Goals derived from the architecture overview and services
    arch = str(blueprint.get('architecture_overview') or '').strip()
    if arch:
        # Use up to two sentences from the architecture overview as the first goal
        arch_sentences = [s.strip() for s in arch.replace('\n', ' ').split('.') if len(s.strip()) > 20]
        if arch_sentences:
            goals.append(arch_sentences[0] + '.')

    services = [item for item in _blueprint_list(blueprint.get('services')) if isinstance(item, dict)]
    for svc in services[:4]:
        name = str(svc.get('name') or '').strip()
        svc_type = str(svc.get('type') or '').strip()
        desc_first = _first_sentence(svc.get('description'))
        if name and desc_first:
            goals.append(f"{name} ({svc_type}): {desc_first}")

    endpoints = [item for item in _blueprint_list(blueprint.get('api_endpoints')) if isinstance(item, dict)]
    if endpoints:
        non_goals.append(
            f"Complete response schema and status-code contracts are not yet authoritative for all {len(endpoints)} endpoints — "
            "callers should verify against live responses until endpoint docs are fully annotated."
        )

    testing = blueprint.get('testing_strategy') if isinstance(blueprint.get('testing_strategy'), dict) else {}
    run_command = str(testing.get('run_command') or '').strip()
    if run_command:
        goals.append(f"Local validation: `{run_command}`.")

    non_goals.append('Features or endpoints with no repository evidence are out of scope for this design document.')
    return goals[:6], non_goals[:3]


def _api_design_summary_lines(endpoints: list[dict], routes: list[Any]) -> list[str]:
    if not endpoints:
        return _markdown_bullets(routes, 'No routes or endpoints were clearly detected.')

    grouped: dict[str, dict[str, Any]] = {}
    for item in endpoints:
        if not isinstance(item, dict):
            continue
        path = str(item.get('path') or '/').strip() or '/'
        method = str(item.get('method') or 'GET').upper()
        segments = [seg for seg in path.strip('/').split('/') if seg and not seg.startswith('<') and not seg.startswith('{')]
        if segments and segments[0] == 'api':
            segments = segments[1:]
        if segments:
            prefix = '/' + '/'.join(segments[:2])
        else:
            prefix = '/api' if path.startswith('/api') else '/'
        bucket = grouped.setdefault(prefix, {'count': 0, 'methods': set(), 'auth': 0})
        bucket['count'] += 1
        bucket['methods'].add(method)
        if item.get('auth_required'):
            bucket['auth'] += 1

    lines = [f"Detected {len(endpoints)} routed endpoints across the indexed backend.", '']
    bullets = []
    for prefix, bucket in sorted(grouped.items(), key=lambda entry: (-int(entry[1]['count']), entry[0]))[:10]:
        methods = ', '.join(sorted(bucket['methods']))
        auth_note = 'mostly authenticated' if bucket['auth'] >= max(1, bucket['count'] // 2) else 'mixed auth visibility'
        bullets.append(f"`{prefix}/*`: {bucket['count']} endpoints across {methods}; {auth_note}.")
    lines.extend(_markdown_bullets(bullets, 'No API groupings were available.'))
    return lines


def _render_blueprint_design_document(project: Project, blueprint: dict, codebase_context: dict, feature_summary: str) -> tuple[str, list[dict]]:
    generated_on = timezone.now().strftime('%Y-%m-%d')
    title = project.name or 'Project'
    services = _blueprint_list(blueprint.get('services'))
    endpoints = _blueprint_list(blueprint.get('api_endpoints'))
    schema = _blueprint_list(blueprint.get('database_schema'))
    key_components = _blueprint_list(blueprint.get('key_components'))
    directories = _blueprint_list(blueprint.get('directory_guide'))
    workflows = _blueprint_list(blueprint.get('common_workflows'))
    setup_steps = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('setup_steps')), ('step', 'command', 'explanation', 'os_note'))
    env_vars = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('environment_variables')), ('name', 'description', 'default', 'example', 'category'))
    security = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('security_considerations')), ('area', 'description', 'severity'))
    performance = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('performance_notes')), ('area', 'description', 'impact'))
    integrations = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('integration_points')), ('name', 'type', 'description', 'evidence'))
    onboarding = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('onboarding_checklist')), ('task', 'instructions', 'why_important', 'category'))
    concepts = _filter_design_doc_dict_items(_blueprint_list(blueprint.get('key_concepts')), ('concept', 'explanation', 'why_important', 'why_it_matters'))
    gotchas = _filter_design_doc_strings(_blueprint_list(blueprint.get('gotchas')))
    feature_inventory = _blueprint_list(blueprint.get('feature_inventory'))
    tech_stack_details = _blueprint_list(blueprint.get('tech_stack_details'))
    change_guide = _blueprint_list(blueprint.get('change_guide'))
    sequence_flows = _blueprint_list(blueprint.get('sequence_flows'))
    pipeline = blueprint.get('sdlc_pipeline') or {}
    routes = _blueprint_list(codebase_context.get('routes'))
    data_models = _blueprint_list(codebase_context.get('data_models'))
    testing_strategy_lines = _testing_strategy_lines_for_design_doc(project, blueprint, codebase_context)

    sections = []

    sections.append({
        'id': 'executive-summary',
        'title': 'Executive Summary',
        'body': [
            _blueprint_text(blueprint.get('project_summary'), project.description or 'No project summary has been generated yet.'),
            '',
            _blueprint_text(blueprint.get('architecture_overview')),
        ],
    })

    sections.append({
        'id': 'problem-statement',
        'title': 'Problem Statement',
        'body': _design_doc_problem_statement(project, blueprint),
    })

    goal_lines, non_goal_lines = _design_doc_goal_lines(blueprint)
    sections.append({
        'id': 'goals-non-goals',
        'title': 'Goals & Non-Goals',
        'body': [
            'Goals inferred from the current repository evidence:',
            *_markdown_bullets(goal_lines, 'No explicit goals were captured in the blueprint yet.'),
            '',
            'Non-goals and boundaries:',
            *_markdown_bullets(non_goal_lines, 'Non-goals were not clearly documented.'),
        ],
    })

    architecture_body = [
        _blueprint_text(blueprint.get('architecture_overview')),
        '',
        'Repository shape:',
        *_markdown_bullets(
            [f"{item.get('area')}: {item.get('description')}" for item in _blueprint_list(blueprint.get('repository_map')) if isinstance(item, dict)],
            'Repository area mapping is not available.',
        ),
    ]
    if blueprint.get('mermaid_architecture'):
        architecture_body.extend(['', '```mermaid', blueprint.get('mermaid_architecture', ''), '```'])
    sections.append({
        'id': 'system-architecture-overview',
        'title': 'System Architecture Overview',
        'body': architecture_body,
    })

    sections.append({
        'id': 'technology-stack',
        'title': 'Technology Stack',
        'body': [
            *(
                [
                    f"- `{item.get('tech', 'Unknown')}`: {item.get('purpose') or item.get('why_chosen') or 'No purpose documented.'}"
                    for item in tech_stack_details if isinstance(item, dict)
                ] or _markdown_bullets(project.tech_stack or [], 'No technology stack details were captured.')
            )
        ],
    })

    sections.append({
        'id': 'component-design',
        'title': 'Component Design',
        'body': [
            'Services and major modules:',
            *_markdown_bullets(
                [
                    f"{item.get('name', 'Unnamed service')} ({item.get('type', 'unknown')}): {item.get('description') or 'No description available.'}"
                    for item in services if isinstance(item, dict)
                ],
                'No service-level component design was detected.',
            ),
            '',
            'Key files and components:',
            *_markdown_bullets(
                [
                    f"{item.get('file_path', 'unknown file')}: {item.get('purpose') or item.get('summary') or 'No purpose available.'}"
                    for item in key_components if isinstance(item, dict)
                ],
                'No key components were identified.',
            ),
        ],
    })

    data_body = []
    if schema:
        data_body.extend(
            _markdown_bullets(
                [
                    f"{item.get('table', 'Unnamed entity')}: {item.get('description') or item.get('relationships') or 'No entity detail available.'}"
                    for item in schema if isinstance(item, dict)
                ],
                'No schema entities were documented.',
            )
        )
    else:
        data_body.extend(_markdown_bullets(data_models, 'No models or typed entities were clearly detected.'))
    sections.append({
        'id': 'data-model',
        'title': 'Data Model',
        'body': data_body,
    })

    api_body = []
    if endpoints:
        api_body.extend(_api_design_summary_lines(endpoints, routes))
    else:
        api_body.extend(_markdown_bullets(routes, 'No routes or endpoints were clearly detected.'))
    sections.append({
        'id': 'api-design',
        'title': 'API Design',
        'body': api_body,
    })

    workflow_body = [
        'Common workflows:',
        *_markdown_bullets(
            [
                f"{item.get('title', 'Workflow')}: {', '.join(_blueprint_list(item.get('steps'))[:5])}"
                for item in workflows if isinstance(item, dict)
            ],
            'No common workflows were documented.',
        ),
        '',
        'Pipeline and execution flow:',
        *_markdown_bullets(
            [stage.get('name') for stage in _blueprint_list(pipeline.get('stages')) if isinstance(stage, dict)],
            'No explicit SDLC stages were documented.',
        ),
    ]
    if blueprint.get('mermaid_service_dependencies'):
        workflow_body.extend(['', '```mermaid', blueprint.get('mermaid_service_dependencies', ''), '```'])
    sections.append({
        'id': 'workflow-design',
        'title': 'Workflow Design',
        'body': workflow_body,
    })

    sections.append({
        'id': 'frontend-repository-architecture',
        'title': 'Frontend / Repository Architecture',
        'body': [
            'Directory guide:',
            *_markdown_bullets(
                [
                    f"{item.get('path', './')}: {item.get('purpose') or 'No purpose summary available.'}"
                    for item in directories if isinstance(item, dict)
                ],
                'No directory guide is available yet.',
            ),
            '',
            'Repository tree:',
            '```text',
            str(blueprint.get('repo_tree') or 'No repository tree available.'),
            '```',
        ],
    })

    sections.append({
        'id': 'ai-integration-design',
        'title': 'AI / Integration Design',
        'body': [
            *_markdown_bullets(
                [
                    f"{item.get('name', 'Integration')}: {item.get('description') or 'No description available.'}"
                    for item in integrations if isinstance(item, dict)
                ],
                'No AI or external integration points were clearly documented.',
            )
        ],
    })

    sections.append({
        'id': 'setup-operations',
        'title': 'Setup & Operations',
        'body': [
            'Setup steps:',
            *_markdown_bullets(
                [
                    f"{item.get('step', 'Setup step')}: {item.get('command') or item.get('explanation') or 'No command documented.'}"
                    for item in setup_steps if isinstance(item, dict)
                ],
                'No setup steps were documented.',
            ),
            '',
            'Environment variables:',
            *_markdown_bullets(
                [
                    f"{item.get('name', 'VAR_NAME')}: {item.get('description') or 'No description available.'}"
                    for item in env_vars if isinstance(item, dict)
                ],
                'No environment variables were documented.',
            ),
            '',
            'Testing strategy:',
            *testing_strategy_lines,
        ],
    })

    sections.append({
        'id': 'security-performance',
        'title': 'Security & Performance',
        'body': [
            'Security considerations:',
            *_markdown_bullets(
                [
                    f"{item.get('area', 'Security area')}: {item.get('description') or 'No detail available.'}"
                    for item in security if isinstance(item, dict)
                ],
                'No explicit security considerations were documented.',
            ),
            '',
            'Performance notes:',
            *_markdown_bullets(
                [
                    f"{item.get('area', 'Performance area')}: {item.get('description') or 'No detail available.'}"
                    for item in performance if isinstance(item, dict)
                ],
                'No explicit performance notes were documented.',
            ),
        ],
    })

    sections.append({
        'id': 'onboarding-knowledge',
        'title': 'Onboarding & Knowledge',
        'body': [
            'Onboarding checklist:',
            *_markdown_bullets(
                [
                    f"{item.get('task', 'Task')}: {item.get('instructions') or item.get('why_important') or 'No instructions available.'}"
                    for item in onboarding if isinstance(item, dict)
                ],
                'No onboarding checklist was documented.',
            ),
            '',
            'Key concepts:',
            *_markdown_bullets(
                [
                    f"{item.get('concept', 'Concept')}: {item.get('explanation') or 'No explanation available.'}"
                    for item in concepts if isinstance(item, dict)
                ],
                'No key concepts were documented.',
            ),
        ],
    })

    sections.append({
        'id': 'known-limitations-future-work',
        'title': 'Known Limitations & Future Work',
        'body': [
            'Known gotchas and sharp edges:',
            *_markdown_bullets(gotchas, 'No gotchas were documented.'),
            '',
            'Backlog and future-facing work:',
            *_markdown_bullets(
                [
                    f"{item.get('title', 'Work item')} [{item.get('status', 'unknown')}]"
                    for item in feature_inventory if isinstance(item, dict) and item.get('status') in {'backlog', 'development', 'testing', 'code_review'}
                ],
                feature_summary[:200] or 'No future work items were captured.',
            ),
        ],
    })

    toc_lines = []
    for index, section in enumerate(sections, start=1):
        toc_lines.append(f"{index}. [{section['title']}](#{_slugify_heading(section['title'])})")

    lines = [
        f"# {title} - Blueprint Design Document",
        '',
        '**Version:** 1.0',
        f'**Date:** {generated_on}',
        '**Source:** DevHub Blueprint',
        '',
        '---',
        '',
        '## Table of Contents',
        '',
        *toc_lines,
        '',
        '---',
        '',
    ]

    for index, section in enumerate(sections, start=1):
        lines.append(f"## {index}. {section['title']}")
        lines.append('')
        lines.extend(section['body'])
        lines.append('')
        lines.append('---')
        lines.append('')

    return '\n'.join(lines).strip(), sections




def _enrich_blueprint_document(project: Project, blueprint: dict, codebase_context: dict, feature_summary: str) -> dict:
    blueprint = dict(blueprint or {})
    workspace_path = Path(project.local_path) if project.local_path else None
    indexed_endpoints = _blueprint_list(codebase_context.get('api_reference'))
    existing_endpoints = blueprint.get('api_endpoints') or []
    # Prefer indexed (AST-extracted) data when it has >= entries — ground truth over stale LLM output.
    if indexed_endpoints and len(indexed_endpoints) >= len(existing_endpoints):
        blueprint['api_endpoints'] = indexed_endpoints
    elif existing_endpoints:
        blueprint['api_endpoints'] = existing_endpoints
    elif indexed_endpoints:
        blueprint['api_endpoints'] = indexed_endpoints
    indexed_schema = _blueprint_list(codebase_context.get('database_schema'))
    if indexed_schema and len(indexed_schema) >= len(blueprint.get('database_schema') or []):
        blueprint['database_schema'] = indexed_schema
    indexed_erd = str(codebase_context.get('database_mermaid_erd') or '')
    if indexed_erd and len(indexed_erd) > len(blueprint.get('mermaid_erd') or ''):
        blueprint['mermaid_erd'] = indexed_erd
    evidence_sequence_flows, evidence_common_workflows = _build_evidence_backed_workflows(workspace_path)
    if evidence_sequence_flows:
        blueprint['sequence_flows'] = evidence_sequence_flows
    if evidence_common_workflows:
        blueprint['common_workflows'] = evidence_common_workflows
    blueprint['mermaid_architecture'] = _normalize_mermaid_chart(blueprint.get('mermaid_architecture', ''), 'graph')
    blueprint['mermaid_service_dependencies'] = _normalize_mermaid_chart(blueprint.get('mermaid_service_dependencies', ''), 'graph')
    blueprint['mermaid_erd'] = _normalize_mermaid_chart(blueprint.get('mermaid_erd', ''), 'erd')

    sequence_flows = []
    for flow in (blueprint.get('sequence_flows') or []):
        if isinstance(flow, dict):
            normalized = dict(flow)
            normalized['mermaid_sequence'] = _normalize_mermaid_chart(normalized.get('mermaid_sequence', ''), 'sequence')
            sequence_flows.append(normalized)
    blueprint['sequence_flows'] = sequence_flows

    # Structural sections must come from the indexed repository cache, not model guesses.
    blueprint['directory_guide'] = _build_directory_guide_from_context(codebase_context)
    blueprint['repository_map'] = _build_repository_map_from_context(codebase_context)
    blueprint['repo_tree'] = str(codebase_context.get('repo_tree') or '')
    blueprint['repo_tree_nodes'] = _blueprint_list(codebase_context.get('repo_tree_nodes'))
    blueprint['readme_excerpt'] = str(codebase_context.get('readme_excerpt') or '')
    blueprint['instruction_files'] = _blueprint_list(_public_instruction_files(codebase_context))
    blueprint['file_structure_visualizer'] = _build_file_structure_visualizer(codebase_context)
    blueprint['change_guide'] = _build_change_guide(codebase_context)
    live_features = _project_features_payload(project)
    blueprint['feature_inventory'] = _live_feature_inventory(project) or [{
        'title': 'Current project work',
        'status': 'unknown',
        'description': feature_summary[:1200] or 'No feature inventory available yet.',
        'implementation_notes': 'Use Work Items to create and track project scope.',
    }]
    blueprint['sdlc_pipeline'] = _live_pipeline_document(project, live_features)
    blueprint = _merge_repo_guidance_into_blueprint(project, blueprint, codebase_context)
    blueprint = _finalize_blueprint_document(project, blueprint, codebase_context)
    blueprint.update(_build_blueprint_overview_insights(project, blueprint, codebase_context, live_features))
    design_document_markdown, design_document_sections = _render_blueprint_design_document(project, blueprint, codebase_context, feature_summary)
    blueprint['design_document_markdown'] = design_document_markdown
    blueprint['design_document_sections'] = [
        {
            'id': section.get('id'),
            'title': section.get('title'),
            'markdown': '\n'.join(section.get('body') or []).strip(),
        }
        for section in design_document_sections
    ]
    return blueprint

