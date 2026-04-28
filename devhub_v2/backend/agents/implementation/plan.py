import ast
import json
import logging
import os
import re
import subprocess
import time
from difflib import unified_diff
from pathlib import Path

from agents.core.base import ai_config_is_usable
from agents.memory.store import build_blueprint_context
from agents.core.workspace import SKIP_DIRS
from agents.customization.project_customization import (
    build_role_customization_addendum,
    build_role_prompt_context,
)
from core.models import Changeset, ChatMessage, Feature, Project

from api.project_utils import DEVHUB_META_DIR, _project_ai_config
from api.workspace.memory import _workspace_file_inventory
from api.workspace.runtime import detect_runtime

logger = logging.getLogger(__name__)


def _render_project_features_summary(project: Project, limit: int = 8) -> str:
    try:
        features = list(
            Feature.objects.filter(project=project)
            .order_by("-updated_at", "-created_at")[:limit]
            .values_list("title", "status")
        )
    except Exception:
        return "No recent feature records available."
    if not features:
        return "No recent feature records available."
    return "\n".join(f"- {title} [{status}]" for title, status in features)


def _render_recent_changes_summary(project: Project, limit: int = 6) -> str:
    try:
        changesets = list(
            Changeset.objects.filter(project=project)
            .order_by("-updated_at", "-created_at")[:limit]
            .values_list("title", "status")
        )
    except Exception:
        return "No recent changesets recorded."
    if not changesets:
        return "No recent changesets recorded."
    return "\n".join(f"- {title} [{status}]" for title, status in changesets)


def _recent_chat_history(project: Project, limit: int = 6) -> str:
    try:
        messages = list(
            ChatMessage.objects.filter(project=project)
            .order_by("-created_at", "-id")[:limit]
            .values_list("role", "content")
        )
    except Exception:
        return "No recent chat history available."
    if not messages:
        return "No recent chat history available."
    ordered = list(reversed(messages))
    return "\n".join(f"- {role}: {str(content or '')[:180]}" for role, content in ordered)

def _fallback_plan(selected_file: str, file_inventory: str, request_text: str) -> dict:
    inventory_lines = [line.strip() for line in file_inventory.splitlines() if line.strip()]
    relevant = []
    if selected_file:
        relevant.append(selected_file)
    priority_matches = []
    for candidate in inventory_lines:
        lower = candidate.lower()
        if any(token in lower for token in ('app', 'index', 'main', 'style', 'component', 'view', 'page', 'url', 'route')):
            priority_matches.append(candidate)
        if len(priority_matches) >= 7:
            break
    for item in priority_matches:
        if item not in relevant:
            relevant.append(item)
    return {
        "objective": request_text,
        "relevant_files": relevant[:8],
        "new_files": [],
        "implementation_steps": [
            "Inspect the existing implementation.",
            "Update the minimum set of files needed for a consistent change.",
            "Keep related UI, logic, and docs aligned.",
        ],
        "consistency_requirements": [
            "Reuse the current project structure.",
            "Reflect the request in all directly related files.",
        ],
        "risks": [
            "Changing the wrong scaffold files can make the app unrunnable.",
        ],
        "validation_commands": [],
        "acceptance_checks": [
            "The requested behavior is implemented in the current project structure.",
        ],
        "memory_updates": [],
    }


def _collect_workspace_context(
    workspace_path: Path,
    *,
    selected_file: str = "",
    selected_content: str = "",
    limit: int = 20,
) -> list[dict]:
    context: list[dict] = []
    seen: set[str] = set()

    def add_file(rel_path: str, content_override: str | None = None):
        normalized = str(rel_path or "").replace("\\", "/").strip("/")
        if not normalized or normalized in seen or len(context) >= limit:
            return
        candidate = workspace_path / normalized
        if content_override is None:
            if not candidate.exists() or not candidate.is_file():
                return
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return
        else:
            content = content_override
        seen.add(normalized)
        context.append({"path": normalized, "content": content})

    if selected_file:
        add_file(selected_file, selected_content or None)

    for rel_path in (
        "README.md",
        "package.json",
        "index.html",
        "manage.py",
        "requirements.txt",
        ".devhub/DEVHUB.md",
        ".devhub/prompts/implementation.md",
        ".devhub/prompts/coder.md",
        "AGENTS.md",
    ):
        add_file(rel_path)

    # Include framework-agnostic contract/routing files so the agent can
    # understand data flow before touching UI files. These names are common
    # across many frameworks (Django, Rails, Laravel, Express, FastAPI, etc.).
    _CONTRACT_FILENAMES = {
        "urls.py", "routes.py", "router.py", "routes.ts", "routes.js",
        "routes.rb", "web.php", "forms.py", "schema.py", "serializers.py",
    }
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for fname in files:
            if fname in _CONTRACT_FILENAMES and len(context) < limit:
                rel = str((Path(root) / fname).relative_to(workspace_path)).replace("\\", "/")
                add_file(rel)

    return context


