"""app/integrations/connector_registry.py — Connector Metadata Registry (PR 3).

Central definition of all integrations.
"""
from typing import List, Dict, Any

CONNECTOR_REGISTRY = {
    # ══════════════════════════════════════════════════════════════════════════
    # MESSAGING
    # ══════════════════════════════════════════════════════════════════════════
    "whatsapp": {
        "name": "WhatsApp",
        "category": "messaging",
        "description": "Connect WhatsApp Business API via Meta Cloud.",
        "fields": [
            {"key": "mode", "label": "Mode", "type": "select", "options": ["qr", "api"]},
            {"key": "phone_number_id", "label": "Phone Number ID", "type": "text", "depends_on": "mode=api"},
            {"key": "access_token", "label": "Access Token", "type": "password", "depends_on": "mode=api"},
            {"key": "verify_token", "label": "Verify Token", "type": "text", "depends_on": "mode=api"},
            {"key": "app_secret", "label": "App Secret", "type": "password", "depends_on": "mode=api"},
        ],
        "setup_doc": "whatsapp.md",
        "icon": "whatsapp",
    },
    "telegram": {
        "name": "Telegram",
        "category": "messaging",
        "description": "Connect Telegram Bot API.",
        "fields": [
            {"key": "bot_token", "label": "Bot Token", "type": "password"},
            {"key": "admin_chat_id", "label": "Admin Chat ID", "type": "text", "optional": True},
        ],
        "setup_doc": "telegram.md",
        "icon": "telegram",
    },
    "sms": {
        "name": "SMS (Twilio)",
        "category": "messaging",
        "description": "Send and receive SMS via Twilio.",
        "fields": [
            {"key": "account_sid", "label": "Account SID", "type": "text"},
            {"key": "auth_token", "label": "Auth Token", "type": "password"},
            {"key": "phone_number", "label": "Twilio Phone Number", "type": "text"},
        ],
        "setup_doc": "sms.md",
        "icon": "message-circle",
    },
    "twilio_voice": {
        "name": "Twilio Voice",
        "category": "messaging",
        "description": "Inbound and outbound voice calls via Twilio.",
        "fields": [
            {"key": "account_sid", "label": "Account SID", "type": "text"},
            {"key": "auth_token", "label": "Auth Token", "type": "password"},
            {"key": "phone_number", "label": "Voice Phone Number", "type": "text"},
            {"key": "twiml_app_sid", "label": "TwiML App SID", "type": "text", "optional": True},
        ],
        "setup_doc": "twilio_voice.md",
        "icon": "phone",
    },
    "postmark": {
        "name": "Postmark",
        "category": "messaging",
        "description": "Transactional email delivery with high deliverability.",
        "fields": [
            {"key": "server_token", "label": "Server API Token", "type": "password"},
            {"key": "from_email", "label": "Sender Email", "type": "text"},
            {"key": "from_name", "label": "Sender Name", "type": "text", "optional": True},
        ],
        "setup_doc": "postmark.md",
        "icon": "mail",
    },
    "smtp_email": {
        "name": "SMTP E-Mail",
        "category": "messaging",
        "description": "Eigener SMTP-Server für E-Mail-Versand.",
        "fields": [
            {"key": "host", "label": "SMTP Host", "type": "text"},
            {"key": "port", "label": "Port", "type": "text"},
            {"key": "username", "label": "Benutzername", "type": "text"},
            {"key": "password", "label": "Passwort", "type": "password"},
            {"key": "from_email", "label": "Absender-E-Mail", "type": "text"},
            {"key": "from_name", "label": "Absendername", "type": "text", "optional": True},
        ],
        "setup_doc": "smtp.md",
        "icon": "mail",
    },
    "instagram": {
        "name": "Instagram Messenger",
        "category": "messaging",
        "description": "Respond to Instagram DMs via Meta Graph API.",
        "fields": [
            {"key": "page_id", "label": "Instagram Business Account ID", "type": "text"},
            {"key": "access_token", "label": "Page Access Token", "type": "password"},
        ],
        "setup_doc": "instagram.md",
        "icon": "camera",
    },
    "facebook": {
        "name": "Facebook Messenger",
        "category": "messaging",
        "description": "Automate Facebook Page messaging.",
        "fields": [
            {"key": "page_id", "label": "Facebook Page ID", "type": "text"},
            {"key": "access_token", "label": "Page Access Token", "type": "password"},
        ],
        "setup_doc": "facebook.md",
        "icon": "facebook",
    },
    "viber": {
        "name": "Viber",
        "category": "messaging",
        "description": "Connect Viber Bot for Eastern Europe and Asia.",
        "fields": [
            {"key": "auth_token", "label": "Bot Auth Token", "type": "password"},
            {"key": "bot_name", "label": "Bot Name", "type": "text"},
            {"key": "bot_avatar", "label": "Bot Avatar URL", "type": "text", "optional": True},
        ],
        "setup_doc": "viber.md",
        "icon": "message-square",
    },
    "google_business": {
        "name": "Google Business Messages",
        "category": "messaging",
        "description": "Respond to customers from Google Search and Maps.",
        "fields": [
            {"key": "service_account_json", "label": "Service Account JSON", "type": "password"},
            {"key": "agent_id", "label": "Agent ID", "type": "text"},
        ],
        "setup_doc": "google_business.md",
        "icon": "globe",
    },
    "line": {
        "name": "LINE",
        "category": "messaging",
        "description": "Connect LINE Messaging API for Japan, Thailand, Taiwan.",
        "fields": [
            {"key": "channel_access_token", "label": "Channel Access Token", "type": "password"},
            {"key": "channel_secret", "label": "Channel Secret", "type": "password"},
        ],
        "setup_doc": "line.md",
        "icon": "message-square",
    },
    "wechat": {
        "name": "WeChat",
        "category": "messaging",
        "description": "Connect WeChat Official Account for the Chinese market.",
        "fields": [
            {"key": "app_id", "label": "App ID", "type": "text"},
            {"key": "app_secret", "label": "App Secret", "type": "password"},
            {"key": "token", "label": "Token", "type": "text"},
            {"key": "encoding_aes_key", "label": "Encoding AES Key", "type": "password"},
        ],
        "setup_doc": "wechat.md",
        "icon": "message-square",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # MEMBERS
    # ══════════════════════════════════════════════════════════════════════════
    "magicline": {
        "name": "Magicline",
        "category": "members",
        "description": "Sync members and check-ins from Magicline.",
        "fields": [
            {"key": "base_url", "label": "API Base URL", "type": "text"},
            {"key": "api_key", "label": "API Key", "type": "password"},
            {"key": "studio_id", "label": "Studio ID", "type": "text", "optional": True},
        ],
        "setup_doc": "magicline.md",
        "icon": "dumbbell",
    },
    "shopify": {
        "name": "Shopify",
        "category": "members",
        "description": "Sync customers from Shopify store.",
        "fields": [
            {"key": "domain", "label": "Shop Domain", "type": "text", "placeholder": "shop.myshopify.com"},
            {"key": "access_token", "label": "Admin API Token", "type": "password"},
        ],
        "setup_doc": "shopify.md",
        "icon": "shopping-bag",
    },
    "woocommerce": {
        "name": "WooCommerce",
        "category": "members",
        "description": "Sync customers from WooCommerce store.",
        "fields": [
            {"key": "store_url", "label": "Store URL", "type": "text", "placeholder": "https://yourstore.com"},
            {"key": "consumer_key", "label": "Consumer Key", "type": "text"},
            {"key": "consumer_secret", "label": "Consumer Secret", "type": "password"},
        ],
        "setup_doc": "woocommerce.md",
        "icon": "shopping-cart",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CRM
    # ══════════════════════════════════════════════════════════════════════════
    "hubspot": {
        "name": "HubSpot",
        "category": "crm",
        "description": "Sync contacts with HubSpot CRM.",
        "fields": [
            {"key": "access_token", "label": "Private App Token", "type": "password"},
        ],
        "setup_doc": "hubspot.md",
        "icon": "users",
    },
    "salesforce": {
        "name": "Salesforce",
        "category": "crm",
        "description": "Sync contacts and leads from Salesforce CRM.",
        "fields": [
            {"key": "instance_url", "label": "Instance URL", "type": "text", "placeholder": "https://yourorg.salesforce.com"},
            {"key": "client_id", "label": "Client ID (Consumer Key)", "type": "text"},
            {"key": "client_secret", "label": "Client Secret", "type": "password"},
            {"key": "refresh_token", "label": "Refresh Token", "type": "password"},
        ],
        "setup_doc": "salesforce.md",
        "icon": "cloud",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # PAYMENTS & BILLING
    # ══════════════════════════════════════════════════════════════════════════
    "stripe": {
        "name": "Stripe",
        "category": "payments",
        "description": "Accept payments and manage subscriptions.",
        "fields": [
            {"key": "publishable_key", "label": "Publishable Key", "type": "text"},
            {"key": "secret_key", "label": "Secret Key", "type": "password"},
            {"key": "webhook_secret", "label": "Webhook Signing Secret", "type": "password", "optional": True},
        ],
        "setup_doc": "stripe.md",
        "icon": "credit-card",
    },
    "paypal": {
        "name": "PayPal",
        "category": "payments",
        "description": "Accept PayPal payments worldwide.",
        "fields": [
            {"key": "client_id", "label": "Client ID", "type": "text"},
            {"key": "client_secret", "label": "Client Secret", "type": "password"},
            {"key": "mode", "label": "Environment", "type": "select", "options": ["sandbox", "live"]},
        ],
        "setup_doc": "paypal.md",
        "icon": "credit-card",
    },
    "mollie": {
        "name": "Mollie",
        "category": "payments",
        "description": "European payment provider with local payment methods.",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password"},
        ],
        "setup_doc": "mollie.md",
        "icon": "credit-card",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # SCHEDULING & BOOKING
    # ══════════════════════════════════════════════════════════════════════════
    "calendly": {
        "name": "Calendly",
        "category": "scheduling",
        "description": "Let customers book appointments and meetings.",
        "fields": [
            {"key": "api_key", "label": "Personal Access Token", "type": "password"},
            {"key": "organization_uri", "label": "Organization URI", "type": "text", "optional": True},
        ],
        "setup_doc": "calendly.md",
        "icon": "calendar",
    },
    "calcom": {
        "name": "Cal.com",
        "category": "scheduling",
        "description": "Open-source scheduling infrastructure.",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password"},
            {"key": "base_url", "label": "Base URL", "type": "text", "optional": True},
        ],
        "setup_doc": "calcom.md",
        "icon": "calendar",
    },
    "acuity": {
        "name": "Acuity Scheduling",
        "category": "scheduling",
        "description": "Advanced appointment scheduling with payment integration.",
        "fields": [
            {"key": "user_id", "label": "User ID", "type": "text"},
            {"key": "api_key", "label": "API Key", "type": "password"},
        ],
        "setup_doc": "acuity.md",
        "icon": "calendar",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # AI & VOICE
    # ══════════════════════════════════════════════════════════════════════════
    "elevenlabs": {
        "name": "ElevenLabs",
        "category": "ai_voice",
        "description": "Premium AI voice synthesis with ultra-realistic voices.",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password"},
            {"key": "voice_id", "label": "Default Voice ID", "type": "text", "optional": True},
            {"key": "model_id", "label": "Model", "type": "select",
             "options": ["eleven_multilingual_v2", "eleven_turbo_v2", "eleven_monolingual_v1"]},
        ],
        "setup_doc": "elevenlabs.md",
        "icon": "volume-2",
    },
    "openai_tts": {
        "name": "OpenAI TTS",
        "category": "ai_voice",
        "description": "Text-to-speech powered by OpenAI voice models.",
        "fields": [
            {"key": "api_key", "label": "OpenAI API Key", "type": "password"},
            {"key": "voice", "label": "Default Voice", "type": "select",
             "options": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]},
            {"key": "model", "label": "Model", "type": "select", "options": ["tts-1", "tts-1-hd"]},
        ],
        "setup_doc": "openai_tts.md",
        "icon": "volume-2",
    },
    "openai_whisper": {
        "name": "OpenAI Whisper",
        "category": "ai_voice",
        "description": "Speech-to-text transcription with high accuracy.",
        "fields": [
            {"key": "api_key", "label": "OpenAI API Key", "type": "password"},
            {"key": "model", "label": "Model", "type": "select", "options": ["whisper-1"]},
        ],
        "setup_doc": "openai_whisper.md",
        "icon": "mic",
    },
    "deepgram": {
        "name": "Deepgram",
        "category": "ai_voice",
        "description": "Real-time speech-to-text with streaming support.",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password"},
            {"key": "model", "label": "Model", "type": "select",
             "options": ["nova-2", "nova", "enhanced", "base"]},
        ],
        "setup_doc": "deepgram.md",
        "icon": "mic",
    },
    "google_tts": {
        "name": "Google Cloud TTS",
        "category": "ai_voice",
        "description": "Multi-language text-to-speech with WaveNet voices.",
        "fields": [
            {"key": "service_account_json", "label": "Service Account JSON", "type": "password"},
            {"key": "language_code", "label": "Default Language", "type": "text"},
        ],
        "setup_doc": "google_tts.md",
        "icon": "volume-2",
    },
    "azure_speech": {
        "name": "Azure Speech",
        "category": "ai_voice",
        "description": "Enterprise-grade TTS and STT from Microsoft Azure.",
        "fields": [
            {"key": "subscription_key", "label": "Subscription Key", "type": "password"},
            {"key": "region", "label": "Service Region", "type": "text"},
        ],
        "setup_doc": "azure_speech.md",
        "icon": "brain",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ANALYTICS
    # ══════════════════════════════════════════════════════════════════════════
    "google_analytics": {
        "name": "Google Analytics",
        "category": "analytics",
        "description": "Track customer interactions and conversion events.",
        "fields": [
            {"key": "measurement_id", "label": "Measurement ID", "type": "text"},
            {"key": "api_secret", "label": "API Secret", "type": "password"},
        ],
        "setup_doc": "google_analytics.md",
        "icon": "trending-up",
    },
    "mixpanel": {
        "name": "Mixpanel",
        "category": "analytics",
        "description": "Product analytics for customer behavior insights.",
        "fields": [
            {"key": "project_token", "label": "Project Token", "type": "text"},
            {"key": "api_secret", "label": "API Secret", "type": "password", "optional": True},
        ],
        "setup_doc": "mixpanel.md",
        "icon": "bar-chart-3",
    },
}


def get_connector_meta(connector_id: str) -> Dict[str, Any] | None:
    return CONNECTOR_REGISTRY.get(connector_id)


def list_connectors() -> List[Dict[str, Any]]:
    return [{"id": k, **v} for k, v in CONNECTOR_REGISTRY.items()]
