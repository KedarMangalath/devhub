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
- The generated frontend must be impressive, DENSE, and usable before any backend is running.
- MINIMUM 10 pages: home (full landing), explore/catalog, detail, workflow/action, dashboard,
  history/records, login, register, about, settings. Add more domain-specific pages as needed.
- The HOME/LANDING page MUST have ALL of: navbar, hero (with image), logo-cloud, feature grid
  (6+ cards), stats band, testimonials (6+), pricing (3 tiers), FAQ (8+), CTA band, footer.
  This page alone should be 400-600 lines of JSX. DO NOT omit any section.
- Every non-home page must have 6-8 sections. No page should be under 300 lines.
- DESIGN SYSTEM: Pick a strong, opinionated visual direction based on the product domain.
  Options: (a) Clean minimalist SaaS — white/slate, Inter font, subtle shadows, pill badges;
  (b) Bold premium — dark backgrounds, gradient accents, large typography, glassmorphism;
  (c) Warm editorial — cream/tan backgrounds, serif display font, warm accent color;
  (d) Energetic/vibrant — strong color blocks, geometric patterns, high contrast.
  The design system MUST match the product domain — do not default to generic blue-gray.
  Include: specific hex palette (bg, surface, text, primary, accent, muted), Google Fonts pairing
  (display + body), card style, button radius, spacing scale, imagery strategy.
- CONTENT BANK must be large and realistic: 20+ distinct entity names, 10+ status labels,
  8+ metric values, 6+ testimonial quotes, 3 pricing tiers with 6+ features each,
  10+ FAQ pairs, 5+ process steps, 6+ team members (for about page), 8+ partner logos.
- DATA: seed_data_description must specify 30+ primary records, 30+ activity/history records,
  10+ categories, 8+ dashboard KPIs, realistic images from Unsplash.
- USE realistic mock interactions everywhere: search filters, tab switching, selected cards,
  multi-step forms, modal confirmations, dashboard panels, table sorting, pagination.
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
- MINIMUM 10 pages: always include home, explore/catalog, detail, workflow, dashboard, history,
  login, register, about, settings — plus any domain-specific pages needed
- Home page MUST have sections: navbar, hero, logo_cloud, feature_grid, stats_band, testimonials,
  pricing, faq, cta_band, footer — every section fully specified with real content
- Every page must have sections array with AT LEAST 6 sections; home/detail/dashboard need 8-10
- Minimum 8 frontend data collections; each must have minimum_records >= 20 for primary, >= 30 for activity
- Minimum 5 backend data models with realistic field names (created_at, user_id, is_active, etc.)
- Minimum 12 API endpoints covering: auth (login/register/me), CRUD for each model, search, stats
- Every API endpoint has realistic request_body and response_shape
- design_system MUST be opinionated and domain-specific — pick one of the 4 styles from the rules above
  and commit to it: specific hex palette, real Google Fonts names, card border-radius, shadow style
- content_bank must have: 15+ sample_names, 8+ metrics with real values, 6+ testimonial quotes,
  3 pricing tiers with 6+ features each, 10+ FAQ pairs, 5+ workflow steps, 6+ team members
