"""ARIIA – Feature Gate System (S4.2).

Enforces plan-based limits and feature availability per tenant.
Used by webhook endpoints and the swarm router before processing messages.

Usage:
    from app.core.feature_gates import FeatureGate
    gate = FeatureGate(tenant_id=7)
    gate.require_channel("telegram")       # raises HTTP 402 if not in plan
    gate.check_message_limit()             # raises HTTP 429 if monthly limit exceeded
    gate.increment_inbound_usage()         # call after successful processing
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import HTTPException

logger = structlog.get_logger()

# Default plan used when no subscription exists for a tenant.
# Maps to feature flags — mirrors the "Starter" plan seeded at startup.
_STARTER_DEFAULTS: dict[str, object] = {
    "max_monthly_messages": 1000,
    "max_members": 500,
    "max_channels": 1,
    "whatsapp_enabled": True,
    "telegram_enabled": False,
    "sms_enabled": False,
    "email_channel_enabled": False,
    "voice_enabled": False,
    "memory_analyzer_enabled": False,
    "custom_prompts_enabled": False,
}


class FeatureGate:
    """Checks and enforces plan limits for a given tenant.

    One instance per request — do not cache as usage counters change frequently.
    """

    def __init__(self, tenant_id: int) -> None:
        self._tenant_id = tenant_id
        self._plan_data: dict[str, object] = self._load_plan()

    # ── Plan Loading ──────────────────────────────────────────────────────────

    def _load_plan(self) -> dict[str, object]:
        """Load the tenant's plan data from DB. Falls back to Starter defaults."""
        try:
            from app.core.db import SessionLocal
            from app.core.models import Subscription, Plan
            db = SessionLocal()
            try:
                sub = db.query(Subscription).filter(
                    Subscription.tenant_id == self._tenant_id,
                    Subscription.status.in_(["active", "trialing"]),
                ).first()
                if sub:
                    plan = db.query(Plan).filter(Plan.id == sub.plan_id, Plan.is_active.is_(True)).first()
                    if plan:
                        return {col.name: getattr(plan, col.name) for col in Plan.__table__.columns}
            finally:
                db.close()
        except Exception as exc:
            logger.wariiang("feature_gate.plan_load_failed", tenant_id=self._tenant_id, error=str(exc))
        return dict(_STARTER_DEFAULTS)

    # ── Channel Gates ─────────────────────────────────────────────────────────

    def require_channel(self, channel: str) -> None:
        """Raise HTTP 402 if the given channel is not enabled in the tenant's plan.

        Args:
            channel: One of 'whatsapp', 'telegram', 'sms', 'email', 'voice'.
        """
        key_map = {
            "whatsapp": "whatsapp_enabled",
            "telegram": "telegram_enabled",
            "sms": "sms_enabled",
            "email": "email_channel_enabled",
            "voice": "voice_enabled",
        }
        plan_key = key_map.get(channel.lower())
        if plan_key and not self._plan_data.get(plan_key, False):
            raise HTTPException(
                status_code=402,
                detail=f"Channel '{channel}' is not available on your current plan. Please upgrade.",
            )

    def require_feature(self, feature: str) -> None:
        """Raise HTTP 402 if a named feature is not in the tenant's plan.

        Args:
            feature: e.g. 'memory_analyzer', 'custom_prompts'
        """
        key = f"{feature}_enabled"
        if not self._plan_data.get(key, False):
            raise HTTPException(
                status_code=402,
                detail=f"Feature '{feature}' is not available on your current plan. Please upgrade.",
            )

    # ── Usage Gates ───────────────────────────────────────────────────────────

    def check_message_limit(self) -> None:
        """Raise HTTP 429 if the tenant has reached their monthly message quota."""
        max_msgs = self._plan_data.get("max_monthly_messages")
        if max_msgs is None:
            return  # unlimited
        current = self._get_current_usage()
        total = current.get("messages_inbound", 0) + current.get("messages_outbound", 0)
        if total >= int(max_msgs):
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Monthly message limit of {max_msgs} reached. "
                    "Please upgrade your plan to continue."
                ),
            )

    def _get_current_usage(self) -> dict[str, int]:
        """Return current month's usage record for the tenant."""
        now = datetime.now(timezone.utc)
        try:
            from app.core.db import SessionLocal
            from app.core.models import UsageRecord
            db = SessionLocal()
            try:
                rec = db.query(UsageRecord).filter(
                    UsageRecord.tenant_id == self._tenant_id,
                    UsageRecord.period_year == now.year,
                    UsageRecord.period_month == now.month,
                ).first()
                if rec:
                    return {
                        "messages_inbound": rec.messages_inbound,
                        "messages_outbound": rec.messages_outbound,
                        "active_members": rec.active_members,
                        "llm_tokens_used": rec.llm_tokens_used,
                    }
            finally:
                db.close()
        except Exception as exc:
            logger.wariiang("feature_gate.usage_load_failed", tenant_id=self._tenant_id, error=str(exc))
        return {"messages_inbound": 0, "messages_outbound": 0, "active_members": 0, "llm_tokens_used": 0}

    # ── Usage Tracking ────────────────────────────────────────────────────────

    def increment_inbound_usage(self) -> None:
        """Increment the inbound message counter for the current month. Non-fatal."""
        self._increment_usage_field("messages_inbound")

    def increment_outbound_usage(self) -> None:
        """Increment the outbound message counter for the current month. Non-fatal."""
        self._increment_usage_field("messages_outbound")

    def add_llm_tokens(self, tokens: int) -> None:
        """Add LLM token usage for the current month. Non-fatal."""
        self._increment_usage_field("llm_tokens_used", amount=tokens)

    def _increment_usage_field(self, field: str, amount: int = 1) -> None:
        now = datetime.now(timezone.utc)
        try:
            from sqlalchemy import text
            from app.core.db import SessionLocal, engine
            db = SessionLocal()
            try:
                dialect = engine.dialect.name
                if dialect == "postgresql":
                    db.execute(
                        text(
                            f"INSERT INTO usage_records (tenant_id, period_year, period_month, {field}) "
                            f"VALUES (:tid, :yr, :mo, :amt) "
                            f"ON CONFLICT (tenant_id, period_year, period_month) "
                            f"DO UPDATE SET {field} = usage_records.{field} + :amt"
                        ),
                        {"tid": self._tenant_id, "yr": now.year, "mo": now.month, "amt": amount},
                    )
                else:
                    # SQLite fallback — read-modify-write (acceptable for low concurrency)
                    from app.core.models import UsageRecord
                    rec = db.query(UsageRecord).filter(
                        UsageRecord.tenant_id == self._tenant_id,
                        UsageRecord.period_year == now.year,
                        UsageRecord.period_month == now.month,
                    ).first()
                    if rec:
                        setattr(rec, field, getattr(rec, field, 0) + amount)
                    else:
                        rec = UsageRecord(
                            tenant_id=self._tenant_id,
                            period_year=now.year,
                            period_month=now.month,
                            **{field: amount},
                        )
                        db.add(rec)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.wariiang("feature_gate.usage_increment_failed", field=field, tenant_id=self._tenant_id, error=str(exc))


