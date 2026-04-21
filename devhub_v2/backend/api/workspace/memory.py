import html
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from django.utils import timezone

from agents.core.workspace import SKIP_DIRS
from core.models import Changeset, ChatMessage, Feature, Project

from api.project_utils import DEVHUB_META_DIR, MEMORY_DB_ERRORS, PROJECT_INSTRUCTIONS_FILE, PROJECT_MEMORY_FILE
from api.workspace.runtime import detect_runtime

logger = logging.getLogger(__name__)

BLUEPRINT_SECTION_LABELS = {
    'design_doc': 'Design Doc',
    'overview': 'Overview',
    'repository': 'Repository',
    'services': 'Services & Components',
    'api': 'API Reference',
    'database': 'Database Schema',
    'workflows': 'Workflows & Sequences',
    'setup': 'Setup & Environment',
    'quality': 'Quality & Security',
    'knowledge': 'Knowledge Base',
}

BLUEPRINT_SECTION_FIELDS = {
    'design_doc': ['design_document_markdown', 'design_document_sections'],
    'overview': ['project_summary', 'architecture_overview', 'mermaid_architecture', 'mermaid_service_dependencies', 'data_flow', 'tech_stack_details', 'feature_inventory', 'sdlc_pipeline', 'overview_project_health', 'overview_current_risks', 'overview_runtime_entrypoints', 'overview_read_first', 'overview_recent_changes', 'overview_next_steps'],
    'repository': ['directory_guide', 'repository_map', 'repo_tree', 'repo_tree_nodes', 'readme_excerpt', 'instruction_files', 'file_structure_visualizer', 'change_guide'],
    'services': ['services', 'key_components', 'integration_points'],
    'api': ['api_endpoints'],
    'database': ['database_schema', 'mermaid_erd'],
    'workflows': ['sequence_flows', 'common_workflows'],
    'setup': ['setup_steps', 'environment_variables', 'onboarding_checklist'],
    'quality': ['security_considerations', 'performance_notes', 'testing_strategy', 'code_quality_standards'],
    'knowledge': ['key_concepts', 'faq', 'gotchas'],
}

LLM_BLUEPRINT_SECTION_KEYS = {'overview', 'services', 'api', 'database', 'workflows', 'setup', 'quality', 'knowledge'}
TOKEN_FREE_BLUEPRINT_SECTION_KEYS = {'design_doc', 'repository', 'api', 'setup', 'quality', 'knowledge'}


def _devhub_meta_dir(workspace_path: Path) -> Path:
    path = workspace_path / DEVHUB_META_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _project_memory_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / PROJECT_MEMORY_FILE


def _project_instructions_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / PROJECT_INSTRUCTIONS_FILE


def _deep_docs_progress_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / "deep-docs-progress.json"


def _write_deep_docs_progress(workspace_path: Path, payload: dict) -> None:
    path = _deep_docs_progress_path(workspace_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    progress = dict(payload)
    progress["updated_at"] = timezone.now().isoformat()
    serialized = json.dumps(progress)
    temp_fd, temp_path = tempfile.mkstemp(prefix="deep-docs-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)

        for attempt in range(5):
            try:
                os.replace(temp_path, path)
                temp_path = None
                return
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))

        path.write_text(serialized, encoding="utf-8")
        temp_path = None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _safe_write_deep_docs_progress(workspace_path: Path, payload: dict) -> None:
    try:
        _write_deep_docs_progress(workspace_path, payload)
    except Exception:
        logger.exception("Failed to write deep docs progress for %s", workspace_path)


