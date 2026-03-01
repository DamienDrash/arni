"""ARIIA v2.0 – Integration Registry Models.

@ARCH: Phase 2, Meilenstein 2.1 – Integration & Skills
Database models for the Integration Registry: the central catalog of all
integrations, capabilities, and tenant-specific activation/configuration.

Three core tables:
  - IntegrationDefinition: Available integrations (e.g., Magicline, Shopify)
  - CapabilityDefinition: Abstract business capabilities (e.g., crm.customer.search)
  - IntegrationCapability: Links integrations to their capabilities
  - TenantIntegration: Per-tenant activation and configuration

Design Principles:
  - Capabilities are abstract; the same capability can be provided by different integrations.
  - Integrations are self-describing via config_schema (JSON Schema for setup fields).
  - Tenant isolation is enforced via tenant_id on TenantIntegration.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.db import Base


# ─── Enums ───────────────────────────────────────────────────────────────────

import enum


class IntegrationCategory(str, enum.Enum):
    """Categories for grouping integrations in the marketplace."""
    CRM = "crm"
    BOOKING = "booking"
    PAYMENT = "payment"
    MESSAGING = "messaging"
    ANALYTICS = "analytics"
    ECOMMERCE = "ecommerce"
    FITNESS = "fitness"
    CUSTOM = "custom"


class AuthType(str, enum.Enum):
    """Authentication methods supported by integrations."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    NONE = "none"


class IntegrationStatus(str, enum.Enum):
    """Status of a tenant's integration activation."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING_SETUP = "pending_setup"


# ─── Integration Definition ──────────────────────────────────────────────────


class IntegrationDefinition(Base):
    """A globally available integration in the ARIIA marketplace.

    Each row represents a type of integration (e.g., "Magicline", "Shopify")
    that tenants can activate. The config_schema field contains a JSON Schema
    describing what configuration fields are needed (API keys, URLs, etc.).
    """
    __tablename__ = "integration_definitions"

    id = Column(String(32), primary_key=True)  # e.g., "magicline", "shopify"
    name = Column(String(100), nullable=False)  # Human-readable: "Magicline"
    description = Column(Text, nullable=True)
    category = Column(
        String(32),
        nullable=False,
        default=IntegrationCategory.CUSTOM.value,
    )
    logo_url = Column(Text, nullable=True)
    auth_type = Column(
        String(16),
        nullable=False,
        default=AuthType.API_KEY.value,
    )
    config_schema = Column(JSONB, nullable=True)  # JSON Schema for setup fields
    adapter_class = Column(String(255), nullable=True)  # e.g., "app.integrations.adapters.magicline_adapter.MagiclineAdapter"
    skill_file = Column(String(255), nullable=True)  # e.g., "skills/crm/magicline.SKILL.md"
    is_public = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    min_plan = Column(String(32), nullable=True, default="professional")  # Minimum plan required
    version = Column(String(16), nullable=True, default="1.0.0")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    capabilities = relationship(
        "IntegrationCapability",
        back_populates="integration",
        cascade="all, delete-orphan",
    )
    tenant_integrations = relationship(
        "TenantIntegration",
        back_populates="integration",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<IntegrationDefinition(id='{self.id}', name='{self.name}')>"


# ─── Capability Definition ────────────────────────────────────────────────────


class CapabilityDefinition(Base):
    """An abstract business capability that integrations can provide.

    Capabilities are integration-agnostic. For example, 'crm.customer.search'
    can be provided by Magicline, Shopify, or a manual CRM adapter.
    The input_schema and output_schema define the contract for tool calling.
    """
    __tablename__ = "capability_definitions"

    id = Column(String(64), primary_key=True)  # e.g., "crm.customer.search"
    name = Column(String(100), nullable=False)  # Human-readable
    description = Column(Text, nullable=True)
    input_schema = Column(JSONB, nullable=True)  # JSON Schema for LLM tool calling params
    output_schema = Column(JSONB, nullable=True)  # JSON Schema for return data
    is_destructive = Column(Boolean, default=False, nullable=False)
    category = Column(String(32), nullable=True)  # Group: "crm", "booking", etc.

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    integrations = relationship(
        "IntegrationCapability",
        back_populates="capability",
        cascade="all, delete-orphan",
    )

    def to_openai_tool(self) -> dict:
        """Convert this capability to an OpenAI function-calling tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.id.replace(".", "_"),  # OpenAI doesn't allow dots
                "description": self.description or self.name,
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }

    def __repr__(self) -> str:
        return f"<CapabilityDefinition(id='{self.id}', name='{self.name}')>"


# ─── Integration ↔ Capability Link ───────────────────────────────────────────


class IntegrationCapability(Base):
    """Links an integration to the capabilities it provides.

    This is a many-to-many relationship: one integration can provide many
    capabilities, and one capability can be provided by many integrations.
    """
    __tablename__ = "integration_capabilities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    integration_id = Column(
        String(32),
        ForeignKey("integration_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capability_id = Column(
        String(64),
        ForeignKey("capability_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("integration_id", "capability_id", name="uq_integration_capability"),
    )

    # Relationships
    integration = relationship("IntegrationDefinition", back_populates="capabilities")
    capability = relationship("CapabilityDefinition", back_populates="integrations")

    def __repr__(self) -> str:
        return f"<IntegrationCapability(integration='{self.integration_id}', capability='{self.capability_id}')>"


# ─── Tenant Integration (per-tenant activation) ──────────────────────────────


class TenantIntegration(Base):
    """A tenant's activation and configuration of a specific integration.

    Each row represents one tenant's use of one integration, including
    their encrypted credentials and current status.
    """
    __tablename__ = "tenant_integrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id = Column(
        String(32),
        ForeignKey("integration_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        String(16),
        nullable=False,
        default=IntegrationStatus.PENDING_SETUP.value,
    )
    config_encrypted = Column(Text, nullable=True)  # Encrypted JSON with credentials
    config_meta = Column(JSONB, nullable=True)  # Non-sensitive config metadata
    enabled = Column(Boolean, default=True, nullable=False)
    last_health_check = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "integration_id", name="uq_tenant_integration"),
    )

    # Relationships
    integration = relationship("IntegrationDefinition", back_populates="tenant_integrations")

    def __repr__(self) -> str:
        return f"<TenantIntegration(tenant={self.tenant_id}, integration='{self.integration_id}', status='{self.status}')>"
