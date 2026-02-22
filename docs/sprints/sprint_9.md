# Sprint 9 – Real-World Readiness
> **Phase 9** | Woche 22–23 | Status: 🟡 Aktiv

## Ziel
ARIIA von Prototyp → Produktionsreif. Alle Mocks entfernt, LLM-Agenten live, E2E getestet.

## Tasks
| # | Task | Status | Owner |
|---|------|--------|-------|
| 9.1 | LLM-Agenten (Persona, Ops, Sales, Medic → GPT-4o-mini) | ✅ | @BACKEND |
| 9.2 | Stub Removal (alle Mocks/Fake-Daten) | ✅ | @BACKEND |
| 9.3 | Bridge Production Mode (`BRIDGE_MODE` via .env) | ✅ | @BACKEND |
| 9.4 | SOUL.md Rewrite (Persona statt Keywords) | ✅ | @PO |
| 9.5 | E2E WhatsApp Test (Nachricht → Antwort) | ✅ | @BACKEND + User |
| 9.6 | Error Handling (Ariia-Style Fallbacks) | ✅ | @BACKEND |
| 9.7 | Telegram Admin-Alerts bei Notfällen | ✅ | @BACKEND |

## Geänderte Dateien
- `app/swarm/base.py` – `_chat()` + `set_llm()` hinzugefügt
- `app/swarm/agents/persona.py` – LLM + SOUL.md System Prompt
- `app/swarm/agents/ops.py` – LLM + Öffnungszeiten
- `app/swarm/agents/sales.py` – LLM + Tarife
- `app/swarm/agents/medic.py` – LLM + Disclaimer
- `app/swarm/router/router.py` – `BaseAgent.set_llm()` Wiring
- `app/vision/processor.py` – Stub → Error
- `app/vision/rtsp.py` – Stub → ConnectionError
- `app/voice/stt.py` – Stub → Error
- `app/voice/pipeline.py` – `is_stub` → `is_offline`
- `app/memory/graph.py` – Docs gereinigt
- `app/integrations/whatsapp_web/index.js` – Production Mode
- `config/settings.py` – Bridge-Felder
- `.env` – Bridge-Config
- `scripts/launch.sh` – Production Launch
- `app/gateway/main.py` – TelegramBot + ARIIA_ERROR_MESSAGES + error handling
- `app/swarm/router/router.py` – Emergency Hard-Route
- `docs/personas/SOUL.md` – Persona-Rewrite
- `docs/sprints/ROADMAP.md` – Phase 9

## Ergebnisse
- ✅ API-Test: Alle 5 Agents antworten via GPT-4o-mini
- ✅ `grep mock/stub/fake` = 0 Treffer im `app/` Verzeichnis
- ✅ YOLOv8 real geladen, faster-whisper installiert
- ✅ Emergency Hard-Route: Notfall-Keywords bypassen LLM-Klassifikation
- ✅ Error Handling: Ariia-Style Messages statt Stack Traces
- ✅ Telegram Alerts: Notfälle + System-Fehler → Admin