def _create_implementation_plan(
    project: Project,
    request_title: str,
    request_text: str,
    workspace_path: Path,
    project_memory: str,
    memory_context_text: str = "",
    selected_file: str = "",
    customization_bundle: dict | None = None,
    request_attachments: list[dict] | None = None,
) -> dict:
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        logger.exception("Failed to load cached codebase context for planning in project %s", project.id)
    codebase_summary = (codebase_context or {}).get('compact_summary') or 'No cached codebase summary available.'
    file_inventory = _workspace_file_inventory(workspace_path, limit=160)
    blueprint_summary = json.dumps(project.blueprint or {}, indent=2)[:3500] if project.blueprint else "No blueprint available."
    supporting_context = f"""Recent Features:
{_render_project_features_summary(project)}

Recent Changes:
{_render_recent_changes_summary(project)}

Recent Chat:
{_recent_chat_history(project)}

Memory Recall:
{memory_context_text or 'No additional memory recall available.'}

Cached Codebase Context:
{codebase_summary[:5000]}
"""
    customization_context = build_role_prompt_context(customization_bundle, "planner")
    if customization_context:
        supporting_context = f"{supporting_context}\n\nProject Customization:\n{customization_context[:8000]}"

    if not ai_config_is_usable(_project_ai_config(project)):
        return _fallback_plan(selected_file, file_inventory, request_text)

    try:
        from agents.coding.planner import PlannerAgent

        planner = PlannerAgent(
            ai_config=_project_ai_config(project),
            customization_instruction=build_role_customization_addendum(customization_bundle, "planner"),
        )
        plan = planner.create_plan(
            project_name=project.name,
            request_title=request_title,
            request_text=request_text,
            project_memory=project_memory[:12000],
            codebase_summary=codebase_summary[:9000],
            file_inventory=file_inventory[:5000],
            blueprint_summary=blueprint_summary,
            supporting_context=supporting_context[:8000],
            customization_context=customization_context[:8000],
            request_attachments=request_attachments,
        )
        if not isinstance(plan, dict):
            return _fallback_plan(selected_file, file_inventory, request_text)
        return plan
    except Exception:
        logger.exception("Implementation planner failed for project %s", project.id)
        return _fallback_plan(selected_file, file_inventory, request_text)


def _collect_relevant_files(
    workspace_path: Path,
    plan: dict,
    request_text: str = "",
    codebase_context: dict | None = None,
    selected_file: str = "",
    selected_content: str = "",
    limit: int = 20,
) -> list[dict]:
    context = []
    seen = set()
    codebase_context = codebase_context or {}

    def add_file(rel_path: str, content_override: str | None = None):
        normalized = rel_path.replace('\\', '/')
        if normalized in seen or len(context) >= limit:
            return
        candidate = workspace_path / normalized
        if not candidate.exists() or not candidate.is_file():
            return
        try:
            content = content_override if content_override is not None else candidate.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return
        seen.add(normalized)
        context.append({"path": normalized, "content": content})

    if selected_file:
        add_file(selected_file, selected_content or None)

    for rel_path in plan.get('relevant_files', [])[:limit]:
        if isinstance(rel_path, str):
            add_file(rel_path)

    for item in (codebase_context.get('instruction_files') or [])[:4]:
        if isinstance(item, dict) and item.get('path'):
            add_file(str(item['path']), str(item.get('content') or '') or None)

    for item in (codebase_context.get('important_files') or [])[:10]:
        rel_path = item.get('path')
        if isinstance(rel_path, str):
            add_file(rel_path)

    search_terms = _tokenize_search_terms(
        request_text,
        plan.get('objective', ''),
        ' '.join(plan.get('acceptance_checks', []) or []),
        ' '.join(plan.get('implementation_steps', []) or []),
    )
    for rel_path in _search_workspace_paths(workspace_path, search_terms, limit=10):
        add_file(rel_path)
    for rel_path in _search_workspace_content(workspace_path, search_terms, limit=10):
        add_file(rel_path)

    # Fill remaining slots with priority files and a broader sample if the plan is sparse.
    for rel_path in [
        "package.json", "vite.config.js", "vite.config.ts", "index.html",
        "main.py", "app.py", "requirements.txt", "manage.py", "README.md",
    ]:
        add_file(rel_path)

    if len(context) < limit:
        for item in _collect_workspace_context(workspace_path, selected_file=selected_file, selected_content=selected_content, limit=limit):
            if len(context) >= limit:
                break
            if item['path'] not in seen:
                seen.add(item['path'])
                context.append(item)

    return context


