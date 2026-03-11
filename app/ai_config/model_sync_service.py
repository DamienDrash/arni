"""Auto-sync image model metadata from Artificial Analysis + fal.ai.

Fetches fresh Elo rankings from the AA Arena and the fal.ai model catalog,
then updates ImageProvider priorities and static catalog metadata in the DB.

Usage:
    From code:  from app.ai_config.model_sync_service import run_model_sync
                result = await run_model_sync(db)
    From CLI:   python -m app.ai_config.model_sync_service
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any
import httpx
import structlog

logger = structlog.get_logger()

AA_T2I_URL = "https://artificialanalysis.ai/api/text-to-image/arena/preferences?supports_image_input=false"
AA_EDIT_URL = "https://artificialanalysis.ai/api/text-to-image/arena/preferences?supports_image_input=true"
FAL_CATALOG_URL = "https://fal.ai/api/models?category=text-to-image,image-to-image&size=200&page={page}"

# Maps AA model display names → our internal slug (text-to-image)
AA_T2I_SLUG_MAP: dict[str, str] = {
    "GPT Image 1.5 (high)": "gpt_image_15",
    "Nano Banana 2 (Gemini 3.1 Flash Image Preview)": "gemini_flash",
    "Nano Banana Pro (Gemini 3 Pro Image)": "gemini_pro",
    "FLUX.2 [max]": "flux2_max",
    "FLUX.2 [pro]": "flux2_pro",
    "FLUX.2 [flex]": "flux2_flex",
    "Imagen 4 Ultra": "imagen4_ultra",
    "Imagen 4 Ultra Preview 0606": "imagen4_ultra",
    "Seedream 4.5": "seedream_45",
    "FLUX.2 [dev] Turbo": "flux2_turbo",
    "Nano Banana (Gemini 2.5 Flash Image)": "nano_banana",
    "FLUX.2 [klein] 9B": "flux2_klein",
    "Imagen 4 Preview 0606": "imagen4_standard",
    "Ideogram 3.0": "ideogram_v3",
}

# Maps AA model display names → our internal slug (image editing)
AA_EDIT_SLUG_MAP: dict[str, str] = {
    "GPT Image 1.5 (high)": "gpt_image_15_edit",
    "Nano Banana Pro (Gemini 3 Pro Image)": "nano_banana_pro_edit",
    "Nano Banana 2 (Gemini 3.1 Flash Image Preview)": "nano_banana2_edit",
    "FLUX.2 [max]": "flux2_max_edit",
    "Seedream 4.5": "seedream_45_edit",
    "Nano Banana (Gemini 2.5 Flash Image)": "nano_banana_edit",
    "FLUX.2 [pro]": "flux2_pro_edit",
    "FLUX.2 [flex]": "flux2_flex_edit",
    "FLUX.1 Kontext Pro": "flux_kontext_pro",
    "FLUX.2 [dev] Turbo": "flux2_turbo_edit",
}

# Known fal.ai endpoints for our slugs (for availability checks)
SLUG_TO_FAL_ENDPOINT: dict[str, str] = {
    "gpt_image_15":       "fal-ai/gpt-image-1.5",
    "gemini_flash":       "fal-ai/nano-banana-2",
    "gemini_pro":         "fal-ai/nano-banana-pro",
    "flux2_max":          "fal-ai/flux-2-max",
    "flux2_pro":          "fal-ai/flux-2-pro",
    "flux2_flex":         "fal-ai/flux-2-flex",
    "imagen4_ultra":      "fal-ai/imagen4/preview/ultra",
    "seedream_45":        "fal-ai/bytedance/seedream/v4.5/text-to-image",
    "flux2_turbo":        "fal-ai/flux-2/turbo",
    "nano_banana":        "fal-ai/nano-banana",
    "flux2_klein":        "fal-ai/flux-2/klein/9b",
    "imagen4_standard":   "fal-ai/imagen4/preview",
    "ideogram_v3":        "fal-ai/ideogram/v3",
    "recraft_v4":         "fal-ai/recraft/v4/text-to-image",
    "fal_ai_schnell":     "fal-ai/flux/schnell",
    # Edit models
    "gpt_image_15_edit":       "fal-ai/gpt-image-1.5/edit",
    "nano_banana_pro_edit":    "fal-ai/nano-banana-pro/edit",
    "nano_banana2_edit":       "fal-ai/nano-banana-2/edit",
    "flux2_max_edit":          "fal-ai/flux-2-max/edit",
    "seedream_45_edit":        "fal-ai/bytedance/seedream/v4.5/edit",
    "nano_banana_edit":        "fal-ai/nano-banana/edit",
    "flux2_pro_edit":          "fal-ai/flux-2-pro/edit",
    "flux2_flex_edit":         "fal-ai/flux-2-flex/edit",
    "flux_kontext_pro":        "fal-ai/flux-pro/kontext",
    "flux2_flash_edit":        "fal-ai/flux-2/flash/edit",
    "flux2_turbo_edit":        "fal-ai/flux-2/turbo/edit",
}


async def _fetch_aa_leaderboard(url: str, client: httpx.AsyncClient) -> list[dict]:
    """Fetch Artificial Analysis leaderboard data."""
    try:
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("models", [])
    except Exception as e:
        logger.warning("model_sync.aa_fetch_failed", url=url, error=str(e))
        return []


async def _fetch_fal_catalog(client: httpx.AsyncClient) -> set[str]:
    """Fetch all text-to-image and image-to-image model IDs from fal.ai."""
    available: set[str] = set()
    for page in range(1, 8):
        try:
            url = FAL_CATALOG_URL.format(page=page)
            resp = await client.get(url, timeout=15.0)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                break
            for m in items:
                mid = m.get("id", "")
                cat = m.get("category", "")
                if cat in ("text-to-image", "image-to-image") and mid:
                    available.add(mid)
        except Exception as e:
            logger.warning("model_sync.fal_fetch_failed", page=page, error=str(e))
            break
    return available


def _parse_aa_rankings(models: list[dict], slug_map: dict[str, str]) -> dict[str, dict]:
    """Extract ELO scores and rank for known models."""
    results: dict[str, dict] = {}
    sorted_models = sorted(models, key=lambda m: m["elos"][0]["elo"], reverse=True)
    for rank, m in enumerate(sorted_models, 1):
        name = m.get("name", "")
        slug = slug_map.get(name)
        if slug:
            elo_data = m["elos"][0]
            results[slug] = {
                "elo_score": round(elo_data["elo"]),
                "elo_rank": rank,
                "price_per_1k": m.get("pricePer1kImages"),
                "appearances": elo_data.get("appearances", 0),
            }
    return results


def _detect_new_models(
    aa_models: list[dict],
    slug_map: dict[str, str],
    fal_catalog: set[str],
) -> list[dict]:
    """Detect AA models that have fal.ai endpoints but aren't in our catalog yet."""
    # Rough name-to-endpoint heuristics for unknown models
    new_models = []
    known_names = set(slug_map.keys())
    for m in aa_models:
        name = m.get("name", "")
        if name in known_names:
            continue
        elo = m["elos"][0]["elo"]
        if elo < 1100:
            continue  # skip low-ranked unknowns
        price = m.get("pricePer1kImages")
        new_models.append({
            "name": name,
            "creator": m.get("creator", {}).get("name", "?"),
            "elo": round(elo),
            "price_per_1k": price,
            "release_date": m.get("releaseDate", "?"),
        })
    return new_models


