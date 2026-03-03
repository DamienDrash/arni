"""
ARIIA Billing V2 – Seed Data (Hybrid Pricing Model)

Seeds the billing_features, billing_feature_sets, and billing_feature_entitlements
tables with the canonical ARIIA feature catalog. This maps all existing V1 plan
columns (channel toggles, feature toggles, limits) into the normalized V2 model.

Pricing Model: Hybrid (Basis-Pläne + Modulare Add-ons + Overage/Usage-Based)
Plans: Trial → Starter (99€) → Professional (249€) → Business (499€) → Enterprise

Stripe Product/Price IDs are stored per environment (test/live).

Usage:
    python -m app.billing.seed          # Run standalone
    await seed_billing_v2(db)           # Call from code
"""
from __future__ import annotations

import json
import os
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
# STRIPE PRODUCT/PRICE ID MAPPING (per environment)
# ══════════════════════════════════════════════════════════════════════════════

STRIPE_IDS = {
    "test": {
        "plans": {
            "starter": {
                "product_id": "prod_U4rFiet9dALMCX",
                "price_monthly_id": "price_1T6hXAEblznFgoKRkbQRnY66",
                "price_yearly_id": "price_1T6hXBEblznFgoKRJG60DgCB",
            },
            "pro": {
                "product_id": "prod_U4rFcVnusNv3wG",
                "price_monthly_id": "price_1T6hXCEblznFgoKRubsTuVMm",
                "price_yearly_id": "price_1T6hXDEblznFgoKRkyVQ4Pqc",
            },
            "business": {
                "product_id": "prod_U4rFZdJSiuDeMm",
                "price_monthly_id": "price_1T6hXEEblznFgoKRPD4OQWkC",
                "price_yearly_id": "price_1T6hXFEblznFgoKRCgfs7Tbl",
            },
        },
        "addons": {
            "voice_pipeline": {"product_id": "prod_U4rF43kA7qt99J", "price_monthly_id": "price_1T6hXGEblznFgoKRW0NCXJv9"},
            "vision_ai": {"product_id": "prod_U4rFtC4afeiIsj", "price_monthly_id": "price_1T6hXIEblznFgoKRwWzdc6Ug"},
            "white_label": {"product_id": "prod_U4rFXDwBFlHG2N", "price_monthly_id": "price_1T6hXKEblznFgoKRmncyYGyj"},
            "churn_prediction": {"product_id": "prod_U4rFf9un0qLAWb", "price_monthly_id": "price_1T6hXLEblznFgoKRR6dmjG73"},
            "extra_channel": {"product_id": "prod_U4rFwxNNjwCvE8", "price_monthly_id": "price_1T6hXNEblznFgoKR87CLsieD"},
            "automation_pack": {"product_id": "prod_U4rFTsoIUb1NTh", "price_monthly_id": "price_1T6hXOEblznFgoKRjmupULSV"},
            "advanced_analytics": {"product_id": "prod_U4rF7P89YF1B0m", "price_monthly_id": "price_1T6hXPEblznFgoKRILKqltoe"},
            "api_developer_toolkit": {"product_id": "prod_U4rF4OoqaIguL2", "price_monthly_id": "price_1T6hXREblznFgoKRokdoevMj"},
            "priority_support": {"product_id": "prod_U4rF2vuthkNJz4", "price_monthly_id": "price_1T6hXTEblznFgoKRXygq0FFE"},
            "multi_language_ai": {"product_id": "prod_U4rGCPINvs0sLU", "price_monthly_id": "price_1T6hXUEblznFgoKRgHq1LLwM"},
            "lead_scoring_ai": {"product_id": "prod_U4rGfuHqGpaRot", "price_monthly_id": "price_1T6hXWEblznFgoKRtd7IVl5F"},
            "custom_integrations": {"product_id": "prod_U4rGdj4SdcFDRG", "price_monthly_id": "price_1T6hXYEblznFgoKR7GPqmwAb"},
        },
        "overage": {
            "contacts": {
                "product_id": "prod_U4rGNKnodcwoQ7",
                "price_metered_id": "price_1T6haKEblznFgoKRGyUeVU9b",
                "meter_id": "mtr_test_61UG5WjQR7DsqsYjn41EblznFgoKRCSW",
                "meter_event_name": "ariia_contacts",
            },
            "ai_messages": {
                "product_id": "prod_U4rHyunuxfp5h3",
                "price_metered_id": "price_1T6haLEblznFgoKRBXylPqbI",
                "meter_id": "mtr_test_61UG5WkScA3HVwp7741EblznFgoKRXNA",
                "meter_event_name": "ariia_ai_messages",
            },
            "ai_tokens": {
                "product_id": "prod_U4rILORUDjo12A",
                "price_metered_id": "price_1T6haMEblznFgoKRodBUZu3M",
                "meter_id": "mtr_test_61UG5Wn0okluNbztr41EblznFgoKRTyy",
                "meter_event_name": "ariia_ai_tokens_1k",
            },
            "campaigns": {
                "product_id": "prod_U4rIfYet6Z7zvi",
                "price_metered_id": "price_1T6haNEblznFgoKR5aNDziMs",
                "meter_id": "mtr_test_61UG5Wp2bSuUYjsET41EblznFgoKRR7I",
                "meter_event_name": "ariia_campaigns",
            },
        },
    },
    "live": {
        "plans": {
            "starter": {
                "product_id": "prod_U4rGYUS3jRdqEo",
                "price_monthly_id": "price_1T6hXbEblznFgoKR31vk8sEb",
                "price_yearly_id": "price_1T6hXbEblznFgoKRKO6f6OcK",
            },
            "pro": {
                "product_id": "prod_U4rGfY0yjEjrQr",
                "price_monthly_id": "price_1T6hXdEblznFgoKRYTXfICsK",
                "price_yearly_id": "price_1T6hXdEblznFgoKRcLGSlOel",
            },
            "business": {
                "product_id": "prod_U4rGn5RmTCCssV",
                "price_monthly_id": "price_1T6hXfEblznFgoKR0dBTk2uD",
                "price_yearly_id": "price_1T6hXfEblznFgoKRq3RZ8nmF",
            },
        },
        "addons": {
            "voice_pipeline": {"product_id": "prod_U4rGWJ6AwFxgOx", "price_monthly_id": "price_1T6hXhEblznFgoKRdz8uwMzF"},
            "vision_ai": {"product_id": "prod_U4rG8MYTUCiuun", "price_monthly_id": "price_1T6hXiEblznFgoKRBmyqryhQ"},
            "white_label": {"product_id": "prod_U4rGDAZdmW4S7l", "price_monthly_id": "price_1T6hXjEblznFgoKRvklINuGv"},
            "churn_prediction": {"product_id": "prod_U4rGvvsNR03ZaX", "price_monthly_id": "price_1T6hXlEblznFgoKRT7NLQSDE"},
            "extra_channel": {"product_id": "prod_U4rGJZbgIVDHjz", "price_monthly_id": "price_1T6hXmEblznFgoKRfL4cXWeL"},
            "automation_pack": {"product_id": "prod_U4rGGhgX7oMTGE", "price_monthly_id": "price_1T6hXnEblznFgoKRifDSzIUF"},
            "advanced_analytics": {"product_id": "prod_U4rGt5siGlivhU", "price_monthly_id": "price_1T6hXpEblznFgoKRK6cGEIX4"},
            "api_developer_toolkit": {"product_id": "prod_U4rGFQYW8LUr72", "price_monthly_id": "price_1T6hXqEblznFgoKRfeyxDPia"},
            "priority_support": {"product_id": "prod_U4rGHdPDKU035g", "price_monthly_id": "price_1T6hXsEblznFgoKRWA080cOG"},
            "multi_language_ai": {"product_id": "prod_U4rGbgOqWZXqAz", "price_monthly_id": "price_1T6hXtEblznFgoKRXkqjbff4"},
            "lead_scoring_ai": {"product_id": "prod_U4rGgJ4yBeUt8K", "price_monthly_id": "price_1T6hXvEblznFgoKROc9GVzYE"},
            "custom_integrations": {"product_id": "prod_U4rGY7XFzJRXw1", "price_monthly_id": "price_1T6hXwEblznFgoKRThDDOOEZ"},
        },
        "overage": {
            "contacts": {
                "product_id": "prod_U4rG8BdUU5Jz6Q",
                "price_metered_id": "price_1T6haOEblznFgoKRBfj4GbL6",
                "meter_id": "mtr_61UG5WrWE3YLOmQRc41EblznFgoKRTns",
                "meter_event_name": "ariia_contacts",
            },
            "ai_messages": {
                "product_id": "prod_U4rIZEYL0AnEek",
                "price_metered_id": "price_1T6haPEblznFgoKRwcwbomyU",
                "meter_id": "mtr_61UG5WtFoVmkMRypz41EblznFgoKRMXw",
                "meter_event_name": "ariia_ai_messages",
            },
            "ai_tokens": {
                "product_id": "prod_U4rI8e17vhoiw4",
                "price_metered_id": "price_1T6haQEblznFgoKRn5sFUHLB",
                "meter_id": "mtr_61UG5WvV2ilYvOLsr41EblznFgoKR2Cu",
                "meter_event_name": "ariia_ai_tokens_1k",
            },
            "campaigns": {
                "product_id": "prod_U4rIquDI5MhZ34",
                "price_metered_id": "price_1T6haREblznFgoKR6z9oVtOQ",
                "meter_id": "mtr_61UG5WxcDjZjlFXgs41EblznFgoKRPui",
                "meter_event_name": "ariia_campaigns",
            },
        },
    },
}


