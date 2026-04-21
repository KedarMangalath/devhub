"""Deterministic fact extractors for blueprint generation.

These functions scan the workspace using AST, filesystem patterns, and
package manifests — never LLM calls. Results are injected into prompts so
the LLM synthesizes prose around verified facts rather than hallucinating lists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ── CSS / Styling frameworks ────────────────────────────────────────────────

_CSS_PACKAGE_PATTERNS: list[tuple[str, str]] = [
    ('tailwindcss', 'Tailwind CSS'),
    ('tailwind', 'Tailwind CSS'),
    ('bootstrap', 'Bootstrap'),
    ('bootstrap-icons', 'Bootstrap Icons'),
    ('@mui/material', 'Material UI'),
    ('@mui/core', 'Material UI'),
    ('@chakra-ui/react', 'Chakra UI'),
    ('styled-components', 'styled-components'),
    ('@emotion/react', 'Emotion'),
    ('@emotion/styled', 'Emotion'),
    ('antd', 'Ant Design'),
    ('@mantine/core', 'Mantine'),
    ('daisyui', 'daisyUI'),
    ('shadcn', 'shadcn/ui'),
    ('sass', 'SASS'),
    ('node-sass', 'SASS'),
    ('less', 'Less CSS'),
    ('bulma', 'Bulma'),
    ('foundation-sites', 'Foundation'),
    ('materialize-css', 'Materialize CSS'),
    ('primereact', 'PrimeReact'),
    ('primevue', 'PrimeVue'),
    ('vuetify', 'Vuetify'),
    ('quasar', 'Quasar'),
]

_CSS_IMPORT_PATTERNS: list[tuple[str, str]] = [
    ('bootstrap/dist/css', 'Bootstrap'),
    ('bootstrap-icons/', 'Bootstrap Icons'),
    ("'bootstrap'", 'Bootstrap'),
    ('"bootstrap"', 'Bootstrap'),
    ('tailwind', 'Tailwind CSS'),
    ('@mui/', 'Material UI'),
    ('chakra', 'Chakra UI'),
    ('antd/', 'Ant Design'),
    ('@mantine/', 'Mantine'),
]


def detect_css_frameworks(workspace: Path) -> list[dict[str, Any]]:
    """Detect CSS/styling frameworks present in the workspace.

    Scans package.json deps/devDeps and JS/JSX/TSX imports.
    Returns [{'name', 'evidence_file', 'version'}].
    """
    found: dict[str, dict] = {}

    def _register(name: str, evidence: str, version: str = 'unknown') -> None:
        if name not in found:
            found[name] = {'name': name, 'evidence_file': evidence, 'version': version}

    # Scan all package.json files
    for pkg_path in workspace.rglob('package.json'):
        if _skip_path(pkg_path, workspace):
            continue
        try:
            data = json.loads(pkg_path.read_text(encoding='utf-8', errors='ignore'))
        except Exception:
            continue
        rel = str(pkg_path.relative_to(workspace)).replace('\\', '/')
        all_deps = {}
        all_deps.update(data.get('dependencies') or {})
        all_deps.update(data.get('devDependencies') or {})
        for pkg_key, friendly_name in _CSS_PACKAGE_PATTERNS:
            if pkg_key in all_deps:
                _register(friendly_name, rel, str(all_deps[pkg_key]))

    # Grep JSX/TSX/JS/TS imports for CSS framework markers
    for ext in ('*.jsx', '*.tsx', '*.js', '*.ts', '*.css', '*.scss'):
        for src_path in workspace.rglob(ext):
            if _skip_path(src_path, workspace):
                continue
            try:
                content = src_path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            rel = str(src_path.relative_to(workspace)).replace('\\', '/')
            for marker, friendly_name in _CSS_IMPORT_PATTERNS:
                if marker in content and friendly_name not in found:
                    _register(friendly_name, rel)
                    break  # one match per file is enough

    return list(found.values())


# ── Test frameworks ─────────────────────────────────────────────────────────

_TEST_PACKAGE_PATTERNS: list[tuple[str, str]] = [
    ('pytest', 'pytest'),
    ('pytest-asyncio', 'pytest-asyncio'),
    ('playwright', 'Playwright'),
    ('@playwright/test', 'Playwright'),
    ('jest', 'Jest'),
    ('vitest', 'Vitest'),
    ('cypress', 'Cypress'),
    ('@cypress/react', 'Cypress'),
    ('mocha', 'Mocha'),
    ('chai', 'Chai'),
    ('selenium', 'Selenium'),
    ('selenium-webdriver', 'Selenium'),
    ('unittest', 'unittest'),
    ('nose2', 'nose2'),
    ('hypothesis', 'Hypothesis'),
    ('@testing-library/react', 'React Testing Library'),
    ('@testing-library/jest-dom', 'React Testing Library'),
    ('supertest', 'Supertest'),
]

_TEST_REQUIREMENTS_PATTERNS: list[tuple[str, str]] = [
    ('pytest', 'pytest'),
    ('playwright', 'Playwright'),
    ('selenium', 'Selenium'),
    ('nose', 'nose'),
    ('hypothesis', 'Hypothesis'),
    ('factory.boy', 'factory_boy'),
    ('faker', 'Faker'),
]

_TEST_CONFIG_FILES: list[tuple[str, str]] = [
    ('pytest.ini', 'pytest'),
    ('conftest.py', 'pytest'),
    ('jest.config.js', 'Jest'),
    ('jest.config.ts', 'Jest'),
    ('vitest.config.ts', 'Vitest'),
    ('vitest.config.js', 'Vitest'),
    ('cypress.config.js', 'Cypress'),
    ('cypress.config.ts', 'Cypress'),
    ('playwright.config.js', 'Playwright'),
    ('playwright.config.ts', 'Playwright'),
]


def detect_test_frameworks(workspace: Path) -> list[dict[str, Any]]:
    """Detect test frameworks from deps, configs, and test file patterns."""
    found: dict[str, dict] = {}

    def _register(name: str, evidence: str, version: str = 'detected') -> None:
        if name not in found:
            found[name] = {'name': name, 'evidence_file': evidence, 'version': version}

    # package.json deps
    for pkg_path in workspace.rglob('package.json'):
        if _skip_path(pkg_path, workspace):
            continue
        try:
            data = json.loads(pkg_path.read_text(encoding='utf-8', errors='ignore'))
        except Exception:
            continue
        rel = str(pkg_path.relative_to(workspace)).replace('\\', '/')
        all_deps = {}
        all_deps.update(data.get('dependencies') or {})
        all_deps.update(data.get('devDependencies') or {})
        for pkg_key, friendly_name in _TEST_PACKAGE_PATTERNS:
            if pkg_key in all_deps:
                _register(friendly_name, rel, str(all_deps[pkg_key]))

    # requirements.txt / pyproject.toml
    for req_path in workspace.rglob('requirements*.txt'):
        if _skip_path(req_path, workspace):
            continue
        try:
            content = req_path.read_text(encoding='utf-8', errors='ignore').lower()
        except Exception:
            continue
        rel = str(req_path.relative_to(workspace)).replace('\\', '/')
        for pkg_key, friendly_name in _TEST_REQUIREMENTS_PATTERNS:
            if pkg_key in content:
                _register(friendly_name, rel)

    for toml_path in workspace.rglob('pyproject.toml'):
        if _skip_path(toml_path, workspace):
            continue
        try:
            content = toml_path.read_text(encoding='utf-8', errors='ignore').lower()
        except Exception:
            continue
        rel = str(toml_path.relative_to(workspace)).replace('\\', '/')
        for pkg_key, friendly_name in _TEST_REQUIREMENTS_PATTERNS:
            if pkg_key in content:
                _register(friendly_name, rel)
        if '[tool.pytest' in content:
            _register('pytest', rel)

    # Known config files
    for config_name, framework_name in _TEST_CONFIG_FILES:
        for config_path in workspace.rglob(config_name):
            if _skip_path(config_path, workspace):
                continue
            rel = str(config_path.relative_to(workspace)).replace('\\', '/')
            _register(framework_name, rel)

    # Scan for test files by name pattern (evidence-only, don't add new framework unless confirmed)
    _PW_PATTERNS = re.compile(r'test_pw|pw_test|e2e|playwright', re.IGNORECASE)
    for test_file in workspace.rglob('test_*.py'):
        if _skip_path(test_file, workspace):
            continue
        if _PW_PATTERNS.search(test_file.name):
            rel = str(test_file.relative_to(workspace)).replace('\\', '/')
            _register('Playwright', rel)

    return list(found.values())


# ── Lint / static analysis tools ────────────────────────────────────────────

_LINT_PACKAGE_PATTERNS: list[tuple[str, str]] = [
    ('eslint', 'ESLint'),
    ('@typescript-eslint/eslint-plugin', 'TypeScript ESLint'),
    ('prettier', 'Prettier'),
    ('stylelint', 'Stylelint'),
    ('tslint', 'TSLint'),
    ('oxlint', 'oxlint'),
    ('biome', 'Biome'),
]

_LINT_REQUIREMENTS_PATTERNS: list[tuple[str, str]] = [
    ('flake8', 'Flake8'),
    ('pylint', 'Pylint'),
    ('black', 'Black'),
    ('isort', 'isort'),
    ('mypy', 'mypy'),
    ('ruff', 'ruff'),
    ('bandit', 'Bandit'),
    ('semgrep', 'semgrep'),
    ('pyflakes', 'pyflakes'),
    ('pycodestyle', 'pycodestyle'),
    ('pydocstyle', 'pydocstyle'),
]

_LINT_CONFIG_FILES: list[tuple[str, str]] = [
    ('eslint.config.js', 'ESLint'),
    ('eslint.config.ts', 'ESLint'),
    ('.eslintrc', 'ESLint'),
    ('.eslintrc.json', 'ESLint'),
    ('.eslintrc.js', 'ESLint'),
    ('.eslintrc.yaml', 'ESLint'),
    ('.eslintrc.yml', 'ESLint'),
    ('.prettierrc', 'Prettier'),
    ('prettier.config.js', 'Prettier'),
    ('.flake8', 'Flake8'),
    ('mypy.ini', 'mypy'),
    ('.mypy.ini', 'mypy'),
    ('.bandit', 'Bandit'),
    ('ruff.toml', 'ruff'),
    ('.ruff.toml', 'ruff'),
    ('.pre-commit-config.yaml', 'pre-commit'),
    ('sonar-project.properties', 'SonarQube'),
    ('.pylintrc', 'Pylint'),
    ('tox.ini', 'tox'),
]


def detect_lint_tools(workspace: Path) -> list[dict[str, Any]]:
    """Detect linting, formatting, and static analysis tools."""
    found: dict[str, dict] = {}

    def _register(name: str, evidence: str, version: str = 'detected') -> None:
        if name not in found:
            found[name] = {'name': name, 'evidence_file': evidence, 'version': version}

    # package.json
    for pkg_path in workspace.rglob('package.json'):
        if _skip_path(pkg_path, workspace):
            continue
        try:
            data = json.loads(pkg_path.read_text(encoding='utf-8', errors='ignore'))
        except Exception:
            continue
        rel = str(pkg_path.relative_to(workspace)).replace('\\', '/')
        all_deps = {}
        all_deps.update(data.get('dependencies') or {})
        all_deps.update(data.get('devDependencies') or {})
        for pkg_key, friendly_name in _LINT_PACKAGE_PATTERNS:
            if pkg_key in all_deps:
                _register(friendly_name, rel, str(all_deps[pkg_key]))
        # npm scripts with 'lint'
        scripts = data.get('scripts') or {}
        for script_name, cmd in scripts.items():
            if 'eslint' in str(cmd).lower() and 'ESLint' not in found:
                _register('ESLint', rel)
            if 'prettier' in str(cmd).lower() and 'Prettier' not in found:
                _register('Prettier', rel)

    # requirements.txt / pyproject.toml
    for req_path in list(workspace.rglob('requirements*.txt')) + list(workspace.rglob('pyproject.toml')):
        if _skip_path(req_path, workspace):
            continue
        try:
            content = req_path.read_text(encoding='utf-8', errors='ignore').lower()
        except Exception:
            continue
        rel = str(req_path.relative_to(workspace)).replace('\\', '/')
        for pkg_key, friendly_name in _LINT_REQUIREMENTS_PATTERNS:
            if pkg_key in content:
                _register(friendly_name, rel)

    # Config files
    for config_name, tool_name in _LINT_CONFIG_FILES:
        for config_path in workspace.rglob(config_name):
            if _skip_path(config_path, workspace):
                continue
            rel = str(config_path.relative_to(workspace)).replace('\\', '/')
            _register(tool_name, rel)

    return list(found.values())


# ── WebSocket / realtime services ────────────────────────────────────────────

_WS_CONSUMER_PATTERNS = re.compile(
    r'(AsyncWebsocketConsumer|WebsocketConsumer|JsonWebsocketConsumer|'
    r'AsyncJsonWebsocketConsumer|StompWebSocketHandler|WebSocketHandler)',
    re.IGNORECASE,
)
_WS_FILE_NAMES = re.compile(r'consumer|counsumer|channel|socket|ws_|websocket', re.IGNORECASE)
_ASGI_PATTERNS = re.compile(r'URLRouter|ProtocolTypeRouter|AuthMiddlewareStack', re.IGNORECASE)


def detect_websocket_services(workspace: Path) -> list[dict[str, Any]]:
    """Detect WebSocket/realtime service files via class inheritance + file naming."""
    found: list[dict] = []
    seen: set[str] = set()

    for src_path in workspace.rglob('*.py'):
        if _skip_path(src_path, workspace):
            continue
        rel = str(src_path.relative_to(workspace)).replace('\\', '/')
        if rel in seen:
            continue
        try:
            content = src_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        is_consumer = bool(_WS_CONSUMER_PATTERNS.search(content))
        is_asgi = bool(_ASGI_PATTERNS.search(content))
        is_named = bool(_WS_FILE_NAMES.search(src_path.name))
        if is_consumer or (is_named and is_asgi):
            seen.add(rel)
            # Extract class names
            class_names = re.findall(r'class\s+(\w+)', content)
            found.append({
                'path': rel,
                'type': 'websocket_consumer',
                'classes': class_names[:4],
                'description': f'WebSocket consumer service ({src_path.name})',
            })

    return found


# ── Integration clients ──────────────────────────────────────────────────────

_INTEGRATION_IMPORTS = [
    ('requests', 'HTTP client (requests)'),
    ('httpx', 'Async HTTP client (httpx)'),
    ('aiohttp', 'Async HTTP client (aiohttp)'),
    ('boto3', 'AWS SDK (boto3)'),
    ('stripe', 'Stripe payments'),
    ('retell', 'Retell AI'),
    ('openai', 'OpenAI API'),
    ('anthropic', 'Anthropic API'),
    ('google.cloud', 'Google Cloud'),
    ('firebase_admin', 'Firebase Admin'),
    ('twilio', 'Twilio'),
    ('sendgrid', 'SendGrid'),
    ('celery', 'Celery task queue'),
    ('redis', 'Redis client'),
    ('pymongo', 'MongoDB client'),
    ('elasticsearch', 'Elasticsearch client'),
]

_INTEGRATION_FILE_SKIP = re.compile(
    r'test_|_test\.|conftest|migration|admin\.py|settings|__pycache__', re.IGNORECASE
)


def detect_integration_clients(workspace: Path) -> list[dict[str, Any]]:
    """Detect files that are integration clients (external HTTP + SDK callers)."""
    found: list[dict] = []
    seen: set[str] = set()

    for src_path in workspace.rglob('*.py'):
        if _skip_path(src_path, workspace):
            continue
        if _INTEGRATION_FILE_SKIP.search(src_path.name):
            continue
        rel = str(src_path.relative_to(workspace)).replace('\\', '/')
        if rel in seen:
            continue
        try:
            content = src_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        integrations: list[str] = []
        for import_marker, friendly in _INTEGRATION_IMPORTS:
            if re.search(rf'\b{re.escape(import_marker)}\b', content):
                integrations.append(friendly)
        if len(integrations) >= 2 or (integrations and _is_service_file(src_path)):
            seen.add(rel)
            found.append({
                'path': rel,
                'type': 'integration_client',
                'integrations': integrations,
                'description': f'Integration client: {", ".join(integrations[:3])}',
            })

    return found


# ── helpers ──────────────────────────────────────────────────────────────────

try:
    from agents.core.workspace import SKIP_DIRS as _SKIP_DIRS
except ImportError:
    _SKIP_DIRS = frozenset({
        'node_modules', '.git', '__pycache__', 'dist', 'build', '.venv', 'venv',
        'env', '.next', '.nuxt', 'coverage', '.nyc_output', 'htmlcov', 'data',
    })


def _skip_path(path: Path, workspace: Path) -> bool:
    try:
        parts = path.relative_to(workspace).parts
    except ValueError:
        return True
    return any(part in _SKIP_DIRS for part in parts)


def _is_service_file(path: Path) -> bool:
    name = path.stem.lower()
    return any(tok in name for tok in ('service', 'client', 'api', 'gateway', 'adapter', 'integration'))


def render_facts_block(label: str, items: list[dict], fields: list[str]) -> str:
    """Render a deterministic facts block for injection into LLM prompts."""
    if not items:
        return ''
    lines = [f'{label} ({len(items)} detected):']
    for item in items:
        values = [str(item.get(f) or '') for f in fields if item.get(f)]
        lines.append(f'  - {" | ".join(values)}')
    return '\n'.join(lines)
