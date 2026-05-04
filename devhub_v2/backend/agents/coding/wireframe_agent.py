"""
WireframeAgent — Stage 1.5 of the scaffold pipeline.

Converts spec pages into concrete, section-by-section wireframes with
populated prop data drawn from the spec's content_bank and design_system.

The 25-kind section catalogue is framework-agnostic — every stack (React,
Vue, Svelte, Next.js, Astro, etc.) consumes the same wireframe JSON.
FileCodeAgent renders from the wireframe; no LLM freestyling per section.
"""
from __future__ import annotations

import json
import logging
from agents.core.base import BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section catalogue — 25 kinds with required/optional prop shapes
# ---------------------------------------------------------------------------

SECTION_CATALOGUE = {
    # ── Navigation ────────────────────────────────────────────────────────
    "navbar": {
        "desc": "Top navigation bar with logo, links, and optional CTA.",
        "required": ["logo", "links"],
        "optional": ["cta_label", "cta_href", "theme"],
    },
    # ── Hero variants ─────────────────────────────────────────────────────
    "hero": {
        "desc": "Full-width hero with headline, sub, CTAs, optional image.",
        "required": ["headline", "sub", "cta_primary"],
        "optional": ["badge", "cta_secondary", "image", "video_src"],
        "rules": {"headline": ">=40 chars", "sub": ">=80 chars"},
    },
    "hero_split": {
        "desc": "50/50 hero split — text left, image right.",
        "required": ["headline", "sub", "cta_primary", "image"],
        "optional": ["badge", "cta_secondary"],
        "rules": {"headline": ">=40 chars", "sub": ">=80 chars"},
    },
    # ── Trust / social proof ──────────────────────────────────────────────
    "logo_cloud": {
        "desc": "Row of partner/customer logos with label.",
        "required": ["label", "logos"],
        "rules": {"logos": ">=5 items"},
    },
    "stats_band": {
        "desc": "Horizontal band of impressive numeric stats.",
        "required": ["items"],
        "rules": {"items": ">=3 items, each with value+label+detail"},
    },
    "testimonials": {
        "desc": "Grid or carousel of customer quotes.",
        "required": ["headline", "items"],
        "rules": {"items": ">=3 items, each with quote+name+role+avatar"},
    },
    # ── Feature / content ────────────────────────────────────────────────
    "feature_grid": {
        "desc": "Grid of feature cards with icon, title, body.",
        "required": ["headline", "items"],
        "optional": ["sub", "cols"],
        "rules": {"items": ">=6 items, each with icon+title+body(>=60 chars)"},
    },
    "bento_grid": {
        "desc": "Asymmetric bento-box feature grid with mixed card sizes.",
        "required": ["headline", "items"],
        "optional": ["sub"],
        "rules": {"items": ">=5 items, each with title+body+size(sm|md|lg)+icon"},
    },
    "pricing": {
        "desc": "Pricing tiers with feature lists and CTAs.",
        "required": ["headline", "tiers"],
        "optional": ["sub", "toggle_label"],
        "rules": {"tiers": "2-4 tiers, each with name+price+description+features[]+cta"},
    },
    "faq": {
        "desc": "Accordion FAQ section.",
        "required": ["headline", "items"],
        "optional": ["sub"],
        "rules": {"items": ">=6 items, each with question+answer(>=60 chars)"},
    },
    "cta_band": {
        "desc": "Full-width CTA band to drive conversions.",
        "required": ["headline", "cta_primary"],
        "optional": ["sub", "cta_secondary", "bg_tone"],
    },
    "footer": {
        "desc": "Site footer with links, brand, legal.",
        "required": ["brand", "link_groups", "legal"],
    },
    # ── List / browse ─────────────────────────────────────────────────────
    "list_filters": {
        "desc": "Search bar + filter pills above a list/grid.",
        "required": ["title", "filters", "empty_message"],
        "rules": {"filters": ">=4 filter pills"},
    },
    "list_grid": {
        "desc": "Responsive grid of item cards drawn from mock data.",
        "required": ["items"],
        "rules": {"items": ">=8 items, each with id+title+meta+status+image"},
    },
    "list_table": {
        "desc": "Sortable table view of records.",
        "required": ["columns", "sample_rows"],
        "rules": {"columns": ">=4 columns; sample_rows>=5"},
    },
    # ── Detail page ───────────────────────────────────────────────────────
    "detail_hero": {
        "desc": "Large hero for a single entity detail page.",
        "required": ["title", "image", "meta_items", "cta"],
        "optional": ["sub", "rating", "badge"],
    },
    "detail_meta": {
        "desc": "Metadata / info sections below the detail hero.",
        "required": ["sections"],
        "rules": {"sections": ">=2 sections each with label+items[]"},
    },
    "sticky_summary": {
        "desc": "Sticky sidebar/bottom bar with price, action, and key meta.",
        "required": ["title", "price_or_action", "cta", "meta_items"],
    },
    # ── Workflow / forms ──────────────────────────────────────────────────
    "multi_step_form": {
        "desc": "Multi-step wizard: selection → config → review → confirm.",
        "required": ["steps", "cta_submit"],
        "rules": {"steps": ">=3 steps each with label+fields[]"},
    },
    # ── Dashboard / app ───────────────────────────────────────────────────
    "dashboard_kpi": {
        "desc": "Row of KPI / metric cards at top of dashboard.",
        "required": ["cards"],
        "rules": {"cards": ">=4 cards each with label+value+trend+icon"},
    },
    "dashboard_tabs": {
        "desc": "Tabbed panels inside a dashboard.",
        "required": ["tabs"],
        "rules": {"tabs": ">=3 tabs each with label+panel_kind"},
    },
    "timeline": {
        "desc": "Vertical timeline of events / activity.",
        "required": ["title", "items"],
        "rules": {"items": ">=5 items each with date+title+body+status"},
    },
    "messages_panel": {
        "desc": "Conversation list or message thread panel.",
        "required": ["conversations"],
        "rules": {"conversations": ">=4 items each with name+preview+time+unread"},
    },
    # ── Misc ──────────────────────────────────────────────────────────────
    "settings_form": {
        "desc": "Grouped settings/profile form.",
        "required": ["sections"],
        "rules": {"sections": ">=2 sections each with label+fields[]"},
    },
    "empty_state": {
        "desc": "Graceful empty state with icon, message, and action.",
        "required": ["icon", "headline", "sub", "cta"],
    },
}

