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
from core.models import Feature, Project

from api.project_utils import DEVHUB_META_DIR, _project_ai_config
from api.workspace.memory import _workspace_file_inventory
from api.workspace.runtime import detect_runtime

logger = logging.getLogger(__name__)

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


def _run_validation_suite(workspace_path: Path) -> list[dict]:
    results = []
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


