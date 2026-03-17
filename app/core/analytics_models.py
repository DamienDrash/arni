"""ARIIA v2.2 – Analytics & Omnichannel Orchestration Models.

Provides data models for:
- analytics_events: High-volume event tracking (opens, clicks, conversions)
- campaign_orchestration_steps: Multi-channel campaign sequences

@ARCH: Campaign Refactoring Phase 3, Task 3.1
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Float, DateTime, ForeignKey, Index
)
from app.core.db import Base


class AnalyticsEvent(Base):
    """Individual tracking event for campaign analytics.

    Stores every open, click, bounce, unsubscribe, and conversion event.
    Optimized for fast writes (via Redis queue) and aggregated reads.
    """
    __tablename__ = "analytics_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    recipient_id = Column(Integer, ForeignKey("campaign_recipients.id"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    idempotency_key = Column(String(128), nullable=True)

    # Event classification
    # sent | delivered | opened | clicked | bounced | unsubscribed | converted
    event_type = Column(String(30), nullable=False, index=True)
    # email | whatsapp | sms | telegram
    channel = Column(String(20), nullable=False)

    # Event-specific data
    url = Column(Text, nullable=True)               # Clicked URL (only for 'clicked' events)
    user_agent = Column(Text, nullable=True)         # Client user-agent string
    ip_address = Column(String(45), nullable=True)   # IPv4 or IPv6

    # Extensible metadata
    metadata_json = Column(Text, nullable=True)      # JSON: {"conversion_value": 49.99, ...}

    created_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_ae_campaign_event", "campaign_id", "event_type"),
        Index("ix_ae_tenant_created", "tenant_id", "created_at"),
        Index("ix_ae_recipient_event", "recipient_id", "event_type"),
        Index(
            "uq_ae_idempotency", "idempotency_key",
            unique=True, postgresql_where=Column("idempotency_key").isnot(None),
        ),
    )


class CampaignOrchestrationStep(Base):
    """Defines a single step in a multi-channel campaign sequence.

    Replaces the simple 'channel' field on campaigns with a full
    orchestration sequence. Example: Email first, then WhatsApp
    fallback after 24h if not opened.
    """
    __tablename__ = "campaign_orchestration_steps"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)          # 1, 2, 3, ...
    channel = Column(String(20), nullable=False)           # email | whatsapp | sms | telegram
    template_id = Column(Integer, ForeignKey("campaign_templates.id"), nullable=True)
    content_override_json = Column(Text, nullable=True)    # Channel-specific content override
    wait_hours = Column(Integer, nullable=False, default=0)  # Wait time before this step
    # if_not_opened | if_not_clicked | always
    condition_type = Column(String(30), nullable=True, default="always")

    __table_args__ = (
        Index("ix_cos_campaign_order", "campaign_id", "step_order"),
    )
