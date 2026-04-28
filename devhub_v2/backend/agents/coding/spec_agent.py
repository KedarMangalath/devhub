import json
from agents.core.base import BaseAgent
from agents.coding.stack_conventions import get_conventions, build_constraint_block


class SpecAgent(BaseAgent):
    """
    Stage 1: Expands a single-line description into a full product spec.

    The tech_stack is treated as a hard constraint — the agent designs the
    product (pages, models, flows, endpoints) but never overrides the stack.
    """

    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="Product Architect",
            system_instruction=(
                "You are a senior product architect. Given a short app description and a fixed "
                "tech stack, you produce a complete, concrete product specification that a team "
                "of engineers can build from immediately. "
                "Be specific: name real pages, realistic data collections with real field names, "
                "and API endpoints only when the fixed stack includes a backend. "
                "Infer sensible product defaults — do not ask clarifying questions. "
                "You design the PRODUCT, not the tech stack. The stack is given and fixed. "
                "Return ONLY valid JSON with no markdown fences."
            ),
            ai_config=ai_config,
        )

    def expand(self, description: str, tech_stack: str) -> dict:
        conventions = get_conventions(tech_stack)
        constraint_block = build_constraint_block(tech_stack)
        frontend_only = not bool(conventions.get("backend_framework"))
        frontend_demo_rules = """
FRONTEND EXPERIENCE RULES (apply whenever the stack has a frontend):
- The generated frontend must be impressive and usable before any backend is running.
- Design a frontend-first demo data layer even for full-stack apps. Backend APIs may exist, but
  React pages must render rich local mock data immediately and must never collapse into empty
  lists, "failed to load", or login walls when the API is unavailable.
- Every non-trivial product needs at least 6 routes: home/overview, primary list/catalog/workspace,
  primary detail, main action workflow, dashboard/account/workspace, and history/records/settings/admin
  as appropriate to the domain.
- Every major page should have 4-7 concrete sections or panels. Examples: hero, filters,
  featured records, process steps, comparison grid, detail summary, timeline, dashboard tabs,
  activity feed, trust/privacy block, checkout/booking/application flow, records/history table.
- Include a frontend content bank with realistic names, entities, dates, ratings, stats,
  images, statuses, messages, testimonials, notes, and CTA labels. It must be domain-adaptive;
  do not hardcode healthcare unless the user's idea is healthcare.
- Include a design system: visual direction, typography pairing, palette, surface/card style,
  button style, icon strategy, and imagery strategy. Avoid generic blue-gray admin UI.
- Use real-feeling mock interactions: search, filters, tabs, selected states, forms, confirmations,
  saved/draft states, dashboard metrics, and populated detail pages.
"""

        backend_rules = (
            """
FRONTEND-ONLY MVP RULES:
- Build a polished working UI with rich local mock data. Do NOT design a backend.
- api_endpoints MUST be an empty array.
- Every page api_calls MUST be an empty array.
- data_models means frontend demo-data entities, not database tables.
- For any non-trivial product, design a dense multi-page starter with at least 6 routes:
  home/overview, primary directory/list, primary detail, action workflow, user dashboard/workspace,
  and history/records/settings/admin as appropriate to the domain.
- The dashboard/workspace route must include 3-4 real panels or tabs backed by mock data, such as
  scheduled items, messages/activity, saved items, records/history, analytics, orders, tasks, or insights.
- Include an end-to-end mock workflow route for the product's main action: booking, checkout,
  onboarding, application, planning, publishing, reservation, intake, or an equivalent domain action.
- Keep the domain generic and adaptive. Do not hardcode healthcare, doctors, bookings, prescriptions,
  or records unless the user's app idea is actually healthcare.
- seed_data_description must describe the exact rich mock data needed in src/mockData.js:
  at least 15 primary records, 20 secondary/activity records, 8 category/status/metric records,
  a user/account profile, dashboard summaries, realistic names, images, prices/statuses/ratings/dates
  appropriate to the product.
- Auth, payments, real chat, persistence, and database behavior should be represented as
  convincing UI states backed by mock data, not network calls.
"""
            if frontend_only
            else """
BACKEND-CONNECTED RULES:
- Design real API endpoints with request/response shapes for every meaningful user action.
- data_models means backend persistence models.
- seed_data_description must describe realistic records for the backend seed script.
- The frontend still needs a local src/mockData.js-style demo dataset and should be fully populated
  from that data by default. API helpers may exist, but they must not be required for first render.
- Frontend page api_calls may list intended backend integrations, but the page contract must also
  include the local mock data collections it displays.
"""
        )

        prompt = f"""Expand this app idea into a complete product specification.

{constraint_block}

App idea: {description}

The tech_stack field in your response MUST exactly match the constraint above.
Do NOT substitute frameworks. Do NOT choose Next.js if the constraint says React+Vite.
Do NOT choose FastAPI if the constraint says Django.
{frontend_demo_rules}
{backend_rules}

Return a JSON object with EXACTLY this structure:

{{
  "product_name": "short product name",
  "tagline": "one-sentence value proposition",
  "tech_stack": {{
    "frontend": "{conventions['frontend_framework']}",
    "backend": "{conventions.get('backend_framework', 'none')}",
    "notes": "any product-specific notes (not stack changes)"
  }},
  "personas": [
    {{"name": "persona name", "description": "who they are and what they need"}}
  ],
  "pages": [
    {{
      "route": "/route",
      "name": "PageName",
      "purpose": "what the user does on this page",
      "sections": [
        {{"kind": "hero|filters|grid|detail|workflow|dashboard|timeline|trust|cta|footer", "intent": "what this section shows", "data_used": ["collectionName"]}}
      ],
      "components": ["ExactComponentName", "AnotherComponent"],
      "api_calls": ["GET /api/resource", "POST /api/resource"]
    }}
  ],
  "data_models": [
    {{
      "name": "ModelName",
      "fields": [
        {{"name": "id", "type": "integer", "required": true, "notes": "primary key"}},
        {{"name": "field_name", "type": "string|integer|text|boolean|datetime|fk:OtherModel|decimal", "required": true, "notes": ""}}
      ],
      "description": "what this model represents"
    }}
  ],
  "api_endpoints": [
    {{
      "method": "GET|POST|PUT|DELETE|PATCH",
      "path": "/api/resource/",
      "handler": "HandlerName",
      "purpose": "exact description of what it does",
      "auth_required": false,
      "request_body": {{"field": "type"}},
      "response_shape": {{"field": "type"}}
    }}
  ],
  "auth_model": "none | jwt-token | session — describe the approach",
  "seed_data_description": "describe 10+ realistic records per model for demo purposes",
  "design_system": {{
    "aesthetic": "short concrete visual direction, not generic",
    "typography": {{"display": "Google font or system display choice", "body": "Google font or system body choice"}},
    "palette": {{"background": "#hex", "surface": "#hex", "text": "#hex", "primary": "#hex", "accent": "#hex", "muted": "#hex"}},
    "surface_style": "cards, borders, shadows, radius, spacing",
    "imagery_strategy": "Unsplash/picsum/dicebear strategy with domain keywords",
    "interaction_style": "tabs, pills, cards, drawers, forms, etc."
  }},
  "frontend_data_collections": [
    {{"name": "collectionName", "description": "what records it contains", "minimum_records": 8, "sample_fields": ["id", "title", "status"]}}
  ],
  "content_bank": {{
    "headlines": ["domain-specific headline"],
    "metrics": ["metric labels and values"],
    "sample_names": ["realistic names/entities"],
    "workflow_steps": ["step label"],
    "testimonials_or_notes": ["short realistic note"]
  }},
  "key_user_flows": [
    "Flow 1: User visits home → sees X → clicks Y → does Z",
    "Flow 2: ..."
  ]
}}

Rules for a high-quality spec:
- Minimum 6 pages/routes for any non-trivial app with a frontend, even if it also has a backend
- Frontend-only routes must include: home, list/catalog/workspace, detail, main action flow,
  dashboard/account, and history/records/settings/admin where relevant
- Minimum 5 frontend data collections for apps with a frontend: primary records, categories/statuses,
  activity/history, dashboard metrics, and user/account/profile data
- Minimum 3 backend data models/data collections with real field names (e.g. created_at, user_id, is_active)
- Minimum 8 API endpoints — one per meaningful user action, not just CRUD
- Every page must include a sections array with at least 4 sections/panels for important pages
- Every page lists EVERY component it renders by name
- Every API endpoint has a realistic request_body and response_shape
- For a healthcare app: home, doctor directory with filters, doctor profile+booking, patient dashboard, services page
- For e-commerce: home, product catalog with filters, product detail, cart, checkout, order history
- For any other domain, infer the equivalent: marketplace/listing, project/workspace, entity detail,
  action flow, dashboard, history/insights/settings. Never leave this as a generic landing page.
- api_calls in pages must EXACTLY match paths in api_endpoints — no mismatches
- auth_model must be realistic: if app has user accounts, specify jwt-token or session
- If the stack is frontend-only, the FRONTEND-ONLY MVP RULES override endpoint minimums.
"""
        raw = self.generate(prompt=prompt)
        spec = self.parse_json(raw)

        # Enforce stack — overwrite whatever the LLM wrote
        spec["tech_stack"] = {
            "frontend": conventions["frontend_framework"],
            "backend": conventions.get("backend_framework") or "none",
            "notes": spec.get("tech_stack", {}).get("notes", ""),
        }
        spec["_conventions_key"] = conventions.get("label", "")

        # Ensure minimum shape
        for key in ("pages", "data_models", "api_endpoints", "personas", "key_user_flows", "frontend_data_collections"):
            if not isinstance(spec.get(key), list):
                spec[key] = []

        if not isinstance(spec.get("design_system"), dict):
            spec["design_system"] = {}
        if not isinstance(spec.get("content_bank"), dict):
            spec["content_bank"] = {}

        if frontend_only:
            spec["api_endpoints"] = []
            spec["auth_model"] = "mock-ui-only"
            for page in spec["pages"]:
                if isinstance(page, dict):
                    page["api_calls"] = []
            if not spec.get("seed_data_description"):
                spec["seed_data_description"] = (
                    "Create rich frontend mock data in src/mockData.js with at least 15 primary "
                    "records and 20 activity/transaction/appointment-style records using realistic "
                    "names, statuses, dates, ratings, prices, and picsum.photos image URLs."
                )

        if "react" in str(conventions.get("frontend_framework", "")).lower():
            if not spec.get("frontend_data_collections"):
                spec["frontend_data_collections"] = [
                    {"name": "primaryItems", "description": "main domain records displayed in list/detail pages", "minimum_records": 15, "sample_fields": ["id", "title", "category", "status", "image", "rating"]},
                    {"name": "categories", "description": "filters, specialties, product groups, services, or statuses", "minimum_records": 8, "sample_fields": ["id", "name", "count", "icon"]},
                    {"name": "activity", "description": "timeline, messages, bookings, orders, reports, or history records", "minimum_records": 20, "sample_fields": ["id", "title", "date", "status", "description"]},
                    {"name": "dashboardMetrics", "description": "summary cards and insight metrics", "minimum_records": 8, "sample_fields": ["label", "value", "detail", "trend"]},
                    {"name": "userProfile", "description": "signed-in demo profile and preferences", "minimum_records": 1, "sample_fields": ["name", "email", "role", "avatar"]},
                ]
            if not spec.get("design_system"):
                spec["design_system"] = {
                    "aesthetic": "premium editorial product UI with warm surfaces, confident contrast, and domain-specific imagery",
                    "typography": {"display": "Fraunces", "body": "Inter"},
                    "palette": {"background": "#f8f3ea", "surface": "#fffdf8", "text": "#10251f", "primary": "#10251f", "accent": "#f18455", "muted": "#5a6c64"},
                    "surface_style": "soft bordered cards, rounded panels, subtle shadows, generous whitespace, compact action pills",
                    "imagery_strategy": "Unsplash hero/detail images with picsum.photos seeded fallback",
                    "interaction_style": "tabs, pills, cards, sticky summaries, search filters, multi-step forms, and confirmations",
                }
            if not spec.get("content_bank"):
                spec["content_bank"] = {
                    "headlines": ["A polished, complete product experience built from realistic demo data"],
                    "metrics": ["15+ records", "20+ activity items", "4 dashboard panels"],
                    "sample_names": [],
                    "workflow_steps": ["Choose", "Review", "Confirm", "Track"],
                    "testimonials_or_notes": ["Demo data should feel specific to this product, not placeholder copy"],
                }
            for page in spec.get("pages", []):
                if isinstance(page, dict) and not isinstance(page.get("sections"), list):
                    page["sections"] = [
                        {"kind": "hero", "intent": "introduce the page value and primary action", "data_used": ["content_bank"]},
                        {"kind": "filters", "intent": "let users narrow or switch the visible data", "data_used": ["categories"]},
                        {"kind": "grid", "intent": "show populated domain records", "data_used": ["primaryItems"]},
                        {"kind": "timeline", "intent": "show recent or upcoming activity", "data_used": ["activity"]},
                    ]

        return spec
