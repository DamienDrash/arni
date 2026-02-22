# Sprint 8 – WhatsApp Web Bridge & Reply Loop

> **Status:** 🟡 Aktiv | **Methodik:** BMAD | **Start:** 2026-02-15

---

## 8a – WhatsApp Web Bridge (Node.js/Baileys)

| # | Task | Agent | Beschreibung | Status |
|---|------|-------|-------------|--------|
| 8a.1 | Node.js Projekt | @BACKEND | `package.json`, npm install (`@whiskeysockets/baileys`, Express) | ✅ |
| 8a.2 | Bridge Logic | @BACKEND | `index.js` – Baileys Connect, QR, Message Forward | ✅ |
| 8a.3 | Live QR Viewer | @BACKEND | `/qr` Endpoint mit Auto-Refresh (HTML + `qrcode` npm) | ✅ |
| 8a.4 | QR Scan | @QA | Manueller Test: QR scannen, Verbindung herstellen | ✅ |
| 8a.5 | Inbound Test | @QA | Nachricht senden → Bridge → Gateway → Redis | ✅ |

## 8b – Integration & Reply Loop

| # | Task | Agent | Beschreibung | Status |
|---|------|-------|-------------|--------|
| 8b.1 | `whatsapp.py` Refactor | @BACKEND | Graph API → Bridge (`localhost:3000/send`) | ✅ |
| 8b.2 | `launch.sh` Update | @DEVOPS | Node-Bridge im Hintergrund starten | ✅ |
| 8b.3 | HMAC Bypass | @SEC | Signaturprüfung deaktiviert (Bridge signiert nicht) | ✅ |
| 8b.4 | Reply Loop | @BACKEND | Webhook → SwarmRouter → Agent → Bridge `/send` → WhatsApp | ✅ |
| 8b.5 | Self-Message | @BACKEND | `fromMe`-Filter entfernt (User kann sich selbst schreiben) | ✅ |
| 8b.6 | E2E Reply Test | @QA | Nachricht senden → ARIIA antwortet via WhatsApp | 🟡 |

## Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `app/integrations/whatsapp_web/index.js` | **NEU** – Baileys Bridge + Express API + Live QR |
| `app/integrations/whatsapp_web/package.json` | **NEU** – Node.js Dependencies |
| `app/integrations/whatsapp.py` | `_send()` → Bridge statt Graph API, HMAC bypass |
| `app/gateway/main.py` | `process_and_reply()` – Inline Routing + Bridge Reply |
| `scripts/launch.sh` | Node Bridge Autostart |

## Definition of Done
- [x] WhatsApp verbindet via QR Code
- [x] Inbound Messages erreichen ARIIA Gateway
- [x] Reply Loop verdrahtet (Webhook → Router → Agent → Bridge)
- [ ] E2E: User sendet Nachricht → ARIIA antwortet via WhatsApp
