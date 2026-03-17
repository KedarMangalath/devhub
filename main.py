import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()  # Load .env file (looks in current dir and parent dirs)

import openai
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
APPS_DIR = DATA_DIR / "apps"

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
DATA_DIR.mkdir(parents=True, exist_ok=True)
APPS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------
client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="DevHub", version="1.0.0")


@app.on_event("startup")
async def seed_default_app():
    """Auto-register the DevHub project itself on first launch."""
    if get_apps():
        return  # already has apps, skip

    project_dir = str(BASE_DIR)
    local_scan = scan_local_folder(project_dir)

    tech = ["Python", "FastAPI", "Alpine.js", "Tailwind CSS", "OpenAI gpt-5-mini"]
    tech_joined = ", ".join(tech)

    blueprint_prompt = f"""You are a senior software architect. Analyze this project and generate a comprehensive blueprint.

Project: DevHub
Description: Multi-Application Developer Intelligence Platform — a web dashboard where teams register any application, auto-generate its architecture blueprint via AI, onboard new developers, manage features, and run a full SDLC pipeline from backlog to production.
Tech Stack: {tech_joined}
Team: Platform Team
GitHub: Not provided

Local folder scan:
{local_scan}

Return ONLY valid JSON with these fields:
{{
  "architecture_overview": "3-4 paragraphs describing the complete system architecture",
  "tech_stack_details": [{{"tech": "name", "purpose": "why it's used", "version": "if known"}}],
  "services": [{{"name": "...", "type": "frontend|backend|database|cache|queue|external|mobile", "description": "...", "tech": "...", "port": "if applicable"}}],
  "api_endpoints": [{{"method": "GET|POST|PUT|DELETE|PATCH", "path": "/api/...", "description": "...", "auth_required": false, "request_body": "...", "response": "..."}}],
  "database_schema": [{{"table": "...", "description": "...", "key_fields": ["..."], "relationships": "..."}}],
  "data_flow": "Description of how data flows through the system end-to-end",
  "key_components": [{{"name": "...", "file_path": "...", "purpose": "...", "complexity": "low|medium|high", "dependencies": ["..."]}}],
  "setup_steps": ["Step 1: ...", "Step 2: ..."],
  "environment_variables": [{{"name": "OPENAI_API_KEY", "description": "OpenAI API key for AI features", "required": true, "example": "sk-proj-..."}}],
  "onboarding_checklist": [{{"task": "...", "category": "environment|codebase|processes|tools|team", "estimated_time": "...", "resources": "..."}}],
  "key_concepts": [{{"concept": "...", "explanation": "...", "why_important": "..."}}],
  "gotchas": ["..."],
  "deployment_info": {{"environments": ["local", "production"], "ci_cd": "Manual", "deployment_process": "python main.py", "rollback_process": "git revert"}},
  "code_quality_standards": ["..."],
  "testing_strategy": {{"unit": "...", "integration": "...", "e2e": "...", "coverage_target": "80%"}},
  "security_considerations": ["..."],
  "performance_notes": ["..."]
}}"""

    try:
        message = client.chat.completions.create(
            model="gpt-5-mini",
            max_tokens=4096,
            messages=[{"role": "user", "content": blueprint_prompt}],
        )
        blueprint = parse_json_from_response(message.choices[0].message.content)
    except Exception as e:
        # Fallback minimal blueprint if AI fails
        blueprint = {
            "architecture_overview": "DevHub is a FastAPI + Alpine.js single-page application. The backend exposes REST APIs consumed by the frontend. Data is stored in JSON files under devhub/data/.",
            "tech_stack_details": [{"tech": t, "purpose": "Core technology", "version": "latest"} for t in tech],
            "services": [
                {"name": "FastAPI Backend", "type": "backend", "description": "REST API server", "tech": "Python / FastAPI", "port": "8080"},
                {"name": "Alpine.js SPA", "type": "frontend", "description": "Single-page dashboard", "tech": "HTML + Alpine.js + Tailwind", "port": "8080"},
                {"name": "JSON File Store", "type": "database", "description": "Persistent data storage", "tech": "JSON files", "port": ""},
            ],
            "api_endpoints": [
                {"method": "GET", "path": "/api/apps", "description": "List all registered apps", "auth_required": False, "request_body": "", "response": "[]"},
                {"method": "POST", "path": "/api/apps", "description": "Register a new app", "auth_required": False, "request_body": "{name, description}", "response": "{app, blueprint}"},
            ],
            "database_schema": [{"table": "apps.json", "description": "App registry", "key_fields": ["id", "name", "status"], "relationships": ""}],
            "data_flow": "User submits app details → FastAPI calls OpenAI → Blueprint stored as JSON → Frontend reads and displays",
            "key_components": [
                {"name": "main.py", "file_path": "devhub/main.py", "purpose": "FastAPI backend with all routes", "complexity": "medium", "dependencies": ["openai", "fastapi"]},
                {"name": "index.html", "file_path": "devhub/static/index.html", "purpose": "Alpine.js SPA frontend", "complexity": "high", "dependencies": ["Alpine.js", "Tailwind"]},
            ],
            "setup_steps": ["Clone or download the project", "Set OPENAI_API_KEY environment variable", "Run: cd devhub && pip install -r requirements.txt", "Run: python main.py", "Open http://localhost:8080"],
            "environment_variables": [{"name": "OPENAI_API_KEY", "description": "OpenAI API key", "required": True, "example": "sk-proj-..."}],
            "onboarding_checklist": [
                {"task": "Set OPENAI_API_KEY", "category": "environment", "estimated_time": "5 min", "resources": "platform.openai.com"},
                {"task": "Install Python dependencies", "category": "environment", "estimated_time": "5 min", "resources": "requirements.txt"},
                {"task": "Read main.py to understand API routes", "category": "codebase", "estimated_time": "20 min", "resources": "devhub/main.py"},
                {"task": "Explore index.html Alpine.js components", "category": "codebase", "estimated_time": "30 min", "resources": "devhub/static/index.html"},
                {"task": "Register your first test application", "category": "processes", "estimated_time": "10 min", "resources": "http://localhost:8080"},
            ],
            "key_concepts": [
                {"concept": "App Registry", "explanation": "All apps stored in data/apps.json with metadata", "why_important": "Central source of truth for all registered projects"},
                {"concept": "Blueprint Generation", "explanation": "OpenAI analyzes project info and generates structured JSON blueprint", "why_important": "Core AI feature that powers onboarding and documentation"},
                {"concept": "SDLC Pipeline", "explanation": "7-stage workflow: backlog → development → testing → code_review → staging → approved → production", "why_important": "Tracks features from idea to deployment"},
                {"concept": "Alpine.js Reactivity", "explanation": "x-data, x-show, x-for directives drive the UI without a build step", "why_important": "Understand this to modify the frontend"},
            ],
            "gotchas": [
                "OPENAI_API_KEY must be set before starting — the app will fail silently if missing",
                "JSON files in data/ are the database — back them up before updates",
                "The webkitdirectory upload only works in Chrome/Edge, not Firefox",
                "Advancing a feature to 'testing' calls OpenAI and may take 20-30 seconds",
            ],
            "deployment_info": {"environments": ["local", "production"], "ci_cd": "Manual", "deployment_process": "python main.py", "rollback_process": "Restore data/ JSON files"},
            "code_quality_standards": ["Use async/await for all route handlers", "Parse JSON responses from AI with error handling", "Keep frontend logic in Alpine.js data object"],
            "testing_strategy": {"unit": "Test individual API endpoints", "integration": "Test full register→blueprint flow", "e2e": "Browser test the full SDLC pipeline", "coverage_target": "70%"},
            "security_considerations": ["Never commit OPENAI_API_KEY to source control", "Validate file upload paths to prevent directory traversal", "Sanitize all user inputs"],
            "performance_notes": ["AI calls (blueprint/spec/tests) can take 30-60s — show loading states", "Batch file uploads in groups of 20 to avoid request size limits"],
        }

    now = datetime.now(timezone.utc).isoformat()
    app_entry = {
        "id": "devhub01",
        "name": "DevHub",
        "description": "Multi-Application Developer Intelligence Platform — this app itself",
        "tech_stack": tech,
        "team_members": ["Platform Team"],
        "github_url": None,
        "registered_at": now,
        "status": "active",
    }

    apps = get_apps()
    apps.append(app_entry)
    save_apps(apps)
    save_blueprint("devhub01", blueprint)
    (APPS_DIR / "devhub01").mkdir(parents=True, exist_ok=True)
    save_features("devhub01", [])
    save_chat("devhub01", [])

    # Also copy actual source files so Code Explorer works
    files_dir = APPS_DIR / "devhub01" / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    EXCLUDE_ROOTS = SKIP_DIRS | {"data"}  # exclude data dir to prevent recursion
    for src_file in BASE_DIR.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(BASE_DIR)
        parts = rel.parts
        # Skip if any part of the path is in excluded dirs
        if any(p in EXCLUDE_ROOTS for p in parts):
            continue
        dest = files_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_bytes(src_file.read_bytes())
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------
PIPELINE_STAGES = [
    "backlog",
    "development",
    "testing",
    "code_review",
    "staging",
]

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RegisterAppRequest(BaseModel):
    name: str
    description: str
    github_url: Optional[str] = None
    local_path: Optional[str] = None
    tech_stack: List[str] = []
    team_members: List[str] = []
    role: str = "admin"


