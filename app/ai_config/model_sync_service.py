"""Auto-sync image model catalog from fal.ai (primary) + Artificial Analysis (ELO).

Priority logic:
  1. Fetch fal.ai catalog — add new models, deactivate removed, update names/endpoints.
  2. Fetch AA leaderboards — apply ELO scores and set priority = elo_rank for matched models.
  3. Unranked active models — priority = 9001 + index (newest first among unknowns).

Usage:
    From code:  from app.ai_config.model_sync_service import run_model_sync
                result = await run_model_sync(db)
    From CLI:   python -m app.ai_config.model_sync_service
"""
from __future__ import annotations
import asyncio
import re
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


def _slug_from_fal_id(fal_id: str) -> str:
    """Derive a stable DB slug from a fal.ai model ID.

    e.g. "fal-ai/flux-2-pro"  → "flux2_pro"  (but existing DB slugs take precedence)
         "fal-ai/some/new/model" → "fal_some_new_model"
    """
    s = fal_id.replace("fal-ai/", "fal_")
    s = re.sub(r"[/\-\.]", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:64]


async def _fetch_fal_catalog(client: httpx.AsyncClient) -> list[dict]:
    """Fetch all text-to-image and image-to-image models from fal.ai catalog."""
    models: list[dict] = []
    for page in range(1, 12):
        try:
            url = FAL_CATALOG_URL.format(page=page)
            resp = await client.get(url, timeout=15.0)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                break
            for m in items:
                fal_id = m.get("id", "")
                cat = m.get("category", "")
                if cat in ("text-to-image", "image-to-image") and fal_id:
                    models.append({
                        "id": fal_id,
                        "category": cat,
                        # fal catalog uses various field names for title/name
                        "title": (
                            m.get("title") or m.get("name") or m.get("display_name")
                            or fal_id.split("/")[-1].replace("-", " ").title()
                        ),
                        # Pricing: look for common field patterns
                        "price_per_image": (
                            m.get("price_per_image")
                            or m.get("pricePerImage")
                            or (m.get("pricing") or {}).get("price_per_image")
                            or (m.get("pricing") or {}).get("inference")
                        ),
                        "created_at": m.get("created_at") or m.get("publishedAt") or m.get("createdAt"),
                    })
        except Exception as e:
            logger.warning("model_sync.fal_fetch_failed", page=page, error=str(e))
            break
    return models


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
            }
    return results


def _reconcile_fal_catalog(db, fal_models: list[dict]) -> dict[str, Any]:
    """Step 1: Add/update/deactivate ImageProviders based on fal catalog.

    Matching key: default_model (the fal endpoint ID).
    New models are created with priority=9000 (to be updated in step 3).
    Returns report dict.
    """
    from app.ai_config.image_models import ImageProvider
    from app.ai_config.encryption import encrypt_api_key
    from app.ai_config.image_credits_config import price_to_credits
    from config.settings import get_settings

    settings = get_settings()
    fal_key_enc = encrypt_api_key(settings.fal_key) if settings.fal_key else None

    report = {"added": [], "updated": [], "deactivated": [], "reactivated": []}

    fal_ids_in_catalog = {m["id"] for m in fal_models}

    # Index existing fal_generic providers by default_model
    existing_by_endpoint: dict[str, Any] = {}
    for p in db.query(ImageProvider).filter(
        ImageProvider.provider_type.in_(["fal_generic", "fal_ai", "fal_ai_schnell", "recraft_v3", "ideogram_v2"])
    ).all():
        if p.default_model:
            existing_by_endpoint[p.default_model] = p

    for m in fal_models:
        fal_id = m["id"]
        title = m["title"]
        category = m["category"]  # "text-to-image" or "image-to-image"
        price = m["price_per_image"]

        existing = existing_by_endpoint.get(fal_id)

        if existing:
            changed = False
            # Reactivate if was deactivated
            if not existing.is_active:
                existing.is_active = True
                report["reactivated"].append(fal_id)
                changed = True
            # Update fal_category if missing
            if not existing.fal_category:
                existing.fal_category = category
                changed = True
            # Update price if we got one and it's new info
            if price is not None and existing.price_per_image_cents is None:
                existing.price_per_image_cents = int(round(float(price) * 100000))  # store as micro-cents
                changed = True
            if changed:
                report["updated"].append(fal_id)
        else:
            # New model — auto-create
            slug = _slug_from_fal_id(fal_id)
            # Ensure slug uniqueness
            base_slug = slug
            counter = 1
            while db.query(ImageProvider).filter(ImageProvider.slug == slug).first():
                slug = f"{base_slug}_{counter}"
                counter += 1

            auto_credit_cost = price_to_credits(price)
            new_provider = ImageProvider(
                slug=slug,
                name=title,
                provider_type="fal_generic",
                api_base_url="https://fal.run",
                default_model=fal_id,
                fal_category=category,
                priority=9000,  # Will be sorted in step 3
                is_active=True,
                price_per_image_cents=int(round(float(price) * 100000)) if price is not None else None,
            )
            if fal_key_enc:
                new_provider.api_key_encrypted = fal_key_enc
            db.add(new_provider)
            report["added"].append({"slug": slug, "fal_id": fal_id, "category": category, "credits": auto_credit_cost})
            logger.info("model_sync.new_model_added", slug=slug, fal_id=fal_id, category=category)

    # Deactivate models that are no longer in fal catalog
    for endpoint, provider in existing_by_endpoint.items():
        if endpoint not in fal_ids_in_catalog and provider.is_active:
            provider.is_active = False
            report["deactivated"].append(endpoint)
            logger.info("model_sync.model_deactivated", endpoint=endpoint)

    db.commit()
    return report