async def run_model_sync(db=None) -> dict[str, Any]:
    """
    Fetch fresh leaderboard data and update ImageProvider priorities.

    Returns a report dict with:
      - updated: list of slugs whose priority changed
      - new_t2i: unknown models from AA t2i leaderboard (not in catalog)
      - new_edit: unknown models from AA edit leaderboard
      - fal_missing: slugs whose fal endpoint is no longer in catalog
      - synced_at: ISO timestamp
    """
    from app.ai_config.image_models_meta import MODELS_BY_SLUG
    from app.ai_config.image_edit_models_meta import EDIT_MODELS_BY_SLUG

    report: dict[str, Any] = {
        "updated": [],
        "new_t2i": [],
        "new_edit": [],
        "fal_missing": [],
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }

    async with httpx.AsyncClient(
        headers={"User-Agent": "ARIIA-ModelSync/1.0"},
        follow_redirects=True,
    ) as client:
        t2i_models, edit_models, fal_catalog = await asyncio.gather(
            _fetch_aa_leaderboard(AA_T2I_URL, client),
            _fetch_aa_leaderboard(AA_EDIT_URL, client),
            _fetch_fal_catalog(client),
        )

    if not t2i_models and not edit_models:
        logger.warning("model_sync.no_data_received")
        return report

    t2i_rankings = _parse_aa_rankings(t2i_models, AA_T2I_SLUG_MAP)
    edit_rankings = _parse_aa_rankings(edit_models, AA_EDIT_SLUG_MAP)

    # Update ImageProvider priorities based on ELO rank (lower rank = lower priority number = shown first)
    if db is not None:
        from app.ai_config.image_models import ImageProvider
        for slug, ranking in {**t2i_rankings, **edit_rankings}.items():
            provider = db.query(ImageProvider).filter(ImageProvider.slug == slug).first()
            if provider:
                new_priority = ranking["elo_rank"]
                if provider.priority != new_priority:
                    provider.priority = new_priority
                    report["updated"].append({
                        "slug": slug,
                        "old_priority": provider.priority,
                        "new_priority": new_priority,
                        "elo": ranking["elo_score"],
                    })
        if report["updated"]:
            db.commit()

    # Detect new models from AA that aren't in our catalog
    report["new_t2i"] = _detect_new_models(t2i_models, AA_T2I_SLUG_MAP, fal_catalog)
    report["new_edit"] = _detect_new_models(edit_models, AA_EDIT_SLUG_MAP, fal_catalog)

    # Check if our known endpoints are still in fal catalog
    if fal_catalog:
        for slug, endpoint in SLUG_TO_FAL_ENDPOINT.items():
            if endpoint not in fal_catalog:
                report["fal_missing"].append({"slug": slug, "endpoint": endpoint})

    logger.info(
        "model_sync.complete",
        updated=len(report["updated"]),
        new_t2i=len(report["new_t2i"]),
        new_edit=len(report["new_edit"]),
        fal_missing=len(report["fal_missing"]),
    )
    return report


if __name__ == "__main__":
    result = asyncio.run(run_model_sync())
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
