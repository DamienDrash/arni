"""
ARIIA Billing V2 – Metering Service

Handles granular usage tracking per tenant, per feature, per billing period.

Key capabilities:
- Record usage increments with soft/hard limit enforcement
- Query current usage for any feature
- Aggregate usage across periods
- Detect overage conditions
- Redis caching for hot-path queries

Usage:
    from app.billing.metering_service import metering_service

    # Record usage
    result = await metering_service.record_usage(db, tenant_id=42, feature_key="messages_outbound", quantity=1)
    if result.blocked:
        raise HTTPException(429, "Message limit reached")

    # Check usage
    usage = await metering_service.get_usage(db, tenant_id=42, feature_key="messages_outbound")
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.billing.events import billing_events
from app.billing.gating_repository import gating_repository
from app.billing.metering_repository import metering_repository
from app.billing.models import (
    BillingEventType,
)

logger = structlog.get_logger()


@dataclass
class UsageResult:
    """Result of a usage recording operation."""
    recorded: bool
    current_count: int
    soft_limit: Optional[int]
    hard_limit: Optional[int]
    in_overage: bool
    blocked: bool
    overage_count: int
    message: Optional[str] = None


@dataclass
class UsageSummary:
    """Summary of usage for a feature."""
    feature_key: str
    feature_name: str
    usage_count: int
    soft_limit: Optional[int]
    hard_limit: Optional[int]
    percentage_used: Optional[float]  # 0.0 - 1.0+
    in_overage: bool
    remaining: Optional[int]  # None if unlimited


class MeteringService:
    """
    Service for tracking and querying usage metrics.

    Supports both increment-based (messages, tokens) and
    gauge-based (active members, channels) usage tracking.
    """

    # ── Record Usage ────────────────────────────────────────────────────

    async def record_usage(
        self,
        db: Session,
        tenant_id: int,
        feature_key: str,
        quantity: int = 1,
        check_limits: bool = True,
    ) -> UsageResult:
        """
        Record usage for a tenant/feature combination.

        Args:
            db: Database session.
            tenant_id: The tenant recording usage.
            feature_key: The feature key (e.g., "messages_outbound").
            quantity: Amount to increment (default: 1).
            check_limits: Whether to enforce limits (default: True).

        Returns:
            UsageResult with current state and limit information.
        """
        now = datetime.now(timezone.utc)
        period_year = now.year
        period_month = now.month

        # Get limits for this tenant/feature
        soft_limit, hard_limit = self._get_limits(db, tenant_id, feature_key)

        # Get or create usage record
        usage = metering_repository.get_usage_record(
            db,
            tenant_id=tenant_id,
            feature_key=feature_key,
            period_year=period_year,
            period_month=period_month,
        )

        if not usage:
            usage = metering_repository.create_usage_record(
                db,
                tenant_id=tenant_id,
                feature_key=feature_key,
                period_year=period_year,
                period_month=period_month,
                soft_limit=soft_limit,
                hard_limit=hard_limit,
            )

        # Check hard limit before recording
        if check_limits and hard_limit is not None:
            if usage.usage_count + quantity > hard_limit:
                logger.warning(
                    "billing.metering.hard_limit_reached",
                    tenant_id=tenant_id,
                    feature_key=feature_key,
                    current=usage.usage_count,
                    hard_limit=hard_limit,
                )
                return UsageResult(
                    recorded=False,
                    current_count=usage.usage_count,
                    soft_limit=soft_limit,
                    hard_limit=hard_limit,
                    in_overage=True,
                    blocked=True,
                    overage_count=usage.overage_count,
                    message=f"Hard limit ({hard_limit}) für '{feature_key}' erreicht.",
                )

        # Record usage
        new_count = usage.usage_count + quantity
        usage.usage_count = new_count
        usage.last_recorded_at = now

        # Track overage
        in_overage = False
        if soft_limit is not None and new_count > soft_limit:
            overage = new_count - soft_limit
            usage.overage_count = overage
            in_overage = True

            # Emit overage event (only when first crossing the threshold)
            if usage.usage_count - quantity <= soft_limit:
                await billing_events.emit(
                    db=db,
                    tenant_id=tenant_id,
                    event_type=BillingEventType.USAGE_OVERAGE_STARTED,
                    payload={
                        "feature_key": feature_key,
                        "soft_limit": soft_limit,
                        "current_count": new_count,
                    },
                    actor_type="system",
                )

        db.commit()

        return UsageResult(
            recorded=True,
            current_count=new_count,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            in_overage=in_overage,
            blocked=False,
            overage_count=usage.overage_count,
        )

    # ── Set Gauge ───────────────────────────────────────────────────────

    async def set_gauge(
        self,
        db: Session,
        tenant_id: int,
        feature_key: str,
        value: int,
    ) -> UsageResult:
        """
        Set an absolute gauge value (e.g., active_members count).

        Unlike record_usage which increments, this sets the value directly.
        """
        now = datetime.now(timezone.utc)
        period_year = now.year
        period_month = now.month

        soft_limit, hard_limit = self._get_limits(db, tenant_id, feature_key)

        usage = metering_repository.get_usage_record(
            db,
            tenant_id=tenant_id,
            feature_key=feature_key,
            period_year=period_year,
            period_month=period_month,
        )

        if not usage:
            usage = metering_repository.create_usage_record(
                db,
                tenant_id=tenant_id,
                feature_key=feature_key,
                period_year=period_year,
                period_month=period_month,
                soft_limit=soft_limit,
                hard_limit=hard_limit,
            )

        usage.usage_count = value
        usage.last_recorded_at = now

        in_overage = False
        if soft_limit is not None and value > soft_limit:
            usage.overage_count = value - soft_limit
            in_overage = True
        else:
            usage.overage_count = 0

        db.commit()

        return UsageResult(
            recorded=True,
            current_count=value,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            in_overage=in_overage,
            blocked=False,
            overage_count=usage.overage_count,
        )

    # ── Query Usage ─────────────────────────────────────────────────────

    async def get_usage(
        self,
        db: Session,
        tenant_id: int,
        feature_key: str,
        period_year: Optional[int] = None,
        period_month: Optional[int] = None,
    ) -> UsageSummary:
        """Get usage summary for a specific feature."""
        now = datetime.now(timezone.utc)
        year = period_year or now.year
        month = period_month or now.month

        usage = metering_repository.get_usage_record(
            db,
            tenant_id=tenant_id,
            feature_key=feature_key,
            period_year=year,
            period_month=month,
        )

        soft_limit, hard_limit = self._get_limits(db, tenant_id, feature_key)
        count = usage.usage_count if usage else 0

        # Get feature name
        feature = gating_repository.get_feature_by_key(db, feature_key)
        feature_name = feature.name if feature else feature_key

        percentage = None
        remaining = None
        if soft_limit is not None and soft_limit > 0:
            percentage = count / soft_limit
            remaining = max(0, soft_limit - count)

        return UsageSummary(
            feature_key=feature_key,
            feature_name=feature_name,
            usage_count=count,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            percentage_used=percentage,
            in_overage=count > soft_limit if soft_limit is not None else False,
            remaining=remaining,
        )

    async def get_all_usage(
        self,
        db: Session,
        tenant_id: int,
        period_year: Optional[int] = None,
        period_month: Optional[int] = None,
    ) -> list[UsageSummary]:
        """Get usage summaries for all tracked features."""
        now = datetime.now(timezone.utc)
        year = period_year or now.year
        month = period_month or now.month

        records = metering_repository.list_usage_records(
            db,
            tenant_id=tenant_id,
            period_year=year,
            period_month=month,
        )

        features_by_key = {
            feature.key: feature
            for feature in metering_repository.list_features_by_keys(
                db,
                [record.feature_key for record in records],
            )
        }

        summaries = []
        for rec in records:
            feature = features_by_key.get(rec.feature_key)
            soft_limit = rec.soft_limit_snapshot
            hard_limit = rec.hard_limit_snapshot

            percentage = None
            remaining = None
            if soft_limit is not None and soft_limit > 0:
                percentage = rec.usage_count / soft_limit
                remaining = max(0, soft_limit - rec.usage_count)

            summaries.append(UsageSummary(
                feature_key=rec.feature_key,
                feature_name=feature.name if feature else rec.feature_key,
                usage_count=rec.usage_count,
                soft_limit=soft_limit,
                hard_limit=hard_limit,
                percentage_used=percentage,
                in_overage=rec.overage_count > 0,
                remaining=remaining,
            ))

        return summaries

    # ── Reset Usage ─────────────────────────────────────────────────────

    async def reset_period(
        self,
        db: Session,
        tenant_id: int,
        period_year: int,
        period_month: int,
    ) -> int:
        """Reset all usage records for a tenant/period. Returns count of reset records."""
        records = metering_repository.list_usage_records(
            db,
            tenant_id=tenant_id,
            period_year=period_year,
            period_month=period_month,
        )

        count = 0
        for rec in records:
            rec.usage_count = 0
            rec.overage_count = 0
            count += 1

        db.commit()
        return count

    # ── Helpers ─────────────────────────────────────────────────────────

    def _get_limits(
        self,
        db: Session,
        tenant_id: int,
        feature_key: str,
    ) -> tuple[Optional[int], Optional[int]]:
        """
        Get the soft and hard limits for a tenant/feature.

        Resolves through: Subscription → Plan → FeatureSet → FeatureEntitlement
        Returns (soft_limit, hard_limit). None = unlimited.
        """
        sub = gating_repository.get_subscription_by_tenant(db, tenant_id)
        if not sub:
            return (None, None)

        plan = gating_repository.get_plan_by_id(db, sub.plan_id)
        if not plan or not plan.feature_set_id:
            return (None, None)

        feature = gating_repository.get_feature_by_key(db, feature_key)
        if not feature:
            return (None, None)

        entitlement = gating_repository.get_feature_entitlement(
            db,
            feature_set_id=plan.feature_set_id,
            feature_id=feature.id,
        )

        if not entitlement:
            return (None, None)

        return (entitlement.value_limit, entitlement.hard_limit)


# Singleton
metering_service = MeteringService()