def _apply_aa_rankings(db, t2i_rankings: dict, edit_rankings: dict) -> list[dict]:
    """Step 2: Update ELO scores and set priority = elo_rank for matched providers."""
    from app.ai_config.image_models import ImageProvider

    updated = []
    for slug, ranking in {**t2i_rankings, **edit_rankings}.items():
        provider = db.query(ImageProvider).filter(ImageProvider.slug == slug).first()
        if provider:
            old_priority = provider.priority
            provider.elo_score = ranking["elo_score"]
            provider.elo_rank = ranking["elo_rank"]
            provider.priority = ranking["elo_rank"]
            if old_priority != ranking["elo_rank"]:
                updated.append({
                    "slug": slug,
                    "old_priority": old_priority,
                    "new_priority": ranking["elo_rank"],
                    "elo": ranking["elo_score"],
                })

    if updated:
        db.commit()
    return updated


def _sort_unranked(db) -> None:
    """Step 3: Assign priority 9001+ to active providers without ELO rank.

    Newest (by created_at DESC) gets 9001, then ascending.
    This puts the most recently added unknown models first among the unknowns.
    """
    from app.ai_config.image_models import ImageProvider

    unranked = (
        db.query(ImageProvider)
        .filter(
            ImageProvider.is_active.is_(True),
            ImageProvider.elo_rank.is_(None),
        )
        .order_by(ImageProvider.created_at.desc())
        .all()
    )
    for i, provider in enumerate(unranked):
        provider.priority = 9001 + i

    if unranked:
        db.commit()


async def run_model_sync(db=None) -> dict[str, Any]:
    """
    Full model sync: fal catalog → DB reconciliation → AA ELO → unranked sorting.

    Returns report dict with:
      - added: new fal models auto-created in DB
      - updated: providers whose data was updated
      - deactivated: providers no longer in fal catalog
      - reactivated: providers that came back to fal catalog
      - elo_updated: slugs whose priority/ELO changed
      - synced_at: ISO timestamp
    """
    report: dict[str, Any] = {
        "added": [],
        "updated": [],
        "deactivated": [],
        "reactivated": [],
        "elo_updated": [],
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }

    async with httpx.AsyncClient(
        headers={"User-Agent": "ARIIA-ModelSync/2.0"},
        follow_redirects=True,
    ) as client:
        fal_models, t2i_aa_models, edit_aa_models = await asyncio.gather(
            _fetch_fal_catalog(client),
            _fetch_aa_leaderboard(AA_T2I_URL, client),
            _fetch_aa_leaderboard(AA_EDIT_URL, client),
        )

    logger.info(
        "model_sync.data_fetched",
        fal_models=len(fal_models),
        aa_t2i=len(t2i_aa_models),
        aa_edit=len(edit_aa_models),
    )

    if not fal_models:
        logger.warning("model_sync.fal_catalog_empty")
        return report

    if db is not None:
        # Step 1: Reconcile fal catalog
        cat_report = _reconcile_fal_catalog(db, fal_models)
        report["added"] = cat_report["added"]
        report["updated"] = cat_report["updated"]
        report["deactivated"] = cat_report["deactivated"]
        report["reactivated"] = cat_report["reactivated"]

        # Step 2: Apply AA ELO rankings
        t2i_rankings = _parse_aa_rankings(t2i_aa_models, AA_T2I_SLUG_MAP)
        edit_rankings = _parse_aa_rankings(edit_aa_models, AA_EDIT_SLUG_MAP)
        report["elo_updated"] = _apply_aa_rankings(db, t2i_rankings, edit_rankings)

        # Step 3: Sort unranked models (newest first, after all ranked models)
        _sort_unranked(db)

    logger.info(
        "model_sync.complete",
        added=len(report["added"]),
        updated=len(report["updated"]),
        deactivated=len(report["deactivated"]),
        reactivated=len(report["reactivated"]),
        elo_updated=len(report["elo_updated"]),
    )
    return report


if __name__ == "__main__":
    result = asyncio.run(run_model_sync())
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
