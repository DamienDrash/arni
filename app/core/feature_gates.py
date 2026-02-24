"""ARIIA – Feature Gate & Permission System (S4.2 / S6.1).

Enforces plan-based limits, feature availability, LLM model access,
connector quotas, and role-based access per tenant.  Tightly coupled
with Stripe for overage billing.

Plans:
    Starter     79 €/mo  – 1 channel, 500 conversations, Basic AI, 1 user
    Professional 199 €/mo – 3 channels, 2 000 conversations, Full AI Swarm, 5 users
    Business    399 €/mo  – All channels, 10 000 conversations, Priority, 15 users
    Enterprise  Custom    – Unlimited, SLA, Dedicated Support, On-Premise

Usage:
    from app.core.feature_gates import FeatureGate, get_permissions
    gate = FeatureGate(tenant_id=7)
    gate.require_channel("telegram")
    gate.require_llm_model("gpt-4.1-mini")
    gate.require_connector("shopify")
    gate.check_message_limit()
    gate.check_llm_token_limit()
    gate.increment_inbound_usage()

    perms = get_permissions(tenant_id=7, role="tenant_admin")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import HTTPException

logger = structlog.get_logger()

# ── Default plan (Starter) ──────────────────────────────────────────────────

_STARTER_DEFAULTS: dict[str, object] = {
    "name": "Starter",
    "slug": "starter",
    "price_monthly_cents": 7900,
    "max_monthly_messages": 500,
    "max_members": 500,
    "max_channels": 1,
    "max_users": 1,
    "max_connectors": 0,
    "max_monthly_llm_tokens": 100_000,
    "ai_tier": "basic",
    "allowed_llm_models": '["gpt-4.1-nano"]',
    "custom_llm_keys_enabled": False,
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
    # Connectors
    "connector_manual_enabled": True,
    "connector_api_enabled": True,
    "connector_csv_enabled": True,
    "connector_magicline_enabled": False,
    "connector_shopify_enabled": False,
    "connector_woocommerce_enabled": False,
    "connector_hubspot_enabled": False,
    # Premium
    "churn_prediction_enabled": False,
    "vision_ai_enabled": False,
    "white_label_enabled": False,
    "priority_support": False,
    "dedicated_support": False,
    "sla_enabled": False,
    "on_premise_option": False,
}

# ── Role → Page Access Matrix ───────────────────────────────────────────────

_FEATURE_GATED_PAGES: dict[str, list[str]] = {
    "memory_analyzer_enabled": ["/member-memory"],
    "custom_prompts_enabled": ["/settings/prompts"],
    "advanced_analytics_enabled": [],
    "branding_enabled": ["/settings/branding"],
    "audit_log_enabled": ["/audit"],
    "automation_enabled": ["/settings/automation"],
    "multi_source_members_enabled": [],
}

_ROLE_PAGES: dict[str, list[str]] = {
    "system_admin": [
        "/dashboard", "/tenants", "/plans", "/system-prompt", "/users",
        "/audit", "/settings", "/settings/account", "/settings/general",
        "/settings/ai",
    ],
    "tenant_admin": [
        "/dashboard", "/live", "/escalations", "/analytics", "/members",
        "/member-memory", "/knowledge", "/magicline", "/users", "/audit",
        "/settings", "/settings/account", "/settings/integrations",
        "/settings/prompts", "/settings/billing", "/settings/branding",
        "/settings/automation",
    ],
    "tenant_user": [
        "/dashboard", "/live", "/escalations", "/analytics",
        "/settings", "/settings/account",
    ],
}

_PUBLIC_PAGES = [
    "/", "/login", "/register", "/features", "/pricing",
    "/impressum", "/datenschutz", "/agb",
]

# ── Plan → minimum plan slug mapping (for upgrade prompts) ──────────────────

PLAN_HIERARCHY = ["starter", "professional", "business", "enterprise"]

_FEATURE_MIN_PLAN: dict[str, str] = {
    # Pro features
    "telegram": "professional",
    "sms": "professional",
    "email_channel": "professional",
    "instagram": "professional",
    "facebook": "professional",
    "memory_analyzer": "professional",
    "custom_prompts": "professional",
    "advanced_analytics": "professional",
    "branding": "professional",
    "audit_log": "professional",
    "api_access": "professional",
    "multi_source_members": "professional",
    "connector_magicline": "professional",
    "connector_shopify": "professional",
    "connector_woocommerce": "professional",
    "connector_hubspot": "professional",
    # Business features
    "voice": "business",
    "google_business": "business",
    "automation": "business",
    "churn_prediction": "business",
    "vision_ai": "business",
    "priority_support": "business",
    # Enterprise features
    "white_label": "enterprise",
    "dedicated_support": "enterprise",
    "sla": "enterprise",
    "on_premise_option": "enterprise",
    "custom_llm_keys": "enterprise",
}


class FeatureGate:
    """Checks and enforces plan limits for a given tenant.

    One instance per request — do not cache as usage counters change frequently.
    """

    def __init__(self, tenant_id: int) -> None:
        self._tenant_id = tenant_id
        self._plan_data: dict[str, object] = self._load_plan()
        self._active_addons: list[dict[str, Any]] = self._load_addons()

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

    def _load_addons(self) -> list[dict[str, Any]]:
        """Load active add-ons for the tenant."""
        try:
            from app.core.db import SessionLocal
            from app.core.models import TenantAddon, PlanAddon
            db = SessionLocal()
            try:
                rows = (
                    db.query(TenantAddon, PlanAddon)
                    .join(PlanAddon, TenantAddon.addon_id == PlanAddon.id)
                    .filter(
                        TenantAddon.tenant_id == self._tenant_id,
                        TenantAddon.status == "active",
                    )
                    .all()
                )
                return [
                    {
                        "slug": addon.slug,
                        "feature_key": addon.feature_key,
                        "quantity": ta.quantity,
                        "category": addon.category,
                    }
                    for ta, addon in rows
                ]
            finally:
                db.close()
        except Exception as exc:
            logger.warning("feature_gate.addons_load_failed", tenant_id=self._tenant_id, error=str(exc))
        return []

    @property
    def plan_data(self) -> dict[str, object]:
        return dict(self._plan_data)

    @property
    def active_addons(self) -> list[dict[str, Any]]:
        return list(self._active_addons)

    # ── Effective limits (plan + addons) ─────────────────────────────────────

    def _effective_max_channels(self) -> int | None:
        base = int(self._plan_data.get("max_channels", 1))  # type: ignore[arg-type]
        extra = sum(a["quantity"] for a in self._active_addons if a["slug"] == "extra_channel")
        total = base + extra
        return None if total >= 99 else total

    def _effective_max_connectors(self) -> int | None:
        base = int(self._plan_data.get("max_connectors", 0))  # type: ignore[arg-type]
        extra = sum(a["quantity"] for a in self._active_addons if a["slug"] == "extra_connector")
        total = base + extra
        return None if total >= 99 else total

    def _effective_max_users(self) -> int | None:
        base = self._plan_data.get("max_users")
        if base is None:
            return None
        extra = sum(a["quantity"] for a in self._active_addons if a["slug"] == "extra_user")
        return int(base) + extra  # type: ignore[arg-type]

    def _effective_max_messages(self) -> int | None:
        base = self._plan_data.get("max_monthly_messages")
        if base is None:
            return None
        extra = sum(a["quantity"] * 500 for a in self._active_addons if a["slug"] == "extra_conversations")
        return int(base) + extra  # type: ignore[arg-type]

    def _effective_max_llm_tokens(self) -> int | None:
        base = self._plan_data.get("max_monthly_llm_tokens")
        if base is None:
            return None
        return int(base)  # type: ignore[arg-type]

    def _is_feature_from_addon(self, feature_key: str) -> bool:
        """Check if a feature is enabled via an active add-on."""
        return any(a.get("feature_key") == feature_key for a in self._active_addons)

    # ── Channel Gates ─────────────────────────────────────────────────────────

    def require_channel(self, channel: str) -> None:
        """Raise HTTP 402 if the given channel is not enabled in the tenant's plan or addons."""
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
            return
        enabled = bool(self._plan_data.get(plan_key, False))
        # Check if enabled via addon (e.g. extra_channel or voice_pipeline)
        if not enabled:
            addon_feature = f"{channel.lower()}_enabled"
            enabled = self._is_feature_from_addon(addon_feature)
        if not enabled:
            min_plan = _FEATURE_MIN_PLAN.get(channel.lower(), "professional")
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "channel_not_available",
                    "channel": channel,
                    "required_plan": min_plan,
                    "message": f"Kanal '{channel}' ist in deinem aktuellen Plan nicht verfügbar. Upgrade auf {min_plan.title()} erforderlich.",
                },
            )

    def require_feature(self, feature: str) -> None:
        """Raise HTTP 402 if a named feature is not in the tenant's plan or addons."""
        key = f"{feature}_enabled"
        enabled = bool(self._plan_data.get(key, False)) or self._is_feature_from_addon(key)
        if not enabled:
            min_plan = _FEATURE_MIN_PLAN.get(feature, "professional")
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "feature_not_available",
                    "feature": feature,
                    "required_plan": min_plan,
                    "message": f"Feature '{feature}' ist in deinem aktuellen Plan nicht verfügbar. Upgrade auf {min_plan.title()} erforderlich.",
                },
            )

    def is_feature_enabled(self, feature: str) -> bool:
        key = f"{feature}_enabled"
        return bool(self._plan_data.get(key, False)) or self._is_feature_from_addon(key)

    def is_channel_enabled(self, channel: str) -> bool:
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
        return bool(self._plan_data.get(plan_key, False)) or self._is_feature_from_addon(plan_key)

    # ── Connector Gates ──────────────────────────────────────────────────────

    def require_connector(self, connector: str) -> None:
        """Raise HTTP 402 if a connector is not available in the tenant's plan."""
        # Manual, API, CSV always allowed
        if connector.lower() in ("manual", "api", "csv"):
            return
        key = f"connector_{connector.lower()}_enabled"
        enabled = bool(self._plan_data.get(key, False)) or self._is_feature_from_addon(key)
        if not enabled:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "connector_not_available",
                    "connector": connector,
                    "required_plan": "professional",
                    "message": f"Connector '{connector}' ist in deinem aktuellen Plan nicht verfügbar. Upgrade auf Professional erforderlich.",
                },
            )
        # Also check connector quota
        max_conn = self._effective_max_connectors()
        if max_conn is not None and max_conn <= 0:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "connector_limit_reached",
                    "connector": connector,
                    "message": "Connector-Limit erreicht. Buche das Add-on 'Zusätzlicher Connector' oder upgrade deinen Plan.",
                },
            )

    def is_connector_enabled(self, connector: str) -> bool:
        if connector.lower() in ("manual", "api", "csv"):
            return True
        key = f"connector_{connector.lower()}_enabled"
        return bool(self._plan_data.get(key, False)) or self._is_feature_from_addon(key)

    # ── LLM Model Gates ──────────────────────────────────────────────────────

    def require_llm_model(self, model: str) -> None:
        """Raise HTTP 402 if the requested LLM model is not available."""
        allowed_raw = self._plan_data.get("allowed_llm_models")
        if allowed_raw is None:
            return  # NULL = all models allowed (Enterprise)
        try:
            allowed = json.loads(str(allowed_raw)) if isinstance(allowed_raw, str) else allowed_raw
        except (json.JSONDecodeError, TypeError):
            allowed = ["gpt-4.1-nano"]
        if model not in allowed:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "llm_model_not_available",
                    "model": model,
                    "allowed_models": allowed,
                    "message": f"LLM-Modell '{model}' ist in deinem aktuellen Plan nicht verfügbar.",
                },
            )

    def get_allowed_llm_models(self) -> list[str]:
        """Return list of allowed LLM models for this tenant."""
        allowed_raw = self._plan_data.get("allowed_llm_models")
        if allowed_raw is None:
            return ["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4.1", "gemini-2.5-flash"]
        try:
            return json.loads(str(allowed_raw)) if isinstance(allowed_raw, str) else list(allowed_raw)
        except (json.JSONDecodeError, TypeError):
            return ["gpt-4.1-nano"]

    def get_default_llm_model(self) -> str:
        """Return the best available model for this tenant's plan."""
        models = self.get_allowed_llm_models()
        # Prefer the most capable model available
        preference = ["gpt-4.1", "gemini-2.5-flash", "gpt-4.1-mini", "gpt-4.1-nano"]
        for m in preference:
            if m in models:
                return m
        return models[0] if models else "gpt-4.1-nano"

    # ── Usage Gates ───────────────────────────────────────────────────────────

    def check_message_limit(self) -> None:
        """Raise HTTP 429 if the tenant has reached their monthly message quota."""
        max_msgs = self._effective_max_messages()
        if max_msgs is None:
            return
        current = self._get_current_usage()
        total = current.get("messages_inbound", 0) + current.get("messages_outbound", 0)
        if total >= max_msgs:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "message_limit_reached",
                    "limit": max_msgs,
                    "used": total,
                    "message": f"Monatliches Nachrichtenlimit von {max_msgs:,} erreicht. Upgrade deinen Plan oder buche das Add-on 'Zusätzliche Konversationen'.",
                },
            )

    def check_member_limit(self) -> None:
        """Raise HTTP 402 if the tenant has reached their member limit."""
        max_members = self._plan_data.get("max_members")
        if max_members is None:
            return
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
                        detail={
                            "error": "member_limit_reached",
                            "limit": int(max_members),
                            "used": count,
                            "message": f"Mitgliederlimit von {max_members} erreicht. Upgrade deinen Plan.",
                        },
                    )
            finally:
                db.close()
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("feature_gate.member_limit_check_failed", error=str(exc))

    def check_llm_token_limit(self) -> None:
        """Raise HTTP 429 if the tenant has reached their monthly LLM token quota."""
        max_tokens = self._effective_max_llm_tokens()
        if max_tokens is None:
            return
        current = self._get_current_usage()
        used = current.get("llm_tokens_used", 0)
        if used >= max_tokens:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "llm_token_limit_reached",
                    "limit": max_tokens,
                    "used": used,
                    "message": f"Monatliches LLM-Token-Limit von {max_tokens:,} erreicht. Upgrade deinen Plan.",
                },
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
                        "conversations_count": rec.conversations_count,
                        "active_members": rec.active_members,
                        "llm_tokens_used": rec.llm_tokens_used,
                        "llm_requests_count": rec.llm_requests_count,
                        "active_channels_count": rec.active_channels_count,
                        "active_connectors_count": rec.active_connectors_count,
                        "active_users_count": rec.active_users_count,
                        "overage_conversations": rec.overage_conversations,
                        "overage_tokens": rec.overage_tokens,
                        "overage_billed_cents": rec.overage_billed_cents,
                    }
            finally:
                db.close()
        except Exception as exc:
            logger.warning("feature_gate.usage_load_failed", tenant_id=self._tenant_id, error=str(exc))
        return {
            "messages_inbound": 0, "messages_outbound": 0, "conversations_count": 0,
            "active_members": 0, "llm_tokens_used": 0, "llm_requests_count": 0,
            "active_channels_count": 0, "active_connectors_count": 0,
            "active_users_count": 0, "overage_conversations": 0,
            "overage_tokens": 0, "overage_billed_cents": 0,
        }

    # ── Usage Tracking ────────────────────────────────────────────────────────

    def increment_inbound_usage(self) -> None:
        self._increment_usage_field("messages_inbound")

    def increment_outbound_usage(self) -> None:
        self._increment_usage_field("messages_outbound")

    def add_llm_tokens(self, tokens: int) -> None:
        self._increment_usage_field("llm_tokens_used", amount=tokens)
        self._increment_usage_field("llm_requests_count")

    def increment_conversation(self) -> None:
        self._increment_usage_field("conversations_count")

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
        "churn_prediction", "vision_ai", "white_label",
        "priority_support", "dedicated_support", "sla", "on_premise_option",
        "custom_llm_keys",
    ]
    features: dict[str, bool] = {}
    for key in feature_keys:
        features[key] = gate.is_feature_enabled(key)

    # Build connector access map
    connector_keys = ["manual", "api", "csv", "magicline", "shopify", "woocommerce", "hubspot"]
    connectors: dict[str, bool] = {}
    for key in connector_keys:
        connectors[key] = gate.is_connector_enabled(key)

    # Build LLM info
    llm_info = {
        "allowed_models": gate.get_allowed_llm_models(),
        "default_model": gate.get_default_llm_model(),
        "ai_tier": str(plan.get("ai_tier", "basic")),
        "custom_keys_enabled": bool(plan.get("custom_llm_keys_enabled", False)),
        "max_monthly_tokens": plan.get("max_monthly_llm_tokens"),
    }

    # Build limits (effective = plan + addons)
    limits: dict[str, int | None] = {
        "max_members": plan.get("max_members"),  # type: ignore[arg-type]
        "max_monthly_messages": gate._effective_max_messages(),
        "max_channels": gate._effective_max_channels(),
        "max_users": gate._effective_max_users(),
        "max_connectors": gate._effective_max_connectors(),
        "max_monthly_llm_tokens": gate._effective_max_llm_tokens(),
    }

    # Build overage pricing
    overage: dict[str, int | None] = {
        "per_conversation_cents": plan.get("overage_per_conversation_cents"),  # type: ignore[arg-type]
        "per_user_cents": plan.get("overage_per_user_cents"),  # type: ignore[arg-type]
        "per_connector_cents": plan.get("overage_per_connector_cents"),  # type: ignore[arg-type]
        "per_channel_cents": plan.get("overage_per_channel_cents"),  # type: ignore[arg-type]
    }

    # Build usage
    usage_raw = gate._get_current_usage()
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
        "messages_used": usage_raw.get("messages_inbound", 0) + usage_raw.get("messages_outbound", 0),
        "messages_inbound": usage_raw.get("messages_inbound", 0),
        "messages_outbound": usage_raw.get("messages_outbound", 0),
        "conversations_count": usage_raw.get("conversations_count", 0),
        "members_count": members_count,
        "llm_tokens_used": usage_raw.get("llm_tokens_used", 0),
        "llm_requests_count": usage_raw.get("llm_requests_count", 0),
        "active_channels_count": usage_raw.get("active_channels_count", 0),
        "active_connectors_count": usage_raw.get("active_connectors_count", 0),
        "active_users_count": usage_raw.get("active_users_count", 0),
        "overage_conversations": usage_raw.get("overage_conversations", 0),
        "overage_tokens": usage_raw.get("overage_tokens", 0),
        "overage_billed_cents": usage_raw.get("overage_billed_cents", 0),
    }

    # Build page access map
    role_pages = _ROLE_PAGES.get(role, [])
    pages: dict[str, bool] = {}
    for page in role_pages:
        is_feature_gated = False
        for feature_key, gated_pages in _FEATURE_GATED_PAGES.items():
            if page in gated_pages:
                is_feature_gated = True
                pages[page] = bool(plan.get(feature_key, False))
                break
        if not is_feature_gated:
            pages[page] = True
    for page in _PUBLIC_PAGES:
        pages[page] = True

    # Build active addons list
    addons_list = [
        {"slug": a["slug"], "quantity": a["quantity"], "category": a["category"]}
        for a in gate.active_addons
    ]

    # Subscription info
    sub_info: dict[str, Any] = {"has_subscription": False, "status": "free", "billing_interval": "monthly"}
    try:
        from app.core.db import SessionLocal
        from app.core.models import Subscription
        db = SessionLocal()
        try:
            sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
            if sub:
                sub_info = {
                    "has_subscription": True,
                    "status": sub.status,
                    "billing_interval": "yearly" if sub.stripe_subscription_id and "yearly" in str(sub.stripe_subscription_id) else "monthly",
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
            "price_monthly_cents": plan.get("price_monthly_cents", 7900),
            "price_yearly_cents": plan.get("price_yearly_cents"),
            "is_custom_pricing": plan.get("is_custom_pricing", False),
            "features": features,
            "connectors": connectors,
            "llm": llm_info,
            "limits": limits,
            "overage": overage,
        },
        "subscription": sub_info,
        "usage": usage_data,
        "addons": addons_list,
        "pages": pages,
    }


