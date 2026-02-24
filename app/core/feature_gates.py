"""ARIIA – Feature Gate & Permission System (S4.2 / S6.1).

Enforces plan-based limits, feature availability, and role-based access per tenant.
Used by webhook endpoints, the swarm router, and the admin permission endpoint.

Usage:
    from app.core.feature_gates import FeatureGate, get_permissions
    gate = FeatureGate(tenant_id=7)
    gate.require_channel("telegram")       # raises HTTP 402 if not in plan
    gate.check_message_limit()             # raises HTTP 429 if monthly limit exceeded
    gate.increment_inbound_usage()         # call after successful processing

    perms = get_permissions(tenant_id=7, role="tenant_admin")
    # → full permission map for frontend consumption
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import HTTPException

logger = structlog.get_logger()

# ── Default plan (Starter) ──────────────────────────────────────────────────

_STARTER_DEFAULTS: dict[str, object] = {
    "name": "Starter",
    "slug": "starter",
    "price_monthly_cents": 0,
    "max_monthly_messages": 1000,
    "max_members": 500,
    "max_channels": 1,
    # Channels
    "whatsapp_enabled": True,
    "telegram_enabled": False,
    "sms_enabled": False,
    "email_channel_enabled": False,
    "voice_enabled": False,
    "instagram_enabled": False,
    "facebook_enabled": False,
    "google_business_enabled": False,
    # Features
    "memory_analyzer_enabled": False,
    "custom_prompts_enabled": False,
    "advanced_analytics_enabled": False,
    "branding_enabled": False,
    "audit_log_enabled": False,
    "automation_enabled": False,
    "api_access_enabled": False,
    "multi_source_members_enabled": False,
}

# ── Role → Page Access Matrix ───────────────────────────────────────────────

# Pages that require specific plan features (feature_key → page paths)
_FEATURE_GATED_PAGES: dict[str, list[str]] = {
    "memory_analyzer_enabled": ["/member-memory"],
    "custom_prompts_enabled": ["/settings/prompts"],
    "advanced_analytics_enabled": [],  # analytics page always visible, but advanced widgets gated
    "branding_enabled": ["/settings/branding"],
    "audit_log_enabled": ["/audit"],
    "automation_enabled": ["/settings/automation"],
    "multi_source_members_enabled": [],  # members page always visible, multi-source features gated
}

# Role → allowed pages (independent of plan)
_ROLE_PAGES: dict[str, list[str]] = {
    "system_admin": [
        "/dashboard",
        "/tenants",
        "/plans",
        "/system-prompt",
        "/users",
        "/audit",
        "/settings",
        "/settings/account",
        "/settings/general",
        "/settings/ai",
    ],
    "tenant_admin": [
        "/dashboard",
        "/live",
        "/escalations",
        "/analytics",
        "/members",
        "/member-memory",
        "/knowledge",
        "/magicline",
        "/users",
        "/audit",
        "/settings",
        "/settings/account",
        "/settings/integrations",
        "/settings/prompts",
        "/settings/billing",
        "/settings/branding",
        "/settings/automation",
    ],
    "tenant_user": [
        "/dashboard",
        "/live",
        "/escalations",
        "/analytics",
        "/settings",
        "/settings/account",
    ],
}

# Public pages (no auth required)
_PUBLIC_PAGES = [
    "/", "/login", "/register", "/features", "/pricing",
    "/impressum", "/datenschutz", "/agb",
]


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
            logger.warning("feature_gate.plan_load_failed", tenant_id=self._tenant_id, error=str(exc))
        return dict(_STARTER_DEFAULTS)

    @property
    def plan_data(self) -> dict[str, object]:
        """Expose plan data for permission building."""
        return dict(self._plan_data)

    # ── Channel Gates ─────────────────────────────────────────────────────────

    def require_channel(self, channel: str) -> None:
        """Raise HTTP 402 if the given channel is not enabled in the tenant's plan."""
        key_map = {
            "whatsapp": "whatsapp_enabled",
            "telegram": "telegram_enabled",
            "sms": "sms_enabled",
            "email": "email_channel_enabled",
            "voice": "voice_enabled",
            "instagram": "instagram_enabled",
            "facebook": "facebook_enabled",
            "google_business": "google_business_enabled",
        }
        plan_key = key_map.get(channel.lower())
        if plan_key and not self._plan_data.get(plan_key, False):
            raise HTTPException(
                status_code=402,
                detail=f"Channel '{channel}' is not available on your current plan. Please upgrade.",
            )

    def require_feature(self, feature: str) -> None:
        """Raise HTTP 402 if a named feature is not in the tenant's plan."""
        key = f"{feature}_enabled"
        if not self._plan_data.get(key, False):
            raise HTTPException(
                status_code=402,
                detail=f"Feature '{feature}' is not available on your current plan. Please upgrade.",
            )

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled without raising."""
        key = f"{feature}_enabled"
        return bool(self._plan_data.get(key, False))

    def is_channel_enabled(self, channel: str) -> bool:
        """Check if a channel is enabled without raising."""
        key_map = {
            "whatsapp": "whatsapp_enabled",
            "telegram": "telegram_enabled",
            "sms": "sms_enabled",
            "email": "email_channel_enabled",
            "voice": "voice_enabled",
            "instagram": "instagram_enabled",
            "facebook": "facebook_enabled",
            "google_business": "google_business_enabled",
        }
        plan_key = key_map.get(channel.lower())
        if not plan_key:
            return False
        return bool(self._plan_data.get(plan_key, False))

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

    def check_member_limit(self) -> None:
        """Raise HTTP 402 if the tenant has reached their member limit."""
        max_members = self._plan_data.get("max_members")
        if max_members is None:
            return  # unlimited
        try:
            from app.core.db import SessionLocal
            from app.core.models import StudioMember
            db = SessionLocal()
            try:
                count = db.query(StudioMember).filter(
                    StudioMember.tenant_id == self._tenant_id,
                ).count()
                if count >= int(max_members):
                    raise HTTPException(
                        status_code=402,
                        detail=f"Member limit of {max_members} reached. Please upgrade your plan.",
                    )
            finally:
                db.close()
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("feature_gate.member_limit_check_failed", error=str(exc))

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
            logger.warning("feature_gate.usage_load_failed", tenant_id=self._tenant_id, error=str(exc))
        return {"messages_inbound": 0, "messages_outbound": 0, "active_members": 0, "llm_tokens_used": 0}

    # ── Usage Tracking ────────────────────────────────────────────────────────

    def increment_inbound_usage(self) -> None:
        self._increment_usage_field("messages_inbound")

    def increment_outbound_usage(self) -> None:
        self._increment_usage_field("messages_outbound")

    def add_llm_tokens(self, tokens: int) -> None:
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
            logger.warning("feature_gate.usage_increment_failed", field=field, tenant_id=self._tenant_id, error=str(exc))


# ── Permission Builder ────────────────────────────────────────────────────────

def get_permissions(tenant_id: int, role: str) -> dict[str, Any]:
    """Build the complete permission map for a user.

    Returns a dict consumed by the frontend to control visibility and access.
    """
    gate = FeatureGate(tenant_id)
    plan = gate.plan_data

    # Build features map
    feature_keys = [
        "whatsapp", "telegram", "sms", "email_channel", "voice",
        "instagram", "facebook", "google_business",
        "memory_analyzer", "custom_prompts", "advanced_analytics",
        "branding", "audit_log", "automation", "api_access",
        "multi_source_members",
    ]
    features: dict[str, bool] = {}
    for key in feature_keys:
        features[key] = bool(plan.get(f"{key}_enabled", False))

    # Build limits
    limits: dict[str, int | None] = {
        "max_members": plan.get("max_members"),  # type: ignore[arg-type]
        "max_monthly_messages": plan.get("max_monthly_messages"),  # type: ignore[arg-type]
        "max_channels": int(plan.get("max_channels", 1)),  # type: ignore[arg-type]
    }

    # Build usage
    usage = gate._get_current_usage()
    try:
        from app.core.db import SessionLocal
        from app.core.models import StudioMember
        db = SessionLocal()
        try:
            members_count = db.query(StudioMember).filter(
                StudioMember.tenant_id == tenant_id,
            ).count()
        finally:
            db.close()
    except Exception:
        members_count = 0

    usage_data = {
        "messages_used": usage.get("messages_inbound", 0) + usage.get("messages_outbound", 0),
        "messages_inbound": usage.get("messages_inbound", 0),
        "messages_outbound": usage.get("messages_outbound", 0),
        "members_count": members_count,
        "llm_tokens_used": usage.get("llm_tokens_used", 0),
    }

    # Build page access map
    role_pages = _ROLE_PAGES.get(role, [])
    pages: dict[str, bool] = {}

    for page in role_pages:
        # Check if page requires a feature
        is_feature_gated = False
        for feature_key, gated_pages in _FEATURE_GATED_PAGES.items():
            if page in gated_pages:
                is_feature_gated = True
                pages[page] = bool(plan.get(feature_key, False))
                break
        if not is_feature_gated:
            pages[page] = True

    # Add public pages
    for page in _PUBLIC_PAGES:
        pages[page] = True

    # Subscription info
    sub_info: dict[str, Any] = {
        "has_subscription": False,
        "status": "free",
    }
    try:
        from app.core.db import SessionLocal
        from app.core.models import Subscription
        db = SessionLocal()
        try:
            sub = db.query(Subscription).filter(
                Subscription.tenant_id == tenant_id,
            ).first()
            if sub:
                sub_info = {
                    "has_subscription": True,
                    "status": sub.status,
                    "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
                    "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
                }
        finally:
            db.close()
    except Exception:
        pass

    return {
        "role": role,
        "plan": {
            "slug": plan.get("slug", "starter"),
            "name": plan.get("name", "Starter"),
            "price_monthly_cents": plan.get("price_monthly_cents", 0),
            "features": features,
            "limits": limits,
        },
        "subscription": sub_info,
        "usage": usage_data,
        "pages": pages,
    }


# ── Plan Seeding ──────────────────────────────────────────────────────────────

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
                "instagram_enabled": False,
                "facebook_enabled": False,
                "google_business_enabled": False,
                "memory_analyzer_enabled": False,
                "custom_prompts_enabled": False,
                "advanced_analytics_enabled": False,
                "branding_enabled": False,
                "audit_log_enabled": False,
                "automation_enabled": False,
                "api_access_enabled": False,
                "multi_source_members_enabled": False,
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
                "instagram_enabled": True,
                "facebook_enabled": True,
                "google_business_enabled": False,
                "memory_analyzer_enabled": True,
                "custom_prompts_enabled": True,
                "advanced_analytics_enabled": True,
                "branding_enabled": True,
                "audit_log_enabled": True,
                "automation_enabled": False,
                "api_access_enabled": True,
                "multi_source_members_enabled": True,
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
                "instagram_enabled": True,
                "facebook_enabled": True,
                "google_business_enabled": True,
                "memory_analyzer_enabled": True,
                "custom_prompts_enabled": True,
                "advanced_analytics_enabled": True,
                "branding_enabled": True,
                "audit_log_enabled": True,
                "automation_enabled": True,
                "api_access_enabled": True,
                "multi_source_members_enabled": True,
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
        logger.warning("feature_gate.plans_seed_failed", error=str(exc))
    finally:
        db.close()
