"""Multi-pass deep documentation agent.

Each Blueprint section gets its own focused LLM call with domain-specific
file content so the model can produce genuinely detailed output instead of
spreading attention across 30+ JSON keys in a single massive prompt.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Generator

from agents.base import BaseAgent
from agents.memory import (
    read_deep_file_content,
    select_files_for_section,
)


SECTION_ORDER = [
    'services',
    'api',
    'database',
    'workflows',
    'setup',
    'quality',
    'knowledge',
]

SECTION_LABELS = {
    'overview': 'Overview',
    'repository': 'Repository',
    'design_doc': 'Design Doc',
    'services': 'Services & Components',
    'api': 'API Reference',
    'database': 'Database Schema',
    'workflows': 'Workflows & Sequences',
    'setup': 'Setup & Environment',
    'quality': 'Quality & Security',
    'knowledge': 'Knowledge Base',
}


class DeepDocumentationAgent(BaseAgent):
    """Generates each Blueprint section via a dedicated, focused LLM call."""

    def __init__(self, ai_config: dict | None = None, observer=None):
        super().__init__(
            role="Deep Documentation Specialist",
            system_instruction=(
                "You are a meticulous software documentation specialist. "
                "You produce rich, detailed, evidence-grounded documentation for exactly the section requested. "
                "Cite concrete file paths, function names, class names, routes, and code patterns. "
                "If information is not clearly visible in the provided source files, say so explicitly. "
                "Return ONLY valid JSON with no markdown wrappers."
            ),
            model=(ai_config or {}).get("model") or os.environ.get("DEVHUB_BLUEPRINT_MODEL", "gemini-3.1-pro-preview"),
            ai_config=ai_config,
        )
        self.observer = observer
        self._current_section: str = ''

    # ── helpers ──────────────────────────────────────────────────────────

    def _extract_json_candidate(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        if cleaned[:1] not in {'{', '['}:
            match = re.search(r'(\{.*\}|\[.*\])', cleaned, flags=re.DOTALL)
            if match:
                cleaned = match.group(1).strip()
        return cleaned

    def _safe_parse_json(self, text: str) -> dict:
        """Parse JSON from LLM response, stripping wrappers and leading prose."""
        cleaned = self._extract_json_candidate(text)
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return {'_error': f'Failed to parse JSON: {text[:200]}'}

    def _section_retry_budget(self) -> int:
        try:
            return max(0, int(str(os.environ.get('DEVHUB_BLUEPRINT_SECTION_RETRIES', '1')).strip()))
        except (TypeError, ValueError):
            return 1

    def _fallback_section_model(self) -> str:
        return str(self.ai_config.get('fallback_model') or os.environ.get('DEVHUB_GEMINI_FALLBACK_MODEL') or '').strip()

    def _retry_instruction(self, error_text: str) -> str:
        base = (
            "Return exactly one valid JSON object that matches the requested schema. "
            "Do not include commentary, markdown fences, headings, or trailing notes."
        )
        if 'parse json' in error_text.lower():
            return base + " The previous response was invalid JSON."
        return base + " The previous attempt failed due to a transient generation error."

    def _should_retry_section_error(self, error_text: str) -> bool:
        lowered = str(error_text or '').lower()
        if not lowered:
            return False
        return any(
            token in lowered
            for token in (
                'failed to parse json',
                'request failed',
                'request timed out',
                'resource_exhausted',
                'temporarily unavailable',
                'deadline exceeded',
                'quota',
                'timeout',
                '502',
                '503',
                '504',
                '429',
            )
        )

    def _quality_score(self, section_key: str, section_data: dict) -> tuple[int, list[str]]:
        """Score section output quality 0-100. Returns (score, weak_areas)."""
        weak: list[str] = []
        score = 100

        if section_key == 'services':
            services = section_data.get('services') or []
            if len(services) < 3:
                weak.append(f'only {len(services)} service entries — expected distinct modules not just frontend/backend')
                score -= 50
            short = [s for s in services if len(str(s.get('description') or '')) < 60]
            if short:
                weak.append(f'{len(short)} service(s) have very short descriptions (under 60 chars)')
                score -= 20

        elif section_key == 'api':
            endpoints = section_data.get('api_endpoints') or []
            no_fields = [e for e in endpoints if not e.get('request_fields') and e.get('method') not in {'GET', 'DELETE'}]
            no_status = [e for e in endpoints if not e.get('status_codes')]
            if endpoints and len(no_fields) > len(endpoints) * 0.6:
                weak.append(f'{len(no_fields)}/{len(endpoints)} non-GET endpoints still have no request_fields')
                score -= 30
            if endpoints and len(no_status) > len(endpoints) * 0.7:
                weak.append(f'{len(no_status)}/{len(endpoints)} endpoints have no status_codes')
                score -= 20

        elif section_key == 'quality':
            standards = section_data.get('code_quality_standards') or []
            styling_only = standards and all(
                any(t in str(s.get('tool') or '').lower() for t in ('tailwind', 'bootstrap', 'css', 'sass', 'less', 'styled'))
                for s in standards
            )
            if styling_only or not standards:
                weak.append('code_quality_standards lists only styling tools, not linting/testing/type-checking')
                score -= 40
            testing = section_data.get('testing_strategy') or {}
            unit_desc = str(testing.get('unit') or '')
            if not unit_desc or 'not clearly' in unit_desc.lower() or len(unit_desc) < 40:
                weak.append('testing_strategy is vague — no actual test files or frameworks cited')
                score -= 25

        elif section_key == 'knowledge':
            concepts = section_data.get('key_concepts') or []
            faq = section_data.get('faq') or []
            if len(concepts) < 4:
                weak.append(f'only {len(concepts)} key_concepts — need at least 5')
                score -= 30
            if len(faq) < 4:
                weak.append(f'only {len(faq)} FAQ entries — need at least 6')
                score -= 20

        return max(0, score), weak

    def _second_pass_improve(
        self,
        section_key: str,
        current: dict,
        weak: list[str],
        project_name: str,
        cache: dict,
        workspace_path: Path,
    ) -> dict:
        """Targeted second pass: ask LLM to fix specific weak areas in current output."""
        files = select_files_for_section(cache, section_key, workspace_path)
        file_context = self._file_context_block(workspace_path, files)

        issues_text = '\n'.join(f'- {w}' for w in weak)
        current_json = json.dumps(current, indent=2)[:8000]

        prompt = f"""The following is a partially complete Blueprint section `{section_key}` for the project `{project_name}`.
It has these quality problems that must be fixed:
{issues_text}

CURRENT OUTPUT (improve this, do not start from scratch):
{current_json}

SOURCE FILES to help fix the issues:
{file_context}

