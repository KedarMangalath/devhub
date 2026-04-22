import json
import re
from pathlib import Path, PurePosixPath

from django.utils import timezone

from core.models import Changeset, Feature, FeatureHistory, Project, TestResult

from agents.core.workspace import PROJECTS_DIR

from api.blueprint.builders import (
    _confirmed_overview_doc_paths,
    _dedupe_json_items,
    _enrich_blueprint_document,
    _format_path_list,
    _prefix_command_for_dir,
    _run_script_command,
    _is_speculative_risk_text,
    _workspace_package_manifests,
    _workspace_python_roots,
)
from api.codebase.doc_builder import _blueprint_list, _project_workspace_path
from api.project_utils import PIPELINE_STAGES, _normalize_tech_stack
from api.workspace.runtime import detect_runtime

def _project_features_payload(project: Project):
    features = list(
        Feature.objects.filter(project=project).order_by('-created_at').values(
            'id', 'title', 'description', 'status', 'spec', 'created_by', 'created_at', 'suggestions'
        )
    )
    for feature in features:
        try:
            test_result = TestResult.objects.get(feature_id=feature['id'])
            feature['test_results'] = {
                'overall_status': test_result.overall_status,
                'score': test_result.score,
                'summary': test_result.summary,
                'tests': test_result.tests,
                'coverage': test_result.coverage,
                'suggestions': test_result.suggestions,
                'blockers': test_result.blockers,
            }
        except TestResult.DoesNotExist:
            feature['test_results'] = None

        feature['pipeline_history'] = list(FeatureHistory.objects.filter(feature_id=feature['id']).order_by('at').values('stage', 'action', 'by', 'comment', 'at'))
        feature['approvals'] = list(FeatureApproval.objects.filter(feature_id=feature['id']).order_by('at').values('by', 'role', 'comment', 'at'))
    return features


def _normalize_tech_stack(raw_value) -> list[str]:
    if isinstance(raw_value, str):
        values = [item.strip() for item in raw_value.split(',')]
    elif isinstance(raw_value, list):
        values = [str(item).strip() for item in raw_value]
    else:
        values = []

    normalized = []
    seen = set()
    for value in values:
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _project_source_type(project: Project) -> str:
    if project.github_url:
        return 'github'
    if project.local_path and not str(project.local_path).startswith(str(PROJECTS_DIR)):
        return 'folder'
    return 'starter'


def _recommended_start_tab(project: Project) -> str:
    source_type = _project_source_type(project)
    if source_type in {'github', 'folder'}:
        return 'onboarding'
    return 'overview'


def _feature_stage_counts(features: list[dict]) -> dict:
    counts = {stage: 0 for stage in PIPELINE_STAGES}
    for feature in features:
        status = str(feature.get('status') or '')
        if status in counts:
            counts[status] += 1
    return counts


def _live_feature_inventory(project: Project) -> list[dict]:
    inventory = []
    for feature in Feature.objects.filter(project=project).order_by('-created_at')[:20]:
        spec = feature.spec or {}
        latest_history = FeatureHistory.objects.filter(feature=feature).order_by('-at').first()
        inventory.append({
            'title': feature.title,
            'status': feature.status or 'unknown',
            'description': feature.description or spec.get('user_story') or 'No feature description captured yet.',
            'implementation_notes': (
                (latest_history.comment if latest_history and latest_history.comment else '')
                or str(spec.get('technical_approach') or '')[:320]
                or 'Tracked as a live work item in DevHub.'
            ),
        })
    return inventory


def _live_pipeline_document(project: Project, features_payload: list[dict] | None = None) -> dict:
    features_payload = features_payload or _project_features_payload(project)
    counts = _feature_stage_counts(features_payload)
    stage_titles = {
        'backlog': 'Scoped work waiting to be started.',
        'development': 'Work currently being implemented in code.',
        'testing': 'Changes being validated through tests and checks.',
        'code_review': 'Work waiting for approval or review.',
        'staging': 'Changes that are nearly ready to ship.',
    }
    stage_rows = []
    for stage in PIPELINE_STAGES:
        stage_features = [feature for feature in features_payload if feature.get('status') == stage][:6]
        stage_rows.append({
            'name': stage.replace('_', ' ').title(),
            'purpose': stage_titles.get(stage, 'Tracked work stage'),
            'entry_criteria': [f'Feature reaches {stage.replace("_", " ")} stage.'],
            'exit_criteria': ['Advance to the next stage or send back for changes.'],
            'count': counts.get(stage, 0),
            'active_features': [item.get('title') for item in stage_features if item.get('title')],
        })
    return {
        'stages': stage_rows,
        'approval_gates': [
            'Approve confirms a feature is ready for the next checkpoint.',
            'Move Forward advances the same work item through the shared lifecycle.',
        ],
        'ai_capabilities': [
            'AI can generate specs, implement changes, simulate tests, and refresh architecture context.',
            'Pipeline actions update the same work items used by Overview and Onboarding.',
        ],
        'team_workflow': 'DevHub tracks one work-item model that can be viewed as either a list of features or a delivery board.',
    }


