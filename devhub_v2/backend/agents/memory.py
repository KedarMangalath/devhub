import hashlib
import json
import os
import re
from pathlib import Path

from agents.workspace import SKIP_DIRS
from django.db import OperationalError, ProgrammingError
from core.models import Changeset, ChatMessage, EpisodicMemory, Project, SemanticMemory, WorkingMemory

INDEXABLE_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json', '.md'}
BLUEPRINT_CACHE_VERSION = 5
BLUEPRINT_CONFIG_FILES = {
    'package.json', 'package-lock.json', 'requirements.txt', 'pyproject.toml', 'manage.py',
    'vite.config.js', 'vite.config.ts', 'next.config.js', 'next.config.mjs', 'docker-compose.yml',
    'dockerfile', 'readme.md', 'README.md', '.env.example', 'tsconfig.json',
}
BLUEPRINT_CACHE_FILE = 'blueprint-context.json'
REPO_MAP_FILE = 'repo-map.md'
INSTRUCTION_FILES = [
    'DEVHUB.md',
    'AGENTS.md',
    'GEMINI.md',
    'CLAUDE.md',
    '.devhub/DEVHUB.md',
]
STOPWORDS = {
    'the', 'and', 'for', 'with', 'that', 'this', 'from', 'into', 'your', 'have', 'will',
    'were', 'been', 'http', 'https', 'file', 'files', 'code', 'user', 'using', 'used',
}
MEMORY_DB_ERRORS = (OperationalError, ProgrammingError)


def _tokenize(text: str) -> list[str]:
    return [
        token for token in re.findall(r'[a-zA-Z0-9_]+', (text or '').lower())
        if len(token) > 2 and token not in STOPWORDS
    ]


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 160) -> list[str]:
    cleaned = (text or '').strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _extract_symbol(content: str) -> str:
    patterns = [
        r'^\s*class\s+([A-Za-z0-9_]+)',
        r'^\s*def\s+([A-Za-z0-9_]+)',
        r'^\s*function\s+([A-Za-z0-9_]+)',
        r'^\s*const\s+([A-Za-z0-9_]+)\s*=',
        r'^\s*export\s+default\s+function\s+([A-Za-z0-9_]+)',
    ]
    for line in (content or '').splitlines()[:80]:
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)
    return ''


def _detect_language(file_path: Path) -> str:
    mapping = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript-react',
        '.ts': 'typescript',
        '.tsx': 'typescript-react',
        '.html': 'html',
        '.css': 'css',
        '.json': 'json',
        '.md': 'markdown',
    }
    return mapping.get(file_path.suffix.lower(), file_path.suffix.lower().lstrip('.') or 'text')


def _workspace_fingerprint(workspace_path: Path) -> str:
    digest = hashlib.sha1()
    digest.update(f'blueprint-cache-v{BLUEPRINT_CACHE_VERSION}'.encode('utf-8'))
    for file_path in sorted(_iter_blueprint_files(workspace_path), key=lambda item: str(item)):
        rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
        if rel_path.startswith('.devhub/'):
            continue
        try:
            stat = file_path.stat()
        except OSError:
            continue
        digest.update(rel_path.encode('utf-8', errors='ignore'))
        digest.update(str(stat.st_size).encode('utf-8'))
        digest.update(str(getattr(stat, 'st_mtime_ns', int(stat.st_mtime * 1_000_000_000))).encode('utf-8'))
    return digest.hexdigest()


def _extract_imports(content: str, language: str) -> list[str]:
    imports: list[str] = []
    for line in (content or '').splitlines()[:120]:
        stripped = line.strip()
        if language.startswith('python') and (stripped.startswith('import ') or stripped.startswith('from ')):
            imports.append(stripped[:160])
        elif language in {'javascript', 'javascript-react', 'typescript', 'typescript-react'} and (
            stripped.startswith('import ') or 'require(' in stripped
        ):
            imports.append(stripped[:160])
    return imports[:12]


def _extract_routes(content: str, language: str) -> list[str]:
    routes = []
    if language.startswith('python'):
        patterns = [
            r'path\(\s*[\'"]([^\'"]+)',
            r're_path\(\s*[\'"]([^\'"]+)',
            r'@app\.(get|post|put|delete|patch)\(\s*[\'"]([^\'"]+)',
            r'@router\.(get|post|put|delete|patch)\(\s*[\'"]([^\'"]+)',
        ]
    elif language in {'javascript', 'javascript-react', 'typescript', 'typescript-react'}:
        patterns = [
            r'router\.(get|post|put|delete|patch)\(\s*[\'"]([^\'"]+)',
            r'app\.(get|post|put|delete|patch)\(\s*[\'"]([^\'"]+)',
            r'path:\s*[\'"]([^\'"]+)',
            r'Route\s+path=[{]?[\'"]([^\'"]+)',
        ]
    else:
        return []
    for line in (content or '').splitlines():
        for pattern in patterns:
            match = re.search(pattern, line)
            if not match:
                continue
            route = match.group(match.lastindex or 1)
            if route and route not in routes:
                routes.append(route)
    return routes[:16]


