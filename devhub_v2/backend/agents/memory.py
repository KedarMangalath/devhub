import ast
import hashlib
import json
import os
import posixpath
import re
from collections import defaultdict
from pathlib import Path

from agents.api_reference import build_api_reference_catalog
from agents.workspace import SKIP_DIRS
from django.db import OperationalError, ProgrammingError
from core.models import Changeset, ChatMessage, EpisodicMemory, Project, SemanticMemory, WorkingMemory

INDEXABLE_EXTENSIONS = {
    # Web / JavaScript ecosystem
    '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json', '.md',
    '.vue', '.svelte', '.astro',
    # Go
    '.go',
    # Rust
    '.rs',
    # Java / Kotlin / Scala / Groovy
    '.java', '.kt', '.kts', '.scala', '.groovy',
    # C# / F# / VB.NET
    '.cs', '.fs', '.vb',
    # Ruby
    '.rb', '.erb', '.rake',
    # PHP
    '.php',
    # Elixir / Erlang
    '.ex', '.exs', '.erl', '.hrl',
    # Swift / Dart / Objective-C
    '.swift', '.dart', '.m', '.mm',
    # C / C++
    '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx',
    # Shell / scripting
    '.sh', '.bash', '.zsh', '.fish', '.ps1',
    # Config / infra / data
    '.yaml', '.yml', '.toml', '.ini', '.env', '.conf',
    '.sql', '.graphql', '.gql', '.proto',
    # Styling
    '.scss', '.sass', '.less',
    # Docs / templates
    '.rst', '.txt', '.jinja', '.jinja2', '.j2', '.tmpl',
    # Lua / R / Julia
    '.lua', '.r', '.jl',
    # Terraform / Pulumi / Nix
    '.tf', '.tfvars', '.nix',
    # Misc
    '.xml', '.gradle',
}
BLUEPRINT_CACHE_VERSION = 24  # bumped: deterministic fact extractors, quality/css/ws/integration injection
BLUEPRINT_CONFIG_FILES = {
    # JavaScript / Node
    'package.json', 'tsconfig.json',
    'vite.config.js', 'vite.config.ts', 'next.config.js', 'next.config.mjs',
    'nuxt.config.ts', 'nuxt.config.js', 'svelte.config.js', 'astro.config.mjs',
    'webpack.config.js', 'rollup.config.js', 'esbuild.config.js',
    'jest.config.js', 'jest.config.ts', 'vitest.config.ts',
    'eslint.config.js', '.eslintrc.json', 'prettier.config.js', '.prettierrc',
    # Python
    'requirements.txt', 'pyproject.toml', 'setup.py', 'setup.cfg',
    'pipfile', 'tox.ini', 'pytest.ini', 'manage.py',
    # Go
    'go.mod', 'go.sum',
    # Rust
    'cargo.toml',
    # Java / Kotlin / Scala
    'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts',
    'gradlew', 'mvnw', 'build.sbt',
    # Ruby
    'gemfile', 'rakefile', 'config.ru', '.ruby-version',
    # PHP
    'composer.json', 'artisan', 'index.php',
    # Elixir / Erlang
    'mix.exs', 'rebar.config', 'rebar3',
    # .NET
    'global.json', 'nuget.config', 'directory.build.props',
    # Swift / iOS
    'package.swift', 'podfile',
    # Infra / DevOps
    'dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
    '.env.example', '.env.sample',
    'makefile', 'justfile', 'taskfile.yml', 'taskfile.yaml',
    'ansible.cfg', 'vagrantfile',
    # Docs / project
    'readme.md', 'readme.rst', 'readme.txt', 'readme',
    'contributing.md', 'changelog.md', 'license', 'license.md',
}
BLUEPRINT_MAX_FILE_BYTES = 256 * 1024
BLUEPRINT_MAX_JSON_BYTES = 96 * 1024
BLUEPRINT_EXCERPT_CHARS = 1400
BLUEPRINT_SKIP_FILE_NAMES = {
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'bun.lock', 'bun.lockb',
    'cargo.lock', 'poetry.lock', 'composer.lock', 'gemfile.lock',
    'packages.lock.json', 'pubspec.lock',
}
BLUEPRINT_JUNK_PATTERNS = {
    'tsc_out.txt',
    '.tsbuildinfo',
}
BLUEPRINT_JUNK_PREFIXES = (
    '2026-',
    '2025-',
)
BLUEPRINT_SKIP_DIRS = {
    # JS build artifacts
    'dist', 'build', '.next', 'out',
    # Test coverage
    'coverage', '.nyc_output',
    # Dependencies (language-agnostic)
    'vendor', 'node_modules',
    # Temp / generated
    'tmp', 'temp', '.tmp',
    # Java / Kotlin / Scala / Gradle build output
    'target', '.gradle', '__pycache__',
    # Elixir / Erlang build output
    '_build', 'deps',
    # Python virtual envs
    '.venv', 'venv', 'env', '.env',
    # .NET build output
    'bin', 'obj',
    # iOS / macOS
    'pods', 'derived_data', '.build',
    # Misc generated
    'generated', 'gen', '.cache', '.parcel-cache',
}
BLUEPRINT_CACHE_FILE = 'blueprint-context.json'
BLUEPRINT_MANIFEST_FILE = 'manifest.json'
BLUEPRINT_DEPENDENCY_GRAPH_FILE = 'dependency-graph.json'
REPO_MAP_FILE = 'repo-map.md'
BLUEPRINT_TIER_1_NAMES = {
    # Docs
    'readme.md', 'readme.rst', 'readme.txt', 'readme',
    'contributing.md', 'security.md', 'changelog.md',
    '.env.example', '.env.sample',
    # JavaScript / TypeScript
    'package.json', 'tsconfig.json',
    'vite.config.ts', 'vite.config.js', 'next.config.js', 'next.config.mjs',
    'main.ts', 'main.tsx', 'main.js', 'main.jsx',
    'index.ts', 'index.tsx', 'index.js', 'index.jsx',
    'app.ts', 'app.tsx', 'app.js', 'app.jsx',
    'server.ts', 'server.js',
    # Python
    'requirements.txt', 'pyproject.toml', 'setup.py', 'manage.py',
    'main.py', 'app.py', 'wsgi.py', 'asgi.py',
    # Go
    'go.mod', 'main.go',
    # Rust
    'cargo.toml', 'main.rs', 'lib.rs',
    # Java / Kotlin / Scala
    'pom.xml', 'build.gradle', 'build.gradle.kts', 'build.sbt',
    'application.java', 'main.java',
    'application.kt', 'main.kt',
    # Ruby
    'gemfile', 'config.ru', 'application.rb', 'routes.rb',
    # PHP
    'composer.json', 'index.php',
    # Elixir
    'mix.exs', 'application.ex', 'router.ex', 'endpoint.ex',
    # .NET
    'program.cs', 'startup.cs', 'appsettings.json',
    # Infra
    'dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
    'makefile', 'justfile',
    # Django-specific
    'urls.py', 'settings.py',
}
BLUEPRINT_TIER_1_TOKENS = ('router', 'routes', 'urls', 'config', 'settings', 'application', 'startup')
BLUEPRINT_SUMMARY_SIZE_THRESHOLD = 20 * 1024
BLUEPRINT_LARGE_FILE_CHUNK_LINES = 120
BLUEPRINT_LARGE_FILE_CHUNK_OVERLAP = 20
BLUEPRINT_DISCOVERY_CONTENT_BYTES = 12 * 1024
BLUEPRINT_DISCOVERY_MAX_SCAN_FILES = 72
INSTRUCTION_FILES = [
    'DEVHUB.md',
    'AGENTS.md',
    'GEMINI.md',
    'CLAUDE.md',
    '.devhub/DEVHUB.md',
]
INSTRUCTION_DOC_NAME_TOKENS = (
    'readme',
    'documentation',
    'document',
    'design',
    'guide',
    'overview',
    'flow',
    'workflow',
    'architecture',
    'reference',
    'manual',
    'roadmap',
    'plan',
    'proposal',
    'integration',
    'setup',
    'faq',
    'concept',
    'permission',
    'role',
)
INSTRUCTION_DOC_DIR_TOKENS = {
    'docs',
    'doc',
    'documentation',
    'guides',
    'guide',
    'design',
    'plans',
}
SECTION_FILE_KIND_SCORES = {
    'services': {
        'source-file': 8.0,
        'api-module': 8.0,
        'routing-module': 8.0,
        'config': 4.0,
        'package-manifest': 4.0,
        'script': 4.0,
    },
}
STOPWORDS = {
    'the', 'and', 'for', 'with', 'that', 'this', 'from', 'into', 'your', 'have', 'will',
    'were', 'been', 'http', 'https', 'file', 'files', 'code', 'user', 'using', 'used',
}
MEMORY_DB_ERRORS = (OperationalError, ProgrammingError)
QUERY_INTENT_ALIASES = {
    'sandbox': {'sandbox', 'executor', 'process', 'spawn', 'terminal', 'runtime', 'isolation', 'workspace', 'pty', 'stdin', 'stdout', 'stderr', 'io'},
    'auth': {'auth', 'authentication', 'authorize', 'authorization', 'session', 'token', 'jwt', 'login', 'permission', 'acl'},
    'api': {'api', 'endpoint', 'route', 'router', 'handler', 'view', 'controller', 'request', 'response'},
    'backend': {'backend', 'server', 'service', 'worker', 'api', 'process', 'runtime'},
    'database': {'database', 'db', 'model', 'schema', 'entity', 'orm', 'migration', 'table', 'query'},
    'queue': {'queue', 'job', 'worker', 'task', 'background', 'scheduler', 'cron'},
    'config': {'config', 'settings', 'env', 'environment', 'flag', 'option', 'manifest'},
    'frontend': {'frontend', 'ui', 'component', 'page', 'view', 'screen', 'client'},
    'styling': {'color', 'colors', 'highlight', 'hover', 'theme', 'styling', 'style', 'css', 'class', 'tailwind', 'bg', 'text', 'accent'},
    'navigation': {'sidebar', 'nav', 'navigation', 'tab', 'tabs', 'menu', 'panel', 'item', 'items', 'selected', 'active'},
    'chat': {'chat', 'message', 'assistant', 'conversation', 'prompt', 'mention', 'context'},
    'docs': {'docs', 'documentation', 'blueprint', 'wiki', 'reference', 'onboarding', 'readme'},
}


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
        r'^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z0-9_]+)\s*\(',
        r'^\s*(?:pub\s+)?(?:struct|enum|trait|fn)\s+([A-Za-z0-9_]+)',
        r'^\s*type\s+([A-Za-z0-9_]+)\s+struct\s*\{',
        r'^\s*(?:public\s+)?(?:class|interface|record|enum)\s+([A-Za-z0-9_]+)',
        r'^\s*function\s+([A-Za-z0-9_]+)',
        r'^\s*const\s+([A-Za-z0-9_]+)\s*=',
        r'^\s*export\s+default\s+function\s+([A-Za-z0-9_]+)',
        r'^\s*defmodule\s+([A-Za-z0-9_.]+)',
        r'^\s*class\s+([A-Za-z0-9_:]+)\s*<',
    ]
    for line in (content or '').splitlines()[:80]:
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)
    return ''


def _detect_language(file_path: Path) -> str:
    file_name = file_path.name.lower()
    special_names = {
        'dockerfile': 'docker',
        'docker-compose.yml': 'docker-compose',
        'docker-compose.yaml': 'docker-compose',
        'compose.yml': 'docker-compose',
        'compose.yaml': 'docker-compose',
        'makefile': 'makefile',
        'justfile': 'just',
        'taskfile.yml': 'yaml',
        'taskfile.yaml': 'yaml',
        'jenkinsfile': 'groovy',
        'procfile': 'procfile',
        'gemfile': 'ruby',
        'rakefile': 'ruby',
        'podfile': 'ruby',
        'config.ru': 'ruby',
        '.env': 'env',
        '.env.example': 'env',
        '.env.sample': 'env',
        'go.mod': 'go-module',
        'go.sum': 'go-module',
        'cargo.toml': 'rust-manifest',
        'mix.exs': 'elixir',
        'package.swift': 'swift',
    }
    if file_name in special_names:
        return special_names[file_name]

    mapping = {
        # Web / JS ecosystem
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript-react',
        '.ts': 'typescript',
        '.tsx': 'typescript-react',
        '.vue': 'vue',
        '.svelte': 'svelte',
        '.astro': 'astro',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.json': 'json',
        '.md': 'markdown',
        '.rst': 'rst',
        # Go
        '.go': 'go',
        # Rust
        '.rs': 'rust',
        # Java / JVM
        '.java': 'java',
        '.kt': 'kotlin',
        '.kts': 'kotlin',
        '.scala': 'scala',
        '.groovy': 'groovy',
        # .NET
        '.cs': 'csharp',
        '.fs': 'fsharp',
        '.vb': 'vb',
        # Ruby
        '.rb': 'ruby',
        '.erb': 'ruby-erb',
        '.rake': 'ruby',
        # PHP
        '.php': 'php',
        # Elixir / Erlang
        '.ex': 'elixir',
        '.exs': 'elixir',
        '.erl': 'erlang',
        '.hrl': 'erlang',
        # Swift / Dart / ObjC
        '.swift': 'swift',
        '.dart': 'dart',
        '.m': 'objc',
        '.mm': 'objc',
        # C / C++
        '.c': 'c',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.hxx': 'cpp',
        # Shell
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',
        '.fish': 'shell',
        '.ps1': 'powershell',
        # Config / infra
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.conf': 'conf',
        '.env': 'env',
        '.tf': 'terraform',
        '.tfvars': 'terraform',
        '.nix': 'nix',
        # Data / query
        '.sql': 'sql',
        '.graphql': 'graphql',
        '.gql': 'graphql',
        '.proto': 'protobuf',
        # Templates
        '.jinja': 'jinja',
        '.jinja2': 'jinja',
        '.j2': 'jinja',
        '.tmpl': 'template',
        # Misc
        '.xml': 'xml',
        '.gradle': 'groovy',
        '.lua': 'lua',
        '.r': 'r',
        '.jl': 'julia',
        '.txt': 'text',
    }
    return mapping.get(file_path.suffix.lower(), file_path.suffix.lower().lstrip('.') or 'text')