def _work_items_summary(project: Project, features_payload: list[dict] | None = None) -> dict:
    features_payload = features_payload or _project_features_payload(project)
    counts = _feature_stage_counts(features_payload)
    in_progress = [feature.get('title') for feature in features_payload if feature.get('status') in {'development', 'testing', 'code_review'}][:6]
    return {
        'total': len(features_payload),
        'by_stage': counts,
        'in_progress': in_progress,
        'completed_like': counts.get('staging', 0),
        'empty': len(features_payload) == 0,
    }


def _overview_time_label(value) -> str:
    if not value:
        return ""
    try:
        delta = timezone.now() - value
    except Exception:
        return str(value)
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    days = hours // 24
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return value.strftime("%Y-%m-%d")


def _overview_severity_weight(value: str) -> int:
    normalized = str(value or "").strip().lower()
    return {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "warning": 2,
        "low": 1,
        "info": 0,
    }.get(normalized, 0)


def _build_overview_project_health(blueprint: dict, runtime: dict, features_payload: list[dict], codebase_context: dict) -> list[dict]:
    counts = _feature_stage_counts(features_payload)
    active_count = counts.get('development', 0) + counts.get('testing', 0) + counts.get('code_review', 0)
    runtime_type = str(runtime.get('runtime_type') or '').strip().lower()
    runtime_command = str(runtime.get('run_command') or '').strip()
    testing = blueprint.get('testing_strategy') if isinstance(blueprint.get('testing_strategy'), dict) else {}
    validation_command = str(testing.get('run_command') or '').strip()
    doc_paths = _confirmed_overview_doc_paths(blueprint, codebase_context)
    return [
        {
            'label': 'Runtime',
            'value': runtime_type.title() if runtime_type and runtime_type != 'unknown' else 'Not detected',
            'detail': runtime_command or 'No primary run command was detected from the indexed entrypoints.',
            'tone': 'good' if runtime_command else 'warn',
        },
        {
            'label': 'Validation',
            'value': 'Command detected' if validation_command else 'Manual validation',
            'detail': validation_command or str(testing.get('unit') or 'No primary validation command was detected yet.'),
            'tone': 'good' if validation_command else 'warn',
        },
        {
            'label': 'Docs',
            'value': f'{len(doc_paths)} source{"s" if len(doc_paths) != 1 else ""}' if doc_paths else 'Thin docs',
            'detail': _format_path_list(doc_paths, max_paths=3) or 'No README, instruction file, or docs directory content was detected in the indexed paths.',
            'tone': 'good' if doc_paths else 'warn',
        },
        {
            'label': 'Active Work',
            'value': f'{active_count} active / {len(features_payload)} total' if features_payload else 'No tracked work',
            'detail': f"Backlog {counts.get('backlog', 0)}, development {counts.get('development', 0)}, testing {counts.get('testing', 0)}, review {counts.get('code_review', 0)}.",
            'tone': 'neutral' if features_payload else 'warn',
        },
    ]


