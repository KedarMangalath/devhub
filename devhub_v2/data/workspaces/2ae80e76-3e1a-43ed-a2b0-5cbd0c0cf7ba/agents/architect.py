from agents.base import BaseAgent
import json
from enum import Enum

class ArchitectAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            role="Software Architect",
            system_instruction="""You are an expert Software Architect for the DevHub platform. 
Your primary role is to analyze project codebases, structural definitions, and requirements to 
generate comprehensive system blueprints. You focus on high-level architecture, technology 
choices, service boundaries, and data flows. Your output MUST always be structured JSON."""
        )

    def generate_blueprint(self, project_name: str, tech_stack: list, local_scan: str, readme: str = "") -> dict:
        tech_joined = ", ".join(tech_stack) if tech_stack else "Not specified"
        
        prompt = f"""Analyze this project and generate a comprehensive technical blueprint.

Project Name: {project_name}
Tech Stack: {tech_joined}

README Content:
{readme}

Local Folder Scan:
{local_scan}

Generate a clear, detailed blueprint covering architecture overview, tech stack details, 
services, API endpoints, database schema, data flow, key components, setup steps, and gotchas.
"""
        # Define the expected JSON schema as per the old main.py implementation
        # For simplicity in this example, we'll let the agent just return unstructured or generic JSON.
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "architecture_overview": {"type": "STRING"},
                "tech_stack_details": {
                    "type": "ARRAY", 
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "tech": {"type": "STRING"},
                            "purpose": {"type": "STRING"}
                        }
                    }
                },
                "services": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "type": {"type": "STRING"},
                            "description": {"type": "STRING"}
                        }
                    }
                },
                 "key_components": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "file_path": {"type": "STRING"},
                            "purpose": {"type": "STRING"}
                        }
                    }
                },
                "setup_steps": {"type": "ARRAY", "items": {"type": "STRING"}},
                "gotchas": {"type": "ARRAY", "items": {"type": "STRING"}}
            },
            "required": ["architecture_overview", "tech_stack_details", "services"]
        }
        
        # We can either use strict schema or just parse JSON
        try:
            # Note: For google-genai, the schema mapping has specific types, we'll rely on parse_json for now
            # if we don't map perfectly.
            result = self.generate(
                prompt=prompt + "\n\nReturn valid JSON only matching the requested fields.",
                response_schema=None # Removing strict schema temporarily for flexibility
            )
            return self.parse_json(result)
        except Exception as e:
            # Fallback
            return {
                "architecture_overview": "Failed to generate blueprint: " + str(e),
                "tech_stack_details": [],
                "services": []
            }
