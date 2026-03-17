from agents.base import BaseAgent
import os
import json

class FeatureAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            role="Feature Implementation Engineer",
            system_instruction="""You are a Senior Feature Implementation Engineer.
Your role is to write clean, maintainable, and well-tested code that fulfills feature specs.
You will be provided with a technical specification, the project's codebase snapshot, and 
the current architecture blueprint.
Output your implementation plan as a JSON object detailing exactly which files to create, 
modify, or delete, along with the complete source code for each file."""
        )

    def generate_spec(self, feature_title: str, feature_desc: str, tech_stack: str, blueprint: str) -> dict:
        """Generates a detailed technical specification for a feature."""
        prompt = f"""Generate a technical spec for this feature.
        
Title: {feature_title}
Description: {feature_desc}
Tech Stack: {tech_stack}
Architecture Blueprint: {blueprint}

Return a valid JSON object matching this structure:
{{
  "user_story": "As a X, I want Y so that Z",
  "technical_approach": "...",
  "files_to_modify": ["path/to/file"],
  "new_files_needed": ["path/to/new_file"],
  "estimated_complexity": "low|medium|high",
  "dependencies": []
}}
"""
        result = self.generate(prompt=prompt)
        return self.parse_json(result)

    def implement_feature(self, spec: dict, codebase_context: str) -> dict:
        """Generates the actual code changes needed to implement the feature."""
        prompt = f"""Implement the feature based on the spec.
        
Specification:
{json.dumps(spec, indent=2)}

Codebase Context:
{codebase_context}

Return a valid JSON object matching this structure:
{{
  "summary": "Summary of changes made.",
  "files": [
    {{
      "action": "create|modify|delete",
      "path": "path/to/file.py",
      "content": "The actual complete file code OR empty if delete",
      "explanation": "Why this change was made"
    }}
  ]
}}
"""
        result = self.generate(prompt=prompt)
        return self.parse_json(result)
