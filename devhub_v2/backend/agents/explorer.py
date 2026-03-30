import json
import os

from agents.base import BaseAgent


class CodebaseExplorerAgent(BaseAgent):
    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="Codebase Explorer",
            system_instruction="""You are a high-discipline codebase exploration agent.
Your job is to inspect structured repository evidence and produce grounded, low-hallucination analysis.
Only make claims that are directly supported by the provided repository evidence.
If a detail is uncertain, say 'Not clearly detected from the scanned codebase'.
Return ONLY valid JSON with no markdown.""",
            model=(ai_config or {}).get("model") or os.environ.get("DEVHUB_BLUEPRINT_MODEL", "gemini-3.1-pro-preview"),
            ai_config=ai_config,
        )

    def explore_codebase(
        self,
        project_name: str,
        tech_stack: list[str],
        codebase_context: dict,
    ) -> dict:
        prompt = f"""Explore this project codebase and produce a grounded architecture analysis.

Project: {project_name}
Declared tech stack: {", ".join(tech_stack or []) or "Not specified"}

Codebase context JSON:
{json.dumps(codebase_context, indent=2)[:60000]}

Return ONLY this JSON shape:
{{
  "system_shape": "A factual summary of the repository structure and likely application shape.",
  "services": [
    {{
      "name": "service name",
      "type": "frontend|backend|database|worker|config",
      "evidence": ["specific files or routes that support the claim"],
      "responsibilities": ["what it appears to do"],
      "key_files": ["path/to/file"]
    }}
  ],
  "entrypoints": [
    {{
      "path": "path/to/file",
      "kind": "runtime|route|config|ui|data",
      "reason": "Why this file matters"
    }}
  ],
  "api_surface": [
    {{
      "path": "/api/example",
      "method": "GET|POST|unknown",
      "evidence_file": "path/to/file",
      "description": "Grounded explanation or 'Not clearly detected from the scanned codebase'"
    }}
  ],
  "data_models": [
    {{
      "name": "ModelName",
      "evidence_file": "path/to/file",
      "description": "What it appears to represent"
    }}
  ],
  "key_components": [
    {{
      "file_path": "path/to/file",
      "summary": "Grounded summary",
      "role": "ui|logic|routing|config|data|unknown"
    }}
  ],
  "developer_workflows": [
    "Grounded workflow guidance based on the scanned files"
  ],
  "unknowns": [
    "Important things that were not clearly detectable"
  ]
}}

Rules:
- Prefer omission over guessing.
- Cite concrete files in evidence.
- Keep services and key components limited to the highest-signal files.
- Treat README claims as lower confidence than actual code files.
"""
        return self.parse_json(self.generate(prompt=prompt, response_schema=True))