def _extract_data_models(content: str, language: str) -> list[str]:
    if language not in {'python', 'javascript', 'javascript-react', 'typescript', 'typescript-react'}:
        return []
    models = []
    patterns = [
        r'class\s+([A-Za-z0-9_]+)\((?:models\.Model|BaseModel|Model)\)',
        r'interface\s+([A-Za-z0-9_]+)',
        r'type\s+([A-Za-z0-9_]+)\s*=',
        r'const\s+([A-Za-z0-9_]+Schema)\s*=',
    ]
    for line in (content or '').splitlines()[:200]:
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                symbol = match.group(1)
                if symbol not in models:
                    models.append(symbol)
    return models[:10]


def _extract_markdown_headings(content: str, limit: int = 8) -> list[str]:
    headings = []
    for line in (content or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        heading = stripped.lstrip("#").strip()
        if heading and heading not in headings:
            headings.append(heading)
        if len(headings) >= limit:
            break
    return headings


def _extract_json_keys(content: str, limit: int = 12) -> list[str]:
    try:
        payload = json.loads(content)
    except Exception:
        return []
    if isinstance(payload, dict):
        return [str(key) for key in list(payload.keys())[:limit]]
    return []


def _extract_command_snippets(content: str, limit: int = 8) -> list[str]:
    commands = []
    seen = set()
    pattern = re.compile(r"^(pnpm|npm|yarn|bun|python|pip|uv|poetry|docker|make|cargo|go|bash|sh|\./)", re.IGNORECASE)
    for raw_line in (content or "").splitlines():
        line = raw_line.strip()
        if not line or len(line) > 180:
            continue
        candidate = line.split("#", 1)[0].strip()
        if not candidate or not pattern.match(candidate):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        commands.append(candidate)
        if len(commands) >= limit:
            break
    return commands


def _infer_file_kind(rel_path: str, language: str, role_hints: list[str], headings: list[str], json_keys: list[str], routes: list[str], data_models: list[str]) -> str:
    lowered_path = rel_path.lower()
    file_name = Path(lowered_path).name
    if file_name == "readme.md":
        return "readme"
    if file_name == "security.md":
        return "security-doc"
    if file_name == "contributing.md":
        return "contributing-doc"
    if file_name == "package.json":
        return "package-manifest"
    if file_name.startswith("tsconfig"):
        return "typescript-config"
    if "vite.config" in file_name or "next.config" in file_name or "webpack" in file_name or "rollup" in file_name or "tsdown.config" in file_name:
        return "build-config"
    if file_name in {"dockerfile", "docker-compose.yml"}:
        return "container-config"
    if lowered_path.endswith(".env.example"):
        return "env-template"
    if "/prompts/" in lowered_path and language == "markdown":
        return "prompt-doc"
    if "/scripts/" in lowered_path or language == "sh":
        return "script"
    if language == "markdown":
        if headings:
            return "documentation"
        return "notes"
    if routes or "api" in role_hints:
        return "api-module"
    if data_models or "data-model" in role_hints:
        return "data-model"
    if "ui" in role_hints and ("page" in lowered_path or "view" in lowered_path or "route" in lowered_path):
        return "page-component"
    if "ui" in role_hints:
        return "ui-component"
    if "routing" in role_hints:
        return "routing-module"
    if "config" in role_hints or json_keys:
        return "config"
    return "source-file"


def _build_file_explanation(rel_path: str, language: str, symbol: str, role_hints: list[str], imports: list[str], routes: list[str], data_models: list[str], headings: list[str], json_keys: list[str], commands: list[str]) -> tuple[str, str, str, str]:
    file_name = Path(rel_path).name
    file_kind = _infer_file_kind(rel_path, language, role_hints, headings, json_keys, routes, data_models)
    heading_suffix = f": {', '.join(headings[:5])}" if headings else ""
    command_suffix = f", especially {', '.join(commands[:3])}" if commands else ""
    command_examples = f" such as {', '.join(commands[:4])}" if commands else ""
    import_suffix = f" like {', '.join(imports[:4])}" if imports else ""
    route_suffix = f" like {', '.join(routes[:4])}" if routes else ""
    model_suffix = f": {', '.join(data_models[:5])}" if data_models else ""

    if file_kind == "readme":
        purpose = "Primary repository guide that explains what the project is, how to get it running, and which workflows matter first."
        why = "New developers usually start here because it establishes product context, setup order, and high-level repo conventions."
        how = f"Read the main headings first{heading_suffix}, then follow any setup or run commands it documents."
    elif file_kind == "security-doc":
        purpose = "Security policy and risk guidance for the repository."
        why = "It exists to document trust boundaries, security expectations, disclosure rules, or deployment safeguards that should not be inferred ad hoc."
        how = "Use it before exposing services, handling secrets, or making auth-related changes."
    elif file_kind == "contributing-doc":
        purpose = "Contributor workflow guide covering how changes should be developed, validated, and submitted."
        why = "It exists to keep contributions consistent by documenting validation steps, branch expectations, and review rules."
        how = f"Look for required commands and contribution rules{command_suffix}."
    elif file_kind == "package-manifest":
        purpose = "Node package manifest defining runtime metadata, scripts, dependencies, and package-manager behavior for the repo or workspace."
        why = "It exists as the control file for install/build/test commands and for declaring the dependency surface this project expects."
        how = f"Start with top-level keys like {', '.join(json_keys[:6]) or 'name, scripts, dependencies'} and then inspect the scripts section to understand day-to-day commands."
    elif file_kind == "typescript-config":
        purpose = "TypeScript compiler configuration that controls type-checking, module resolution, emitted output, and project references."
        why = "It exists to standardize how TypeScript is compiled across the repo so editors, builds, and tests all agree on the same rules."
        how = f"Read compiler-related keys such as {', '.join(json_keys[:6]) or 'compilerOptions and include/exclude'}, then compare it with nearby tsconfig variants if this repo has more than one."
    elif file_kind == "build-config":
        purpose = "Build or bundling configuration that tells the toolchain how to compile, package, or emit artifacts for this project."
        why = "It exists because the build pipeline has repo-specific entrypoints, output rules, plugins, or environment handling that cannot live in default tool settings."
        how = f"Start with `{symbol}` if present, then inspect imported helpers{import_suffix} to see which parts of the build are delegated elsewhere."
    elif file_kind == "container-config":
        purpose = "Container/runtime configuration for local or deployment environments."
        why = "It exists to codify how services, images, and environment assumptions should be assembled outside the application source itself."
        how = "Read the declared services, images, ports, and environment references before changing runtime or deployment behavior."
    elif file_kind == "env-template":
        purpose = "Environment-variable template showing which config values the project expects and how they should be provided."
        why = "It exists so setup is repeatable and secrets/config are documented without hardcoding them into source files."
        how = "Use it as the checklist for local configuration and compare it with setup docs before running the project."
    elif file_kind == "prompt-doc":
        purpose = "Prompt or instruction file used by the project as an input artifact for an LLM, agent, or guided workflow."
        why = "It exists because prompt wording is part of product behavior and needs to be versioned like code."
        how = f"Read the headings and body as executable product logic; changes here affect assistant behavior rather than application control flow."
    elif file_kind == "script":
        purpose = "Automation script used to install, build, scaffold, or operate part of the repository."
        why = "It exists to encode repeatable operational steps that would otherwise live in docs or manual terminal workflows."
        how = f"Read the invoked commands{command_examples} and any imported helpers to understand which environments or outputs it touches."
    elif file_kind == "documentation":
        title = headings[0] if headings else file_name
        purpose = f"Project documentation page focused on `{title}`."
        why = "It exists to explain a specific subsystem, workflow, or policy in more depth than inline code comments can."
        how = f"Read the heading structure{heading_suffix} and follow any referenced commands or file paths."
    elif file_kind == "api-module":
        purpose = "API-facing module that defines endpoints, handlers, or service integration behavior."
        why = "It exists to translate requests into application actions and to keep routing or handler logic separate from lower-level implementation details."
        route_text = f" Routes detected: {', '.join(routes[:4])}." if routes else ""
        how = f"Start with `{symbol}` if present and then trace the request flow through imports and downstream service calls.{route_text}"
    elif file_kind == "data-model":
        purpose = "Data model or type-definition file describing the shapes the application stores, exchanges, or validates."
        why = "It exists to centralize schema expectations so other layers can rely on shared structure instead of duplicating field logic."
        how = f"Start with the declared models or types{model_suffix} and then inspect which services or routes consume them."
    elif file_kind == "page-component":
        purpose = "Page-level UI module that usually composes other components and represents a route or large screen."
        why = "It exists to keep route-specific rendering, loading, and orchestration concerns out of smaller reusable components."
        how = f"Start with `{symbol}` if present, then trace imported components, hooks, and data calls to see how the page is assembled."
    elif file_kind == "ui-component":
        purpose = "Reusable UI component responsible for part of the interface."
        why = "It exists to encapsulate rendering behavior, styling, and interaction logic so screens can compose consistent UI pieces."
        how = f"Start with `{symbol}` if present and inspect props, imported utilities, and any sibling components it collaborates with."
    elif file_kind == "routing-module":
        purpose = "Routing or entrypoint module that wires screens, handlers, or navigation together."
        why = "It exists to centralize how the application exposes pages or request paths instead of scattering that wiring across the repo."
        how = f"Look for the declared routes{route_suffix} and the imports they dispatch into."
    elif file_kind == "config":
        purpose = "Configuration file that controls tooling, runtime behavior, or project conventions."
        why = "It exists to keep environment-specific or tool-specific rules out of application logic."
        how = f"Start with top-level keys such as {', '.join(json_keys[:6]) or 'the main config fields'} and compare them with the commands or tools that consume this file."
    else:
        parent_area = Path(rel_path).parent.as_posix().strip()
        area_label = "project root" if not parent_area or parent_area == "." else f"`{parent_area}`"
        purpose = f"Source file that contributes to the {area_label} area of the repository."
        why = "It exists as part of the application or tooling implementation for this part of the codebase."
        how = f"Start with `{symbol}` if present, then inspect imports and nearby files to understand how this module fits into the surrounding flow."

    summary = purpose
    if symbol and file_kind not in {"build-config", "api-module", "data-model", "page-component", "ui-component", "routing-module"}:
        summary += f" Its main symbol appears to be `{symbol}`."
    return file_kind, purpose, why, how


def _file_summary(file_path: Path, workspace_path: Path) -> dict | None:
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
    language = _detect_language(file_path)
    symbol = _extract_symbol(content)
    imports = _extract_imports(content, language)
    routes = _extract_routes(content, language)
    data_models = _extract_data_models(content, language)
    headings = _extract_markdown_headings(content)
    json_keys = _extract_json_keys(content)
    commands = _extract_command_snippets(content)
    line_count = len(content.splitlines())
    lowered_path = rel_path.lower()

    role_hints = []
    if 'component' in lowered_path or language.endswith('react'):
        role_hints.append('ui')
    if 'view' in lowered_path or 'page' in lowered_path or 'route' in lowered_path:
        role_hints.append('routing')
    if 'api' in lowered_path or 'service' in lowered_path or routes:
        role_hints.append('api')
    if 'model' in lowered_path or data_models:
        role_hints.append('data-model')
    if language == 'markdown':
        role_hints.append('docs')
    if file_path.name.lower() in BLUEPRINT_CONFIG_FILES:
        role_hints.append('config')
    file_kind, purpose, why, how = _build_file_explanation(
        rel_path,
        language,
        symbol,
        role_hints,
        imports,
        routes,
        data_models,
        headings,
        json_keys,
        commands,
    )

    summary_parts = [
        purpose,
        f"It has about {line_count} lines.",
        f"Primary symbol: {symbol}." if symbol else "",
        f"Top headings: {', '.join(headings[:5])}." if headings else "",
        f"Top-level keys: {', '.join(json_keys[:6])}." if json_keys else "",
        f"Key imports: {', '.join(imports[:5])}." if imports else "",
        f"Routes/endpoints: {', '.join(routes[:6])}." if routes else "",
        f"Data models/types: {', '.join(data_models[:6])}." if data_models else "",
        f"Representative commands: {', '.join(commands[:4])}." if commands else "",
    ]
    summary = " ".join(part for part in summary_parts if part).strip()

    return {
        'path': rel_path,
        'file_kind': file_kind,
        'language': language,
        'lines': line_count,
        'symbol': symbol,
        'imports': imports,
        'routes': routes,
        'data_models': data_models,
        'role_hints': role_hints,
        'headings': headings,
        'json_keys': json_keys,
        'commands': commands,
        'purpose': purpose,
        'why': why,
        'how': how,
        'excerpt': content[:1400],
        'brief': f"{rel_path} ({language}{', ' + ', '.join(role_hints) if role_hints else ''})",
        'summary': summary[:600],
    }


def _score_blueprint_file(summary: dict) -> int:
    score = 0
    path = str(summary.get('path') or '').lower()
    file_name = Path(path).name
    if file_name in BLUEPRINT_CONFIG_FILES:
        score += 12
    if summary.get('routes'):
        score += 10
    if summary.get('data_models'):
        score += 9
    if summary.get('symbol'):
        score += 3
    if any(hint in (summary.get('role_hints') or []) for hint in ('ui', 'api', 'data-model', 'routing')):
        score += 6
    if any(token in path for token in ('app', 'main', 'index', 'views', 'urls', 'router', 'models', 'components', 'pages')):
        score += 4
    return score


def _devhub_meta_dir(workspace_path: Path) -> Path:
    path = workspace_path / '.devhub'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _blueprint_cache_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / BLUEPRINT_CACHE_FILE


def _repo_map_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / REPO_MAP_FILE


def _instruction_context(workspace_path: Path) -> list[dict]:
    entries = []
    for rel_path in INSTRUCTION_FILES:
        path = workspace_path / rel_path
        excerpt = _read_text_excerpt(path, limit=3000)
        if excerpt:
            entries.append({
                'path': rel_path.replace('\\', '/'),
                'content': excerpt,
            })
    return entries


def _render_repo_map(project: Project, cache: dict) -> str:
    lines = [
        f"# Repo Map: {project.name}",
        "",
        f"- Fingerprint: {cache.get('fingerprint')}",
        f"- Indexed files: {cache.get('file_count')}",
        "",
        "## Top Directories",
    ]
    for directory, count in sorted((cache.get('directory_counts') or {}).items(), key=lambda item: (-item[1], item[0]))[:12]:
        lines.append(f"- `{directory}`: {count} files")

    lines.extend(["", "## Important Files"])
    for item in (cache.get('important_files') or [])[:24]:
        lines.append(f"- `{item.get('path')}`: {item.get('summary')}")

    instruction_files = cache.get('instruction_files') or []
    if instruction_files:
        lines.extend(["", "## Project Instructions"])
        for item in instruction_files:
            lines.append(f"- `{item.get('path')}`")

    routes = cache.get('routes') or []
    if routes:
        lines.extend(["", "## Detected Routes"])
        for route in routes[:20]:
            lines.append(f"- `{route}`")

    data_models = cache.get('data_models') or []
    if data_models:
        lines.extend(["", "## Detected Models / Types"])
        for model in data_models[:20]:
            lines.append(f"- `{model}`")

    repo_tree = cache.get('repo_tree') or ''
    if repo_tree:
        lines.extend(["", "## Repo Tree", "```text", repo_tree[:12000], "```"])

    return "\n".join(lines)[:20000]


def _render_repo_tree(file_summaries: list[dict], project_name: str) -> str:
    tree: dict[str, dict] = {}
    for item in file_summaries:
        path = str(item.get('path') or '')
        if not path:
            continue
        node = tree
        for part in path.split('/'):
            node = node.setdefault(part, {})

    def render(node: dict[str, dict], prefix: str = '') -> list[str]:
        keys = sorted(node.keys(), key=lambda key: (0 if node[key] else 1, key.lower()))
        lines: list[str] = []
        for index, key in enumerate(keys):
            is_last = index == len(keys) - 1
            connector = '`- ' if is_last else '|- '
            lines.append(f"{prefix}{connector}{key}")
            child = node[key]
            if child:
                child_prefix = f"{prefix}{'   ' if is_last else '|  '}"
                lines.extend(render(child, child_prefix))
        return lines

    lines = [f"{project_name}/"]
    lines.extend(render(tree))
    return "\n".join(lines)[:24000]


def _build_repo_tree_nodes(indexed_paths: list[str], project_name: str, max_nodes: int = 1600, max_children_per_dir: int = 60) -> list[dict]:
    tree: dict[str, dict] = {}
    node_budget = 0

    for raw_path in indexed_paths:
        path = str(raw_path or "").strip("/")
        if not path:
            continue
        parts = [part for part in path.split("/") if part]
        current = tree
        current_path_parts: list[str] = []
        for index, part in enumerate(parts):
            current_path_parts.append(part)
            is_file = index == len(parts) - 1
            entry = current.setdefault(
                part,
                {
                    "name": part,
                    "path": "/".join(current_path_parts),
                    "type": "file" if is_file else "directory",
                    "children": {},
                },
            )
            if not is_file:
                entry["type"] = "directory"
                current = entry["children"]
            node_budget += 1
            if node_budget >= max_nodes:
                break
        if node_budget >= max_nodes:
            break

    def finalize(children: dict[str, dict]) -> list[dict]:
        entries = sorted(
            children.values(),
            key=lambda item: (0 if item.get("type") == "directory" else 1, str(item.get("name", "")).lower()),
        )
        rendered: list[dict] = []
        overflow = len(entries) - max_children_per_dir
        for entry in entries[:max_children_per_dir]:
            child_nodes = finalize(entry.get("children") or {}) if entry.get("type") == "directory" else []
            rendered.append(
                {
                    "name": entry.get("name"),
                    "path": entry.get("path"),
                    "type": entry.get("type"),
                    "children": child_nodes,
                    "child_count": len(entry.get("children") or {}),
                }
            )
        if overflow > 0:
            rendered.append(
                {
                    "name": f"... {overflow} more items",
                    "path": f"{project_name}/__truncated__/{len(rendered)}",
                    "type": "file",
                    "children": [],
                    "child_count": 0,
                    "truncated": True,
                }
            )
        return rendered

    return finalize(tree)


def build_blueprint_context(project: Project, workspace_path: Path, force: bool = False) -> dict:
    cache_path = _blueprint_cache_path(workspace_path)
    fingerprint = _workspace_fingerprint(workspace_path)

    if not force and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding='utf-8', errors='ignore'))
            if cached.get('fingerprint') == fingerprint and cached.get('cache_version') == BLUEPRINT_CACHE_VERSION:
                summary_text = str(cached.get('compact_summary') or '')[:12000]
                upsert_working_memory(project, 'blueprint_context', summary_text, {
                    'fingerprint': fingerprint,
                    'cache_version': BLUEPRINT_CACHE_VERSION,
                    'file_count': cached.get('file_count', 0),
                    'cache_path': str(cache_path),
                })
                return cached
        except Exception:
            pass

    file_summaries = []
    directory_counts: dict[str, int] = {}
    for file_path in _iter_blueprint_files(workspace_path):
        rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
        if rel_path.startswith('.devhub/'):
            continue
        directory = rel_path.split('/')[0] if '/' in rel_path else '.'
        directory_counts[directory] = directory_counts.get(directory, 0) + 1
        summary = _file_summary(file_path, workspace_path)
        if summary:
            file_summaries.append(summary)

    indexed_paths = [item.get('path') for item in file_summaries if item.get('path')]

    ranked_files = sorted(file_summaries, key=_score_blueprint_file, reverse=True)
    important_files = ranked_files[:40]
    all_file_summaries = ranked_files[:200]
    routes = []
    data_models = []
    for item in all_file_summaries:
        for route in item.get('routes') or []:
            if route not in routes:
                routes.append(route)
        for model in item.get('data_models') or []:
            if model not in data_models:
                data_models.append(model)

    readme_excerpt = ''
    for candidate in ('README.md', 'readme.md'):
        readme_excerpt = _read_text_excerpt(workspace_path / candidate)
        if readme_excerpt:
            break
    instruction_files = _instruction_context(workspace_path)

    compact_lines = [
        f"Project: {project.name}",
        f"Fingerprint: {fingerprint}",
        f"Indexed files: {len(file_summaries)}",
        "Top directories:",
    ]
    for directory, count in sorted(directory_counts.items(), key=lambda item: (-item[1], item[0]))[:12]:
        compact_lines.append(f"- {directory}: {count} files")
    compact_lines.append("Important files:")
    for item in important_files[:20]:
        compact_lines.append(f"- {item['path']}: {item['summary']}")
    if routes:
        compact_lines.append("Detected routes/endpoints:")
        for route in routes[:20]:
            compact_lines.append(f"- {route}")
    if data_models:
        compact_lines.append("Detected data models/types:")
        for model in data_models[:20]:
            compact_lines.append(f"- {model}")
    if instruction_files:
        compact_lines.append("Project instructions:")
        for item in instruction_files:
            compact_lines.append(f"- {item['path']}: {item['content'][:220].replace(chr(10), ' ')}")

    repo_tree = _render_repo_tree(file_summaries, project.name)
    repo_tree_nodes = _build_repo_tree_nodes(indexed_paths, project.name)

    compact_summary = "\n".join(compact_lines)[:12000]
    cache = {
        'cache_version': BLUEPRINT_CACHE_VERSION,
        'fingerprint': fingerprint,
        'file_count': len(file_summaries),
        'directory_counts': directory_counts,
        'indexed_paths': indexed_paths[:4000],
        'important_files': important_files,
        'all_file_summaries': all_file_summaries,
        'routes': routes[:24],
        'data_models': data_models[:24],
        'readme_excerpt': readme_excerpt[:4000],
        'instruction_files': instruction_files,
        'repo_tree': repo_tree,
        'repo_tree_nodes': repo_tree_nodes,
        'compact_summary': compact_summary,
    }

    cache_path.write_text(json.dumps(cache, indent=2), encoding='utf-8')
    _repo_map_path(workspace_path).write_text(_render_repo_map(project, cache), encoding='utf-8')
    upsert_working_memory(project, 'blueprint_context', compact_summary, {
        'fingerprint': fingerprint,
        'cache_version': BLUEPRINT_CACHE_VERSION,
        'file_count': len(file_summaries),
        'cache_path': str(cache_path),
        'repo_map_path': str(_repo_map_path(workspace_path)),
    })
    return cache


