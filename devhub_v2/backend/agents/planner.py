import json

from agents.base import BaseAgent, describe_image_attachments


class PlannerAgent(BaseAgent):
    BASE_SYSTEM_INSTRUCTION = """You are a senior staff engineer planning code changes for an autonomous coding system.
You receive a full project context pack including project memory, feature specs, recent changes, and a file inventory.
Your job is to identify which files matter, what must stay consistent, and what success looks like before coding starts.
Prefer the smallest coherent implementation that fully satisfies the request.
Return ONLY valid JSON with no markdown."""

    def __init__(self, ai_config: dict | None = None, customization_instruction: str = ""):
        system_instruction = self.BASE_SYSTEM_INSTRUCTION
        if customization_instruction.strip():
            system_instruction = f"{system_instruction}\n\n{customization_instruction.strip()}"
        super().__init__(
            role="Implementation Planner",
            system_instruction=system_instruction,
            ai_config=ai_config,
        )

    def create_plan(
        self,
        project_name: str,
        request_title: str,
        request_text: str,
        project_memory: str,
        codebase_summary: str,
        file_inventory: str,
        blueprint_summary: str,
        supporting_context: str,
        customization_context: str = "",
        request_attachments: list[dict] | None = None,
    ) -> dict:
        attachment_context = describe_image_attachments(request_attachments) or "No image attachments were supplied."
        prompt = f"""Create an implementation plan for this change request.

Project: {project_name}
Request Title: {request_title}
Request: {request_text}

Attached Images:
{attachment_context}

Project Memory:
{project_memory}

Cached Codebase Summary:
{codebase_summary}

Blueprint Summary:
{blueprint_summary}

Supporting Context:
{supporting_context}

Project Customization:
{customization_context or 'No additional planner-specific customization was supplied.'}

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
- Treat Cached Codebase Summary as the primary compressed context and use File Inventory mostly for path selection.
- If a request changes UI behavior, include related styles, scripts/components, and docs when needed.
- If there are existing relevant files, prefer modifying them over inventing parallel structure.
- Keep the existing runtime and project scaffold intact unless the request explicitly asks for a migration.
- For modern app stacks, avoid introducing duplicate top-level HTML/CSS/JS alongside an existing framework structure.
- Keep relevant_files limited to the highest-signal files.
- Keep validation_commands limited to safe, local verification commands that a developer can run after the change.
"""
        result = self.generate_with_attachments(prompt, request_attachments) if request_attachments else self.generate(prompt)
        return self.parse_json(result)
