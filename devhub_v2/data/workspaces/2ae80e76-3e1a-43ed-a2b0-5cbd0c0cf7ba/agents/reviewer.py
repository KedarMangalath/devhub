from agents.base import BaseAgent
import json

class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            role="Code Reviewer",
            system_instruction="""You are a Senior Code Reviewer.
Analyze proposed code changes (Changesets) against the project architecture and best practices.
Identify bugs, security issues, performance bottlenecks, and style violations.
Your output must be a structured JSON review."""
        )

    def review_changeset(self, changeset_diff: str, tech_stack: str, blueprint: str) -> dict:
        """Reviews a changeset and returns structured feedback."""
        prompt = f"""Review the following changeset.

Tech Stack: {tech_stack}
Blueprint: {blueprint}

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
        result = self.generate(prompt=prompt)
        return self.parse_json(result)