def _read_text_excerpt(file_path: Path, limit: int = 4000) -> str:
    try:
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding='utf-8', errors='ignore')[:limit]
    except Exception:
        return ''
    return ''


def read_deep_file_content(workspace_path: Path, rel_path: str, limit: int = 8000) -> str:
    """Read full file content (up to *limit* chars) for targeted deep analysis."""
    try:
        file_path = workspace_path / rel_path
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding='utf-8', errors='ignore')[:limit]
    except Exception:
        return ''
    return ''


def select_files_for_section(cache: dict, section_key: str) -> list[dict]:
    """Return the most relevant indexed files for a given Blueprint section.

    Uses role hints and path-name heuristics to rank files by relevance.
    """
    important_files = list((cache.get('important_files') or [])[:40])
    expanded_files = list((cache.get('all_file_summaries') or [])[:200])
    all_files: list[dict] = []
    seen_paths: set[str] = set()
    for item in [*expanded_files, *important_files]:
        path = str(item.get('path') or '')
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        all_files.append(item)

    # Section-specific relevance matchers
    matchers: dict[str, dict] = {
        'services': {
            'role_hints': {'api', 'routing', 'ui'},
            'path_tokens': {'app', 'main', 'index', 'server', 'views', 'urls', 'router', 'service', 'worker'},
        },
        'api': {
            'role_hints': {'api', 'routing'},
            'path_tokens': {'urls', 'router', 'views', 'api', 'routes', 'endpoint', 'controller'},
        },
        'database': {
            'role_hints': {'data-model'},
            'path_tokens': {'model', 'schema', 'migration', 'database', 'entity', 'orm'},
        },
        'workflows': {
            'role_hints': {'api', 'routing', 'ui'},
            'path_tokens': {'workflow', 'pipeline', 'agent', 'task', 'feature', 'views', 'main'},
        },
        'setup': {
            'role_hints': {'config', 'docs'},
            'path_tokens': {'package.json', 'requirements', 'manage', 'docker', 'env', 'readme', 'config', 'setup', 'vite.config'},
        },
        'quality': {
            'role_hints': {'config', 'docs'},
            'path_tokens': {'test', 'spec', 'eslint', 'prettier', 'security', 'auth', 'middleware', 'lint', 'pyproject'},
        },
        'knowledge': {
            'role_hints': {'api', 'ui', 'routing', 'data-model'},
            'path_tokens': {'readme', 'doc', 'agent', 'base', 'core', 'main', 'app', 'index'},
        },
    }

    matcher = matchers.get(section_key, {'role_hints': set(), 'path_tokens': set()})

    def relevance_score(item: dict) -> float:
        score = 0.0
        hints = set(item.get('role_hints') or [])
        if hints & matcher['role_hints']:
            score += 10.0

        path_lower = str(item.get('path', '')).lower()
        for token in matcher['path_tokens']:
            if token in path_lower:
                score += 5.0

        if item.get('routes'):
            if section_key in ('api', 'services', 'workflows'):
                score += 8.0
        if item.get('data_models'):
            if section_key == 'database':
                score += 8.0

        # Larger files tend to have more detail
        lines = item.get('lines', 0)
        if lines > 100:
            score += 2.0
        if lines > 300:
            score += 2.0

        return score

    scored = [(relevance_score(item), item) for item in all_files]
    scored.sort(key=lambda x: -x[0])

    # Return top files with a non-zero score, fallback to top important files
    result = [item for score, item in scored if score > 0][:12]
    if not result:
        result = all_files[:12] or important_files[:12]
    return result



