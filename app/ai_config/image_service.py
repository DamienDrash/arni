"""ImageConfigService: manage AI image providers and resolve config for tenants."""
from __future__ import annotations
from typing import Optional
from dataclasses import dataclass
import structlog
from sqlalchemy.orm import Session
from fastapi import HTTPException

logger = structlog.get_logger()


@dataclass
class ResolvedImageConfig:
    provider_slug: str
    provider_type: str
    api_base_url: str
    api_key: str
    model: str
    is_byok: bool = False


class ImageConfigService:
    def __init__(self, db: Session):
        self._db = db

    def resolve_image_provider(self, tenant_id: int) -> ResolvedImageConfig:
        """Resolve image provider for a tenant. Priority: Tenant BYOK > Platform default."""
        from app.ai_config.image_models import ImageProvider, TenantImageProvider
        from app.ai_config.encryption import decrypt_api_key

        # 1. Check tenant BYOK
        byok = self._db.query(TenantImageProvider).filter(
            TenantImageProvider.tenant_id == tenant_id,
            TenantImageProvider.is_active.is_(True),
        ).first()

        if byok:
            platform = self._db.query(ImageProvider).filter(
                ImageProvider.id == byok.provider_id,
                ImageProvider.is_active.is_(True),
            ).first()
            if platform:
                api_key = decrypt_api_key(byok.api_key_encrypted) if byok.api_key_encrypted else \
                          decrypt_api_key(platform.api_key_encrypted) if platform.api_key_encrypted else ""
                return ResolvedImageConfig(
                    provider_slug=platform.slug,
                    provider_type=platform.provider_type,
                    api_base_url=platform.api_base_url,
                    api_key=api_key,
                    model=byok.preferred_model or platform.default_model or "dall-e-3",
                    is_byok=True,
                )

        # 2. Fall back to platform provider (lowest priority number = highest priority)
        platform = self._db.query(ImageProvider).filter(
            ImageProvider.is_active.is_(True),
        ).order_by(ImageProvider.priority).first()

        if not platform:
            raise HTTPException(
                status_code=402,
                detail="No AI image provider is configured. Please contact your administrator.",
            )

        api_key = decrypt_api_key(platform.api_key_encrypted) if platform.api_key_encrypted else ""
        if not api_key:
            raise HTTPException(
                status_code=402,
                detail="AI image provider is not configured with an API key.",
            )

        return ResolvedImageConfig(
            provider_slug=platform.slug,
            provider_type=platform.provider_type,
            api_base_url=platform.api_base_url,
            api_key=api_key,
            model=platform.default_model or "dall-e-3",
            is_byok=False,
        )

    def resolve_provider_for_mode(
        self,
        tenant_id: int,
        mode: str = "final",
        has_text_overlay: bool = False,
        use_brand_style: bool = False,
    ) -> "ResolvedImageConfig":
        """Select the best provider based on generation mode and features.

        Priority:
        1. preview mode → FLUX Schnell
        2. has_text_overlay → Ideogram v2
        3. use_brand_style → Recraft V3
        4. default → FLUX 1.1 Pro (fal_ai)
        """
        from app.ai_config.image_models import ImageProvider
        from app.ai_config.encryption import decrypt_api_key

        if mode == "preview":
            target_slug = "fal_ai_schnell"
        elif has_text_overlay:
            target_slug = "ideogram_v2"
        elif use_brand_style:
            target_slug = "recraft_v3"
        else:
            target_slug = "fal_ai"

        provider = self._db.query(ImageProvider).filter(
            ImageProvider.slug == target_slug,
            ImageProvider.is_active.is_(True),
        ).first()

        # Fall back to fal_ai if target not available
        if not provider:
            provider = self._db.query(ImageProvider).filter(
                ImageProvider.slug == "fal_ai",
                ImageProvider.is_active.is_(True),
            ).first()

        if not provider:
            raise HTTPException(status_code=402, detail="No AI image provider configured.")

        api_key = decrypt_api_key(provider.api_key_encrypted) if provider.api_key_encrypted else ""
        if not api_key:
            raise HTTPException(status_code=402, detail="AI image provider has no API key configured.")

        return ResolvedImageConfig(
            provider_slug=provider.slug,
            provider_type=provider.provider_type,
            api_base_url=provider.api_base_url,
            api_key=api_key,
            model=provider.default_model or "fal-ai/flux-pro/v1.1",
            is_byok=False,
        )

    def resolve_provider_by_slug(self, tenant_id: int, slug: str) -> "ResolvedImageConfig":
        """Resolve a specific provider by slug (user model selection)."""
        from app.ai_config.image_models import ImageProvider
        from app.ai_config.encryption import decrypt_api_key

        provider = self._db.query(ImageProvider).filter(
            ImageProvider.slug == slug,
            ImageProvider.is_active.is_(True),
        ).first()

        if not provider:
            # Slug not in DB → fall back to default
            logger.warning("image_service.slug_not_found", slug=slug)
            return self.resolve_image_provider(tenant_id)

        api_key = decrypt_api_key(provider.api_key_encrypted) if provider.api_key_encrypted else ""
        if not api_key:
            logger.warning("image_service.slug_no_key", slug=slug)
            return self.resolve_image_provider(tenant_id)

        return ResolvedImageConfig(
            provider_slug=provider.slug,
            provider_type=provider.provider_type,
            api_base_url=provider.api_base_url,
            api_key=api_key,
            model=provider.default_model or "",
            is_byok=False,
        )

    def list_providers(self) -> list:
        from app.ai_config.image_models import ImageProvider
        return self._db.query(ImageProvider).order_by(ImageProvider.priority).all()

    def create_provider(self, data: dict) -> object:
        from app.ai_config.image_models import ImageProvider
        from app.ai_config.encryption import encrypt_api_key
        api_key = data.pop("api_key", None)
        provider = ImageProvider(**data)
        if api_key:
            provider.api_key_encrypted = encrypt_api_key(api_key)
        self._db.add(provider)
        self._db.commit()
        self._db.refresh(provider)
        return provider

    def update_provider(self, provider_id: int, data: dict) -> object:
        from app.ai_config.image_models import ImageProvider
        from app.ai_config.encryption import encrypt_api_key
        provider = self._db.query(ImageProvider).filter(ImageProvider.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        api_key = data.pop("api_key", None)
        for k, v in data.items():
            setattr(provider, k, v)
        if api_key:
            provider.api_key_encrypted = encrypt_api_key(api_key)
        self._db.commit()
        self._db.refresh(provider)
        return provider

    def deactivate_provider(self, provider_id: int) -> None:
        from app.ai_config.image_models import ImageProvider
        provider = self._db.query(ImageProvider).filter(ImageProvider.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        provider.is_active = False
        self._db.commit()

    def get_tenant_override(self, tenant_id: int) -> Optional[object]:
        from app.ai_config.image_models import TenantImageProvider
        return self._db.query(TenantImageProvider).filter(
            TenantImageProvider.tenant_id == tenant_id,
            TenantImageProvider.is_active.is_(True),
        ).first()

    def set_tenant_override(self, tenant_id: int, data: dict) -> object:
        from app.ai_config.image_models import TenantImageProvider
        from app.ai_config.encryption import encrypt_api_key
        existing = self._db.query(TenantImageProvider).filter(
            TenantImageProvider.tenant_id == tenant_id,
        ).first()
        api_key = data.pop("api_key", None)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            if api_key:
                existing.api_key_encrypted = encrypt_api_key(api_key)
            existing.is_active = True
            self._db.commit()
            self._db.refresh(existing)
            return existing
        override = TenantImageProvider(tenant_id=tenant_id, **data)
        if api_key:
            override.api_key_encrypted = encrypt_api_key(api_key)
        self._db.add(override)
        self._db.commit()
        self._db.refresh(override)
        return override

    def remove_tenant_override(self, tenant_id: int, override_id: int) -> None:
        from app.ai_config.image_models import TenantImageProvider
        override = self._db.query(TenantImageProvider).filter(
            TenantImageProvider.id == override_id,
            TenantImageProvider.tenant_id == tenant_id,
        ).first()
        if not override:
            raise HTTPException(status_code=404, detail="Override not found")
        override.is_active = False
        self._db.commit()
