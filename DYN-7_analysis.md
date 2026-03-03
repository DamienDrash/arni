# DYN-7 Analysis: Schema Finalization & Seed Data

## Current State

### Existing Tables (from migration 002_integration_registry):
- `integration_definitions` - Core table, already created
- `capability_definitions` - Core table, already created  
- `integration_capabilities` - Many-to-many link, already created
- `tenant_integrations` - Per-tenant activation, already created

### Additional columns added (from 2026_03_02_contact_sync_refactoring):
- `last_sync_at`, `last_sync_status`, `last_sync_error`, `sync_direction`, `sync_mode`, `records_synced_total`, `health_status`, `health_checked_at` on `tenant_integrations`

### Model vs Migration Delta:
The SQLAlchemy models in `integration_models.py` match the combined schema from both migrations. No additional columns are needed.

## CONNECTOR_REGISTRY Entries (28 total):

| ID | Name | Category | Auth Type |
|---|---|---|---|
| whatsapp | WhatsApp | messaging | api_key |
| telegram | Telegram | messaging | api_key |
| sms | SMS (Twilio) | messaging | api_key |
| twilio_voice | Twilio Voice | messaging | api_key |
| postmark | Postmark | messaging | api_key |
| smtp_email | E-Mail (SMTP & IMAP) | messaging | basic |
| instagram | Instagram Messenger | messaging | oauth2 |
| facebook | Facebook Messenger | messaging | oauth2 |
| viber | Viber | messaging | api_key |
| google_business | Google Business Messages | messaging | api_key |
| line | LINE | messaging | api_key |
| wechat | WeChat | messaging | api_key |
| magicline | Magicline | members/fitness | api_key |
| shopify | Shopify | members/ecommerce | api_key |
| woocommerce | WooCommerce | members/ecommerce | api_key |
| hubspot | HubSpot | crm | api_key |
| salesforce | Salesforce | crm | oauth2 |
| stripe | Stripe | payments | api_key |
| paypal | PayPal | payments | oauth2 |
| mollie | Mollie | payments | api_key |
| calendly | Calendly | scheduling | api_key |
| calcom | Cal.com | scheduling | api_key |
| acuity | Acuity Scheduling | scheduling | basic |
| elevenlabs | ElevenLabs | ai_voice | api_key |
| openai_tts | OpenAI TTS | ai_voice | api_key |
| openai_whisper | OpenAI Whisper | ai_voice | api_key |
| deepgram | Deepgram | ai_voice | api_key |
| google_tts | Google Cloud TTS | ai_voice | api_key |
| azure_speech | Azure Speech | ai_voice | api_key |
| google_analytics | Google Analytics | analytics | api_key |
| mixpanel | Mixpanel | analytics | api_key |

Plus internal adapters not in CONNECTOR_REGISTRY:
- database_crm (ARIIA CRM) - internal
- knowledge - internal
- member_memory - internal
- manual_crm (ARIIA CRM) - internal

## Plan:
1. Create migration that ensures schema is finalized (idempotent)
2. Add seed data for all CONNECTOR_REGISTRY entries + internal adapters
