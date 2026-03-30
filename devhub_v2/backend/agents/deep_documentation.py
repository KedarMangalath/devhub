"""Multi-pass deep documentation agent.

Each Blueprint section gets its own focused LLM call with domain-specific
file content so the model can produce genuinely detailed output instead of
spreading attention across 30+ JSON keys in a single massive prompt.
"""

from __future__ import annotations

import json
import os
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

    def __init__(self, ai_config: dict | None = None):
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

    # ── helpers ──────────────────────────────────────────────────────────

    def _safe_parse_json(self, text: str) -> dict:
        """Parse JSON from LLM response, stripping markdown wrappers if present."""
        cleaned = text.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return {'_error': f'Failed to parse JSON: {text[:200]}'}


    def _file_context_block(self, workspace_path: Path, files: list[dict]) -> str:
        """Build a context block with full file content for the LLM prompt."""
        blocks: list[str] = []
        for item in files[:12]:
            rel_path = item.get('path', '')
            content = read_deep_file_content(workspace_path, rel_path, limit=8000)
            if not content:
                continue
            summary = item.get('summary', '')
            blocks.append(
                f"=== FILE: {rel_path} ===\n"
                f"Summary: {summary}\n"
                f"Content ({len(content)} chars):\n"
                f"{content}\n"
                f"=== END FILE ==="
            )
        return "\n\n".join(blocks)

    def _base_context(self, cache: dict) -> str:
        """Compact overview context included in every section prompt."""
        lines = [
            f"Project file count: {cache.get('file_count', 0)}",
            f"Top directories: {json.dumps(cache.get('directory_counts', {}), indent=None)}",
        ]
        routes = cache.get('routes', [])
        if routes:
            lines.append(f"Detected routes: {json.dumps(routes[:30])}")
        data_models = cache.get('data_models', [])
        if data_models:
            lines.append(f"Detected data models: {json.dumps(data_models[:30])}")
        readme = str(cache.get('readme_excerpt', ''))[:1200]
        if readme.strip():
            lines.append(f"README excerpt: {readme}")
        return "\n".join(lines)

    # ── section generators ──────────────────────────────────────────────

    def _important_file_context(self, cache: dict, workspace_path: Path, limit: int = 10) -> str:
        return self._file_context_block(workspace_path, list((cache.get('important_files') or [])[:limit]))

    def generate_overview(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        file_context = self._important_file_context(cache, workspace_path, limit=10)
        base_context = self._base_context(cache)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce a DETAILED overview and architecture summary.

{base_context}

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
- If something is unclear from the scanned files, say so explicitly.
- Mermaid diagrams should reflect the actual repo shape, not a generic stack template.
- For Mermaid graph/flowchart output, quote node labels whenever they contain spaces, slashes, parentheses, or punctuation, for example `API["Backend API / Django"]`.
"""
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    def generate_services(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        files = select_files_for_section(cache, 'services', workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce a DETAILED services & components documentation.

{base_context}

SOURCE FILES (read carefully, these are FULL file contents):
{file_context}

Return ONLY this JSON:
{{
  "services": [
    {{
      "name": "Service or module name",
      "type": "frontend|backend|database|cache|queue|worker|proxy",
      "description": "Detailed multi-sentence description of what this service does, how it works, what patterns it uses. Include specific function names, class names, and behavioral details.",
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
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    def generate_api(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        if cache.get('api_reference'):
            return {
                'api_endpoints': list(cache.get('api_reference') or []),
            }

        files = select_files_for_section(cache, 'api', workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce a DETAILED API reference.

{base_context}

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
- Request body and response examples should use realistic field names from the actual code.
- Each description should be 2-5 sentences explaining the full behavior.
- Include query parameters, path parameters, and headers where visible.
- For curl examples, use localhost:8000 as the base URL.
- If response shape is not clear, describe what you can infer.
"""
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    def generate_database(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        if cache.get('database_schema'):
            return {
                'database_schema': cache.get('database_schema') or [],
                'mermaid_erd': cache.get('database_mermaid_erd') or '',
            }

        files = select_files_for_section(cache, 'database', workspace_path)
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
        files = select_files_for_section(cache, 'workflows', workspace_path)
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

    def generate_setup(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        files = select_files_for_section(cache, 'setup', workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce DETAILED setup, environment, and onboarding documentation.

{base_context}

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

Rules:
- Setup steps should form a complete, working path from clone to running app.
- Environment variables should be extracted from actual code (os.environ, process.env, .env files).
- Every setup command should be tested and realistic for this specific project.
- Onboarding checklist should cover everything from environment setup to understanding the codebase.
- Include OS-specific notes where relevant (Windows vs Linux/Mac).
"""
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    def generate_quality(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        files = select_files_for_section(cache, 'quality', workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce DETAILED code quality, security, performance, and testing documentation.

{base_context}

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
- Testing strategy should reference actual test files and frameworks found in the code.
- Code quality tools should be detected from config files (pyproject.toml, .eslintrc, etc).
"""
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

    def generate_knowledge(self, project_name: str, cache: dict, workspace_path: Path) -> dict:
        files = select_files_for_section(cache, 'knowledge', workspace_path)
        file_context = self._file_context_block(workspace_path, files)
        base_context = self._base_context(cache)

        prompt = f"""Analyze the following codebase for the project `{project_name}` and produce DETAILED knowledge base documentation including key concepts, FAQ, and gotchas.

{base_context}

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
- Key concepts should cover the unique architectural patterns, not generic software concepts.
- FAQ should be questions a real new team member would ask after their first week.
- Gotchas should be genuinely surprising behaviors found by reading the code carefully.
- Each answer should include enough detail that the reader doesn't need to look at the code.
- Include at least 5 key concepts, 6 FAQ entries, and 4 gotchas.
"""
        return self._safe_parse_json(self.generate(prompt=prompt, response_schema=True))

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
        return generator(project_name, cache, workspace_path)

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
        blueprint = dict(existing_blueprint or {})
        total = len(SECTION_ORDER)
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
            try:
                section_data = self.generate_section(
                    section_key,
                    project_name,
                    cache,
                    workspace_path,
                    existing_blueprint=blueprint,
                )
                # Merge into blueprint
                for key, value in section_data.items():
                    blueprint[key] = value
            except Exception as exc:
                section_data = {'_error': str(exc)}

            yield {
                'section_key': section_key,
                'section_label': SECTION_LABELS.get(section_key, section_key),
                'section_data': section_data,
                'progress_pct': int(((index + 1) / total) * 100),
                'status': 'completed' if '_error' not in section_data else 'failed',
                'total_sections': total,
                'completed_sections': index + 1,
                'blueprint_snapshot': blueprint,
            }