def _build_overview_current_risks(blueprint: dict) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for item in _blueprint_list(blueprint.get('security_considerations'))[:3]:
        if not isinstance(item, dict):
            continue
        detail = str(item.get('description') or '').strip()
        if not detail or detail in seen:
            continue
        seen.add(detail)
        items.append({
            'title': str(item.get('area') or 'Security consideration').strip(),
            'severity': str(item.get('severity') or 'medium').strip().lower(),
            'detail': detail,
        })
    for item in _blueprint_list(blueprint.get('performance_notes'))[:2]:
        if not isinstance(item, dict):
            continue
        detail = str(item.get('description') or '').strip()
        if not detail or detail in seen:
            continue
        seen.add(detail)
        items.append({
            'title': str(item.get('area') or 'Performance note').strip(),
            'severity': str(item.get('impact') or 'medium').strip().lower(),
            'detail': detail,
        })
    for note in _blueprint_list(blueprint.get('gotchas'))[:2]:
        detail = str(note or '').strip()
        if not detail or detail in seen or _is_speculative_risk_text(detail):
            continue
        seen.add(detail)
        items.append({
            'title': 'Operational gotcha',
            'severity': 'medium',
            'detail': detail,
        })
    items.sort(key=lambda item: (-_overview_severity_weight(str(item.get('severity') or '')), str(item.get('title') or '')))
    return items[:5]


def _setup_command_entry_path(workspace_path: Path, codebase_context: dict, runtime: dict) -> str:
    setup_command = str(runtime.get('setup_command') or '').strip()
    if not setup_command:
        return str(runtime.get('entrypoint') or '')

    lowered = setup_command.lower()
    if any(token in lowered for token in ('npm', 'pnpm', 'yarn')):
        manifests = _workspace_package_manifests(workspace_path, codebase_context)
        preferred = next(
            (
                manifest
                for manifest in manifests
                if str(manifest.get('rel_dir') or '').strip()
                and any((manifest.get('scripts') or {}).get(name) for name in ('dev', 'start', 'serve', 'preview'))
            ),
            None,
        )
        if preferred:
            return str(preferred.get('path') or '')
        if manifests:
            return str(manifests[0].get('path') or '')

    if any(token in lowered for token in ('pip', 'poetry', 'uv ', 'manage.py', 'pytest', 'tox')):
        for root in _workspace_python_roots(workspace_path, codebase_context):
            for candidate in (root.get('requirements'), root.get('pyproject'), root.get('manage_py')):
                if str(candidate or '').strip():
                    return str(candidate)

    return str(runtime.get('entrypoint') or '')


def _build_overview_runtime_entrypoints(project: Project, codebase_context: dict, runtime: dict) -> list[dict]:
    workspace_path = _project_workspace_path(project)
    if not workspace_path:
        return []

    items: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(label: str, path: str = "", command: str = "", detail: str = "") -> None:
        normalized_path = str(path or "").replace("\\", "/").strip()
        normalized_command = str(command or "").strip()
        normalized_detail = str(detail or "").strip()
        if not (normalized_path or normalized_command or normalized_detail):
            return
        key = (normalized_path, normalized_command)
        if key in seen:
            return
        seen.add(key)
        items.append({
            'label': label,
            'path': normalized_path,
            'command': normalized_command,
            'detail': normalized_detail,
        })

    runtime_type = str(runtime.get('runtime_type') or '').strip().lower()
    if runtime_type and runtime_type != 'unknown':
        runtime_detail = 'Detected from repository entrypoints.'
        if runtime.get('preview_url'):
            runtime_detail = f"Preview URL: {runtime.get('preview_url')}"
        add(
            f"{runtime_type.title()} runtime",
            str(runtime.get('entrypoint') or ''),
            str(runtime.get('run_command') or ''),
            runtime_detail,
        )
    if runtime.get('setup_command'):
        add(
            'Setup command',
            _setup_command_entry_path(workspace_path, codebase_context, runtime),
            str(runtime.get('setup_command') or ''),
            'Detected setup or install command for the active runtime.',
        )

    for root in _workspace_python_roots(workspace_path, codebase_context)[:4]:
        rel_dir = str(root.get('rel_dir') or '')
        manage_py = str(root.get('manage_py') or '')
        if manage_py:
            command = _prefix_command_for_dir(rel_dir, 'python manage.py runserver') if str(root.get('framework') or '').lower() == 'django' else ''
            detail = 'Django management entrypoint.' if str(root.get('framework') or '').lower() == 'django' else 'Python entrypoint root.'
            add(f"Python entrypoint in {rel_dir or 'project root'}", manage_py, command, detail)

    for manifest in _workspace_package_manifests(workspace_path, codebase_context)[:6]:
        scripts = manifest.get('scripts') if isinstance(manifest.get('scripts'), dict) else {}
        package_manager = str(manifest.get('package_manager') or 'npm')
        rel_dir = str(manifest.get('rel_dir') or '')
        for script_name in ('dev', 'start', 'serve', 'preview'):
            if scripts.get(script_name):
                add(
                    f"Package script in {rel_dir or 'project root'}",
                    str(manifest.get('path') or ''),
                    _prefix_command_for_dir(rel_dir, _run_script_command(package_manager, script_name)),
                    f"Uses `{script_name}` from `{manifest.get('path')}`.",
                )
                break

    return items[:5]