class CreateFeatureRequest(BaseModel):
    title: str
    description: str
    created_by: str = "Developer"
    role: str = "developer"


class PipelineActionRequest(BaseModel):
    feature_id: str
    action: str  # advance | reject | approve
    by: str = "Developer"
    role: str = "developer"
    comment: str = ""


class ChatRequest(BaseModel):
    message: str
    username: str = "Developer"


class CommentRequest(BaseModel):
    text: str
    author: str = "Developer"


# ---------------------------------------------------------------------------
# Helper: JSON I/O
# ---------------------------------------------------------------------------


def _load(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_apps() -> list:
    return _load(DATA_DIR / "apps.json", [])


def save_apps(apps):
    _save(DATA_DIR / "apps.json", apps)


def get_blueprint(app_id: str) -> dict:
    return _load(APPS_DIR / app_id / "blueprint.json", {})


def save_blueprint(app_id: str, data: dict):
    _save(APPS_DIR / app_id / "blueprint.json", data)


def get_features(app_id: str) -> list:
    return _load(APPS_DIR / app_id / "features.json", [])


def save_features(app_id: str, features: list):
    _save(APPS_DIR / app_id / "features.json", features)


def get_chat(app_id: str) -> list:
    return _load(APPS_DIR / app_id / "chat.json", [])


def save_chat(app_id: str, messages: list):
    _save(APPS_DIR / app_id / "chat.json", messages)


# ---------------------------------------------------------------------------
# Helper: scan local folder
# ---------------------------------------------------------------------------

CONFIG_FILES = [
    "README.md", "readme.md", "README.txt",
    "package.json", "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".env.example", "env.example",
    "pom.xml", "build.gradle", "go.mod", "Cargo.toml", "composer.json",
    "angular.json", "next.config.js", "vite.config.js", "webpack.config.js",
]

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "target", "vendor", ".idea", ".vscode",
}