def get_stripe_env() -> str:
    """Determine Stripe environment from STRIPE_SECRET_KEY or ENVIRONMENT."""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if key.startswith("sk_live_"):
        return "live"
    return "test"


def get_stripe_ids() -> dict[str, Any]:
    """Get Stripe IDs for the current environment."""
    return STRIPE_IDS[get_stripe_env()]


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
    {"key": "max_campaigns", "name": "Max. Kampagnen", "feature_type": "limit", "category": "limit", "unit": "campaigns", "order": 25},

    # ── AI ──────────────────────────────────────────────────────────────
    {"key": "ai_tier", "name": "KI-Stufe", "feature_type": "tier", "category": "ai", "order": 30},
    {"key": "memory_analyzer", "name": "Memory Analyzer", "feature_type": "boolean", "category": "ai", "order": 31},
    {"key": "custom_prompts", "name": "Eigene Prompts", "feature_type": "boolean", "category": "ai", "order": 32},
    {"key": "vision_ai", "name": "Vision AI", "feature_type": "boolean", "category": "ai", "order": 33},
    {"key": "multi_language_ai", "name": "Multi-Language AI", "feature_type": "boolean", "category": "ai", "order": 34},
    {"key": "lead_scoring_ai", "name": "Lead Scoring AI", "feature_type": "boolean", "category": "ai", "order": 35},

    # ── Analytics & Automation ──────────────────────────────────────────
    {"key": "advanced_analytics", "name": "Erweiterte Analysen", "feature_type": "boolean", "category": "analytics", "order": 40},
    {"key": "churn_prediction", "name": "Abwanderungs-Vorhersage", "feature_type": "boolean", "category": "analytics", "order": 41},
    {"key": "automation", "name": "Automatisierung", "feature_type": "boolean", "category": "automation", "order": 42},

    # ── Platform Features ───────────────────────────────────────────────
    {"key": "branding", "name": "Eigenes Branding", "feature_type": "boolean", "category": "platform", "order": 50},
    {"key": "audit_log", "name": "Audit-Log", "feature_type": "boolean", "category": "platform", "order": 51},
    {"key": "api_access", "name": "API-Zugang", "feature_type": "boolean", "category": "platform", "order": 52},
    {"key": "multi_source_members", "name": "Multi-Source Kontakte", "feature_type": "boolean", "category": "platform", "order": 53},
    {"key": "custom_integrations", "name": "Custom Integrations", "feature_type": "boolean", "category": "platform", "order": 54},
    {"key": "priority_support", "name": "Priority Support & SLA", "feature_type": "boolean", "category": "platform", "order": 55},
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
            "max_campaigns": {"limit": 2},
            "ai_tier": {"tier": "basic"},
            "memory_analyzer": {"bool": True},
            "custom_prompts": {"bool": True},
            "vision_ai": {"bool": False},
            "multi_language_ai": {"bool": False},
            "lead_scoring_ai": {"bool": False},
            "advanced_analytics": {"bool": False},
            "churn_prediction": {"bool": False},
            "automation": {"bool": False},
            "branding": {"bool": False},
            "audit_log": {"bool": False},
            "api_access": {"bool": False},
            "multi_source_members": {"bool": True},
            "custom_integrations": {"bool": False},
            "priority_support": {"bool": False},
            "white_label": {"bool": False},
            "sla_guarantee": {"bool": False},
            "on_premise": {"bool": False},
        },
    },

    # ── Starter: 99 €/Monat ─────────────────────────────────────────────
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
            "max_monthly_messages": {"limit": 2000},
            "max_channels": {"limit": 1},
            "max_connectors": {"limit": 0},
            "monthly_tokens": {"limit": 100000},
            "max_campaigns": {"limit": 5},
            "ai_tier": {"tier": "basic"},
            "memory_analyzer": {"bool": False},
            "custom_prompts": {"bool": False},
            "vision_ai": {"bool": False},
            "multi_language_ai": {"bool": False},
            "lead_scoring_ai": {"bool": False},
            "advanced_analytics": {"bool": False},
            "churn_prediction": {"bool": False},
            "automation": {"bool": False},
            "branding": {"bool": False},
            "audit_log": {"bool": False},
            "api_access": {"bool": False},
            "multi_source_members": {"bool": True},
            "custom_integrations": {"bool": False},
            "priority_support": {"bool": False},
            "white_label": {"bool": False},
            "sla_guarantee": {"bool": False},
            "on_premise": {"bool": False},
        },
    },

    # ── Professional: 249 €/Monat ───────────────────────────────────────
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
            "max_members": {"limit": 5000},
            "max_monthly_messages": {"limit": 10000},
            "max_channels": {"limit": 3},
            "max_connectors": {"limit": 3},
            "monthly_tokens": {"limit": 500000},
            "max_campaigns": {"limit": 25},
            "ai_tier": {"tier": "standard"},
            "memory_analyzer": {"bool": True},
            "custom_prompts": {"bool": True},
            "vision_ai": {"bool": False},
            "multi_language_ai": {"bool": False},
            "lead_scoring_ai": {"bool": False},
            "advanced_analytics": {"bool": True},
            "churn_prediction": {"bool": False},
            "automation": {"bool": False},
            "branding": {"bool": True},
            "audit_log": {"bool": True},
            "api_access": {"bool": True},
            "multi_source_members": {"bool": True},
            "custom_integrations": {"bool": False},
            "priority_support": {"bool": False},
            "white_label": {"bool": False},
            "sla_guarantee": {"bool": False},
            "on_premise": {"bool": False},
        },
    },

    # ── Business: 499 €/Monat ───────────────────────────────────────────
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
            "max_members": {"limit": 25000},
            "max_monthly_messages": {"limit": 50000},
            "max_channels": {"limit": 99},
            "max_connectors": {"limit": 99},
            "monthly_tokens": {"limit": 2000000},
            "max_campaigns": {"limit": 100},
            "ai_tier": {"tier": "premium"},
            "memory_analyzer": {"bool": True},
            "custom_prompts": {"bool": True},
            "vision_ai": {"bool": True},
            "multi_language_ai": {"bool": True},
            "lead_scoring_ai": {"bool": True},
            "advanced_analytics": {"bool": True},
            "churn_prediction": {"bool": True},
            "automation": {"bool": True},
            "branding": {"bool": True},
            "audit_log": {"bool": True},
            "api_access": {"bool": True},
            "multi_source_members": {"bool": True},
            "custom_integrations": {"bool": False},
            "priority_support": {"bool": False},
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
            "max_campaigns": {"limit": None},  # Unbegrenzt
            "ai_tier": {"tier": "unlimited"},
            "memory_analyzer": {"bool": True},
            "custom_prompts": {"bool": True},
            "vision_ai": {"bool": True},
            "multi_language_ai": {"bool": True},
            "lead_scoring_ai": {"bool": True},
            "advanced_analytics": {"bool": True},
            "churn_prediction": {"bool": True},
            "automation": {"bool": True},
            "branding": {"bool": True},
            "audit_log": {"bool": True},
            "api_access": {"bool": True},
            "multi_source_members": {"bool": True},
            "custom_integrations": {"bool": True},
            "priority_support": {"bool": True},
            "white_label": {"bool": True},
            "sla_guarantee": {"bool": True},
            "on_premise": {"bool": True},
        },
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PLAN DEFINITIONS (Hybrid Pricing Model)
# Prices updated: Starter 99€, Professional 249€, Business 499€
# Yearly = Monthly * 12 * 0.80 (20% Rabatt)
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
        "stripe_product_id": None,  # Trial hat kein Stripe-Produkt
        "stripe_price_monthly_id": None,
        "stripe_price_yearly_id": None,
        "features_json": [
            "1 WhatsApp-Kanal",
            "50 Kontakte",
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
        "price_monthly_cents": 9900,   # 99 €
        "price_yearly_cents": 95040,   # 99 * 12 * 0.80 = 950,40 € → 950 € in Stripe
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
            "500 Kontakte",
            "2.000 AI-Nachrichten/Monat",
            "Basic AI",
            "100K Tokens/Monat",
            "5 Kampagnen",
            "Multi-Source Kontakte",
        ],
    },
    {
        "slug": "pro",
        "name": "Professional",
        "description": "Für wachsende Teams – Multi-Channel, erweiterte Analytics und Automatisierung.",
        "tagline": "Unser beliebtester Plan",
        "price_monthly_cents": 24900,  # 249 €
        "price_yearly_cents": 239040,  # 249 * 12 * 0.80 = 2.390,40 € → 2.390 € in Stripe
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
            "3 Kanäle (WhatsApp, Telegram, SMS, E-Mail, IG, FB)",
            "5.000 Kontakte",
            "10.000 AI-Nachrichten/Monat",
            "Standard AI",
            "500K Tokens/Monat",
            "25 Kampagnen",
            "Memory Analyzer & Custom Prompts",
            "Advanced Analytics",
            "Branding, Audit Log, API Access",
            "3 Integrationen",
        ],
    },
    {
        "slug": "business",
        "name": "Business",
        "description": "Für Unternehmen – alle Kanäle, Premium AI, Automation und Churn Prediction.",
        "tagline": "Maximale Leistung",
        "price_monthly_cents": 49900,  # 499 €
        "price_yearly_cents": 479040,  # 499 * 12 * 0.80 = 4.790,40 € → 4.790 € in Stripe
        "trial_days": 0,
        "display_order": 3,
        "is_highlighted": False,
        "is_public": True,
        "cta_text": "Jetzt starten",
        "feature_set_slug": "business",
        "allowed_llm_providers": ["groq", "mistral", "openai", "anthropic", "gemini"],
        "token_price_per_1k_cents": 7,
        "features_json": [
            "Alle 8 Kanäle inkl. Voice & Google Business",
            "25.000 Kontakte",
            "50.000 AI-Nachrichten/Monat",
            "Premium AI",
            "2M Tokens/Monat",
            "100 Kampagnen",
            "Alle Pro-Features",
            "Automation & Churn Prediction",
            "Vision AI, Multi-Language AI, Lead Scoring AI",
            "99 Kanäle · 99 Integrationen",
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
        "stripe_product_id": None,  # Enterprise hat kein Stripe-Produkt
        "stripe_price_monthly_id": None,
        "stripe_price_yearly_id": None,
        "features_json": [
            "Alles aus Business",
            "Unbegrenzte Nachrichten & Kontakte",
            "Unlimited AI",
            "White Label",
            "SLA-Garantie",
            "On-Premise Option",
            "Dedizierter Support",
            "Custom Integrations",
            "Priority Support",
            "999 Kanäle · 999 Integrationen",
        ],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# ADD-ON DEFINITIONS (12 modulare Add-ons)
# 6 bestehende + 6 neue Module
# ══════════════════════════════════════════════════════════════════════════════

ADDONS: list[dict[str, Any]] = [
    # ── Bestehende Add-ons ──────────────────────────────────────────────
    {
        "slug": "voice_pipeline",
        "name": "Voice Pipeline",
        "description": "Sprach-KI für eingehende und ausgehende Anrufe mit natürlicher Sprachverarbeitung.",
        "category": "channel",
        "price_monthly_cents": 4900,
        "features_json": ["voice_enabled"],
        "display_order": 1,
        "min_plan": "starter",
    },
    {
        "slug": "vision_ai",
        "name": "Vision AI",
        "description": "Bild- und Dokumentenanalyse mit KI – automatische Erkennung und Klassifizierung.",
        "category": "ai",
        "price_monthly_cents": 2900,
        "features_json": ["vision_ai_enabled"],
        "display_order": 2,
        "min_plan": "starter",
    },
    {
        "slug": "white_label",
        "name": "White Label",
        "description": "Eigenes Branding – Logo, Farben und Domain für deine Kunden.",
        "category": "branding",
        "price_monthly_cents": 9900,
        "features_json": ["white_label_enabled"],
        "display_order": 3,
        "min_plan": "pro",
    },
    {
        "slug": "churn_prediction",
        "name": "Churn Prediction",
        "description": "KI-basierte Abwanderungsvorhersage mit automatischen Warnungen.",
        "category": "analytics",
        "price_monthly_cents": 3900,
        "features_json": ["churn_prediction_enabled"],
        "display_order": 4,
        "min_plan": "pro",
    },
    {
        "slug": "extra_channel",
        "name": "Extra Channel",
        "description": "Zusätzlicher Messaging-Kanal über das Plan-Limit hinaus.",
        "category": "channel",
        "price_monthly_cents": 2900,
        "features_json": ["extra_channel"],
        "display_order": 5,
        "min_plan": "starter",
    },
    {
        "slug": "automation_pack",
        "name": "Automation Pack",
        "description": "Erweiterte Workflow-Automatisierung mit Trigger-Regeln und Aktionen.",
        "category": "automation",
        "price_monthly_cents": 4900,
        "features_json": ["automation_enabled"],
        "display_order": 6,
        "min_plan": "starter",
    },

    # ── Neue Add-ons (Hybrid-Modell) ───────────────────────────────────
    {
        "slug": "advanced_analytics",
        "name": "Advanced Analytics",
        "description": "Erweiterte Dashboards, Exportfunktionen und benutzerdefinierte Reports.",
        "category": "analytics",
        "price_monthly_cents": 3900,
        "features_json": ["advanced_analytics_addon"],
        "display_order": 7,
        "min_plan": "starter",
    },
    {
        "slug": "api_developer_toolkit",
        "name": "API Developer Toolkit",
        "description": "Erweiterter API-Zugang mit Webhooks, SDKs und höheren Rate-Limits.",
        "category": "developer",
        "price_monthly_cents": 5900,
        "features_json": ["api_developer_toolkit_enabled"],
        "display_order": 8,
        "min_plan": "pro",
    },
    {
        "slug": "priority_support",
        "name": "Priority Support & SLA",
        "description": "Garantierte Reaktionszeiten, dedizierter Account Manager und SLA.",
        "category": "support",
        "price_monthly_cents": 7900,
        "features_json": ["priority_support_enabled", "sla_guarantee_enabled"],
        "display_order": 9,
        "min_plan": "pro",
    },
    {
        "slug": "multi_language_ai",
        "name": "Multi-Language AI",
        "description": "Automatische Spracherkennung und Antworten in 50+ Sprachen.",
        "category": "ai",
        "price_monthly_cents": 2900,
        "features_json": ["multi_language_ai_enabled"],
        "display_order": 10,
        "min_plan": "starter",
    },
    {
        "slug": "lead_scoring_ai",
        "name": "Lead Scoring AI",
        "description": "KI-basierte Lead-Bewertung und automatische Priorisierung.",
        "category": "ai",
        "price_monthly_cents": 3900,
        "features_json": ["lead_scoring_ai_enabled"],
        "display_order": 11,
        "min_plan": "pro",
    },
    {
        "slug": "custom_integrations",
        "name": "Custom Integrations",
        "description": "Maßgeschneiderte Integrationen mit CRM, ERP und Drittanbieter-Systemen.",
        "category": "integration",
        "price_monthly_cents": 4900,
        "features_json": ["custom_integrations_enabled"],
        "display_order": 12,
        "min_plan": "pro",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# OVERAGE PRICING CONFIGURATION
# Charged automatically when plan limits are exceeded
# ══════════════════════════════════════════════════════════════════════════════

OVERAGE_CONFIG: list[dict[str, Any]] = [
    {
        "slug": "overage_contacts",
        "name": "Zusätzliche Kontakte",
        "description": "10 € pro 1.000 zusätzliche Kontakte über das Plan-Limit hinaus.",
        "unit": "contacts",
        "unit_amount_cents": 1,  # 1 Cent pro Kontakt = 10 €/1.000
        "display_unit": "1.000 Kontakte",
        "display_price": "10 €",
    },
    {
        "slug": "overage_ai_messages",
        "name": "Zusätzliche AI-Nachrichten",
        "description": "5 € pro 1.000 zusätzliche AI-Nachrichten über das Plan-Limit hinaus.",
        "unit": "messages",
        "unit_amount_cents": 1,  # ~0.5 Cent pro Nachricht ≈ 5 €/1.000
        "display_unit": "1.000 Nachrichten",
        "display_price": "5 €",
    },
    {
        "slug": "overage_ai_tokens",
        "name": "Zusätzliche AI-Tokens",
        "description": "2 € pro 100.000 zusätzliche AI-Tokens über das Plan-Limit hinaus.",
        "unit": "tokens_1k",
        "unit_amount_cents": 2,  # 2 Cent pro 1K Tokens = 2 €/100K
        "display_unit": "100.000 Tokens",
        "display_price": "2 €",
    },
    {
        "slug": "overage_campaigns",
        "name": "Zusätzliche Kampagnen",
        "description": "5 € pro 10 zusätzliche Kampagnen über das Plan-Limit hinaus.",
        "unit": "campaigns",
        "unit_amount_cents": 50,  # 50 Cent pro Kampagne = 5 €/10
        "display_unit": "10 Kampagnen",
        "display_price": "5 €",
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
    stripe_env = get_stripe_env()
    stripe_ids = get_stripe_ids()

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

    # 3. Seed Plans (with Stripe IDs)
    for pdef in PLANS:
        plan_slug = pdef["slug"]

        # Resolve Stripe IDs for this plan
        plan_stripe = stripe_ids.get("plans", {}).get(plan_slug, {})
        stripe_product_id = pdef.get("stripe_product_id") or plan_stripe.get("product_id")
        stripe_price_monthly_id = pdef.get("stripe_price_monthly_id") or plan_stripe.get("price_monthly_id")
        stripe_price_yearly_id = pdef.get("stripe_price_yearly_id") or plan_stripe.get("price_yearly_id")

        existing = db.query(PlanV2).filter(PlanV2.slug == plan_slug).first()
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
            existing.stripe_product_id = stripe_product_id
            existing.stripe_price_monthly_id = stripe_price_monthly_id
            existing.stripe_price_yearly_id = stripe_price_yearly_id
            fs = feature_set_map.get(pdef["feature_set_slug"])
            if fs:
                existing.feature_set_id = fs.id
            continue

        fs = feature_set_map.get(pdef["feature_set_slug"])
        plan = PlanV2(
            slug=plan_slug,
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
            stripe_product_id=stripe_product_id,
            stripe_price_monthly_id=stripe_price_monthly_id,
            stripe_price_yearly_id=stripe_price_yearly_id,
        )
        db.add(plan)
        stats["plans"] += 1

    db.commit()
    logger.info(
        "billing.seed.complete",
        stripe_env=stripe_env,
        **stats,
    )
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
