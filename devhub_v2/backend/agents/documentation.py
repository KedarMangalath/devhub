from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from django.utils import timezone

from agents.memory import build_blueprint_context
from core.models import DocumentationRun, DocumentationSection, Project


def _runtime_profile(workspace_path: Path) -> dict[str, str]:
    if (workspace_path / 'manage.py').exists():
        return {
            'runtime': 'django',
            'setup_command': 'pip install -r requirements.txt',
            'run_command': 'python manage.py runserver',
        }
    if (workspace_path / 'package.json').exists() and (
        (workspace_path / 'vite.config.js').exists() or (workspace_path / 'vite.config.ts').exists()
    ):
        return {
            'runtime': 'vite',
            'setup_command': 'npm install',
            'run_command': 'npm run dev',
        }
    if (workspace_path / 'package.json').exists():
        return {
            'runtime': 'node',
            'setup_command': 'npm install',
            'run_command': 'npm start',
        }
    if (workspace_path / 'requirements.txt').exists() and (workspace_path / 'main.py').exists():
        return {
            'runtime': 'python',
            'setup_command': 'pip install -r requirements.txt',
            'run_command': 'python main.py',
        }
    return {
        'runtime': 'static',
        'setup_command': 'No setup command detected from the indexed files.',
        'run_command': 'python -m http.server 4173 --bind 127.0.0.1',
    }


def _evidence(path: str, note: str) -> dict[str, str]:
    return {'path': path, 'note': note}


def _important_files(cache: dict, limit: int = 24) -> list[dict[str, Any]]:
    return list((cache.get('important_files') or [])[:limit])