def _iter_workspace_files(workspace_path: Path) -> list[Path]:
    items: list[Path] = []
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() in INDEXABLE_EXTENSIONS:
                items.append(path)
    return items


def _iter_blueprint_files(workspace_path: Path) -> list[Path]:
    config_names = {name.lower() for name in BLUEPRINT_CONFIG_FILES}
    items: list[Path] = []

    # Project root marker files — if a subdirectory contains any of these,
    # it's a separate project and should not be indexed as part of this codebase.
    project_root_markers = {'.git', 'package.json', 'Cargo.toml', 'go.mod', 'pom.xml', 'setup.py', 'pyproject.toml'}

    # Track directories detected as nested project roots so we skip them.
    nested_project_roots: set[str] = set()

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
        rel_root = str(Path(root).relative_to(workspace_path)).replace('\\', '/')
        depth = 0 if rel_root == '.' else rel_root.count('/') + 1

        # Check if this directory is under a known nested project root — skip it.
        if any(rel_root == npr or rel_root.startswith(npr + '/') for npr in nested_project_roots):
            dirs.clear()
            continue

        # At depth >= 2, detect nested project roots by looking for marker files.
        # Depth 0 = workspace root, depth 1 = top-level dirs like 'backend/', 'data/'
        # Depth 2+ = potential nested projects like 'data/projects/<id>/'
        if depth >= 2:
            file_set = set(files) | set(dirs)
            if file_set & project_root_markers:
                nested_project_roots.add(rel_root)
                dirs.clear()
                continue

        for filename in files:
            path = Path(root) / filename
            rel_path = str(path.relative_to(workspace_path)).replace('\\', '/')
            if rel_path.startswith('.devhub/'):
                continue
            if path.suffix.lower() in INDEXABLE_EXTENSIONS or filename.lower() in config_names:
                items.append(path)
    return items


