"""Seed default AI image providers at startup."""
from __future__ import annotations
import structlog
from sqlalchemy.orm import Session

logger = structlog.get_logger()

DEFAULT_IMAGE_PROVIDERS = [
    {
        "slug": "fal_ai",
        "name": "fal.ai (FLUX 1.1 Pro)",
        "provider_type": "fal_ai",
        "api_base_url": "https://fal.run",
        "default_model": "fal-ai/flux-pro/v1.1",
        "priority": 5,   # Highest priority (lower number = preferred)
        "is_active": True,
    },
    {
        "slug": "openai_images",
        "name": "OpenAI Images (DALL-E 3)",
        "provider_type": "openai_images",
        "api_base_url": "https://api.openai.com/v1",
        "default_model": "dall-e-3",
        "priority": 10,
        "is_active": True,
    },
    {
        "slug": "stability_ai",
        "name": "Stability AI",
        "provider_type": "stability_ai",
        "api_base_url": "https://api.stability.ai",
        "default_model": "stable-image-core",
        "priority": 20,
        "is_active": False,
    },
    {
        "slug": "fal_ai_schnell",
        "name": "fal.ai (FLUX Schnell — Preview)",
        "provider_type": "fal_ai_schnell",
        "api_base_url": "https://fal.run",
        "default_model": "fal-ai/flux/schnell",
        "priority": 6,   # Used only for preview mode
        "is_active": True,
    },
    {
        "slug": "recraft_v3",
        "name": "Recraft V3 (Brand Style)",
        "provider_type": "recraft_v3",
        "api_base_url": "https://fal.run",
        "default_model": "fal-ai/recraft-v3",
        "priority": 7,   # Used when brand style enabled
        "is_active": True,
    },
    {
        "slug": "ideogram_v2",
        "name": "Ideogram v2 (Text Overlay)",
        "provider_type": "ideogram_v2",
        "api_base_url": "https://fal.run",
        "default_model": "fal-ai/ideogram/v2",
        "priority": 8,   # Used for text-overlay images
        "is_active": True,
    },
]


def seed_image_providers(db: Session) -> None:
    """Idempotently seed default image providers."""
    from app.ai_config.image_models import ImageProvider
    from app.ai_config.encryption import encrypt_api_key
    from config.settings import get_settings

    settings = get_settings()

    for data in DEFAULT_IMAGE_PROVIDERS:
        existing = db.query(ImageProvider).filter(
            ImageProvider.slug == data["slug"]
        ).first()
        if existing:
            # Update api_key if it became available since last seed
            if data["slug"] == "fal_ai" and settings.fal_key and not existing.api_key_encrypted:
                existing.api_key_encrypted = encrypt_api_key(settings.fal_key)
                db.commit()
            if data["slug"] in ("fal_ai_schnell", "recraft_v3", "ideogram_v2") and settings.fal_key:
                if not existing.api_key_encrypted:
                    existing.api_key_encrypted = encrypt_api_key(settings.fal_key)
                    db.commit()
            continue

        provider = ImageProvider(**data)

        if data["slug"] == "fal_ai" and settings.fal_key:
            provider.api_key_encrypted = encrypt_api_key(settings.fal_key)
        elif data["slug"] == "openai_images" and settings.openai_api_key:
            provider.api_key_encrypted = encrypt_api_key(settings.openai_api_key)
        elif data["slug"] in ("fal_ai_schnell", "recraft_v3", "ideogram_v2") and settings.fal_key:
            provider.api_key_encrypted = encrypt_api_key(settings.fal_key)

        db.add(provider)
        logger.info("image_seed.provider_created", slug=data["slug"])

    db.commit()
    logger.info("image_seed.complete")
