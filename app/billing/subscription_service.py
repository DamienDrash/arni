"""
ARIIA Billing V2 – Subscription Service

Manages the complete subscription lifecycle:
- Create / activate / cancel / reactivate subscriptions
- Plan upgrades and downgrades (immediate or scheduled)
- Trial management
- Stripe synchronization
- Event emission for every state change

Usage:
    from app.billing.subscription_service import SubscriptionServiceV2

    service = SubscriptionServiceV2()
    sub = await service.create_subscription(db, tenant_id=42, plan_slug="starter")
    await service.upgrade(db, tenant_id=42, new_plan_slug="professional")
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.billing.events import billing_events
from app.billing.models import (
    BillingEventType,
    BillingInterval,
    PlanV2,
    SubscriptionStatus,
    SubscriptionV2,
    TenantAddonV2,
)

logger = structlog.get_logger()


class SubscriptionServiceV2:
    """
    Service for managing tenant subscriptions.

    All operations:
    1. Validate the request
    2. Update the local database
    3. Emit a BillingEvent for the audit trail
    4. Return the updated subscription

    Stripe communication is handled separately by the StripeAdapterV2,
    which is called by the API layer or webhook processor.
    """

    # ── Create ──────────────────────────────────────────────────────────

    async def create_subscription(
        self,
        db: Session,
        tenant_id: int,
        plan_slug: str,
        billing_interval: BillingInterval = BillingInterval.MONTH,
        stripe_subscription_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        trial_days: Optional[int] = None,
        actor_type: str = "system",
        actor_id: Optional[str] = None,
    ) -> SubscriptionV2:
        """
        Create a new subscription for a tenant.

        If the plan has trial_days > 0 and no trial_days override is given,
        the subscription starts in TRIALING status.
        """
        # Validate plan exists
        plan = db.query(PlanV2).filter(PlanV2.slug == plan_slug, PlanV2.is_active.is_(True)).first()
        if not plan:
            raise ValueError(f"Plan '{plan_slug}' nicht gefunden oder nicht aktiv.")

        # Check for existing subscription
        existing = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()
        if existing:
            raise ValueError(
                f"Tenant {tenant_id} hat bereits ein Abonnement (ID: {existing.id}, "
                f"Status: {existing.status}). Bitte zuerst kündigen oder upgraden."
            )

        # Determine trial
        effective_trial_days = trial_days if trial_days is not None else plan.trial_days
        now = datetime.now(timezone.utc)

        if effective_trial_days > 0:
            status = SubscriptionStatus.TRIALING
            trial_start = now
            trial_end = now + timedelta(days=effective_trial_days)
            period_end = trial_end
        else:
            status = SubscriptionStatus.ACTIVE
            trial_start = None
            trial_end = None
            if billing_interval == BillingInterval.YEAR:
                period_end = now + timedelta(days=365)
            else:
                period_end = now + timedelta(days=30)

        subscription = SubscriptionV2(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status=status,
            billing_interval=billing_interval,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            current_period_start=now,
            current_period_end=period_end,
            trial_start=trial_start,
            trial_end=trial_end,
        )

        db.add(subscription)
        db.flush()

        # Emit event
        event_type = (
            BillingEventType.SUBSCRIPTION_TRIAL_STARTED
            if effective_trial_days > 0
            else BillingEventType.SUBSCRIPTION_CREATED
        )
        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=event_type,
            payload={
                "subscription_id": subscription.id,
                "plan_slug": plan_slug,
                "plan_id": plan.id,
                "billing_interval": billing_interval.value,
                "trial_days": effective_trial_days,
                "stripe_subscription_id": stripe_subscription_id,
            },
            actor_type=actor_type,
            actor_id=actor_id,
        )

        db.commit()
        logger.info(
            "billing.subscription.created",
            tenant_id=tenant_id,
            plan_slug=plan_slug,
            status=status.value,
            trial_days=effective_trial_days,
        )
        return subscription

    # ── Get ─────────────────────────────────────────────────────────────

    def get_subscription(self, db: Session, tenant_id: int) -> Optional[SubscriptionV2]:
        """Get the current subscription for a tenant."""
        return db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()

    def get_subscription_with_plan(self, db: Session, tenant_id: int) -> Optional[dict[str, Any]]:
        """Get subscription with plan details."""
        sub = self.get_subscription(db, tenant_id)
        if not sub:
            return None

        plan = db.query(PlanV2).filter(PlanV2.id == sub.plan_id).first()
        return {
            "subscription": sub,
            "plan": plan,
        }

    # ── Activate ────────────────────────────────────────────────────────

    async def activate(
        self,
        db: Session,
        tenant_id: int,
        stripe_subscription_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        actor_type: str = "system",
        actor_id: Optional[str] = None,
    ) -> SubscriptionV2:
        """Activate a subscription (e.g., after trial ends or payment succeeds)."""
        sub = self._get_or_raise(db, tenant_id)

        sub.status = SubscriptionStatus.ACTIVE
        if stripe_subscription_id:
            sub.stripe_subscription_id = stripe_subscription_id
        if stripe_customer_id:
            sub.stripe_customer_id = stripe_customer_id

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.SUBSCRIPTION_ACTIVATED,
            payload={
                "subscription_id": sub.id,
                "previous_status": "trialing",
                "stripe_subscription_id": stripe_subscription_id,
            },
            actor_type=actor_type,
            actor_id=actor_id,
        )

        db.commit()
        logger.info("billing.subscription.activated", tenant_id=tenant_id)
        return sub

    # ── Upgrade ─────────────────────────────────────────────────────────

    async def upgrade(
        self,
        db: Session,
        tenant_id: int,
        new_plan_slug: str,
        billing_interval: Optional[BillingInterval] = None,
        immediate: bool = True,
        actor_type: str = "user",
        actor_id: Optional[str] = None,
    ) -> SubscriptionV2:
        """
        Upgrade a subscription to a higher plan.

        Upgrades are always immediate (prorated in Stripe).
        """
        sub = self._get_or_raise(db, tenant_id)
        old_plan = db.query(PlanV2).filter(PlanV2.id == sub.plan_id).first()

        new_plan = db.query(PlanV2).filter(
            PlanV2.slug == new_plan_slug,
            PlanV2.is_active.is_(True),
        ).first()
        if not new_plan:
            raise ValueError(f"Plan '{new_plan_slug}' nicht gefunden oder nicht aktiv.")

        if new_plan.id == sub.plan_id:
            raise ValueError("Bereits auf diesem Plan.")

        old_plan_id = sub.plan_id
        old_plan_slug = old_plan.slug if old_plan else "unknown"

        sub.plan_id = new_plan.id
        if billing_interval:
            sub.billing_interval = billing_interval
        sub.pending_plan_id = None
        sub.scheduled_change_at = None

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.SUBSCRIPTION_UPGRADED,
            payload={
                "subscription_id": sub.id,
                "old_plan_id": old_plan_id,
                "old_plan_slug": old_plan_slug,
                "new_plan_id": new_plan.id,
                "new_plan_slug": new_plan_slug,
                "billing_interval": (billing_interval or sub.billing_interval).value if billing_interval else sub.billing_interval.value if isinstance(sub.billing_interval, BillingInterval) else str(sub.billing_interval),
                "immediate": immediate,
            },
            actor_type=actor_type,
            actor_id=actor_id,
        )

        db.commit()
        logger.info(
            "billing.subscription.upgraded",
            tenant_id=tenant_id,
            from_plan=old_plan_slug,
            to_plan=new_plan_slug,
        )
        return sub

    # ── Downgrade ───────────────────────────────────────────────────────

    async def downgrade(
        self,
        db: Session,
        tenant_id: int,
        new_plan_slug: str,
        billing_interval: Optional[BillingInterval] = None,
        immediate: bool = False,
        actor_type: str = "user",
        actor_id: Optional[str] = None,
    ) -> SubscriptionV2:
        """
        Downgrade a subscription to a lower plan.

        By default, downgrades are scheduled for the end of the current period.
        Set immediate=True to apply immediately (not recommended).
        """
        sub = self._get_or_raise(db, tenant_id)
        old_plan = db.query(PlanV2).filter(PlanV2.id == sub.plan_id).first()

        new_plan = db.query(PlanV2).filter(
            PlanV2.slug == new_plan_slug,
            PlanV2.is_active.is_(True),
        ).first()
        if not new_plan:
            raise ValueError(f"Plan '{new_plan_slug}' nicht gefunden oder nicht aktiv.")

        if new_plan.id == sub.plan_id:
            raise ValueError("Bereits auf diesem Plan.")

        old_plan_slug = old_plan.slug if old_plan else "unknown"

        if immediate:
            sub.plan_id = new_plan.id
            if billing_interval:
                sub.billing_interval = billing_interval
            sub.pending_plan_id = None
            sub.scheduled_change_at = None
        else:
            sub.pending_plan_id = new_plan.id
            sub.scheduled_change_at = sub.current_period_end

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.SUBSCRIPTION_DOWNGRADED,
            payload={
                "subscription_id": sub.id,
                "old_plan_slug": old_plan_slug,
                "new_plan_slug": new_plan_slug,
                "immediate": immediate,
                "scheduled_at": sub.scheduled_change_at.isoformat() if sub.scheduled_change_at else None,
            },
            actor_type=actor_type,
            actor_id=actor_id,
        )

        db.commit()
        logger.info(
            "billing.subscription.downgraded",
            tenant_id=tenant_id,
            from_plan=old_plan_slug,
            to_plan=new_plan_slug,
            immediate=immediate,
        )
        return sub

    # ── Cancel ──────────────────────────────────────────────────────────

    async def cancel(
        self,
        db: Session,
        tenant_id: int,
        reason: Optional[str] = None,
        immediate: bool = False,
        actor_type: str = "user",
        actor_id: Optional[str] = None,
    ) -> SubscriptionV2:
        """
        Cancel a subscription.

        By default, cancellation takes effect at the end of the current period.
        Set immediate=True for immediate cancellation.
        """
        sub = self._get_or_raise(db, tenant_id)
        now = datetime.now(timezone.utc)

        if immediate:
            sub.status = SubscriptionStatus.CANCELED
            sub.canceled_at = now
        else:
            sub.cancel_at_period_end = True
            sub.canceled_at = now

        sub.cancellation_reason = reason

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.SUBSCRIPTION_CANCELED,
            payload={
                "subscription_id": sub.id,
                "reason": reason,
                "immediate": immediate,
                "cancel_at_period_end": sub.cancel_at_period_end,
                "effective_date": (
                    now.isoformat() if immediate
                    else sub.current_period_end.isoformat() if sub.current_period_end
                    else now.isoformat()
                ),
            },
            actor_type=actor_type,
            actor_id=actor_id,
        )

        db.commit()
        logger.info(
            "billing.subscription.canceled",
            tenant_id=tenant_id,
            immediate=immediate,
        )
        return sub

    # ── Reactivate ──────────────────────────────────────────────────────

    async def reactivate(
        self,
        db: Session,
        tenant_id: int,
        actor_type: str = "user",
        actor_id: Optional[str] = None,
    ) -> SubscriptionV2:
        """Reactivate a canceled subscription (before period end)."""
        sub = self._get_or_raise(db, tenant_id)

        if sub.status == SubscriptionStatus.CANCELED and not sub.cancel_at_period_end:
            raise ValueError("Abonnement ist bereits endgültig gekündigt und kann nicht reaktiviert werden.")

        sub.cancel_at_period_end = False
        sub.canceled_at = None
        sub.cancellation_reason = None
        sub.status = SubscriptionStatus.ACTIVE

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.SUBSCRIPTION_REACTIVATED,
            payload={"subscription_id": sub.id},
            actor_type=actor_type,
            actor_id=actor_id,
        )

        db.commit()
        logger.info("billing.subscription.reactivated", tenant_id=tenant_id)
        return sub

    # ── Update from Stripe ──────────────────────────────────────────────

    async def sync_from_stripe(
        self,
        db: Session,
        tenant_id: int,
        stripe_data: dict[str, Any],
    ) -> SubscriptionV2:
        """
        Update local subscription state from Stripe webhook data.

        This is the primary method called by the webhook processor.
        """
        sub = self.get_subscription(db, tenant_id)
        if not sub:
            logger.warning("billing.subscription.sync_no_sub", tenant_id=tenant_id)
            raise ValueError(f"Kein Abonnement für Tenant {tenant_id} gefunden.")

        # Map Stripe status to our enum
        stripe_status = stripe_data.get("status", "")
        status_map = {
            "trialing": SubscriptionStatus.TRIALING,
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "unpaid": SubscriptionStatus.UNPAID,
            "incomplete": SubscriptionStatus.INCOMPLETE,
            "incomplete_expired": SubscriptionStatus.INCOMPLETE_EXPIRED,
            "paused": SubscriptionStatus.PAUSED,
        }

        new_status = status_map.get(stripe_status)
        if new_status:
            sub.status = new_status

        # Update period
        if stripe_data.get("current_period_start"):
            sub.current_period_start = datetime.fromtimestamp(
                stripe_data["current_period_start"], tz=timezone.utc
            )
        if stripe_data.get("current_period_end"):
            sub.current_period_end = datetime.fromtimestamp(
                stripe_data["current_period_end"], tz=timezone.utc
            )

        # Update Stripe IDs
        if stripe_data.get("id"):
            sub.stripe_subscription_id = stripe_data["id"]
        if stripe_data.get("customer"):
            sub.stripe_customer_id = stripe_data["customer"]
        if stripe_data.get("latest_invoice"):
            sub.stripe_latest_invoice_id = stripe_data["latest_invoice"]

        # Cancellation
        sub.cancel_at_period_end = stripe_data.get("cancel_at_period_end", False)
        if stripe_data.get("canceled_at"):
            sub.canceled_at = datetime.fromtimestamp(
                stripe_data["canceled_at"], tz=timezone.utc
            )

        # Trial
        if stripe_data.get("trial_start"):
            sub.trial_start = datetime.fromtimestamp(
                stripe_data["trial_start"], tz=timezone.utc
            )
        if stripe_data.get("trial_end"):
            sub.trial_end = datetime.fromtimestamp(
                stripe_data["trial_end"], tz=timezone.utc
            )

        db.commit()
        logger.info(
            "billing.subscription.synced_from_stripe",
            tenant_id=tenant_id,
            status=sub.status.value if isinstance(sub.status, SubscriptionStatus) else str(sub.status),
        )
        return sub

    # ── Apply Scheduled Changes ─────────────────────────────────────────

    async def apply_pending_changes(self, db: Session) -> list[int]:
        """
        Apply all pending plan changes that are due.

        Called by a cron job at the start of each billing period.
        Returns list of tenant_ids that were updated.
        """
        now = datetime.now(timezone.utc)
        pending = (
            db.query(SubscriptionV2)
            .filter(
                SubscriptionV2.pending_plan_id.isnot(None),
                SubscriptionV2.scheduled_change_at <= now,
            )
            .all()
        )

        updated_tenants = []
        for sub in pending:
            old_plan_id = sub.plan_id
            sub.plan_id = sub.pending_plan_id
            sub.pending_plan_id = None
            sub.scheduled_change_at = None

            await billing_events.emit(
                db=db,
                tenant_id=sub.tenant_id,
                event_type=BillingEventType.SUBSCRIPTION_DOWNGRADED,
                payload={
                    "subscription_id": sub.id,
                    "old_plan_id": old_plan_id,
                    "new_plan_id": sub.plan_id,
                    "applied": "scheduled_change",
                },
                actor_type="cron",
                actor_id="apply_pending_changes",
            )
            updated_tenants.append(sub.tenant_id)

        if updated_tenants:
            db.commit()
            logger.info(
                "billing.subscription.pending_changes_applied",
                count=len(updated_tenants),
            )

        return updated_tenants

    # ── Helpers ─────────────────────────────────────────────────────────

    def _get_or_raise(self, db: Session, tenant_id: int) -> SubscriptionV2:
        """Get subscription or raise ValueError."""
        sub = self.get_subscription(db, tenant_id)
        if not sub:
            raise ValueError(f"Kein Abonnement für Tenant {tenant_id} gefunden.")
        return sub


# Singleton
subscription_service = SubscriptionServiceV2()