def _overview_section(project: Project, cache: dict, workspace_path: Path) -> dict[str, Any]:
    runtime = _runtime_profile(workspace_path)
    directory_counts = cache.get('directory_counts') or {}
    top_directories = sorted(directory_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    instruction_files = cache.get('instruction_files') or []
    readme_excerpt = str(cache.get('readme_excerpt') or '').strip()

    lines = [
        f"{project.name} is indexed from the live workspace and documented against fingerprint `{cache.get('fingerprint', 'unknown')}`.",
        f"Detected runtime: {runtime['runtime']}. Primary run command: `{runtime['run_command']}`.",
        f"Indexed file count: {cache.get('file_count', 0)}.",
        "",
        "Top-level areas:",
    ]
    for directory, count in top_directories:
        label = directory if directory != '.' else 'repo root'
        lines.append(f"- `{label}`: {count} files")

    if instruction_files:
        lines.extend(["", "Instruction files loaded:"])
        for item in instruction_files[:5]:
            lines.append(f"- `{item.get('path')}`")

    if readme_excerpt:
        lines.extend([
            "",
            "README signal:",
            readme_excerpt[:900],
        ])

    evidence = [
        _evidence(item.get('path', ''), 'High-signal file from the repository index.')
        for item in _important_files(cache, limit=6)
        if item.get('path')
    ]
    for item in instruction_files[:3]:
        evidence.append(_evidence(item.get('path', ''), 'Project instruction file loaded into the index.'))

    return {
        'key': 'overview',
        'title': 'Overview',
        'summary': f"Indexed {cache.get('file_count', 0)} files across {len(directory_counts)} top-level areas.",
        'markdown': "\n".join(lines).strip(),
        'evidence': evidence,
    }


def _repository_section(cache: dict) -> dict[str, Any]:
    important_files = _important_files(cache, limit=18)
    repo_tree = str(cache.get('repo_tree') or '').strip()

    lines = [
        "Important files:",
    ]
    for item in important_files:
        lines.append(f"- `{item.get('path')}`: {item.get('summary') or item.get('brief') or 'Indexed file'}")

    if repo_tree:
        lines.extend([
            "",
            "Repository tree:",
            "```text",
            repo_tree[:12000],
            "```",
        ])

    evidence = [
        _evidence(item.get('path', ''), 'Repository map ranked this file as high signal.')
        for item in important_files
        if item.get('path')
    ]
    return {
        'key': 'repository',
        'title': 'Repository Map',
        'summary': f"Captured {len(important_files)} high-signal files and the indexed repo tree.",
        'markdown': "\n".join(lines).strip(),
        'evidence': evidence,
    }


def _module_catalog_section(cache: dict) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in _important_files(cache, limit=28):
        path = str(item.get('path') or '')
        top_level = path.split('/', 1)[0] if '/' in path else '.'
        grouped[top_level].append(item)

    lines = []
    evidence = []
    for directory, items in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        label = directory if directory != '.' else 'repo root'
        lines.append(f"### `{label}`")
        for item in items[:6]:
            path = item.get('path', '')
            summary = item.get('summary') or item.get('brief') or 'Indexed file'
            lines.append(f"- `{path}`: {summary}")
            if path:
                evidence.append(_evidence(path, f"Represents the `{label}` area in the module catalog."))
        lines.append("")

    content = "\n".join(lines).strip() or "No module catalog data available yet."
    return {
        'key': 'modules',
        'title': 'App / Module Catalog',
        'summary': f"Grouped important files into {len(grouped)} top-level areas.",
        'markdown': content,
        'evidence': evidence[:18],
    }


def _api_surface_section(cache: dict) -> dict[str, Any]:
    routes = list(cache.get('routes') or [])
    route_files = [
        item for item in _important_files(cache, limit=24)
        if item.get('routes') or any(token in str(item.get('path', '')).lower() for token in ('urls', 'router', 'api', 'view'))
    ]

    lines = []
    if routes:
        lines.append("Detected routes and endpoints:")
        for route in routes[:24]:
            lines.append(f"- `{route}`")
    else:
        lines.append("No route patterns were clearly detected from the indexed files.")

    if route_files:
        lines.extend(["", "Files that appear to own API or routing behavior:"])
        for item in route_files[:10]:
            lines.append(f"- `{item.get('path')}`: {item.get('summary') or 'Routing or API-related file.'}")

    evidence = []
    for item in route_files[:10]:
        path = item.get('path', '')
        if path:
            evidence.append(_evidence(path, 'Detected as an API, routing, or view-related file.'))
    return {
        'key': 'api_surface',
        'title': 'API Surface',
        'summary': f"Detected {len(routes)} route patterns from indexed source files.",
        'markdown': "\n".join(lines).strip(),
        'evidence': evidence,
    }


def _data_model_section(cache: dict) -> dict[str, Any]:
    data_models = list(cache.get('data_models') or [])
    model_files = [
        item for item in _important_files(cache, limit=24)
        if item.get('data_models') or 'model' in str(item.get('path', '')).lower()
    ]

    lines = []
    if data_models:
        lines.append("Detected entities, models, or schema types:")
        for name in data_models[:24]:
            lines.append(f"- `{name}`")
    else:
        lines.append("No data model names were clearly detected from the indexed files.")

    if model_files:
        lines.extend(["", "Files carrying model or schema responsibility:"])
        for item in model_files[:10]:
            lines.append(f"- `{item.get('path')}`: {item.get('summary') or 'Model-related file.'}")

    evidence = []
    for item in model_files[:10]:
        path = item.get('path', '')
        if path:
            evidence.append(_evidence(path, 'Detected as a model, schema, or typed data file.'))
    return {
        'key': 'data_model',
        'title': 'Data Model',
        'summary': f"Detected {len(data_models)} model or type names.",
        'markdown': "\n".join(lines).strip(),
        'evidence': evidence,
    }


def _runtime_setup_section(project: Project, cache: dict, workspace_path: Path) -> dict[str, Any]:
    runtime = _runtime_profile(workspace_path)
    instruction_files = cache.get('instruction_files') or []

    lines = [
        f"Detected runtime family: {runtime['runtime']}",
        f"- Setup command: `{runtime['setup_command']}`",
        f"- Run command: `{runtime['run_command']}`",
        "",
        "Configuration and setup-oriented files:",
    ]

    config_candidates = []
    for item in _important_files(cache, limit=28):
        path = str(item.get('path') or '')
        if any(token in path.lower() for token in ('package.json', 'requirements', 'manage.py', 'vite.config', 'docker', '.env', 'readme')):
            config_candidates.append(item)

    for item in config_candidates[:10]:
        lines.append(f"- `{item.get('path')}`: {item.get('summary') or item.get('brief') or 'Configuration file.'}")

    if project.github_url:
        lines.extend(["", f"Source repository: {project.github_url}"])

    evidence = []
    for item in config_candidates[:10]:
        path = item.get('path', '')
        if path:
            evidence.append(_evidence(path, 'Detected as setup, runtime, or configuration evidence.'))
    for item in instruction_files[:3]:
        path = item.get('path', '')
        if path:
            evidence.append(_evidence(path, 'Project instruction file influences setup and execution expectations.'))

    return {
        'key': 'runtime_setup',
        'title': 'Runtime / Setup',
        'summary': f"Runtime detected as {runtime['runtime']} with setup command `{runtime['setup_command']}`.",
        'markdown': "\n".join(lines).strip(),
        'evidence': evidence,
    }


def _append_evidence(markdown: str, evidence: list[dict[str, str]]) -> str:
    if not evidence:
        return markdown.strip()
    lines = [markdown.strip(), "", "### Evidence"]
    for item in evidence:
        lines.append(f"- `{item.get('path', '')}`: {item.get('note', '')}")
    return "\n".join(lines).strip()


def _documentation_output_path(workspace_path: Path) -> Path:
    docs_dir = workspace_path / 'docs'
    if docs_dir.exists() and docs_dir.is_dir():
        target_dir = docs_dir
    else:
        target_dir = workspace_path / '.devhub' / 'docs'
        target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / 'DEVHUB_CODEBASE_REFERENCE.md'


def _render_reference_markdown(project: Project, run: DocumentationRun, sections: list[DocumentationSection]) -> str:
    lines = [
        f"# {project.name} Codebase Reference",
        "",
        f"- Generated by DevHub: {timezone.localtime(run.completed_at or timezone.now()).isoformat()}",
        f"- Documentation mode: `{run.mode}`",
        f"- Fingerprint: `{run.target_fingerprint or 'unknown'}`",
        "",
    ]

    for section in sections:
        lines.extend([
            f"## {section.title}",
            "",
            section.markdown.strip(),
            "",
        ])

    return "\n".join(lines).strip() + "\n"


def generate_codebase_reference_sync(project: Project) -> DocumentationRun:
    workspace_path = Path(project.local_path or '').expanduser().resolve()
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise RuntimeError('Project workspace is not available for documentation generation.')

    cache = build_blueprint_context(project, workspace_path, force=True)
    run = DocumentationRun.objects.create(
        project=project,
        mode='codebase_reference',
        status='running',
        target_fingerprint=str(cache.get('fingerprint') or ''),
        metadata={
            'indexed_files': cache.get('file_count', 0),
            'top_directories': cache.get('directory_counts', {}),
        },
    )

    try:
        section_specs = [
            _overview_section(project, cache, workspace_path),
            _repository_section(cache),
            _module_catalog_section(cache),
            _api_surface_section(cache),
            _data_model_section(cache),
            _runtime_setup_section(project, cache, workspace_path),
        ]

        created_sections = []
        for order, spec in enumerate(section_specs, start=1):
            section = DocumentationSection.objects.create(
                run=run,
                key=spec['key'],
                title=spec['title'],
                order=order,
                status='completed',
                summary=spec.get('summary', ''),
                markdown=_append_evidence(spec.get('markdown', ''), spec.get('evidence', [])),
                evidence=spec.get('evidence', []),
                metadata=spec.get('metadata', {}),
            )
            created_sections.append(section)

        output_path = _documentation_output_path(workspace_path)
        output_path.write_text(_render_reference_markdown(project, run, created_sections), encoding='utf-8')

        run.status = 'completed'
        run.summary = (
            f"Generated {len(created_sections)} verified documentation sections from "
            f"{cache.get('file_count', 0)} indexed files."
        )
        run.output_path = str(output_path)
        run.completed_at = timezone.now()
        run.metadata = {
            **(run.metadata or {}),
            'section_count': len(created_sections),
            'output_path': str(output_path),
        }
        run.save(update_fields=['status', 'summary', 'output_path', 'completed_at', 'metadata'])
    except Exception as exc:
        run.status = 'failed'
        run.error = str(exc)
        run.completed_at = timezone.now()
        run.save(update_fields=['status', 'error', 'completed_at'])

    return run
