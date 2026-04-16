import json
import logging
from typing import List

from .base import BaseAgent, describe_image_attachments
from .workspace import workspace_manager

logger = logging.getLogger(__name__)


class CoderAgent(BaseAgent):
    BASE_SYSTEM_INSTRUCTION = (
        "You are an expert autonomous coder. Given a feature specification, an implementation plan, project memory, "
        "and current project context, you write the precise code changes required to implement it.\n"
        "You must return ONLY a JSON array, where each element represents a file to be written or modified.\n\n"
        "JSON format:\n"
        "[\n"
        "  {\n"
        "    \"path\": \"relative/path/to/file.py\",\n"
        "    \"content\": \"<exact raw file content to write (replacing file entirely)>\"\n"
        "  }\n"
        "]\n\n"
        "Rules:\n"
        "1. DO NOT return markdown blocks (```json ... ```).\n"
        "2. DO NOT include explanations, only the valid JSON array.\n"
        "3. Ensure the 'content' string handles quotes and newlines safely according to JSON specs.\n"
        "4. Rewrite the entire file content for each changed file; do not omit unchanged sections.\n"
        "5. Respect the implementation plan and keep related UI, logic, styles, wiring, and docs aligned.\n"
        "6. Prefer extending existing project structure over creating duplicate parallel implementations.\n"
        "7. Preserve the existing runnable scaffold and runtime conventions unless the request explicitly asks for a migration.\n"
        "8. If the project already uses React/Vite, Django, FastAPI, or another framework structure, do not fall back to ad-hoc top-level HTML/CSS/JS files.\n"
        "9. Use the smallest file set that fully satisfies the request while preserving existing behavior outside the requested change.\n"
        "10. Treat project-specific overrides or active skill instructions appended later in the system prompt as required constraints."
    )

    def __init__(self, ai_config: dict | None = None, customization_instruction: str = ""):
        system_instruction = self.BASE_SYSTEM_INSTRUCTION
        if customization_instruction.strip():
            system_instruction = f"{system_instruction}\n\n{customization_instruction.strip()}"
        super().__init__(
            role="Senior Software Engineer",
            system_instruction=system_instruction,
            ai_config=ai_config,
        )

    def implement_feature(
        self,
        workspace_id: str,
        feature_title: str,
        feature_desc: str,
        spec: dict,
        files_context: List[dict],
        implementation_plan: dict | None = None,
        project_memory: str = "",
        supporting_context: str = "",
        customization_context: str = "",
        request_attachments: list[dict] | None = None,
    ) -> dict:
        """
        Takes spec and context, generates code, and writes it directly to the workspace.
        files_context should be a list of dicts: [{'path': '...', 'content': '...'}, ...]
        """
        context_str = "\n\n".join([f"--- FILE: {f['path']} ---\n{f['content']}" for f in files_context])
        attachment_context = describe_image_attachments(request_attachments) or "No image attachments were supplied."

        prompt = f"""
## Feature Required
Title: {feature_title}
Description: {feature_desc}

## Attached Images
{attachment_context}

## AI Specification
{json.dumps(spec, indent=2) if spec else 'No spec available.'}

## Implementation Plan
{json.dumps(implementation_plan, indent=2) if implementation_plan else 'No formal plan available.'}

## Project Memory
{project_memory or 'No project memory available yet.'}

## Supporting Context
{supporting_context or 'No additional supporting context.'}

## Project Customization
{customization_context or 'No project-specific implementation overrides were supplied for this change.'}

## Current File Context
(These are the relevant files before your changes. If you need to modify them, rewrite the entire file content incorporating your changes.)
{context_str}

Please generate the required file modifications and additions to implement this feature.
Keep the project consistent across related files when the request affects multiple surfaces.
Return ONLY the JSON array as instructed.
"""

        print("CoderAgent: Generating implementation...")
        response_text = self.generate_with_attachments(prompt, request_attachments) if request_attachments else self.generate(prompt)

        if response_text.startswith("```json"):
            response_text = response_text.split("```json", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text.rsplit("```", 1)[0]

        response_text = response_text.strip()

        try:
            changes = json.loads(response_text)
            if not isinstance(changes, list):
                raise ValueError("Response is not a JSON array")
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM output as JSON: %s\nOutput was: %s...", exc, response_text[:500])
            return {"error": "Failed to parse code output from LLM.", "raw_response": response_text}

        applied_changes = []

        print(f"CoderAgent: Writing {len(changes)} files to workspace {workspace_id}...")
        for change in changes:
            filepath = change.get("path")
            content = change.get("content")

            if filepath and content is not None:
                try:
                    workspace_manager.write_file(workspace_id, filepath, content)
                    applied_changes.append(filepath)
                    print(f"  -> Wrote {filepath}")
                except Exception as exc:
                    logger.error("Failed to write file %s: %s", filepath, exc)

        return {
            "status": "success",
            "files_modified": applied_changes,
        }