def _workspace_fingerprint(workspace_path: Path) -> str:
    manifest = _build_blueprint_manifest(workspace_path)
    return _manifest_fingerprint(manifest.get('files') or [])


def _manifest_fingerprint(entries: list[dict]) -> str:
    digest = hashlib.sha1()
    digest.update(f'blueprint-cache-v{BLUEPRINT_CACHE_VERSION}'.encode('utf-8'))
    for entry in sorted(entries, key=lambda item: str(item.get('path') or '')):
        rel_path = str(entry.get('path') or '')
        if not rel_path or rel_path.startswith('.devhub/'):
            continue
        digest.update(rel_path.encode('utf-8', errors='ignore'))
        digest.update(str(entry.get('size') or 0).encode('utf-8'))
        digest.update(str(entry.get('modified') or 0).encode('utf-8'))
        digest.update(str(entry.get('tier') or 3).encode('utf-8'))
    return digest.hexdigest()


def _extract_imports(content: str, language: str) -> list[str]:
    imports: list[str] = []
    for line in (content or '').splitlines()[:150]:
        stripped = line.strip()
        if not stripped:
            continue
        if language == 'python' and (stripped.startswith('import ') or stripped.startswith('from ')):
            imports.append(stripped[:160])
        elif language in {'javascript', 'javascript-react', 'typescript', 'typescript-react', 'vue', 'svelte'} and (
            stripped.startswith('import ') or 'require(' in stripped
        ):
            imports.append(stripped[:160])
        elif language == 'go' and (stripped.startswith('import ') or (stripped.startswith('"') and '/' in stripped)):
            imports.append(stripped[:160])
        elif language == 'rust' and (stripped.startswith('use ') or stripped.startswith('extern crate ')):
            imports.append(stripped[:160])
        elif language in {'java', 'kotlin', 'scala', 'groovy'} and stripped.startswith('import '):
            imports.append(stripped[:160])
        elif language == 'csharp' and (stripped.startswith('using ') or stripped.startswith('namespace ')):
            imports.append(stripped[:160])
        elif language == 'ruby' and (stripped.startswith('require ') or stripped.startswith('require_relative ')):
            imports.append(stripped[:160])
        elif language == 'php' and (stripped.startswith('use ') or stripped.startswith('require') or stripped.startswith('namespace ')):
            imports.append(stripped[:160])
        elif language == 'elixir' and (stripped.startswith('alias ') or stripped.startswith('import ') or stripped.startswith('use ') or stripped.startswith('require ')):
            imports.append(stripped[:160])
        elif language == 'swift' and stripped.startswith('import '):
            imports.append(stripped[:160])
        elif language == 'dart' and stripped.startswith('import '):
            imports.append(stripped[:160])
    return imports[:15]


def _extract_routes(content: str, language: str) -> list[str]:
    routes = []
    if language == 'python':
        patterns = [
            r'path\(\s*[\'"]([^\'"]+)',
            r're_path\(\s*[\'"]([^\'"]+)',
            r'@(?:app|router|blueprint)\.(get|post|put|delete|patch)\(\s*[\'"]([^\'"]+)',
        ]
    elif language in {'javascript', 'javascript-react', 'typescript', 'typescript-react', 'vue', 'svelte'}:
        patterns = [
            r'(?:router|app|fastify|server|hono)\.(get|post|put|delete|patch)\(\s*[\'"`]([^\'"` ]+)',
            r'path:\s*[\'"`]([^\'"` ]+)',
            r'Route\s+path=[{]?[\'"]([^\'"]+)',
            r'\{[\'"]?path[\'"]?\s*:\s*[\'"]([^\'"]+)',
        ]
    elif language == 'go':
        patterns = [
            r'(?:r|router|mux|e|g)\.\w+\(\s*[\'"`]([^\'"` ]+)',
            r'http\.Handle\s*\(\s*[\'"`]([^\'"` ]+)',
            r'HandleFunc\s*\(\s*[\'"`]([^\'"` ]+)',
        ]
    elif language == 'ruby':
        patterns = [
            r'(?:get|post|put|patch|delete|resources?)\s+[\'"]([^\'"]+)',
            r'(?:get|post|put|patch|delete)\s+:?(\w+)',
        ]
    elif language == 'java':
        patterns = [
            r'@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*\(\s*[\'"]?([^\'")\s]+)',
        ]
    elif language in {'kotlin', 'scala'}:
        patterns = [
            r'@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)\s*\(\s*[\'"]?([^\'")\s]+)',
        ]
    elif language == 'csharp':
        patterns = [
            r'\[(?:HttpGet|HttpPost|HttpPut|HttpDelete|Route)\s*\(\s*[\'"]([^\'"]+)',
            r'MapGet\s*\(\s*[\'"]([^\'"]+)',
            r'MapPost\s*\(\s*[\'"]([^\'"]+)',
        ]
    elif language == 'elixir':
        patterns = [
            r'(?:get|post|put|patch|delete|resources|scope)\s+[\'"]([^\'"]+)',
        ]
    elif language == 'php':
        patterns = [
            r'Route::(?:get|post|put|patch|delete)\s*\(\s*[\'"]([^\'"]+)',
            r'\$(?:app|router)->(?:get|post|put|patch|delete)\s*\(\s*[\'"]([^\'"]+)',
        ]
    else:
        return []

    for line in (content or '').splitlines():
        for pattern in patterns:
            match = re.search(pattern, line)
            if not match:
                continue
            route = match.group(match.lastindex or 1)
            if route and len(route) > 1 and route not in routes:
                routes.append(route)
    return routes[:16]


