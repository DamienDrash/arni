# Sprint 2 – Swarm Intelligence (Woche 3–4)

> **Status:** ✅ Abgeschlossen | **Methodik:** BMAD

---

## Tasks

| # | Task | Agent | Beschreibung | Benchmark | Status |
|---|------|-------|-------------|-----------|--------|
| 2.1 | Base Agent Class | @ARCH | Abstrakte Agent-Klasse mit `handle()` Interface | Importierbar, Typen valide | ✅ |
| 2.2 | Swarm Router | @ARCH/@BACKEND | GPT-4o-mini Intent Classifier | Intent → Agent Mapping korrekt | ✅ |
| 2.3 | Routing Table | @BACKEND | Intent Enum + Dispatch Logic | 5 Intents routen fehlerfrei | ✅ |
| 2.4 | Agent Ops | @BACKEND | Magicline Stub, Booking/Schedule | `INTENT_BOOKING` → Ops.handle() | ✅ |
| 2.5 | Agent Sales | @BACKEND | CRM Stub, Retention-Flow | `INTENT_SALES` → Sales.handle() | ✅ |
| 2.6 | Agent Medic | @BACKEND | Disclaimer-Logic, GraphRAG Stub | `INTENT_HEALTH` → Medic.handle() + Disclaimer | ✅ |
| 2.7 | Agent Vision | @BACKEND | Stub (Placeholder für Sprint 5) | `INTENT_CROWD` → Vision.handle() | ✅ |
| 2.8 | Persona Handler | @BACKEND | Smalltalk direkt beantworten | `INTENT_SMALLTALK` → Persona Response | ✅ |
| 2.9 | Ollama Fallback | @BACKEND/@DEVOPS | Local LLM bei Cloud-Ausfall | Fallback in <3s aktiv | ✅ |
| 2.10 | Gateway Integration | @BACKEND | Redis Bus → Router → Agent → Response | E2E Pipeline durchgängig | ✅ |
| 2.11 | Unit Tests Router | @QA | Router-Tests mit Mock-LLM | ≥80% Coverage | ✅ |
| 2.12 | Unit Tests Agents | @QA | Agent-Tests mit Stubs | Alle Agents getestet | ✅ |
| 2.13 | Integration Tests | @QA | E2E Webhook → Router → Agent → Response | Pipeline durchgängig | ✅ |
| 2.14 | @SEC Audit | @SEC | LLM-Prompt-Injection-Tests | Keine Injections möglich | ✅ |
| 2.15 | Docs Update | @DOCS | README + API Docs erweitert | Dokumentation aktuell | ✅ |

## Definition of Done
- [x] Alle 5 Intents routen korrekt zum richtigen Agent
- [x] Medic-Agent IMMER mit Disclaimer
- [x] Ollama-Fallback funktioniert bei simuliertem Cloud-Ausfall
- [x] Tests: ≥30 Tests, ≥80% Coverage auf Swarm-Modul
- [x] Kein PII in Router-/Agent-Logs (DSGVO_BASELINE)

## Risiken
- OpenAI API Rate Limits → Fallback auf Ollama
- Intent-Misclassification → Confidence Threshold + Fallback
- Prompt Injection → @SEC Audit ✅

## Dependencies
- Sprint 1 ✅ (Gateway, Redis Bus, Schemas)
- OpenAI API Key (für Router – kann mit Mock-LLM getestet werden)
- Ollama Installation auf VPS (für Fallback-Tests)

