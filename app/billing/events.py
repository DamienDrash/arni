"""
ARIIA Billing V2 – Event Service

Provides the event-sourcing backbone for the billing system.
Every billing-relevant state change is recorded as an immutable event.

Usage:
    from app.billing.events import BillingEventService

    event_service = BillingEventService()
    await event_service.emit(
        db=db,
        tenant_id=42,
        event_type=BillingEventType.SUBSCRIPTION_CREATED,
        payload={"plan_slug": "pro", "interval": "month"},
        actor_type="user",
        actor_id="user_123",
    )
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.billing.models import BillingEvent, BillingEventType

logger = structlog.get_logger()


class BillingEventService:
    """
    Service for creating and querying billing events.

    All events are immutable once created. The service provides:
    - Event emission with optional idempotency keys
    - Querying events by tenant, type, or time range
    - Stripe event correlation
    """

    async def emit(
        self,
        db: Session,
        tenant_id: Optional[int],
        event_type: BillingEventType,
        payload: Optional[dict[str, Any]] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        stripe_event_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> BillingEvent:
        """
        Record a billing event.

        Args:
            db: Database session.
            tenant_id: Tenant this event belongs to (None for system events).
            event_type: The type of billing event.
            payload: Arbitrary JSON-serializable data for the event.
            actor_type: Who triggered this event ("user", "system", "stripe", "cron").
            actor_id: Identifier of the actor.
            stripe_event_id: Stripe event ID for correlation.
            idempotency_key: Unique key to prevent duplicate events.

        Returns:
            The created BillingEvent.

        Raises:
            ValueError: If an event with the same idempotency_key already exists.
        """
        # Check idempotency
        if idempotency_key:
            existing = (
                db.query(BillingEvent)
                .filter(BillingEvent.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                logger.info(
                    "billing.event.duplicate",
                    idempotency_key=idempotency_key,
                    event_type=event_type.value,
                )
                return existing

        event = BillingEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            payload_json=json.dumps(payload, default=str) if payload else None,
            actor_type=actor_type,
            actor_id=actor_id,
            stripe_event_id=stripe_event_id,
            idempotency_key=idempotency_key or f"{event_type.value}_{tenant_id}_{uuid.uuid4().hex[:12]}",
            created_at=datetime.now(timezone.utc),
        )

        db.add(event)
        db.flush()  # Flush to get the ID without committing

        logger.info(
            "billing.event.emitted",
            event_id=event.id,
            tenant_id=tenant_id,
            event_type=event_type.value,
            actor_type=actor_type,
        )

        return event

    async def emit_and_commit(
        self,
        db: Session,
        tenant_id: Optional[int],
        event_type: BillingEventType,
        payload: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> BillingEvent:
        """Emit an event and immediately commit the transaction."""
        event = await self.emit(db, tenant_id, event_type, payload, **kwargs)
        db.commit()
        return event

    def get_events_for_tenant(
        self,
        db: Session,
        tenant_id: int,
        event_types: Optional[list[BillingEventType]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BillingEvent]:
        """Query events for a specific tenant, optionally filtered by type."""
        query = (
            db.query(BillingEvent)
            .filter(BillingEvent.tenant_id == tenant_id)
            .order_by(BillingEvent.created_at.desc())
        )
        if event_types:
            query = query.filter(BillingEvent.event_type.in_(event_types))
        return query.offset(offset).limit(limit).all()

    def get_events_by_stripe_id(
        self,
        db: Session,
        stripe_event_id: str,
    ) -> list[BillingEvent]:
        """Find all events correlated with a Stripe event."""
        return (
            db.query(BillingEvent)
            .filter(BillingEvent.stripe_event_id == stripe_event_id)
            .order_by(BillingEvent.created_at.desc())
            .all()
        )

    def get_recent_events(
        self,
        db: Session,
        since: Optional[datetime] = None,
        event_types: Optional[list[BillingEventType]] = None,
        limit: int = 100,
    ) -> list[BillingEvent]:
        """Get recent events across all tenants."""
        query = db.query(BillingEvent).order_by(BillingEvent.created_at.desc())
        if since:
            query = query.filter(BillingEvent.created_at >= since)
        if event_types:
            query = query.filter(BillingEvent.event_type.in_(event_types))
        return query.limit(limit).all()

    def count_events(
        self,
        db: Session,
        tenant_id: Optional[int] = None,
        event_type: Optional[BillingEventType] = None,
    ) -> int:
        """Count events with optional filters."""
        query = db.query(BillingEvent)
        if tenant_id is not None:
            query = query.filter(BillingEvent.tenant_id == tenant_id)
        if event_type is not None:
            query = query.filter(BillingEvent.event_type == event_type)
        return query.count()


# Singleton instance
billing_events = BillingEventService()
