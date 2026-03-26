"""app/platform/seed.py — Idempotent seeding of integration_definitions.

Called at startup from app/gateway/main.py.
Data mirrors alembic/versions/2026_03_03_dyn7_integration_registry_seed.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

logger = structlog.get_logger()

INTEGRATION_DEFINITIONS = [
    # ── Messaging ────────────────────────────────────────────────────────
    {"id": "whatsapp", "name": "WhatsApp", "description": "Connect WhatsApp Business API via Meta Cloud.", "category": "messaging", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.whatsapp_adapter.WhatsAppAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "telegram", "name": "Telegram", "description": "Connect Telegram Bot API.", "category": "messaging", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.telegram_adapter.TelegramAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "sms", "name": "SMS (Twilio)", "description": "Send and receive SMS via Twilio.", "category": "messaging", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.sms_voice_adapter.SmsVoiceAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "twilio_voice", "name": "Twilio Voice", "description": "Inbound and outbound voice calls via Twilio.", "category": "messaging", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.sms_voice_adapter.SmsVoiceAdapter", "is_public": True, "min_plan": "enterprise"},
    {"id": "postmark", "name": "Postmark", "description": "Transactional email delivery with high deliverability.", "category": "messaging", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.email_adapter.EmailAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "smtp_email", "name": "E-Mail (SMTP & IMAP)", "description": "Eigener Mail-Server für Versand (SMTP) und Empfang (IMAP).", "category": "messaging", "auth_type": "basic", "adapter_class": "app.integrations.adapters.email_adapter.EmailAdapter", "is_public": True, "min_plan": "starter"},
    {"id": "instagram", "name": "Instagram Messenger", "description": "Respond to Instagram DMs via Meta Graph API.", "category": "messaging", "auth_type": "oauth2", "adapter_class": None, "is_public": True, "min_plan": "professional"},
    {"id": "facebook", "name": "Facebook Messenger", "description": "Automate Facebook Page messaging.", "category": "messaging", "auth_type": "oauth2", "adapter_class": None, "is_public": True, "min_plan": "professional"},
    {"id": "viber", "name": "Viber", "description": "Connect Viber Bot for Eastern Europe and Asia.", "category": "messaging", "auth_type": "api_key", "adapter_class": None, "is_public": True, "min_plan": "professional"},
    {"id": "google_business", "name": "Google Business Messages", "description": "Respond to customers from Google Search and Maps.", "category": "messaging", "auth_type": "api_key", "adapter_class": None, "is_public": True, "min_plan": "professional"},
    {"id": "line", "name": "LINE", "description": "Connect LINE Messaging API for Japan, Thailand, Taiwan.", "category": "messaging", "auth_type": "api_key", "adapter_class": None, "is_public": True, "min_plan": "enterprise"},
    {"id": "wechat", "name": "WeChat", "description": "Connect WeChat Official Account for the Chinese market.", "category": "messaging", "auth_type": "api_key", "adapter_class": None, "is_public": True, "min_plan": "enterprise"},
    # ── Fitness / Members ────────────────────────────────────────────────
    {"id": "magicline", "name": "Magicline", "description": "Sync members and check-ins from Magicline.", "category": "fitness", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.magicline_adapter.MagiclineAdapter", "is_public": True, "min_plan": "professional"},
    # ── E-Commerce ───────────────────────────────────────────────────────
    {"id": "shopify", "name": "Shopify", "description": "Sync customers from Shopify store.", "category": "ecommerce", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.shopify_adapter.ShopifyAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "woocommerce", "name": "WooCommerce", "description": "Sync customers from WooCommerce store.", "category": "ecommerce", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.woocommerce_adapter.WooCommerceAdapter", "is_public": True, "min_plan": "professional"},
    # ── CRM ──────────────────────────────────────────────────────────────
    {"id": "hubspot", "name": "HubSpot", "description": "Sync contacts with HubSpot CRM.", "category": "crm", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.hubspot_adapter.HubSpotAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "salesforce", "name": "Salesforce", "description": "Sync contacts and leads from Salesforce CRM.", "category": "crm", "auth_type": "oauth2", "adapter_class": "app.integrations.adapters.salesforce_adapter.SalesforceAdapter", "is_public": True, "min_plan": "enterprise"},
    # ── Payments ─────────────────────────────────────────────────────────
    {"id": "stripe", "name": "Stripe", "description": "Accept payments and manage subscriptions.", "category": "payment", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.stripe_adapter.StripeAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "paypal", "name": "PayPal", "description": "Accept PayPal payments worldwide.", "category": "payment", "auth_type": "oauth2", "adapter_class": "app.integrations.adapters.paypal_adapter.PayPalAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "mollie", "name": "Mollie", "description": "European payment provider with local payment methods.", "category": "payment", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.mollie_adapter.MollieAdapter", "is_public": True, "min_plan": "professional"},
    # ── Booking ───────────────────────────────────────────────────────────
    {"id": "calendly", "name": "Calendly", "description": "Let customers book appointments and meetings.", "category": "booking", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.calendly_adapter.CalendlyAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "calcom", "name": "Cal.com", "description": "Open-source scheduling infrastructure.", "category": "booking", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.calcom_adapter.CalComAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "acuity", "name": "Acuity Scheduling", "description": "Advanced appointment scheduling with payment integration.", "category": "booking", "auth_type": "basic", "adapter_class": "app.integrations.adapters.acuity_adapter.AcuityAdapter", "is_public": True, "min_plan": "professional"},
    # ── AI & Voice ────────────────────────────────────────────────────────
    {"id": "elevenlabs", "name": "ElevenLabs", "description": "Premium AI voice synthesis with ultra-realistic voices.", "category": "ai_voice", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.elevenlabs_adapter.ElevenLabsAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "openai_tts", "name": "OpenAI TTS", "description": "Text-to-speech powered by OpenAI voice models.", "category": "ai_voice", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.openai_tts_adapter.OpenAITtsAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "openai_whisper", "name": "OpenAI Whisper", "description": "Speech-to-text transcription with high accuracy.", "category": "ai_voice", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.openai_whisper_adapter.OpenAIWhisperAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "deepgram", "name": "Deepgram", "description": "Real-time speech-to-text with streaming support.", "category": "ai_voice", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.deepgram_adapter.DeepgramAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "google_tts", "name": "Google Cloud TTS", "description": "Multi-language text-to-speech with WaveNet voices.", "category": "ai_voice", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.google_tts_adapter.GoogleTtsAdapter", "is_public": True, "min_plan": "professional"},
    {"id": "azure_speech", "name": "Azure Speech", "description": "Enterprise-grade TTS and STT from Microsoft Azure.", "category": "ai_voice", "auth_type": "api_key", "adapter_class": "app.integrations.adapters.azure_speech_adapter.AzureSpeechAdapter", "is_public": True, "min_plan": "enterprise"},
    # ── Analytics ─────────────────────────────────────────────────────────
    {"id": "google_analytics", "name": "Google Analytics", "description": "Track customer interactions and conversion events.", "category": "analytics", "auth_type": "api_key", "adapter_class": None, "is_public": True, "min_plan": "professional"},
    {"id": "mixpanel", "name": "Mixpanel", "description": "Product analytics for customer behavior insights.", "category": "analytics", "auth_type": "api_key", "adapter_class": None, "is_public": True, "min_plan": "professional"},
    # ── Internal (built-in) ───────────────────────────────────────────────
    {"id": "database_crm", "name": "ARIIA Database CRM", "description": "Integrierter Kontakt-Adapter für die ARIIA-Datenbank.", "category": "crm", "auth_type": "none", "adapter_class": "app.integrations.adapters.database_contact_adapter.DatabaseContactAdapter", "is_public": False, "min_plan": "starter"},
    {"id": "manual_crm", "name": "ARIIA CRM", "description": "Integriertes CRM für manuelle Mitgliederverwaltung.", "category": "crm", "auth_type": "none", "adapter_class": "app.integrations.adapters.manual_crm_adapter.ManualCrmAdapter", "is_public": False, "min_plan": "starter"},
    {"id": "knowledge", "name": "ARIIA Knowledge Base", "description": "Integrierte Wissensdatenbank mit Vektorsuche.", "category": "custom", "auth_type": "none", "adapter_class": "app.integrations.adapters.knowledge_adapter.KnowledgeAdapter", "is_public": False, "min_plan": "starter"},
    {"id": "member_memory", "name": "ARIIA Member Memory", "description": "Kontextuelles Gedächtnis für Mitglieder-Interaktionen.", "category": "custom", "auth_type": "none", "adapter_class": "app.integrations.adapters.member_memory_adapter.MemberMemoryAdapter", "is_public": False, "min_plan": "starter"},
]

# Map settings key prefix → integration_id for backfill detection
# e.g. settings key "magicline_api_key" → integration "magicline"
_SETTINGS_TO_INTEGRATION: dict[str, str] = {
    "magicline_api_key": "magicline",
    "telegram_bot_token": "telegram",
    "calendly_api_key": "calendly",
    "shopify_access_token": "shopify",
    "hubspot_access_token": "hubspot",
}


def seed_integration_definitions(db: Session) -> None:
    """Idempotent upsert of all integration_definitions."""
    from app.core.integration_models import IntegrationDefinition

    now = datetime.now(timezone.utc)
    created = updated = 0
    for defn in INTEGRATION_DEFINITIONS:
        existing = db.query(IntegrationDefinition).filter_by(id=defn["id"]).first()
        if existing:
            # Keep fields in sync
            for key, val in defn.items():
                if key != "id" and getattr(existing, key, None) != val:
                    setattr(existing, key, val)
                    updated += 1
            existing.is_active = True
        else:
            db.add(IntegrationDefinition(
                **defn,
                is_active=True,
                version="1.0.0",
                created_at=now,
                updated_at=now,
            ))
            created += 1

    if created or updated:
        db.commit()
    logger.info("platform.seed.integration_definitions", created=created, updated=updated)


def backfill_prompt_settings(db: Session) -> None:
    """Ensure every tenant has studio_name and persona_name in settings.

    Uses Tenant.name as the default studio_name when the setting is absent.
    Safe to call multiple times — only inserts missing rows.
    """
    from app.core.models import Tenant
    from sqlalchemy import text

    tenants = db.query(Tenant).all()
    filled = 0
    for tenant in tenants:
        tid = tenant.id
        for key, default in [
            ("studio_name", tenant.name),
            ("persona_name", "ARIIA"),
        ]:
            existing = db.execute(
                text("SELECT value FROM settings WHERE tenant_id = :tid AND key = :k"),
                {"tid": tid, "k": key},
            ).scalar()
            if not existing:
                db.execute(
                    text("INSERT INTO settings (tenant_id, key, value) VALUES (:tid, :k, :v)"),
                    {"tid": tid, "k": key, "v": default},
                )
                filled += 1

    if filled:
        db.commit()
    logger.info("platform.seed.prompt_settings_backfill", filled=filled)


def backfill_tenant_integrations(db: Session) -> None:
    """Create tenant_integrations rows for tenants that have integrations
    configured in settings but no corresponding row in tenant_integrations.

    Handles:
    - integration_{name}_{tid}_enabled = true  (WhatsApp style)
    - {name}_api_key present                   (Magicline, Calendly, etc.)
    """
    from app.core.integration_models import TenantIntegration
    from app.core.models import Tenant
    from sqlalchemy import text

    now = datetime.now(timezone.utc)
    created = 0

    tenants = db.query(Tenant).all()
    for tenant in tenants:
        tid = tenant.id

        # Collect which integrations are configured for this tenant
        configured: set[str] = set()

        # Pattern 1: integration_{name}_{tid}_enabled = true
        rows = db.execute(
            text("SELECT key FROM settings WHERE tenant_id = :tid AND key LIKE 'integration_%_enabled'"),
            {"tid": tid},
        ).fetchall()
        import re
        pat1 = re.compile(rf"^integration_([a-z_]+?)_(?:\d+_)?enabled$")
        for row in rows:
            m = pat1.match(row[0])
            if m:
                configured.add(m.group(1))

        # Pattern 2: known settings keys that imply an integration
        for settings_key, integration_id in _SETTINGS_TO_INTEGRATION.items():
            val = db.execute(
                text("SELECT value FROM settings WHERE tenant_id = :tid AND key = :key"),
                {"tid": tid, "key": settings_key},
            ).scalar()
            if val:
                configured.add(integration_id)

        for integration_id in configured:
            existing = db.query(TenantIntegration).filter_by(
                tenant_id=tid, integration_id=integration_id
            ).first()
            if not existing:
                db.add(TenantIntegration(
                    tenant_id=tid,
                    integration_id=integration_id,
                    status="enabled",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ))
                created += 1

    if created:
        db.commit()
    logger.info("platform.seed.tenant_integrations_backfill", created=created)