CATALOGUE_SUMMARY = "\n".join(
    f"  {kind}: {meta['desc']}" for kind, meta in SECTION_CATALOGUE.items()
)


# ---------------------------------------------------------------------------
# Default section plans per page pattern
# ---------------------------------------------------------------------------

_LANDING_SECTIONS = [
    "navbar", "hero", "logo_cloud", "feature_grid", "stats_band",
    "testimonials", "pricing", "faq", "cta_band", "footer",
]
_LIST_SECTIONS = ["list_filters", "list_grid"]
_DETAIL_SECTIONS = ["detail_hero", "detail_meta", "sticky_summary", "timeline"]
_WORKFLOW_SECTIONS = ["multi_step_form"]
_DASHBOARD_SECTIONS = ["dashboard_kpi", "dashboard_tabs", "timeline"]
_HISTORY_SECTIONS = ["list_filters", "list_table", "timeline"]
_SETTINGS_SECTIONS = ["settings_form"]

def _default_sections_for_route(route: str, name: str) -> list[str]:
    r = route.lower()
    n = name.lower()
    if r in ("/", "") or n in ("home", "landing", "index"):
        return _LANDING_SECTIONS
    if any(x in r or x in n for x in ("dashboard", "workspace", "account")):
        return _DASHBOARD_SECTIONS
    if any(x in r or x in n for x in ("explore", "list", "catalog", "browse", "search", "directory")):
        return _LIST_SECTIONS + ["list_table"]
    if any(x in r or x in n for x in (":id", "detail", "profile", "view", "item")):
        return _DETAIL_SECTIONS
    if any(x in r or x in n for x in ("book", "checkout", "workflow", "wizard", "apply", "order", "onboard")):
        return _WORKFLOW_SECTIONS + ["sticky_summary"]
    if any(x in r or x in n for x in ("history", "record", "report", "activity", "log")):
        return _HISTORY_SECTIONS
    if any(x in r or x in n for x in ("setting", "profile", "account", "preference")):
        return _SETTINGS_SECTIONS + ["dashboard_kpi"]
    return ["hero", "feature_grid", "list_grid", "cta_band"]


# ---------------------------------------------------------------------------
# WireframeAgent
# ---------------------------------------------------------------------------