def _build_supporting_context(project: Project, plan: dict, workspace_path: Path, customization_bundle: dict | None = None) -> str:
    runtime = detect_runtime(workspace_path)
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        logger.exception("Failed to load codebase context for supporting context in project %s", project.id)
    instruction_context = codebase_context.get('instruction_files') or []
    customization_context = build_role_prompt_context(customization_bundle, "coder")
    return f"""Runtime:
{json.dumps(runtime, indent=2)}

Recent Features:
{_render_project_features_summary(project)}

Recent Changes:
{_render_recent_changes_summary(project)}

Recent Chat:
{_recent_chat_history(project)}

Plan Acceptance Checks:
{json.dumps(plan.get('acceptance_checks', []), indent=2)}

Project Instructions:
{json.dumps(instruction_context, indent=2)[:2500] if instruction_context else 'No DEVHUB.md / AGENTS.md style instruction file detected.'}

Project Customization:
{customization_context[:8000] if customization_context else 'No additional implementation customization detected.'}
"""


def _tokenize_search_terms(*values: str, limit: int = 12) -> list[str]:
    tokens = []
    seen = set()
    for value in values:
        for token in re.findall(r'[A-Za-z0-9_./-]+', str(value or '').lower()):
            normalized = token.strip('./-')
            if len(normalized) < 3:
                continue
            if normalized in {'the', 'and', 'with', 'from', 'this', 'that', 'feature', 'project', 'update'}:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            tokens.append(normalized)
            if len(tokens) >= limit:
                return tokens
    return tokens