def _extract_data_models(content: str, language: str) -> list[str]:
    models = []
    if language == 'python':
        patterns = [
            r'class\s+([A-Za-z0-9_]+)\s*\((?:models\.Model|Base|BaseModel|db\.Model|Schema)\)',
            r'@dataclass\s*\nclass\s+([A-Za-z0-9_]+)',
        ]
    elif language in {'javascript', 'javascript-react', 'typescript', 'typescript-react', 'vue', 'svelte'}:
        patterns = [
            r'interface\s+([A-Za-z0-9_]+)',
            r'type\s+([A-Za-z0-9_]+)\s*[={]',
            r'const\s+([A-Za-z0-9_]+Schema)\s*=',
            r'class\s+([A-Za-z0-9_]+)\s+(?:extends|implements)',
        ]
    elif language == 'go':
        patterns = [r'type\s+([A-Za-z0-9_]+)\s+struct\s*\{']
    elif language == 'rust':
        patterns = [
            r'^(?:pub\s+)?struct\s+([A-Za-z0-9_]+)',
            r'^(?:pub\s+)?enum\s+([A-Za-z0-9_]+)',
        ]
    elif language in {'java', 'kotlin'}:
        patterns = [
            r'@Entity',  # marker — capture class name on next line via multiline approach below
            r'(?:class|data class|record)\s+([A-Za-z0-9_]+)',
        ]
    elif language == 'csharp':
        patterns = [
            r'(?:public\s+)?(?:class|record|struct)\s+([A-Za-z0-9_]+)',
        ]
    elif language == 'ruby':
        patterns = [
            r'class\s+([A-Za-z0-9:]+)\s*<\s*(?:ApplicationRecord|ActiveRecord::Base|ActiveModel)',
        ]
    elif language == 'elixir':
        patterns = [r'schema\s+[\'"]([^\'"]+)']
    elif language == 'php':
        patterns = [r'class\s+([A-Za-z0-9_]+)\s+extends\s+(?:Model|Eloquent)']
    elif language in {'protobuf', 'graphql'}:
        patterns = [r'(?:message|type)\s+([A-Za-z0-9_]+)']
    elif language == 'sql':
        patterns = [r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?([A-Za-z0-9_]+)']
    elif language in {'yaml', 'json'}:
        # Prisma-style or OpenAPI schemas
        patterns = [r'\b([A-Za-z0-9_]+):\s*\n\s+type:']
    else:
        return []

    for line in (content or '').splitlines()[:300]:
        for pattern in patterns:
            match = re.search(pattern, line)
            if match and match.lastindex:
                symbol = match.group(1)
                if symbol and symbol not in models and len(symbol) > 1:
                    models.append(symbol)
    return models[:12]


def _safe_source_text(source: str, node: ast.AST | None) -> str:
    if node is None:
        return ''
    try:
        text = ast.get_source_segment(source, node)
    except Exception:
        text = ''
    if text:
        return " ".join(text.split())
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _safe_source_text(source, node.value)
        return f"{base}.{node.attr}".strip(".")
    if isinstance(node, ast.Tuple):
        return "(" + ", ".join(_safe_source_text(source, item) for item in node.elts) + ")"
    if isinstance(node, ast.List):
        return "[" + ", ".join(_safe_source_text(source, item) for item in node.elts) + "]"
    if isinstance(node, ast.Set):
        return "{" + ", ".join(_safe_source_text(source, item) for item in node.elts) + "}"
    return ''


def _call_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ''


def _literal_str(node: ast.AST | None) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        return "".join(parts)
    return ''


def _meta_value_to_strings(source: str, node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        items = []
        for child in node.elts:
            rendered = _safe_source_text(source, child)
            if rendered:
                items.append(rendered)
        return items
    rendered = _safe_source_text(source, node)
    return [rendered] if rendered else []


def _field_call_signature(source: str, call: ast.Call) -> str:
    field_type = _call_name(call.func) or 'Field'
    arguments = []
    for arg in call.args:
        text = _safe_source_text(source, arg)
        if text:
            arguments.append(text)
    for keyword in call.keywords:
        if keyword.arg:
            text = _safe_source_text(source, keyword.value)
            arguments.append(f"{keyword.arg}={text}")
    return f"{field_type}({', '.join(arguments)})" if arguments else field_type


def _constraint_parts(field_name: str, field_type: str, call: ast.Call, source: str, target_model: str = '') -> list[str]:
    keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
    parts: list[str] = []
    primary_key = keywords.get('primary_key')
    unique = keywords.get('unique')
    nullable = keywords.get('null')
    blank = keywords.get('blank')

    if isinstance(primary_key, ast.Constant) and bool(primary_key.value):
        parts.append('PK')
    if target_model and field_type == 'ForeignKey':
        parts.append(f'FK({target_model})')
    elif target_model and field_type == 'OneToOneField':
        parts.append(f'ONE_TO_ONE({target_model})')
    elif target_model and field_type == 'ManyToManyField':
        parts.append(f'M2M({target_model})')
    if isinstance(unique, ast.Constant) and bool(unique.value):
        parts.append('UNIQUE')
    if not (isinstance(nullable, ast.Constant) and bool(nullable.value)) and field_type != 'ManyToManyField':
        parts.append('NOT NULL')
    if isinstance(blank, ast.Constant) and bool(blank.value):
        parts.append('blank=True')

    for key in ('default', 'related_name', 'on_delete', 'editable', 'auto_now_add', 'auto_now', 'max_length'):
        if key in keywords:
            parts.append(f"{key}={_safe_source_text(source, keywords[key])}")

    choices = keywords.get('choices')
    if isinstance(choices, (ast.List, ast.Tuple, ast.Set)):
        parts.append(f"choices={len(choices.elts)} values")

    if field_name == 'id' and 'PK' not in parts:
        parts.insert(0, 'PK')
    return parts


def _relationship_cardinality(field_type: str) -> str:
    return {
        'ForeignKey': 'many-to-one',
        'OneToOneField': 'one-to-one',
        'ManyToManyField': 'many-to-many',
    }.get(field_type, '')


def _target_model_from_call(source: str, call: ast.Call) -> str:
    if call.args:
        target = _safe_source_text(source, call.args[0])
    else:
        keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
        target = _safe_source_text(source, keywords.get('to'))
    return target.replace("'", "").replace('"', '').split('.')[-1]


def _field_description(field_name: str, field_type: str, target_model: str = '') -> str:
    lowered = field_name.lower()
    if target_model:
        return f"References the related `{target_model}` record through the ORM association."
    if lowered == 'id':
        return "Primary identifier for this record."
    if lowered.endswith('_at') or lowered in {'at', 'registered_at', 'started_at', 'completed_at'}:
        return "Timestamp used to record when this event or record state was written."
    if lowered in {'name', 'title'}:
        return "Human-readable label shown in the product and internal workflows."
    if lowered == 'description':
        return "Long-form text describing the record's purpose or requirements."
    if lowered == 'status':
        return "Lifecycle or processing state for the record."
    if lowered in {'metadata', 'context', 'blueprint', 'ai_config', 'spec'}:
        return "Structured JSON payload persisted alongside the record for richer application state."
    if lowered in {'content', 'summary', 'diff_content'}:
        return "Main persisted text content for this record."
    if lowered in {'file_path', 'local_path'}:
        return "Filesystem path or repository-relative path associated with the record."
    if lowered in {'github_url', 'preview_url'}:
        return "External URL stored with the record."
    if lowered in {'logs', 'tests', 'suggestions', 'blockers', 'keywords', 'related_files', 'team_members', 'tech_stack'}:
        return "Collection field storing repeated structured values for this record."
    if field_type.endswith('JSONField'):
        return "JSON-backed field used to store flexible structured data."
    if field_type.endswith('TextField'):
        return "Free-form text captured for the record."
    if field_type.endswith('CharField'):
        return "Short string field used by the application domain."
    if field_type.endswith('BooleanField'):
        return "Boolean flag that tracks a persisted yes/no state."
    if field_type.endswith('IntegerField') or field_type.endswith('PositiveIntegerField'):
        return "Numeric field used by the application when counting or scoring data."
    return "Persisted application field defined on the model."


def _mermaid_scalar_type(field_type: str) -> str:
    lowered = field_type.lower()
    if 'uuid' in lowered:
        return 'uuid'
    if 'json' in lowered:
        return 'json'
    if 'boolean' in lowered:
        return 'boolean'
    if 'datetime' in lowered:
        return 'datetime'
    if 'integer' in lowered or 'positiveinteger' in lowered or 'bigauto' in lowered:
        return 'int'
    if 'text' in lowered:
        return 'text'
    if 'url' in lowered:
        return 'string'
    return 'string'


def _model_description(model_name: str, source_path: str, field_names: list[str], relationships: list[dict], inbound: list[str]) -> str:
    timestamp_fields = [name for name in field_names if name.endswith('_at') or name in {'at', 'registered_at'}]
    json_fields = [name for name in field_names if any(token in name for token in ('metadata', 'context', 'blueprint', 'config', 'spec', 'logs', 'tests', 'suggestions', 'blockers', 'keywords', 'related_files', 'tech_stack', 'team_members'))]
    parts = [
        f"Django model defined in `{source_path}` that persists `{model_name}` records for the application domain.",
        f"It stores {len(field_names)} mapped field{'s' if len(field_names) != 1 else ''}",
    ]
    if relationships:
        targets = ", ".join(f"`{item['target_model']}`" for item in relationships[:5] if item.get('target_model'))
        if targets:
            parts.append(f" and links to {targets}")
    parts[-1] += "."
    if timestamp_fields:
        parts.append(f"The model tracks lifecycle timing through {', '.join(f'`{name}`' for name in timestamp_fields[:3])}.")
    if json_fields:
        parts.append(f"It also keeps flexible structured state in {', '.join(f'`{name}`' for name in json_fields[:3])}.")
    if inbound:
        parts.append(f"Other persisted records point back to it from {', '.join(inbound[:4])}.")
    return " ".join(parts)


def _relationship_summary(model_name: str, relationships: list[dict], inbound: list[str]) -> str:
    statements: list[str] = []
    for relation in relationships:
        target = relation.get('target_model')
        field_name = relation.get('field_name')
        cardinality = relation.get('cardinality')
        on_delete = relation.get('on_delete')
        related_name = relation.get('related_name')
        if not target or not field_name:
            continue
        line = f"`{field_name}` is a {cardinality} relationship from `{model_name}` to `{target}`"
        if on_delete:
            line += f" with `on_delete={on_delete}`"
        if related_name:
            line += f" and `related_name={related_name}`"
        line += "."
        statements.append(line)
    statements.extend(inbound)
    return " ".join(statements) if statements else "No persisted relationships were clearly detected from the scanned model classes."


def _extract_django_model_schema(workspace_path: Path, manifest_entries: list[dict] | None = None) -> dict:
    manifest_entries = manifest_entries or []
    python_paths = [
        str(item.get('path') or '')
        for item in manifest_entries
        if str(item.get('path') or '').endswith('.py') and not str(item.get('path') or '').startswith('.devhub/')
    ]
    if not python_paths:
        python_paths = [
            str(path.relative_to(workspace_path)).replace('\\', '/')
            for path in _iter_blueprint_files(workspace_path)
            if path.suffix.lower() == '.py'
        ]

    parsed_models: list[dict] = []
    source_files: set[str] = set()

    for rel_path in python_paths:
        file_path = workspace_path / rel_path
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        if 'models.Model' not in source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = {_safe_source_text(source, base) for base in node.bases}
            if not any(base.endswith('models.Model') or base == 'Model' for base in base_names):
                continue

            model_fields: list[dict] = []
            model_relationships: list[dict] = []
            model_indexes: list[str] = []

            for child in node.body:
                if isinstance(child, ast.Assign) and len(child.targets) == 1 and isinstance(child.targets[0], ast.Name) and isinstance(child.value, ast.Call):
                    field_name = child.targets[0].id
                    field_type = _call_name(child.value.func) or 'Field'
                    target_model = ''
                    if field_type in {'ForeignKey', 'OneToOneField', 'ManyToManyField'}:
                        target_model = _target_model_from_call(source, child.value)
                        model_relationships.append(
                            {
                                'field_name': field_name,
                                'field_type': field_type,
                                'target_model': target_model,
                                'cardinality': _relationship_cardinality(field_type),
                                'on_delete': _safe_source_text(source, next((keyword.value for keyword in child.value.keywords if keyword.arg == 'on_delete'), None)),
                                'related_name': _safe_source_text(source, next((keyword.value for keyword in child.value.keywords if keyword.arg == 'related_name'), None)).replace("'", "").replace('"', ''),
                            }
                        )
                    model_fields.append(
                        {
                            'name': field_name,
                            'type': _field_call_signature(source, child.value),
                            'constraints': ", ".join(_constraint_parts(field_name, field_type, child.value, source, target_model)),
                            'description': _field_description(field_name, field_type, target_model),
                            'field_type': field_type,
                        }
                    )
                elif isinstance(child, ast.ClassDef) and child.name == 'Meta':
                    for meta_child in child.body:
                        if not isinstance(meta_child, ast.Assign) or len(meta_child.targets) != 1 or not isinstance(meta_child.targets[0], ast.Name):
                            continue
                        meta_name = meta_child.targets[0].id
                        if meta_name == 'unique_together':
                            value = _safe_source_text(source, meta_child.value)
                            if value:
                                model_indexes.append(f"unique_together={value}")
                        elif meta_name == 'indexes':
                            for value in _meta_value_to_strings(source, meta_child.value):
                                model_indexes.append(value)
                        elif meta_name == 'constraints':
                            for value in _meta_value_to_strings(source, meta_child.value):
                                model_indexes.append(value)

            if not model_fields:
                continue

            parsed_models.append(
                {
                    'name': node.name,
                    'source_path': rel_path,
                    'fields': model_fields,
                    'relationships': model_relationships,
                    'indexes': model_indexes,
                }
            )
            source_files.add(rel_path)

    if not parsed_models:
        return {
            'database_schema': [],
            'database_mermaid_erd': '',
            'database_source_files': [],
            'database_model_names': [],
        }

    model_names = {model['name'] for model in parsed_models}
    inbound_relationships: dict[str, list[str]] = defaultdict(list)
    mermaid_relationships: list[str] = []

    for model in parsed_models:
        for relation in model.get('relationships') or []:
            target = relation.get('target_model')
            if not target or target not in model_names:
                continue
            source_name = model['name']
            field_name = relation.get('field_name') or 'relates_to'
            if relation.get('field_type') == 'ForeignKey':
                mermaid_relationships.append(f"  {target} ||--o{{ {source_name} : {field_name}")
                inbound_relationships[target].append(f"`{source_name}.{field_name}` gives `{target}` a one-to-many reverse relation.")
            elif relation.get('field_type') == 'OneToOneField':
                mermaid_relationships.append(f"  {target} ||--|| {source_name} : {field_name}")
                inbound_relationships[target].append(f"`{source_name}.{field_name}` creates a one-to-one reverse relation back to `{target}`.")
            elif relation.get('field_type') == 'ManyToManyField':
                mermaid_relationships.append(f"  {source_name} }}o--o{{ {target} : {field_name}")
                inbound_relationships[target].append(f"`{source_name}.{field_name}` participates in a many-to-many relation with `{target}`.")

    schema_rows: list[dict] = []
    mermaid_lines = ['erDiagram']
    for model in sorted(parsed_models, key=lambda item: (item['source_path'], item['name'])):
        mermaid_lines.append(f"  {model['name']} {{")
        for field in model['fields']:
            mermaid_lines.append(f"    {_mermaid_scalar_type(field['type'])} {field['name']}")
        mermaid_lines.append("  }")
        schema_rows.append(
            {
                'table': model['name'],
                'description': _model_description(
                    model['name'],
                    model['source_path'],
                    [field['name'] for field in model['fields']],
                    model['relationships'],
                    inbound_relationships.get(model['name'], []),
                ),
                'key_fields': [
                    {
                        'name': field['name'],
                        'type': field['type'],
                        'constraints': field['constraints'],
                        'description': field['description'],
                    }
                    for field in model['fields']
                ],
                'relationships': _relationship_summary(model['name'], model['relationships'], inbound_relationships.get(model['name'], [])),
                'indexes': model['indexes'],
            }
        )

    seen_relationships: set[str] = set()
    for relation_line in mermaid_relationships:
        if relation_line in seen_relationships:
            continue
        seen_relationships.add(relation_line)
        mermaid_lines.append(relation_line)

    return {
        'database_schema': schema_rows,
        'database_mermaid_erd': "\n".join(mermaid_lines),
        'database_source_files': sorted(source_files),
        'database_model_names': [item['table'] for item in schema_rows],
    }


def _empty_schema_payload() -> dict:
    return {
        'database_schema': [],
        'database_mermaid_erd': '',
        'database_source_files': [],
        'database_model_names': [],
    }


def _extract_universal_schema(
    workspace_path: Path,
    manifest_entries: list[dict] | None = None,
    graph_data: dict | None = None,
) -> dict:
    django_schema = _extract_django_model_schema(workspace_path, manifest_entries)
    if django_schema.get('database_schema'):
        return django_schema

    sqlalchemy_schema = _extract_sqlalchemy_model_schema(workspace_path, manifest_entries)
    if sqlalchemy_schema.get('database_schema'):
        return sqlalchemy_schema

    prisma_schema = _extract_prisma_model_schema(workspace_path)
    if prisma_schema.get('database_schema'):
        return prisma_schema

    raw_sql_schema = _extract_raw_sql_schema(workspace_path)
    if raw_sql_schema.get('database_schema'):
        return raw_sql_schema

    graph_schema = _extract_graph_schema_fallback(workspace_path, graph_data or {})
    if graph_schema.get('database_schema'):
        return graph_schema

    return _empty_schema_payload()


def _candidate_python_paths(workspace_path: Path, manifest_entries: list[dict] | None = None) -> list[str]:
    manifest_entries = manifest_entries or []
    python_paths = [
        str(item.get('path') or '')
        for item in manifest_entries
        if str(item.get('path') or '').endswith('.py') and not str(item.get('path') or '').startswith('.devhub/')
    ]
    if python_paths:
        return python_paths
    return [
        str(path.relative_to(workspace_path)).replace('\\', '/')
        for path in _iter_blueprint_files(workspace_path)
        if path.suffix.lower() == '.py'
    ]


def _extract_sqlalchemy_model_schema(workspace_path: Path, manifest_entries: list[dict] | None = None) -> dict:
    parsed_models: list[dict] = []
    source_files: set[str] = set()

    for rel_path in _candidate_python_paths(workspace_path, manifest_entries):
        file_path = workspace_path / rel_path
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source)
        except Exception:
            continue

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = {_safe_source_text(source, base) for base in node.bases}
            looks_like_sqlalchemy = any(
                base.endswith('Base') or base.endswith('db.Model') or 'DeclarativeBase' in base
                for base in base_names
            )
            if not looks_like_sqlalchemy:
                continue

            table_name = node.name
            fields: list[dict] = []
            relationships: list[dict] = []
            indexes: list[str] = []

            for child in node.body:
                if isinstance(child, ast.Assign) and len(child.targets) == 1 and isinstance(child.targets[0], ast.Name):
                    target_name = child.targets[0].id
                    if target_name == '__tablename__':
                        table_name = _literal_str(child.value) or table_name
                        continue
                    if isinstance(child.value, ast.Call):
                        call_name = _call_name(child.value.func)
                        if call_name in {'Column', 'mapped_column'}:
                            field_type = _safe_source_text(source, child.value.args[0]) if child.value.args else 'Column'
                            fields.append(
                                {
                                    'name': target_name,
                                    'type': str(field_type or 'Column'),
                                    'constraints': _safe_source_text(source, child.value),
                                    'description': f"SQLAlchemy column on `{table_name}`.",
                                }
                            )
                        elif call_name == 'relationship':
                            target_model = _literal_str(child.value.args[0]) if child.value.args else ''
                            relationships.append(
                                {
                                    'field_name': target_name,
                                    'target_model': target_model,
                                    'cardinality': 'many-to-one',
                                }
                            )
                elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name) and isinstance(child.value, ast.Call):
                    call_name = _call_name(child.value.func)
                    if call_name in {'Column', 'mapped_column'}:
                        fields.append(
                            {
                                'name': child.target.id,
                                'type': _safe_source_text(source, child.annotation) or 'Column',
                                'constraints': _safe_source_text(source, child.value),
                                'description': f"SQLAlchemy column on `{table_name}`.",
                            }
                        )

            if not fields and not relationships:
                continue

            parsed_models.append(
                {
                    'name': table_name,
                    'fields': fields,
                    'relationships': relationships,
                    'indexes': indexes,
                    'source_path': rel_path,
                }
            )
            source_files.add(rel_path)

    return _schema_payload_from_models(parsed_models, source_files, description_prefix='SQLAlchemy model')