def seed_plans() -> None:
    """Seed the three standard plans if they don't exist yet. Called at startup."""
    from app.core.db import SessionLocal
    from app.core.models import Plan
    db = SessionLocal()
    try:
        plans_data = [
            {
                "name": "Starter",
                "slug": "starter",
                "price_monthly_cents": 0,
                "max_members": 500,
                "max_monthly_messages": 1000,
                "max_channels": 1,
                "whatsapp_enabled": True,
                "telegram_enabled": False,
                "sms_enabled": False,
                "email_channel_enabled": False,
                "voice_enabled": False,
                "memory_analyzer_enabled": False,
                "custom_prompts_enabled": False,
            },
            {
                "name": "Pro",
                "slug": "pro",
                "price_monthly_cents": 9900,  # 99.00 EUR
                "max_members": None,
                "max_monthly_messages": None,
                "max_channels": 4,
                "whatsapp_enabled": True,
                "telegram_enabled": True,
                "sms_enabled": True,
                "email_channel_enabled": True,
                "voice_enabled": False,
                "memory_analyzer_enabled": True,
                "custom_prompts_enabled": True,
            },
            {
                "name": "Enterprise",
                "slug": "enterprise",
                "price_monthly_cents": 0,   # Invoiced separately
                "max_members": None,
                "max_monthly_messages": None,
                "max_channels": 10,
                "whatsapp_enabled": True,
                "telegram_enabled": True,
                "sms_enabled": True,
                "email_channel_enabled": True,
                "voice_enabled": True,
                "memory_analyzer_enabled": True,
                "custom_prompts_enabled": True,
            },
        ]
        for data in plans_data:
            existing = db.query(Plan).filter(Plan.slug == data["slug"]).first()
            if not existing:
                db.add(Plan(**data))
        db.commit()
        logger.info("feature_gate.plans_seeded")

        # Assign Starter plan to any tenant without a subscription (idempotent)
        from app.core.models import Subscription, Tenant
        starter_plan = db.query(Plan).filter(Plan.slug == "starter", Plan.is_active.is_(True)).first()
        if starter_plan:
            all_tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
            seeded_count = 0
            for t in all_tenants:
                existing_sub = db.query(Subscription).filter(Subscription.tenant_id == t.id).first()
                if not existing_sub:
                    db.add(Subscription(tenant_id=t.id, plan_id=starter_plan.id, status="active"))
                    seeded_count += 1
            if seeded_count:
                db.commit()
                logger.info("feature_gate.subscriptions_seeded", count=seeded_count)
    except Exception as exc:
        db.rollback()
        logger.wariiang("feature_gate.plans_seed_failed", error=str(exc))
    finally:
        db.close()
