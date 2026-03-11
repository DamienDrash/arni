"""ARIIA AI Config – Image Provider Database Models.

Parallel subsystem to LLMProvider/TenantLLMProvider for image generation.
Uses the same encryption utilities and audit log table.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean,
    ForeignKey, UniqueConstraint,
)
from app.core.db import Base


class ImageProvider(Base):
    """Platform-level catalog of image generation providers (DALL-E, Stability AI, fal.ai)."""
    __tablename__ = "ai_image_providers"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    provider_type = Column(String(32), nullable=False)          # "openai_images" | "stability_ai" | "fal_ai"
    api_base_url = Column(String(512), nullable=False)
    api_key_encrypted = Column(Text, nullable=True)             # Platform master key (encrypted)
    supported_models_json = Column(Text, nullable=True)         # JSON: ["dall-e-3", "dall-e-2"]
    default_model = Column(String(128), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=9000)    # Lower = higher priority; ELO rank for ranked, 9000+ for unranked

    # Enrichment (updated by model_sync_service)
    fal_category = Column(String(32), nullable=True)            # "text-to-image" | "image-to-image"
    elo_score = Column(Integer, nullable=True)                  # Elo score from AA leaderboard
    elo_rank = Column(Integer, nullable=True)                   # Elo rank (1 = best) from AA leaderboard
    price_per_image_cents = Column(Integer, nullable=True)      # Pricing from fal catalog (in €-cents * 1000, i.e. milli-cents)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class TenantImageProvider(Base):
    """Tenant-specific image provider configuration (BYOK)."""
    __tablename__ = "ai_tenant_image_providers"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("ai_image_providers.id"), nullable=False)
    api_key_encrypted = Column(Text, nullable=True)
    preferred_model = Column(String(128), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_id", name="uq_tenant_image_provider"),
    )
