"""ARIIA v1.4 – Gateway Message Schemas.

@BACKEND: Pydantic Models (Sprint 1, Task 1.7)
Defines all message types flowing through the Redis Bus.
PII-MASKING: See docs/specs/DSGVO_BASELINE.md for masking rules.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Platform(str, Enum):
    """Supported messaging platforms."""

    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SMS = "sms"
    EMAIL = "email"
    PHONE = "phone"
    VOICE = "voice"
    DASHBOARD = "dashboard"


class MessageRole(str, Enum):
    """Message roles per MEMORY.md schema."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class InboundMessage(BaseModel):
    """Message arriving at the Gateway from any platform.

    All external messages are normalized into this schema
    before being published to the Redis Bus.
    """

    message_id: str = Field(..., description="Unique message identifier")
    platform: Platform = Field(..., description="Source platform")
    user_id: str = Field(..., description="Platform-specific user ID (not PII)")
    content: str = Field(..., description="Message text content")
    content_type: str = Field(default="text", description="text|image|voice|location")
    media_url: str | None = Field(default=None, description="URL to media attachment")
    tenant_id: int | None = Field(default=None, description="Resolved tenant context for message scope")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Message timestamp (UTC)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Platform-specific metadata")


class OutboundMessage(BaseModel):
    """Message sent from the Gateway to a platform.

    Produced by Swarm Agents, routed back through Redis Bus.
    """

    message_id: str = Field(..., description="Unique message identifier")
    platform: Platform = Field(..., description="Target platform")
    user_id: str = Field(..., description="Recipient user ID")
    content: str = Field(..., description="Response text content")
    content_type: str = Field(default="text", description="text|image|voice|audio")
    media_url: str | None = Field(default=None, description="URL to media attachment")
    tenant_id: int | None = Field(default=None, description="Resolved tenant context for message scope")
    reply_to: str | None = Field(default=None, description="Original message ID being replied to")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class SystemEvent(BaseModel):
    """Internal system event published to Redis Bus.

    Used for admin notifications, health events, alerts.
    """

    event_type: str = Field(..., description="Event type identifier")
    source: str = Field(..., description="Originating service/agent")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event data")
    severity: str = Field(default="info", description="info|warning|error|critical")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class WebhookPayload(BaseModel):
    """Raw WhatsApp webhook payload wrapper.

    Validates the outer structure before normalization to InboundMessage.
    """

    object: str = Field(default="whatsapp_business_account")
    entry: list[dict[str, Any]] = Field(default_factory=list)
