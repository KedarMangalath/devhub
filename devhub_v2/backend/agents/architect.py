import json
import os

from agents.base import BaseAgent


class ArchitectAgent(BaseAgent):
    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="Software Architect",
            system_instruction=(
                "You are an expert software architect and technical design writer. "
                "You generate exhaustive, evidence-first project blueprints that work like an internal engineering wiki and a hand-written staff-level design document. "
                "Do not invent services, endpoints, schema, or workflows that are not supported by the supplied repository evidence. "
                "If information is incomplete, say that it was not clearly detected from the codebase. "
                "Return only valid JSON with no markdown wrappers."
            ),
            model=(ai_config or {}).get("model") or os.environ.get("DEVHUB_BLUEPRINT_MODEL", "gemini-3.1-pro-preview"),
            ai_config=ai_config,
        )

    def generate_blueprint(
        self,
        project_name: str,
        tech_stack: list,
        local_scan: str,
        readme: str = "",
        codebase_context: dict | None = None,
        exploration_report: dict | None = None,
        feature_summary: str = "",
        repo_map: str = "",
    ) -> dict:
        tech_joined = ", ".join(tech_stack) if tech_stack else "Not specified"
        context_json = json.dumps(codebase_context or {}, indent=2)[:36000]
        exploration_json = json.dumps(exploration_report or {}, indent=2)[:30000]

        prompt = f"""Analyze this project and generate a COMPLETE engineering blueprint as a single JSON object.
This document should feel like the internal wiki a new engineer can rely on to understand the entire project.

Project Name: {project_name}
Tech Stack: {tech_joined}

README Content:
{readme}

Structured Codebase Context:
{context_json}

Explorer Report:
{exploration_json}

Current Feature / Pipeline Context:
{feature_summary}

Repository Map:
{repo_map[:12000]}

Local Folder Scan:
{local_scan}

Return ONLY one JSON object with all keys below populated with project-specific content:
{{
  "project_summary": "Detailed overview of what the project is, who uses it, the product surface, and the core problems it solves.",
  "architecture_overview": "Detailed architecture explanation covering frontend/backend/services/data/external systems and how they fit together.",
  "mermaid_architecture": "graph TD ...",
  "mermaid_service_dependencies": "graph TD ...",
  "mermaid_erd": "erDiagram ...",
  "data_flow": "Detailed explanation of major user/data flows across the system.",
  "sequence_flows": [
    {{"title": "Flow title", "description": "Why this flow matters", "mermaid_sequence": "sequenceDiagram ...", "touchpoints": ["services, files, endpoints, jobs"]}}
  ],
  "tech_stack_details": [
    {{"tech": "Technology", "purpose": "What it does here", "why_chosen": "Why it fits", "version": "version or unknown", "category": "language|framework|database|tool|library"}}
  ],
  "services": [
    {{"name": "Service", "type": "frontend|backend|database|cache|queue|worker|proxy", "description": "Detailed responsibility summary", "port": "port or null", "tech": "main tech", "health_endpoint": "/health or null", "dependencies": ["service names"], "key_files": ["important files"]}}
  ],
  "api_endpoints": [
    {{"method": "GET|POST|PUT|DELETE|PATCH|unknown", "path": "/api/path", "description": "What it does", "request_body": "JSON example or null", "response": "JSON example or explanation", "auth_required": true, "curl_example": "curl example"}}
  ],
  "database_schema": [
    {{"table": "table_or_model", "description": "Purpose of this entity", "key_fields": [{{"name": "field", "type": "type", "constraints": "PK|FK|UNIQUE|NOT NULL", "description": "field purpose"}}], "relationships": "How it relates to other models", "indexes": ["important indexes"]}}
  ],
  "key_components": [
    {{"name": "Component", "file_path": "path/to/file", "purpose": "Why it exists", "complexity": "low|medium|high", "dependencies": ["dependencies"], "exports": "main exports", "lines_estimate": "approximate lines"}}
  ],
  "directory_guide": [
    {{"path": "folder/", "purpose": "What lives here", "key_files": ["file - description"], "pattern": "architecture pattern in this area"}}
  ],
  "repo_tree": "project-name/\\n|- src/\\n|  `- App.tsx",
  "repository_map": [
    {{"area": "frontend/", "description": "What this area owns", "important_files": ["file paths"], "relationships": ["connected areas"]}}
  ],
  "file_structure_visualizer": [
    {{"folder": "src/", "summary": "What this folder contributes", "files": [{{"path": "src/App.tsx", "role": "ui", "purpose": "What it does", "why": "Why it exists", "how": "How it fits into project behavior", "related_symbols": ["App"]}}]}}
  ],
  "change_guide": [
    {{"area": "UI changes", "where": ["src/..."], "notes": "Where to start and what to update together"}}
  ],
  "setup_steps": [
    {{"step": "Step title", "command": "command", "explanation": "why", "os_note": "optional platform note"}}
  ],
  "environment_variables": [
    {{"name": "VAR_NAME", "description": "What it controls", "required": true, "default": "default or null", "example": "value", "category": "api_key|database|config|feature_flag"}}
  ],
  "security_considerations": [
    {{"area": "Authentication", "description": "What exists and what to watch for", "severity": "high|medium|low"}}
  ],
  "performance_notes": [
    {{"area": "Caching", "description": "What exists / where bottlenecks may be", "impact": "high|medium|low"}}
  ],
  "testing_strategy": {{
    "unit": "Detailed unit testing approach",
    "integration": "Detailed integration testing approach",
    "e2e": "Detailed e2e testing approach",
    "coverage_target": "target or current expectation",
    "run_command": "how to run tests"
  }},
  "code_quality_standards": [
    {{"tool": "tool", "purpose": "what it enforces", "config_file": "config path"}}
  ],
  "common_workflows": [
    {{"title": "Workflow title", "steps": ["step 1", "step 2", "step 3"]}}
  ],
  "feature_inventory": [
    {{"title": "Feature title", "status": "backlog|development|testing|code_review|staging|done|unknown", "description": "What this feature covers", "implementation_notes": "How it shows up in the codebase or workflow"}}
  ],
  "sdlc_pipeline": {{
    "stages": [
      {{"name": "Backlog", "purpose": "what happens here", "entry_criteria": ["..."], "exit_criteria": ["..."]}}
    ],
    "approval_gates": ["approval expectations"],
    "ai_capabilities": ["how AI helps in this pipeline"],
    "team_workflow": "How work moves across the pipeline in this project"
  }},
  "integration_points": [
    {{"name": "Integration", "type": "internal|external", "description": "what it connects to", "evidence": ["files, endpoints, configs"], "failure_modes": ["things that break"]}}
  ],
  "faq": [
    {{"question": "Question", "answer": "Detailed answer with commands or paths where possible"}}
  ],
  "gotchas": [
    "Important non-obvious behavior or pitfall"
  ],
  "onboarding_checklist": [
    {{"task": "Task", "category": "environment|codebase|processes|tools|team", "estimated_time": "time", "why_important": "why it matters", "instructions": "how to do it"}}
  ],
  "key_concepts": [
    {{"concept": "Concept", "explanation": "Detailed explanation", "why_important": "why it matters", "related_code": "path", "related_concepts": ["related concepts"]}}
  ]
}}

Rules:
- This should be a complete project document, not a short summary.
- Make the design document genuinely detailed, comparable to a strong human-written architecture/design doc.
- The design document should include substantial detail for system architecture, key components, data flow, API surface, setup, onboarding, limitations, and future work.
- Prefer grounded specifics from the codebase over generic software phrasing.
- If a section is thin because evidence is limited, explicitly say what is unknown instead of filling it with boilerplate.
- Prefer concrete evidence from Structured Codebase Context and Explorer Report over README prose.
- Treat Structured Codebase Context, the repo tree, and explorer report as the source of truth.
- If a detail is not clearly evidenced, say so instead of guessing.
- Never invent files, folders, services, routes, entities, or dependencies that do not appear in the supplied repository evidence.
- Prefer empty arrays or explicit "not clearly detected" text over speculation.
- Cover the major frontend, backend, data, workflow, and onboarding surfaces of the project.
- For database_schema and mermaid_erd, focus EXCLUSIVELY on backend entity models or actual database tables. Strictly ignore frontend UI props, transient states, or DTOs unless the project lacks a backend entirely.
- Ensure the mermaid_erd includes ALL primary models and accurately maps their relationships, rather than summarizing a tiny subset.
- For Mermaid graph/flowchart output, quote node labels whenever they contain spaces, slashes, parentheses, or punctuation, for example `API["Backend API / Django"]`.
- For repo_tree, return a gitingest-style textual tree derived from the repository layout.
- For sequence_flows, include at least the most important user/application interactions you can ground in the codebase.
- For repository_map, turn the repo into a newcomer-friendly map of major areas and how they connect.
- For file_structure_visualizer, explain what important files are for, why they exist, and how they fit into the project.
- For change_guide, show a new engineer where to start when changing UI, APIs, data models, or runtime behavior.
- For feature_inventory and sdlc_pipeline, connect the tracked features/workflow with the actual project operating model when evidence exists.
- For faq and gotchas, optimize for a new engineer joining the team.
- Return only JSON.
"""

        try:
            result = self.generate(prompt=prompt)
            return self.parse_json(result)
        except Exception as exc:
            return self._fallback_blueprint(
                project_name=project_name,
                tech_stack=tech_stack,
                error=str(exc),
                codebase_context=codebase_context or {},
                exploration_report=exploration_report or {},
                feature_summary=feature_summary,
                repo_map=repo_map,
            )

    def _fallback_blueprint(
        self,
        project_name: str,
        tech_stack: list,
        error: str,
        codebase_context: dict,
        exploration_report: dict,
        feature_summary: str,
        repo_map: str,
    ) -> dict:
        important_files = codebase_context.get("important_files") or []
        directory_counts = codebase_context.get("directory_counts") or {}
        routes = codebase_context.get("routes") or []
        data_models = codebase_context.get("data_models") or []
        services = exploration_report.get("services") or []
        key_components = exploration_report.get("key_components") or []
        repo_map_entries = [
            {
                "area": f"{directory}/" if directory != "." else "Project Root",
                "description": f"Contains roughly {count} indexed files.",
                "important_files": [
                    file.get("path")
                    for file in important_files
                    if str(file.get("path", "")).startswith(f"{directory}/")
                ][:6],
                "relationships": [],
            }
            for directory, count in list(sorted(directory_counts.items(), key=lambda item: (-item[1], item[0])))[:12]
        ]

        return {
            "project_summary": (
                f"{project_name} was scanned from the local codebase, but full AI blueprint generation failed. "
                f"The fallback blueprint is grounded in {len(important_files)} important files and {len(directory_counts)} top-level directories."
            ),
            "architecture_overview": (
                f"Detailed AI architecture generation failed with: {error}. "
                "This fallback blueprint uses the cached repository context and should still help a new engineer navigate the codebase."
            ),
            "mermaid_architecture": "graph TD\n  App[Application] --> Runtime[Runtime]\n  Runtime --> Data[(Data Layer)]",
            "mermaid_service_dependencies": "graph TD\n  UI[UI] --> API[Application Layer]\n  API --> Data[(Data Layer)]",
            "mermaid_erd": "",
            "data_flow": "Not clearly detected from the fallback analysis. Review routes, important files, and runtime entrypoints.",
            "sequence_flows": [],
            "tech_stack_details": [],
            "services": [],
            "api_endpoints": [],
            "database_schema": [],
            "key_components": [],
            "directory_guide": [
                {
                    "path": entry["area"],
                    "purpose": entry["description"],
                    "key_files": entry["important_files"],
                    "pattern": "Not clearly detected from the fallback analysis",
                }
                for entry in repo_map_entries
            ],
            "repository_map": repo_map_entries,
            "setup_steps": [],
            "environment_variables": [],
            "security_considerations": [],
            "performance_notes": [],
            "testing_strategy": {},
            "code_quality_standards": [],
            "common_workflows": [],
            "feature_inventory": [],
            "sdlc_pipeline": {},
            "integration_points": [],
            "faq": [],
            "gotchas": [f"AI blueprint generation failed: {error}"],
            "onboarding_checklist": [],
            "key_concepts": [],
        }
