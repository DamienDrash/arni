"""DYN-7: Finalize Integration Registry schema & seed integration_definitions.

This migration:
  1. Ensures the integration_definitions, capability_definitions,
     integration_capabilities, and tenant_integrations tables have all
     columns defined in the current SQLAlchemy models (idempotent).
  2. Seeds integration_definitions with all entries from the
     CONNECTOR_REGISTRY plus internal adapters (database_crm,
     knowledge, member_memory, manual_crm).

The seed uses INSERT ... ON CONFLICT DO UPDATE so it is safe to run
multiple times (idempotent upsert).

Revision ID: dyn7_integration_seed_001
Revises: auth_refactoring_001
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "dyn7_integration_seed_001"
down_revision: Union[str, None] = "auth_refactoring_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ─── Helper ─────────────────────────────────────────────────────────────────

def _column_exists(table: str, column: str) -> bool:
    """Check whether *column* already exists on *table*."""
    bind = op.get_bind()
    insp = sa_inspect(bind)
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def _table_exists(table: str) -> bool:
    """Check whether *table* already exists."""
    bind = op.get_bind()
    insp = sa_inspect(bind)
    return table in insp.get_table_names()


# ─── Seed Data ──────────────────────────────────────────────────────────────

INTEGRATION_DEFINITIONS = [
    # ── Messaging ───────────────────────────────────────────────────────
    {
        "id": "whatsapp",
        "name": "WhatsApp",
        "description": "Connect WhatsApp Business API via Meta Cloud.",
        "category": "messaging",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.whatsapp_adapter.WhatsAppAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "mode", "label": "Mode", "type": "select", "options": ["qr", "api"]},
                {"key": "phone_number_id", "label": "Phone Number ID", "type": "text", "depends_on": "mode=api"},
                {"key": "access_token", "label": "Access Token", "type": "password", "depends_on": "mode=api"},
                {"key": "verify_token", "label": "Verify Token", "type": "text", "depends_on": "mode=api"},
                {"key": "app_secret", "label": "App Secret", "type": "password", "depends_on": "mode=api"},
            ]
        },
    },
    {
        "id": "telegram",
        "name": "Telegram",
        "description": "Connect Telegram Bot API.",
        "category": "messaging",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.telegram_adapter.TelegramAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "bot_token", "label": "Bot Token", "type": "password"},
                {"key": "admin_chat_id", "label": "Admin Chat ID", "type": "text", "optional": True},
            ]
        },
    },
    {
        "id": "sms",
        "name": "SMS (Twilio)",
        "description": "Send and receive SMS via Twilio.",
        "category": "messaging",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.sms_voice_adapter.SmsVoiceAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "account_sid", "label": "Account SID", "type": "text"},
                {"key": "auth_token", "label": "Auth Token", "type": "password"},
                {"key": "phone_number", "label": "Twilio Phone Number", "type": "text"},
            ]
        },
    },
    {
        "id": "twilio_voice",
        "name": "Twilio Voice",
        "description": "Inbound and outbound voice calls via Twilio.",
        "category": "messaging",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.sms_voice_adapter.SmsVoiceAdapter",
        "is_public": True,
        "min_plan": "enterprise",
        "config_schema": {
            "fields": [
                {"key": "account_sid", "label": "Account SID", "type": "text"},
                {"key": "auth_token", "label": "Auth Token", "type": "password"},
                {"key": "phone_number", "label": "Voice Phone Number", "type": "text"},
                {"key": "twiml_app_sid", "label": "TwiML App SID", "type": "text", "optional": True},
            ]
        },
    },
    {
        "id": "postmark",
        "name": "Postmark",
        "description": "Transactional email delivery with high deliverability.",
        "category": "messaging",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.email_adapter.EmailAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "server_token", "label": "Server API Token", "type": "password"},
                {"key": "from_email", "label": "Sender Email", "type": "text"},
                {"key": "from_name", "label": "Sender Name", "type": "text", "optional": True},
            ]
        },
    },
    {
        "id": "smtp_email",
        "name": "E-Mail (SMTP & IMAP)",
        "description": "Eigener Mail-Server für Versand (SMTP) und Empfang (IMAP).",
        "category": "messaging",
        "auth_type": "basic",
        "adapter_class": "app.integrations.adapters.email_adapter.EmailAdapter",
        "is_public": True,
        "min_plan": "starter",
        "config_schema": {
            "fields": [
                {"key": "host", "label": "SMTP Host", "type": "text"},
                {"key": "port", "label": "SMTP Port", "type": "text"},
                {"key": "imap_host", "label": "IMAP Host", "type": "text", "optional": True},
                {"key": "imap_port", "label": "IMAP Port", "type": "text", "optional": True},
                {"key": "username", "label": "Benutzername", "type": "text"},
                {"key": "password", "label": "Passwort", "type": "password"},
                {"key": "from_email", "label": "Absender-E-Mail", "type": "text"},
                {"key": "from_name", "label": "Absendername", "type": "text", "optional": True},
            ]
        },
    },
    {
        "id": "instagram",
        "name": "Instagram Messenger",
        "description": "Respond to Instagram DMs via Meta Graph API.",
        "category": "messaging",
        "auth_type": "oauth2",
        "adapter_class": None,
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "page_id", "label": "Instagram Business Account ID", "type": "text"},
                {"key": "access_token", "label": "Page Access Token", "type": "password"},
            ]
        },
    },
    {
        "id": "facebook",
        "name": "Facebook Messenger",
        "description": "Automate Facebook Page messaging.",
        "category": "messaging",
        "auth_type": "oauth2",
        "adapter_class": None,
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "page_id", "label": "Facebook Page ID", "type": "text"},
                {"key": "access_token", "label": "Page Access Token", "type": "password"},
            ]
        },
    },
    {
        "id": "viber",
        "name": "Viber",
        "description": "Connect Viber Bot for Eastern Europe and Asia.",
        "category": "messaging",
        "auth_type": "api_key",
        "adapter_class": None,
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "auth_token", "label": "Bot Auth Token", "type": "password"},
                {"key": "bot_name", "label": "Bot Name", "type": "text"},
                {"key": "bot_avatar", "label": "Bot Avatar URL", "type": "text", "optional": True},
            ]
        },
    },
    {
        "id": "google_business",
        "name": "Google Business Messages",
        "description": "Respond to customers from Google Search and Maps.",
        "category": "messaging",
        "auth_type": "api_key",
        "adapter_class": None,
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "service_account_json", "label": "Service Account JSON", "type": "password"},
                {"key": "agent_id", "label": "Agent ID", "type": "text"},
            ]
        },
    },
    {
        "id": "line",
        "name": "LINE",
        "description": "Connect LINE Messaging API for Japan, Thailand, Taiwan.",
        "category": "messaging",
        "auth_type": "api_key",
        "adapter_class": None,
        "is_public": True,
        "min_plan": "enterprise",
        "config_schema": {
            "fields": [
                {"key": "channel_access_token", "label": "Channel Access Token", "type": "password"},
                {"key": "channel_secret", "label": "Channel Secret", "type": "password"},
            ]
        },
    },
    {
        "id": "wechat",
        "name": "WeChat",
        "description": "Connect WeChat Official Account for the Chinese market.",
        "category": "messaging",
        "auth_type": "api_key",
        "adapter_class": None,
        "is_public": True,
        "min_plan": "enterprise",
        "config_schema": {
            "fields": [
                {"key": "app_id", "label": "App ID", "type": "text"},
                {"key": "app_secret", "label": "App Secret", "type": "password"},
                {"key": "token", "label": "Token", "type": "text"},
                {"key": "encoding_aes_key", "label": "Encoding AES Key", "type": "password"},
            ]
        },
    },

    # ── Members / Fitness / E-Commerce ──────────────────────────────────
    {
        "id": "magicline",
        "name": "Magicline",
        "description": "Sync members and check-ins from Magicline.",
        "category": "fitness",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.magicline_adapter.MagiclineAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "base_url", "label": "API Base URL", "type": "text"},
                {"key": "api_key", "label": "API Key", "type": "password"},
                {"key": "studio_id", "label": "Studio ID", "type": "text", "optional": True},
            ]
        },
    },
    {
        "id": "shopify",
        "name": "Shopify",
        "description": "Sync customers from Shopify store.",
        "category": "ecommerce",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.shopify_adapter.ShopifyAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "domain", "label": "Shop Domain", "type": "text", "placeholder": "shop.myshopify.com"},
                {"key": "access_token", "label": "Admin API Token", "type": "password"},
            ]
        },
    },
    {
        "id": "woocommerce",
        "name": "WooCommerce",
        "description": "Sync customers from WooCommerce store.",
        "category": "ecommerce",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.woocommerce_adapter.WooCommerceAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "store_url", "label": "Store URL", "type": "text", "placeholder": "https://yourstore.com"},
                {"key": "consumer_key", "label": "Consumer Key", "type": "text"},
                {"key": "consumer_secret", "label": "Consumer Secret", "type": "password"},
            ]
        },
    },

    # ── CRM ─────────────────────────────────────────────────────────────
    {
        "id": "hubspot",
        "name": "HubSpot",
        "description": "Sync contacts with HubSpot CRM.",
        "category": "crm",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.hubspot_adapter.HubSpotAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "access_token", "label": "Private App Token", "type": "password"},
            ]
        },
    },
    {
        "id": "salesforce",
        "name": "Salesforce",
        "description": "Sync contacts and leads from Salesforce CRM.",
        "category": "crm",
        "auth_type": "oauth2",
        "adapter_class": "app.integrations.adapters.salesforce_adapter.SalesforceAdapter",
        "is_public": True,
        "min_plan": "enterprise",
        "config_schema": {
            "fields": [
                {"key": "instance_url", "label": "Instance URL", "type": "text", "placeholder": "https://yourorg.salesforce.com"},
                {"key": "client_id", "label": "Client ID (Consumer Key)", "type": "text"},
                {"key": "client_secret", "label": "Client Secret", "type": "password"},
                {"key": "refresh_token", "label": "Refresh Token", "type": "password"},
            ]
        },
    },

    # ── Payments & Billing ──────────────────────────────────────────────
    {
        "id": "stripe",
        "name": "Stripe",
        "description": "Accept payments and manage subscriptions.",
        "category": "payment",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.stripe_adapter.StripeAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "publishable_key", "label": "Publishable Key", "type": "text"},
                {"key": "secret_key", "label": "Secret Key", "type": "password"},
                {"key": "webhook_secret", "label": "Webhook Signing Secret", "type": "password", "optional": True},
            ]
        },
    },
    {
        "id": "paypal",
        "name": "PayPal",
        "description": "Accept PayPal payments worldwide.",
        "category": "payment",
        "auth_type": "oauth2",
        "adapter_class": "app.integrations.adapters.paypal_adapter.PayPalAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "client_id", "label": "Client ID", "type": "text"},
                {"key": "client_secret", "label": "Client Secret", "type": "password"},
                {"key": "mode", "label": "Environment", "type": "select", "options": ["sandbox", "live"]},
            ]
        },
    },
    {
        "id": "mollie",
        "name": "Mollie",
        "description": "European payment provider with local payment methods.",
        "category": "payment",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.mollie_adapter.MollieAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "api_key", "label": "API Key", "type": "password"},
            ]
        },
    },

    # ── Scheduling & Booking ────────────────────────────────────────────
    {
        "id": "calendly",
        "name": "Calendly",
        "description": "Let customers book appointments and meetings.",
        "category": "booking",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.calendly_adapter.CalendlyAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "api_key", "label": "Personal Access Token", "type": "password"},
                {"key": "organization_uri", "label": "Organization URI", "type": "text", "optional": True},
            ]
        },
    },
    {
        "id": "calcom",
        "name": "Cal.com",
        "description": "Open-source scheduling infrastructure.",
        "category": "booking",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.calcom_adapter.CalComAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "api_key", "label": "API Key", "type": "password"},
                {"key": "base_url", "label": "Base URL", "type": "text", "optional": True},
            ]
        },
    },
    {
        "id": "acuity",
        "name": "Acuity Scheduling",
        "description": "Advanced appointment scheduling with payment integration.",
        "category": "booking",
        "auth_type": "basic",
        "adapter_class": "app.integrations.adapters.acuity_adapter.AcuityAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "user_id", "label": "User ID", "type": "text"},
                {"key": "api_key", "label": "API Key", "type": "password"},
            ]
        },
    },

    # ── AI & Voice ──────────────────────────────────────────────────────
    {
        "id": "elevenlabs",
        "name": "ElevenLabs",
        "description": "Premium AI voice synthesis with ultra-realistic voices.",
        "category": "ai_voice",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.elevenlabs_adapter.ElevenLabsAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "api_key", "label": "API Key", "type": "password"},
                {"key": "voice_id", "label": "Default Voice ID", "type": "text", "optional": True},
                {"key": "model_id", "label": "Model", "type": "select",
                 "options": ["eleven_multilingual_v2", "eleven_turbo_v2", "eleven_monolingual_v1"]},
            ]
        },
    },
    {
        "id": "openai_tts",
        "name": "OpenAI TTS",
        "description": "Text-to-speech powered by OpenAI voice models.",
        "category": "ai_voice",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.openai_tts_adapter.OpenAITtsAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "api_key", "label": "OpenAI API Key", "type": "password"},
                {"key": "voice", "label": "Default Voice", "type": "select",
                 "options": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]},
                {"key": "model", "label": "Model", "type": "select", "options": ["tts-1", "tts-1-hd"]},
            ]
        },
    },
    {
        "id": "openai_whisper",
        "name": "OpenAI Whisper",
        "description": "Speech-to-text transcription with high accuracy.",
        "category": "ai_voice",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.openai_whisper_adapter.OpenAIWhisperAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "api_key", "label": "OpenAI API Key", "type": "password"},
                {"key": "model", "label": "Model", "type": "select", "options": ["whisper-1"]},
            ]
        },
    },
    {
        "id": "deepgram",
        "name": "Deepgram",
        "description": "Real-time speech-to-text with streaming support.",
        "category": "ai_voice",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.deepgram_adapter.DeepgramAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "api_key", "label": "API Key", "type": "password"},
                {"key": "model", "label": "Model", "type": "select",
                 "options": ["nova-2", "nova", "enhanced", "base"]},
            ]
        },
    },
    {
        "id": "google_tts",
        "name": "Google Cloud TTS",
        "description": "Multi-language text-to-speech with WaveNet voices.",
        "category": "ai_voice",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.google_tts_adapter.GoogleTtsAdapter",
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "service_account_json", "label": "Service Account JSON", "type": "password"},
                {"key": "language_code", "label": "Default Language", "type": "text"},
            ]
        },
    },
    {
        "id": "azure_speech",
        "name": "Azure Speech",
        "description": "Enterprise-grade TTS and STT from Microsoft Azure.",
        "category": "ai_voice",
        "auth_type": "api_key",
        "adapter_class": "app.integrations.adapters.azure_speech_adapter.AzureSpeechAdapter",
        "is_public": True,
        "min_plan": "enterprise",
        "config_schema": {
            "fields": [
                {"key": "subscription_key", "label": "Subscription Key", "type": "password"},
                {"key": "region", "label": "Service Region", "type": "text"},
            ]
        },
    },

    # ── Analytics ───────────────────────────────────────────────────────
    {
        "id": "google_analytics",
        "name": "Google Analytics",
        "description": "Track customer interactions and conversion events.",
        "category": "analytics",
        "auth_type": "api_key",
        "adapter_class": None,
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "measurement_id", "label": "Measurement ID", "type": "text"},
                {"key": "api_secret", "label": "API Secret", "type": "password"},
            ]
        },
    },
    {
        "id": "mixpanel",
        "name": "Mixpanel",
        "description": "Product analytics for customer behavior insights.",
        "category": "analytics",
        "auth_type": "api_key",
        "adapter_class": None,
        "is_public": True,
        "min_plan": "professional",
        "config_schema": {
            "fields": [
                {"key": "project_token", "label": "Project Token", "type": "text"},
                {"key": "api_secret", "label": "API Secret", "type": "password", "optional": True},
            ]
        },
    },

    # ── Internal / Built-in Adapters (not in CONNECTOR_REGISTRY) ───────
    {
        "id": "database_crm",
        "name": "ARIIA Database CRM",
        "description": "Integrierter Kontakt-Adapter für die ARIIA-Datenbank. Ermöglicht direkten Zugriff auf die lokale Kontaktverwaltung.",
        "category": "crm",
        "auth_type": "none",
        "adapter_class": "app.integrations.adapters.database_contact_adapter.DatabaseContactAdapter",
        "is_public": False,
        "min_plan": "starter",
        "config_schema": None,
    },
    {
        "id": "manual_crm",
        "name": "ARIIA CRM",
        "description": "Integriertes CRM für manuelle Mitgliederverwaltung. Keine externe API erforderlich – verwaltet Kontakte direkt in der ARIIA-Datenbank.",
        "category": "crm",
        "auth_type": "none",
        "adapter_class": "app.integrations.adapters.manual_crm_adapter.ManualCrmAdapter",
        "is_public": False,
        "min_plan": "starter",
        "config_schema": None,
    },
    {
        "id": "knowledge",
        "name": "ARIIA Knowledge Base",
        "description": "Integrierte Wissensdatenbank mit Vektorsuche für FAQ, Dokumente und Unternehmens-Know-how.",
        "category": "custom",
        "auth_type": "none",
        "adapter_class": "app.integrations.adapters.knowledge_adapter.KnowledgeAdapter",
        "is_public": False,
        "min_plan": "starter",
        "config_schema": None,
    },
    {
        "id": "member_memory",
        "name": "ARIIA Member Memory",
        "description": "Kontextuelles Gedächtnis für Mitglieder-Interaktionen. Speichert Zusammenfassungen und Verlauf für personalisierte Agenten-Antworten.",
        "category": "custom",
        "auth_type": "none",
        "adapter_class": "app.integrations.adapters.member_memory_adapter.MemberMemoryAdapter",
        "is_public": False,
        "min_plan": "starter",
        "config_schema": None,
    },
]


def upgrade() -> None:
    # ── Step 1: Ensure schema is complete ───────────────────────────────
    # The tables were created in 002_integration_registry.
    # The sync columns were added in 2026_03_02_contact_sync_refactoring.
    # Here we only add columns that might be missing if migrations ran
    # out of order.  Each add is guarded by _column_exists.

    if _table_exists("integration_definitions"):
        for col_name, col_type, default in [
            ("logo_url", sa.Text(), None),
            ("skill_file", sa.String(255), None),
            ("is_active", sa.Boolean(), "true"),
            ("min_plan", sa.String(32), "'professional'"),
            ("version", sa.String(16), "'1.0.0'"),
        ]:
            if not _column_exists("integration_definitions", col_name):
                kw = {}
                if default is not None:
                    kw["server_default"] = sa.text(default)
                else:
                    kw["nullable"] = True
                op.add_column("integration_definitions", sa.Column(col_name, col_type, **kw))

    if _table_exists("tenant_integrations"):
        for col_name, col_type, default in [
            ("last_sync_at", sa.DateTime(), None),
            ("last_sync_status", sa.String(16), "idle"),
            ("last_sync_error", sa.Text(), None),
            ("sync_direction", sa.String(16), "inbound"),
            ("sync_mode", sa.String(16), "full"),
            ("records_synced_total", sa.Integer(), "0"),
            ("health_status", sa.String(16), "unknown"),
            ("health_checked_at", sa.DateTime(), None),
        ]:
            if not _column_exists("tenant_integrations", col_name):
                kw = {}
                if default is not None:
                    kw["server_default"] = default
                else:
                    kw["nullable"] = True
                op.add_column("tenant_integrations", sa.Column(col_name, col_type, **kw))

    # ── Step 2: Seed integration_definitions ────────────────────────────
    # Use raw SQL with ON CONFLICT for idempotent upsert.
    import json

    for defn in INTEGRATION_DEFINITIONS:
        config_json = json.dumps(defn["config_schema"]) if defn["config_schema"] else "NULL"
        adapter_class = f"'{defn['adapter_class']}'" if defn["adapter_class"] else "NULL"
        is_public = "true" if defn["is_public"] else "false"

        op.execute(sa.text(f"""
            INSERT INTO integration_definitions
                (id, name, description, category, auth_type, adapter_class,
                 config_schema, is_public, is_active, min_plan, version,
                 created_at, updated_at)
            VALUES
                (:id, :name, :description, :category, :auth_type, :adapter_class,
                 :config_schema::jsonb, :is_public, true, :min_plan, '1.0.0',
                 NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                category = EXCLUDED.category,
                auth_type = EXCLUDED.auth_type,
                adapter_class = EXCLUDED.adapter_class,
                config_schema = EXCLUDED.config_schema,
                is_public = EXCLUDED.is_public,
                min_plan = EXCLUDED.min_plan,
                updated_at = NOW()
        """).bindparams(
            id=defn["id"],
            name=defn["name"],
            description=defn["description"],
            category=defn["category"],
            auth_type=defn["auth_type"],
            adapter_class=defn["adapter_class"],
            config_schema=json.dumps(defn["config_schema"]) if defn["config_schema"] else None,
            is_public=defn["is_public"],
            min_plan=defn.get("min_plan", "professional"),
        ))


def downgrade() -> None:
    # Remove seeded rows (only the ones we inserted).
    ids = [d["id"] for d in INTEGRATION_DEFINITIONS]
    placeholders = ", ".join(f"'{i}'" for i in ids)
    op.execute(f"DELETE FROM integration_definitions WHERE id IN ({placeholders})")
