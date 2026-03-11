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
    # Selectable models (sorted by Elo rank from Artificial Analysis Arena)
    {"slug": "gemini_flash",    "name": "Gemini 3.1 Flash (Nano Banana 2)","provider_type": "fal_generic",    "default_model": "fal-ai/gemini-3.1-flash-image-preview",        "priority": 1,  "is_active": True},
    {"slug": "gemini_pro",      "name": "Gemini 3 Pro (Nano Banana Pro)",  "provider_type": "fal_generic",    "default_model": "fal-ai/gemini-3-pro-image-preview",            "priority": 2,  "is_active": True},
    {"slug": "gpt_image_15",    "name": "GPT Image 1.5 (High)",            "provider_type": "fal_generic",    "default_model": "fal-ai/gpt-image-1.5",                         "priority": 3,  "is_active": True},
    {"slug": "imagen4_ultra",   "name": "Imagen 4 Ultra",                  "provider_type": "fal_generic",    "default_model": "fal-ai/imagen4/preview/ultra",                 "priority": 4,  "is_active": True},
    {"slug": "flux2_pro",       "name": "FLUX.2 Pro",                      "provider_type": "fal_generic",    "default_model": "fal-ai/flux-2-pro",                            "priority": 5,  "is_active": True},
    {"slug": "seedream_45",     "name": "Seedream 4.5 (ByteDance)",        "provider_type": "fal_generic",    "default_model": "fal-ai/bytedance/seedream/v4.5/text-to-image", "priority": 6,  "is_active": True},
    {"slug": "flux2_turbo",     "name": "FLUX.2 Dev Turbo",                "provider_type": "fal_generic",    "default_model": "fal-ai/flux-2/turbo",                          "priority": 7,  "is_active": True},
    {"slug": "flux2_klein",     "name": "FLUX.2 Klein 9B",                 "provider_type": "fal_generic",    "default_model": "fal-ai/flux-2/klein/9b",                       "priority": 8,  "is_active": True},
    {"slug": "imagen4_standard","name": "Imagen 4 Standard",               "provider_type": "fal_generic",    "default_model": "fal-ai/imagen4/preview",                       "priority": 9,  "is_active": True},
    {"slug": "ideogram_v3",     "name": "Ideogram V3",                     "provider_type": "fal_generic",    "default_model": "fal-ai/ideogram/v3",                           "priority": 10, "is_active": True},
    {"slug": "recraft_v4",      "name": "Recraft V4",                      "provider_type": "fal_generic",    "default_model": "fal-ai/recraft/v4/text-to-image",              "priority": 11, "is_active": True},
    # Image editing models (img2img)
    {"slug": "nano_banana2_edit","name": "Nano Banana 2 Edit (Gemini Flash)","provider_type": "fal_generic",   "default_model": "fal-ai/gemini-3.1-flash-image-preview/edit",   "priority": 20, "is_active": True},
    {"slug": "gpt_image_15_edit","name": "GPT Image 1.5 Edit",             "provider_type": "fal_generic",    "default_model": "fal-ai/gpt-image-1.5/edit",                    "priority": 21, "is_active": True},
    {"slug": "seedream_45_edit", "name": "Seedream 4.5 Edit",              "provider_type": "fal_generic",    "default_model": "fal-ai/bytedance/seedream/v4.5/edit",          "priority": 22, "is_active": True},
    {"slug": "flux2_flash_edit", "name": "FLUX.2 Dev Flash Edit",          "provider_type": "fal_generic",    "default_model": "fal-ai/flux-2/flash/edit",                     "priority": 23, "is_active": True},
    {"slug": "flux2_turbo_edit", "name": "FLUX.2 Dev Turbo Edit",          "provider_type": "fal_generic",    "default_model": "fal-ai/flux-2/turbo/edit",                     "priority": 24, "is_active": True},
    {"slug": "flux_kontext_pro", "name": "FLUX.1 Kontext Pro",             "provider_type": "fal_generic",    "default_model": "fal-ai/flux-pro/kontext",                      "priority": 25, "is_active": True},
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
