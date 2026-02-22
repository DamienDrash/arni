# Sprint 3 – Communication Layer (Woche 5–6)

> **Status:** 🟡 Aktiv | **Methodik:** BMAD | **Start:** 2026-02-14

---

## Tasks

| # | Task | Agent | Beschreibung | Benchmark | Status |
|---|------|-------|-------------|-----------|--------|
| 3.1 | WhatsApp Outbound Client | @BACKEND | Meta Cloud API – Nachrichten senden (Text, Template) | Message → WhatsApp User sichtbar | ⬜ |
| 3.2 | Webhook Signature Validation | @BACKEND/@SEC | HMAC-SHA256 Verification für Meta Webhooks | Ungültige Signatur → 403 | ⬜ |
| 3.3 | Telegram Bot Client | @BACKEND | python-telegram-bot – Admin Alerts, Ghost Mode Commands | `/status` → Bot antwortet | ⬜ |
| 3.4 | Telegram Admin Alerts | @BACKEND | Emergency + System Events → Telegram Gruppen-Chat | Medic Emergency → Telegram Alert | ⬜ |
| 3.5 | Message Normalizer | @BACKEND | Multi-Platform Inbound → InboundMessage Schema | WA + Telegram → gleiche Redis Message | ⬜ |
| 3.6 | Outbound Dispatcher | @BACKEND | OutboundMessage → richtigen Kanal senden (WA/TG/WS) | Route nach `platform` Field | ⬜ |
| 3.7 | Conversation Flow Templates | @UX | Booking, Cancellation, FAQ – Nachrichtenfluss definieren | 3 Flows dokumentiert | ⬜ |
| 3.8 | PII-Scan Middleware | @SEC | Redis Bus Middleware filtert PII vor Agent-Dispatch | Telefonnummer → `****` in Logs | ⬜ |
| 3.9 | WhatsApp Native Flows (Stub) | @BACKEND | JSON-Form-Schema für interaktive WA Buttons/Lists | Schema definiert, Stub-Endpoint | ⬜ |
| 3.10 | Unit Tests Integrations | @QA | WhatsApp Client, Telegram Bot, Normalizer Tests | ≥80% Coverage, alle Tests grün | ⬜ |
| 3.11 | Integration Tests E2E | @QA | WA Webhook → Router → Agent → WA Outbound | Pipeline E2E | ⬜ |
| 3.12 | README + API Docs Update | @DOCS | Neue Endpoints + Telegram Setup dokumentieren | Docs aktuell | ⬜ |

## Definition of Done
- [ ] WhatsApp Outbound funktioniert (Text-Nachrichten)
- [ ] Telegram Bot antwortet auf Admin-Commands
- [ ] Emergency Alerts → Telegram Gruppe
- [ ] Multi-Platform Normalization (WA + TG → gleiche Pipeline)
- [ ] PII-Scan filtert sensible Daten vor Logging
- [ ] Tests: ≥80% Coverage, alle Tests grün
- [ ] Kein PII in Logs (DSGVO_BASELINE)

## Risiken
- Meta Cloud API Rate Limits → Exponential Backoff
- Telegram Bot Token Rotation → Config über .env
- Baileys (inoffizielle WA-API) → Auf Stub reduziert, erst bei Bedarf in Sprint 4

## Dependencies
- Sprint 1 ✅ (Gateway, Redis Bus, Schemas)
- Sprint 2 ✅ (Swarm Router, Agents)
- Meta Cloud API Credentials (Phone Number ID, Access Token)
- Telegram Bot Token (via @BotFather)