def _search_workspace_paths(workspace_path: Path, terms: list[str], limit: int = 24) -> list[str]:
    if not terms:
        return []

    results = []
    seen = set()

    try:
        completed = subprocess.run(
            ['rg', '--files', str(workspace_path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode == 0:
            for rel_path in completed.stdout.splitlines():
                normalized = str(rel_path).replace('\\', '/')
                lower = normalized.lower()
                if normalized.startswith(f"{DEVHUB_META_DIR}/"):
                    continue
                if any(term in lower for term in terms):
                    if normalized not in seen:
                        seen.add(normalized)
                        results.append(normalized)
                        if len(results) >= limit:
                            return results
    except Exception:
        pass

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for filename in sorted(files):
            rel_path = str((Path(root) / filename).relative_to(workspace_path)).replace('\\', '/')
            lower = rel_path.lower()
            if rel_path.startswith(f"{DEVHUB_META_DIR}/"):
                continue
            if any(term in lower for term in terms):
                if rel_path not in seen:
                    seen.add(rel_path)
                    results.append(rel_path)
                    if len(results) >= limit:
                        return results
    return results


def _search_workspace_content(workspace_path: Path, terms: list[str], limit: int = 16) -> list[str]:
    if not terms:
        return []

    results = []
    seen = set()
    source_exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".md"}

    for term in terms[:6]:
        try:
            completed = subprocess.run(
                ['rg', '--files-with-matches', '--glob', '!*.min.*', term, str(workspace_path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if completed.returncode in (0, 1):
                for rel_path in completed.stdout.splitlines():
                    normalized = str(rel_path).replace('\\', '/')
                    if normalized.startswith(f"{DEVHUB_META_DIR}/") or normalized in seen:
                        continue
                    seen.add(normalized)
                    results.append(normalized)
                    if len(results) >= limit:
                        return results
        except Exception:
            break

    if results:
        return results

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for filename in sorted(files):
            path = Path(root) / filename
            rel_path = str(path.relative_to(workspace_path)).replace('\\', '/')
            if rel_path.startswith(f"{DEVHUB_META_DIR}/") or path.suffix.lower() not in source_exts:
                continue
            try:
                content = path.read_text(encoding='utf-8', errors='ignore').lower()
            except Exception:
                continue
            if any(term in content for term in terms):
                if rel_path not in seen:
                    seen.add(rel_path)
                    results.append(rel_path)
                    if len(results) >= limit:
                        return results
    return results


def _workspace_python_files(workspace_path: Path):
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for filename in sorted(files):
            if filename.endswith('.py'):
                yield Path(root) / filename


def _ast_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _string_literals(node) -> list[str]:
    values: list[str] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for item in node.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                values.append(item.value)
    return values


def _parse_form_definitions(workspace_path: Path) -> tuple[dict[str, set[str]], dict[str, str]]:
    form_fields: dict[str, set[str]] = {}
    formsets: dict[str, str] = {}

    for py_path in _workspace_python_files(workspace_path):
        if py_path.name != "forms.py":
            continue
        try:
            source = py_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source)
        except Exception:
            continue

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                fields: set[str] = set()
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                        target_name = stmt.targets[0].id
                        if isinstance(stmt.value, ast.Call) and _ast_name(stmt.value.func).endswith('Field'):
                            fields.add(target_name)
                    if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
                        for meta_stmt in stmt.body:
                            if isinstance(meta_stmt, ast.Assign) and len(meta_stmt.targets) == 1 and isinstance(meta_stmt.targets[0], ast.Name):
                                if meta_stmt.targets[0].id == "fields":
                                    fields.update(_string_literals(meta_stmt.value))
                if fields:
                    form_fields[node.name] = fields

            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                value = node.value
                if isinstance(value, ast.Call) and _ast_name(value.func) == 'formset_factory' and value.args:
                    base_form_name = _ast_name(value.args[0])
                    if base_form_name:
                        formsets[node.targets[0].id] = base_form_name

    return form_fields, formsets


def _parse_context_dict(node, dict_bindings: dict[str, dict], form_assignments: dict[str, str]) -> dict:
    if isinstance(node, ast.Name):
        return dict_bindings.get(node.id, {'context_keys': set(), 'form_bindings': {}})

    context_keys: set[str] = set()
    form_bindings: dict[str, str] = {}
    if not isinstance(node, ast.Dict):
        return {'context_keys': context_keys, 'form_bindings': form_bindings}

    for key_node, value_node in zip(node.keys, node.values):
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            continue
        key = key_node.value
        context_keys.add(key)
        if isinstance(value_node, ast.Name) and value_node.id in form_assignments:
            form_bindings[key] = form_assignments[value_node.id]
    return {'context_keys': context_keys, 'form_bindings': form_bindings}


def _parse_template_view_contracts(workspace_path: Path) -> dict[str, list[dict]]:
    contracts: dict[str, list[dict]] = {}

    for py_path in _workspace_python_files(workspace_path):
        if py_path.name != "views.py":
            continue
        try:
            source = py_path.read_text(encoding='utf-8', errors='ignore')
            lines = source.splitlines()
            tree = ast.parse(source)
        except Exception:
            continue

        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue

            form_assignments: dict[str, str] = {}
            dict_bindings: dict[str, dict] = {}
            function_source = "\n".join(lines[node.lineno - 1:getattr(node, 'end_lineno', node.lineno)])
            post_keys = set(re.findall(r"request\.POST\.get\(\s*['\"]([^'\"]+)['\"]", function_source))
            supports_json = 'JsonResponse(' in function_source

            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    target_name = stmt.targets[0].id
                    if isinstance(stmt.value, ast.Call):
                        callable_name = _ast_name(stmt.value.func)
                        if callable_name.endswith('Form') or callable_name.endswith('FormSet'):
                            form_assignments[target_name] = callable_name
                    parsed_dict = _parse_context_dict(stmt.value, {}, form_assignments)
                    if parsed_dict.get('context_keys'):
                        dict_bindings[target_name] = parsed_dict

            for stmt in ast.walk(node):
                if not isinstance(stmt, ast.Call) or _ast_name(stmt.func) != 'render':
                    continue

                template_name = ""
                if len(stmt.args) >= 2 and isinstance(stmt.args[1], ast.Constant) and isinstance(stmt.args[1].value, str):
                    template_name = stmt.args[1].value
                else:
                    for kw in stmt.keywords:
                        if kw.arg == 'template_name' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            template_name = kw.value.value
                            break
                if not template_name:
                    continue

                context_expr = None
                if len(stmt.args) >= 3:
                    context_expr = stmt.args[2]
                else:
                    for kw in stmt.keywords:
                        if kw.arg == 'context':
                            context_expr = kw.value
                            break

                context_meta = _parse_context_dict(context_expr, dict_bindings, form_assignments)
                entry = {
                    'context_keys': set(context_meta.get('context_keys') or []),
                    'form_bindings': dict(context_meta.get('form_bindings') or {}),
                    'post_keys': set(post_keys),
                    'supports_json': supports_json,
                }
                contracts.setdefault(template_name, []).append(entry)
                contracts.setdefault(Path(template_name).name, []).append(entry)

    return contracts


def _resolve_template_file(workspace_path: Path, template_name: str) -> Path | None:
    candidate = workspace_path / template_name
    if candidate.exists() and candidate.is_file():
        return candidate
    for path in workspace_path.rglob(Path(template_name).name):
        if path.is_file() and 'templates' in {part.lower() for part in path.parts}:
            return path
    return None


def _extract_template_blocks(text: str) -> set[str]:
    return {match.group(1) for match in re.finditer(r"\{%\s*block\s+([A-Za-z_][A-Za-z0-9_]*)", text)}


def _extract_template_roots(text: str) -> set[str]:
    roots: set[str] = set()
    for expr in re.findall(r"\{\{\s*(.*?)\s*\}\}", text, re.DOTALL):
        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", expr.strip())
        if match:
            roots.add(match.group(1))
    return roots


def _extract_loop_variables(text: str) -> set[str]:
    loop_vars: set[str] = set()
    for match in re.finditer(r"\{%\s*for\s+([^%]+?)\s+in\s+[^%]+%\}", text):
        names = [item.strip() for item in str(match.group(1)).split(',')]
        for name in names:
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                loop_vars.add(name)
    return loop_vars


def _hardcoded_template_field_names(text: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(r'<(?:input|textarea|select)\b[^>]*\bname="([^"]+)"', text, re.IGNORECASE):
        value = str(match.group(1) or '').strip()
        if not value or '{{' in value or '{%' in value:
            continue
        names.add(value)
    return names


def _field_name_matches(name: str, allowed_fields: set[str]) -> bool:
    if name in allowed_fields:
        return True
    match = re.match(r'^[A-Za-z0-9_]+-\d+-([A-Za-z0-9_]+)$', name)
    if match and match.group(1) in allowed_fields:
        return True
    return False


def _run_django_template_contract_checks(workspace_path: Path, changed_files: list[str] | None = None) -> list[dict]:
    if not (workspace_path / 'manage.py').exists():
        return []

    changed_templates = [
        str(path).replace('\\', '/')
        for path in (changed_files or [])
        if str(path).lower().endswith('.html')
    ]
    if not changed_templates:
        return []

    form_fields, formsets = _parse_form_definitions(workspace_path)
    template_contracts = _parse_template_view_contracts(workspace_path)
    issues: list[dict] = []

    for rel_path in changed_templates:
        template_path = workspace_path / rel_path
        if not template_path.exists():
            continue

        try:
            text = template_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        template_name = Path(rel_path).name
        contract_entries = list(template_contracts.get(rel_path) or []) + list(template_contracts.get(template_name) or [])
        context_keys: set[str] = set()
        allowed_fields: set[str] = set()
        supports_json = False

        for entry in contract_entries:
            context_keys.update(entry.get('context_keys') or [])
            supports_json = supports_json or bool(entry.get('supports_json'))
            allowed_fields.update(entry.get('post_keys') or [])
            for bound_form in (entry.get('form_bindings') or {}).values():
                resolved_form = formsets.get(bound_form, bound_form)
                allowed_fields.update(form_fields.get(resolved_form, set()))

        extends_match = re.search(r"\{%\s*extends\s+['\"]([^'\"]+)['\"]\s*%\}", text)
        if extends_match:
            parent_path = _resolve_template_file(workspace_path, extends_match.group(1))
            if parent_path and parent_path.exists():
                try:
                    parent_text = parent_path.read_text(encoding='utf-8', errors='ignore')
                    parent_blocks = _extract_template_blocks(parent_text)
                    child_blocks = _extract_template_blocks(text)
                    invalid_blocks = sorted(block for block in child_blocks if block not in parent_blocks)
                    for block_name in invalid_blocks:
                        issues.append({
                            'severity': 'high',
                            'file': rel_path,
                            'description': f"Template defines block `{block_name}` that parent template does not render.",
                            'suggestion': f"Use one of parent blocks: {', '.join(sorted(parent_blocks))}.",
                        })
                except Exception:
                    pass

        if contract_entries:
            loop_locals = _extract_loop_variables(text)
            template_roots = _extract_template_roots(text)
            allowed_roots = context_keys | loop_locals | {
                'request', 'user', 'messages', 'csrf_token', 'forloop', 'form', 'formset', 'True', 'False', 'None',
            }

            for root in sorted(template_roots):
                if root not in allowed_roots:
                    issues.append({
                        'severity': 'high',
                        'file': rel_path,
                        'description': f"Template references `{root}`, but matching Django view context does not provide that key.",
                        'suggestion': "Use an existing context key or update the view/template contract together.",
                    })

            if allowed_fields:
                field_names = _hardcoded_template_field_names(text) - {'csrfmiddlewaretoken'}
                for field_name in sorted(field_names):
                    if not _field_name_matches(field_name, allowed_fields):
                        issues.append({
                            'severity': 'high',
                            'file': rel_path,
                            'description': f"Hardcoded field name `{field_name}` does not match bound form fields or `request.POST` keys used by the view.",
                            'suggestion': "Render field names from the Django form or align the view and template to the same contract.",
                        })

            if re.search(r"\bresponse\.json\s*\(", text) and not supports_json:
                issues.append({
                    'severity': 'medium',
                    'file': rel_path,
                    'description': "Template JavaScript expects JSON responses, but matching Django view does not return `JsonResponse`.",
                    'suggestion': "Return JSON for AJAX requests or stop parsing the response as JSON.",
                })

    if not issues:
        return [{
            'command': 'django template contract check',
            'success': True,
            'exit_code': 0,
            'stdout': 'No changed-template contract issues detected.',
            'stderr': '',
            'details': [],
        }]

    summary_lines = [
        f"- {issue.get('file')}: {issue.get('description')}"
        for issue in issues[:10]
    ]
    return [{
        'command': 'django template contract check',
        'success': False,
        'exit_code': 1,
        'stdout': '',
        'stderr': "\n".join(summary_lines),
        'details': issues,
    }]


def _package_scripts(project_root: Path) -> dict:
    package_json_path = project_root / "package.json"
    if not package_json_path.exists():
        return {}
    try:
        package_json = json.loads(package_json_path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return package_json.get('scripts', {}) or {}


def _validation_commands(workspace_path: Path) -> list[str]:
    runtime = detect_runtime(workspace_path)
    commands: list[str] = []

    if runtime.get('runtime_type') == 'node':
        scripts = _package_scripts(workspace_path)
        if scripts.get('lint'):
            commands.append('npm run lint')
        if scripts.get('typecheck'):
            commands.append('npm run typecheck')
        elif scripts.get('build'):
            commands.append('npm run build')
        if scripts.get('test'):
            commands.append('npm run test -- --watch=false')
    elif runtime.get('runtime_type') == 'django':
        commands.append('python manage.py check')
        commands.append('python manage.py test')
    elif runtime.get('runtime_type') == 'python':
        if (workspace_path / 'pytest.ini').exists() or (workspace_path / 'tests').exists():
            commands.append('pytest')
        elif runtime.get('entrypoint'):
            commands.append(f"python -m py_compile {runtime.get('entrypoint')}")

    return commands[:3]


def _run_validation_suite(workspace_path: Path, changed_files: list[str] | None = None) -> list[dict]:
    results = []
    results.extend(_run_django_template_contract_checks(workspace_path, changed_files))
    for command in _validation_commands(workspace_path):
        try:
            completed = subprocess.run(
                command,
                cwd=str(workspace_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            results.append({
                'command': command,
                'success': completed.returncode == 0,
                'exit_code': completed.returncode,
                'stdout': completed.stdout[:4000],
                'stderr': completed.stderr[:4000],
            })
        except subprocess.TimeoutExpired:
            results.append({
                'command': command,
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': 'Timed out after 180 seconds.',
            })
        except Exception as exc:
            results.append({
                'command': command,
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': str(exc),
            })
    return results


def _validation_summary(results: list[dict]) -> str:
    if not results:
        return "No validation commands were available."
    lines = []
    for result in results:
        status = 'passed' if result.get('success') else 'failed'
        lines.append(f"- {result.get('command')}: {status}")
        if result.get('stderr'):
            lines.append(f"  stderr: {str(result['stderr'])[:240]}")
    return "\n".join(lines)


def _all_validations_passed(results: list[dict]) -> bool:
    return all(result.get('success') for result in results) if results else True


def _build_review_diff(workspace_path: Path, previous_contents: dict, applied_files: list[str]) -> str:
    sections = []
    for rel_path in applied_files:
        current_path = workspace_path / rel_path
        before = previous_contents.get(rel_path, "")
        after = current_path.read_text(encoding='utf-8', errors='ignore') if current_path.exists() else ""
        diff = ''.join(
            unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f'a/{rel_path}',
                tofile=f'b/{rel_path}',
            )
        )
        sections.append(diff or f"# {rel_path}\nNo textual diff available.")
    return "\n".join(sections)[:14000]


def _review_attempt(
    project: Project,
    workspace_path: Path,
    previous_contents: dict,
    applied_files: list[str],
    validation_results: list[dict],
    customization_bundle: dict | None = None,
    request_text: str = "",
    request_attachments: list[dict] | None = None,
) -> dict:
    if not applied_files:
        return {
            'approved': True,
            'score': 100,
            'summary': 'No file changes were produced.',
            'issues': [],
        }

    if not ai_config_is_usable(_project_ai_config(project)):
        issues = []
        for result in validation_results:
            if not result.get('success'):
                issues.append({
                    'severity': 'high',
                    'file': '',
                    'description': f"Validation failed for {result.get('command')}",
                    'suggestion': str(result.get('stderr') or result.get('stdout') or '')[:300],
                })
        return {
            'approved': _all_validations_passed(validation_results),
            'score': 95 if _all_validations_passed(validation_results) else 40,
            'summary': _validation_summary(validation_results),
            'issues': issues,
        }

    try:
        from agents.coding.reviewer import ReviewerAgent

        reviewer = ReviewerAgent(
            ai_config=_project_ai_config(project),
            customization_instruction=build_role_customization_addendum(customization_bundle, "reviewer"),
        )
        return reviewer.review_changeset(
            changeset_diff=_build_review_diff(workspace_path, previous_contents, applied_files),
            tech_stack=", ".join(project.tech_stack or []),
            blueprint=json.dumps(project.blueprint or {}, indent=2)[:3000],
            evaluation_summary=_validation_summary(validation_results),
            customization_context=build_role_prompt_context(customization_bundle, "reviewer")[:8000],
            request_text=request_text,
            request_attachments=request_attachments,
        )
    except Exception:
        logger.exception("ReviewerAgent failed for project %s", project.id)
        return {
            'approved': _all_validations_passed(validation_results),
            'score': 70 if _all_validations_passed(validation_results) else 45,
            'summary': _validation_summary(validation_results),
            'issues': [],
        }


def _count_total_workspace_files(workspace_path: Path) -> int:
    """
    Count all files in the workspace (not just indexable ones).
    Used for routing decisions so that Go/Rust/Java/etc. repos aren't
    incorrectly classified as empty by manifest_file_count.
    """
    try:
        total = 0
        for root, dirs, files in os.walk(workspace_path):
            # Mirror SKIP_DIRS logic to avoid inflating counts with node_modules etc.
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            total += len(files)
            if total > 100_000:  # Cap to avoid hanging on massive repos
                return total
        return total
    except Exception:
        return 0