def scan_local_folder(folder_path: str) -> str:
    """Scan a local folder and return a text summary for AI analysis."""
    base = Path(folder_path)
    if not base.exists() or not base.is_dir():
        return f"Path not found: {folder_path}"

    result = []

    # 1. File tree (max 3 levels deep)
    result.append("=== FILE STRUCTURE ===")
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        depth = len(Path(root).relative_to(base).parts)
        if depth > 3:
            dirs[:] = []
            continue
        indent = "  " * depth
        folder_name = Path(root).name if depth > 0 else base.name
        result.append(f"{indent}{folder_name}/")
        for f in sorted(files)[:30]:
            result.append(f"{indent}  {f}")
    result.append("")

    # 2. Read config/key files
    result.append("=== KEY FILES ===")
    for fname in CONFIG_FILES:
        fpath = base / fname
        if fpath.exists():
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")[:2000]
                result.append(f"\n--- {fname} ---\n{content}")
            except Exception:
                pass

    # 3. Try to read a few source files (first .py / .js / .ts / .go etc.)
    result.append("\n=== SAMPLE SOURCE FILES ===")
    source_exts = {".py", ".js", ".ts", ".go", ".java", ".rb", ".php", ".cs", ".rs"}
    found = 0
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if found >= 3:
                break
            if Path(f).suffix in source_exts:
                fpath = Path(root) / f
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")[:1500]
                    rel = fpath.relative_to(base)
                    result.append(f"\n--- {rel} ---\n{content}")
                    found += 1
                except Exception:
                    pass
        if found >= 3:
            break

    return "\n".join(result)[:8000]  # cap total size


# ---------------------------------------------------------------------------
# Helper: parse JSON from Claude response
# ---------------------------------------------------------------------------


