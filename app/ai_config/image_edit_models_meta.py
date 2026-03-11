"""Static metadata for image-to-image editing models.

Source rankings: Artificial Analysis Image Editing Arena (Elo-based), März 2026.
Pricing: fal.ai pricing page (März 2026).
"""
from __future__ import annotations
from typing import Optional

IMAGE_EDIT_MODELS_CATALOG: list[dict] = [
    # ── RANG #1 ──────────────────────────────────────────────────────────────
    {
        "slug": "nano_banana2_edit",
        "name": "Nano Banana 2 Edit (Gemini Flash)",
        "fal_endpoint": "fal-ai/gemini-3.1-flash-image-preview/edit",
        "price_per_image": 0.067,
        "price_label": "$0.067 / Bild",
        "cost_tier": "premium",
        "elo_score": 1157,
        "elo_rank": 1,
        "elo_source": "Artificial Analysis Image Edit Arena (März 2026)",
        "quality_stars": 5,
        "speed_seconds": 8,
        "description": "Rang #1 Img2Img (Elo 1157). Googles Gemini 3.1 Flash — bestes Bearbeitungsmodell 2026.",
        "badge": "Rang #1 Editing",
        "badge_color": "#FFD700",
        "supports_strength": False,
        "is_default": True,
    },
    # ── RANG #2 (zu teuer) ────────────────────────────────────────────────────
    {
        "slug": "gpt_image_15_edit",
        "name": "GPT Image 1.5 Edit (High)",
        "fal_endpoint": "fal-ai/gpt-image-1.5/edit",
        "price_per_image": 0.133,
        "price_label": "$0.133 / Bild",
        "cost_tier": "expensive",
        "elo_score": 1161,
        "elo_rank": 2,
        "elo_source": "Artificial Analysis Image Edit Arena (März 2026)",
        "quality_stars": 5,
        "speed_seconds": 12,
        "description": "Höchstes Elo im Edit-Leaderboard (1161), aber sehr teuer.",
        "badge": "Rang #2",
        "badge_color": "#C0C0C0",
        "supports_strength": False,
        "is_default": False,
        "cost_note": "⚠️ Teuer: $133/1.000 Bilder — nur für kritische Assets",
    },
    # ── RANG #3 — Günstig & Gut ───────────────────────────────────────────────
    {
        "slug": "seedream_45_edit",
        "name": "Seedream 4.5 Edit",
        "fal_endpoint": "fal-ai/bytedance/seedream/v4.5/edit",
        "price_per_image": 0.040,
        "price_label": "$0.04 / Bild",
        "cost_tier": "standard",
        "elo_score": 1090,
        "elo_rank": 3,
        "elo_source": "Artificial Analysis Image Edit Arena (März 2026)",
        "quality_stars": 4,
        "speed_seconds": 6,
        "description": "ByteDance Seedream 4.5 Edit, Rang #3 (Elo 1090). Sehr gutes Preis-Leistungs-Verhältnis.",
        "badge": "Günstig & Gut",
        "badge_color": "#FD79A8",
        "supports_strength": True,
        "is_default": False,
    },
    # ── RANG #4 — Budget ─────────────────────────────────────────────────────
    {
        "slug": "flux2_flash_edit",
        "name": "FLUX.2 Dev Flash Edit",
        "fal_endpoint": "fal-ai/flux-2/flash/edit",
        "price_per_image": 0.005,
        "price_label": "$0.005 / Bild",
        "cost_tier": "budget",
        "elo_score": 1039,
        "elo_rank": 4,
        "elo_source": "Artificial Analysis Image Edit Arena (März 2026)",
        "quality_stars": 3,
        "speed_seconds": 2,
        "description": "Rang #4 (Elo 1039), $5/1.000 Bilder — ideal für schnelle Iterationen und Tests.",
        "badge": "Günstigstes Edit",
        "badge_color": "#55EFC4",
        "supports_strength": True,
        "is_default": False,
    },
    # ── RANG #5 ───────────────────────────────────────────────────────────────
    {
        "slug": "flux2_turbo_edit",
        "name": "FLUX.2 Dev Turbo Edit",
        "fal_endpoint": "fal-ai/flux-2/turbo/edit",
        "price_per_image": 0.008,
        "price_label": "$0.008 / Bild",
        "cost_tier": "budget",
        "elo_score": 1009,
        "elo_rank": 5,
        "elo_source": "Artificial Analysis Image Edit Arena (März 2026)",
        "quality_stars": 3,
        "speed_seconds": 3,
        "description": "FLUX.2 Dev Turbo Edit, Rang #5 (Elo 1009). $8/1.000 Bilder.",
        "badge": None,
        "badge_color": None,
        "supports_strength": True,
        "is_default": False,
    },
    # ── KONTEXT ───────────────────────────────────────────────────────────────
    {
        "slug": "flux_kontext_pro",
        "name": "FLUX.1 Kontext Pro",
        "fal_endpoint": "fal-ai/flux-pro/kontext",
        "price_per_image": 0.040,
        "price_label": "$0.04 / Bild",
        "cost_tier": "standard",
        "elo_score": 908,
        "elo_rank": 6,
        "elo_source": "Artificial Analysis Image Edit Arena (März 2026)",
        "quality_stars": 4,
        "speed_seconds": 10,
        "description": "FLUX.1 Kontext Pro — spezialisiert auf lokale Bildbearbeitung mit exakter Texttreue.",
        "badge": "Kontextuell",
        "badge_color": "#6C5CE7",
        "supports_strength": True,
        "is_default": False,
    },
]

EDIT_MODELS_BY_SLUG: dict[str, dict] = {m["slug"]: m for m in IMAGE_EDIT_MODELS_CATALOG}
SELECTABLE_EDIT_MODELS: list[dict] = IMAGE_EDIT_MODELS_CATALOG


def get_edit_model_meta(slug: str) -> Optional[dict]:
    return EDIT_MODELS_BY_SLUG.get(slug)
