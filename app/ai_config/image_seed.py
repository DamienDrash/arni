"""Seed default AI image providers at startup."""
from __future__ import annotations
import structlog
from sqlalchemy.orm import Session

logger = structlog.get_logger()

# All fal.ai-based providers (slug → fal endpoint)
_FAL_PROVIDERS = [
    # Legacy / routing providers
    {"slug": "fal_ai",          "name": "fal.ai (FLUX 1.1 Pro)",          "provider_type": "fal_ai",         "default_model": "fal-ai/flux-pro/v1.1",                        "priority": 5,  "is_active": True},
    {"slug": "fal_ai_schnell",  "name": "FLUX Schnell (Vorschau)",         "provider_type": "fal_ai_schnell", "default_model": "fal-ai/flux/schnell",                          "priority": 6,  "is_active": True},
    {"slug": "recraft_v3",      "name": "Recraft V3 (Brand Style)",        "provider_type": "recraft_v3",     "default_model": "fal-ai/recraft-v3",                            "priority": 7,  "is_active": True},
    {"slug": "ideogram_v2",     "name": "Ideogram V2 (Text Overlay)",      "provider_type": "ideogram_v2",    "default_model": "fal-ai/ideogram/v2",                           "priority": 8,  "is_active": True},
    # Top 10 selectable models via fal_generic dispatcher
    {"slug": "flux2_pro",       "name": "FLUX.2 Pro",                      "provider_type": "fal_generic",    "default_model": "fal-ai/flux-2-pro",                            "priority": 1,  "is_active": True},
    {"slug": "flux2_max",       "name": "FLUX.2 Max",                      "provider_type": "fal_generic",    "default_model": "fal-ai/flux-2-max",                            "priority": 2,  "is_active": True},
    {"slug": "flux2_flex",      "name": "FLUX.2 Flex",                     "provider_type": "fal_generic",    "default_model": "fal-ai/flux-2-flex",                           "priority": 3,  "is_active": True},
    {"slug": "seedream_45",     "name": "Seedream 4.5 (ByteDance)",        "provider_type": "fal_generic",    "default_model": "fal-ai/bytedance/seedream/v4.5/text-to-image", "priority": 9,  "is_active": True},
    {"slug": "recraft_v4",      "name": "Recraft V4",                      "provider_type": "fal_generic",    "default_model": "fal-ai/recraft/v4/text-to-image",              "priority": 10, "is_active": True},
    {"slug": "ideogram_v3_turbo","name": "Ideogram V3 Turbo",              "provider_type": "fal_generic",    "default_model": "fal-ai/ideogram/v3",                           "priority": 11, "is_active": True},
    {"slug": "flux_pro_ultra",  "name": "FLUX 1.1 Pro Ultra (Raw)",        "provider_type": "fal_generic",    "default_model": "fal-ai/flux-pro/v1.1-ultra",                   "priority": 12, "is_active": True},
    {"slug": "hidream_fast",    "name": "HiDream I1 Fast",                 "provider_type": "fal_generic",    "default_model": "fal-ai/hidream-i1-fast",                       "priority": 13, "is_active": True},
]

_OPENAI_PROVIDERS = [
    {"slug": "openai_images",   "name": "OpenAI Images (DALL-E 3)",        "provider_type": "openai_images",  "default_model": "dall-e-3",                                     "priority": 20, "is_active": True, "api_base_url": "https://api.openai.com/v1"},
]


def seed_image_providers(db: Session) -> None:
    """Idempotently seed default image providers."""
    from app.ai_config.image_models import ImageProvider
    from app.ai_config.encryption import encrypt_api_key
    from config.settings import get_settings

    settings = get_settings()
    fal_key_enc = encrypt_api_key(settings.fal_key) if settings.fal_key else None
    openai_key_enc = encrypt_api_key(settings.openai_api_key) if settings.openai_api_key else None

    all_providers = [
        {**p, "api_base_url": "https://fal.run", "_key_enc": fal_key_enc}
        for p in _FAL_PROVIDERS
    ] + [
        {**p, "_key_enc": openai_key_enc}
        for p in _OPENAI_PROVIDERS
    ]

    for data in all_providers:
        key_enc = data.pop("_key_enc", None)
        existing = db.query(ImageProvider).filter(ImageProvider.slug == data["slug"]).first()
        if existing:
            # Backfill key if it became available
            if key_enc and not existing.api_key_encrypted:
                existing.api_key_encrypted = key_enc
                db.commit()
            # Update name/model if changed (non-destructive)
            if existing.name != data["name"] or existing.default_model != data["default_model"]:
                existing.name = data["name"]
                existing.default_model = data["default_model"]
                db.commit()
            continue

        provider = ImageProvider(**data)
        if key_enc:
            provider.api_key_encrypted = key_enc
        db.add(provider)
        logger.info("image_seed.provider_created", slug=data["slug"])

    db.commit()
    logger.info("image_seed.complete")