def _build_overview_read_first(blueprint: dict, codebase_context: dict, runtime_entrypoints: list[dict]) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()

    def add(title: str, path: str, reason: str) -> None:
        normalized = str(path or '').replace("\\", "/").strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        items.append({
            'title': title,
            'path': normalized,
            'reason': reason,
        })

    for path in _confirmed_overview_doc_paths(blueprint, codebase_context)[:3]:
        add(PurePosixPath(path).name, path, 'Repository documentation or instruction content detected from indexed files.')
    for entry in runtime_entrypoints[:2]:
        if isinstance(entry, dict) and entry.get('path'):
            add('Runtime entrypoint', str(entry.get('path')), 'Useful for understanding how the application boots locally.')
    api_source_paths: list[str] = []
    for item in _blueprint_list(blueprint.get('api_endpoints'))[:8]:
        if not isinstance(item, dict):
            continue
        source = item.get('source') or {}
        if not isinstance(source, dict):
            continue
        for key in ('url_file', 'view_file'):
            value = str(source.get(key) or '').strip()
            if value:
                api_source_paths.append(value)
    if api_source_paths:
        add('Primary backend routes', api_source_paths[0], 'Start here to trace routed endpoints back to their handlers.')
    database_sources = _blueprint_list(codebase_context.get('database_source_files'))
    if database_sources:
        add('Primary data model', str(database_sources[0]), 'Useful before changing persistence rules, schema, or API payloads.')
    return items[:5]


def _build_overview_recent_changes(project: Project) -> list[dict]:
    items: list[dict] = []
    changesets = Changeset.objects.filter(project=project).prefetch_related('files_changed', 'feature').order_by('-created_at')[:4]
    for changeset in changesets:
        file_list = list(changeset.files_changed.values_list('file_path', flat=True)[:3])
        detail = str(changeset.description or '').strip()
        if not detail and file_list:
            detail = f"Affects {_format_path_list(file_list, max_paths=3)}."
        items.append({
            'title': changeset.title,
            'status': changeset.status,
            'detail': detail or 'Recorded project changeset.',
            'meta': _overview_time_label(changeset.created_at),
        })
    if items:
        return items

    history = FeatureHistory.objects.select_related('feature').order_by('-at')[:4]
    for entry in history:
        stage = str(entry.stage or '').replace('_', ' ').strip() or 'workflow'
        action = str(entry.action or 'updated').replace('_', ' ').strip()
        detail = str(entry.comment or '').strip() or f"{action.title()} in {stage} by {entry.by}."
        items.append({
            'title': entry.feature.title if entry.feature_id else 'Tracked work item',
            'status': stage,
            'detail': detail,
            'meta': _overview_time_label(entry.at),
        })
    return items


def _build_overview_next_steps(blueprint: dict, runtime_entrypoints: list[dict], read_first: list[dict], features_payload: list[dict]) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()

    def add(title: str, detail: str) -> None:
        normalized_title = str(title or '').strip()
        normalized_detail = str(detail or '').strip()
        if not normalized_title or not normalized_detail:
            return
        key = f"{normalized_title}|{normalized_detail}"
        if key in seen:
            return
        seen.add(key)
        items.append({
            'title': normalized_title,
            'detail': normalized_detail,
        })

    for item in _blueprint_list(blueprint.get('onboarding_checklist'))[:2]:
        if isinstance(item, dict):
            add(str(item.get('task') or '').strip(), str(item.get('instructions') or item.get('why_important') or '').strip())

    first_runtime = next((item for item in runtime_entrypoints if isinstance(item, dict) and item.get('command')), None)
    if first_runtime:
        runtime_path = str(first_runtime.get('path') or '').strip()
        runtime_command = str(first_runtime.get('command') or '').strip()
        location = f" from `{runtime_path}`" if runtime_path else ""
        add('Run the main entrypoint locally', f"Use `{runtime_command}`{location} to confirm the current baseline before changing behavior.")

    testing = blueprint.get('testing_strategy') if isinstance(blueprint.get('testing_strategy'), dict) else {}
    validation_command = str(testing.get('run_command') or '').strip()
    if validation_command:
        add('Validate the current baseline', f"Run `{validation_command}` early so later regressions are easier to isolate.")

    if read_first:
        read_paths = [str(item.get('path') or '') for item in read_first[:3] if isinstance(item, dict) and item.get('path')]
        if read_paths:
            add('Read the core repo files first', f"Start with {_format_path_list(read_paths, max_paths=3)} before editing deeper modules.")

    active_count = sum(1 for item in features_payload if str(item.get('status') or '') in {'development', 'testing', 'code_review'})
    if active_count:
        add('Check in-flight work before large edits', f"There {'is' if active_count == 1 else 'are'} {active_count} active tracked work item{'s' if active_count != 1 else ''} that may already touch the same surfaces.")

    return items[:5]