def index_semantic_memory(project: Project, workspace_path: Path, changed_paths: list[str] | None = None):
    try:
        SemanticMemory.objects.exists()
    except MEMORY_DB_ERRORS:
        return

    if changed_paths:
        target_paths = []
        for rel_path in changed_paths:
            normalized = str(rel_path).replace('\\', '/')
            try:
                SemanticMemory.objects.filter(project=project, file_path=normalized).delete()
            except MEMORY_DB_ERRORS:
                return
            candidate = workspace_path / rel_path
            if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in INDEXABLE_EXTENSIONS:
                target_paths.append(candidate)
    else:
        target_paths = _iter_workspace_files(workspace_path)

    for file_path in target_paths:
        rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        try:
            SemanticMemory.objects.filter(project=project, file_path=rel_path).delete()
        except MEMORY_DB_ERRORS:
            return
        chunks = _chunk_text(content)
        if not chunks:
            continue

        symbol = _extract_symbol(content)
        entries = []
        for index, chunk in enumerate(chunks):
            entries.append(
                SemanticMemory(
                    project=project,
                    file_path=rel_path,
                    chunk_index=index,
                    symbol=symbol,
                    content=chunk[:2400],
                    keywords=_tokenize(f'{rel_path} {symbol} {chunk}')[:80],
                    metadata={'length': len(chunk)},
                )
            )
        try:
            SemanticMemory.objects.bulk_create(entries)
        except MEMORY_DB_ERRORS:
            return


