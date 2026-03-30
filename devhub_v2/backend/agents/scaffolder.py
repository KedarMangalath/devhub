from agents.base import BaseAgent
import os
import json

class ScaffolderAgent(BaseAgent):
    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="Project Scaffolding Expert",
            system_instruction="""You are a Project Scaffolding Expert.
Given a short description of a new component, module, or full project, your job is to 
generate the initial directory structure and the core files required to start development.
Always output your scaffolding plan as a structured JSON object.""",
            ai_config=ai_config,
        )

    def generate_scaffold(self, description: str, tech_stack: str) -> dict:
        """Generates the initial framework and file structure for a new feature/project."""
        prompt = f"""Generate a basic scaffolding plan based on this description.

Description: {description}
Tech Stack: {tech_stack}

Return a valid JSON object matching this structure:
{{
  "project_name": "Suggested project or feature name",
  "files": [
    {{
      "path": "path/to/file.ext",
      "content": "Initial boilerplate code for the file"
    }}
  ],
  "commands": [
    "npm install package",
    "python manage.py runserver"
  ]
}}
"""
        result = self.generate(prompt=prompt)
        return self.parse_json(result)