def _build_blueprint_overview_insights(project: Project, blueprint: dict, codebase_context: dict, features_payload: list[dict]) -> dict:
    workspace_path = _project_workspace_path(project)
    runtime = detect_runtime(workspace_path) if workspace_path else {}
    runtime_entrypoints = _build_overview_runtime_entrypoints(project, codebase_context, runtime)
    read_first = _build_overview_read_first(blueprint, codebase_context, runtime_entrypoints)
    return {
        'overview_project_health': _build_overview_project_health(blueprint, runtime, features_payload, codebase_context),
        'overview_current_risks': _build_overview_current_risks(blueprint),
        'overview_runtime_entrypoints': runtime_entrypoints,
        'overview_read_first': read_first,
        'overview_recent_changes': _build_overview_recent_changes(project),
        'overview_next_steps': _build_overview_next_steps(blueprint, runtime_entrypoints, read_first, features_payload),
    }


def _suggested_work_items(project: Project, features_payload: list[dict] | None = None) -> list[dict]:
    features_payload = features_payload or _project_features_payload(project)
    existing_titles = {str(item.get('title') or '').strip().lower() for item in features_payload}
    suggestions = []

    for item in (project.blueprint or {}).get('feature_inventory') or []:
        title = str(item.get('title') or '').strip()
        if not title or title.lower() in existing_titles:
            continue
        suggestions.append({
            'title': title,
            'reason': str(item.get('description') or item.get('implementation_notes') or 'Suggested from the current blueprint.'),
            'source': 'blueprint',
            'suggested_stage': str(item.get('status') or 'backlog'),
        })
        if len(suggestions) >= 5:
            return suggestions

    for item in (project.blueprint or {}).get('change_guide') or []:
        area = str(item.get('area') or '').strip()
        if not area:
            continue
        title = f"{area} follow-up"
        if title.lower() in existing_titles:
            continue
        suggestions.append({
            'title': title,
            'reason': str(item.get('notes') or 'Suggested from the blueprint change guide.'),
            'source': 'change_guide',
            'suggested_stage': 'backlog',
        })
        if len(suggestions) >= 5:
            break
    return suggestions


def _derive_onboarding_ai_suggestions(
    project: Project,
    runtime: dict | None,
    features_payload: list[dict],
    suggested_work_items: list[dict],
) -> list[str]:
    blueprint = project.blueprint if isinstance(project.blueprint, dict) else {}
    suggestions: list[str] = []
    source_type = _project_source_type(project)

    read_first = _blueprint_list(blueprint.get('overview_read_first'))
    if read_first:
        item = read_first[0] if isinstance(read_first[0], dict) else {}
        title = str(item.get('title') or item.get('label') or 'the recommended starting files').strip()
        reason = str(item.get('reason') or '').strip()
        suggestions.append(
            f"Start with {title}{f' to {reason.lower()}' if reason else ' before making changes'}."
        )

    runtime_command = str((runtime or {}).get('run_command') or '').strip()
    if runtime_command:
        suggestions.append(f"Run `{runtime_command}` in Workspace to verify the app boots before changing behavior.")
    elif project.workspace_id:
        suggestions.append("Open Workspace and confirm the detected runtime or setup commands before editing code.")

    if suggested_work_items:
        top_item = suggested_work_items[0]
        title = str(top_item.get('title') or 'the top suggested work item').strip()
        reason = str(top_item.get('reason') or '').strip()
        suggestions.append(
            f"Turn {title} into a tracked work item{f' because {reason.lower()}' if reason else ''}."
        )
    elif not features_payload:
        suggestions.append("Create the first work item from the current blueprint so planning and implementation stay aligned.")
    else:
        active_feature = next(
            (feature for feature in features_payload if str(feature.get('status') or '') in {'backlog', 'development', 'testing', 'code_review'}),
            None,
        )
        if active_feature:
            title = str(active_feature.get('title') or 'the active work item').strip()
            status = str(active_feature.get('status') or 'current').replace('_', ' ')
            suggestions.append(f"Continue with {title} from the {status} stage and keep the blueprint in sync with the change.")

    docs_available = bool(str(blueprint.get('readme_excerpt') or '').strip()) or bool(_blueprint_list(blueprint.get('instruction_files')))
    if docs_available and source_type in {'github', 'folder'}:
        suggestions.append("Use the Repository and Onboarding tabs together to map root docs, important folders, and runtime entrypoints before deeper edits.")

    if blueprint and source_type in {'starter', 'github', 'folder'}:
        suggestions.append("Regenerate the blueprint after structural changes so repository docs, onboarding context, and architecture notes stay accurate.")

    return _dedupe_json_items([item for item in suggestions if item])[:4]


