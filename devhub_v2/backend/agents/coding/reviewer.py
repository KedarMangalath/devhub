from agents.core.base import BaseAgent, describe_image_attachments
import json

class ReviewerAgent(BaseAgent):
    BASE_SYSTEM_INSTRUCTION = """You are a Senior Code Reviewer.
Analyze proposed code changes against the project architecture and implementation goals.
Prioritize correctness, regressions, missing validation, security issues, and mismatches with the requested behavior.
Do not spend the review on style-only nitpicks when there is no user-visible or correctness impact.
Your output must be a structured JSON review."""

    def __init__(self, ai_config: dict | None = None, customization_instruction: str = ""):
        system_instruction = self.BASE_SYSTEM_INSTRUCTION
        if customization_instruction.strip():
            system_instruction = f"{system_instruction}\n\n{customization_instruction.strip()}"
        super().__init__(
            role="Code Reviewer",
            system_instruction=system_instruction,
            ai_config=ai_config,
        )

    def review_changeset(
        self,
        changeset_diff: str,
        tech_stack: str,
        blueprint: str,
        evaluation_summary: str = "",
        customization_context: str = "",
        request_text: str = "",
        request_attachments: list[dict] | None = None,
    ) -> dict:
        """Reviews a changeset and returns structured feedback."""
        attachment_context = describe_image_attachments(request_attachments) or "No image attachments were supplied."
        prompt = f"""Review the following changeset.

Tech Stack: {tech_stack}
Blueprint: {blueprint}

Original Request:
{request_text or 'No original request text was provided.'}

Attached Images:
{attachment_context}

Evaluation Summary:
{evaluation_summary or 'No automated evaluation results were provided.'}

Project Customization:
{customization_context or 'No additional reviewer-specific customization was supplied.'}

Changeset Diff:
{changeset_diff}

Return valid JSON matching this structure:
{{
  "approved": true|false,
  "score": 0-100,
  "summary": "Overall impression",
  "issues": [
    {{
      "severity": "low|medium|high|critical",
      "file": "path/to/file",
      "description": "Issue description",
      "suggestion": "How to fix it"
    }}
  ]
}}
"""
        result = self.generate_with_attachments(prompt, request_attachments) if request_attachments else self.generate(prompt=prompt)
        return self.parse_json(result)
