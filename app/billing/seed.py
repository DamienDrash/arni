"""
ARIIA Billing V2 – Seed Data

Seeds the billing_features, billing_feature_sets, and billing_feature_entitlements
tables with the canonical ARIIA feature catalog. This maps all existing V1 plan
columns (channel toggles, feature toggles, limits) into the normalized V2 model.

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
# ══════════════════════════════════════════════════════════════════════════════

FEATURE_SETS: dict[str, dict[str, Any]] = {
    "free": {
        "name": "Free Tier",
        "description": "Grundlegende Funktionen für den Einstieg",
        "entitlements": {
            "channel_whatsapp": {"bool": True},
            "channel_telegram": {"bool": False},
            "channel_sms": {"bool": False},
            "channel_email": {"bool": False},
            "channel_voice": {"bool": False},
            "channel_instagram": {"bool": False},
            "channel_facebook": {"bool": False},
            "channel_google_business": {"bool": False},
            "max_members": {"limit": 100},
            "max_monthly_messages": {"limit": 500},
            "max_channels": {"limit": 1},
            "max_connectors": {"limit": 0},
            "monthly_tokens": {"limit": 50000},
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
            "multi_source_members": {"bool": False},
            "white_label": {"bool": False},
            "sla_guarantee": {"bool": False},
            "on_premise": {"bool": False},
        },
    },
    "starter": {
        "name": "Starter Tier",
        "description": "Für kleine Teams und Einzelunternehmer",
        "entitlements": {
            "channel_whatsapp": {"bool": True},
            "channel_telegram": {"bool": True},
            "channel_sms": {"bool": False},
            "channel_email": {"bool": True},
            "channel_voice": {"bool": False},
            "channel_instagram": {"bool": True},
            "channel_facebook": {"bool": True},
            "channel_google_business": {"bool": False},
            "max_members": {"limit": 500},
            "max_monthly_messages": {"limit": 2000},
            "max_channels": {"limit": 3},
            "max_connectors": {"limit": 2},
            "monthly_tokens": {"limit": 200000},
            "ai_tier": {"tier": "standard"},
            "memory_analyzer": {"bool": True},
            "custom_prompts": {"bool": True},
            "vision_ai": {"bool": False},
            "advanced_analytics": {"bool": False},
            "churn_prediction": {"bool": False},
            "automation": {"bool": True},
            "branding": {"bool": False},
            "audit_log": {"bool": False},
            "api_access": {"bool": False},
            "multi_source_members": {"bool": False},
            "white_label": {"bool": False},
            "sla_guarantee": {"bool": False},
            "on_premise": {"bool": False},
        },
    },
    "professional": {
        "name": "Professional Tier",
        "description": "Für wachsende Unternehmen mit erweiterten Anforderungen",
        "entitlements": {
            "channel_whatsapp": {"bool": True},
            "channel_telegram": {"bool": True},
            "channel_sms": {"bool": True},
            "channel_email": {"bool": True},
            "channel_voice": {"bool": True},
            "channel_instagram": {"bool": True},
            "channel_facebook": {"bool": True},
            "channel_google_business": {"bool": True},
            "max_members": {"limit": 5000},
            "max_monthly_messages": {"limit": 10000},
            "max_channels": {"limit": 8},
            "max_connectors": {"limit": 10},
            "monthly_tokens": {"limit": 1000000},
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
    "enterprise": {
        "name": "Enterprise Tier",
        "description": "Für Großunternehmen mit individuellen Anforderungen",
        "entitlements": {
            "channel_whatsapp": {"bool": True},
            "channel_telegram": {"bool": True},
            "channel_sms": {"bool": True},
            "channel_email": {"bool": True},
            "channel_voice": {"bool": True},
            "channel_instagram": {"bool": True},
            "channel_facebook": {"bool": True},
            "channel_google_business": {"bool": True},
            "max_members": {"limit": None},  # Unlimited
            "max_monthly_messages": {"limit": None},  # Unlimited
            "max_channels": {"limit": None},  # Unlimited
            "max_connectors": {"limit": None},  # Unlimited
            "monthly_tokens": {"limit": None},  # Unlimited
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
# ══════════════════════════════════════════════════════════════════════════════

PLANS: list[dict[str, Any]] = [
    {
        "slug": "free",
        "name": "Free",
        "description": "Perfekt zum Ausprobieren",
        "tagline": "Kostenlos starten",
        "price_monthly_cents": 0,
        "price_yearly_cents": None,
        "trial_days": 0,
        "display_order": 0,
        "is_highlighted": False,
        "cta_text": "Kostenlos starten",
        "feature_set_slug": "free",
        "features_json": [
            "1 WhatsApp-Kanal",
            "100 Kontakte",
            "500 Nachrichten/Monat",
            "50.000 KI-Tokens",
            "Basis-KI",
        ],
    },
    {
        "slug": "starter",
        "name": "Starter",
        "description": "Für kleine Teams und Einzelunternehmer",
        "tagline": "Ideal für den Einstieg",
        "price_monthly_cents": 4900,
        "price_yearly_cents": 47000,
        "trial_days": 14,
        "display_order": 1,
        "is_highlighted": False,
        "cta_text": "14 Tage kostenlos testen",
        "feature_set_slug": "starter",
        "features_json": [
            "3 Kanäle (WhatsApp, Telegram, E-Mail, Instagram, Facebook)",
            "500 Kontakte",
            "2.000 Nachrichten/Monat",
            "200.000 KI-Tokens",
            "Standard-KI mit Memory Analyzer",
            "Eigene Prompts",
            "Automatisierung",
            "2 Integrationen",
        ],
    },
    {
        "slug": "professional",
        "name": "Professional",
        "description": "Für wachsende Unternehmen",
        "tagline": "Unser beliebtester Plan",
        "price_monthly_cents": 14900,
        "price_yearly_cents": 143000,
        "trial_days": 14,
        "display_order": 2,
        "is_highlighted": True,
        "highlight_label": "Beliebteste Wahl",
        "cta_text": "14 Tage kostenlos testen",
        "feature_set_slug": "professional",
        "features_json": [
            "Alle 8 Kanäle",
            "5.000 Kontakte",
            "10.000 Nachrichten/Monat",
            "1.000.000 KI-Tokens",
            "Premium-KI mit Vision AI",
            "Erweiterte Analysen & Churn-Vorhersage",
            "Eigenes Branding & Audit-Log",
            "API-Zugang",
            "10 Integrationen",
        ],
    },
    {
        "slug": "enterprise",
        "name": "Enterprise",
        "description": "Für Großunternehmen mit individuellen Anforderungen",
        "tagline": "Maßgeschneidert für Sie",
        "price_monthly_cents": 0,  # Custom pricing
        "price_yearly_cents": None,
        "trial_days": 30,
        "display_order": 3,
        "is_highlighted": False,
        "cta_text": "Kontakt aufnehmen",
        "feature_set_slug": "enterprise",
        "features_json": [
            "Alle Kanäle – unbegrenzt",
            "Unbegrenzte Kontakte",
            "Unbegrenzte Nachrichten",
            "Unbegrenzte KI-Tokens",
            "White-Label & On-Premise",
            "SLA-Garantie",
            "Dedizierter Account Manager",
            "Individuelle Integrationen",
        ],
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