# ── Plan Seeding ──────────────────────────────────────────────────────────────

def seed_plans() -> None:
    """Seed the four standard plans and add-ons if they don't exist yet."""
    from app.core.db import SessionLocal
    from app.core.models import Plan, PlanAddon
    db = SessionLocal()
    try:
        plans_data = [
            # ── Starter (79 €/mo) ────────────────────────────────────────────
            {
                "name": "Starter",
                "slug": "starter",
                "price_monthly_cents": 7900,
                "price_yearly_cents": 75840,  # 79 * 12 * 0.8
                "is_custom_pricing": False,
                "max_members": 500,
                "max_monthly_messages": 500,
                "max_channels": 1,
                "max_users": 1,
                "max_connectors": 0,
                "overage_per_conversation_cents": 5,   # 0.05 €
                "overage_per_user_cents": 1500,        # 15 €
                "overage_per_connector_cents": None,
                "overage_per_channel_cents": 2900,     # 29 €
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
                # AI & LLM
                "ai_tier": "basic",
                "allowed_llm_models": '["gpt-4.1-nano"]',
                "max_monthly_llm_tokens": 100_000,
                "custom_llm_keys_enabled": False,
                # Connectors
                "connector_manual_enabled": True,
                "connector_api_enabled": True,
                "connector_csv_enabled": True,
                "connector_magicline_enabled": False,
                "connector_shopify_enabled": False,
                "connector_woocommerce_enabled": False,
                "connector_hubspot_enabled": False,
                # Premium
                "churn_prediction_enabled": False,
                "vision_ai_enabled": False,
                "white_label_enabled": False,
                "priority_support": False,
                "dedicated_support": False,
                "sla_enabled": False,
                "on_premise_option": False,
                "sort_order": 1,
            },
            # ── Professional (199 €/mo) ──────────────────────────────────────
            {
                "name": "Professional",
                "slug": "professional",
                "price_monthly_cents": 19900,
                "price_yearly_cents": 191040,  # 199 * 12 * 0.8
                "is_custom_pricing": False,
                "max_members": None,  # unlimited
                "max_monthly_messages": 2000,
                "max_channels": 3,
                "max_users": 5,
                "max_connectors": 1,  # 1 frei wählbar
                "overage_per_conversation_cents": 5,
                "overage_per_user_cents": 1500,
                "overage_per_connector_cents": 4900,
                "overage_per_channel_cents": 2900,
                # Channels (3 wählbar aus allen)
                "whatsapp_enabled": True,
                "telegram_enabled": True,
                "sms_enabled": True,
                "email_channel_enabled": True,
                "voice_enabled": False,
                "instagram_enabled": True,
                "facebook_enabled": True,
                "google_business_enabled": False,
                # Features
                "memory_analyzer_enabled": True,
                "custom_prompts_enabled": True,
                "advanced_analytics_enabled": True,
                "branding_enabled": True,
                "audit_log_enabled": True,
                "automation_enabled": False,
                "api_access_enabled": True,
                "multi_source_members_enabled": True,
                # AI & LLM
                "ai_tier": "standard",
                "allowed_llm_models": '["gpt-4.1-nano", "gpt-4.1-mini"]',
                "max_monthly_llm_tokens": 500_000,
                "custom_llm_keys_enabled": False,
                # Connectors (1 frei wählbar)
                "connector_manual_enabled": True,
                "connector_api_enabled": True,
                "connector_csv_enabled": True,
                "connector_magicline_enabled": True,
                "connector_shopify_enabled": True,
                "connector_woocommerce_enabled": True,
                "connector_hubspot_enabled": True,
                # Premium
                "churn_prediction_enabled": False,
                "vision_ai_enabled": False,
                "white_label_enabled": False,
                "priority_support": False,
                "dedicated_support": False,
                "sla_enabled": False,
                "on_premise_option": False,
                "sort_order": 2,
            },
            # ── Business (399 €/mo) ──────────────────────────────────────────
            {
                "name": "Business",
                "slug": "business",
                "price_monthly_cents": 39900,
                "price_yearly_cents": 383040,  # 399 * 12 * 0.8
                "is_custom_pricing": False,
                "max_members": None,
                "max_monthly_messages": 10000,
                "max_channels": 99,  # effectively unlimited
                "max_users": 15,
                "max_connectors": 99,  # effectively unlimited
                "overage_per_conversation_cents": 5,
                "overage_per_user_cents": 1500,
                "overage_per_connector_cents": None,
                "overage_per_channel_cents": None,
                # Channels – all
                "whatsapp_enabled": True,
                "telegram_enabled": True,
                "sms_enabled": True,
                "email_channel_enabled": True,
                "voice_enabled": True,
                "instagram_enabled": True,
                "facebook_enabled": True,
                "google_business_enabled": True,
                # Features – all except enterprise-only
                "memory_analyzer_enabled": True,
                "custom_prompts_enabled": True,
                "advanced_analytics_enabled": True,
                "branding_enabled": True,
                "audit_log_enabled": True,
                "automation_enabled": True,
                "api_access_enabled": True,
                "multi_source_members_enabled": True,
                # AI & LLM
                "ai_tier": "premium",
                "allowed_llm_models": '["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4.1", "gemini-2.5-flash"]',
                "max_monthly_llm_tokens": 2_000_000,
                "custom_llm_keys_enabled": False,
                # Connectors – all
                "connector_manual_enabled": True,
                "connector_api_enabled": True,
                "connector_csv_enabled": True,
                "connector_magicline_enabled": True,
                "connector_shopify_enabled": True,
                "connector_woocommerce_enabled": True,
                "connector_hubspot_enabled": True,
                # Premium
                "churn_prediction_enabled": True,
                "vision_ai_enabled": True,
                "white_label_enabled": False,
                "priority_support": True,
                "dedicated_support": False,
                "sla_enabled": False,
                "on_premise_option": False,
                "sort_order": 3,
            },
            # ── Enterprise (Custom) ──────────────────────────────────────────
            {
                "name": "Enterprise",
                "slug": "enterprise",
                "price_monthly_cents": 0,  # Invoiced separately
                "price_yearly_cents": None,
                "is_custom_pricing": True,
                "max_members": None,
                "max_monthly_messages": None,  # unlimited
                "max_channels": 99,
                "max_users": None,  # unlimited
                "max_connectors": 99,
                "overage_per_conversation_cents": None,
                "overage_per_user_cents": None,
                "overage_per_connector_cents": None,
                "overage_per_channel_cents": None,
                # Channels – all
                "whatsapp_enabled": True,
                "telegram_enabled": True,
                "sms_enabled": True,
                "email_channel_enabled": True,
                "voice_enabled": True,
                "instagram_enabled": True,
                "facebook_enabled": True,
                "google_business_enabled": True,
                # Features – all
                "memory_analyzer_enabled": True,
                "custom_prompts_enabled": True,
                "advanced_analytics_enabled": True,
                "branding_enabled": True,
                "audit_log_enabled": True,
                "automation_enabled": True,
                "api_access_enabled": True,
                "multi_source_members_enabled": True,
                # AI & LLM
                "ai_tier": "unlimited",
                "allowed_llm_models": None,  # NULL = all models
                "max_monthly_llm_tokens": None,  # unlimited
                "custom_llm_keys_enabled": True,
                # Connectors – all
                "connector_manual_enabled": True,
                "connector_api_enabled": True,
                "connector_csv_enabled": True,
                "connector_magicline_enabled": True,
                "connector_shopify_enabled": True,
                "connector_woocommerce_enabled": True,
                "connector_hubspot_enabled": True,
                # Premium – all
                "churn_prediction_enabled": True,
                "vision_ai_enabled": True,
                "white_label_enabled": True,
                "priority_support": True,
                "dedicated_support": True,
                "sla_enabled": True,
                "on_premise_option": True,
                "sort_order": 4,
            },
        ]

        for data in plans_data:
            existing = db.query(Plan).filter(Plan.slug == data["slug"]).first()
            if existing:
                # Update existing plan with new fields
                for key, value in data.items():
                    if key != "slug" and hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                db.add(Plan(**data))
        db.commit()

        # Remove old plans that are no longer in the new pricing
        for old_slug in ["pro"]:
            old = db.query(Plan).filter(Plan.slug == old_slug).first()
            if old:
                old.is_active = False
                db.commit()

        logger.info("feature_gate.plans_seeded")

        # ── Seed Add-ons ─────────────────────────────────────────────────────
        addons_data = [
            {
                "slug": "churn_prediction",
                "name": "Churn Prediction",
                "description": "ML-basierte Abwanderungsprognose für deine Mitglieder.",
                "category": "feature",
                "price_monthly_cents": 4900,
                "is_per_unit": False,
                "min_plan_slug": "starter",
                "feature_key": "churn_prediction_enabled",
                "sort_order": 1,
            },
            {
                "slug": "voice_pipeline",
                "name": "Voice Pipeline",
                "description": "Whisper STT + ElevenLabs TTS für Sprach-Interaktionen.",
                "category": "channel",
                "price_monthly_cents": 7900,
                "is_per_unit": False,
                "min_plan_slug": "starter",
                "feature_key": "voice_enabled",
                "sort_order": 2,
            },
            {
                "slug": "vision_ai",
                "name": "Vision AI",
                "description": "YOLOv8-basierte Bildanalyse für Nachrichten mit Fotos.",
                "category": "feature",
                "price_monthly_cents": 3900,
                "is_per_unit": False,
                "min_plan_slug": "starter",
                "feature_key": "vision_ai_enabled",
                "sort_order": 3,
            },
            {
                "slug": "extra_channel",
                "name": "Zusätzlicher Kanal",
                "description": "Einen weiteren Kommunikationskanal freischalten.",
                "category": "channel",
                "price_monthly_cents": 2900,
                "is_per_unit": True,
                "unit_label": "Kanal",
                "min_plan_slug": None,
                "sort_order": 4,
            },
            {
                "slug": "extra_conversations",
                "name": "Zusätzliche Konversationen",
                "description": "500 zusätzliche Konversationen pro Monat.",
                "category": "capacity",
                "price_monthly_cents": 1900,
                "is_per_unit": True,
                "unit_label": "500 Konversationen",
                "min_plan_slug": None,
                "sort_order": 5,
            },
            {
                "slug": "extra_user",
                "name": "Zusätzlicher User",
                "description": "Einen weiteren Benutzer-Account hinzufügen.",
                "category": "capacity",
                "price_monthly_cents": 1500,
                "is_per_unit": True,
                "unit_label": "User",
                "min_plan_slug": None,
                "sort_order": 6,
            },
            {
                "slug": "white_label",
                "name": "White-Label",
                "description": "Eigenes Branding, Logo und Domain für den Chatbot.",
                "category": "feature",
                "price_monthly_cents": 14900,
                "is_per_unit": False,
                "min_plan_slug": "professional",
                "feature_key": "white_label_enabled",
                "sort_order": 7,
            },
            {
                "slug": "api_access",
                "name": "API Access",
                "description": "REST API + Webhooks für externe Integrationen.",
                "category": "feature",
                "price_monthly_cents": 9900,
                "is_per_unit": False,
                "min_plan_slug": "starter",
                "feature_key": "api_access_enabled",
                "sort_order": 8,
            },
            {
                "slug": "extra_connector",
                "name": "Zusätzlicher Connector",
                "description": "Einen weiteren Mitglieder-Connector freischalten (Magicline, Shopify, WooCommerce, HubSpot).",
                "category": "capacity",
                "price_monthly_cents": 4900,
                "is_per_unit": True,
                "unit_label": "Connector",
                "min_plan_slug": "professional",
                "sort_order": 9,
            },
        ]

        for data in addons_data:
            existing = db.query(PlanAddon).filter(PlanAddon.slug == data["slug"]).first()
            if existing:
                for key, value in data.items():
                    if key != "slug" and hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                db.add(PlanAddon(**data))
        db.commit()
        logger.info("feature_gate.addons_seeded")

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