def _derive_onboarding_summary(project: Project, runtime: dict | None, features_payload: list[dict] | None = None) -> dict:
    features_payload = features_payload or _project_features_payload(project)
    source_type = _project_source_type(project)
    source_label = {
        'starter': 'Managed starter project',
        'github': 'Imported GitHub repository',
        'folder': 'Connected local project folder',
    }.get(source_type, 'Project')
    next_steps = []
    if source_type in {'github', 'folder'}:
        next_steps.extend([
            'Review onboarding first to understand how this codebase is organized.',
            'Open the blueprint to inspect architecture, repository structure, and key workflows.',
        ])
    else:
        next_steps.extend([
            'Review the overview and first-run context for the generated starter.',
            'Create or review the initial work items before editing code.',
        ])
    next_steps.append('Use Work Items to manage scope and Workspace to implement code changes.')
    suggested_work_items = _suggested_work_items(project, features_payload)
    ai_suggestions = _derive_onboarding_ai_suggestions(project, runtime, features_payload, suggested_work_items)

    runtime_hint = runtime.get('run_command') if isinstance(runtime, dict) else None
    return {
        'source_label': source_label,
        'recommended_start_tab': _recommended_start_tab(project),
        'next_steps': next_steps,
        'ai_suggestions': ai_suggestions,
        'suggested_work_items': suggested_work_items,
        'runtime_hint': runtime_hint or 'Runtime command will appear once detected.',
        'existing_work_items': len(features_payload),
        'has_blueprint': bool(project.blueprint),
    }


def _project_flow_payload(project: Project, runtime: dict | None, features_payload: list[dict] | None = None) -> list[dict]:
    features_payload = features_payload or _project_features_payload(project)
    source_type = _project_source_type(project)
    recommended = _recommended_start_tab(project)
    runtime_suffix = ''
    if isinstance(runtime, dict) and runtime.get('runtime_type'):
        runtime_suffix = f" using {runtime.get('runtime_type')}"
    steps = [
        {
            'id': 'overview',
            'title': 'Project overview',
            'description': 'Understand the project source, stack, runtime, and current health.',
            'status': 'current' if recommended == 'overview' else 'ready',
        },
        {
            'id': 'onboarding',
            'title': 'Get oriented',
            'description': 'Learn how the repo is structured and where to start contributing.',
            'status': 'current' if recommended == 'onboarding' else 'ready',
        },
        {
            'id': 'blueprint',
            'title': 'Read the blueprint',
            'description': 'Inspect architecture, repository map, APIs, schema, and workflows.',
            'status': 'ready' if project.blueprint else 'pending',
        },
        {
            'id': 'work_items',
            'title': 'Plan and track work',
            'description': 'Manage the same work items in list and board views.',
            'status': 'ready' if features_payload else 'pending',
        },
        {
            'id': 'code',
            'title': 'Edit in workspace',
            'description': f"Implement and review changes in the live workspace{runtime_suffix}.",
            'status': 'ready' if project.workspace_id else 'pending',
        },
    ]
    if source_type == 'starter':
        steps[0]['status'] = 'current'
        if len(steps) > 1 and steps[1]['status'] == 'current':
            steps[1]['status'] = 'ready'
    return steps


