"""
ARIIA Billing V2 – Seed Data

Seeds the billing_features, billing_feature_sets, and billing_feature_entitlements
tables with the canonical ARIIA feature catalog. This maps all existing V1 plan
columns (channel toggles, feature toggles, limits) into the normalized V2 model.

Plans match the V1 configuration exactly:
  Trial → Starter → Professional → Business → Enterprise

Usage:
    python -m app.billing.seed          # Run standalone
    await seed_billing_v2(db)           # Call from code
"""
from __future__ import annotations

import json
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.billing.models import (
    Feature,
    FeatureEntitlement,
    FeatureSet,
    FeatureType,
    PlanV2,
)

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════════════════════
# CANONICAL FEATURE CATALOG
# ══════════════════════════════════════════════════════════════════════════════

FEATURES: list[dict[str, Any]] = [
    # ── Channels ────────────────────────────────────────────────────────
    {"key": "channel_whatsapp", "name": "WhatsApp", "feature_type": "boolean", "category": "channel", "order": 10},
    {"key": "channel_telegram", "name": "Telegram", "feature_type": "boolean", "category": "channel", "order": 11},
    {"key": "channel_sms", "name": "SMS", "feature_type": "boolean", "category": "channel", "order": 12},
    {"key": "channel_email", "name": "E-Mail", "feature_type": "boolean", "category": "channel", "order": 13},
    {"key": "channel_voice", "name": "Voice", "feature_type": "boolean", "category": "channel", "order": 14},
    {"key": "channel_instagram", "name": "Instagram", "feature_type": "boolean", "category": "channel", "order": 15},
    {"key": "channel_facebook", "name": "Facebook", "feature_type": "boolean", "category": "channel", "order": 16},
    {"key": "channel_google_business", "name": "Google Business", "feature_type": "boolean", "category": "channel", "order": 17},

    # ── Limits ──────────────────────────────────────────────────────────
    {"key": "max_members", "name": "Max. Kontakte", "feature_type": "limit", "category": "limit", "unit": "members", "order": 20},
    {"key": "max_monthly_messages", "name": "Max. Nachrichten/Monat", "feature_type": "limit", "category": "limit", "unit": "messages", "order": 21},
    {"key": "max_channels", "name": "Max. Kanäle", "feature_type": "limit", "category": "limit", "unit": "channels", "order": 22},
    {"key": "max_connectors", "name": "Max. Integrationen", "feature_type": "limit", "category": "limit", "unit": "connectors", "order": 23},
    {"key": "monthly_tokens", "name": "KI-Tokens/Monat", "feature_type": "limit", "category": "limit", "unit": "tokens", "order": 24},

    # ── AI ──────────────────────────────────────────────────────────────
    {"key": "ai_tier", "name": "KI-Stufe", "feature_type": "tier", "category": "ai", "order": 30},
    {"key": "memory_analyzer", "name": "Memory Analyzer", "feature_type": "boolean", "category": "ai", "order": 31},
    {"key": "custom_prompts", "name": "Eigene Prompts", "feature_type": "boolean", "category": "ai", "order": 32},
    {"key": "vision_ai", "name": "Vision AI", "feature_type": "boolean", "category": "ai", "order": 33},

    # ── Analytics & Automation ──────────────────────────────────────────
    {"key": "advanced_analytics", "name": "Erweiterte Analysen", "feature_type": "boolean", "category": "analytics", "order": 40},
    {"key": "churn_prediction", "name": "Abwanderungs-Vorhersage", "feature_type": "boolean", "category": "analytics", "order": 41},
    {"key": "automation", "name": "Automatisierung", "feature_type": "boolean", "category": "automation", "order": 42},

    # ── Platform Features ───────────────────────────────────────────────
    {"key": "branding", "name": "Eigenes Branding", "feature_type": "boolean", "category": "platform", "order": 50},
    {"key": "audit_log", "name": "Audit-Log", "feature_type": "boolean", "category": "platform", "order": 51},
    {"key": "api_access", "name": "API-Zugang", "feature_type": "boolean", "category": "platform", "order": 52},
    {"key": "multi_source_members", "name": "Multi-Source Kontakte", "feature_type": "boolean", "category": "platform", "order": 53},
    {"key": "white_label", "name": "White-Label", "feature_type": "boolean", "category": "enterprise", "order": 60},
    {"key": "sla_guarantee", "name": "SLA-Garantie", "feature_type": "boolean", "category": "enterprise", "order": 61},
    {"key": "on_premise", "name": "On-Premise", "feature_type": "boolean", "category": "enterprise", "order": 62},

    # ── Metered (Usage-Based) ───────────────────────────────────────────
    {"key": "messages_inbound", "name": "Eingehende Nachrichten", "feature_type": "metered", "category": "usage", "unit": "messages", "order": 70},
    {"key": "messages_outbound", "name": "Ausgehende Nachrichten", "feature_type": "metered", "category": "usage", "unit": "messages", "order": 71},
    {"key": "llm_tokens_used", "name": "KI-Token-Verbrauch", "feature_type": "metered", "category": "usage", "unit": "tokens", "order": 72},
    {"key": "active_members", "name": "Aktive Kontakte", "feature_type": "metered", "category": "usage", "unit": "members", "order": 73},
]


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE SET DEFINITIONS (one per plan tier)
# Matches V1 feature_gates.py exactly
# ══════════════════════════════════════════════════════════════════════════════