Return the COMPLETE improved JSON for section `{section_key}`, fixing every listed problem.
Keep all correct data from the current output. Only improve the weak areas.
Return ONLY valid JSON with the same top-level structure as the current output."""

        improved = self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))
        if isinstance(improved, dict) and not improved.get('_error'):
            # Merge: prefer improved fields, keep existing fields not in improved
            merged = dict(current)
            for k, v in improved.items():
                if v:  # only overwrite with non-empty improvements
                    merged[k] = v
            return merged
        return current

    def _quota_backoff_seconds(self, error_text: str, attempt_index: int) -> float:
        lowered = str(error_text or '').lower()
        if any(t in lowered for t in ('429', 'resource_exhausted', 'quota')):
            # Exponential back-off: 15s, 30s, 60s — respect Gemini per-minute quotas
            return min(60.0, 15.0 * (2 ** attempt_index))
        return 0.0


    def _file_context_block(self, workspace_path: Path, files: list[dict]) -> str:
        """Build a context block with full file content for the LLM prompt."""
        from concurrent.futures import ThreadPoolExecutor

        if self.observer and files:
            self.observer.thinking(
                self._current_section,
                f'Reading {len(files)} files: {", ".join(f.get("path","") for f in files[:6])}'
                + (f' … +{len(files)-6} more' if len(files) > 6 else '')
            )

        def _read_one(item: dict) -> str | None:
            rel_path = item.get('path', '')
            content = read_deep_file_content(workspace_path, rel_path, limit=40000)
            if not content:
                return None
            if self.observer:
                self.observer.file_access(self._current_section, rel_path, len(content))
            summary = item.get('summary', '')
            return (
                f"=== FILE: {rel_path} ===\n"
                f"Summary: {summary}\n"
                f"Content ({len(content)} chars):\n"
                f"{content}\n"
                f"=== END FILE ==="
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(_read_one, files))
        return "\n\n".join(r for r in results if r)

    def _base_context(self, cache: dict) -> str:
        """Compact overview context included in every section prompt."""
        lines = [
            f"Project file count: {cache.get('file_count', 0)}",
            f"Top directories: {json.dumps(cache.get('directory_counts', {}), indent=None)}",
        ]
        routes = cache.get('routes', [])
        if routes:
            lines.append(f"Detected routes: {json.dumps(routes)}")
        data_models = cache.get('data_models', [])
        if data_models:
            lines.append(f"Detected data models: {json.dumps(data_models)}")
        db_model_names = cache.get('database_model_names', [])
        if db_model_names:
            lines.append(f"Extracted database model names: {json.dumps(db_model_names)}")
        api_count = len(cache.get('api_reference') or [])
        if api_count:
            lines.append(f"Total API endpoints extracted: {api_count}")
        readme = str(cache.get('readme_excerpt', ''))[:1200]
        if readme.strip():
            lines.append(f"README excerpt: {readme}")
        return "\n".join(lines)

    # ── section generators ──────────────────────────────────────────────

    def _important_file_context(self, cache: dict, workspace_path: Path) -> str:
        return self._file_context_block(workspace_path, list(cache.get('important_files') or []))

    def generate_overview(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        from agents.fact_extractors import render_facts_block
        file_context = self._important_file_context(cache, workspace_path)
        base_context = self._base_context(cache)

        css_block = render_facts_block(
            'CSS_FRAMEWORKS_DETECTED',
            cache.get('detected_css_frameworks') or [],
            ['name', 'evidence_file', 'version'],
        )
        ws_block = render_facts_block(
            'WEBSOCKET_SERVICES_DETECTED',
            cache.get('detected_websocket_services') or [],
            ['path', 'classes'],
        )
        integration_block = render_facts_block(
            'INTEGRATION_CLIENTS_DETECTED',
            cache.get('detected_integration_clients') or [],
            ['path', 'integrations'],
        )
        facts_block = '\n'.join(filter(None, [css_block, ws_block, integration_block]))

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce a DETAILED overview and architecture summary.

{base_context}

DETERMINISTIC FACTS (extracted from the codebase — these are ground truth, you MUST include all of them):
{facts_block if facts_block else '(none pre-extracted)'}

SOURCE FILES (read carefully, these are FULL file contents):
{file_context}

Return ONLY this JSON:
{{
  "project_summary": "Detailed overview of what the project is, who it serves, and the main product surface.",
  "architecture_overview": "Detailed architecture explanation covering frontend/backend/services/data layers and how they fit together.",
  "mermaid_architecture": "graph TD\\n  A[Frontend] --> B[Backend]",
  "mermaid_service_dependencies": "graph TD\\n  A[Service A] --> B[Service B]",
  "data_flow": "Detailed explanation of the most important request/data flow through the system.",
  "tech_stack_details": [
    {{
      "tech": "Technology name",
      "purpose": "What it does in this repo",
      "why_chosen": "Why it fits this codebase",
      "version": "detected version or unknown",
      "category": "language|framework|database|tool|library"
    }}
  ]
}}

Rules:
- Keep this grounded in the supplied codebase evidence.
- Prefer concrete repo-specific details over generic software phrasing.
- MANDATORY: Every item in CSS_FRAMEWORKS_DETECTED MUST appear as its own entry in tech_stack_details with category="library". Do NOT merge them or omit any.
- MANDATORY: If multiple CSS frameworks detected, mention all of them by name in architecture_overview.
- MANDATORY: Every item in WEBSOCKET_SERVICES_DETECTED must be mentioned in architecture_overview as a realtime/WebSocket layer.
- Mermaid diagrams should reflect the actual repo shape, not a generic stack template.
- For Mermaid graph/flowchart output, quote node labels whenever they contain spaces, slashes, parentheses, or punctuation, for example `API["Backend API / Django"]`.
"""
        result = self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))
        # Validator: ensure all detected CSS frameworks appear in tech_stack_details
        css_frameworks = cache.get('detected_css_frameworks') or []
        if css_frameworks and isinstance(result.get('tech_stack_details'), list):
            existing_techs = {str(t.get('tech') or '').lower() for t in result['tech_stack_details']}
            for fw in css_frameworks:
                fw_name = str(fw.get('name') or '')
                if fw_name and fw_name.lower() not in existing_techs:
                    result['tech_stack_details'].append({
                        'tech': fw_name,
                        'purpose': 'CSS/styling framework used in the frontend',
                        'why_chosen': 'Detected from package.json or source imports',
                        'version': str(fw.get('version') or 'unknown'),
                        'category': 'library',
                    })
        return result

    def _extract_port_facts(self, workspace_path: Path) -> str:
        """Scan package.json scripts + vite/django config for actual port numbers."""
        import json as _json
        facts: list[str] = []
        for pkg_path in list(workspace_path.rglob('package.json'))[:6]:
            try:
                data = _json.loads(pkg_path.read_text(encoding='utf-8', errors='ignore'))
                scripts = data.get('scripts') or {}
                for name, cmd in scripts.items():
                    if any(p in str(cmd) for p in ('--port', 'PORT=', '-p ')):
                        facts.append(f"package.json({pkg_path.relative_to(workspace_path)}) script '{name}': {cmd}")
            except Exception:
                pass
        for cfg in list(workspace_path.rglob('vite.config.*'))[:4]:
            try:
                content = cfg.read_text(encoding='utf-8', errors='ignore')
                import re
                for m in re.finditer(r'port\s*:\s*(\d+)', content):
                    facts.append(f"{cfg.relative_to(workspace_path)}: port {m.group(1)}")
            except Exception:
                pass
        return '\n'.join(facts) if facts else ''

    def _select_and_observe(self, section_key: str, cache: dict, workspace_path: Path) -> list[dict]:
        """Select files for a section and emit a thinking event listing them."""
        if self.observer:
            self.observer.thinking(section_key, f'Selecting relevant files for {section_key} section…')
        files = select_files_for_section(cache, section_key, workspace_path)
        if self.observer and files:
            paths = [f.get('path', '') for f in files]
            preview = ', '.join(paths[:8]) + (f' … +{len(paths)-8} more' if len(paths) > 8 else '')
            self.observer.thinking(section_key, f'Selected {len(files)} files → {preview}')
        return files

    def _llm_and_observe(self, section_key: str, prompt: str) -> dict:
        """Run LLM call with before/after thinking events."""
        model = self.model or (self.ai_config or {}).get('model', '?')
        if self.observer:
            self.observer.thinking(section_key, f'Calling LLM ({model}) to generate {section_key}…')
            self.observer.llm_call(section_key, str(model))
        result = self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))
        if self.observer:
            size = len(str(result))
            self.observer.thinking(section_key, f'LLM response received ({size} chars), parsing output…')
        return result

    def generate_services(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        from agents.fact_extractors import render_facts_block
        files = self._select_and_observe('services', cache, workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)
        port_facts = self._extract_port_facts(workspace_path)
        port_section = f"\nEXTRACTED PORT CONFIGURATION (use these exact values for port fields, do not guess):\n{port_facts}\n" if port_facts else ""

        ws_block = render_facts_block(
            'WEBSOCKET_SERVICES (MANDATORY — each must get its own services entry)',
            cache.get('detected_websocket_services') or [],
            ['path', 'classes', 'description'],
        )
        integration_block = render_facts_block(
            'INTEGRATION_CLIENTS (MANDATORY — each must get its own services entry)',
            cache.get('detected_integration_clients') or [],
            ['path', 'integrations'],
        )
        mandatory_block = '\n'.join(filter(None, [ws_block, integration_block]))

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce DETAILED services & architecture documentation.

{base_context}
{port_section}
MANDATORY SERVICE ENTRIES (detected deterministically — EVERY item below must appear as its own entry in the services array):
{mandatory_block if mandatory_block else '(none pre-detected)'}

SOURCE FILES (read carefully, these are FULL file contents):
{file_context}

IMPORTANT — capture ALL of the following, not just top-level processes:
1. Runtime services (server processes, workers, schedulers, daemons)
2. Service-layer modules (files named *service*, *services*, *utils*, *helpers*, *builder*, *processor*, *manager*, *client*, *gateway*, *adapter*)
3. Any file in a `services/` directory
4. Integration clients (API clients, external service wrappers, SDK adapters)

Do NOT collapse multiple distinct modules into one generic "backend" or "frontend" entry.
Each logical subsystem or service file gets its own entry.

Return ONLY this JSON:
{{
  "services": [
    {{
      "name": "Exact module or service name",
      "type": "frontend|backend|database|cache|queue|worker|proxy|service-module|integration-client",
      "description": "Detailed multi-sentence description. Cite specific function names, class names, and behavioral details from the source files.",
      "port": "port number or null",
      "tech": "primary technology",
      "health_endpoint": "health check path or null",
      "dependencies": ["concrete dependency names from the code"],
      "key_files": ["file paths with brief role explanation"]
    }}
  ],
  "key_components": [
    {{
      "name": "Component or class name",
      "file_path": "exact file path",
      "purpose": "Detailed multi-sentence explanation of what this component does, why it exists, and how it fits into the architecture",
      "complexity": "low|medium|high",
      "dependencies": ["imports and dependencies"],
      "exports": "main exports or public interface",
      "lines_estimate": "approximate line count"
    }}
  ],
  "integration_points": [
    {{
      "name": "Integration name",
      "type": "internal|external",
      "description": "Detailed explanation of what connects, how data flows, what protocol is used",
      "evidence": ["concrete file paths and function names"],
      "failure_modes": ["specific things that could break and why"]
    }}
  ]
}}

Rules:
- Read every file thoroughly. Cite specific class names, function names, decorators, and patterns.
- Each service description should be 3-8 sentences, not one-liners.
- Each key_component purpose should explain WHY it exists, not just WHAT it is.
- Prefer concrete evidence over generic descriptions.
- If a detail is not in the files, say "Not clearly detected from the scanned source files."
"""
        result = self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))
        # Enforce: seed any missing WS/integration services the LLM dropped
        services = result.get('services') or []
        existing_paths = {
            str(s.get('key_files') or [''])[0].split(':')[0].lower()
            for s in services
        }
        existing_text = ' '.join(str(s) for s in services).lower()

        for ws in (cache.get('detected_websocket_services') or []):
            ws_path = str(ws.get('path') or '')
            stem = Path(ws_path).stem.lower()
            if stem not in existing_text and ws_path.lower() not in existing_text:
                services.append({
                    'name': f'WebSocket Consumer ({Path(ws_path).stem})',
                    'type': 'backend',
                    'description': ws.get('description', f'WebSocket consumer at {ws_path}'),
                    'port': None,
                    'tech': 'Django Channels',
                    'health_endpoint': None,
                    'dependencies': [],
                    'key_files': [ws_path],
                })

        for ic in (cache.get('detected_integration_clients') or []):
            ic_path = str(ic.get('path') or '')
            stem = Path(ic_path).stem.lower()
            if stem not in existing_text and ic_path.lower() not in existing_text:
                integrations = ic.get('integrations') or []
                services.append({
                    'name': f'Integration Client ({Path(ic_path).stem})',
                    'type': 'integration-client',
                    'description': ic.get('description', f'Integration client: {", ".join(integrations[:3])}'),
                    'port': None,
                    'tech': ', '.join(integrations[:2]) if integrations else 'HTTP client',
                    'health_endpoint': None,
                    'dependencies': integrations,
                    'key_files': [ic_path],
                })

        result['services'] = services
        return result

    def _find_serializer_files(self, workspace_path: Path, cache: dict) -> list[dict]:
        """Find serializer/schema files from cache manifest — universal across stacks."""
        from agents.memory import _summary_pool
        all_items = _summary_pool(cache)
        results: list[dict] = []
        seen: set[str] = set()
        _serializer_stems = (
            'serializer', 'serializers', 'schema', 'schemas',
            'validator', 'validators', 'form', 'forms', 'dto', 'dtos',
        )
        for item in all_items:
            path = str(item.get('path') or '')
            if not path or path in seen:
                continue
            name_lower = Path(path).stem.lower()
            if any(name_lower == s or name_lower.endswith('_' + s) or name_lower.startswith(s + '_')
                   for s in _serializer_stems):
                seen.add(path)
                results.append(item)
        return results

    def _enrich_api_endpoints(
        self, api_ref: list[dict], workspace_path: Path, project_name: str, cache: dict
    ) -> list[dict]:
        """Enrich write endpoints that have no request fields with serializer data.

        Only processes POST/PUT/PATCH endpoints that AST extraction missed.
        GET/DELETE endpoints and already-enriched endpoints are returned unchanged.
        """
        serializer_files = self._find_serializer_files(workspace_path, cache)
        if not serializer_files:
            return api_ref

        serializer_context = self._file_context_block(workspace_path, serializer_files)
        if not serializer_context.strip():
            return api_ref

        # Only enrich write endpoints that still have no request_fields — skip already-enriched
        to_enrich = [
            ep for ep in api_ref
            if ep.get('method') in {'POST', 'PUT', 'PATCH'}
            and not (ep.get('request_fields') or ep.get('request_body'))
        ][:40]  # hard cap at 40 to keep prompt size manageable

        if not to_enrich:
            return api_ref

        if self.observer:
            self.observer.thinking(
                self._current_section,
                f'Enriching {len(to_enrich)} write endpoints with serializer field shapes'
            )

        # Summarise only the endpoints that need enrichment
        endpoint_lines = []
        for ep in to_enrich:
            method = ep.get('method') or 'POST'
            path = ep.get('path') or ''
            summary = ep.get('summary') or ep.get('description') or ''
            auth = ep.get('auth_required', True)
            endpoint_lines.append(f"- [{method}] {path}  auth={auth}  {summary[:120]}")
        endpoints_block = '\n'.join(endpoint_lines)

        prompt = f"""You are enriching an API reference for the project `{project_name}`.

Below is the complete list of endpoints extracted by static analysis:
{endpoints_block}

SERIALIZER / SCHEMA FILES (these define the exact request and response field shapes):
{serializer_context}

For EACH endpoint, output an enriched entry. Use the serializer files to determine:
- `request_body`: the fields the client must send (field name, type, required/optional)
- `response`: the fields the server returns
- `description`: expand any generic description with concrete detail from the serializer

Return ONLY this JSON:
{{
  "api_endpoints": [
    {{
      "method": "GET|POST|PUT|PATCH|DELETE",
      "path": "/exact/path",
      "description": "Detailed description including what serializer/schema is used and what it validates",
      "request_body": "JSON object showing request fields with types, or null for read-only endpoints",
      "response": "JSON object showing response fields and their types",
      "auth_required": true,
      "curl_example": "curl -X METHOD localhost:8000/path -H 'Authorization: Bearer TOKEN' -d '{{...}}'"
    }}
  ]
}}

Rules:
- Include ALL endpoints from the list above — do not drop any.
- Where a serializer clearly maps to an endpoint (by name or path), use its fields exactly.
- Where no serializer maps, write `request_body` and `response` based on the endpoint name/path.
- curl_example should include realistic field values from the serializer.
- Keep descriptions factual — cite serializer class names when relevant.
"""
        result = self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))
        enriched = result.get('api_endpoints') if isinstance(result, dict) else None
        if not enriched:
            return api_ref
        # Merge enriched entries back into original api_ref by (method, path) key
        enriched_map = {(e.get('method', ''), e.get('path', '')): e for e in enriched}
        merged = []
        for ep in api_ref:
            key = (ep.get('method', ''), ep.get('path', ''))
            if key in enriched_map:
                # Overlay enrichment on top of original (original has auth, group, source etc)
                merged.append({**ep, **{k: v for k, v in enriched_map[key].items() if v}})
            else:
                merged.append(ep)
        return merged

    def _raw_urls_context(self, workspace_path: Path, meta: dict) -> str:
        """Read raw content of all urls.py files when AST extraction produced nothing."""
        urls_files: list[str] = meta.get('urls_files_found') or []
        if not urls_files:
            return ''
        blocks: list[str] = []
        for rel_path in urls_files:
            file_path = workspace_path / rel_path
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')[:20000]
            except Exception:
                continue
            blocks.append(
                f"=== URL FILE: {rel_path} ===\n{content}\n=== END URL FILE ==="
            )
        return '\n\n'.join(blocks)

    def generate_api(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        self._current_section = 'api'
        meta = cache.get('api_extraction_meta') or {}
        api_ref = cache.get('api_reference') or []

        # Confidence check: if many URL files exist but very few endpoints, don't trust extraction
        urls_count = len(meta.get('urls_files_found') or [])
        extraction_suspiciously_low = api_ref and urls_count > 1 and len(api_ref) < 5

        if api_ref and not extraction_suspiciously_low:
            if self.observer:
                self.observer.thinking('api', f'Enriching {len(api_ref)} AST-extracted endpoints with serializer data')
                self.observer.extraction('api', 'api_reference_catalog', len(api_ref),
                                         f'deterministic extraction from {urls_count} url file(s)')
            enriched = self._enrich_api_endpoints(api_ref, workspace_path, project_name, cache)
            return {'api_endpoints': enriched}

        if self.observer:
            reason = 'suspiciously low count' if extraction_suspiciously_low else 'no cached api_reference'
            self.observer.thinking('api', f'Falling back to LLM analysis ({reason}) — selecting files')

        files = self._select_and_observe('api', cache, workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        # When AST extraction found 0 endpoints but urls.py files exist, pass
        # their raw content so the LLM reads real route patterns instead of inventing.
        extraction_ok = meta.get('extraction_ok', True)
        raw_urls_block = ''
        extraction_warning = ''
        if not extraction_ok:
            raw_urls_block = self._raw_urls_context(workspace_path, meta)
            extraction_warning = (
                'WARNING: Automated route extraction found 0 endpoints. '
                'The URL files below contain the real route patterns. '
                'Read them EXACTLY — do not invent routes not present in these files.'
            )

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce a DETAILED API reference.

{base_context}

{extraction_warning}

{('RAW URL PATTERN FILES (source of truth for all routes):\n' + raw_urls_block) if raw_urls_block else ''}

SOURCE FILES (read carefully, these are FULL file contents):
{file_context}

Return ONLY this JSON:
{{
  "api_endpoints": [
    {{
      "method": "GET|POST|PUT|DELETE|PATCH",
      "path": "/api/exact/path",
      "description": "Detailed multi-sentence description of what this endpoint does, what business logic it triggers, what validations it performs, and any side effects.",
      "request_body": "Example JSON request body with realistic field values, or null for GET requests",
      "response": "Example JSON response showing the actual shape returned by the code",
      "auth_required": true,
      "curl_example": "A working curl command example with headers and sample data"
    }}
  ]
}}

Rules:
- Trace each endpoint from its URL pattern through to its view/handler function.
- Document every endpoint you can find in the source files, not just the obvious ones.
- If RAW URL PATTERN FILES are provided above, use them as the definitive list of routes — do NOT add routes not present there.
- Request body and response examples should use realistic field names from the actual code.
- Each description should be 2-5 sentences explaining the full behavior.
- Include query parameters, path parameters, and headers where visible.
- For curl examples, use localhost:8000 as the base URL.
- If a route exists in the URL files but its handler is unclear, document the path and method and say the handler was not clearly detected.
"""
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    def generate_database(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        if cache.get('database_schema'):
            return {
                'database_schema': cache.get('database_schema') or [],
                'mermaid_erd': cache.get('database_mermaid_erd') or '',
            }

        files = self._select_and_observe('database', cache, workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce a DETAILED database schema and data model documentation.

{base_context}

SOURCE FILES (read carefully, these are FULL file contents):
{file_context}

Return ONLY this JSON:
{{
  "database_schema": [
    {{
      "table": "Model or table name",
      "description": "Detailed multi-sentence description of what this entity represents, when records are created/updated, and its role in the domain model",
      "key_fields": [
        {{
          "name": "field_name",
          "type": "CharField(max_length=255)|IntegerField|ForeignKey|etc",
          "constraints": "PK|FK(OtherModel)|UNIQUE|NOT NULL|blank=True|default=X",
          "description": "What this field represents and how it is used in the application"
        }}
      ],
      "relationships": "Detailed description of foreign keys, many-to-many, one-to-many relationships with other models",
      "indexes": ["index descriptions if visible"]
    }}
  ],
  "mermaid_erd": "erDiagram\\n  Model1 ||--o{{ Model2 : has\\n  ..."
}}

Rules:
- Read model class definitions carefully. Document EVERY field, not just primary keys.
- Include field types with their exact Django/ORM parameters (max_length, default, null, blank, etc).
- For relationships, name both sides and the cardinality (one-to-many, many-to-many).
- The ERD mermaid diagram should show all models and their relationships.
- Each table description should be 2-4 sentences.
- If using Django, look for models.Model subclasses. If using TypeScript, look for interfaces/types.
"""
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    def generate_workflows(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        files = self._select_and_observe('workflows', cache, workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce DETAILED workflow and sequence flow documentation.

{base_context}

SOURCE FILES (read carefully, these are FULL file contents):
{file_context}

Return ONLY this JSON:
{{
  "sequence_flows": [
    {{
      "title": "Flow name (e.g., 'User Authentication Flow', 'Feature Implementation Pipeline')",
      "description": "Detailed multi-sentence description of what triggers this flow, who participates, and what the outcome is",
      "mermaid_sequence": "sequenceDiagram\\n  participant User\\n  participant Frontend\\n  participant Backend\\n  User->>Frontend: action\\n  ...",
      "touchpoints": ["specific files, services, endpoints involved"]
    }}
  ],
  "common_workflows": [
    {{
      "title": "Workflow name (e.g., 'Adding a New Feature', 'Deploying Changes')",
      "steps": [
        "Step 1: Detailed instruction with specific file paths and commands",
        "Step 2: ..."
      ]
    }}
  ]
}}

  Rules:
  - Trace actual code paths for the sequence flows. Follow function calls across files.
  - Include at least 3-5 meaningful sequence flows covering the main user/system interactions.
  - Each workflow step should include concrete commands, file paths, or UI actions.
  - Mermaid sequence diagrams should have realistic participant names from the actual code.
  - Common workflows should be things a developer, operator, or maintainer would actually need to do in this repository.
  - Only document a workflow as active when the initiating code path and handling code path both exist in the provided files.
  - Do not invent realtime collaboration, sockets, or background loops unless the frontend caller and backend handler are both present.
  - Prefer the most central repo-specific flows visible in the code, whether they are product flows, data-processing flows, admin flows, background-job flows, setup flows, testing flows, or documentation flows.
  - Avoid duplicate participants, placeholder actors, and speculative future-state flows.
  - Do not bias toward IDE, workspace, or code-generation workflows unless the provided repository actually contains those capabilities.
  """
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    def _confirmed_setup_facts(self, cache: dict, workspace_path: Path) -> str:
        """Build a grounded facts block for setup generation — only confirmed file/var names."""
        env_var_names: list[str] = list(cache.get('env_var_names') or [])

        # Files that physically exist on disk — only these may be referenced in commands
        setup_signals = [
            '.env.example', '.env.sample', '.env.template',
            'Makefile', 'makefile', 'justfile',
            'docker-compose.yml', 'docker-compose.yaml',
            'Dockerfile', 'dockerfile',
            'requirements.txt', 'requirements-dev.txt',
            'pyproject.toml', 'setup.py',
            'package.json', 'yarn.lock', 'pnpm-lock.yaml',
            'README.md', 'readme.md', 'CONTRIBUTING.md',
        ]
        confirmed_files: list[str] = []
        for name in setup_signals:
            for candidate in workspace_path.rglob(name):
                parts = set(candidate.relative_to(workspace_path).parts)
                from agents.workspace import SKIP_DIRS
                if parts & SKIP_DIRS:
                    continue
                rel = str(candidate.relative_to(workspace_path)).replace('\\', '/')
                if rel not in confirmed_files:
                    confirmed_files.append(rel)

        lines = ['CONFIRMED SETUP FILES (only these may be referenced in commands):']
        if confirmed_files:
            for f in confirmed_files:
                lines.append(f'  - {f}')
        else:
            lines.append('  (none detected)')

        lines.append('')
        lines.append('CONFIRMED ENV VARS (grep of codebase — only these may appear in environment_variables):')
        if env_var_names:
            for name in env_var_names:
                lines.append(f'  - {name}')
        else:
            lines.append('  (none detected)')

        return '\n'.join(lines)

    def generate_setup(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        files = self._select_and_observe('setup', cache, workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)
        confirmed_facts = self._confirmed_setup_facts(cache, workspace_path)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce DETAILED setup, environment, and onboarding documentation.

{base_context}

{confirmed_facts}

SOURCE FILES (read carefully, these are FULL file contents):
{file_context}

Return ONLY this JSON:
{{
  "setup_steps": [
    {{
      "step": "Step title (e.g., 'Install Python dependencies')",
      "command": "exact terminal command to run",
      "explanation": "Why this step is needed and what it does. 2-3 sentences.",
      "os_note": "Platform-specific notes (e.g., 'On Windows, use python instead of python3')"
    }}
  ],
  "environment_variables": [
    {{
      "name": "VARIABLE_NAME",
      "description": "Detailed description of what this variable controls and where it is used in the code",
      "required": true,
      "default": "default value or null",
      "example": "realistic example value",
      "category": "api_key|database|config|feature_flag|runtime"
    }}
  ],
  "onboarding_checklist": [
    {{
      "task": "Concrete onboarding task",
      "category": "environment|codebase|processes|tools|team",
      "estimated_time": "realistic time estimate",
      "why_important": "Why a new developer needs to do this",
      "instructions": "Step-by-step instructions with commands and file paths"
    }}
  ]
}}

STRICT RULES — violations cause hallucination:
- ONLY reference files that appear in CONFIRMED SETUP FILES above. If `.env.example` is NOT listed, do NOT suggest `cp .env.example .env` or any similar command.
- ONLY document environment variables that appear in CONFIRMED ENV VARS above. Do not invent variable names.
- Setup steps must form a complete, working path from clone to running app using only confirmed files.
- If a setup file (e.g., .env.example) does not exist, tell the user to CREATE the file manually instead of copying it.
- Include OS-specific notes where relevant (Windows vs Linux/Mac).
"""
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    def generate_quality(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        from agents.fact_extractors import render_facts_block
        files = self._select_and_observe('quality', cache, workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        lint_block = render_facts_block(
            'LINT_TOOLS_DETECTED',
            cache.get('detected_lint_tools') or [],
            ['name', 'evidence_file', 'version'],
        )
        test_block = render_facts_block(
            'TEST_FRAMEWORKS_DETECTED',
            cache.get('detected_test_frameworks') or [],
            ['name', 'evidence_file', 'version'],
        )
        facts_block = '\n'.join(filter(None, [lint_block, test_block]))

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce DETAILED code quality, security, performance, and testing documentation.

{base_context}

DETERMINISTIC FACTS (extracted from the codebase — these are ground truth):
{facts_block if facts_block else '(none pre-extracted)'}

SOURCE FILES (read carefully, these are FULL file contents):
{file_context}

Return ONLY this JSON:
{{
  "security_considerations": [
    {{
      "area": "Specific security area (e.g., 'API Authentication', 'CSRF Protection', 'Input Validation')",
      "description": "Detailed description of what security measures exist, what files implement them, and what risks remain. 3-5 sentences.",
      "severity": "high|medium|low"
    }}
  ],
  "performance_notes": [
    {{
      "area": "Specific performance area (e.g., 'Database Query Optimization', 'File I/O in Indexing')",
      "description": "Detailed description of potential bottlenecks, current optimizations, and recommendations. 2-4 sentences with file references.",
      "impact": "high|medium|low"
    }}
  ],
  "testing_strategy": {{
    "unit": "Detailed description of the unit testing approach, frameworks used, test file locations, and patterns followed",
    "integration": "Description of integration test approach with specific examples from the code",
    "e2e": "End-to-end testing approach or 'Not clearly detected from the scanned codebase'",
    "coverage_target": "Coverage target or current state as detected from config files",
    "run_command": "Exact command to run tests"
  }},
  "code_quality_standards": [
    {{
      "tool": "Tool name (e.g., 'ESLint', 'Black', 'mypy')",
      "purpose": "What it enforces and how it is configured",
      "config_file": "path to config file"
    }}
  ]
}}

Rules:
- Look for actual security patterns: CSRF decorators, authentication checks, input validation, SQL injection prevention.
- Performance notes should reference specific code patterns (N+1 queries, large file reads, blocking I/O).
- MANDATORY: Every tool in LINT_TOOLS_DETECTED MUST appear in code_quality_standards with its evidence_file as config_file.
- MANDATORY: Every framework in TEST_FRAMEWORKS_DETECTED MUST be mentioned in the testing_strategy fields.
  Document the specific test files found (test_pw.py, conftest.py, etc.) — do not say "Not detected" if TEST_FRAMEWORKS_DETECTED has entries.
- Do NOT list UI styling libraries (Tailwind, Bootstrap, CSS-in-JS) as code_quality_standards. Those belong in tech_stack_details.
  code_quality_standards is for linting, testing, type checking, and security scanning tools only.
- Avoid generic entries. Every item must cite a specific file or pattern found in the source.
"""
        result = self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))
        # Post-process: strip styling tools regardless of what the LLM returns
        _STYLING_TOOLS = {'tailwind', 'bootstrap', 'sass', 'less', 'scss', 'css-in-js', 'styled-components', 'emotion'}
        standards = result.get('code_quality_standards') or []
        result['code_quality_standards'] = [
            s for s in standards
            if not any(t in str(s.get('tool') or '').lower() for t in _STYLING_TOOLS)
        ]
        # Enforce: missing lint tools get added as stubs so validator can catch them
        existing_tools = {str(s.get('tool') or '').lower() for s in result['code_quality_standards']}
        for tool in (cache.get('detected_lint_tools') or []):
            name = str(tool.get('name') or '')
            if name and name.lower() not in existing_tools:
                result['code_quality_standards'].append({
                    'tool': name,
                    'purpose': f'Detected from {tool.get("evidence_file", "config files")}',
                    'config_file': str(tool.get('evidence_file') or ''),
                })
                existing_tools.add(name.lower())
        # Enforce: testing_strategy must mention all detected test frameworks
        test_frameworks = cache.get('detected_test_frameworks') or []
        if test_frameworks:
            testing = result.get('testing_strategy') or {}
            for key in ('unit', 'integration', 'e2e'):
                val = str(testing.get(key) or '')
                if val.lower().startswith('not clearly') or not val:
                    for fw in test_frameworks:
                        fw_name = str(fw.get('name') or '')
                        ev = str(fw.get('evidence_file') or '')
                        if fw_name.lower() in ('playwright', 'cypress', 'selenium') and key == 'e2e':
                            testing[key] = f'{fw_name} detected ({ev})'
                        elif fw_name.lower() in ('pytest', 'jest', 'vitest', 'mocha') and key == 'unit':
                            testing[key] = f'{fw_name} detected ({ev})'
            result['testing_strategy'] = testing
        return result

    def generate_knowledge(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        files = self._select_and_observe('knowledge', cache, workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        # Inject project documentation files directly
        instruction_files = cache.get('instruction_files') or []
        docs_block = ''
        if instruction_files:
            doc_lines = ['PROJECT DOCUMENTATION FILES (read carefully — these explain design decisions and workflows):']
            for item in instruction_files:
                path = item.get('path') or ''
                content = (item.get('content') or '')[:3000]
                if path and content:
                    doc_lines.append(f'\n=== {path} ===\n{content}\n=== END {path} ===')
            docs_block = '\n'.join(doc_lines)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce DETAILED knowledge base documentation including key concepts, FAQ, and gotchas.

{base_context}

{docs_block}

SOURCE FILES (read carefully, these are FULL file contents):
{file_context}

Return ONLY this JSON:
{{
  "key_concepts": [
    {{
      "concept": "Concept name (e.g., 'Request Lifecycle', 'Module Boundaries', 'Background Job Flow')",
      "explanation": "Detailed 3-6 sentence explanation of what this concept means in this codebase, how it works, and what code implements it",
      "why_important": "Why a new engineer needs to understand this to be productive",
      "related_code": "primary file path implementing this concept",
      "related_concepts": ["related concept names"]
    }}
  ],
  "faq": [
    {{
      "question": "A realistic question a new engineer would ask (e.g., 'How do I add a new API endpoint?')",
      "answer": "Detailed answer with specific file paths, commands, and step-by-step guidance. 3-8 sentences."
    }}
  ],
  "gotchas": [
    "Specific non-obvious behavior or pitfall with file references (e.g., 'A configuration file in one folder can silently override defaults defined elsewhere in the repo, so check load order before changing shared settings.')"
  ]
}}

Rules:
- If PROJECT DOCUMENTATION FILES are provided above, extract key concepts and gotchas DIRECTLY from them — do not ignore them.
- Key concepts should cover the unique architectural patterns, not generic software concepts.
- FAQ should be questions a real new team member would ask after their first week.
- Gotchas should be genuinely surprising behaviors found by reading the code carefully.
- Each answer should include enough detail that the reader doesn't need to look at the code.
- Include at least 5 key concepts, 6 FAQ entries, and 4 gotchas.
"""
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    # ── post-generation validators ──────────────────────────────────────

    def _validate_file_paths(self, section_data: dict, workspace_path: Path) -> dict:
        """Walk all string values that look like relative file paths.
        Replace paths that do not exist with a 'not confirmed in workspace' marker
        so hallucinated file references are visible without crashing consumers.
        Also scans free-text strings (steps, gotchas) for embedded path tokens.
        """
        import re
        PATH_LIKE = re.compile(r'^[\w\-./]+\.\w{1,8}$')
        PATH_KEYS = {'file_path', 'config_file', 'related_code', 'source_path'}
        # Regex to find path-like tokens embedded in free text strings
        EMBEDDED_PATH = re.compile(r'\b([\w\-./]+/[\w\-./]+\.\w{1,8})\b')

        def _path_exists(token: str) -> bool:
            """Try multiple root prefixes before declaring a path missing."""
            if (workspace_path / token).exists():
                return True
            # Try common subdirectory prefixes for monorepo layouts
            for prefix in ('backend', 'frontend', 'src', 'app', 'server', 'client'):
                if (workspace_path / prefix / token).exists():
                    return True
            # Strip a leading top-level dir (e.g. "remo/models/x.py" → try "backend/remo/models/x.py")
            parts = token.split('/', 1)
            if len(parts) == 2:
                for prefix in ('backend', 'frontend', 'src', 'app', 'server', 'client'):
                    if (workspace_path / prefix / token).exists():
                        return True
            return False

        def _check(value: object) -> object:
            if isinstance(value, str) and PATH_LIKE.match(value) and '/' in value:
                if not value.startswith(('http', 'null', 'unknown', 'not clearly')):
                    if not _path_exists(value):
                        return f'{value} (not confirmed in workspace)'
            return value

        def _check_embedded(text: str) -> str:
            """Replace unconfirmed path tokens embedded in free text."""
            def _replace(m: re.Match) -> str:
                token = m.group(1)
                if token.startswith(('http', 'null', 'unknown')):
                    return token
                if not _path_exists(token):
                    return f'{token} (not confirmed)'
                return token
            return EMBEDDED_PATH.sub(_replace, text)

        def _walk(obj: object, key: str = '') -> object:
            if isinstance(obj, dict):
                return {k: _walk(v, k) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_walk(item, key) for item in obj]
            if isinstance(obj, str):
                if key in PATH_KEYS:
                    return _check(obj)
                # Scan free-text fields for embedded path references
                if key in {'steps', 'gotchas', 'touchpoints', 'answer', 'explanation', 'why_important'}:
                    return _check_embedded(obj)
            return obj

        return _walk(section_data)  # type: ignore[return-value]

    def _validate_setup_commands(self, section_data: dict, workspace_path: Path) -> dict:
        """Flag setup commands that reference files not present in the workspace."""
        import re
        steps = section_data.get('setup_steps')
        if not isinstance(steps, list):
            return section_data

        FILE_REF = re.compile(r'(?:cp|cat|source|mv|touch|nano|vim|code)\s+([\w./\-]+)')
        validated: list[dict] = []
        for step in steps:
            if not isinstance(step, dict):
                validated.append(step)
                continue
            cmd = str(step.get('command') or '')
            warnings: list[str] = []
            for match in FILE_REF.finditer(cmd):
                ref = match.group(1)
                if ref.startswith('-') or ref.startswith('$'):
                    continue
                if not (workspace_path / ref).exists():
                    warnings.append(f"'{ref}' not found in workspace")
            if warnings:
                step = dict(step)
                step['_warning'] = 'References file(s) not confirmed in workspace: ' + ', '.join(warnings)
            validated.append(step)

        section_data = dict(section_data)
        section_data['setup_steps'] = validated
        return section_data

    def _validate_api_endpoints(self, section_data: dict, workspace_path: Path) -> dict:
        """Spot-check that claimed endpoint paths appear in at least one urls.py.
        Flags low-confidence endpoints rather than removing them.
        """
        endpoints = section_data.get('api_endpoints')
        if not isinstance(endpoints, list):
            return section_data

        # Collect raw content of all urls.py files
        urls_content_parts: list[str] = []
        for urls_file in workspace_path.rglob('urls.py'):
            parts = set(urls_file.parts)
            skip = {'node_modules', 'dist', 'build', '.git', '__pycache__', 'venv', '.venv'}
            if parts & skip:
                continue
            try:
                urls_content_parts.append(urls_file.read_text(encoding='utf-8', errors='ignore'))
            except Exception:
                continue
        all_urls_content = '\n'.join(urls_content_parts)

        if not all_urls_content:
            return section_data

        validated: list[dict] = []
        for ep in endpoints:
            if not isinstance(ep, dict):
                validated.append(ep)
                continue
            path = str(ep.get('path') or '')
            # Extract meaningful path segments (skip empty, 'api', UUIDs, path params)
            segments = [
                seg for seg in path.strip('/').split('/')
                if seg and seg != 'api' and not seg.startswith('<') and not seg.startswith('{')
                and len(seg) < 40  # exclude UUIDs
            ]
            if segments:
                # At least one significant segment must appear in a urls.py
                confirmed = any(seg in all_urls_content for seg in segments[-2:])
                if not confirmed:
                    ep = dict(ep)
                    ep['_confidence'] = 'low — path not confirmed in urls.py files'
            validated.append(ep)

        section_data = dict(section_data)
        section_data['api_endpoints'] = validated
        return section_data

    def _run_validators(self, section_key: str, section_data: dict, workspace_path: Path, cache: dict | None = None) -> dict:
        """Run the appropriate post-generation validator for a section."""
        try:
            section_data = self._validate_file_paths(section_data, workspace_path)
            if section_key == 'setup':
                section_data = self._validate_setup_commands(section_data, workspace_path)
            if section_key == 'api':
                section_data = self._validate_api_endpoints(section_data, workspace_path)
            if section_key == 'overview' and cache:
                section_data = self._validate_overview_css(section_data, cache)
            if section_key == 'services' and cache:
                section_data = self._validate_services_completeness(section_data, cache)
        except Exception:
            pass  # validators must never break generation
        return section_data

    def _validate_overview_css(self, section_data: dict, cache: dict) -> dict:
        """Ensure all detected CSS frameworks appear in tech_stack_details."""
        css_frameworks = cache.get('detected_css_frameworks') or []
        if not css_frameworks:
            return section_data
        tech_stack = section_data.get('tech_stack_details')
        if not isinstance(tech_stack, list):
            return section_data
        existing = {str(t.get('tech') or '').lower() for t in tech_stack}
        for fw in css_frameworks:
            name = str(fw.get('name') or '')
            if name and name.lower() not in existing:
                tech_stack.append({
                    'tech': name,
                    'purpose': 'CSS/styling framework',
                    'why_chosen': f'Detected from {fw.get("evidence_file", "package.json")}',
                    'version': str(fw.get('version') or 'unknown'),
                    'category': 'library',
                })
                existing.add(name.lower())
        section_data = dict(section_data)
        section_data['tech_stack_details'] = tech_stack
        return section_data

    def _validate_services_completeness(self, section_data: dict, cache: dict) -> dict:
        """Ensure all detected WS/integration services appear in the services list."""
        services = list(section_data.get('services') or [])
        existing_text = ' '.join(str(s) for s in services).lower()
        for ws in (cache.get('detected_websocket_services') or []):
            ws_path = str(ws.get('path') or '')
            if Path(ws_path).stem.lower() not in existing_text:
                services.append({
                    'name': f'WebSocket Consumer ({Path(ws_path).stem})',
                    'type': 'backend',
                    'description': ws.get('description', f'WebSocket/realtime service at {ws_path}'),
                    'port': None, 'tech': 'WebSocket / Django Channels',
                    'health_endpoint': None, 'dependencies': [], 'key_files': [ws_path],
                })
        for ic in (cache.get('detected_integration_clients') or []):
            ic_path = str(ic.get('path') or '')
            if Path(ic_path).stem.lower() not in existing_text:
                integrations = ic.get('integrations') or []
                services.append({
                    'name': f'Integration Client ({Path(ic_path).stem})',
                    'type': 'integration-client',
                    'description': ic.get('description', f'External API client: {", ".join(integrations[:3])}'),
                    'port': None, 'tech': ', '.join(integrations[:2]) or 'HTTP',
                    'health_endpoint': None, 'dependencies': integrations, 'key_files': [ic_path],
                })
        section_data = dict(section_data)
        section_data['services'] = services
        return section_data

    # ── orchestrator ────────────────────────────────────────────────────

    def generate_section(
        self,
        section_key: str,
        project_name: str,
        cache: dict,
        workspace_path: Path,
        existing_blueprint: dict | None = None,
    ) -> dict[str, Any]:
        generators = {
            'overview': self.generate_overview,
            'services': self.generate_services,
            'api': self.generate_api,
            'database': self.generate_database,
            'workflows': self.generate_workflows,
            'setup': self.generate_setup,
            'quality': self.generate_quality,
            'knowledge': self.generate_knowledge,
        }
        generator = generators.get(section_key)
        if not generator:
            raise ValueError(f'Unsupported Blueprint section: {section_key}')

        original_model = self.model
        original_instruction = self.system_instruction
        fallback_model = self._fallback_section_model()
        attempt_budget = 1 + self._section_retry_budget()
        last_error = ''
        try:
            for attempt_index in range(attempt_budget):
                retrying = attempt_index > 0
                attempt_model = original_model
                if fallback_model and fallback_model != original_model and attempt_index == attempt_budget - 1:
                    attempt_model = fallback_model

                self.model = attempt_model
                self.ai_config['model'] = attempt_model
                self.system_instruction = original_instruction
                if retrying:
                    self.system_instruction = f"{original_instruction}\n{self._retry_instruction(last_error)}"
                    if self.observer:
                        self.observer.thinking(
                            section_key,
                            f"Retrying {SECTION_LABELS.get(section_key, section_key)} attempt {attempt_index + 1}/{attempt_budget} with model {attempt_model}",
                        )

                try:
                    result = generator(project_name, cache, workspace_path)
                except Exception as exc:
                    error_text = str(exc).strip()
                    if self._should_retry_section_error(error_text) and attempt_index < attempt_budget - 1:
                        last_error = error_text
                        backoff = self._quota_backoff_seconds(error_text, attempt_index)
                        if backoff > 0:
                            import time as _time_mod
                            _time_mod.sleep(backoff)
                        continue
                    raise
                error_text = str(result.get('_error') or '').strip() if isinstance(result, dict) else ''
                if error_text and self._should_retry_section_error(error_text) and attempt_index < attempt_budget - 1:
                    last_error = error_text
                    backoff = self._quota_backoff_seconds(error_text, attempt_index)
                    if backoff > 0:
                        import time as _time_mod
                        _time_mod.sleep(backoff)
                    continue
                # Quality gate: second-pass improvement for low-quality sections
                if isinstance(result, dict) and not result.get('_error') and attempt_index == 0:
                    q_score, weak = self._quality_score(section_key, result)
                    if q_score < 60 and weak:
                        if self.observer:
                            self.observer.thinking(section_key, f'Quality score {q_score}/100 — running second-pass improvement: {"; ".join(weak)}')
                        result = self._second_pass_improve(section_key, result, weak, project_name, cache, workspace_path)
                return result
            return {'_error': last_error or f'{section_key} generation failed'}
        finally:
            self.model = original_model
            self.ai_config['model'] = original_model
            self.system_instruction = original_instruction

    def generate_all_sections(
        self,
        project_name: str,
        cache: dict,
        workspace_path: Path,
        existing_blueprint: dict | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Generate all 7 sections sequentially, yielding progress events.

        Each yield is a dict:
        {
            "section_key": "services",
            "section_data": { ... merged data for this section ... },
            "progress_pct": 14,
            "status": "completed",
            "total_sections": 7,
            "completed_sections": 1,
        }
        """
        import time as _time
        blueprint = dict(existing_blueprint or {})
        total = len(SECTION_ORDER)
        for index, section_key in enumerate(SECTION_ORDER):
            self._current_section = section_key
            if self.observer:
                self.observer.thinking(section_key, f'Starting section {index + 1}/{total}: {SECTION_LABELS.get(section_key, section_key)}')
            yield {
                'section_key': section_key,
                'section_label': SECTION_LABELS.get(section_key, section_key),
                'section_data': {},
                'progress_pct': int((index / total) * 100),
                'status': 'started',
                'total_sections': total,
                'completed_sections': index,
                'blueprint_snapshot': blueprint,
            }
            _t0 = _time.monotonic()
            try:
                section_data = self.generate_section(
                    section_key,
                    project_name,
                    cache,
                    workspace_path,
                    existing_blueprint=blueprint,
                )
                if isinstance(section_data, dict) and section_data.get('_error'):
                    raise ValueError(str(section_data.get('_error')))
                # Post-generation validation: flag hallucinated paths/commands/endpoints
                section_data = self._run_validators(section_key, section_data, workspace_path, cache=cache)
                # Merge into blueprint
                for key, value in section_data.items():
                    blueprint[key] = value
                _status = 'completed'
            except Exception as exc:
                section_data = {'_error': str(exc)}
                _status = 'failed'

            if self.observer:
                self.observer.section_done(section_key, _time.monotonic() - _t0, _status)

            yield {
                'section_key': section_key,
                'section_label': SECTION_LABELS.get(section_key, section_key),
                'section_data': section_data,
                'progress_pct': int(((index + 1) / total) * 100),
                'status': _status,
                'total_sections': total,
                'completed_sections': index + 1,
                'blueprint_snapshot': blueprint,
                'agent_events': self.observer.events_for_section(section_key) if self.observer else [],
            }

    async def generate_all_sections_async(
        self,
        project_name: str,
        cache: dict,
        workspace_path: Path,
        existing_blueprint: dict | None = None,
    ):
        """Async version of generate_all_sections. Runs independent sections in parallel.

        Yields the same event dicts as the sync version but sections complete as soon
        as they're ready rather than strictly in order.
        """
        import asyncio
        import time as _time

        blueprint = dict(existing_blueprint or {})
        total = len(SECTION_ORDER)

        # Emit started events for all sections immediately
        for index, section_key in enumerate(SECTION_ORDER):
            yield {
                'section_key': section_key,
                'section_label': SECTION_LABELS.get(section_key, section_key),
                'section_data': {},
                'progress_pct': int((index / total) * 100),
                'status': 'started',
                'total_sections': total,
                'completed_sections': index,
                'blueprint_snapshot': blueprint,
            }

        def _run_section(section_key: str, idx: int) -> dict:
            t0 = _time.monotonic()
            try:
                self._current_section = section_key
                data = self.generate_section(section_key, project_name, cache, workspace_path, existing_blueprint=blueprint)
                if isinstance(data, dict) and data.get('_error'):
                    raise ValueError(str(data.get('_error')))
                data = self._run_validators(section_key, data, workspace_path, cache=cache)
                status = 'completed'
            except Exception as exc:
                data = {'_error': str(exc)}
                status = 'failed'
            if self.observer:
                self.observer.section_done(section_key, _time.monotonic() - t0, status)
            return {
                'section_key': section_key,
                'section_label': SECTION_LABELS.get(section_key, section_key),
                'section_data': data,
                'progress_pct': int(((idx + 1) / total) * 100),
                'status': status,
                'total_sections': total,
                'completed_sections': idx + 1,
                'blueprint_snapshot': blueprint,
                'agent_events': self.observer.events_for_section(section_key) if self.observer else [],
            }

        loop = asyncio.get_event_loop()
        futures = {
            loop.run_in_executor(None, _run_section, sk, idx)
            for idx, sk in enumerate(SECTION_ORDER)
        }
        # Yield results as they complete
        completed = 0
        for coro in asyncio.as_completed(futures):
            event = await coro
            section_data = event.get('section_data') or {}
            for key, value in section_data.items():
                if key != '_error':
                    blueprint[key] = value
            event['blueprint_snapshot'] = blueprint
            completed += 1
            event['completed_sections'] = completed
            yield event