def _extract_prisma_model_schema(workspace_path: Path) -> dict:
    parsed_models: list[dict] = []
    source_files: set[str] = set()
    for file_path in workspace_path.rglob('*.prisma'):
        if '.devhub' in file_path.parts or 'node_modules' in file_path.parts:
            continue
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for match in re.finditer(r"model\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{(.*?)\}", source, re.DOTALL):
            model_name = match.group(1)
            body = match.group(2)
            fields: list[dict] = []
            relationships: list[dict] = []
            indexes: list[str] = []
            for raw_line in body.splitlines():
                line = raw_line.strip()
                if not line or line.startswith('//'):
                    continue
                if line.startswith('@@'):
                    indexes.append(line)
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                field_name = parts[0]
                field_type = parts[1]
                constraints = " ".join(parts[2:]).strip()
                if '@relation' in constraints:
                    relationships.append(
                        {
                            'field_name': field_name,
                            'target_model': field_type.rstrip('?[]'),
                            'cardinality': 'relation',
                        }
                    )
                fields.append(
                    {
                        'name': field_name,
                        'type': field_type,
                        'constraints': constraints,
                        'description': f"Prisma field on `{model_name}`.",
                    }
                )
            if not fields:
                continue
            rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
            parsed_models.append(
                {
                    'name': model_name,
                    'fields': fields,
                    'relationships': relationships,
                    'indexes': indexes,
                    'source_path': rel_path,
                }
            )
            source_files.add(rel_path)
    return _schema_payload_from_models(parsed_models, source_files, description_prefix='Prisma model')


