import json

from agents.base import BaseAgent


class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            role="Implementation Planner",
            system_instruction="""You are a senior staff engineer planning code changes for an autonomous coding system.
You receive a full project context pack including project memory, feature specs, recent changes, and a file inventory.
Your job is to identify which files matter, what must stay consistent, and what success looks like before coding starts.
Return ONLY valid JSON with no markdown.""",
        )

    def create_plan(
        self,
        project_name: str,
        request_title: str,
        request_text: str,
        project_memory: str,
        file_inventory: str,
        blueprint_summary: str,
        supporting_context: str,
    ) -> dict:
        prompt = f"""Create an implementation plan for this change request.

Project: {project_name}
Request Title: {request_title}
Request: {request_text}

Project Memory:
{project_memory}

Blueprint Summary:
{blueprint_summary}

Supporting Context:
{supporting_context}

File Inventory:
{file_inventory}

Return ONLY a JSON object with this exact structure:
{{
  "objective": "One paragraph describing the end result",
  "relevant_files": ["path/to/file1", "path/to/file2"],
  "new_files": ["path/to/new-file"],
  "implementation_steps": [
    "Concrete step 1",
    "Concrete step 2"
  ],
  "consistency_requirements": [
    "Keep X aligned with Y",
    "Update UI + logic + docs where relevant"
  ],
  "risks": [
    "What could regress or break"
  ],
  "validation_commands": [
    "Safe command to verify the change"
  ],
  "acceptance_checks": [
    "Specific thing the finished code should satisfy"
  ],
  "memory_updates": [
    "Important durable fact to remember for future edits"
  ]
}}

Rules:
- Prefer the smallest file set that still keeps the app consistent.
- If a request changes UI behavior, include related styles, scripts/components, and docs when needed.
- If there are existing relevant files, prefer modifying them over inventing parallel structure.
- Keep the existing runtime and project scaffold intact unless the request explicitly asks for a migration.
- For modern app stacks, avoid introducing duplicate top-level HTML/CSS/JS alongside an existing framework structure.
- Keep relevant_files limited to the highest-signal files.
"""
        result = self.generate(prompt)
        return self.parse_json(result)