class WireframeAgent(BaseAgent):
    """
    Stage 1.5: Converts spec pages into concrete section-prop wireframes.

    Output shape:
        {
            "/": {
                "name": "Home",
                "sections": [
                    {"kind": "navbar", "data": {...}},
                    {"kind": "hero",   "data": {"headline": "...", "sub": "...", ...}},
                    ...
                ]
            },
            ...
        }
    """

    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="Product Designer",
            system_instruction=(
                "You are a product designer generating concrete wireframe prop data. "
                "You receive a product spec and section kinds, and return ONLY valid JSON "
                "with dense, domain-specific, realistic content — not generic placeholder text. "
                "Headlines must be specific and evocative. Body text must be >=60 chars. "
                "Every section must have ALL required props. No lorem ipsum. No 'Coming soon'. "
                "Return ONLY the raw JSON object."
            ),
            ai_config=ai_config,
        )

    def generate(self, prompt: str, **kwargs) -> str:  # type: ignore[override]
        return super().generate(prompt=prompt)

    def wireframe(self, spec: dict) -> dict:
        pages = spec.get("pages", [])
        content_bank = spec.get("content_bank", {})
        design_system = spec.get("design_system", {})
        product_name = spec.get("product_name", "App")
        tagline = spec.get("tagline", "")
        frontend_collections = spec.get("frontend_data_collections", [])

        wireframes: dict = {}

        for page in pages:
            if not isinstance(page, dict):
                continue
            route = page.get("route", "/")
            name = page.get("name", "Page")

            # Determine which sections this page should have
            spec_sections = page.get("sections", [])
            if spec_sections and isinstance(spec_sections[0], dict):
                section_kinds = [s.get("kind", "").lower() for s in spec_sections if isinstance(s, dict) and s.get("kind")]
            else:
                section_kinds = _default_sections_for_route(route, name)

            # Filter to known section kinds
            section_kinds = [k for k in section_kinds if k in SECTION_CATALOGUE] or \
                            _default_sections_for_route(route, name)

            wireframes[route] = self._wireframe_page(
                route=route,
                name=name,
                purpose=page.get("purpose", ""),
                section_kinds=section_kinds,
                product_name=product_name,
                tagline=tagline,
                content_bank=content_bank,
                design_system=design_system,
                frontend_collections=frontend_collections,
                spec=spec,
            )

        return wireframes

    def _wireframe_page(
        self, route: str, name: str, purpose: str,
        section_kinds: list[str], product_name: str, tagline: str,
        content_bank: dict, design_system: dict,
        frontend_collections: list, spec: dict,
    ) -> dict:

        catalogue_for_page = "\n".join(
            f"  {k}: {SECTION_CATALOGUE[k]['desc']} | required={SECTION_CATALOGUE[k]['required']}"
            + (f" | rules={SECTION_CATALOGUE[k].get('rules', {})}" if SECTION_CATALOGUE[k].get("rules") else "")
            for k in section_kinds if k in SECTION_CATALOGUE
        )

        prompt = f"""Generate concrete wireframe prop data for this page.

Product: {product_name} — {tagline}
Page: {name} (route: {route})
Purpose: {purpose}

Design system:
{json.dumps(design_system, indent=2)[:1200]}

Content bank:
{json.dumps(content_bank, indent=2)[:1200]}

Frontend data collections (for list/grid sections):
{json.dumps(frontend_collections, indent=2)[:800]}

Sections to generate IN ORDER:
{catalogue_for_page}

Return a JSON object with this exact shape:
{{
  "name": "{name}",
  "sections": [
    {{"kind": "<section_kind>", "data": {{ <all required + optional props populated with real content> }}}},
    ...
  ]
}}

Rules:
- Generate sections in the ORDER listed above — do not reorder or skip
- Headlines: specific, evocative, >=40 chars — NOT "Welcome to {product_name}"
- Body / sub / description text: domain-specific, >=60 chars each
- Items in lists/grids: minimum counts from catalogue rules
- Use content_bank for names, headlines, metrics, workflow steps, testimonials
- Images: use https://images.unsplash.com/photo-<id>?w=800&q=80 or https://picsum.photos/seed/<stable-slug>/600/400
- Icons: use lucide-react icon names (e.g. "LayoutDashboard", "Sparkles", "Shield")
- Avoid generic blue-gray; use the design_system palette for color references
- Return ONLY the JSON object. No markdown fences."""

        try:
            raw = super().generate(prompt=prompt)
            parsed = self.parse_json(raw)
            if isinstance(parsed, dict) and "sections" in parsed:
                return parsed
        except Exception as exc:
            logger.warning("WireframeAgent page %s failed: %s — using minimal fallback", route, exc)

        # Fallback: minimal wireframe
        return {
            "name": name,
            "sections": [
                {"kind": k, "data": {"headline": f"{product_name} — {name}", "sub": purpose or tagline}}
                for k in section_kinds if k in SECTION_CATALOGUE
            ],
        }