def _extract_raw_sql_schema(workspace_path: Path) -> dict:
    parsed_models: list[dict] = []
    source_files: set[str] = set()
    for file_path in workspace_path.rglob('*.sql'):
        if '.devhub' in file_path.parts or 'node_modules' in file_path.parts:
            continue
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for match in re.finditer(r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+([A-Za-z0-9_`\"\.]+)\s*\((.*?)\);", source, re.IGNORECASE | re.DOTALL):
            table_name = str(match.group(1) or '').strip('`"')
            body = match.group(2)
            fields: list[dict] = []
            relationships: list[dict] = []
            indexes: list[str] = []
            for raw_line in re.split(r",\s*(?![^()]*\))", body):
                line = raw_line.strip().strip(',')
                if not line:
                    continue
                upper_line = line.upper()
                if upper_line.startswith(('PRIMARY KEY', 'UNIQUE', 'CONSTRAINT', 'INDEX')):
                    indexes.append(line)
                    continue
                column_match = re.match(r"([A-Za-z0-9_`\"]+)\s+([A-Za-z0-9_()]+)(.*)", line)
                if not column_match:
                    continue
                field_name = column_match.group(1).strip('`"')
                field_type = column_match.group(2)
                constraints = column_match.group(3).strip()
                reference_match = re.search(r"REFERENCES\s+([A-Za-z0-9_`\"\.]+)", line, re.IGNORECASE)
                if reference_match:
                    relationships.append(
                        {
                            'field_name': field_name,
                            'target_model': str(reference_match.group(1) or '').strip('`"'),
                            'cardinality': 'foreign-key',
                        }
                    )
                fields.append(
                    {
                        'name': field_name,
                        'type': field_type,
                        'constraints': constraints,
                        'description': f"SQL column on `{table_name}`.",
                    }
                )
            if not fields:
                continue
            rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
            parsed_models.append(
                {
                    'name': table_name,
                    'fields': fields,
                    'relationships': relationships,
                    'indexes': indexes,
                    'source_path': rel_path,
                }
            )
            source_files.add(rel_path)
    return _schema_payload_from_models(parsed_models, source_files, description_prefix='SQL table')


def _extract_graph_schema_fallback(workspace_path: Path, graph_data: dict) -> dict:
    graph_components = graph_data.get('key_components') if isinstance(graph_data, dict) else []
    parsed_models: list[dict] = []
    source_files: set[str] = set()

    for item in graph_components or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        file_path = str(item.get('file_path') or '').strip()
        exports = str(item.get('exports') or '').strip().lower()
        if not name or 'class' not in exports and 'type' not in exports:
            continue
        parsed_models.append(
            {
                'name': name,
                'fields': [],
                'relationships': [],
                'indexes': [],
                'source_path': file_path,
            }
        )
        if file_path:
            source_files.add(file_path)

    if not parsed_models:
        try:
            from code_review_graph.tools.query import semantic_search_nodes
        except ImportError:
            return _empty_schema_payload()
        try:
            class_results = semantic_search_nodes(query='model schema entity table', kind='Class', limit=20, repo_root=str(workspace_path))
            type_results = semantic_search_nodes(query='schema type entity', kind='Type', limit=20, repo_root=str(workspace_path))
        except Exception:
            return _empty_schema_payload()
        for item in list(class_results.get('results') or []) + list(type_results.get('results') or []):
            name = str(item.get('name') or '').strip()
            file_path = str(item.get('file_path') or '').strip()
            if not name:
                continue
            parsed_models.append(
                {
                    'name': name,
                    'fields': [],
                    'relationships': [],
                    'indexes': [],
                    'source_path': file_path,
                }
            )
            if file_path:
                source_files.add(file_path)

    if not parsed_models:
        return _empty_schema_payload()
    return _schema_payload_from_models(parsed_models, source_files, description_prefix='Graph-derived type')


def _schema_payload_from_models(parsed_models: list[dict], source_files: set[str], description_prefix: str) -> dict:
    if not parsed_models:
        return _empty_schema_payload()

    schema_rows: list[dict] = []
    mermaid_lines = ['erDiagram']
    for model in parsed_models:
        model_name = str(model.get('name') or '').strip()
        if not model_name:
            continue
        fields = list(model.get('fields') or [])
        mermaid_lines.append(f"  {model_name} {{")
        for field in fields:
            mermaid_lines.append(f"    {_mermaid_scalar_type(str(field.get('type') or 'string'))} {field.get('name')}")
        mermaid_lines.append("  }")
        relationships = list(model.get('relationships') or [])
        relationship_text = " ".join(
            f"`{item.get('field_name')}` -> `{item.get('target_model')}` ({item.get('cardinality')})"
            for item in relationships
            if item.get('field_name') and item.get('target_model')
        ) or "No explicit relationships detected."
        schema_rows.append(
            {
                'table': model_name,
                'description': f"{description_prefix} defined in `{model.get('source_path')}`.",
                'key_fields': fields,
                'relationships': relationship_text,
                'indexes': list(model.get('indexes') or []),
            }
        )

    for model in parsed_models:
        source_name = str(model.get('name') or '').strip()
        for relationship in model.get('relationships') or []:
            target_name = str(relationship.get('target_model') or '').strip()
            field_name = str(relationship.get('field_name') or 'relation').strip()
            if source_name and target_name:
                mermaid_lines.append(f"  {source_name} }}o--|| {target_name} : {field_name}")

    return {
        'database_schema': schema_rows,
        'database_mermaid_erd': "\n".join(mermaid_lines),
        'database_source_files': sorted(source_files),
        'database_model_names': [item['table'] for item in schema_rows],
    }


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
    if file_name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
        return "container-config"
    if lowered_path.endswith(".env.example"):
        return "env-template"
    if "/prompts/" in lowered_path and language == "markdown":
        return "prompt-doc"
    if file_name in {"makefile", "justfile", "taskfile.yml", "taskfile.yaml"}:
        return "script"
    if "/scripts/" in lowered_path or language in {"shell", "powershell"}:
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


def _is_likely_minified(rel_path: str, content: str) -> bool:
    lowered = str(rel_path or '').lower()
    if any(token in lowered for token in ('.min.js', '.min.css', '.bundle.js', '.bundle.css')):
        return True
    lines = (content or '').splitlines()
    if not lines:
        return False
    sample = lines[:8]
    if any(len(line) > 1200 for line in sample):
        return True
    long_lines = sum(1 for line in sample if len(line) > 400)
    return long_lines >= 3


def _should_index_blueprint_file(file_path: Path, workspace_path: Path, config_names: set[str]) -> bool:
    rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
    file_name = file_path.name.lower()
    if file_name in BLUEPRINT_SKIP_FILE_NAMES:
        return False
    if any(part.lower() in BLUEPRINT_SKIP_DIRS for part in file_path.relative_to(workspace_path).parts[:-1]):
        return False
    if file_path.suffix.lower() == '.map':
        return False
    if not (file_path.suffix.lower() in INDEXABLE_EXTENSIONS or file_name in config_names):
        return False
    try:
        size = file_path.stat().st_size
    except OSError:
        return False
    if size <= 0:
        return False
    if file_path.suffix.lower() == '.json' and file_name not in config_names and size > BLUEPRINT_MAX_JSON_BYTES:
        return False
    if size > BLUEPRINT_MAX_FILE_BYTES and file_name not in config_names:
        return False
    try:
        content_probe = file_path.read_text(encoding='utf-8', errors='ignore')[:4000]
    except Exception:
        return False
    if not content_probe.strip():
        return False
    if _is_likely_minified(rel_path, content_probe):
        return False
    return True


def _file_summary(file_path: Path, workspace_path: Path, *, include_excerpt: bool = False, excerpt_chars: int = BLUEPRINT_EXCERPT_CHARS) -> dict | None:
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
    language = _detect_language(file_path)
    try:
        size = int(file_path.stat().st_size)
    except OSError:
        size = len(content.encode('utf-8', errors='ignore'))
    tier, tier_reason = _classify_manifest_tier(rel_path, size, language, {name.lower() for name in BLUEPRINT_CONFIG_FILES})
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
        f"Representative commands: {', '.join(commands[:4])}." if commands else "",
    ]
    summary = " ".join(part for part in summary_parts if part).strip()

    return {
        'path': rel_path,
        'size': size,
        'tier': tier,
        'tier_reason': tier_reason,
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
        'excerpt': content[:excerpt_chars] if include_excerpt and excerpt_chars > 0 else '',
        'brief': f"{rel_path} ({language}{', ' + ', '.join(role_hints) if role_hints else ''})",
        'summary': summary[:600],
    }


def _score_blueprint_file(summary: dict) -> int:
    score = 0
    path = str(summary.get('path') or '').lower()
    file_name = Path(path).name
    config_names_lower = {name.lower() for name in BLUEPRINT_CONFIG_FILES}

    # Config / manifest files are always high value
    if file_name in config_names_lower:
        score += 12

    # Files with extracted routes/endpoints are high signal
    if summary.get('routes'):
        score += 10

    # Files with data models/types are high signal
    if summary.get('data_models'):
        score += 9

    # Role-hint boosts (language-agnostic, derived by _file_summary)
    if any(hint in (summary.get('role_hints') or []) for hint in ('api', 'data-model', 'routing')):
        score += 6
    if 'ui' in (summary.get('role_hints') or []):
        score += 4

    # Defined symbol (class / function / struct / module) → architectural file
    if summary.get('symbol'):
        score += 3

    # Universal entry-point name patterns (any language)
    ENTRY_POINT_TOKENS = (
        'main', 'app', 'index', 'server', 'application',
        'startup', 'bootstrap', 'init', 'run', 'entrypoint',
    )
    if any(token == file_name.split('.')[0] for token in ENTRY_POINT_TOKENS):
        score += 5

    # Universal routing/URL/config path tokens
    ROUTING_TOKENS = (
        'router', 'routes', 'routing', 'urls', 'endpoints',
        'views', 'controllers', 'handlers', 'actions',
    )
    if any(token in path for token in ROUTING_TOKENS):
        score += 4

    # Universal model/schema path tokens
    MODEL_TOKENS = (
        'models', 'model', 'schema', 'schemas', 'entities',
        'domain', 'types', 'structs', 'proto',
    )
    if any(token in path for token in MODEL_TOKENS):
        score += 4

    # Service/business logic orchestration files (language-agnostic)
    SERVICE_TOKENS = (
        'service', 'services', 'usecase', 'usecases', 'business',
        'agent', 'agents', 'coordinator', 'worker', 'executor',
        'pipeline', 'workflow', 'orchestrat',
    )
    if any(token in path for token in SERVICE_TOKENS):
        score += 6

    # UI components / pages / screens
    UI_TOKENS = ('component', 'components', 'pages', 'page', 'screen', 'screens', 'views', 'templates')
    if any(token in path for token in UI_TOKENS):
        score += 3

    # Infrastructure / integration files
    INFRA_TOKENS = (
        'integrations', 'integration', 'providers', 'provider',
        'clients', 'client', 'adapters', 'adapter',
        'middleware', 'interceptors', 'filters',
        'auth', 'security', 'oauth',
        'database', 'db', 'migrations', 'repositories', 'repository',
    )
    if any(token in path for token in INFRA_TOKENS):
        score += 5

    # Config / settings / environment files
    CONFIG_TOKENS = ('config', 'settings', 'configuration', 'environment', 'env')
    if any(token in path for token in CONFIG_TOKENS):
        score += 4

    # Files with many imports → likely an orchestration/wiring hub
    num_imports = len(summary.get('imports') or [])
    if num_imports >= 8:
        score += 5
    elif num_imports >= 5:
        score += 2

    return score


def _devhub_meta_dir(workspace_path: Path) -> Path:
    path = workspace_path / '.devhub'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / BLUEPRINT_MANIFEST_FILE


def _dependency_graph_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / BLUEPRINT_DEPENDENCY_GRAPH_FILE


def _blueprint_cache_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / BLUEPRINT_CACHE_FILE


def _repo_map_path(workspace_path: Path) -> Path:
    return _devhub_meta_dir(workspace_path) / REPO_MAP_FILE


def _classify_manifest_tier(rel_path: str, size: int, language: str, config_names: set[str]) -> tuple[int, str]:
    lowered_path = str(rel_path or '').lower()
    file_name = Path(lowered_path).name
    parts = [part.lower() for part in Path(lowered_path).parts]

    if file_name in BLUEPRINT_SKIP_FILE_NAMES:
        return 3, 'lockfile'
    if any(token in lowered_path for token in ('.min.js', '.min.css', '.bundle.js', '.bundle.css')):
        return 3, 'minified-asset'
    if any(part in BLUEPRINT_SKIP_DIRS for part in parts[:-1]):
        return 3, 'generated-dir'
    if lowered_path.endswith('.map'):
        return 3, 'sourcemap'
    # Skip generated migration files for any framework (Django, Alembic, Flyway, Liquibase, Active Record, Ecto, EF)
    _MIGRATION_DIR_MARKERS = ('/migrations/', '/db/migrate/', '/db/schema/', '/flyway/', '/liquibase/', '/changesets/')
    _MIGRATION_FILE_PATTERNS = (
        re.compile(r'^\d{4,}_.+\.(py|rb|sql|xml|yaml|yml)$'),  # Django/Alembic/Flyway/Liquibase
        re.compile(r'^v\d+__.+\.sql$'),                          # Flyway versioned
        re.compile(r'^\d{14}_.+\.rb$'),                          # Active Record
        re.compile(r'^\d{8,}_\d{6}_.+\.exs?$'),                  # Ecto
    )
    is_in_migration_dir = any(marker in lowered_path for marker in _MIGRATION_DIR_MARKERS)
    is_migration_file = any(pat.match(file_name) for pat in _MIGRATION_FILE_PATTERNS)
    if (is_in_migration_dir or is_migration_file) and file_name not in ('__init__.py', 'schema.rb', 'structure.sql'):
        return 3, 'migration'
    if file_name in BLUEPRINT_TIER_1_NAMES or file_name in config_names:
        return 1, 'critical-config'
    if any(token in file_name for token in BLUEPRINT_TIER_1_TOKENS):
        return 1, 'entry-routing'
    if size > BLUEPRINT_MAX_FILE_BYTES:
        return 3, 'oversized'
    if language == 'json' and size > BLUEPRINT_MAX_JSON_BYTES and file_name not in config_names:
        return 3, 'large-json'
    if not (Path(rel_path).suffix.lower() in INDEXABLE_EXTENSIONS or file_name in config_names):
        return 3, 'non-indexable'
    if size > BLUEPRINT_SUMMARY_SIZE_THRESHOLD:
        return 2, 'large-source'
    return 2, 'source-summary'


def _build_blueprint_manifest(workspace_path: Path) -> dict:
    manifest_files: list[dict] = []
    is_ignored = _build_gitignore_matcher(workspace_path)
    config_names = {name.lower() for name in BLUEPRINT_CONFIG_FILES}
    project_root_markers = {'.git', 'package.json', 'Cargo.toml', 'go.mod', 'pom.xml', 'setup.py', 'pyproject.toml'}
    nested_project_roots: set[str] = set()

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
        rel_root = str(Path(root).relative_to(workspace_path)).replace('\\', '/')
        depth = 0 if rel_root == '.' else rel_root.count('/') + 1

        if is_ignored(rel_root, is_dir=True):
            dirs.clear()
            continue

        if any(rel_root == npr or rel_root.startswith(npr + '/') for npr in nested_project_roots):
            dirs.clear()
            continue

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
            if is_ignored(rel_path):
                continue
            if filename.lower() in BLUEPRINT_JUNK_PATTERNS:
                continue
            if any(filename.startswith(prefix) for prefix in BLUEPRINT_JUNK_PREFIXES):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            language = _detect_language(path)
            tier, tier_reason = _classify_manifest_tier(rel_path, stat.st_size, language, config_names)
            manifest_files.append(
                {
                    'path': rel_path,
                    'size': int(stat.st_size),
                    'extension': path.suffix.lower(),
                    'language': language,
                    'modified': int(getattr(stat, 'st_mtime_ns', int(stat.st_mtime * 1_000_000_000))),
                    'depth': depth if rel_root == '.' else rel_path.count('/') + 1,
                    'tier': tier,
                    'tier_reason': tier_reason,
                }
            )

    manifest = {
        'cache_version': BLUEPRINT_CACHE_VERSION,
        'file_count': len(manifest_files),
        'files': sorted(manifest_files, key=lambda item: str(item.get('path') or '').lower()),
    }
    _manifest_path(workspace_path).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def _chunk_file_by_lines(rel_path: str, content: str, chunk_lines: int = BLUEPRINT_LARGE_FILE_CHUNK_LINES, overlap: int = BLUEPRINT_LARGE_FILE_CHUNK_OVERLAP) -> list[dict]:
    lines = (content or '').splitlines()
    if not lines:
        return []
    if len(lines) <= chunk_lines:
        return [{
            'header': f"lines 1-{len(lines)} of `{rel_path}`",
            'start_line': 1,
            'end_line': len(lines),
            'content': content,
        }]

    chunks: list[dict] = []
    start = 0
    while start < len(lines):
        end = min(len(lines), start + chunk_lines)
        block = "\n".join(lines[start:end])
        chunks.append(
            {
                'header': f"lines {start + 1}-{end} of `{rel_path}`",
                'start_line': start + 1,
                'end_line': end,
                'content': block,
            }
        )
        if end >= len(lines):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _score_chunk(query: str, rel_path: str, header: str, content: str) -> float:
    query_tokens = set(_tokenize(f'{query} {rel_path} {header}'))
    if not query_tokens:
        return 1.0
    haystack_tokens = set(_tokenize(f'{rel_path} {header} {content[:1200]}'))
    overlap = len(query_tokens & haystack_tokens)
    return float(overlap) + (0.5 if overlap else 0.0)


def read_query_relevant_file_content(workspace_path: Path, rel_path: str, query: str = '', limit: int = 8000, force_full: bool = False) -> str:
    try:
        file_path = workspace_path / rel_path
        if not file_path.exists() or not file_path.is_file():
            return ''
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''

    if force_full or len(content) <= limit:
        return content[:limit]

    chunks = _chunk_file_by_lines(rel_path, content)
    if not chunks:
        return content[:limit]
    ranked = sorted(chunks, key=lambda item: _score_chunk(query, rel_path, item['header'], item['content']), reverse=True)
    selected: list[str] = []
    used = 0
    for chunk in ranked[:3]:
        block = f"[Chunk: {chunk['header']}]\n{chunk['content']}\n"
        if used + len(block) > limit and selected:
            break
        selected.append(block[: max(0, limit - used)])
        used += len(selected[-1])
        if used >= limit:
            break
    return "\n".join(selected)[:limit] if selected else content[:limit]


def _resolve_import_reference_path(source_path: str, raw_import: str, known_paths: set[str]) -> str:
    text = str(raw_import or '').strip()
    if not text:
        return ''
    patterns = [
        r"from\s+['\"]([^'\"]+)['\"]",
        r"require\(\s*['\"]([^'\"]+)['\"]\s*\)",
        r"from\s+([A-Za-z0-9_\.\/-]+)",
        r"import\s+([A-Za-z0-9_\.\/-]+)",
    ]
    target = ''
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            target = str(match.group(1) or '').strip()
            break
    if not target:
        return ''
    if target.startswith('.'):
        base = Path(source_path).parent.as_posix()
        normalized = Path(posixpath.normpath(posixpath.join(base, target))).as_posix().lstrip('./')
        candidates = [
            normalized,
            f'{normalized}.ts',
            f'{normalized}.tsx',
            f'{normalized}.js',
            f'{normalized}.jsx',
            f'{normalized}.py',
            f'{normalized}.json',
            f'{normalized}/index.ts',
            f'{normalized}/index.tsx',
            f'{normalized}/index.js',
            f'{normalized}/index.jsx',
            f'{normalized}/__init__.py',
        ]
    else:
        lowered = target.lower()
        candidates = [
            path for path in known_paths
            if path.lower().endswith(f'/{lowered}.py')
            or path.lower().endswith(f'/{lowered}.ts')
            or path.lower().endswith(f'/{lowered}.tsx')
            or path.lower().endswith(f'/{lowered}.js')
            or path.lower().endswith(f'/{lowered}.jsx')
            or Path(path).stem.lower() == lowered
        ]
    for candidate in candidates:
        normalized = str(candidate).replace('\\', '/').lstrip('./')
        if normalized in known_paths:
            return normalized
    return ''


def _build_dependency_graph_payload(file_summaries: list[dict]) -> dict:
    known_paths = {str(item.get('path') or '') for item in file_summaries if item.get('path')}
    adjacency: dict[str, list[str]] = {}
    reverse_adjacency: dict[str, list[str]] = {}
    edges: list[dict] = []
    for item in file_summaries:
        source_path = str(item.get('path') or '')
        if not source_path:
            continue
        for raw_import in item.get('imports') or []:
            target_path = _resolve_import_reference_path(source_path, str(raw_import), known_paths)
            if not target_path or target_path == source_path:
                continue
            adjacency.setdefault(source_path, [])
            if target_path not in adjacency[source_path]:
                adjacency[source_path].append(target_path)
            reverse_adjacency.setdefault(target_path, [])
            if source_path not in reverse_adjacency[target_path]:
                reverse_adjacency[target_path].append(source_path)
            edge = {'from': source_path, 'to': target_path, 'reason': str(raw_import)}
            if edge not in edges:
                edges.append(edge)
    return {
        'edges': edges[:1200],
        'adjacency': adjacency,
        'reverse_adjacency': reverse_adjacency,
    }


def _manifest_entry_map(cache: dict) -> dict[str, dict]:
    return {
        str(item.get('path') or ''): item
        for item in (cache.get('manifest') or [])
        if item.get('path')
    }


def _summary_pool(cache: dict, limit: int = 400) -> list[dict]:
    seen: set[str] = set()
    items: list[dict] = []
    for item in list(cache.get('all_file_summaries') or []) + list(cache.get('important_files') or []):
        path = str(item.get('path') or '')
        if not path or path in seen:
            continue
        seen.add(path)
        items.append(item)
        if limit and len(items) >= limit:
            break
    return items


def _query_requests_broad_listing(query: str) -> bool:
    lowered = str(query or '').lower()
    return bool(re.search(r'\b(all|every|individual)\b', lowered) and re.search(r'\b(files?|modules?|folders?|directories?)\b', lowered))


def _query_requests_system_explanation(query: str) -> bool:
    lowered = str(query or '').lower()
    explanation_markers = (
        'how does', 'how do', 'how is', 'how are', 'tell me about',
        'walk me through', 'explain', 'overview', 'architecture', 'flow',
        'end to end', 'end-to-end', 'works', 'work',
    )
    return any(marker in lowered for marker in explanation_markers)


def _expanded_query_keywords(query: str) -> set[str]:
    lowered_query = str(query or '').lower()
    keywords = set(_tokenize(query))
    for alias_keywords in QUERY_INTENT_ALIASES.values():
        if any(keyword in lowered_query for keyword in alias_keywords):
            keywords.update(alias_keywords)
    return {keyword for keyword in keywords if len(keyword) > 2}


def _safe_query_patterns(query: str, limit: int = 6) -> list[str]:
    patterns: list[str] = []
    seen: set[str] = set()

    quoted = re.findall(r'["\']([^"\']{3,80})["\']', str(query or ''))
    for item in quoted:
        normalized = item.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            patterns.append(normalized)
        if len(patterns) >= limit:
            return patterns

    code_like = re.findall(r'[A-Za-z0-9_./-]{3,}', str(query or ''))
    for item in code_like:
        normalized = item.strip().lower().strip('.,:;()[]{}')
        if not normalized or normalized in seen:
            continue
        if normalized.count('/') >= 1 or '.' in normalized or '_' in normalized:
            seen.add(normalized)
            patterns.append(normalized)
        if len(patterns) >= limit:
            break
    return patterns


def _manifest_query_path_matches(manifest_map: dict[str, dict], query: str, limit: int = 18) -> list[str]:
    lowered = str(query or '').lower()
    candidates: list[str] = []
    patterns = [
        r'\b(?:files?|modules?|directories?|folders?)\s+(?:in|under|inside)\s+([a-zA-Z0-9_./-]+)',
        r'\b(?:about|within)\s+([a-zA-Z0-9_./-]+)\b',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, lowered):
            candidate = str(match.group(1) or '').strip().strip('.,:;')
            if candidate:
                candidates.append(candidate)

    matched_paths: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized_candidate = candidate.strip('/').replace('\\', '/')
        for path, entry in manifest_map.items():
            normalized_path = str(path or '').replace('\\', '/')
            path_parts = normalized_path.split('/')
            if normalized_path.startswith(f'{normalized_candidate}/') or normalized_path == normalized_candidate:
                if normalized_path not in seen and '.' in Path(normalized_path).name:
                    seen.add(normalized_path)
                    matched_paths.append(normalized_path)
            elif normalized_candidate in path_parts[:-1]:
                if normalized_path not in seen and '.' in Path(normalized_path).name:
                    seen.add(normalized_path)
                    matched_paths.append(normalized_path)
            if len(matched_paths) >= limit:
                return matched_paths
    return matched_paths


def _score_discovery_text(text: str, query_keywords: set[str], query_patterns: list[str]) -> float:
    haystack = str(text or '').lower()
    if not haystack:
        return 0.0
    score = 0.0
    for pattern in query_patterns:
        if pattern and pattern in haystack:
            score += 8.0
    for keyword in query_keywords:
        if keyword in haystack:
            score += 1.8
    return score


def _discover_query_candidates(
    manifest_map: dict[str, dict],
    summary_lookup: dict[str, dict],
    workspace_path: Path,
    query: str,
    *,
    limit: int = 24,
) -> list[dict]:
    query_keywords = _expanded_query_keywords(query)
    query_patterns = _safe_query_patterns(query)
    if not query_keywords and not query_patterns:
        return []

    candidate_scores: dict[str, dict] = {}

    def register(path: str, score: float, source: str, reason: str):
        normalized = str(path or '').replace('\\', '/').strip('/')
        if not normalized or normalized not in manifest_map or score <= 0:
            return
        existing = candidate_scores.get(normalized)
        if existing and existing.get('score', 0) >= score:
            return
        candidate_scores[normalized] = {
            'path': normalized,
            'score': score,
            'source': source,
            'reason': reason,
            'tier': int((manifest_map.get(normalized) or {}).get('tier') or 3),
        }

    for path, entry in manifest_map.items():
        path_lower = path.lower()
        stem_lower = Path(path_lower).stem
        parent_lower = Path(path_lower).parent.as_posix()
        manifest_score = _score_discovery_text(
            " ".join(filter(None, [path_lower, stem_lower, parent_lower])),
            query_keywords,
            query_patterns,
        )
        if manifest_score:
            register(path, manifest_score + (2.0 if int(entry.get('tier') or 3) == 1 else 0.0), 'discovery_path', 'Matched query terms against file path or folder names before content loading.')

    for path, summary in summary_lookup.items():
        summary_text = " ".join(
            str(value)
            for value in [
                summary.get('symbol'),
                summary.get('summary'),
                summary.get('purpose'),
                summary.get('why'),
                summary.get('how'),
                " ".join(summary.get('imports') or []),
                " ".join(summary.get('routes') or []),
                " ".join(summary.get('data_models') or []),
                " ".join(summary.get('headings') or []),
                " ".join(summary.get('json_keys') or []),
                " ".join(summary.get('commands') or []),
                " ".join(summary.get('role_hints') or []),
                summary.get('file_kind'),
            ]
            if value
        )
        summary_score = _score_discovery_text(summary_text, query_keywords, query_patterns)
        if summary_score:
            register(path, summary_score + 3.0, 'discovery_index', 'Matched indexed symbols, summaries, or extracted metadata before full file reads.')

    ranked_paths = sorted(
        candidate_scores.values(),
        key=lambda item: (-float(item.get('score') or 0), str(item.get('path') or '')),
    )
    fallback_scan_candidates: list[dict] = []
    for path, item in sorted(
        summary_lookup.items(),
        key=lambda pair: (
            int((manifest_map.get(pair[0]) or {}).get('tier') or pair[1].get('tier') or 3),
            int((manifest_map.get(pair[0]) or {}).get('size') or pair[1].get('size') or 0),
            str(pair[0]),
        ),
    ):
        tier = int((manifest_map.get(path) or {}).get('tier') or item.get('tier') or 3)
        if tier > 2:
            continue
        fallback_scan_candidates.append(
            {
                'path': path,
                'score': 0.0,
                'source': 'discovery_fallback',
                'reason': 'Scanned as part of the bounded fallback candidate pool for content discovery.',
                'tier': tier,
            }
        )
    scan_queue: list[dict] = []
    scan_queue.extend(ranked_paths)
    known_scan_paths = {str(item.get('path') or '') for item in ranked_paths}
    for item in fallback_scan_candidates:
        path = str(item.get('path') or '')
        if path in known_scan_paths:
            continue
        known_scan_paths.add(path)
        scan_queue.append(item)
    scan_budget = min(BLUEPRINT_DISCOVERY_MAX_SCAN_FILES, max(limit * 3, len(ranked_paths), 24))
    scanned = 0
    for item in scan_queue:
        if scanned >= scan_budget:
            break
        path = str(item.get('path') or '')
        entry = manifest_map.get(path) or {}
        if int(entry.get('tier') or 3) == 3 and path not in summary_lookup:
            continue
        excerpt = _read_text_excerpt(workspace_path / path, limit=BLUEPRINT_DISCOVERY_CONTENT_BYTES)
        if not excerpt:
            continue
        scanned += 1
        content_score = _score_discovery_text(excerpt, query_keywords, query_patterns)
        if content_score:
            register(path, float(item.get('score') or 0) + content_score + 6.0, 'discovery_content', 'Matched query terms inside file contents during bounded grep-style discovery.')

    return sorted(
        candidate_scores.values(),
        key=lambda item: (-float(item.get('score') or 0), str(item.get('path') or '')),
    )[:limit]


def _layer_bucket_for_path(path: str) -> str:
    normalized = str(path or '').replace('\\', '/').lower().strip('/')
    if not normalized:
        return ''
    parts = normalized.split('/')
    if not parts:
        return ''
    first = parts[0]
    if first in {'frontend', 'client', 'web', 'ui'}:
        return 'frontend'
    if first in {'backend', 'server', 'api'}:
        return 'backend'
    return ''


def _layer_coverage_candidates(summary_lookup: dict[str, dict], query: str, section_key: str = '') -> list[dict]:
    if not _query_requests_system_explanation(query):
        return []

    best_by_layer: dict[str, tuple[float, dict]] = {}
    for item in summary_lookup.values():
        path = str(item.get('path') or '')
        layer = _layer_bucket_for_path(path)
        if not layer:
            continue
        score = _score_summary_for_query(item, query, section_key=section_key)
        if score <= 0:
            continue
        current = best_by_layer.get(layer)
        if not current or score > current[0]:
            best_by_layer[layer] = (score, item)

    results: list[dict] = []
    for layer in ('backend', 'frontend'):
        current = best_by_layer.get(layer)
        if not current:
            continue
        score, item = current
        results.append({
            'path': str(item.get('path') or ''),
            'score': score,
            'source': f'{layer}_coverage',
            'reason': f'Included to cover the {layer} side of the system for an architectural or end-to-end question.',
            'tier': int(item.get('tier') or 2),
        })
    return results


def _frontend_ui_priority_score(path: str, haystack: str, lowered_query: str) -> float:
    path_lower = str(path or '').lower()
    score = 0.0
    if not any(keyword in lowered_query for keyword in (QUERY_INTENT_ALIASES['frontend'] | QUERY_INTENT_ALIASES['styling'] | QUERY_INTENT_ALIASES['navigation'])):
        return score
    if path_lower.startswith('frontend/'):
        score += 4.0
    if any(token in path_lower for token in ('src/components/', 'src/pages/', '.tsx', '.ts', '.css')):
        score += 2.5
    if any(token in path_lower for token in ('projectview', 'dashboard', 'codeworkspace', 'sidebar', 'layout', 'nav')):
        score += 4.0
    if any(token in haystack for token in ('hover:bg', 'bg-[', 'text-[', 'active', 'selected', 'rounded', 'className'.lower(), 'tailwind')):
        score += 3.0
    if 'sidebar' in lowered_query and any(token in path_lower for token in ('projectview', 'sidebar', 'dashboard', 'codeworkspace')):
        score += 5.0
    if any(token in lowered_query for token in ('highlight', 'color', 'hover', 'theme')) and any(token in path_lower for token in ('projectview', 'codeworkspace', 'dashboard', '.css', '.tsx')):
        score += 4.0
    return score


def _score_summary_for_query(item: dict, query: str, section_key: str = '') -> float:
    path = str(item.get('path') or '')
    tier = int(item.get('tier') or 2)
    path_lower = path.lower()
    file_kind = str(item.get('file_kind') or '').strip().lower()
    score = 0.0
    if tier == 1:
        score += 5.0
    if item.get('routes'):
        score += 2.0
    if item.get('data_models'):
        score += 2.0
    tokens = set(_tokenize(query))
    haystack = " ".join(
        str(value)
        for value in [
            item.get('path'),
            item.get('summary'),
            item.get('purpose'),
            item.get('why'),
            item.get('how'),
            item.get('symbol'),
            " ".join(item.get('imports') or []),
            " ".join(item.get('routes') or []),
            " ".join(item.get('data_models') or []),
            " ".join(item.get('headings') or []),
            " ".join(item.get('json_keys') or []),
            " ".join(item.get('commands') or []),
            " ".join(item.get('role_hints') or []),
            item.get('file_kind'),
        ]
        if value
    ).lower()
    if tokens:
        for token in tokens:
            if token in haystack:
                score += 2.5
            elif token in path.lower():
                score += 3.0
    lowered_query = str(query or '').lower()
    expanded_keywords: set[str] = set(tokens)
    for keywords in QUERY_INTENT_ALIASES.values():
        if any(keyword in lowered_query for keyword in keywords):
            expanded_keywords.update(keywords)

    for keyword in expanded_keywords:
        if keyword in haystack:
            score += 0.75
        if keyword in path.lower():
            score += 1.0

    for concept, keywords in QUERY_INTENT_ALIASES.items():
        if not any(keyword in lowered_query for keyword in keywords):
            continue
        keyword_overlap = sum(1 for keyword in keywords if keyword in haystack or keyword in path_lower)
        if keyword_overlap:
            score += keyword_overlap * (3.0 if concept == 'sandbox' else 1.8)
        if concept == 'sandbox' and any(token in path_lower for token in ('sandbox/', 'sandbox\\', 'executor.py', 'workspace.py', 'workspace_', 'runtime', 'process')):
            score += 8.0
    score += _frontend_ui_priority_score(path, haystack, lowered_query)
    score += SECTION_FILE_KIND_SCORES.get(section_key, {}).get(file_kind, 0.0)

    if section_key == 'services':
        if path_lower.startswith('services/') or '/services/' in f'/{path_lower}':
            score += 6.0
        service_name_patterns = (
            r'(^|[_-])(service|services|client|utils|utility|worker|builder|manager|processor|gateway|adapter)([_-]|$)',
            r'(^|[_-])job[_-]',
        )
        if any(re.search(pattern, path_lower) for pattern in service_name_patterns):
            score += 4.0
        if any(token in path_lower for token in ('entrypoint', 'daemon', 'scheduler', 'orchestr', 'resume_builder', 'clientapi', 'paymentapi')):
            score += 2.5

    section_tokens = {
        'services': {'service', 'worker', 'main', 'server', 'app', 'component'},
        'api': {'api', 'route', 'router', 'view', 'controller', 'endpoint', 'urls'},
        'database': {'model', 'schema', 'entity', 'migration', 'database', 'orm'},
        'workflows': {'workflow', 'agent', 'task', 'pipeline', 'feature'},
        'setup': {'readme', 'package', 'requirements', 'env', 'setup', 'docker', 'config'},
        'quality': {'test', 'spec', 'security', 'lint', 'quality', 'auth'},
        'knowledge': {'readme', 'doc', 'core', 'base', 'architecture', 'concept'},
    }
    for token in section_tokens.get(section_key, set()):
        if token in haystack or token in path.lower():
            score += 1.5
    return score


def retrieve_relevant_files(
    cache: dict,
    workspace_path: Path,
    query: str,
    *,
    explicit_paths: list[str] | None = None,
    section_key: str = '',
    max_files: int = 12,
    include_neighbors: bool = True,
) -> dict:
    manifest_map = _manifest_entry_map(cache)
    summary_lookup = {str(item.get('path') or ''): item for item in _summary_pool(cache)}
    dependency_graph = cache.get('dependency_graph') or {}
    adjacency = dependency_graph.get('adjacency') or {}
    reverse_adjacency = dependency_graph.get('reverse_adjacency') or {}

    selected_paths: list[str] = []
    trace: list[dict] = []
    seen_paths: set[str] = set()
    broad_listing = _query_requests_broad_listing(query)
    target_limit = max(max_files, 14) if broad_listing else max_files

    for raw_path in explicit_paths or []:
        normalized = str(raw_path or '').replace('\\', '/').strip('/')
        if not normalized or normalized not in manifest_map or normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        selected_paths.append(normalized)
        tier = int((manifest_map.get(normalized) or {}).get('tier') or 3)
        trace.append({'path': normalized, 'source': 'explicit', 'tier': tier, 'reason': 'Explicitly requested by query context.'})

    for matched_path in _manifest_query_path_matches(manifest_map, query, limit=max(max_files, 18)):
        if matched_path in seen_paths:
            continue
        seen_paths.add(matched_path)
        selected_paths.append(matched_path)
        trace.append({'path': matched_path, 'source': 'query_path', 'tier': int((manifest_map.get(matched_path) or {}).get('tier') or 2), 'reason': 'Matched a folder or path referenced directly in the question.'})
        if len(selected_paths) >= target_limit:
            break

    discovery_limit = min(max(target_limit * 2, 12), 28)
    for discovered in _discover_query_candidates(
        manifest_map,
        summary_lookup,
        workspace_path,
        query,
        limit=discovery_limit,
    ):
        path = str(discovered.get('path') or '')
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        selected_paths.append(path)
        trace.append({
            'path': path,
            'source': discovered.get('source') or 'discovery',
            'tier': int(discovered.get('tier') or 2),
            'reason': discovered.get('reason') or 'Discovered as a likely match before full retrieval scoring.',
        })
        if len(selected_paths) >= target_limit:
            break

    for layer_item in _layer_coverage_candidates(summary_lookup, query, section_key=section_key):
        path = str(layer_item.get('path') or '')
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        selected_paths.append(path)
        trace.append({
            'path': path,
            'source': layer_item.get('source') or 'layer_coverage',
            'tier': int(layer_item.get('tier') or 2),
            'reason': layer_item.get('reason') or 'Included to cover another major layer of the system.',
        })
        if len(selected_paths) >= target_limit:
            break

    scored: list[tuple[float, dict]] = []
    for item in summary_lookup.values():
        score = _score_summary_for_query(item, query, section_key=section_key)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get('path') or '')))

    for score, item in scored:
        path = str(item.get('path') or '')
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        selected_paths.append(path)
        trace.append({'path': path, 'source': 'retrieval', 'tier': int(item.get('tier') or 2), 'reason': f'Matched query/section relevance with score {score:.1f}.'})
        if len(selected_paths) >= target_limit:
            break

    for item in summary_lookup.values():
        path = str(item.get('path') or '')
        if not path or path in seen_paths or int(item.get('tier') or 2) != 1:
            continue
        seen_paths.add(path)
        selected_paths.append(path)
        trace.append({'path': path, 'source': 'tier1', 'tier': 1, 'reason': 'Always-include Tier 1 file for repository context.'})
        if len(selected_paths) >= target_limit:
            break

    if include_neighbors:
        neighbor_candidates: list[str] = []
        for path in list(selected_paths):
            neighbor_candidates.extend(list(adjacency.get(path) or [])[:2])
            neighbor_candidates.extend(list(reverse_adjacency.get(path) or [])[:2])
        for path in neighbor_candidates:
            if path in seen_paths or path not in manifest_map:
                continue
            seen_paths.add(path)
            selected_paths.append(path)
            trace.append({'path': path, 'source': 'dependency', 'tier': int((manifest_map.get(path) or {}).get('tier') or 2), 'reason': 'One-hop dependency/dependent expansion.'})
            limit_with_neighbors = target_limit + 4
            if len(selected_paths) >= limit_with_neighbors:
                break

    files: list[dict] = []
    for path in selected_paths[: max_files + 4]:
        manifest_entry = dict(manifest_map.get(path) or {'path': path, 'tier': 3})
        summary = dict(summary_lookup.get(path) or {})
        files.append({**manifest_entry, **summary, 'path': path, 'tier': int(manifest_entry.get('tier') or summary.get('tier') or 3)})

    return {
        'files': files,
        'trace': trace,
    }


