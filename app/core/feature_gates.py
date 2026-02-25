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
    "max_monthly_messages": 500,
    "max_members": 500,
    "max_channels": 1,
    "max_connectors": 0,
    "ai_tier": "basic",
    "monthly_tokens": 100000,
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
    "churn_prediction_enabled": False,
    "vision_ai_enabled": False,
    "white_label_enabled": False,
    "sla_guarantee_enabled": False,
    "on_premise_enabled": False,
}


class FeatureGate:
    """Checks and enforces plan limits for a given tenant.

    One instance per request — do not cache as usage counters change frequently.
    """

    def __init__(self, tenant_id: int) -> None:
        self._tenant_id = tenant_id
        self._plan_data: dict[str, object] = self._load_plan()
        self._addon_slugs: set[str] = self._load_active_addons()

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

    def _load_active_addons(self) -> set[str]:
        """Load the set of active addon slugs for this tenant."""
        try:
            from app.core.db import SessionLocal
            from app.core.models import TenantAddon
            db = SessionLocal()
            try:
                addons = db.query(TenantAddon.addon_slug).filter(
                    TenantAddon.tenant_id == self._tenant_id,
                    TenantAddon.status == "active",
                ).all()
                return {a[0] for a in addons}
            finally:
                db.close()
        except Exception as exc:
            logger.warning("feature_gate.addon_load_failed", tenant_id=self._tenant_id, error=str(exc))
        return set()

    def has_addon(self, addon_slug: str) -> bool:
        """Check if the tenant has an active addon by slug."""
        return addon_slug in self._addon_slugs

    # ── Channel Gates ─────────────────────────────────────────────────────────

    def require_channel(self, channel: str) -> None:
        """Raise HTTP 402 if the given channel is not enabled in the tenant's plan.

        Args:
            channel: One of 'whatsapp', 'telegram', 'sms', 'email', 'voice', 'instagram', 'facebook', 'google_business'.
        """
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
            # Check if an addon unlocks this channel
            channel_addon_map = {
                "voice": "voice_pipeline",
                "sms": "extra_channel",
                "instagram": "extra_channel",
                "facebook": "extra_channel",
                "google_business": "extra_channel",
            }
            addon_slug = channel_addon_map.get(channel.lower())
            if addon_slug and self.has_addon(addon_slug):
                return  # Addon unlocks this channel

            raise HTTPException(
                status_code=402,
                detail=f"Channel '{channel}' is not available on your current plan. Please upgrade.",
            )

    def require_feature(self, feature: str) -> None:
        """Raise HTTP 402 if a named feature is not in the tenant's plan or addons.

        Args:
            feature: e.g. 'memory_analyzer', 'custom_prompts', 'vision_ai'
        """
        key = f"{feature}_enabled"
        if self._plan_data.get(key, False):
            return  # Plan includes this feature

        # Check if an addon unlocks this feature
        feature_addon_map = {
            "vision_ai": "vision_ai",
            "churn_prediction": "churn_prediction",
            "voice": "voice_pipeline",
            "white_label": "white_label",
            "advanced_analytics": "advanced_analytics",
        }
        addon_slug = feature_addon_map.get(feature)
        if addon_slug and self.has_addon(addon_slug):
            return  # Addon unlocks this feature

        raise HTTPException(
            status_code=402,
            detail=f"Feature '{feature}' is not available on your current plan. Please upgrade.",
        )

    def get_plan_slug(self) -> str:
        """Return the current plan slug."""
        return str(self._plan_data.get("slug", "starter"))

    def get_plan_name(self) -> str:
        """Return the current plan name."""
        return str(self._plan_data.get("name", "Starter"))

    def get_ai_tier(self) -> str:
        """Return the AI tier for this tenant's plan."""
        return str(self._plan_data.get("ai_tier", "basic"))

    def get_monthly_token_limit(self) -> int:
        """Return the monthly token limit."""
        return int(self._plan_data.get("monthly_tokens", 100000))

    # ── Usage Gates ─────────────────────────────────────────────────────────

    def check_message_limit(self) -> None:
        """Raise HTTP 429 if the tenant has reached their monthly message quota."""
        max_msgs = self._plan_data.get("max_monthly_messages")
        if max_msgs is None:
            return  # unlimited
        
        current = self._get_current_usage()
        total = current.get("messages_inbound", 0) + current.get("messages_outbound", 0)
        
        # In the new model, we allow overage for some plans, but let's stick to the strict limit for Starter
        # and assume "soft limit" for higher tiers if implemented.
        # For this "Gold Standard" implementation, we'll enforce the limit unless it's an Enterprise plan (which is None anyway).
        if total >= int(max_msgs):
             raise HTTPException(
                status_code=429,
                detail=(
                    f"Monthly message limit of {max_msgs} reached. "
                    "Please upgrade your plan to continue."
                ),
            )

    def check_member_limit(self) -> None:
        """Raise HTTP 402 if the tenant has reached their member quota."""
        max_members = self._plan_data.get("max_members")
        if max_members is None:
            return # unlimited
        
        # We need to query the actual member count.
        # This is expensive to do on every request, so we should rely on cached usage record or count efficiently.
        # Here we use the usage record.
        current = self._get_current_usage()
        if current.get("active_members", 0) >= int(max_members):
             raise HTTPException(
                status_code=402,
                detail=(
                    f"Member limit of {max_members} reached. "
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
            logger.warning("feature_gate.usage_load_failed", tenant_id=self._tenant_id, error=str(exc))
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

    def set_active_members(self, count: int) -> None:
        """Set the active members counter for the current month."""
        self._set_usage_field("active_members", count)

    def _increment_usage_field(self, field: str, amount: int = 1) -> None:
        now = datetime.now(timezone.utc)
        try:
            from sqlalchemy import text
            from app.core.db import SessionLocal, engine
            from app.core.models import UsageRecord
            
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

    def _set_usage_field(self, field: str, value: int) -> None:
        now = datetime.now(timezone.utc)
        try:
            from sqlalchemy import text
            from app.core.db import SessionLocal, engine
            from app.core.models import UsageRecord
            
            db = SessionLocal()
            try:
                dialect = engine.dialect.name
                if dialect == "postgresql":
                    db.execute(
                        text(
                            f"INSERT INTO usage_records (tenant_id, period_year, period_month, {field}) "
                            f"VALUES (:tid, :yr, :mo, :val) "
                            f"ON CONFLICT (tenant_id, period_year, period_month) "
                            f"DO UPDATE SET {field} = :val"
                        ),
                        {"tid": self._tenant_id, "yr": now.year, "mo": now.month, "val": value},
                    )
                else:
                    rec = db.query(UsageRecord).filter(
                        UsageRecord.tenant_id == self._tenant_id,
                        UsageRecord.period_year == now.year,
                        UsageRecord.period_month == now.month,
                    ).first()
                    if rec:
                        setattr(rec, field, value)
                    else:
                        rec = UsageRecord(
                            tenant_id=self._tenant_id,
                            period_year=now.year,
                            period_month=now.month,
                            **{field: value},
                        )
                        db.add(rec)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("feature_gate.usage_set_failed", field=field, tenant_id=self._tenant_id, error=str(exc))


def seed_plans() -> None:
    """Seed the 4 standard plans + default add-ons if they don't exist yet.

    Plans: Starter, Professional, Business, Enterprise
    Add-ons: Voice Pipeline, Vision AI, White Label, Churn Prediction, Extra Channel, Automation Pack

    Called at startup from gateway/main.py.
    """
    from app.core.db import SessionLocal
    from app.core.models import Plan, Subscription, Tenant, AddonDefinition

    db = SessionLocal()
    try:
        plans_data = [
            {
                "name": "Starter",
                "slug": "starter",
                "description": "Perfekt fuer den Einstieg - ein WhatsApp-Kanal mit KI-gestuetztem Kundenservice.",
                "price_monthly_cents": 7900,
                "display_order": 1,
                "is_highlighted": False,
                "is_public": True,
                "features_json": '["1 WhatsApp-Kanal", "500 Mitglieder", "500 Nachrichten/Monat", "Basic AI", "100K Tokens/Monat"]',
                "max_members": 500,
                "max_monthly_messages": 500,
                "max_channels": 1,
                "max_connectors": 0,
                "ai_tier": "basic",
                "monthly_tokens": 100000,
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
                "multi_source_members_enabled": True,
                "churn_prediction_enabled": False,
                "vision_ai_enabled": False,
                "white_label_enabled": False,
                "sla_guarantee_enabled": False,
                "on_premise_enabled": False,
            },
            {
                "name": "Professional",
                "slug": "pro",
                "description": "Fuer wachsende Teams - Multi-Channel, erweiterte Analytics und Automatisierung.",
                "price_monthly_cents": 19900,
                "price_yearly_cents": 199000,
                "display_order": 2,
                "is_highlighted": True,
                "is_public": True,
                "features_json": '["3 Kanaele (WhatsApp, Telegram, SMS, E-Mail)", "Unbegrenzte Mitglieder", "2.000 Nachrichten/Monat", "Standard AI", "500K Tokens/Monat", "Memory Analyzer", "Custom Prompts", "Advanced Analytics", "Branding", "Audit Log", "API Access"]',
                "max_members": None,
                "max_monthly_messages": 2000,
                "max_channels": 3,
                "max_connectors": 1,
                "ai_tier": "standard",
                "monthly_tokens": 500000,
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
                "churn_prediction_enabled": False,
                "vision_ai_enabled": False,
                "white_label_enabled": False,
                "sla_guarantee_enabled": False,
                "on_premise_enabled": False,
            },
            {
                "name": "Business",
                "slug": "business",
                "description": "Fuer Unternehmen - alle Kanaele, Premium AI, Automation und Churn Prediction.",
                "price_monthly_cents": 39900,
                "price_yearly_cents": 399000,
                "display_order": 3,
                "is_highlighted": False,
                "is_public": True,
                "features_json": '["Alle Kanaele inkl. Voice", "Unbegrenzte Mitglieder", "10.000 Nachrichten/Monat", "Premium AI", "2M Tokens/Monat", "Alle Pro-Features", "Automation", "Churn Prediction", "Vision AI", "Google Business"]',
                "max_members": None,
                "max_monthly_messages": 10000,
                "max_channels": 99,
                "max_connectors": 99,
                "ai_tier": "premium",
                "monthly_tokens": 2000000,
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
                "churn_prediction_enabled": True,
                "vision_ai_enabled": True,
                "white_label_enabled": False,
                "sla_guarantee_enabled": False,
                "on_premise_enabled": False,
            },
            {
                "name": "Enterprise",
                "slug": "enterprise",
                "description": "Massgeschneiderte Loesung mit White Label, SLA-Garantie und On-Premise Option.",
                "price_monthly_cents": 0,
                "display_order": 4,
                "is_highlighted": False,
                "is_public": True,
                "features_json": '["Alles aus Business", "Unbegrenzte Nachrichten", "Unlimited AI", "White Label", "SLA-Garantie", "On-Premise Option", "Dedizierter Support"]',
                "max_members": None,
                "max_monthly_messages": None,
                "max_channels": 999,
                "max_connectors": 999,
                "ai_tier": "unlimited",
                "monthly_tokens": 0,
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
                "churn_prediction_enabled": True,
                "vision_ai_enabled": True,
                "white_label_enabled": True,
                "sla_guarantee_enabled": True,
                "on_premise_enabled": True,
            },
        ]

        for data in plans_data:
            existing = db.query(Plan).filter(Plan.slug == data["slug"]).first()
            if not existing:
                db.add(Plan(**data))
            else:
                # Update existing plan definitions to match code (important for deployments)
                for key, value in data.items():
                    setattr(existing, key, value)

        db.commit()
        logger.info("feature_gate.plans_seeded")

        # ── Seed Add-on Definitions ──────────────────────────────────────
        addons_data = [
            {
                "slug": "voice_pipeline",
                "name": "Voice Pipeline",
                "description": "Sprach-KI fuer eingehende und ausgehende Anrufe mit natuerlicher Sprachverarbeitung.",
                "category": "channel",
                "price_monthly_cents": 4900,
                "features_json": '["voice_enabled"]',
                "display_order": 1,
            },
            {
                "slug": "vision_ai",
                "name": "Vision AI",
                "description": "Bild- und Dokumentenanalyse mit KI - automatische Erkennung und Klassifizierung.",
                "category": "ai",
                "price_monthly_cents": 2900,
                "features_json": '["vision_ai_enabled"]',
                "display_order": 2,
            },
            {
                "slug": "white_label",
                "name": "White Label",
                "description": "Eigenes Branding - Logo, Farben und Domain fuer deine Kunden.",
                "category": "integration",
                "price_monthly_cents": 9900,
                "features_json": '["white_label_enabled"]',
                "display_order": 3,
            },
            {
                "slug": "churn_prediction",
                "name": "Churn Prediction",
                "description": "KI-basierte Abwanderungsvorhersage mit automatischen Warnungen.",
                "category": "analytics",
                "price_monthly_cents": 3900,
                "features_json": '["churn_prediction_enabled"]',
                "display_order": 4,
            },
            {
                "slug": "extra_channel",
                "name": "Extra Channel",
                "description": "Zusaetzlicher Messaging-Kanal ueber das Plan-Limit hinaus.",
                "category": "channel",
                "price_monthly_cents": 2900,
                "features_json": '["extra_channel"]',
                "display_order": 5,
            },
            {
                "slug": "automation_pack",
                "name": "Automation Pack",
                "description": "Erweiterte Workflow-Automatisierung mit Trigger-Regeln und Aktionen.",
                "category": "integration",
                "price_monthly_cents": 4900,
                "features_json": '["automation_enabled"]',
                "display_order": 6,
            },
        ]

        for adata in addons_data:
            existing_addon = db.query(AddonDefinition).filter(
                AddonDefinition.slug == adata["slug"]
            ).first()
            if not existing_addon:
                db.add(AddonDefinition(**adata))
            # Do NOT overwrite existing addons (admin may have customized them)

        db.commit()
        logger.info("feature_gate.addons_seeded")

        # Assign Starter plan to any tenant without a subscription (idempotent)
        starter_plan = db.query(Plan).filter(Plan.slug == "starter").first()
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