FEATURE_SETS: dict[str, dict[str, Any]] = {
    # ── Trial: 14-Tage kostenloser Test mit eingeschränkten Features ────
    "trial": {
        "name": "Trial Tier",
        "description": "14-Tage kostenloser Test mit eingeschränkten Professional-Features",
        "entitlements": {
            "channel_whatsapp": {"bool": True},
            "channel_telegram": {"bool": False},
            "channel_sms": {"bool": False},
            "channel_email": {"bool": False},
            "channel_voice": {"bool": False},
            "channel_instagram": {"bool": False},
            "channel_facebook": {"bool": False},
            "channel_google_business": {"bool": False},
            "max_members": {"limit": 50},
            "max_monthly_messages": {"limit": 100},
            "max_channels": {"limit": 1},
            "max_connectors": {"limit": 0},
            "monthly_tokens": {"limit": 50000},
            "ai_tier": {"tier": "basic"},
            "memory_analyzer": {"bool": True},
            "custom_prompts": {"bool": True},
            "vision_ai": {"bool": False},
            "advanced_analytics": {"bool": False},
            "churn_prediction": {"bool": False},
            "automation": {"bool": False},
            "branding": {"bool": False},
            "audit_log": {"bool": False},
            "api_access": {"bool": False},
            "multi_source_members": {"bool": True},
            "white_label": {"bool": False},
            "sla_guarantee": {"bool": False},
            "on_premise": {"bool": False},
        },
    },

    # ── Starter: 79 €/Monat ─────────────────────────────────────────────
    "starter": {
        "name": "Starter Tier",
        "description": "Perfekt für den Einstieg – ein WhatsApp-Kanal mit KI-gestütztem Kundenservice",
        "entitlements": {
            "channel_whatsapp": {"bool": True},
            "channel_telegram": {"bool": False},
            "channel_sms": {"bool": False},
            "channel_email": {"bool": False},
            "channel_voice": {"bool": False},
            "channel_instagram": {"bool": False},
            "channel_facebook": {"bool": False},
            "channel_google_business": {"bool": False},
            "max_members": {"limit": 500},
            "max_monthly_messages": {"limit": 500},
            "max_channels": {"limit": 1},
            "max_connectors": {"limit": 0},
            "monthly_tokens": {"limit": 100000},
            "ai_tier": {"tier": "basic"},
            "memory_analyzer": {"bool": False},
            "custom_prompts": {"bool": False},
            "vision_ai": {"bool": False},
            "advanced_analytics": {"bool": False},
            "churn_prediction": {"bool": False},
            "automation": {"bool": False},
            "branding": {"bool": False},
            "audit_log": {"bool": False},
            "api_access": {"bool": False},
            "multi_source_members": {"bool": True},
            "white_label": {"bool": False},
            "sla_guarantee": {"bool": False},
            "on_premise": {"bool": False},
        },
    },

    # ── Professional: 199 €/Monat ───────────────────────────────────────
    "professional": {
        "name": "Professional Tier",
        "description": "Für wachsende Teams – Multi-Channel, erweiterte Analytics und Automatisierung",
        "entitlements": {
            "channel_whatsapp": {"bool": True},
            "channel_telegram": {"bool": True},
            "channel_sms": {"bool": True},
            "channel_email": {"bool": True},
            "channel_voice": {"bool": False},
            "channel_instagram": {"bool": True},
            "channel_facebook": {"bool": True},
            "channel_google_business": {"bool": False},
            "max_members": {"limit": None},  # Unbegrenzt
            "max_monthly_messages": {"limit": 2000},
            "max_channels": {"limit": 3},
            "max_connectors": {"limit": 1},
            "monthly_tokens": {"limit": 500000},
            "ai_tier": {"tier": "standard"},
            "memory_analyzer": {"bool": True},
            "custom_prompts": {"bool": True},
            "vision_ai": {"bool": False},
            "advanced_analytics": {"bool": True},
            "churn_prediction": {"bool": False},
            "automation": {"bool": False},
            "branding": {"bool": True},
            "audit_log": {"bool": True},
            "api_access": {"bool": True},
            "multi_source_members": {"bool": True},
            "white_label": {"bool": False},
            "sla_guarantee": {"bool": False},
            "on_premise": {"bool": False},
        },
    },

    # ── Business: 399 €/Monat ───────────────────────────────────────────
    "business": {
        "name": "Business Tier",
        "description": "Für Unternehmen – alle Kanäle, Premium AI, Automation und Churn Prediction",
        "entitlements": {
            "channel_whatsapp": {"bool": True},
            "channel_telegram": {"bool": True},
            "channel_sms": {"bool": True},
            "channel_email": {"bool": True},
            "channel_voice": {"bool": True},
            "channel_instagram": {"bool": True},
            "channel_facebook": {"bool": True},
            "channel_google_business": {"bool": True},
            "max_members": {"limit": None},  # Unbegrenzt
            "max_monthly_messages": {"limit": 10000},
            "max_channels": {"limit": 99},
            "max_connectors": {"limit": 99},
            "monthly_tokens": {"limit": 2000000},
            "ai_tier": {"tier": "premium"},
            "memory_analyzer": {"bool": True},
            "custom_prompts": {"bool": True},
            "vision_ai": {"bool": True},
            "advanced_analytics": {"bool": True},
            "churn_prediction": {"bool": True},
            "automation": {"bool": True},
            "branding": {"bool": True},
            "audit_log": {"bool": True},
            "api_access": {"bool": True},
            "multi_source_members": {"bool": True},
            "white_label": {"bool": False},
            "sla_guarantee": {"bool": False},
            "on_premise": {"bool": False},
        },
    },

    # ── Enterprise: Individuell ─────────────────────────────────────────
    "enterprise": {
        "name": "Enterprise Tier",
        "description": "Maßgeschneiderte Lösung mit White Label, SLA-Garantie und On-Premise Option",
        "entitlements": {
            "channel_whatsapp": {"bool": True},
            "channel_telegram": {"bool": True},
            "channel_sms": {"bool": True},
            "channel_email": {"bool": True},
            "channel_voice": {"bool": True},
            "channel_instagram": {"bool": True},
            "channel_facebook": {"bool": True},
            "channel_google_business": {"bool": True},
            "max_members": {"limit": None},  # Unbegrenzt
            "max_monthly_messages": {"limit": None},  # Unbegrenzt
            "max_channels": {"limit": 999},
            "max_connectors": {"limit": 999},
            "monthly_tokens": {"limit": None},  # Unbegrenzt
            "ai_tier": {"tier": "unlimited"},
            "memory_analyzer": {"bool": True},
            "custom_prompts": {"bool": True},
            "vision_ai": {"bool": True},
            "advanced_analytics": {"bool": True},
            "churn_prediction": {"bool": True},
            "automation": {"bool": True},
            "branding": {"bool": True},
            "audit_log": {"bool": True},
            "api_access": {"bool": True},
            "multi_source_members": {"bool": True},
            "white_label": {"bool": True},
            "sla_guarantee": {"bool": True},
            "on_premise": {"bool": True},
        },
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PLAN DEFINITIONS
# Matches V1 feature_gates.py + Live Frontend (www.ariia.ai/pricing) exactly
# Yearly prices = monthly * 12 * 0.80 (20% discount)
# ══════════════════════════════════════════════════════════════════════════════

PLANS: list[dict[str, Any]] = [
    {
        "slug": "trial",
        "name": "Trial",
        "description": "14-Tage kostenloser Test mit eingeschränkten Professional-Features.",
        "tagline": "Kostenlos testen",
        "price_monthly_cents": 0,
        "price_yearly_cents": None,
        "trial_days": 14,
        "display_order": 0,
        "is_highlighted": False,
        "is_public": False,
        "cta_text": "Kostenlos testen",
        "feature_set_slug": "trial",
        "allowed_llm_providers": ["groq"],
        "token_price_per_1k_cents": 0,
        "features_json": [
            "1 WhatsApp-Kanal",
            "50 Mitglieder",
            "100 Nachrichten/Monat",
            "Basic AI (Groq)",
            "50K Tokens/Monat",
            "Member Memory",
            "Wissensbasis",
            "Live Chat",
        ],
    },
    {
        "slug": "starter",
        "name": "Starter",
        "description": "Perfekt für den Einstieg – ein WhatsApp-Kanal mit KI-gestütztem Kundenservice.",
        "tagline": "Ideal für den Einstieg",
        "price_monthly_cents": 7900,
        "price_yearly_cents": 75840,  # 79 * 12 * 0.80 = 758,40 €
        "trial_days": 0,
        "display_order": 1,
        "is_highlighted": False,
        "is_public": True,
        "cta_text": "Jetzt starten",
        "feature_set_slug": "starter",
        "allowed_llm_providers": ["groq"],
        "token_price_per_1k_cents": 15,
        "features_json": [
            "1 WhatsApp-Kanal",
            "500 Mitglieder",
            "500 Nachrichten/Monat",
            "Basic AI",
            "100K Tokens/Monat",
            "500 Kontakte",
            "1 Kanal · 0 Connectors",
        ],
    },
    {
        "slug": "pro",
        "name": "Professional",
        "description": "Für wachsende Teams – Multi-Channel, erweiterte Analytics und Automatisierung.",
        "tagline": "Unser beliebtester Plan",
        "price_monthly_cents": 19900,
        "price_yearly_cents": 191040,  # 199 * 12 * 0.80 = 1.910,40 €
        "trial_days": 0,
        "display_order": 2,
        "is_highlighted": True,
        "highlight_label": "Am beliebtesten",
        "is_public": True,
        "cta_text": "Jetzt starten",
        "feature_set_slug": "professional",
        "allowed_llm_providers": ["groq", "mistral", "openai"],
        "token_price_per_1k_cents": 10,
        "features_json": [
            "3 Kanäle (WhatsApp, Telegram, SMS, E-Mail)",
            "Unbegrenzte Mitglieder",
            "2.000 Nachrichten/Monat",
            "Standard AI",
            "500K Tokens/Monat",
            "Memory Analyzer",
            "Custom Prompts",
            "Advanced Analytics",
            "Branding",
            "Audit Log",
            "API Access",
            "Unbegrenzte Kontakte",
            "3 Kanäle · 1 Connectors",
        ],
    },
    {
        "slug": "business",
        "name": "Business",
        "description": "Für Unternehmen – alle Kanäle, Premium AI, Automation und Churn Prediction.",
        "tagline": "Maximale Leistung",
        "price_monthly_cents": 39900,
        "price_yearly_cents": 383040,  # 399 * 12 * 0.80 = 3.830,40 €
        "trial_days": 0,
        "display_order": 3,
        "is_highlighted": False,
        "is_public": True,
        "cta_text": "Jetzt starten",
        "feature_set_slug": "business",
        "allowed_llm_providers": ["groq", "mistral", "openai", "anthropic", "gemini"],
        "token_price_per_1k_cents": 7,
        "features_json": [
            "Alle Kanäle inkl. Voice",
            "Unbegrenzte Mitglieder",
            "10.000 Nachrichten/Monat",
            "Premium AI",
            "2M Tokens/Monat",
            "Alle Pro-Features",
            "Automation",
            "Churn Prediction",
            "Vision AI",
            "Google Business",
            "Unbegrenzte Kontakte",
            "99 Kanäle · 99 Connectors",
        ],
    },
    {
        "slug": "enterprise",
        "name": "Enterprise",
        "description": "Maßgeschneiderte Lösung mit White Label, SLA-Garantie und On-Premise Option.",
        "tagline": "Maßgeschneidert für Sie",
        "price_monthly_cents": 0,  # Individuell / Contact Sales
        "price_yearly_cents": None,
        "trial_days": 30,
        "display_order": 4,
        "is_highlighted": False,
        "is_public": True,
        "cta_text": "Kontakt aufnehmen",
        "feature_set_slug": "enterprise",
        "allowed_llm_providers": ["groq", "mistral", "openai", "anthropic", "gemini"],
        "token_price_per_1k_cents": 5,
        "features_json": [
            "Alles aus Business",
            "Unbegrenzte Nachrichten",
            "Unlimited AI",
            "White Label",
            "SLA-Garantie",
            "On-Premise Option",
            "Dedizierter Support",
            "Unbegrenzte Kontakte",
            "999 Kanäle · 999 Connectors",
        ],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# ADD-ON DEFINITIONS
# Matches V1 feature_gates.py exactly
# ══════════════════════════════════════════════════════════════════════════════

ADDONS: list[dict[str, Any]] = [
    {
        "slug": "voice_pipeline",
        "name": "Voice Pipeline",
        "description": "Sprach-KI für eingehende und ausgehende Anrufe mit natürlicher Sprachverarbeitung.",
        "category": "channel",
        "price_monthly_cents": 4900,
        "features_json": ["voice_enabled"],
        "display_order": 1,
    },
    {
        "slug": "vision_ai",
        "name": "Vision AI",
        "description": "Bild- und Dokumentenanalyse mit KI – automatische Erkennung und Klassifizierung.",
        "category": "ai",
        "price_monthly_cents": 2900,
        "features_json": ["vision_ai_enabled"],
        "display_order": 2,
    },
    {
        "slug": "white_label",
        "name": "White Label",
        "description": "Eigenes Branding – Logo, Farben und Domain für deine Kunden.",
        "category": "integration",
        "price_monthly_cents": 9900,
        "features_json": ["white_label_enabled"],
        "display_order": 3,
    },
    {
        "slug": "churn_prediction",
        "name": "Churn Prediction",
        "description": "KI-basierte Abwanderungsvorhersage mit automatischen Warnungen.",
        "category": "analytics",
        "price_monthly_cents": 3900,
        "features_json": ["churn_prediction_enabled"],
        "display_order": 4,
    },
    {
        "slug": "extra_channel",
        "name": "Extra Channel",
        "description": "Zusätzlicher Messaging-Kanal über das Plan-Limit hinaus.",
        "category": "channel",
        "price_monthly_cents": 2900,
        "features_json": ["extra_channel"],
        "display_order": 5,
    },
    {
        "slug": "automation_pack",
        "name": "Automation Pack",
        "description": "Erweiterte Workflow-Automatisierung mit Trigger-Regeln und Aktionen.",
        "category": "integration",
        "price_monthly_cents": 4900,
        "features_json": ["automation_enabled"],
        "display_order": 6,
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# SEED FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

async def seed_billing_v2(db: Session) -> dict[str, int]:
    """
    Seed all V2 billing tables with the canonical feature catalog.

    Returns a summary of created records.
    """
    stats = {"features": 0, "feature_sets": 0, "entitlements": 0, "plans": 0}

    # 1. Seed Features
    feature_map: dict[str, Feature] = {}
    for fdef in FEATURES:
        existing = db.query(Feature).filter(Feature.key == fdef["key"]).first()
        if existing:
            feature_map[fdef["key"]] = existing
            continue

        feature = Feature(
            key=fdef["key"],
            name=fdef["name"],
            feature_type=FeatureType(fdef["feature_type"]),
            category=fdef.get("category"),
            unit=fdef.get("unit"),
            display_order=fdef.get("order", 0),
        )
        db.add(feature)
        db.flush()
        feature_map[fdef["key"]] = feature
        stats["features"] += 1

    logger.info("billing.seed.features_done", count=stats["features"])

    # 2. Seed Feature Sets and Entitlements
    feature_set_map: dict[str, FeatureSet] = {}
    for slug, fsdef in FEATURE_SETS.items():
        existing = db.query(FeatureSet).filter(FeatureSet.slug == slug).first()
        if existing:
            feature_set_map[slug] = existing
            continue

        fs = FeatureSet(
            name=fsdef["name"],
            slug=slug,
            description=fsdef.get("description"),
        )
        db.add(fs)
        db.flush()
        feature_set_map[slug] = fs
        stats["feature_sets"] += 1

        # Create entitlements
        for feature_key, config in fsdef["entitlements"].items():
            feature = feature_map.get(feature_key)
            if not feature:
                logger.warning("billing.seed.feature_not_found", key=feature_key)
                continue

            entitlement = FeatureEntitlement(
                feature_set_id=fs.id,
                feature_id=feature.id,
                value_bool=config.get("bool"),
                value_limit=config.get("limit"),
                value_tier=config.get("tier"),
                hard_limit=config.get("hard_limit"),
                overage_price_cents=config.get("overage_price_cents"),
            )
            db.add(entitlement)
            stats["entitlements"] += 1

    db.flush()
    logger.info("billing.seed.feature_sets_done", count=stats["feature_sets"], entitlements=stats["entitlements"])

    # 3. Seed Plans
    for pdef in PLANS:
        existing = db.query(PlanV2).filter(PlanV2.slug == pdef["slug"]).first()
        if existing:
            # Update existing plan to match seed data
            existing.name = pdef["name"]
            existing.description = pdef.get("description")
            existing.tagline = pdef.get("tagline")
            existing.price_monthly_cents = pdef["price_monthly_cents"]
            existing.price_yearly_cents = pdef.get("price_yearly_cents")
            existing.trial_days = pdef.get("trial_days", 0)
            existing.display_order = pdef.get("display_order", 0)
            existing.is_highlighted = pdef.get("is_highlighted", False)
            existing.highlight_label = pdef.get("highlight_label")
            existing.cta_text = pdef.get("cta_text")
            existing.features_json = json.dumps(pdef.get("features_json", []), ensure_ascii=False)
            fs = feature_set_map.get(pdef["feature_set_slug"])
            if fs:
                existing.feature_set_id = fs.id
            continue

        fs = feature_set_map.get(pdef["feature_set_slug"])
        plan = PlanV2(
            slug=pdef["slug"],
            name=pdef["name"],
            description=pdef.get("description"),
            tagline=pdef.get("tagline"),
            price_monthly_cents=pdef["price_monthly_cents"],
            price_yearly_cents=pdef.get("price_yearly_cents"),
            trial_days=pdef.get("trial_days", 0),
            display_order=pdef.get("display_order", 0),
            is_highlighted=pdef.get("is_highlighted", False),
            highlight_label=pdef.get("highlight_label"),
            cta_text=pdef.get("cta_text"),
            feature_set_id=fs.id if fs else None,
            features_json=json.dumps(pdef.get("features_json", []), ensure_ascii=False),
        )
        db.add(plan)
        stats["plans"] += 1

    db.commit()
    logger.info("billing.seed.complete", **stats)
    return stats


# ── CLI Entry Point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    from app.core.db import SessionLocal

    async def main():
        db = SessionLocal()
        try:
            result = await seed_billing_v2(db)
            print(f"Seed complete: {result}")
        finally:
            db.close()

    asyncio.run(main())