def _instruction_doc_score(rel_path: str) -> float:
    normalized = str(rel_path or '').replace('\\', '/').strip('/')
    if not normalized:
        return float('-inf')

    lowered = normalized.lower()
    parts = [part for part in lowered.split('/') if part]
    file_name = parts[-1] if parts else lowered
    suffix = Path(file_name).suffix.lower()

    if any(part in {'.git', '.devhub', '.code-review-graph', '__pycache__', 'node_modules'} for part in parts[:-1]):
        return float('-inf')
    if file_name in {'license', 'license.md', 'license.txt'}:
        return float('-inf')
    if suffix not in {'.md', '.rst', '.txt'}:
        return float('-inf')

    token_hits = sum(1 for token in INSTRUCTION_DOC_NAME_TOKENS if token in file_name)
    dir_hits = sum(1 for part in parts[:-1] if part in INSTRUCTION_DOC_DIR_TOKENS)
    doc_like_txt = suffix == '.txt' and (token_hits > 0 or dir_hits > 0)
    if suffix == '.txt' and not doc_like_txt:
        return float('-inf')

    score = 0.0
    if len(parts) == 1:
        score += 18.0
    if file_name.startswith('readme'):
        score += 18.0
    if file_name in {'documentation.md', 'project_detail.md', 'project_readme.md', 'project_flow_documentation.txt'}:
        score += 16.0
    score += token_hits * 4.0
    score += dir_hits * 5.0
    if lowered.startswith('backend/docs/'):
        score += 10.0
    if lowered.startswith('frontend/docs/'):
        score += 8.0
    if lowered.startswith('docs/'):
        score += 8.0
    if '/docs/' in lowered:
        score += 4.0
    if any(part.startswith('.') for part in parts[:-1]):
        score -= 20.0
    if file_name.endswith('.txt'):
        score -= 1.0
    return score