- seed_data_description: 30+ primary records, 30+ activity records, 10+ categories, 8 KPIs
- auth_model: if any user accounts → use "jwt-token"
- If stack is frontend-only: FRONTEND-ONLY MVP RULES override endpoint minimums
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
                    {"name": "primaryItems", "description": "main domain records", "minimum_records": 30, "sample_fields": ["id", "slug", "title", "description", "category", "status", "image", "rating", "price", "tags", "createdAt"]},
                    {"name": "categories", "description": "filter categories/groups", "minimum_records": 10, "sample_fields": ["id", "name", "count", "icon", "color"]},
                    {"name": "activity", "description": "timeline/history/transaction records", "minimum_records": 30, "sample_fields": ["id", "title", "body", "date", "status", "type", "user"]},
                    {"name": "dashboardMetrics", "description": "KPI cards and stats", "minimum_records": 8, "sample_fields": ["label", "value", "detail", "trend", "trendValue", "icon"]},
                    {"name": "userProfile", "description": "demo signed-in user", "minimum_records": 1, "sample_fields": ["name", "email", "role", "avatar", "joinDate", "stats"]},
                    {"name": "testimonials", "description": "customer quotes", "minimum_records": 8, "sample_fields": ["id", "quote", "name", "role", "company", "avatar", "rating"]},
                    {"name": "pricingTiers", "description": "3 pricing plans", "minimum_records": 3, "sample_fields": ["name", "price", "period", "description", "features", "highlighted", "cta"]},
                    {"name": "faqItems", "description": "FAQ Q&A pairs", "minimum_records": 10, "sample_fields": ["question", "answer"]},
                    {"name": "teamMembers", "description": "about page team grid", "minimum_records": 6, "sample_fields": ["name", "role", "bio", "avatar", "linkedin"]},
                    {"name": "processSteps", "description": "how-it-works steps", "minimum_records": 5, "sample_fields": ["step", "title", "description", "icon"]},
                ]
            if not spec.get("design_system"):
                import hashlib
                # Pick design style based on product name hash — ensures variety
                product_name = spec.get("product_name", "App")
                style_idx = int(hashlib.md5(product_name.encode()).hexdigest(), 16) % 4
                design_styles = [
                    {
                        "aesthetic": "Clean modern SaaS — white backgrounds, sharp type, confident primary color, minimal shadows",
                        "typography": {"display": "Plus Jakarta Sans", "body": "Inter"},
                        "palette": {"background": "#ffffff", "surface": "#f8fafc", "text": "#0f172a", "primary": "#6366f1", "accent": "#f59e0b", "muted": "#64748b"},
                        "surface_style": "thin bordered cards, 8px radius, light shadows, tight spacing, colored icon badges",
                        "imagery_strategy": "Unsplash tech/workspace photos, gradient placeholder backgrounds",
                        "interaction_style": "slide-over panels, command palette, inline editing, pill tabs, floating CTAs",
                    },
                    {
                        "aesthetic": "Bold premium dark — near-black backgrounds, bright gradient accents, large type, glassmorphism cards",
                        "typography": {"display": "Syne", "body": "DM Sans"},
                        "palette": {"background": "#09090b", "surface": "#18181b", "text": "#fafafa", "primary": "#a855f7", "accent": "#06b6d4", "muted": "#71717a"},
                        "surface_style": "glass-effect cards with border-white/10, 12px radius, colored glow shadows, backdrop-blur",
                        "imagery_strategy": "Dark moody Unsplash photos with purple/cyan color overlays",
                        "interaction_style": "hover glow effects, animated gradients, sticky headers, full-screen modals",
                    },
                    {
                        "aesthetic": "Warm editorial — cream/sand backgrounds, serif display font, terracotta accent, organic layouts",
                        "typography": {"display": "Playfair Display", "body": "Source Sans 3"},
                        "palette": {"background": "#fdf8f3", "surface": "#fff9f4", "text": "#1c1209", "primary": "#c2410c", "accent": "#d97706", "muted": "#78716c"},
                        "surface_style": "warm-toned cards, 6px radius, hairline borders, generous padding, editorial whitespace",
                        "imagery_strategy": "Warm-toned Unsplash lifestyle photos, illustrated icon accents",
                        "interaction_style": "smooth scroll, full-bleed sections, parallax hero, magazine-style grid",
                    },
                    {
                        "aesthetic": "Energetic vibrant — strong color blocks, bold type, high contrast, geometric shapes",
                        "typography": {"display": "Space Grotesk", "body": "Nunito"},
                        "palette": {"background": "#f0fdf4", "surface": "#ffffff", "text": "#052e16", "primary": "#16a34a", "accent": "#dc2626", "muted": "#6b7280"},
                        "surface_style": "bold bordered cards, 4px radius, thick colored borders, block shadows, vibrant fills",
                        "imagery_strategy": "High-saturation Unsplash photos with green/red accent overlays",
                        "interaction_style": "chunky buttons, tag filters, bold section headers, action-first layouts",
                    },
                ]
                spec["design_system"] = design_styles[style_idx]
            if not spec.get("content_bank"):
                spec["content_bank"] = {
                    "headlines": [
                        f"The smarter way to manage {spec.get('product_name', 'your workflow')}",
                        "Built for teams who move fast",
                        "Everything you need, nothing you don't",
                    ],
                    "metrics": ["10,000+ users", "4.9/5 rating", "99.9% uptime", "50+ integrations"],
                    "sample_names": [],
                    "workflow_steps": ["Choose", "Configure", "Review", "Confirm", "Track"],
                    "testimonials_or_notes": [
                        "This product completely transformed how our team works.",
                        "I can't imagine going back to our old process.",
                        "Setup took 5 minutes. Results were immediate.",
                    ],
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
