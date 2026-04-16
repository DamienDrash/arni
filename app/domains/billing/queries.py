from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.domains.billing.models import ImageCreditBalance, Plan, Subscription, UsageRecord


class BillingQueries:
    """Cross-domain read access for billing-owned entities."""

    def get_subscription_by_tenant(self, db: Session, tenant_id: int) -> Subscription | None:
        return db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()

    def get_subscription_by_tenant_statuses(
        self,
        db: Session,
        tenant_id: int,
        *,
        statuses: Iterable[str],
    ) -> Subscription | None:
        normalized_statuses = tuple(statuses)
        if not normalized_statuses:
            return None
        return (
            db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id,
                Subscription.status.in_(normalized_statuses),
            )
            .first()
        )

    def get_plan_by_id(self, db: Session, plan_id: int | None) -> Plan | None:
        if plan_id is None:
            return None
        return db.query(Plan).filter(Plan.id == plan_id).first()

    def get_tenant_plan_slug(self, db: Session, tenant_id: int) -> str | None:
        subscription = self.get_subscription_by_tenant(db, tenant_id)
        if not subscription:
            return None
        plan = self.get_plan_by_id(db, subscription.plan_id)
        return plan.slug if plan else None

    def list_usage_records_since(self, db: Session, *, tenant_id: int, since: datetime) -> list[UsageRecord]:
        return (
            db.query(UsageRecord)
            .filter(UsageRecord.tenant_id == tenant_id, UsageRecord.created_at >= since)
            .all()
        )

    def get_usage_record_for_period(
        self,
        db: Session,
        *,
        tenant_id: int,
        year: int,
        month: int,
    ) -> UsageRecord | None:
        return (
            db.query(UsageRecord)
            .filter(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.period_year == year,
                UsageRecord.period_month == month,
            )
            .first()
        )

    def get_plan_limits_for_tenant(
        self,
        db: Session,
        tenant_id: int,
        *,
        subscription_statuses: Iterable[str] = ("active",),
    ) -> dict[str, int]:
        subscription = self.get_subscription_by_tenant_statuses(
            db,
            tenant_id,
            statuses=subscription_statuses,
        )
        if not subscription:
            return {}
        plan = self.get_plan_by_id(db, subscription.plan_id)
        if not plan:
            return {}

        limits: dict[str, int] = {}
        if hasattr(plan, "ai_image_generations_per_month"):
            limits["ai_image_generations_per_month"] = plan.ai_image_generations_per_month
        if hasattr(plan, "media_storage_mb"):
            limits["media_storage_mb"] = plan.media_storage_mb
        return limits

    def get_monthly_image_credit_grant_for_tenant(
        self,
        db: Session,
        tenant_id: int,
        *,
        subscription_statuses: Iterable[str] = ("active", "trialing"),
    ) -> tuple[int, str | None]:
        subscription = self.get_subscription_by_tenant_statuses(
            db,
            tenant_id,
            statuses=subscription_statuses,
        )
        if not subscription:
            return 0, None

        plan = self.get_plan_by_id(db, subscription.plan_id)
        if not plan:
            return 0, None

        return (getattr(plan, "monthly_image_credits", 0) or 0), getattr(plan, "slug", None)

    def get_image_credit_balance(self, db: Session, tenant_id: int) -> ImageCreditBalance | None:
        return db.query(ImageCreditBalance).filter(ImageCreditBalance.tenant_id == tenant_id).first()


billing_queries = BillingQueries()
