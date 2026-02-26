# ARIIA Tenant Integrations Catalog

## Categories

### 1. Communication (messaging)
| Service | Plan | Feature Key | Notes |
|---------|------|-------------|-------|
| WhatsApp Web (QR) | Starter+ | whatsapp_enabled | Always available, QR-based |
| WhatsApp Business API | Professional+ | whatsapp_enabled + api_access | Meta Cloud API |
| Telegram | Professional+ | telegram_enabled | Bot API |
| Postmark (Email) | Professional+ | email_channel_enabled | Transactional email |
| Twilio (SMS) | Professional+ | sms_enabled | SMS + Voice |
| Twilio (Voice/Phone) | Professional+ | voice_enabled | Inbound/outbound calls |
| Instagram Messenger | Professional+ | instagram_enabled | Meta Graph API |
| Facebook Messenger | Professional+ | facebook_enabled | Meta Graph API |
| Viber | Business+ | - | Viber Bot API |
| Google Business Messages | Business+ | google_business_enabled | Google API |
| LINE | Business+ | - | LINE Messaging API (Asia) |
| WeChat | Enterprise | - | WeChat Official Account (China) |

### 2. Payments & Billing (payments)
| Service | Plan | Feature Key | Notes |
|---------|------|-------------|-------|
| Stripe | Professional+ | platform_integrations | Payment processing |
| PayPal | Business+ | platform_integrations | Alternative payments |
| Mollie | Business+ | platform_integrations | EU-focused payments |

### 3. Scheduling & Booking (scheduling)
| Service | Plan | Feature Key | Notes |
|---------|------|-------------|-------|
| Calendly | Professional+ | platform_integrations | Appointment scheduling |
| Cal.com | Professional+ | platform_integrations | Open-source scheduling |
| Acuity Scheduling | Business+ | platform_integrations | Advanced scheduling |

### 4. AI & Voice (ai_voice)
| Service | Plan | Feature Key | Notes |
|---------|------|-------------|-------|
| ElevenLabs | Business+ (addon) | voice_pipeline addon | Premium TTS |
| OpenAI TTS | Professional+ | voice_enabled | Standard TTS |
| OpenAI Whisper | Professional+ | voice_enabled | STT |
| Google Cloud TTS | Business+ | voice_enabled | Multi-language TTS |
| Azure Speech | Business+ | voice_enabled | Enterprise TTS/STT |
| Deepgram | Business+ (addon) | voice_pipeline addon | Real-time STT |

### 5. Analytics & CRM (analytics)
| Service | Plan | Feature Key | Notes |
|---------|------|-------------|-------|
| Google Analytics | Professional+ | advanced_analytics | Website tracking |
| Mixpanel | Business+ | advanced_analytics | Product analytics |

## Plan Tiers
- **Starter**: WhatsApp Web (QR) only
- **Professional**: Most communication channels, Stripe, Calendly, basic AI voice
- **Business**: All channels, all payments, all scheduling, premium AI voice
- **Enterprise**: Everything + WeChat, custom integrations, on-premise