def parse_json_from_response(text: str) -> dict:
    """Extract JSON from a Claude response that may be wrapped in markdown code fences."""
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop first line (```json or ```) and last line (```)
        inner = []
        skip_first = True
        for line in lines:
            if skip_first and line.startswith("```"):
                skip_first = False
                continue
            if line.strip() == "```":
                break
            inner.append(line)
        text = "\n".join(inner)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Helper: AI test simulation
# ---------------------------------------------------------------------------


def run_ai_test_simulation(feature: dict, tech_stack: list) -> dict:
    prompt = f"""You are a QA lead. Evaluate this feature spec and simulate test results.

Feature: {feature['title']}
Description: {feature['description']}
Spec: {json.dumps(feature.get('spec', {}), indent=2)}
Tech Stack: {', '.join(tech_stack)}

Return JSON:
{{
  "overall_status": "passed|failed|warning",
  "score": 85,
  "summary": "one line summary",
  "tests": [
    {{"name": "Unit Tests", "status": "passed|failed|warning", "total": 12, "passed": 12, "details": "..."}},
    {{"name": "Integration Tests", "status": "passed|failed|warning", "total": 5, "passed": 4, "details": "..."}},
    {{"name": "Security Scan", "status": "passed|failed|warning", "issues_found": 0, "details": "..."}},
    {{"name": "Code Quality", "status": "passed|failed|warning", "score": 92, "details": "..."}},
    {{"name": "API Contract Tests", "status": "passed|failed|warning", "total": 3, "passed": 3, "details": "..."}},
    {{"name": "Performance Tests", "status": "passed|failed|warning", "details": "..."}}
  ],
  "coverage": 87,
  "suggestions": ["Suggestion 1", "Suggestion 2"],
  "blockers": []
}}
Return ONLY valid JSON."""

    message = client.chat.completions.create(
        model="gpt-5-mini",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_json_from_response(message.choices[0].message.content)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def serve_index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


@app.get("/api/apps")
async def list_apps():
    return get_apps()


@app.post("/api/apps")
async def register_app(req: RegisterAppRequest):
    app_id = str(uuid.uuid4())[:8]

    # Try to fetch GitHub README
    readme_content = ""
    if req.github_url:
        try:
            # Convert github.com URL to raw content URL
            url = req.github_url.rstrip("/")
            # e.g. https://github.com/owner/repo -> owner/repo
            parts = url.replace("https://github.com/", "").replace(
                "http://github.com/", ""
            )
            raw_url = f"https://raw.githubusercontent.com/{parts}/main/README.md"
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(raw_url)
                if resp.status_code == 200:
                    readme_content = resp.text[:3000]  # limit size
        except Exception:
            pass

    # Scan local folder if provided
    local_scan = ""
    if req.local_path:
        local_scan = scan_local_folder(req.local_path)

    tech_joined = ", ".join(req.tech_stack) if req.tech_stack else "Not specified"
    team_joined = ", ".join(req.team_members) if req.team_members else "Not specified"
    readme_section = (
        f"\nREADME:\n{readme_content}" if readme_content else ""
    )
    local_section = (
        f"\nLocal folder scan:\n{local_scan}" if local_scan else ""
    )

    blueprint_prompt = f"""You are a senior software architect. Analyze this project and generate a comprehensive blueprint.

Project: {req.name}
Description: {req.description}
Tech Stack: {tech_joined}
Team: {team_joined}
GitHub: {req.github_url or 'Not provided'}
Local Path: {req.local_path or 'Not provided'}
{readme_section}{local_section}

Return ONLY valid JSON with these fields. Be extremely detailed — a new developer should understand the entire system from this blueprint alone:
{{
  "architecture_overview": "5-6 paragraphs: (1) high-level system purpose and design philosophy, (2) frontend architecture and rendering approach, (3) backend architecture and request lifecycle, (4) data storage design and persistence strategy, (5) integration patterns with external services, (6) key architectural trade-offs made",
  "tech_stack_details": [{{"tech": "name", "purpose": "detailed reason why this was chosen over alternatives", "version": "exact version if known", "config_notes": "any important config or usage notes"}}],
  "services": [{{
    "name": "service name",
    "type": "frontend|backend|database|cache|queue|external|mobile",
    "description": "detailed description of what this service does",
    "tech": "technology stack",
    "port": "port number if applicable",
    "protocol": "HTTP|HTTPS|WebSocket|gRPC|TCP|AMQP",
    "health_check": "how to verify service is running",
    "owns_data": ["list of data entities this service owns"],
    "exposes": ["list of capabilities/endpoints exposed"],
    "consumes": ["list of services/APIs this service calls"]
  }}],
  "service_dependency_graph": [{{
    "from": "service name (caller)",
    "to": "service name (called)",
    "type": "sync|async|event|storage",
    "protocol": "HTTP|gRPC|SQL|Redis|Kafka|etc",
    "description": "what data or operation flows here",
    "criticality": "critical|important|optional"
  }}],
  "api_endpoints": [{{
    "method": "GET|POST|PUT|DELETE|PATCH",
    "path": "/api/...",
    "description": "detailed description of what this endpoint does",
    "auth_required": true,
    "request_body": "JSON schema or example",
    "response": "JSON schema or example",
    "query_params": "list of query parameters",
    "error_codes": ["400: ...", "404: ...", "500: ..."],
    "rate_limited": false,
    "notes": "any important implementation notes"
  }}],
  "database_schema": [{{
    "table": "table or collection name",
    "description": "what this stores and why",
    "key_fields": [{{"name": "field", "type": "string|int|bool|datetime|uuid", "description": "what it stores", "indexed": true, "nullable": false}}],
    "relationships": "detailed FK/reference relationships with other tables",
    "indexes": ["index_name on (field1, field2) — reason for this index"],
    "constraints": ["UNIQUE (email)", "CHECK (status IN ...)"],
    "sample_record": {{}}
  }}],
  "data_flow": "Step-by-step description of how data flows through the system for the most common operations",
  "sequence_flows": [{{
    "name": "flow name (e.g. User Login, Create Order)",
    "description": "when this flow occurs",
    "steps": ["1. User submits form → Frontend", "2. Frontend calls POST /api/...", "3. Backend validates → DB query", "4. DB returns row → Backend formats → Response", "5. Frontend updates UI state"]
  }}],
  "key_components": [{{
    "name": "component name",
    "file_path": "src/path/to/file",
    "purpose": "detailed purpose and responsibilities",
    "complexity": "low|medium|high",
    "dependencies": ["internal module", "external package"],
    "exports": ["function/class names exported"],
    "design_pattern": "pattern used (MVC, Repository, Factory, Observer, etc.)",
    "entry_points": ["main functions/methods a new dev should read first"]
  }}],
  "setup_steps": ["Step 1: Clone repo — git clone ...", "Step 2: ..."],
  "environment_variables": [{{"name": "VAR_NAME", "description": "detailed description of what it controls", "required": true, "example": "example-value", "default": "default if optional", "how_to_get": "where to obtain this value"}}],
  "onboarding_checklist": [{{"task": "...", "category": "environment|codebase|processes|tools|team", "estimated_time": "30 min", "resources": "link or file", "why_important": "why this matters for the role"}}],
  "key_concepts": [{{"concept": "...", "explanation": "thorough explanation with example for new developers", "why_important": "impact if misunderstood", "related_code": "file or function where this is implemented"}}],
  "gotchas": ["Detailed pitfall with context and how to avoid or fix it"],
  "deployment_info": {{
    "environments": ["dev", "staging"],
    "ci_cd": "tool and pipeline description",
    "deployment_process": "step by step deployment",
    "rollback_process": "how to rollback",
    "infrastructure": "cloud provider, region, compute type",
    "monitoring": "what monitoring/alerting is in place",
    "logs": "where to find logs"
  }},
  "code_quality_standards": ["Detailed standard with rationale"],
  "testing_strategy": {{
    "unit": "detailed unit test approach with examples",
    "integration": "integration test approach",
    "e2e": "end-to-end test approach",
    "coverage_target": "80%",
    "test_data": "how test data is managed",
    "ci_test_command": "command to run all tests"
  }},
  "security_considerations": ["Detailed security requirement with implementation guidance"],
  "performance_notes": ["Detailed performance consideration with measurement approach"]
}}"""

    message = client.chat.completions.create(
        model="gpt-5-mini",
        max_tokens=8000,
        messages=[{"role": "user", "content": blueprint_prompt}],
    )
    blueprint = parse_json_from_response(message.choices[0].message.content)

    now = datetime.now(timezone.utc).isoformat()
    app_entry = {
        "id": app_id,
        "name": req.name,
        "description": req.description,
        "tech_stack": req.tech_stack,
        "team_members": req.team_members,
        "github_url": req.github_url,
        "registered_at": now,
        "status": "active",
    }

    apps = get_apps()
    apps.append(app_entry)
    save_apps(apps)
    save_blueprint(app_id, blueprint)

    # Ensure features and chat files exist
    (APPS_DIR / app_id).mkdir(parents=True, exist_ok=True)
    if not (APPS_DIR / app_id / "features.json").exists():
        save_features(app_id, [])
    if not (APPS_DIR / app_id / "chat.json").exists():
        save_chat(app_id, [])

    return {"app": app_entry, "blueprint": blueprint}


@app.get("/api/apps/{app_id}")
async def get_app(app_id: str):
    apps = get_apps()
    app_meta = next((a for a in apps if a["id"] == app_id), None)
    if not app_meta:
        raise HTTPException(status_code=404, detail="App not found")
    blueprint = get_blueprint(app_id)
    return {"app": app_meta, "blueprint": blueprint}


@app.delete("/api/apps/{app_id}")
async def delete_app(app_id: str):
    apps = get_apps()
    apps = [a for a in apps if a["id"] != app_id]
    save_apps(apps)
    app_dir = APPS_DIR / app_id
    if app_dir.exists():
        shutil.rmtree(app_dir)
    return {"ok": True}


@app.get("/api/apps/{app_id}/features")
async def list_features(app_id: str):
    return get_features(app_id)


@app.post("/api/apps/{app_id}/features")
async def create_feature(app_id: str, req: CreateFeatureRequest):
    apps = get_apps()
    app_meta = next((a for a in apps if a["id"] == app_id), None)
    if not app_meta:
        raise HTTPException(status_code=404, detail="App not found")

    blueprint = get_blueprint(app_id)
    arch_overview = blueprint.get("architecture_overview", "")[:500]
    tech_stack = ", ".join(app_meta.get("tech_stack", []))

    spec_prompt = f"""You are a senior developer on the {app_meta['name']} project.
Tech Stack: {tech_stack}
Architecture: {arch_overview}

Feature Request:
Title: {req.title}
Description: {req.description}

Generate a technical spec as JSON:
{{
  "user_story": "As a [user type], I want [feature] so that [benefit]",
  "acceptance_criteria": ["When X, then Y", "..."],
  "technical_approach": "2-3 sentences on how to implement",
  "files_to_modify": ["path/to/file.py"],
  "new_files_needed": ["path/to/new.py"],
  "api_changes": [{{"method": "POST", "path": "/api/...", "description": "..."}}],
  "database_changes": "description or 'None'",
  "testing_requirements": ["Unit test for X", "Integration test for Y"],
  "estimated_complexity": "low|medium|high",
  "estimated_effort": "2 days|1 week|2 weeks",
  "potential_risks": ["Risk 1: ...", "Mitigation: ..."],
  "dependencies": ["Depends on feature X being done first"],
  "definition_of_done": ["Code reviewed", "Tests pass", "Docs updated"]
}}
Return ONLY valid JSON."""

    message = client.chat.completions.create(
        model="gpt-5-mini",
        max_tokens=2000,
        messages=[{"role": "user", "content": spec_prompt}],
    )
    spec = parse_json_from_response(message.choices[0].message.content)

    now = datetime.now(timezone.utc).isoformat()
    feature = {
        "id": str(uuid.uuid4()),
        "title": req.title,
        "description": req.description,
        "created_by": req.created_by,
        "created_at": now,
        "status": "backlog",
        "spec": spec,
        "pipeline_history": [
            {
                "stage": "backlog",
                "at": now,
                "by": req.created_by,
                "action": "created",
            }
        ],
        "approvals": [],
        "test_results": None,
        "comments": [],
        "suggestions": None,
    }

    features = get_features(app_id)
    features.append(feature)
    save_features(app_id, features)

    return feature


@app.post("/api/apps/{app_id}/pipeline/action")
async def pipeline_action(app_id: str, req: PipelineActionRequest):
    apps = get_apps()
    app_meta = next((a for a in apps if a["id"] == app_id), None)
    if not app_meta:
        raise HTTPException(status_code=404, detail="App not found")

    features = get_features(app_id)
    feature = next((f for f in features if f["id"] == req.feature_id), None)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    now = datetime.now(timezone.utc).isoformat()

    if req.action == "advance":
        current_idx = PIPELINE_STAGES.index(feature["status"])
        if current_idx < len(PIPELINE_STAGES) - 1:
            next_stage = PIPELINE_STAGES[current_idx + 1]
            feature["status"] = next_stage
            feature["pipeline_history"].append(
                {
                    "stage": next_stage,
                    "at": now,
                    "by": req.by,
                    "action": "advanced",
                    "comment": req.comment,
                }
            )
            # Run AI test simulation when advancing to testing
            if next_stage == "testing":
                try:
                    test_results = run_ai_test_simulation(
                        feature, app_meta.get("tech_stack", [])
                    )
                    feature["test_results"] = test_results
                except Exception as e:
                    feature["test_results"] = {
                        "overall_status": "warning",
                        "score": 0,
                        "summary": f"Test simulation failed: {str(e)}",
                        "tests": [],
                        "coverage": 0,
                        "suggestions": [],
                        "blockers": [],
                    }

    elif req.action == "reject":
        feature["status"] = "backlog"
        feature["pipeline_history"].append(
            {
                "stage": "backlog",
                "at": now,
                "by": req.by,
                "action": "rejected",
                "comment": req.comment,
            }
        )

    elif req.action == "approve":
        approval_entry = {"by": req.by, "role": req.role, "at": now, "comment": req.comment}
        feature["approvals"].append(approval_entry)
        feature["pipeline_history"].append(
            {
                "stage": feature["status"],
                "at": now,
                "by": req.by,
                "action": "approved",
                "comment": req.comment,
            }
        )

    # Save
    for i, f in enumerate(features):
        if f["id"] == req.feature_id:
            features[i] = feature
            break
    save_features(app_id, features)

    return feature


@app.post("/api/apps/{app_id}/chat")
async def chat(app_id: str, req: ChatRequest):
    apps = get_apps()
    app_meta = next((a for a in apps if a["id"] == app_id), None)
    if not app_meta:
        raise HTTPException(status_code=404, detail="App not found")

    blueprint = get_blueprint(app_id)
    arch = blueprint.get("architecture_overview", "")[:800]
    services_count = len(blueprint.get("services", []))
    endpoints_count = len(blueprint.get("api_endpoints", []))

    system_prompt = (
        f"You are a senior developer and technical advisor for {app_meta['name']}. "
        f"You have deep knowledge of the codebase. "
        f"Project: {app_meta['description']}. "
        f"Architecture: {arch}. "
        f"The system has {services_count} services and {endpoints_count} API endpoints. "
        f"Tech stack: {', '.join(app_meta.get('tech_stack', []))}. "
        f"Be concise, use markdown for code."
    )

    messages = get_chat(app_id)

    # Keep last 20 messages
    history = messages[-20:] if len(messages) > 20 else messages

    # Build message list for API
    api_messages = [{"role": m["role"], "content": m["content"]} for m in history]
    api_messages.append({"role": "user", "content": req.message})

    response = client.chat.completions.create(
        model="gpt-5-mini",
        max_tokens=2000,
        messages=[{"role": "system", "content": system_prompt}] + api_messages,
    )
    assistant_text = response.choices[0].message.content

    now = datetime.now(timezone.utc).isoformat()
    messages.append({"role": "user", "content": req.message, "at": now, "username": req.username})
    messages.append({"role": "assistant", "content": assistant_text, "at": now})

    # Keep last 40 in storage (20 pairs)
    messages = messages[-40:]
    save_chat(app_id, messages)

    return {"response": assistant_text}


@app.get("/api/apps/{app_id}/chat/history")
async def chat_history(app_id: str):
    return get_chat(app_id)


@app.delete("/api/apps/{app_id}/chat/history")
async def clear_chat(app_id: str):
    save_chat(app_id, [])
    return {"ok": True}


@app.post("/api/apps/{app_id}/features/{feature_id}/suggest")
async def get_suggestions(app_id: str, feature_id: str):
    apps = get_apps()
    app_meta = next((a for a in apps if a["id"] == app_id), None)
    if not app_meta:
        raise HTTPException(status_code=404, detail="App not found")

    features = get_features(app_id)
    feature = next((f for f in features if f["id"] == feature_id), None)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    tech_stack = ", ".join(app_meta.get("tech_stack", []))
    spec_summary = json.dumps(feature.get("spec", {}), indent=2)[:1000]

    prompt = (
        f"Provide step-by-step implementation guidance with code examples for:\n\n"
        f"Feature: {feature['title']}\n"
        f"Description: {feature['description']}\n"
        f"Tech Stack: {tech_stack}\n"
        f"Spec Summary: {spec_summary}\n\n"
        f"Include:\n"
        f"1. Implementation steps (numbered)\n"
        f"2. Key code snippets with syntax highlighting\n"
        f"3. Common gotchas to watch for\n"
        f"4. Testing approach\n"
        f"Format using markdown."
    )

    message = client.chat.completions.create(
        model="gpt-5-mini",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    suggestions_text = message.choices[0].message.content

    # Save to feature
    for i, f in enumerate(features):
        if f["id"] == feature_id:
            features[i]["suggestions"] = suggestions_text
            break
    save_features(app_id, features)

    return {"suggestions": suggestions_text}


@app.post("/api/apps/{app_id}/features/{feature_id}/comment")
async def add_comment(app_id: str, feature_id: str, req: CommentRequest):
    features = get_features(app_id)
    feature = next((f for f in features if f["id"] == feature_id), None)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    now = datetime.now(timezone.utc).isoformat()
    comment = {
        "id": str(uuid.uuid4())[:8],
        "text": req.text,
        "author": req.author,
        "at": now,
    }
    feature["comments"].append(comment)

    for i, f in enumerate(features):
        if f["id"] == feature_id:
            features[i] = feature
            break
    save_features(app_id, features)

    return feature


@app.delete("/api/apps/{app_id}/features/{feature_id}")
async def delete_feature(app_id: str, feature_id: str):
    features = get_features(app_id)
    features = [f for f in features if f["id"] != feature_id]
    save_features(app_id, features)
    return {"ok": True}


# ---------------------------------------------------------------------------
# File upload & code explorer
# ---------------------------------------------------------------------------

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss",
    ".java", ".go", ".rs", ".rb", ".php", ".cs", ".cpp", ".c", ".h",
    ".json", ".yaml", ".yml", ".toml", ".env", ".sh", ".bat", ".md",
    ".txt", ".sql", ".xml", ".dockerfile", ".gitignore",
}

def build_file_tree(folder: Path, base: Path) -> list:
    items = []
    try:
        entries = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return items
    for entry in entries:
        rel = str(entry.relative_to(base)).replace("\\", "/")
        if entry.name.startswith(".") or entry.name in SKIP_DIRS:
            continue
        if entry.is_dir():
            items.append({"name": entry.name, "path": rel, "type": "dir", "children": build_file_tree(entry, base)})
        else:
            items.append({"name": entry.name, "path": rel, "type": "file", "ext": entry.suffix.lower(), "size": entry.stat().st_size})
    return items


@app.post("/api/apps/{app_id}/upload")
async def upload_files(app_id: str, files: List[UploadFile] = File(...)):
    """Receive uploaded folder files from browser (webkitdirectory)."""
    apps = get_apps()
    if not any(a["id"] == app_id for a in apps):
        raise HTTPException(status_code=404, detail="App not found")

    files_dir = APPS_DIR / app_id / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for uf in files:
        # filename may be "subfolder/file.py" from webkitRelativePath
        rel_path = uf.filename or "unknown"
        dest = files_dir / Path(rel_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = await uf.read()
        dest.write_bytes(content)
        saved += 1

    return {"saved": saved, "path": str(files_dir)}


@app.get("/api/apps/{app_id}/files")
async def list_files(app_id: str):
    """Return file tree for the uploaded project files."""
    files_dir = APPS_DIR / app_id / "files"
    if not files_dir.exists():
        return {"tree": [], "has_files": False}
    tree = build_file_tree(files_dir, files_dir)
    return {"tree": tree, "has_files": True}


@app.get("/api/apps/{app_id}/file")
async def get_file_content(app_id: str, path: str):
    """Return content of a specific file."""
    files_dir = APPS_DIR / app_id / "files"
    file_path = files_dir / path
    # Security: ensure path stays within files_dir
    try:
        file_path.resolve().relative_to(files_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if file_path.suffix.lower() not in CODE_EXTENSIONS and file_path.stat().st_size > 100_000:
        raise HTTPException(status_code=400, detail="File too large to display")
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return PlainTextResponse(content)


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
