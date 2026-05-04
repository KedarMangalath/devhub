"""
DesignAgent — Stage 1.7 of the scaffold pipeline.

Produces a complete, domain-specific design system:
  1. Picks the closest base theme from a library of 12 opinionated presets
  2. Calls the LLM to customise palette, fonts, and tokens for the product domain
  3. (Optional) If STITCH_API_KEY is set, calls Google Stitch to generate a
     reference screenshot and feeds it back to the LLM for visual fidelity
  4. Returns: css_vars (light+dark), google_fonts_url, tailwind_extend block,
     and a rendered index.css string ready to write to disk

Output is injected into src/index.css and tailwind.config.js before codegen runs,
so every component can use bg-primary, text-foreground, font-display etc.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple

from agents.core.base import BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 12 opinionated base themes  (HSL values — shadcn-compatible)
# ---------------------------------------------------------------------------

class Theme(NamedTuple):
    name: str
    label: str
    keywords: list[str]   # domain words that make this theme a good fit
    light: dict[str, str]
    dark: dict[str, str]
    fonts: dict[str, str]  # display, body


THEME_LIBRARY: list[Theme] = [

    Theme(
        name="clean_saas",
        label="Clean modern SaaS",
        keywords=["saas", "software", "productivity", "tool", "platform", "app",
                  "dashboard", "management", "workspace", "analytics"],
        light={
            "background": "0 0% 100%",
            "foreground": "224 71% 4%",
            "card": "0 0% 100%",
            "card-foreground": "224 71% 4%",
            "popover": "0 0% 100%",
            "popover-foreground": "224 71% 4%",
            "primary": "239 84% 67%",
            "primary-foreground": "0 0% 100%",
            "secondary": "240 5% 96%",
            "secondary-foreground": "240 6% 10%",
            "muted": "240 5% 96%",
            "muted-foreground": "240 4% 46%",
            "accent": "240 5% 96%",
            "accent-foreground": "240 6% 10%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "240 6% 90%",
            "input": "240 6% 90%",
            "ring": "239 84% 67%",
            "radius": "0.5rem",
        },
        dark={
            "background": "224 71% 4%",
            "foreground": "213 31% 91%",
            "card": "224 71% 4%",
            "card-foreground": "213 31% 91%",
            "popover": "224 71% 4%",
            "popover-foreground": "215 20% 65%",
            "primary": "239 84% 67%",
            "primary-foreground": "0 0% 100%",
            "secondary": "222 47% 11%",
            "secondary-foreground": "210 40% 98%",
            "muted": "223 47% 11%",
            "muted-foreground": "215 20% 65%",
            "accent": "216 34% 17%",
            "accent-foreground": "210 40% 98%",
            "destructive": "0 63% 31%",
            "destructive-foreground": "210 40% 98%",
            "border": "216 34% 17%",
            "input": "216 34% 17%",
            "ring": "239 84% 67%",
            "radius": "0.5rem",
        },
        fonts={"display": "Plus Jakarta Sans", "body": "Inter"},
    ),

    Theme(
        name="bold_dark",
        label="Bold premium dark",
        keywords=["crypto", "fintech", "ai", "machine learning", "blockchain",
                  "gaming", "entertainment", "media", "agency", "creative"],
        light={
            "background": "0 0% 98%",
            "foreground": "270 50% 7%",
            "card": "0 0% 100%",
            "card-foreground": "270 50% 7%",
            "popover": "0 0% 100%",
            "popover-foreground": "270 50% 7%",
            "primary": "270 91% 65%",
            "primary-foreground": "0 0% 100%",
            "secondary": "270 10% 94%",
            "secondary-foreground": "270 50% 7%",
            "muted": "270 10% 94%",
            "muted-foreground": "270 10% 45%",
            "accent": "195 100% 50%",
            "accent-foreground": "270 50% 7%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "270 10% 88%",
            "input": "270 10% 88%",
            "ring": "270 91% 65%",
            "radius": "0.75rem",
        },
        dark={
            "background": "270 50% 4%",
            "foreground": "270 10% 95%",
            "card": "270 40% 7%",
            "card-foreground": "270 10% 95%",
            "popover": "270 40% 7%",
            "popover-foreground": "270 10% 95%",
            "primary": "270 91% 65%",
            "primary-foreground": "0 0% 100%",
            "secondary": "270 30% 12%",
            "secondary-foreground": "270 10% 95%",
            "muted": "270 30% 12%",
            "muted-foreground": "270 10% 60%",
            "accent": "195 100% 45%",
            "accent-foreground": "270 50% 4%",
            "destructive": "0 63% 45%",
            "destructive-foreground": "0 0% 100%",
            "border": "270 30% 14%",
            "input": "270 30% 14%",
            "ring": "270 91% 65%",
            "radius": "0.75rem",
        },
        fonts={"display": "Syne", "body": "DM Sans"},
    ),

    Theme(
        name="warm_editorial",
        label="Warm editorial",
        keywords=["blog", "news", "magazine", "publishing", "food", "recipe",
                  "travel", "lifestyle", "wellness", "fashion", "culture"],
        light={
            "background": "36 33% 97%",
            "foreground": "30 20% 10%",
            "card": "36 33% 99%",
            "card-foreground": "30 20% 10%",
            "popover": "36 33% 99%",
            "popover-foreground": "30 20% 10%",
            "primary": "16 72% 43%",
            "primary-foreground": "36 33% 97%",
            "secondary": "36 15% 92%",
            "secondary-foreground": "30 20% 10%",
            "muted": "36 15% 92%",
            "muted-foreground": "30 10% 45%",
            "accent": "43 96% 56%",
            "accent-foreground": "30 20% 10%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "36 33% 97%",
            "border": "36 15% 86%",
            "input": "36 15% 86%",
            "ring": "16 72% 43%",
            "radius": "0.375rem",
        },
        dark={
            "background": "30 20% 7%",
            "foreground": "36 33% 93%",
            "card": "30 20% 10%",
            "card-foreground": "36 33% 93%",
            "popover": "30 20% 10%",
            "popover-foreground": "36 33% 93%",
            "primary": "16 72% 55%",
            "primary-foreground": "30 20% 7%",
            "secondary": "30 15% 15%",
            "secondary-foreground": "36 33% 93%",
            "muted": "30 15% 15%",
            "muted-foreground": "36 15% 60%",
            "accent": "43 80% 50%",
            "accent-foreground": "30 20% 7%",
            "destructive": "0 63% 40%",
            "destructive-foreground": "36 33% 93%",
            "border": "30 15% 18%",
            "input": "30 15% 18%",
            "ring": "16 72% 55%",
            "radius": "0.375rem",
        },
        fonts={"display": "Playfair Display", "body": "Source Serif 4"},
    ),

    Theme(
        name="emerald_fresh",
        label="Emerald fresh",
        keywords=["health", "fitness", "wellness", "eco", "sustainability",
                  "organic", "nature", "outdoor", "sports", "nutrition", "medical"],
        light={
            "background": "150 20% 98%",
            "foreground": "160 40% 6%",
            "card": "0 0% 100%",
            "card-foreground": "160 40% 6%",
            "popover": "0 0% 100%",
            "popover-foreground": "160 40% 6%",
            "primary": "160 84% 39%",
            "primary-foreground": "0 0% 100%",
            "secondary": "150 15% 94%",
            "secondary-foreground": "160 40% 6%",
            "muted": "150 15% 94%",
            "muted-foreground": "160 15% 45%",
            "accent": "82 77% 48%",
            "accent-foreground": "160 40% 6%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "150 15% 88%",
            "input": "150 15% 88%",
            "ring": "160 84% 39%",
            "radius": "0.5rem",
        },
        dark={
            "background": "160 40% 4%",
            "foreground": "150 20% 94%",
            "card": "160 35% 7%",
            "card-foreground": "150 20% 94%",
            "popover": "160 35% 7%",
            "popover-foreground": "150 20% 94%",
            "primary": "160 84% 45%",
            "primary-foreground": "160 40% 4%",
            "secondary": "160 25% 12%",
            "secondary-foreground": "150 20% 94%",
            "muted": "160 25% 12%",
            "muted-foreground": "150 15% 58%",
            "accent": "82 65% 42%",
            "accent-foreground": "160 40% 4%",
            "destructive": "0 63% 38%",
            "destructive-foreground": "0 0% 100%",
            "border": "160 25% 15%",
            "input": "160 25% 15%",
            "ring": "160 84% 45%",
            "radius": "0.5rem",
        },
        fonts={"display": "Nunito", "body": "Inter"},
    ),

    Theme(
        name="rose_boutique",
        label="Rose boutique",
        keywords=["fashion", "beauty", "cosmetics", "ecommerce", "boutique",
                  "luxury", "retail", "wedding", "events", "jewellery", "gifts"],
        light={
            "background": "350 25% 99%",
            "foreground": "350 30% 8%",
            "card": "0 0% 100%",
            "card-foreground": "350 30% 8%",
            "popover": "0 0% 100%",
            "popover-foreground": "350 30% 8%",
            "primary": "350 89% 60%",
            "primary-foreground": "0 0% 100%",
            "secondary": "350 20% 94%",
            "secondary-foreground": "350 30% 8%",
            "muted": "350 20% 94%",
            "muted-foreground": "350 10% 45%",
            "accent": "28 100% 67%",
            "accent-foreground": "350 30% 8%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "350 20% 88%",
            "input": "350 20% 88%",
            "ring": "350 89% 60%",
            "radius": "0.75rem",
        },
        dark={
            "background": "350 30% 5%",
            "foreground": "350 25% 95%",
            "card": "350 25% 8%",
            "card-foreground": "350 25% 95%",
            "popover": "350 25% 8%",
            "popover-foreground": "350 25% 95%",
            "primary": "350 89% 65%",
            "primary-foreground": "0 0% 100%",
            "secondary": "350 20% 13%",
            "secondary-foreground": "350 25% 95%",
            "muted": "350 20% 13%",
            "muted-foreground": "350 10% 60%",
            "accent": "28 90% 62%",
            "accent-foreground": "350 30% 5%",
            "destructive": "0 63% 40%",
            "destructive-foreground": "0 0% 100%",
            "border": "350 20% 15%",
            "input": "350 20% 15%",
            "ring": "350 89% 65%",
            "radius": "0.75rem",
        },
        fonts={"display": "Cormorant Garamond", "body": "Lato"},
    ),

    Theme(
        name="ocean_professional",
        label="Ocean professional",
        keywords=["finance", "banking", "insurance", "legal", "consulting",
                  "corporate", "real estate", "investment", "accounting", "hr"],
        light={
            "background": "210 20% 98%",
            "foreground": "210 40% 8%",
            "card": "0 0% 100%",
            "card-foreground": "210 40% 8%",
            "popover": "0 0% 100%",
            "popover-foreground": "210 40% 8%",
            "primary": "212 100% 47%",
            "primary-foreground": "0 0% 100%",
            "secondary": "210 15% 94%",
            "secondary-foreground": "210 40% 8%",
            "muted": "210 15% 94%",
            "muted-foreground": "210 15% 46%",
            "accent": "199 89% 48%",
            "accent-foreground": "0 0% 100%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "210 15% 88%",
            "input": "210 15% 88%",
            "ring": "212 100% 47%",
            "radius": "0.375rem",
        },
        dark={
            "background": "212 50% 5%",
            "foreground": "210 20% 94%",
            "card": "212 45% 8%",
            "card-foreground": "210 20% 94%",
            "popover": "212 45% 8%",
            "popover-foreground": "210 20% 94%",
            "primary": "212 100% 55%",
            "primary-foreground": "0 0% 100%",
            "secondary": "212 35% 12%",
            "secondary-foreground": "210 20% 94%",
            "muted": "212 35% 12%",
            "muted-foreground": "210 15% 58%",
            "accent": "199 89% 50%",
            "accent-foreground": "0 0% 100%",
            "destructive": "0 63% 38%",
            "destructive-foreground": "0 0% 100%",
            "border": "212 35% 15%",
            "input": "212 35% 15%",
            "ring": "212 100% 55%",
            "radius": "0.375rem",
        },
        fonts={"display": "Manrope", "body": "Inter"},
    ),

    Theme(
        name="amber_marketplace",
        label="Amber marketplace",
        keywords=["marketplace", "freelance", "gig", "jobs", "hiring", "talent",
                  "education", "learning", "courses", "community", "forum"],
        light={
            "background": "45 20% 98%",
            "foreground": "30 35% 7%",
            "card": "0 0% 100%",
            "card-foreground": "30 35% 7%",
            "popover": "0 0% 100%",
            "popover-foreground": "30 35% 7%",
            "primary": "38 92% 50%",
            "primary-foreground": "30 35% 7%",
            "secondary": "45 15% 94%",
            "secondary-foreground": "30 35% 7%",
            "muted": "45 15% 94%",
            "muted-foreground": "30 15% 46%",
            "accent": "16 100% 60%",
            "accent-foreground": "0 0% 100%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "45 15% 87%",
            "input": "45 15% 87%",
            "ring": "38 92% 50%",
            "radius": "0.5rem",
        },
        dark={
            "background": "30 35% 5%",
            "foreground": "45 20% 94%",
            "card": "30 30% 8%",
            "card-foreground": "45 20% 94%",
            "popover": "30 30% 8%",
            "popover-foreground": "45 20% 94%",
            "primary": "38 92% 55%",
            "primary-foreground": "30 35% 5%",
            "secondary": "30 20% 13%",
            "secondary-foreground": "45 20% 94%",
            "muted": "30 20% 13%",
            "muted-foreground": "45 15% 57%",
            "accent": "16 90% 55%",
            "accent-foreground": "30 35% 5%",
            "destructive": "0 63% 38%",
            "destructive-foreground": "0 0% 100%",
            "border": "30 20% 16%",
            "input": "30 20% 16%",
            "ring": "38 92% 55%",
            "radius": "0.5rem",
        },
        fonts={"display": "Space Grotesk", "body": "Nunito"},
    ),

    Theme(
        name="violet_startup",
        label="Violet startup",
        keywords=["startup", "innovation", "tech", "product", "launch", "mvp",
                  "developer", "open source", "api", "integration", "automation"],
        light={
            "background": "270 20% 99%",
            "foreground": "270 50% 6%",
            "card": "0 0% 100%",
            "card-foreground": "270 50% 6%",
            "popover": "0 0% 100%",
            "popover-foreground": "270 50% 6%",
            "primary": "262 83% 58%",
            "primary-foreground": "0 0% 100%",
            "secondary": "270 15% 94%",
            "secondary-foreground": "270 50% 6%",
            "muted": "270 15% 94%",
            "muted-foreground": "270 10% 46%",
            "accent": "316 73% 52%",
            "accent-foreground": "0 0% 100%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "270 15% 88%",
            "input": "270 15% 88%",
            "ring": "262 83% 58%",
            "radius": "0.625rem",
        },
        dark={
            "background": "270 50% 4%",
            "foreground": "270 20% 95%",
            "card": "270 45% 7%",
            "card-foreground": "270 20% 95%",
            "popover": "270 45% 7%",
            "popover-foreground": "270 20% 95%",
            "primary": "262 83% 65%",
            "primary-foreground": "0 0% 100%",
            "secondary": "270 30% 11%",
            "secondary-foreground": "270 20% 95%",
            "muted": "270 30% 11%",
            "muted-foreground": "270 10% 60%",
            "accent": "316 73% 58%",
            "accent-foreground": "0 0% 100%",
            "destructive": "0 63% 40%",
            "destructive-foreground": "0 0% 100%",
            "border": "270 30% 14%",
            "input": "270 30% 14%",
            "ring": "262 83% 65%",
            "radius": "0.625rem",
        },
        fonts={"display": "Outfit", "body": "Inter"},
    ),

    Theme(
        name="slate_enterprise",
        label="Slate enterprise",
        keywords=["enterprise", "government", "administration", "compliance",
                  "security", "infrastructure", "logistics", "supply chain", "b2b"],
        light={
            "background": "220 14% 98%",
            "foreground": "220 30% 8%",
            "card": "0 0% 100%",
            "card-foreground": "220 30% 8%",
            "popover": "0 0% 100%",
            "popover-foreground": "220 30% 8%",
            "primary": "220 90% 40%",
            "primary-foreground": "0 0% 100%",
            "secondary": "220 10% 94%",
            "secondary-foreground": "220 30% 8%",
            "muted": "220 10% 94%",
            "muted-foreground": "220 10% 46%",
            "accent": "220 90% 40%",
            "accent-foreground": "0 0% 100%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "220 10% 88%",
            "input": "220 10% 88%",
            "ring": "220 90% 40%",
            "radius": "0.25rem",
        },
        dark={
            "background": "220 30% 5%",
            "foreground": "220 14% 93%",
            "card": "220 25% 8%",
            "card-foreground": "220 14% 93%",
            "popover": "220 25% 8%",
            "popover-foreground": "220 14% 93%",
            "primary": "220 90% 50%",
            "primary-foreground": "0 0% 100%",
            "secondary": "220 20% 12%",
            "secondary-foreground": "220 14% 93%",
            "muted": "220 20% 12%",
            "muted-foreground": "220 10% 55%",
            "accent": "220 90% 50%",
            "accent-foreground": "0 0% 100%",
            "destructive": "0 63% 38%",
            "destructive-foreground": "0 0% 100%",
            "border": "220 20% 15%",
            "input": "220 20% 15%",
            "ring": "220 90% 50%",
            "radius": "0.25rem",
        },
        fonts={"display": "IBM Plex Sans", "body": "IBM Plex Sans"},
    ),

    Theme(
        name="teal_health",
        label="Teal healthcare",
        keywords=["healthcare", "clinic", "hospital", "doctor", "patient",
                  "pharmacy", "telemedicine", "therapy", "mental health", "veterinary"],
        light={
            "background": "180 20% 98%",
            "foreground": "185 40% 6%",
            "card": "0 0% 100%",
            "card-foreground": "185 40% 6%",
            "popover": "0 0% 100%",
            "popover-foreground": "185 40% 6%",
            "primary": "185 84% 35%",
            "primary-foreground": "0 0% 100%",
            "secondary": "180 15% 94%",
            "secondary-foreground": "185 40% 6%",
            "muted": "180 15% 94%",
            "muted-foreground": "185 15% 45%",
            "accent": "158 64% 52%",
            "accent-foreground": "185 40% 6%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "180 15% 87%",
            "input": "180 15% 87%",
            "ring": "185 84% 35%",
            "radius": "0.5rem",
        },
        dark={
            "background": "185 40% 4%",
            "foreground": "180 20% 94%",
            "card": "185 35% 7%",
            "card-foreground": "180 20% 94%",
            "popover": "185 35% 7%",
            "popover-foreground": "180 20% 94%",
            "primary": "185 84% 42%",
            "primary-foreground": "185 40% 4%",
            "secondary": "185 25% 11%",
            "secondary-foreground": "180 20% 94%",
            "muted": "185 25% 11%",
            "muted-foreground": "180 15% 56%",
            "accent": "158 60% 45%",
            "accent-foreground": "185 40% 4%",
            "destructive": "0 63% 38%",
            "destructive-foreground": "0 0% 100%",
            "border": "185 25% 14%",
            "input": "185 25% 14%",
            "ring": "185 84% 42%",
            "radius": "0.5rem",
        },
        fonts={"display": "Nunito", "body": "Source Sans 3"},
    ),

    Theme(
        name="crimson_bold",
        label="Crimson bold",
        keywords=["restaurant", "food delivery", "catering", "bar", "nightclub",
                  "sports", "gym", "energy", "news", "urgent", "emergency"],
        light={
            "background": "0 0% 99%",
            "foreground": "0 30% 6%",
            "card": "0 0% 100%",
            "card-foreground": "0 30% 6%",
            "popover": "0 0% 100%",
            "popover-foreground": "0 30% 6%",
            "primary": "0 84% 50%",
            "primary-foreground": "0 0% 100%",
            "secondary": "0 10% 94%",
            "secondary-foreground": "0 30% 6%",
            "muted": "0 10% 94%",
            "muted-foreground": "0 10% 45%",
            "accent": "24 100% 55%",
            "accent-foreground": "0 0% 100%",
            "destructive": "0 84% 50%",
            "destructive-foreground": "0 0% 100%",
            "border": "0 10% 88%",
            "input": "0 10% 88%",
            "ring": "0 84% 50%",
            "radius": "0.375rem",
        },
        dark={
            "background": "0 30% 4%",
            "foreground": "0 10% 94%",
            "card": "0 25% 7%",
            "card-foreground": "0 10% 94%",
            "popover": "0 25% 7%",
            "popover-foreground": "0 10% 94%",
            "primary": "0 84% 58%",
            "primary-foreground": "0 0% 100%",
            "secondary": "0 20% 12%",
            "secondary-foreground": "0 10% 94%",
            "muted": "0 20% 12%",
            "muted-foreground": "0 10% 58%",
            "accent": "24 90% 52%",
            "accent-foreground": "0 0% 100%",
            "destructive": "0 84% 58%",
            "destructive-foreground": "0 0% 100%",
            "border": "0 20% 15%",
            "input": "0 20% 15%",
            "ring": "0 84% 58%",
            "radius": "0.375rem",
        },
        fonts={"display": "Barlow Condensed", "body": "Barlow"},
    ),

    Theme(
        name="midnight_luxury",
        label="Midnight luxury",
        keywords=["hotel", "resort", "luxury", "concierge", "travel", "booking",
                  "real estate", "premium", "vip", "exclusive", "spa"],
        light={
            "background": "210 15% 98%",
            "foreground": "220 25% 8%",
            "card": "0 0% 100%",
            "card-foreground": "220 25% 8%",
            "popover": "0 0% 100%",
            "popover-foreground": "220 25% 8%",
            "primary": "220 25% 18%",
            "primary-foreground": "45 60% 80%",
            "secondary": "210 10% 94%",
            "secondary-foreground": "220 25% 8%",
            "muted": "210 10% 94%",
            "muted-foreground": "220 10% 46%",
            "accent": "45 80% 65%",
            "accent-foreground": "220 25% 8%",
            "destructive": "0 72% 51%",
            "destructive-foreground": "0 0% 100%",
            "border": "210 10% 87%",
            "input": "210 10% 87%",
            "ring": "45 80% 65%",
            "radius": "0.25rem",
        },
        dark={
            "background": "220 25% 6%",
            "foreground": "210 15% 94%",
            "card": "220 22% 9%",
            "card-foreground": "210 15% 94%",
            "popover": "220 22% 9%",
            "popover-foreground": "210 15% 94%",
            "primary": "45 80% 65%",
            "primary-foreground": "220 25% 6%",
            "secondary": "220 18% 14%",
            "secondary-foreground": "210 15% 94%",
            "muted": "220 18% 14%",
            "muted-foreground": "210 10% 58%",
            "accent": "45 80% 65%",
            "accent-foreground": "220 25% 6%",
            "destructive": "0 63% 40%",
            "destructive-foreground": "0 0% 100%",
            "border": "220 18% 16%",
            "input": "220 18% 16%",
            "ring": "45 80% 65%",
            "radius": "0.25rem",
        },
        fonts={"display": "Cormorant Garamond", "body": "Josefin Sans"},
    ),
]


# ---------------------------------------------------------------------------
# Theme selector
# ---------------------------------------------------------------------------

# Generic keywords that shouldn't dominate scoring — they appear in many domains
_GENERIC_KEYWORDS = {
    "app", "platform", "tool", "software", "product", "management",
    "workspace", "dashboard", "analytics", "community", "forum",
}


def _score_theme(theme: Theme, text: str) -> int:
    t = text.lower()
    score = 0
    for k in theme.keywords:
        # Word-boundary check to prevent partial matches (e.g. 'art' in 'startup')
        if re.search(rf'\b{re.escape(k)}\b', t):
            score += 1 if k in _GENERIC_KEYWORDS else 3
    return score


def pick_base_theme(product_name: str, tagline: str, description: str) -> Theme:
    """Pick the best-matching theme from the library for this product."""
    text = f"{product_name} {tagline} {description}".lower()
    scored = sorted(THEME_LIBRARY, key=lambda t: _score_theme(t, text), reverse=True)
    if _score_theme(scored[0], text) > 0:
        return scored[0]
    # No keyword match — deterministic fallback by hash
    idx = int(hashlib.md5(product_name.encode()).hexdigest(), 16) % len(THEME_LIBRARY)
    return THEME_LIBRARY[idx]


# ---------------------------------------------------------------------------
# Google Fonts builder
# ---------------------------------------------------------------------------

_FONT_WEIGHTS = "300;400;500;600;700"

def _google_fonts_url(display_font: str, body_font: str) -> str:
    def encode(name: str) -> str:
        return name.replace(" ", "+")
    fonts = []
    if display_font != body_font:
        fonts.append(f"family={encode(display_font)}:ital,wght@0,{_FONT_WEIGHTS};1,400")
        fonts.append(f"family={encode(body_font)}:wght@{_FONT_WEIGHTS}")
    else:
        fonts.append(f"family={encode(display_font)}:ital,wght@0,{_FONT_WEIGHTS};1,400")
    return f"https://fonts.googleapis.com/css2?{'&'.join(fonts)}&display=swap"


# ---------------------------------------------------------------------------
# Stitch integration (optional)
# ---------------------------------------------------------------------------

def _try_stitch_screenshot(product_name: str, tagline: str, aesthetic: str) -> str | None:
    """
    If STITCH_API_KEY is set, generates a reference screenshot using Google Stitch
    and returns a URL to the screenshot image, or None on failure.
    """
    api_key = os.environ.get("STITCH_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        # Use a temp Node.js script to call the Stitch SDK
        script = f"""