def _read_deep_docs_progress(workspace_path: Path) -> dict | None:
    path = _deep_docs_progress_path(workspace_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read deep docs progress from %s", path)
        return None


def _slice_blueprint_section(blueprint: dict, section_key: str) -> dict[str, Any]:
    return {
        field: blueprint.get(field)
        for field in BLUEPRINT_SECTION_FIELDS.get(section_key, [])
        if field in blueprint
    }


def _persist_blueprint_state(project: Project, blueprint: dict) -> None:
    project.blueprint = blueprint
    project.save(update_fields=['blueprint'])


def _render_project_features_summary(project: Project, limit: int = 10) -> str:
    lines = []
    features = Feature.objects.filter(project=project).order_by('-created_at')[:limit]
    for feature in features:
        lines.append(f"- {feature.title} [{feature.status}]")
        if feature.description:
            lines.append(f"  Description: {feature.description[:240]}")
        spec = feature.spec or {}
        if spec.get('technical_approach'):
            lines.append(f"  Approach: {str(spec['technical_approach'])[:240]}")
    return "\n".join(lines) if lines else "No active DevHub work items are recorded yet."


def _render_recent_changes_summary(project: Project, limit: int = 8) -> str:
    lines = []
    changesets = Changeset.objects.filter(project=project).order_by('-created_at')[:limit]
    for changeset in changesets:
        file_list = list(changeset.files_changed.values_list('file_path', flat=True)[:8])
        lines.append(f"- {changeset.title} [{changeset.status}]")
        if file_list:
            lines.append(f"  Files: {', '.join(file_list)}")
    return "\n".join(lines) if lines else "No recorded changesets yet."


def _build_default_project_memory(project: Project, workspace_path: Path) -> str:
    runtime = detect_runtime(workspace_path)
    tech = ", ".join(project.tech_stack or []) or "Unknown"
    blueprint = project.blueprint or {}
    setup_steps = blueprint.get('setup_steps') or []
    setup_text = "\n".join(f"- {step if isinstance(step, str) else step.get('step', '')}" for step in setup_steps[:5]) or "- No setup guidance yet."
    architecture = str(blueprint.get('architecture_overview') or project.description or "No architecture summary yet.")[:1200]

    return f"""# Project Memory

## Project
- Name: {project.name}
- Tech Stack: {tech}
- Runtime: {runtime.get('runtime_type') or 'unknown'}
- Run Command: {runtime.get('run_command') or 'unknown'}

## Architecture Summary
{architecture}

## Setup Notes
{setup_text}

## Known Features
{_render_project_features_summary(project)}

## Recent Changes
{_render_recent_changes_summary(project)}
"""


def _build_default_project_instructions(project: Project, workspace_path: Path) -> str:
    runtime = detect_runtime(workspace_path)
    tech = ", ".join(project.tech_stack or []) or "Unknown"
    return f"""# DevHub Instructions

Project: {project.name}
Tech Stack: {tech}
Runtime: {runtime.get('runtime_type') or 'unknown'}

## Guidance
- Preserve the existing project structure and runtime conventions.
- Prefer editing existing files over creating duplicate parallel implementations.
- Keep Blueprint, Features, Pipeline, and Onboarding aligned with real code changes.
- Update related UI, logic, styles, and runtime wiring together when behavior changes.

## Product Expectations
- This project should remain runnable after changes.
- New features should reflect the current codebase, not a generic starter.
- Favor minimal, targeted edits and reuse existing architecture patterns.

## Notes
- Add project-specific architecture rules, conventions, and deployment constraints here over time.
"""


def _read_project_memory(project: Project, workspace_path: Path) -> str:
    memory_path = _project_memory_path(workspace_path)
    if not memory_path.exists():
        memory_path.write_text(_build_default_project_memory(project, workspace_path), encoding='utf-8')
    return memory_path.read_text(encoding='utf-8', errors='ignore')


def _read_project_instructions(project: Project, workspace_path: Path) -> str:
    instructions_path = _project_instructions_path(workspace_path)
    if not instructions_path.exists():
        instructions_path.write_text(_build_default_project_instructions(project, workspace_path), encoding='utf-8')
    return instructions_path.read_text(encoding='utf-8', errors='ignore')


def _write_project_memory(project: Project, workspace_path: Path, content: str):
    memory_path = _project_memory_path(workspace_path)
    memory_path.write_text(content, encoding='utf-8')


def _update_project_memory(project: Project, workspace_path: Path, request_text: str, applied_files: list[str], memory_updates: list[str] | None = None):
    current_memory = _read_project_memory(project, workspace_path)
    updates = "\n".join(f"- {item}" for item in (memory_updates or []) if item)
    if not updates:
        updates = "- No planner-authored memory updates."
    changed = ", ".join(applied_files) if applied_files else "No files changed."
    appended = f"""

## Latest Update
- Request: {request_text}
- Changed Files: {changed}

### Durable Notes
{updates}

## Recent Changes
{_render_recent_changes_summary(project)}
"""
    _write_project_memory(project, workspace_path, (current_memory[:14000] + appended)[:18000])


def _workspace_file_inventory(workspace_path: Path, limit: int = 400) -> str:
    items = []
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for filename in sorted(files):
            path = Path(root) / filename
            rel_path = str(path.relative_to(workspace_path)).replace('\\', '/')
            if rel_path.startswith(f"{DEVHUB_META_DIR}/"):
                continue
            items.append(rel_path)
            if len(items) >= limit:
                return "\n".join(items)
    return "\n".join(items)


def _recent_chat_history(project: Project, limit: int = 12) -> str:
    messages = list(ChatMessage.objects.filter(project=project).order_by('-created_at')[:limit].values('role', 'content'))
    messages.reverse()
    if not messages:
        return "No recent chat history."
    return "\n".join(f"- {item['role']}: {item['content'][:400]}" for item in messages)


def _normalize_mermaid_chart(chart: str, diagram_type: str = "graph") -> str:
    text = str(chart or "").replace("\\n", "\n").strip()
    if not text:
        return ""

    def _escape_graph_label_text(value: str) -> str:
        label = html.unescape(str(value or ""))
        label = label.replace("\\n", " ")
        label = label.replace("\r", " ").replace("\n", " ")
        label = re.sub(r"\s+", " ", label).strip()
        label = label.replace("\\", "\\\\").replace('"', '\\"')
        return label

    def _rewrite_graph_label(match: re.Match[str], template: str) -> str:
        node_id = str(match.group("id") or "").strip()
        raw_label = str(match.group("label") or "").strip()
        if not node_id or not raw_label:
            return match.group(0)
        if raw_label.startswith('"') and raw_label.endswith('"'):
            return match.group(0)
        return template.format(id=node_id, label=_escape_graph_label_text(raw_label))

    def _normalize_graph_line(line: str) -> str:
        patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\[\((?P<label>[^"\n][^)\n]*?)\)\]'), '{id}[("{label}")]'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\[\[(?P<label>[^"\n][^\]\n]*?)\]\]'), '{id}[["{label}"]]'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\(\((?P<label>[^"\n][^)\n]*?)\)\)'), '{id}(("{label}"))'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\(\[(?P<label>[^"\n][^\]\n]*?)\]\)'), '{id}(["{label}"])'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\[(?P<label>[^"\[(\n][^\]\n]*?)\]'), '{id}["{label}"]'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\((?P<label>[^"\[(\n][^)\n]*?)\)'), '{id}("{label}")'),
            (re.compile(r'(?P<id>\b[A-Za-z][A-Za-z0-9_]*\b)\{(?P<label>[^"\n][^}\n]*?)\}'), '{id}{{"{label}"}}'),
        ]

        normalized = str(line or "")
        for pattern, template in patterns:
            normalized = pattern.sub(lambda match, tpl=template: _rewrite_graph_label(match, tpl), normalized)
        return normalized

    if diagram_type == "erd":
        text = re.sub(r'^\s*erDiagram\s*;?', 'erDiagram\n', text, flags=re.IGNORECASE)
        text = re.sub(r';\s*', '\n', text)
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if not lines or lines[0].strip().lower() != 'erdiagram':
            lines.insert(0, 'erDiagram')
        return "\n".join(lines)

    if diagram_type == "sequence":
        def _escape_sequence_label_text(value: str) -> str:
            inner = html.unescape(str(value or ""))
            inner = inner.replace("\\n", " newline ")
            inner = inner.replace("\r", "").replace("\n", " newline ")
            inner = re.sub(r"<([^>]+)>", r" \1 ", inner)
            inner = re.sub(r"\[([^\]]+)\]", r" \1 ", inner)
            inner = re.sub(r"[{}()]", " ", inner)
            inner = inner.replace("&", " and ")
            inner = re.sub(r"""["'`]""", "", inner)
            inner = re.sub(r"[^A-Za-z0-9 _-]+", " ", inner)
            inner = re.sub(r"\s+", " ", inner)
            return inner.strip()

        def _starts_sequence_statement(line: str) -> bool:
            stripped = str(line or "").strip()
            if not stripped:
                return False
            if stripped.lower() == "sequencediagram":
                return True
            if re.match(r"^(participant|actor|note|activate|deactivate|autonumber|title|link|box|end|alt|else|opt|loop|par|and|critical|break|rect)\b", stripped, re.IGNORECASE):
                return True
            return bool(re.match(r"^[A-Za-z0-9_.()[\]`\"'/-]+\s*(?:-->>|->>|-->|->|<<--|<<->>|<<->|--x|x--)", stripped))

        text = re.sub(r'^\s*sequenceDiagram\s*;?', 'sequenceDiagram\n', text, flags=re.IGNORECASE)
        text = re.sub(r';\s*', '\n', text)
        raw_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        merged_lines: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not merged_lines or _starts_sequence_statement(stripped):
                merged_lines.append(stripped)
            else:
                merged_lines[-1] = f"{merged_lines[-1]}\\n{stripped}"
        if not merged_lines or merged_lines[0].strip().lower() != 'sequencediagram':
            merged_lines.insert(0, 'sequenceDiagram')
        sanitized_lines: list[str] = []
        for line in merged_lines:
            if line.strip().lower() == "sequencediagram":
                sanitized_lines.append("sequenceDiagram")
                continue
            if ":" in line and re.search(r"(?:-->>|->>|-->|->|<<--|<<->>|<<->|--x|x--)", line):
                prefix, label = line.split(":", 1)
                sanitized_lines.append(f"{prefix}: {_escape_sequence_label_text(label.strip())}")
            else:
                sanitized_lines.append(line)
        return "\n".join(sanitized_lines)

    if text.lower().startswith('graph ') or text.lower().startswith('flowchart '):
        text = re.sub(r';\s*', '\n', text)
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        return "\n".join(_normalize_graph_line(line) for line in lines)
    return text
