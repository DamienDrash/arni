"""Seed default AI image providers at startup."""
from __future__ import annotations
import structlog
from sqlalchemy.orm import Session

logger = structlog.get_logger()

DEFAULT_IMAGE_PROVIDERS = [
    {
        "slug": "openai_images",
        "name": "OpenAI Images (DALL-E)",
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
            continue

        provider = ImageProvider(**data)

        # Store openai_api_key for openai_images provider if available
        if data["slug"] == "openai_images" and settings.openai_api_key:
            provider.api_key_encrypted = encrypt_api_key(settings.openai_api_key)

        db.add(provider)
        logger.info("image_seed.provider_created", slug=data["slug"])

    db.commit()
    logger.info("image_seed.complete")
