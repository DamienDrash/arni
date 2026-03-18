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
from sqlalchemy.orm import relationship

from app.core.db import Base, FlexibleJSON


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
    config_schema = Column(FlexibleJSON, nullable=True)  # JSON Schema for setup fields
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
    input_schema = Column(FlexibleJSON, nullable=True)  # JSON Schema for LLM tool calling params
    output_schema = Column(FlexibleJSON, nullable=True)  # JSON Schema for return data
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
    config_meta = Column(FlexibleJSON, nullable=True)  # Non-sensitive config metadata
    enabled = Column(Boolean, default=True, nullable=False)
    last_health_check = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    # ── Sync-specific columns (Contact-Sync Refactoring) ────────────────
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(16), default="idle")
    last_sync_error = Column(Text, nullable=True)
    sync_direction = Column(String(16), default="inbound")  # inbound, outbound, bidirectional
    sync_mode = Column(String(16), default="full")  # full, incremental
    records_synced_total = Column(Integer, default=0)
    health_status = Column(String(16), default="unknown")  # healthy, degraded, unhealthy, unknown
    health_checked_at = Column(DateTime, nullable=True)

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
    sync_logs = relationship(
        "SyncLog", back_populates="tenant_integration",
        cascade="all, delete-orphan", order_by="SyncLog.created_at.desc()",
    )
    schedule = relationship(
        "SyncSchedule", back_populates="tenant_integration",
        uselist=False, cascade="all, delete-orphan",
    )
    webhook_endpoints = relationship(
        "WebhookEndpoint", back_populates="tenant_integration",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_definition: bool = False) -> dict:
        """Serialize to dictionary for API responses."""
        result = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "integration_id": self.integration_id,
            "status": self.status,
            "enabled": self.enabled,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "last_sync_status": self.last_sync_status,
            "last_sync_error": self.last_sync_error,
            "sync_direction": self.sync_direction,
            "sync_mode": self.sync_mode,
            "records_synced_total": self.records_synced_total or 0,
            "health_status": self.health_status,
            "health_checked_at": self.health_checked_at.isoformat() if self.health_checked_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_definition and self.integration:
            result["definition"] = {
                "id": self.integration.id,
                "name": self.integration.name,
                "description": self.integration.description,
                "category": self.integration.category,
                "logo_url": self.integration.logo_url,
                "config_schema": self.integration.config_schema,
                "min_plan": self.integration.min_plan,
            }
        return result

    def __repr__(self) -> str:
        return f"<TenantIntegration(tenant={self.tenant_id}, integration='{self.integration_id}', status='{self.status}')>"


# ─── Sync Log ────────────────────────────────────────────────────────────────


class SyncLog(Base):
    """Detailed log entry for a single sync run.

    Every sync operation (manual, scheduled, webhook-triggered) creates
    exactly one SyncLog record that tracks the full lifecycle from
    pending → running → success/failed.
    """
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_integration_id = Column(
        Integer, ForeignKey("tenant_integrations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    sync_type = Column(String(32), nullable=False, default="full")  # full, incremental, webhook
    trigger = Column(String(32), nullable=False, default="manual")  # manual, scheduled, webhook
    status = Column(String(16), nullable=False, default="pending")  # pending, running, success, failed, cancelled
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    records_fetched = Column(Integer, nullable=False, default=0)
    records_created = Column(Integer, nullable=False, default=0)
    records_updated = Column(Integer, nullable=False, default=0)
    records_deleted = Column(Integer, nullable=False, default=0)
    records_unchanged = Column(Integer, nullable=False, default=0)
    records_failed = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    error_details = Column(FlexibleJSON, nullable=True)
    metadata_json = Column(FlexibleJSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant_integration = relationship("TenantIntegration", back_populates="sync_logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_integration_id": self.tenant_integration_id,
            "sync_type": self.sync_type,
            "trigger": self.trigger,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "records_fetched": self.records_fetched or 0,
            "records_created": self.records_created or 0,
            "records_updated": self.records_updated or 0,
            "records_deleted": self.records_deleted or 0,
            "records_unchanged": self.records_unchanged or 0,
            "records_failed": self.records_failed or 0,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "metadata_json": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─── Sync Schedule ───────────────────────────────────────────────────────────


class SyncSchedule(Base):
    """Cron-based schedule for automatic sync runs.

    Each tenant_integration can have at most one schedule. The scheduler
    loop checks next_run_at to determine when to trigger the next sync.
    """
    __tablename__ = "sync_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_integration_id = Column(
        Integer, ForeignKey("tenant_integrations.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    is_enabled = Column(Boolean, nullable=False, default=False)
    cron_expression = Column(String(64), nullable=False, default="0 */6 * * *")
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    tenant_integration = relationship("TenantIntegration", back_populates="schedule")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_integration_id": self.tenant_integration_id,
            "is_enabled": self.is_enabled,
            "cron_expression": self.cron_expression,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
        }


# ─── Webhook Endpoint ───────────────────────────────────────────────────────


class WebhookEndpoint(Base):
    """Registered webhook receiver for real-time sync events.

    Each integration can register one or more webhook endpoints.
    The endpoint_path is unique and used for routing incoming webhooks.
    """
    __tablename__ = "webhook_endpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_integration_id = Column(
        Integer, ForeignKey("tenant_integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    endpoint_path = Column(String(255), nullable=False, unique=True)
    secret_token = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    events_filter = Column(FlexibleJSON, nullable=True)
    last_received_at = Column(DateTime, nullable=True)
    total_received = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant_integration = relationship("TenantIntegration", back_populates="webhook_endpoints")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_integration_id": self.tenant_integration_id,
            "endpoint_path": self.endpoint_path,
            "is_active": self.is_active,
            "events_filter": self.events_filter,
            "last_received_at": self.last_received_at.isoformat() if self.last_received_at else None,
            "total_received": self.total_received or 0,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Helper: Resolve integration config from Settings (persistence layer)
# ══════════════════════════════════════════════════════════════════════════════

def get_integration_config(tenant_id: int, connector_id: str) -> dict | None:
    """
    Load integration configuration for a given tenant and connector from the
    Settings table.  Keys follow the pattern used by connector_hub:
        integration_{connector_id}_{tenant_id}_{field}

    Returns a dict with all stored fields, or None if the integration is not
    configured / not enabled.
    """
    from app.gateway.persistence import persistence

    def _get(field: str, default: str = "") -> str:
        key = f"integration_{connector_id}_{tenant_id}_{field}"
        return persistence.get_setting(key, default, tenant_id=tenant_id) or default

    enabled = _get("enabled", "false").lower() == "true"
    if not enabled:
        return None

    # Collect all common fields
    config: dict = {}
    common_fields = [
        "host", "port", "username", "password",
        "from_email", "from_name", "use_starttls",
        "imap_host", "imap_port",
        "bot_token", "server_token",
        "api_key", "api_secret",
        "webhook_url", "verify_token",
    ]
    for field in common_fields:
        val = _get(field)
        if val:
            config[field] = val

    return config if config else None
