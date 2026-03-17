from agents.base import BaseAgent
import json


class ArchitectAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            role="Software Architect",
            system_instruction="""You are an expert Software Architect for the DevHub platform.
Your primary role is to analyze project codebases, structural definitions, and requirements to
generate comprehensive system blueprints suitable for an interactive technical wiki.
You focus on high-level architecture, technology choices, service boundaries, data flows,
onboarding guides, and developer workflows.
Your output MUST always be valid JSON with no markdown formatting or code blocks - just raw JSON."""
        )

    def generate_blueprint(self, project_name: str, tech_stack: list, local_scan: str, readme: str = "") -> dict:
        tech_joined = ", ".join(tech_stack) if tech_stack else "Not specified"

        prompt = f"""Analyze this project and generate a COMPREHENSIVE technical blueprint as a single JSON object.
This blueprint will power an interactive technical wiki that developers use to fully understand the project.

Project Name: {project_name}
Tech Stack: {tech_joined}

README Content:
{readme}

Local Folder Scan:
{local_scan}

You MUST return a JSON object with ALL of the following keys populated with rich, meaningful data
based on your analysis. Do NOT leave any field empty — infer from the codebase scan and README.
Every array must have at least 2-3 items. Write as if you are creating a production internal wiki.

REQUIRED JSON STRUCTURE (return ONLY this JSON, no markdown):
{{
  "project_summary": "A comprehensive 4-6 sentence summary of what this project is, who it's for, what problem it solves, and the key user-facing capabilities. Written as if briefing a new team member on day 1.",

  "architecture_overview": "A detailed 5-8 sentence description of the overall system architecture, design patterns used (MVC, microservices, event-driven, etc), how components interact, and the deployment topology.",

  "mermaid_architecture": "A valid Mermaid flowchart (graph TD) string that visually represents the system architecture. Include all major components (frontend, backend, database, external services) with labeled arrows showing data flow. Example: graph TD\\n  A[React Frontend] -->|REST API| B[Django Backend]\\n  B --> C[(SQLite DB)]\\n  B --> D[OpenAI API]",

  "mermaid_erd": "A valid Mermaid erDiagram string showing the database schema and relationships. Example: erDiagram\\n  USER ||--o{{ ORDER : places\\n  ORDER ||--|{{ LINE_ITEM : contains",

  "data_flow": "Detailed description of how data flows through the system — from user action, through API, to storage, back to the UI. Cover at least 2 key user flows.",

  "tech_stack_details": [
    {{"tech": "Technology Name", "purpose": "What it's used for in this project", "why_chosen": "Why this technology was selected over alternatives — what makes it the right fit", "version": "version if known", "category": "language|framework|database|tool|library"}}
  ],

  "services": [
    {{"name": "Service Name", "type": "backend|frontend|database|cache|queue|proxy", "description": "Detailed description of what this service does and its responsibilities", "port": "port number or null", "tech": "primary technology", "health_endpoint": "/health or null", "dependencies": ["other service names"], "key_files": ["important files in this service"]}}
  ],

  "api_endpoints": [
    {{"method": "GET|POST|PUT|DELETE|PATCH", "path": "/api/endpoint", "description": "What this endpoint does", "request_body": "JSON example or null", "response": "JSON example", "auth_required": true, "curl_example": "curl -X METHOD http://localhost:PORT/api/endpoint"}}
  ],

  "database_schema": [
    {{"table": "table_name", "description": "Purpose of this table and what business entity it represents", "key_fields": [{{"name": "field_name", "type": "data type", "constraints": "PK|FK|UNIQUE|NOT NULL", "description": "What this field stores"}}], "relationships": "Description of relations to other tables", "indexes": ["index descriptions"]}}
  ],

  "key_components": [
    {{"name": "Component Name", "file_path": "path/to/file", "purpose": "Detailed description of what this component does and why it exists", "complexity": "low|medium|high", "dependencies": ["what it depends on"], "exports": "Key classes/functions this file exports", "lines_estimate": "approximate number of lines"}}
  ],

  "directory_guide": [
    {{"path": "folder_name/", "purpose": "What this directory contains and why it's organized this way", "key_files": ["important_file.py — brief description"], "pattern": "The architectural pattern this folder follows (e.g., MVC controllers, domain models, etc)"}}
  ],

  "setup_steps": [
    {{"step": "Clone the repository", "command": "git clone <url>", "explanation": "Why: Get the source code on your local machine.", "os_note": "Works on all platforms"}},
    {{"step": "Install dependencies", "command": "npm install OR pip install -r requirements.txt", "explanation": "Why: Downloads all third-party libraries the project needs.", "os_note": "Requires Node.js 18+ or Python 3.10+"}},
    {{"step": "Set up environment variables", "command": "cp .env.example .env", "explanation": "Why: Contains API keys and configuration that should not be committed to git.", "os_note": "Edit .env with your actual values"}},
    {{"step": "Run the application", "command": "npm run dev OR python manage.py runserver", "explanation": "Why: Starts the dev server with hot reload for local development.", "os_note": "Default port: 3000 or 8000"}}
  ],

  "environment_variables": [
    {{"name": "VAR_NAME", "description": "What this variable controls and how it affects behavior", "required": true, "default": "default value or null", "example": "example_value", "category": "api_key|database|config|feature_flag"}}
  ],

  "security_considerations": [
    {{"area": "Authentication", "description": "How authentication works in this project — mechanisms, token types, session management", "severity": "high|medium|low"}},
    {{"area": "Data Validation", "description": "How input validation is handled — serializers, schema validation, sanitization", "severity": "high|medium|low"}}
  ],

  "performance_notes": [
    {{"area": "Caching", "description": "What caching strategy is used and where", "impact": "high|medium|low"}},
    {{"area": "Database Queries", "description": "Query optimization approach — indexes, eager loading, pagination", "impact": "high|medium|low"}}
  ],

  "testing_strategy": {{
    "unit": "Unit testing framework and approach used",
    "integration": "Integration testing approach",
    "e2e": "End-to-end testing approach",
    "coverage_target": "Target coverage percentage",
    "run_command": "Command to run the test suite"
  }},

  "code_quality_standards": [
    {{"tool": "ESLint / Pylint / etc", "purpose": "What it enforces", "config_file": "path to config"}}
  ],

  "common_workflows": [
    {{"title": "Add a new API endpoint", "steps": ["Step 1: Create view function in views.py", "Step 2: Add URL pattern in urls.py", "Step 3: Create serializer if needed", "Step 4: Write unit tests", "Step 5: Test with curl or Postman"]}},
    {{"title": "Add a new database model", "steps": ["Step 1: Define model in models.py", "Step 2: Run makemigrations", "Step 3: Run migrate", "Step 4: Register in admin.py if applicable"]}},
    {{"title": "Add a new frontend component", "steps": ["Step 1: Create component file", "Step 2: Import and use in parent", "Step 3: Add styles", "Step 4: Test in browser"]}}
  ],

  "faq": [
    {{"question": "How do I run the project locally?", "answer": "Detailed step-by-step answer"}},
    {{"question": "Where do I add environment variables?", "answer": "Detailed answer with file paths and examples"}},
    {{"question": "How do I debug issues?", "answer": "Tools, logging setup, common error patterns"}}
  ],

  "gotchas": [
    "Common pitfall or non-obvious behavior — explained in detail so a new dev doesn't waste hours",
    "Important thing to know about the codebase that isn't documented anywhere else",
    "Tricky configuration or setup issue with a workaround"
  ],

  "onboarding_checklist": [
    {{"task": "Set up local development environment", "category": "environment", "estimated_time": "30 min", "why_important": "Required to run the project locally", "instructions": "Detailed step-by-step for this task"}},
    {{"task": "Read the project README and architecture docs", "category": "codebase", "estimated_time": "20 min", "why_important": "Understand the big picture before diving into code"}},
    {{"task": "Run the test suite", "category": "processes", "estimated_time": "10 min", "why_important": "Verify everything is set up correctly"}},
    {{"task": "Set up IDE with recommended extensions", "category": "tools", "estimated_time": "15 min", "why_important": "Consistent development experience across the team"}},
    {{"task": "Review coding standards and PR process", "category": "processes", "estimated_time": "15 min", "why_important": "Follow team conventions from day one"}}
  ],

  "key_concepts": [
    {{"concept": "Core Domain Concept", "explanation": "Thorough 3-5 sentence explanation of this concept, what it represents in the business domain, and how it manifests in the code", "why_important": "Why a new developer needs to understand this before touching the codebase", "related_code": "path/to/relevant/file.py", "related_concepts": ["other related concepts"]}}
  ]
}}

CRITICAL RULES:
- Return ONLY the JSON object, no markdown code blocks, no explanations before or after.
- Fill ALL fields with real, project-specific data based on your analysis. No placeholders.
- For mermaid_architecture: use graph TD syntax. Every node should have a descriptive label. Use arrows with labels.
- For mermaid_erd: list all database tables/models you found. Show cardinality.
- For api_endpoints: infer from route files, view files, controller files in the scan. Include curl examples.
- For directory_guide: cover every top-level directory visible in the folder scan.
- For common_workflows: make them specific to THIS project's tech stack.
- For faq: answer in 2-4 sentences with specific file paths and commands.
- Write RICH content — as if you are creating the internal wiki that a team of 10 developers will rely on daily.
"""

        try:
            result = self.generate(prompt=prompt)
            return self.parse_json(result)
        except Exception as e:
            return self._fallback_blueprint(project_name, tech_stack, str(e))

    def _fallback_blueprint(self, project_name: str, tech_stack: list, error: str) -> dict:
        """Generate a useful fallback blueprint when AI generation fails."""
        return {
            "project_summary": f"Blueprint generation failed: {error}. Please ensure OPENAI_API_KEY is set.",
            "architecture_overview": f"Unable to generate architecture overview. Error: {error}",
            "mermaid_architecture": "graph TD\n  A[Application] --> B[Database]",
            "mermaid_erd": "",
            "data_flow": "Unable to analyze data flow.",
            "tech_stack_details": [{"tech": t, "purpose": "Core technology", "why_chosen": "Selected by the project creator", "version": "unknown", "category": "framework"} for t in (tech_stack or [])],
            "services": [{"name": project_name, "type": "application", "description": "Main application service", "port": None, "tech": ", ".join(tech_stack or []), "health_endpoint": None, "dependencies": [], "key_files": []}],
            "api_endpoints": [],
            "database_schema": [],
            "key_components": [],
            "directory_guide": [],
            "setup_steps": [
                {"step": "Install dependencies", "command": "See README", "explanation": "Downloads required libraries", "os_note": ""},
                {"step": "Configure environment", "command": "cp .env.example .env", "explanation": "Set up API keys", "os_note": ""},
                {"step": "Run the app", "command": "See README", "explanation": "Start the development server", "os_note": ""},
            ],
            "environment_variables": [{"name": "OPENAI_API_KEY", "description": "API key for AI features", "required": True, "default": None, "example": "sk-...", "category": "api_key"}],
            "security_considerations": [{"area": "Authentication", "description": "Review before deploying", "severity": "high"}],
            "performance_notes": [{"area": "General", "description": "Profile under load", "impact": "medium"}],
            "testing_strategy": {"unit": "Not configured", "integration": "Not configured", "e2e": "Not configured", "coverage_target": "80%", "run_command": ""},
            "code_quality_standards": [{"tool": "N/A", "purpose": "Follow project conventions", "config_file": ""}],
            "common_workflows": [],
            "faq": [{"question": "How do I run the project?", "answer": "Check the README for setup instructions."}],
            "gotchas": [f"AI blueprint generation failed: {error}"],
            "onboarding_checklist": [
                {"task": "Set up development environment", "category": "environment", "estimated_time": "30 min", "why_important": "Required to run locally", "instructions": "See README"},
            ],
            "key_concepts": [{"concept": project_name, "explanation": "The main application", "why_important": "Core project", "related_code": "", "related_concepts": []}],
        }