const {{ StitchToolClient }} = require('@google/stitch-sdk');
async function main() {{
    const client = new StitchToolClient({{ apiKey: '{api_key}' }});
    const projects = await client.listProjects();
    let project;
    if (projects.length > 0) {{
        project = projects[0];
    }} else {{
        project = await client.createProject({{ name: 'devhub-design-ref' }});
    }}
    const screen = await project.generate(
        'A modern, polished landing page for {product_name}: {tagline}. Style: {aesthetic}. ' +
        'Show the hero section, navigation, and feature highlights.',
        'DESKTOP'
    );
    const imageUrl = await screen.getImage();
    process.stdout.write(JSON.stringify({{ imageUrl }}));
}}
main().catch(e => process.stdout.write(JSON.stringify({{ error: e.message }})));
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(script)
            tmp_path = f.name

        result = subprocess.run(
            ["node", tmp_path],
            capture_output=True, text=True, timeout=60,
            cwd=tempfile.gettempdir(),
        )
        Path(tmp_path).unlink(missing_ok=True)

        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            if "imageUrl" in data:
                logger.info("Stitch screenshot generated: %s", data["imageUrl"])
                return data["imageUrl"]
            logger.warning("Stitch error: %s", data.get("error"))
    except Exception as exc:
        logger.warning("Stitch integration failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# DesignAgent
# ---------------------------------------------------------------------------

class DesignAgent(BaseAgent):
    """
    Stage 1.7: Produces a complete design system for the project.

    Steps:
    1. Pick base theme from library
    2. (Optional) Call Stitch for a visual reference screenshot
    3. LLM customises the theme tokens for the specific product domain
    4. Return: css_vars, google_fonts_url, rendered index.css, tailwind_extend
    """

    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="UI/UX Designer",
            system_instruction=(
                "You are an expert UI/UX designer who creates precise design tokens. "
                "You receive a base color theme and product context, then customise "
                "the CSS variables to perfectly match the product's domain and aesthetic. "
                "Return ONLY valid JSON — no markdown, no explanation."
            ),
            ai_config=ai_config,
        )

    def generate_design(self, spec: dict, description: str = "") -> dict:
        """
        Returns a design context dict with keys:
          css_vars_light, css_vars_dark, fonts, google_fonts_url,
          tailwind_extend, rendered_index_css
        """
        product_name = spec.get("product_name", "App")
        tagline = spec.get("tagline", "")
        existing_ds = spec.get("design_system") or {}
        aesthetic = existing_ds.get("aesthetic", "")

        # Step 1 — pick base theme
        base = pick_base_theme(product_name, tagline, f"{description} {aesthetic}")
        logger.info("DesignAgent: base theme '%s' for '%s'", base.name, product_name)

        # Override fonts if spec provided them
        display_font = existing_ds.get("typography", {}).get("display") or base.fonts["display"]
        body_font = existing_ds.get("typography", {}).get("body") or base.fonts["body"]

        # Step 2 — optional Stitch screenshot
        stitch_img_url = _try_stitch_screenshot(product_name, tagline, aesthetic or base.label)

        # Step 3 — LLM customisation
        custom_vars = self._llm_customise(
            base=base,
            spec=spec,
            description=description,
            stitch_img_url=stitch_img_url,
            display_font=display_font,
            body_font=body_font,
        )

        # Merge: base → LLM overrides
        light = {**base.light, **custom_vars.get("light", {})}
        dark = {**base.dark, **custom_vars.get("dark", {})}
        fonts = {
            "display": custom_vars.get("display_font") or display_font,
            "body": custom_vars.get("body_font") or body_font,
        }

        gf_url = _google_fonts_url(fonts["display"], fonts["body"])

        return {
            "css_vars_light": light,
            "css_vars_dark": dark,
            "fonts": fonts,
            "google_fonts_url": gf_url,
            "base_theme_name": base.name,
            "rendered_index_css": _render_index_css(light, dark, fonts, gf_url),
            "rendered_tailwind_config": _render_tailwind_config(fonts),
            "stitch_reference_url": stitch_img_url,
        }

    def _llm_customise(
        self,
        base: Theme,
        spec: dict,
        description: str,
        stitch_img_url: str | None,
        display_font: str,
        body_font: str,
    ) -> dict:
        """Ask LLM to fine-tune the base theme for the specific domain."""
        existing_palette = spec.get("design_system", {}).get("palette") or {}
        stitch_note = (
            f"\nA reference screenshot has been generated at: {stitch_img_url}\n"
            "Derive color suggestions that would look great in this visual style."
            if stitch_img_url else ""
        )

        prompt = f"""Customise the design tokens for this product.

Product: {spec.get('product_name')} — {spec.get('tagline')}
Description: {description[:400]}
Domain aesthetic: {spec.get('design_system', {}).get('aesthetic', base.label)}
{stitch_note}

Base theme: {base.label}
Current light tokens (HSL values as "h s% l%"):
{json.dumps(base.light, indent=2)}

User-specified palette overrides (hex — convert to HSL if provided):
{json.dumps(existing_palette, indent=2) if existing_palette else 'none'}

Display font preference: {display_font}
Body font preference: {body_font}

Return a JSON object customising ONLY the tokens that should change for this domain.
Do NOT include tokens that should stay the same as the base.

{{
  "light": {{
    "primary": "h s% l%",
    "primary-foreground": "h s% l%",
    "accent": "h s% l%"
    // only include tokens you want to override
  }},
  "dark": {{
    // same — only overrides
  }},
  "display_font": "Google Font name for headings",
  "body_font": "Google Font name for body text",
  "rationale": "one sentence explaining the design choices"
}}

Rules:
- Values MUST be valid HSL components WITHOUT hsl() wrapper: e.g. "262 83% 58%"
- Choose fonts from Google Fonts that fit the domain and aesthetic
- Keep the design coherent — primary and accent should complement each other
- Return {{}} if the base theme needs no changes"""

        try:
            raw = super().generate(prompt=prompt)
            parsed = self.parse_json(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception as exc:
            logger.warning("DesignAgent LLM customise failed: %s", exc)

        return {}


# ---------------------------------------------------------------------------
# CSS / Tailwind renderers
# ---------------------------------------------------------------------------

def _css_vars_block(vars_dict: dict[str, str], indent: int = 2) -> str:
    pad = " " * indent
    lines = []
    for k, v in vars_dict.items():
        if k == "radius":
            lines.append(f"{pad}--radius: {v};")
        else:
            lines.append(f"{pad}--{k}: {v};")
    return "\n".join(lines)


def _render_index_css(
    light: dict,
    dark: dict,
    fonts: dict,
    google_fonts_url: str,
) -> str:
    display = fonts.get("display", "Inter")
    body = fonts.get("body", "Inter")
    radius = light.get("radius", "0.5rem")

    return f"""@import url('{google_fonts_url}');

@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {{
  :root {{
{_css_vars_block(light, 4)}
    --font-display: '{display}', system-ui, sans-serif;
    --font-body: '{body}', system-ui, sans-serif;
  }}

  .dark {{
{_css_vars_block(dark, 4)}
  }}

  * {{
    @apply border-border;
    box-sizing: border-box;
  }}

  body {{
    @apply bg-background text-foreground;
    font-family: var(--font-body);
    font-feature-settings: 'rlig' 1, 'calt' 1;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }}

  h1, h2, h3, h4, h5, h6 {{
    font-family: var(--font-display);
    @apply font-semibold tracking-tight;
  }}
}}

@layer components {{
  /* Section layout utilities */
  .section-padding {{
    @apply py-16 px-4 sm:px-6 lg:px-8;
  }}
  .container-tight {{
    @apply max-w-7xl mx-auto;
  }}

  /* Typography scale */
  .display-xl {{
    font-family: var(--font-display);
    @apply text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-none;
  }}
  .display-lg {{
    font-family: var(--font-display);
    @apply text-4xl sm:text-5xl font-bold tracking-tight;
  }}
  .display-md {{
    font-family: var(--font-display);
    @apply text-3xl sm:text-4xl font-semibold;
  }}
  .display-sm {{
    font-family: var(--font-display);
    @apply text-2xl sm:text-3xl font-semibold;
  }}
  .body-lg {{ @apply text-lg leading-relaxed; }}
  .body-md {{ @apply text-base leading-relaxed; }}
  .body-sm {{ @apply text-sm leading-relaxed; }}
  .label {{ @apply text-xs font-medium uppercase tracking-widest; }}

  /* Card utilities */
  .card-hover {{
    @apply transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md;
  }}
  .glass-card {{
    @apply bg-white/80 backdrop-blur-sm border border-white/20 shadow-sm;
  }}

  /* Focus ring */
  .focus-ring {{
    @apply focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2;
  }}

  /* Gradient text */
  .gradient-text {{
    @apply bg-clip-text text-transparent;
    background-image: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
  }}

  /* Section divider */
  .section-divider {{
    @apply border-t border-border;
  }}
}}
"""


def _render_tailwind_config(fonts: dict) -> str:
    display = fonts.get("display", "Inter")
    body = fonts.get("body", "Inter")

    return f"""import {{ fontFamily }} from 'tailwindcss/defaultTheme';

/** @type {{import('tailwindcss').Config}} */
export default {{
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{{js,jsx,ts,tsx}}',
    './app/**/*.{{js,jsx,ts,tsx}}',
    './pages/**/*.{{js,jsx,ts,tsx}}',
    './components/**/*.{{js,jsx,ts,tsx}}',
  ],
  theme: {{
    container: {{
      center: true,
      padding: '2rem',
      screens: {{ '2xl': '1400px' }},
    }},
    extend: {{
      colors: {{
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {{
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        }},
        secondary: {{
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        }},
        destructive: {{
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        }},
        muted: {{
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        }},
        accent: {{
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        }},
        popover: {{
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        }},
        card: {{
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        }},
      }},
      borderRadius: {{
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      }},
      fontFamily: {{
        display: ['var(--font-display)', ...fontFamily.sans],
        body: ['var(--font-body)', ...fontFamily.sans],
        sans: ['var(--font-body)', ...fontFamily.sans],
      }},
      keyframes: {{
        'accordion-down': {{
          from: {{ height: '0' }},
          to: {{ height: 'var(--radix-accordion-content-height)' }},
        }},
        'accordion-up': {{
          from: {{ height: 'var(--radix-accordion-content-height)' }},
          to: {{ height: '0' }},
        }},
        'fade-in': {{ from: {{ opacity: '0', transform: 'translateY(8px)' }}, to: {{ opacity: '1', transform: 'translateY(0)' }} }},
        'fade-out': {{ from: {{ opacity: '1' }}, to: {{ opacity: '0' }} }},
        'slide-in': {{ from: {{ transform: 'translateX(-100%)' }}, to: {{ transform: 'translateX(0)' }} }},
        'pulse-slow': {{ '0%, 100%': {{ opacity: '1' }}, '50%': {{ opacity: '0.5' }} }},
      }},
      animation: {{
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'fade-in': 'fade-in 0.3s ease-out',
        'fade-out': 'fade-out 0.2s ease-out',
        'slide-in': 'slide-in 0.3s ease-out',
        'pulse-slow': 'pulse-slow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }},
      backgroundImage: {{
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      }},
    }},
  }},
  plugins: [],
}};
"""