def _service_candidate_score(item: dict) -> float:
    path = str(item.get('path') or '').replace('\\', '/').strip().lower()
    if not path:
        return 0.0

    file_kind = str(item.get('file_kind') or '').strip().lower()
    file_name = Path(path).name
    stem = Path(path).stem
    score = 0.0

    if file_kind in {'documentation', 'notes', 'readme', 'security-doc', 'contributing-doc'}:
        return 0.0

    if path.startswith('frontend/src/services/'):
        score += 14.0
    if path.startswith('backend/services/') or '/services/' in f'/{path}':
        score += 12.0
    if '/jobs/' in path or '/workers/' in path or '/worker/' in path:
        score += 10.0
    if any(path.endswith(suffix) for suffix in ('/urls.py', '/app.py', '/server.py', '/main.py', '/wsgi.py', '/asgi.py')):
        score += 6.0
    if any(re.search(pattern, stem) for pattern in (
        r'(^|[_-])(service|services|client|worker|builder|manager|processor|gateway|adapter)([_-]|$)',
        r'(^|[_-])job[_-]',
        r'(^|[_-])(utils|utility|api)([_-]|$)',
    )):
        score += 8.0
    if any(token in path for token in ('resume_builder', 'retell', 'gemini', 'payment', 'interview', 'aggregator', 'consumer', 'counsumer', 'websocket', 'ws_', 'chat_', 'notify')):
        score += 4.0
    if file_kind in {'source-file', 'api-module', 'routing-module', 'script', 'config', 'package-manifest'}:
        score += 3.0
    if path.startswith('backend/'):
        score += 2.0
    if file_kind in {'ui-component', 'page-component'} and '/services/' not in f'/{path}':
        score -= 12.0
    if '/components/' in path or '/pages/' in path:
        score -= 8.0

    return max(0.0, score)


def _instruction_context(workspace_path: Path) -> list[dict]:
    entries_by_path: dict[str, dict] = {}

    def register(rel_path: str, score: float) -> None:
        normalized = str(rel_path or '').replace('\\', '/').strip('/')
        if not normalized:
            return
        excerpt = _read_text_excerpt(workspace_path / normalized, limit=3000)
        if not excerpt:
            return
        current = entries_by_path.get(normalized)
        if current and float(current.get('score') or 0.0) >= score:
            return
        entries_by_path[normalized] = {
            'path': normalized,
            'content': excerpt,
            'score': score,
        }

    for rel_path in INSTRUCTION_FILES:
        normalized = str(rel_path or '').replace('\\', '/').strip('/')
        if not normalized:
            continue
        explicit_score = 40.0 if not normalized.startswith('.devhub/') else 6.0
        register(normalized, explicit_score)

    for file_path in workspace_path.rglob('*'):
        if not file_path.is_file():
            continue
        try:
            rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
        except ValueError:
            continue
        if not rel_path:
            continue
        parts = [part for part in rel_path.split('/') if part]
        if any(part in SKIP_DIRS for part in parts[:-1]):
            continue
        score = _instruction_doc_score(rel_path)
        if score == float('-inf'):
            continue
        register(rel_path, score)

    ranked = sorted(
        entries_by_path.values(),
        key=lambda item: (
            -float(item.get('score') or 0.0),
            len(str(item.get('path') or '')),
            str(item.get('path') or ''),
        ),
    )
    return [
        {
            'path': str(item.get('path') or ''),
            'content': str(item.get('content') or ''),
        }
        for item in ranked[:24]
    ]


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


def _workspace_root_directories(workspace_path: Path) -> list[str]:
    always_skip = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}
    root_dirs: list[str] = []
    try:
        entries = sorted(workspace_path.iterdir(), key=lambda item: item.name.lower())
    except Exception:
        return root_dirs
    for entry in entries:
        if not entry.is_dir() or entry.name in always_skip:
            continue
        root_dirs.append(entry.name)
    return root_dirs


def _ensure_root_dirs_in_tree(
    repo_tree: str,
    indexed_paths: list[str],
    project_name: str,
    root_directories: list[str] | None = None,
) -> str:
    """Ensure root directories from the manifest appear in repo tree."""
    _ = project_name
    always_skip = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}
    manifest_root_dirs: set[str] = set()
    for raw_path in indexed_paths:
        parts = str(raw_path or "").replace('\\', '/').split('/')
        if len(parts) > 1 and parts[0] not in always_skip:
            manifest_root_dirs.add(parts[0])
    for directory in root_directories or []:
        normalized = str(directory or "").strip()
        if normalized and normalized not in always_skip:
            manifest_root_dirs.add(normalized)

    tree_lines = repo_tree.splitlines()
    mentioned = {line.strip().lstrip('|- ').rstrip('/') for line in tree_lines}
    missing = sorted(manifest_root_dirs - mentioned)
    if missing and tree_lines:
        insert_lines = [f"|- {directory}/" for directory in missing]
        tree_lines = tree_lines[:1] + insert_lines + tree_lines[1:]
    return '\n'.join(tree_lines)


def _build_repo_tree_nodes(
    indexed_paths: list[str],
    project_name: str,
    max_nodes: int = 1600,
    max_children_per_dir: int = 60,
    root_directories: list[str] | None = None,
) -> list[dict]:
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

    for directory in root_directories or []:
        normalized = str(directory or "").strip()
        if not normalized or normalized in tree:
            continue
        tree[normalized] = {
            "name": normalized,
            "path": normalized,
            "type": "directory",
            "children": {},
        }

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


