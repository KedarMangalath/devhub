import json
from agents.core.base import BaseAgent
from agents.coding.stack_conventions import get_conventions, build_constraint_block


class FilePlanAgent(BaseAgent):
    """
    Stage 2: Given a product spec + stack conventions, produces an ordered
    file plan where each entry is a precise, self-contained contract.

    Every file descriptor tells FileCodeAgent exactly what to write:
    - exact imports to use
    - exact field names from the spec
    - exact API paths to call
    - props interface if it's a component

    This eliminates import inconsistency and route mismatch at the source.
    """

    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="Technical Lead",
            system_instruction=(
                "You are a technical lead producing an implementation-ready file plan. "
                "Each file descriptor must be so specific that a junior engineer could write "
                "the file correctly without reading anything else. "
                "Vague descriptions like 'Doctor views' are forbidden — write 'FastAPI router "
                "with GET /api/doctors/ returning DoctorResponse list, GET /api/doctors/{id} "
                "returning single DoctorResponse, both requiring Depends(get_db).' "
                "Return ONLY valid JSON with no markdown fences."
            ),
            ai_config=ai_config,
        )

    def plan(self, spec: dict, tech_stack: str, wireframes: dict | None = None) -> list[dict]:
        conventions = get_conventions(tech_stack)
        constraint_block = build_constraint_block(tech_stack)
        frontend_only = not bool(conventions.get("backend_framework"))
        has_react_frontend = "react" in str(conventions.get("frontend_framework", "")).lower()
        frontend_prefix = "" if conventions.get("frontend_dir", ".") == "." else f"{conventions.get('frontend_dir', 'frontend')}/"
        mock_data_path = f"{frontend_prefix}src/mockData.js"
        frontend_demo_requirements = (
            f"""
FRONTEND-FIRST DEMO REQUIREMENTS:
- Generate `{mock_data_path}` as a rich local demo data layer before components/pages.
- This requirement applies even when the stack includes a backend. The frontend must look complete
  and work on first load while backend APIs are still installing, down, empty, or unfinished.
- `{mock_data_path}` must export rich arrays and helper lookups for the inferred product domain:
  15+ primary records, 20+ activity/history records, 8+ categories/statuses/metrics,
  a user/account profile, dashboard summaries, route-friendly IDs/slugs, and realistic image URLs.
- Plan a complete multi-page app, not a landing page. Include at least 6 routed pages:
  home/overview, primary list/catalog/workspace, primary detail, main action flow,
  dashboard/account/workspace, and history/records/settings/admin as fits the domain.
- Add shared UI components for app shell/navigation, rich cards, metrics, tabs, timelines/lists,
  status pills, filters/search, workflow summaries, and empty-state-free section layouts.
- Dashboard pages must have 3-4 populated tabs or panels backed by mock data.
- Main action pages must simulate a real workflow with local state, forms, selections,
  confirmations, and visible results.
- Pages and components must import from `{mock_data_path}` and use local React state for filters,
  bookings, carts, dashboards, chat/messages, records, uploads, and demo interactions.
- Backend-connected stacks may also include an API client, but pages must not depend on it for first
  render. If an API helper is generated, it must fall back to mock data on network/backend failure.
- Do not render blank grids, "no records yet", permanent spinners, or login-blocked dashboards
  in the starter app unless the user explicitly asked for an empty-state prototype.
- Keep labels and routes domain-adaptive. Do not use healthcare-specific names unless
  the user's app idea is healthcare.
"""
            if has_react_frontend
            else ""
        )
        frontend_only_requirements = (
            """
FRONTEND-ONLY MOCK DATA REQUIREMENTS:
- Generate src/mockData.js as a frontend data layer before components/pages.
- It must export rich arrays and helper lookups for the inferred product domain:
  15+ primary records, 20+ activity/history records, 8+ categories/statuses/metrics,
  a user/account profile, dashboard summaries, and realistic image URLs.
- Plan a complete multi-page app, not a landing page. Include at least 6 routed pages:
  home/overview, primary list/catalog/workspace, primary detail, main action flow,
  dashboard/account/workspace, and history/records/settings/admin as fits the domain.
- Add shared UI components for layout/navigation, cards, metrics, tabs, timelines/lists,
  status pills, filters/search, and workflow summaries.
- Dashboard pages must have 3-4 tabs or panels backed by mock data.
- Main action pages must simulate a real workflow with local state, forms, selections,
  confirmations, and visible results.
- Do not generate backend files, API clients, axios/fetch wrappers, proxy config,
  localhost URLs, or network calls.
- Pages and components import from src/mockData.js and use local React state for filters,
  bookings, carts, dashboards, chat/messages, records, uploads, and demo interactions.
- Keep labels and routes domain-adaptive. Do not use healthcare-specific names unless
  the user's app idea is healthcare.
"""
            if frontend_only
            else ""
        )

        models_summary = "\n".join(
            f"  {m['name']}: {', '.join(f['name']+':'+f['type'] for f in m.get('fields', []))}"
            for m in spec.get("data_models", [])
        )
        endpoints_summary = "\n".join(
            f"  {e['method']} {e['path']} → {e.get('handler','')} — req:{e.get('request_body',{})} resp:{e.get('response_shape',{})}"
            for e in spec.get("api_endpoints", [])
        )
        pages_summary = "\n".join(
            f"  {p['route']} {p['name']}: components={p.get('components',[])} calls={p.get('api_calls',[])}"
            for p in spec.get("pages", [])
        )

        wireframe_summary = ""
        if wireframes:
            wf_lines = []
            for route, wf in list(wireframes.items())[:8]:
                if not isinstance(wf, dict):
                    continue
                section_kinds = [s.get("kind", "") for s in wf.get("sections", []) if isinstance(s, dict)]
                wf_lines.append(f"  {route} ({wf.get('name', '')}): {' → '.join(section_kinds)}")
            wireframe_summary = "Page wireframes (section order for each page):\n" + "\n".join(wf_lines)

        prompt = f"""Produce a complete ordered file plan for this project.

{constraint_block}

PRODUCT SPEC:
Name: {spec.get('product_name')} — {spec.get('tagline')}
Auth: {spec.get('auth_model', 'none')}

Data models:
{models_summary}

API endpoints:
{endpoints_summary}

Pages:
{pages_summary}

{wireframe_summary}

Key user flows:
{chr(10).join(spec.get('key_user_flows', []))}

Design system:
{json.dumps(spec.get('design_system', {}), indent=2)}

Frontend data collections:
{json.dumps(spec.get('frontend_data_collections', []), indent=2)}

Content bank:
{json.dumps(spec.get('content_bank', {}), indent=2)}

{frontend_demo_requirements}

{frontend_only_requirements}

Return a JSON ARRAY of file descriptors ordered by dependency (lowest deps first).
Each descriptor:
{{
  "path": "relative/path/to/file.ext",
  "layer": "config|model|schema|view|url|seed|frontend-config|frontend-api|component|page|entry",
  "depends_on": ["path/to/dep.ext"],
  "description": "COMPLETE file contract — see rules below",
  "exact_imports": ["from database import engine, SessionLocal, Base", "from models import Doctor"],
  "max_lines": 200
}}

DESCRIPTION FIELD RULES (this is the most important field):
1. For Python backend files: list every class/function with its signature, what it imports, what it does.
   Good: "SQLAlchemy models for Doctor(id,name,specialty,bio,experience_years,rating,image_url,created_at), Service(id,name,description,icon,price), Appointment(id,patient_name,patient_email,date,time,notes,status,doctor_id FK→Doctor,created_at). Import from database import Base. All fields specified, no omissions."
   Bad: "Django models for the app"
2. For frontend API layer: list every exported function with its HTTP method, path, params, return type.
   Good: "Axios client. Exports: getDoctors(specialty?,page?) → GET /api/doctors/?specialty=X&page=Y, getDoctor(id) → GET /api/doctors/{id}/, createAppointment(data) → POST /api/appointments/, getMyAppointments(token) → GET /api/appointments/me/ with Authorization header."
   Bad: "API utility functions"
3. For React components: list props interface, what API it calls, what state it manages.
   Good: "DoctorCard component. Props: {{doctor: {{id,name,specialty,bio,rating,image_url}}, onBook: (doctor)=>void}}. Renders doctor image, name, specialty Badge, star rating, 'Book' Button. Import Card from components/ui/card, Badge from components/ui/badge, Button from components/ui/button."
   Bad: "Component for displaying a doctor"
   IMPORTANT: UI primitives (Button, Card, CardHeader, CardContent, CardTitle, CardDescription, CardFooter, Badge, Input, Label, Textarea, Separator, Avatar, Skeleton, Progress, Tabs/TabsList/TabsTrigger/TabsContent, Select, Dialog, Sheet) are pre-built in src/components/ui/. Reference them in descriptions; do NOT plan files for them.
4. For pages: list route, all wireframe sections to render in order, components used, state variables.
   IMPORTANT: Page descriptions MUST reference the wireframe sections for that route.
5. For seed files: describe exact number and shape of records to insert.
   Good: "Seed 15 doctors across 6 specialties (Cardiology, Neurology, Pediatrics, Dermatology, Orthopedics, Psychiatry) with realistic names, bios, ratings 4.0-5.0, experience 3-20 years. Seed 8 services. Seed 20 appointments across different doctors and statuses."

FILE SIZING RULE: max_lines is a hard cap. If a file would exceed it, SPLIT it:
- Large models.py → models/user.py + models/doctor.py + models/appointment.py + models/__init__.py
- Large App.jsx → App.jsx (router only) + separate page files
- Large seed.py is OK up to 300 lines
Set max_lines: 250 for most files, 300 for seed, 150 for components.

ORDERING RULES:
Backend: requirements.txt → database/settings → models → schemas/serializers → auth → routers → main/urls → seed
Frontend: package.json → configs → mockData → optional api client → shared components → page-specific components → pages → App → main entry → css

{self._stack_specific_rules(conventions)}

Generate ALL files needed for a complete, working, runnable app. Do not omit any file.
Required files per conventions: {conventions.get('required_files', [])}
"""
        raw = self.generate(prompt=prompt)
        result = self.parse_json(raw)
        if isinstance(result, list):
            return result
        for key in ("files", "plan", "file_plan", "items"):
            if key in result and isinstance(result[key], list):
                return result[key]
        return []

    def _stack_specific_rules(self, conventions: dict) -> str:
        import_style = conventions.get("import_style", "flat")
        lines = ["STACK-SPECIFIC RULES FOR THIS PROJECT:"]

        if import_style == "flat":
            lines += [
                "- Backend import style: FLAT. Files import each other without package prefix.",
                f"  `from database import engine` ✓   `from backend.database import engine` ✗",
                f"  `from models import Doctor` ✓       `from backend.models import Doctor` ✗",
                "- exact_imports field must reflect this — no 'backend.' prefix ever.",
                f"- Backend runs as: {conventions.get('backend_run')}",
            ]
        elif import_style == "django_apps":
            lines += [
                "- Backend uses Django app structure. Intra-app imports use relative style.",
                "  `from .models import Doctor` ✓   `from api.models import Doctor` (only cross-app)",
                f"- Backend runs as: {conventions.get('backend_run')}",
            ]

        if conventions.get("vite_proxy"):
            lines += [
                f"- Frontend API calls: use path only, NO hostname. `/api/doctors/` not `http://localhost:8000/api/doctors/`",
                f"- vite.config.js MUST include proxy: {{ '/api': {{ target: 'http://localhost:{conventions.get('backend_port', 8000)}', changeOrigin: true }} }}",
                f"- Vite version: {conventions.get('vite_version', '^4.5.2')} (NOT 5.x — Windows compatibility)",
                "- Also generate `frontend/src/mockData.js` and make React pages render from it by default.",
                "- API client functions must be optional enhancement/fallback-aware, not required for first render.",
                "- Frontend pages must not show blank data or permanent error states when the backend is down.",
            ]

        if conventions.get("import_style") == "frontend_mock":
            lines += [
                "- Frontend-only mock data stack: generate no backend files and no API client file.",
                "- Add `src/mockData.js` with rich domain-specific arrays and helper lookups before components/pages.",
                "- Components and pages must import data from `src/mockData.js`; do not use fetch, axios, proxy settings, localhost URLs, or empty loading/error states.",
                "- Plan at least 6 real routed pages for non-trivial apps: home, list/workspace, detail, main action flow, dashboard, and history/settings/admin as fits the domain.",
                "- Include shared components for app shell/navigation, cards, metrics, tabs, timeline/activity, filters/search, and workflow summaries.",
                "- Dashboard/workspace pages must include 3-4 populated tabs or panels using mock data.",
                "- Main action flow pages must simulate the core product workflow with local state, forms/selections, confirmation, and result UI.",
                "- Keep routes, copy, data names, and examples domain-adaptive; do not use healthcare-specific labels unless the prompt is healthcare.",
                "- package.json dependencies must include lucide-react and must not include axios, @heroicons/react, or @mui/icons-material.",
            ]

        exts = conventions.get("file_extensions", {})
        lines.append(f"- File extensions: components={exts.get('components','.jsx')}, pages={exts.get('pages','.jsx')}")

        if conventions.get("vite_version"):
            lines.append("- package.json scripts must be: dev:vite build:vite build preview:vite preview")

        return "\n".join(lines)