def recall_semantic_memory(project: Project, query: str, selected_file: str = '', limit: int = 6) -> list[dict]:
    try:
        entries = list(SemanticMemory.objects.filter(project=project))
    except MEMORY_DB_ERRORS:
        return []

    query_tokens = set(_tokenize(f'{query} {selected_file}'))
    results = []
    for entry in entries:
        keywords = set(entry.keywords or [])
        overlap = len(query_tokens & keywords)
        if not overlap and selected_file and selected_file != entry.file_path:
            continue
        score = float(overlap)
        if entry.file_path == selected_file:
            score += 4.0
        elif selected_file and entry.file_path.startswith('/'.join(selected_file.split('/')[:-1])):
            score += 1.5
        if score <= 0:
            continue
        results.append({
            'file_path': entry.file_path,
            'symbol': entry.symbol,
            'content': entry.content[:800],
            'score': score,
        })

    results.sort(key=lambda item: (-item['score'], item['file_path']))
    return results[:limit]


def upsert_working_memory(project: Project, scope: str, summary: str, context: dict | None = None) -> WorkingMemory:
    try:
        memory, _ = WorkingMemory.objects.update_or_create(
            project=project,
            scope=scope,
            defaults={'summary': summary, 'context': context or {}},
        )
        return memory
    except MEMORY_DB_ERRORS:
        return None