def _scan_env_var_names(workspace_path: Path) -> list[str]:
    """Scan project files for environment variable references."""
    patterns = [
        re.compile(r"""os\.(?:environ\.get|getenv)\(\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
        re.compile(r"""os\.environ\[\s*['"]([A-Z][A-Z0-9_]*)['"]\s*\]"""),
        re.compile(r"""process\.env\.([A-Z][A-Z0-9_]*)"""),
        re.compile(r"""import\.meta\.env\.([A-Z][A-Z0-9_]*)"""),
    ]
    skip_dirs = {'.git', 'node_modules', 'venv', '.venv', '__pycache__', 'dist', 'build', '.devhub', 'data'}
    names: set[str] = set()
    scanned_files = 0

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [directory for directory in dirs if directory not in skip_dirs]
        for filename in files:
            lowered = filename.lower()
            is_code_file = filename.endswith(('.py', '.js', '.ts', '.tsx', '.jsx'))
            is_env_file = lowered == '.env' or lowered.startswith('.env.')
            if not (is_code_file or is_env_file):
                continue
            scanned_files += 1
            if scanned_files > 500:
                return sorted(names)[:60]
            file_path = Path(root) / filename
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')[:50_000]
            except Exception:
                continue
            for pattern in patterns:
                for match in pattern.finditer(content):
                    names.add(match.group(1))
            if is_env_file:
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#') or '=' not in stripped:
                        continue
                    var_name = stripped.split('=', 1)[0].strip()
                    if re.match(r'^[A-Z][A-Z0-9_]*$', var_name):
                        names.add(var_name)
    return sorted(names)[:60]


def build_blueprint_context(project: Project, workspace_path: Path, force: bool = False) -> dict:
    cache_path = _blueprint_cache_path(workspace_path)
    manifest = _build_blueprint_manifest(workspace_path)
    manifest_entries = list(manifest.get('files') or [])
    fingerprint = _manifest_fingerprint(manifest_entries)

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
    root_directories = _workspace_root_directories(workspace_path)
    for entry in manifest_entries:
        rel_path = str(entry.get('path') or '')
        tier = int(entry.get('tier') or 3)
        if not rel_path or rel_path.startswith('.devhub/'):
            continue
        directory = rel_path.split('/')[0] if '/' in rel_path else '.'
        directory_counts[directory] = directory_counts.get(directory, 0) + 1
        if tier == 3:
            continue
        summary = _file_summary(workspace_path / rel_path, workspace_path, include_excerpt=(tier == 1))
        if summary:
            file_summaries.append(summary)

    indexed_paths = [
        str(entry.get('path') or '').replace('\\', '/')
        for entry in manifest_entries
        if str(entry.get('path') or '').replace('\\', '/')
        and not str(entry.get('path') or '').replace('\\', '/').startswith('.devhub/')
    ]

    graph_data = {}
    try:
        from agents.graph_bridge import build_graph_context
        graph_data = build_graph_context(workspace_path)
    except ImportError:
        graph_data = {}
    except Exception:
        graph_data = {}
    if graph_data and len(file_summaries) > 2000:
        hub_files = {
            str(item.get('file_path') or '').replace('\\', '/')
            for item in (graph_data.get('key_components') or [])
            if isinstance(item, dict) and str(item.get('file_path') or '').strip()
        }
        for item in file_summaries:
            if str(item.get('path') or '').replace('\\', '/') in hub_files:
                item['tier'] = 1

    ranked_files = sorted(
        file_summaries,
        key=lambda item: (
            int(item.get('tier') or 3),
            -_score_blueprint_file(item),
            str(item.get('path') or ''),
        ),
    )
    important_files = ranked_files[:60]
    all_file_summaries = ranked_files[:500]
    dependency_graph = _build_dependency_graph_payload(all_file_summaries)
    database_analysis = _extract_universal_schema(workspace_path, manifest_entries, graph_data=graph_data)
    api_reference = build_api_reference_catalog(workspace_path)

    # Deterministic fact extraction — results injected into prompts so LLM
    # synthesizes prose around verified facts, not hallucinated lists.
    from agents.fact_extractors import (
        detect_css_frameworks, detect_test_frameworks,
        detect_lint_tools, detect_websocket_services, detect_integration_clients,
    )
    detected_css_frameworks = detect_css_frameworks(workspace_path)
    detected_test_frameworks = detect_test_frameworks(workspace_path)
    detected_lint_tools = detect_lint_tools(workspace_path)
    detected_websocket_services = detect_websocket_services(workspace_path)
    detected_integration_clients = detect_integration_clients(workspace_path)

    readme_excerpt = ''
    for candidate in ('README.md', 'readme.md'):
        readme_excerpt = _read_text_excerpt(workspace_path / candidate)
        if readme_excerpt:
            break
    instruction_files = _instruction_context(workspace_path)

    compact_lines = [
        f"Project: {project.name}",
        f"Fingerprint: {fingerprint}",
        f"Manifest files: {len(manifest_entries)}",
        f"Indexed files: {len(file_summaries)}",
        "Top directories:",
    ]
    for directory, count in sorted(directory_counts.items(), key=lambda item: (-item[1], item[0]))[:12]:
        compact_lines.append(f"- {directory}: {count} files")
    compact_lines.append("Important files:")
    for item in important_files[:60]:
        compact_lines.append(f"- {item['path']}: {item['summary']}")
    if database_analysis.get('database_model_names'):
        compact_lines.append("Persisted backend models:")
        for model in (database_analysis.get('database_model_names') or [])[:20]:
            compact_lines.append(f"- {model}")
    graph_summary = str(graph_data.get('graph_summary') or '')
    if graph_summary:
        compact_lines.append("Structural graph analysis:")
        for line in graph_summary.splitlines()[:12]:
            if line.strip():
                compact_lines.append(f"- {line.strip()}")
    env_var_names = _scan_env_var_names(workspace_path)
    if env_var_names:
        compact_lines.append(f"Environment variables referenced in code ({len(env_var_names)} found):")
        for name in env_var_names[:60]:
            compact_lines.append(f"  - {name}")
    if instruction_files:
        compact_lines.append("Project instructions:")
        for item in instruction_files:
            compact_lines.append(f"- {item['path']}: {item['content'][:220].replace(chr(10), ' ')}")
    if readme_excerpt:
        compact_lines.append("README content (use for setup_steps):")
        for line in readme_excerpt.splitlines()[:40]:
            compact_lines.append(f"  {line}")

    repo_tree = _render_repo_tree(file_summaries, project.name)
    repo_tree = _ensure_root_dirs_in_tree(repo_tree, indexed_paths, project.name, root_directories=root_directories)
    repo_tree_nodes = _build_repo_tree_nodes(indexed_paths, project.name, root_directories=root_directories)

    compact_summary = "\n".join(compact_lines)[:12000]
    cache = {
        'cache_version': BLUEPRINT_CACHE_VERSION,
        'fingerprint': fingerprint,
        'manifest_file_count': len(manifest_entries),
        'file_count': len(file_summaries),
        'directory_counts': directory_counts,
        'root_directories': root_directories,
        'manifest': manifest_entries[:6000],
        'indexed_paths': indexed_paths[:4000],
        'important_files': important_files,
        'all_file_summaries': all_file_summaries,
        'dependency_graph': dependency_graph,
        'api_reference': api_reference[:200],
        'database_schema': database_analysis.get('database_schema') or [],
        'database_mermaid_erd': database_analysis.get('database_mermaid_erd') or '',
        'database_source_files': database_analysis.get('database_source_files') or [],
        'database_model_names': database_analysis.get('database_model_names') or [],
        'graph_summary': graph_summary,
        'graph_architecture_overview': graph_data.get('architecture_overview') or {},
        'graph_repository_map': graph_data.get('repository_map') or [],
        'graph_key_components': graph_data.get('key_components') or [],
        'graph_sequence_flows': graph_data.get('sequence_flows') or [],
        'graph_knowledge_gaps': graph_data.get('knowledge_gaps') or [],
        'graph_stats': graph_data.get('graph_stats') or {},
        'env_var_names': env_var_names,
        'readme_excerpt': readme_excerpt[:4000],
        'instruction_files': instruction_files,
        'repo_tree': repo_tree,
        'repo_tree_nodes': repo_tree_nodes,
        'compact_summary': compact_summary,
        # Deterministic facts — injected into prompts to ground LLM output
        'detected_css_frameworks': detected_css_frameworks,
        'detected_test_frameworks': detected_test_frameworks,
        'detected_lint_tools': detected_lint_tools,
        'detected_websocket_services': detected_websocket_services,
        'detected_integration_clients': detected_integration_clients,
    }

    cache_path.write_text(json.dumps(cache, indent=2), encoding='utf-8')
    _dependency_graph_path(workspace_path).write_text(json.dumps(dependency_graph, indent=2), encoding='utf-8')
    _repo_map_path(workspace_path).write_text(_render_repo_map(project, cache), encoding='utf-8')
    upsert_working_memory(project, 'blueprint_context', compact_summary, {
        'fingerprint': fingerprint,
        'cache_version': BLUEPRINT_CACHE_VERSION,
        'file_count': len(file_summaries),
        'cache_path': str(cache_path),
        'repo_map_path': str(_repo_map_path(workspace_path)),
    })
    return cache


def slim_context_for_llm(context: dict, important_files_limit: int = 60) -> dict:
    """Return a compact, LLM-safe slice of a codebase_context dict.

    The full context can contain 6 000+ manifest entries and 500 file summaries
    that bloat json.dumps() to several MB before the caller truncates.  This
    function pre-selects the high-signal fields so serialisation stays fast and
    the resulting JSON fits in a model context window without wasted truncation.
    """
    if not isinstance(context, dict):
        return {}
    important = context.get('important_files') or []
    return {
        'compact_summary': context.get('compact_summary') or '',
        'graph_summary': context.get('graph_summary') or '',
        'graph_stats': context.get('graph_stats') or {},
        'file_count': context.get('file_count') or 0,
        'manifest_file_count': context.get('manifest_file_count') or 0,
        'important_files': important[:important_files_limit],
        'routes': (context.get('routes') or [])[:24],
        'data_models': (context.get('data_models') or [])[:24],
        'database_schema': (context.get('database_schema') or [])[:20],
        'database_model_names': (context.get('database_model_names') or [])[:30],
        'readme_excerpt': (context.get('readme_excerpt') or '')[:3000],
        'instruction_files': context.get('instruction_files') or [],
        'repo_tree': (context.get('repo_tree') or '')[:6000],
        'directory_counts': context.get('directory_counts') or {},
    }


def _read_text_excerpt(file_path: Path, limit: int = 4000) -> str:
    try:
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding='utf-8', errors='ignore')[:limit]
    except Exception:
        return ''
    return ''


def read_deep_file_content(workspace_path: Path, rel_path: str, limit: int = 8000) -> str:
    """Read full file content (up to *limit* chars) for targeted deep analysis."""
    return read_query_relevant_file_content(workspace_path, rel_path, query=rel_path, limit=limit)


def select_files_for_section(cache: dict, section_key: str, workspace_path: Path | None = None) -> list[dict]:
    """Return the most relevant indexed files for a given Blueprint section.

    Uses role hints and path-name heuristics to rank files by relevance.
    """
    section_queries = {
        'services': 'find service module business logic client utility worker entrypoint files, services directories, runtime services, servers, schedulers, builders, managers, adapters, and integration clients',
        'api': 'find API routes, router files, endpoint handlers, views, and request-processing modules',
        'database': 'find models, schemas, entities, migrations, and persistence layer files',
        'workflows': 'find workflow, agent, pipeline, task, sequence, and end-to-end execution files',
        'setup': 'find README, setup docs, package manifests, env templates, config, and run commands',
        'quality': 'find tests, security rules, linting, validation, auth, performance, and quality-related files',
        'knowledge': 'find docs, architectural core files, concepts, FAQs, and newcomer-facing reference files',
    }
    if workspace_path:
        if section_key == 'services':
            summary_items = _summary_pool(cache, limit=0)
            service_candidates: list[tuple[float, dict]] = []
            for item in summary_items:
                candidate_score = _service_candidate_score(item)
                if candidate_score <= 0:
                    continue
                combined_score = candidate_score + _score_summary_for_query(item, section_queries['services'], section_key='services')
                service_candidates.append((combined_score, item))
            service_candidates.sort(key=lambda pair: (-pair[0], str(pair[1].get('path') or '')))
            if service_candidates:
                return [dict(item, path=str(item.get('path') or '')) for _, item in service_candidates[:20]]
        if section_key == 'database' and cache.get('database_source_files'):
            summary_lookup = {str(item.get('path') or ''): item for item in _summary_pool(cache, limit=0)}
            structured_files = [
                summary_lookup[path]
                for path in cache.get('database_source_files') or []
                if path in summary_lookup
            ]
            if structured_files:
                return structured_files[:16]
        if section_key == 'quality':
            # Deterministically inject lint/test config files first, then fill with retrieval
            _LINT_STEMS = {'eslint', '.eslintrc', 'pylint', 'flake8', 'mypy', 'pyproject', 'tox', 'pytest',
                           'jest.config', 'vitest.config', 'ruff', 'bandit', 'sonar', 'semgrep'}
            manifest_map = _manifest_entry_map(cache)
            summary_lookup = {str(item.get('path') or ''): item for item in _summary_pool(cache, limit=0)}
            quality_extras: list[dict] = []
            seen_extra: set[str] = set()
            for path in manifest_map:
                path_lower = path.lower()
                stem = Path(path_lower).stem
                # Lint/type-check config
                if any(pat in path_lower for pat in _LINT_STEMS):
                    if path not in seen_extra:
                        seen_extra.add(path)
                        quality_extras.append(summary_lookup.get(path) or {'path': path})
                # Test files (up to 3)
                elif (('test' in path_lower or 'spec' in path_lower) and
                      path_lower.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')) and
                      len([e for e in quality_extras if 'test' in str(e.get('path', '')).lower()]) < 3):
                    if path not in seen_extra:
                        seen_extra.add(path)
                        quality_extras.append(summary_lookup.get(path) or {'path': path})
            retrieval = retrieve_relevant_files(
                cache, workspace_path, section_queries['quality'],
                section_key='quality', max_files=12, include_neighbors=True,
            )
            retrieval_files = retrieval.get('files') or []
            combined: list[dict] = list(quality_extras)
            for f in retrieval_files:
                p = str(f.get('path') or '')
                if p not in seen_extra:
                    combined.append(f)
            return combined[:20]
        retrieval = retrieve_relevant_files(
            cache,
            workspace_path,
            section_queries.get(section_key, section_key),
            section_key=section_key,
            max_files=16,
            include_neighbors=True,
        )
        if retrieval.get('files'):
            return retrieval['files'][:16]
    return _summary_pool(cache, limit=12)



import fnmatch

def _build_gitignore_matcher(workspace_path: Path):
    gitignore_path = workspace_path / '.gitignore'
    rules = []
    if gitignore_path.exists():
        try:
            for line in gitignore_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('!'):
                    if line.endswith('/'):
                        line = line[:-1]
                    rules.append(line)
        except Exception:
            pass

    def is_ignored(rel_path: str, is_dir: bool = False) -> bool:
        if not rules:
            return False
        parts = rel_path.split('/')
        for rule in rules:
            if rule.startswith('/'):
                if fnmatch.fnmatch((rel_path + '/') if is_dir else rel_path, rule[1:] + '*'):
                    return True
            else:
                for part in parts:
                    if fnmatch.fnmatch(part, rule):
                        return True
                if fnmatch.fnmatch(rel_path, rule) or fnmatch.fnmatch(rel_path, '*/' + rule):
                    return True
        return False
    return is_ignored


def _iter_workspace_files(workspace_path: Path) -> list[Path]:
    items: list[Path] = []
    is_ignored = _build_gitignore_matcher(workspace_path)
    project_root_markers = {'.git', 'package.json', 'Cargo.toml', 'go.mod', 'pom.xml', 'setup.py', 'pyproject.toml'}
    nested_project_roots: set[str] = set()

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
        rel_root = str(Path(root).relative_to(workspace_path)).replace('\\', '/')
        depth = 0 if rel_root == '.' else rel_root.count('/') + 1

        if is_ignored(rel_root, is_dir=True):
            dirs.clear()
            continue

        if any(rel_root == npr or rel_root.startswith(npr + '/') for npr in nested_project_roots):
            dirs.clear()
            continue

        if depth >= 2:
            file_set = set(files) | set(dirs)
            if file_set & project_root_markers:
                nested_project_roots.add(rel_root)
                dirs.clear()
                continue

        for filename in files:
            path = Path(root) / filename
            rel_path = str(path.relative_to(workspace_path)).replace('\\', '/')
            if is_ignored(rel_path):
                continue
            if path.suffix.lower() in INDEXABLE_EXTENSIONS:
                items.append(path)
    return items


def _iter_blueprint_files(workspace_path: Path) -> list[Path]:
    config_names = {name.lower() for name in BLUEPRINT_CONFIG_FILES}
    items: list[Path] = []
    is_ignored = _build_gitignore_matcher(workspace_path)

    # Project root marker files — if a subdirectory contains any of these,
    # it's a separate project and should not be indexed as part of this codebase.
    project_root_markers = {'.git', 'package.json', 'Cargo.toml', 'go.mod', 'pom.xml', 'setup.py', 'pyproject.toml'}

    # Track directories detected as nested project roots so we skip them.
    nested_project_roots: set[str] = set()

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS and directory.lower() not in BLUEPRINT_SKIP_DIRS]
        rel_root = str(Path(root).relative_to(workspace_path)).replace('\\', '/')
        depth = 0 if rel_root == '.' else rel_root.count('/') + 1

        if is_ignored(rel_root, is_dir=True):
            dirs.clear()
            continue

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
            if is_ignored(rel_path):
                continue
            if _should_index_blueprint_file(path, workspace_path, config_names):
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
    lowered_query = str(query or '').lower()
    expanded_keywords: set[str] = set(query_tokens)
    for keywords in QUERY_INTENT_ALIASES.values():
        if any(keyword in lowered_query for keyword in keywords):
            expanded_keywords.update(keywords)
    results = []
    for entry in entries:
        keywords = set(entry.keywords or [])
        overlap = len(expanded_keywords & keywords)
        if not overlap and selected_file and selected_file != entry.file_path:
            continue
        score = float(overlap)
        path_lower = str(entry.file_path or '').lower()
        if any(keyword in lowered_query for keyword in QUERY_INTENT_ALIASES['sandbox']):
            if any(token in path_lower for token in ('sandbox/', 'sandbox\\', 'executor.py', 'workspace.py', 'workspace_', 'runtime', 'process')):
                score += 6.0
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
