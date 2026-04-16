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
Generate the actual requested product, not a generic landing page or placeholder marketing screen.
When the selected stack spans frontend and backend, create connected frontend and backend folders and wire the UI to real backend endpoints.
Prefer replacing the main entry files with app-specific code instead of adding disconnected alternates.
If the request needs persistence, scores, leaderboards, auth, or saved state, include the real backend models, storage, and routes for that behavior.
Do not collapse browser apps with backend requirements into a single static HTML file.
Always output your scaffolding plan as a structured JSON object.""",
            ai_config=ai_config,
        )

    def generate_scaffold(self, description: str, tech_stack: str) -> dict:
        """Generates the initial framework and file structure for a new feature/project."""
        prompt = f"""Generate a runnable scaffolding plan based on this description.

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

Rules:
- Return real file contents, not TODO comments or mock landing-page filler.
- If the stack includes both frontend and backend technologies, create both sides and connect them.
- Frontend code must call the backend through working routes, not fake local constants.
- If the product needs persistence, scores, leaderboards, auth, or saved state, create the actual backend logic and wire the frontend to it.
- Do not respond with only a single static HTML/CSS/JS page when the prompt requires backend behavior.
- Prefer a structure that DevHub can run immediately after setup.
"""
        result = self.generate(prompt=prompt)
        return self.parse_json(result)