def get_working_memory(project: Project, scope: str = 'implementation') -> str:
    try:
        memory = WorkingMemory.objects.filter(project=project, scope=scope).first()
        return memory.summary if memory else ''
    except MEMORY_DB_ERRORS:
        return ''


def record_episode(
    project: Project,
    memory_type: str,
    title: str,
    summary: str,
    related_files: list[str] | None = None,
    metadata: dict | None = None,
) -> EpisodicMemory:
    try:
        return EpisodicMemory.objects.create(
            project=project,
            memory_type=memory_type,
            title=title,
            summary=summary,
            related_files=related_files or [],
            metadata=metadata or {},
        )
    except MEMORY_DB_ERRORS:
        return None


def compress_recent_activity(project: Project, limit: int = 10) -> str:
    lines = [f'Project: {project.name}']

    try:
        recent_episodes = EpisodicMemory.objects.filter(project=project).order_by('-created_at')[:limit]
        if recent_episodes:
            lines.append('Recent Episodes:')
            for episode in recent_episodes:
                lines.append(f'- {episode.memory_type}: {episode.title} :: {episode.summary[:180]}')
    except MEMORY_DB_ERRORS:
        return f'Project: {project.name}'

    try:
        recent_changes = Changeset.objects.filter(project=project).order_by('-created_at')[:limit]
        if recent_changes:
            lines.append('Recent Changesets:')
            for changeset in recent_changes:
                lines.append(f'- {changeset.title} [{changeset.status}]')
    except MEMORY_DB_ERRORS:
        pass

    try:
        recent_chat = ChatMessage.objects.filter(project=project).order_by('-created_at')[:limit]
        if recent_chat:
            lines.append('Recent Chat Themes:')
            for message in reversed(recent_chat):
                lines.append(f'- {message.role}: {message.content[:140]}')
    except MEMORY_DB_ERRORS:
        pass

    summary = '\n'.join(lines)[:5000]
    upsert_working_memory(project, 'implementation', summary, {'source': 'compress_recent_activity'})
    return summary


def build_memory_context(project: Project, query: str, selected_file: str = '') -> dict:
    working_summary = get_working_memory(project) or compress_recent_activity(project)
    blueprint_summary = get_working_memory(project, 'blueprint_context')
    try:
        episodes = EpisodicMemory.objects.filter(project=project).order_by('-created_at')[:6]
        episodic_summary = '\n'.join(
            f'- {item.memory_type}: {item.title} :: {item.summary[:180]}'
            for item in episodes
        ) or 'No episodic memory yet.'
    except MEMORY_DB_ERRORS:
        episodic_summary = 'Episodic memory unavailable until migrations are applied.'
    semantic_hits = recall_semantic_memory(project, query, selected_file=selected_file)
    semantic_summary = '\n'.join(
        f"- {item['file_path']} ({item.get('symbol') or 'context'}): {item['content'][:180]}"
        for item in semantic_hits
    ) or 'No semantic matches yet.'
    return {
        'working_summary': working_summary,
        'blueprint_summary': blueprint_summary or 'No cached codebase summary yet.',
        'episodic_summary': episodic_summary,
        'semantic_hits': semantic_hits,
        'semantic_summary': semantic_summary,
    }
