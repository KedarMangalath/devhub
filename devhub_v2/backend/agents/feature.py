from agents.base import BaseAgent
import json


class FeatureAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            role="Feature Implementation Engineer",
            system_instruction="""You are a Senior Feature Implementation Engineer.
Your role is to analyze feature requirements and generate detailed technical specifications.
You will be provided with a feature title, description, the project's tech stack, and 
architecture blueprint. Output ONLY valid JSON with no markdown formatting."""
        )

    def generate_spec(self, feature_title: str, feature_desc: str, tech_stack: str, blueprint: str) -> dict:
        """Generates a detailed technical specification for a feature."""
        prompt = f"""Generate a comprehensive technical specification for this feature.

Feature Title: {feature_title}
Feature Description: {feature_desc}
Tech Stack: {tech_stack}
Architecture Blueprint Summary: {blueprint}

Return ONLY a valid JSON object (no markdown) with this structure:
{{
  "user_story": "As a [role], I want [feature] so that [benefit]",
  "technical_approach": "Detailed explanation of how to implement this feature, including architecture decisions, data flow changes, and integration points",
  "acceptance_criteria": [
    "Criterion 1: Specific testable condition",
    "Criterion 2: Another testable condition"
  ],
  "files_to_modify": [
    {{"path": "path/to/file", "changes": "Description of what changes are needed"}}
  ],
  "new_files_needed": [
    {{"path": "path/to/new_file", "purpose": "What this file does"}}
  ],
  "estimated_complexity": "low|medium|high",
  "estimated_effort": "1-2 hours | 2-4 hours | 4-8 hours | 1-2 days | 3-5 days",
  "dependencies": ["External libraries or services needed"],
  "api_changes": [
    {{"method": "POST", "path": "/api/endpoint", "description": "New endpoint needed"}}
  ],
  "database_changes": [
    {{"table": "table_name", "change": "Add column X / Create table / etc."}}
  ],
  "testing_plan": {{
    "unit_tests": ["Test case 1", "Test case 2"],
    "integration_tests": ["Integration test 1"],
    "edge_cases": ["Edge case to handle"]
  }},
  "risks": ["Potential risk or challenge"],
  "rollback_plan": "How to revert if something goes wrong"
}}
"""
        try:
            result = self.generate(prompt=prompt)
            return self.parse_json(result)
        except Exception as e:
            return {
                "user_story": f"As a developer, I want {feature_title} so that {feature_desc}",
                "technical_approach": f"Implement {feature_title}: {feature_desc}",
                "acceptance_criteria": [f"{feature_title} works as described"],
                "files_to_modify": [],
                "new_files_needed": [],
                "estimated_complexity": "medium",
                "estimated_effort": "2-4 hours",
                "dependencies": [],
                "api_changes": [],
                "database_changes": [],
                "testing_plan": {"unit_tests": [], "integration_tests": [], "edge_cases": []},
                "risks": [f"AI spec generation failed: {str(e)}"],
                "rollback_plan": "Revert the changes",
            }

    def implement_feature(self, spec: dict, codebase_context: str) -> dict:
        """Generates the actual code changes needed to implement the feature."""
        prompt = f"""Implement the feature based on the spec.

Specification:
{json.dumps(spec, indent=2)}

Codebase Context:
{codebase_context}

Return ONLY a valid JSON object (no markdown) with this structure:
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
        try:
            result = self.generate(prompt=prompt)
            return self.parse_json(result)
        except Exception as e:
            return {"summary": f"Implementation failed: {str(e)}", "files": []}
