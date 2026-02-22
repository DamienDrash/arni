# ARNI v1.4 – Roadmap & Sprint Plan

> **Projekt:** ARNI – Living System Agent für GetImpulse Berlin
> **Version:** 1.4  |  **Start:** 2026-02-14  |  **Methodik:** BMAD + 2-Wochen-Sprints

---

## Phasenübersicht

| Phase | Name | Zeitraum | Status |
|-------|------|----------|--------|
| 1 | Foundation & Scaffolding | Sprint 1 (W1–W2) | ✅ Abgeschlossen |
| 2 | Swarm Intelligence | Sprint 2 (W3–W4) | ✅ Abgeschlossen |
| 3 | Communication Layer | Sprint 3 (W5–W6) | ✅ Abgeschlossen |
| 4 | Memory & Knowledge | Sprint 4 (W7–W8) | ✅ Abgeschlossen |
| 5 | Physical Intelligence | Sprint 5a–5b (W9–W12) | ✅ Abgeschlossen |
| 6 | Self-Improvement | Sprint 6a–6b (W13–W16) | ✅ Abgeschlossen |
| 7 | Hardening & Launch | Sprint 7a–7b (W17–W20) | ✅ Abgeschlossen |
| 8 | WhatsApp Web Bridge | Sprint 8 (W21) | ✅ Abgeschlossen |
| 9 | Real-World Readiness | Sprint 9 (W22–W23) | 🟡 Aktiv |

---

## Phase 1 – Foundation & Scaffolding
**Sprint 1 (Woche 1–2)**
- Projektstruktur & Ordnerhierarchie
- Hybrid Gateway (FastAPI + Health Endpoint)
- Redis Pub/Sub Integration (Message Bus)
- WebSocket `/ws/control` (Ghost Mode Basis)
- Webhook Ingress `POST /webhook/whatsapp`
- Config-Management (Pydantic Settings, `.env`)
- CI/CD Pipeline Basis (Dockerfile, Pytest Setup)
- 🆕 **@DEVOPS:** Docker Compose Setup (Gateway + Redis Services)
- 🆕 **@SEC:** DSGVO-Baseline (Consent-Schema, PII-Masking Policy)
- 🆕 **@UX:** Arni Persona Audit (SOUL.md → Greeting/Error-Flows)

## Phase 2 – Swarm Intelligence
**Sprint 2 (Woche 3–4)**
- Manager/Router Agent (GPT-4o-mini Intent Classifier)
- Routing Table Implementation (Intent → Agent Dispatch)
- Agent Ops (Scheduler) – Magicline API Anbindung
- Agent Sales (Hunter) – CRM Logik, Retention Flow
- Agent Medic (Coach) – GraphRAG Stub + Disclaimer Logic
- Agent Vision (Eye) – Stub (Placeholder für Phase 5)
- Local Fallback (Ollama/Llama-3) – Reduced Scope Mode

## Phase 3 – Communication Layer
**Sprint 3 (Woche 5–6)**
- WhatsApp Integration (Meta Cloud API Webhooks)
- Baileys Sidecar (Dev/Prototyping via Redis)
- Telegram Bot (Admin Alerts + Ghost Mode Control)
- WhatsApp Native Flows (JSON Forms)
- Message Normalization Pipeline (alle Kanäle → Redis Bus)
- **@UX:** Conversation Flow Templates (Booking, Cancellation, FAQ)
- **@SEC:** PII-Scan Pipeline für Chat-Messages

## Phase 4 – Memory & Knowledge
**Sprint 4 (Woche 7–8)**
- Short-Term Memory (RAM Context, 20 Turns)
- SQLite Session DB (`sessions.db`) – 90 Tage Retention
- Silent Flush (Context Compaction → Fact Extraction)
- Long-Term Knowledge (`data/knowledge/members/{id}.md`)
- GraphRAG Sync (NetworkX/Neo4j Nightly Job)
- GDPR/DSGVO Compliance (PII Masking, Consent Management)
- **@SEC:** Privacy Impact Assessment für Memory Pipeline
- **@SEC:** Consent-Flow Enforcement (Art. 6, Art. 17 Right to Erasure)

---

## Phase 5 – Physical Intelligence (aufgebrochen in 2×2-Wochen-Sprints)

### Sprint 5a – Vision (Woche 9–10)
| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 5a.1 | YOLOv8 Setup | `ultralytics` Lib installieren, Modell laden | Modell lädt in <5s |
| 5a.2 | RTSP Connector | Snapshot-Grabber für CCTV Streams | Bild-Grab von Test-Stream |
| 5a.3 | Vision Processor | Count Persons → `{count, density}` | ≥90% Accuracy auf Testbild |
| 5a.4 | Privacy Engine | RAM-only Processing, 0s Retention | Kein Bild auf Disk gespeichert |
| 5a.5 | Agent Vision Integration | MCP Tool + Swarm Router Anbindung | Intent "Ist es voll?" → Vision Agent |
| 5a.6 | Tests | Pytest mit Mock-RTSP-Stream | 100% Pass |
| 5a.7 | **@DEVOPS:** RTSP Container | Docker-Container für RTSP-Stream-Routing | Stream erreichbar im Container-Netz |
| 5a.8 | **@SEC:** Vision Privacy Audit | 0s Retention Verifizierung, RAM-only Check | Audit Report: kein Bild persistiert |

### Sprint 5b – Voice (Woche 11–12)
| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 5b.1 | Whisper STT | `faster-whisper` (medium) lokal | Transkription <3s für 10s Audio |
| 5b.2 | Audio Ingress | Voice Message Download + Konvertierung | MP3/OGG → WAV Pipeline |
| 5b.3 | ElevenLabs TTS | Turbo v2.5 Integration | Text → Audio Response <2s |
| 5b.4 | Coqui Fallback | Lokaler TTS Fallback (offline) | Funktioniert ohne Internet |
| 5b.5 | Voice Pipeline | End-to-End: Voice In → Text → Swarm → Voice Out | Rundlauf <8s |
| 5b.6 | Tests | Pytest mit Audio-Fixtures | 100% Pass |

---

## Phase 6 – Self-Improvement (aufgebrochen in 2×2-Wochen-Sprints)

### Sprint 6a – ACP Pipeline (Woche 13–14)
| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 6a.1 | ACP Server | WebSocket/TCP Endpunkt für IDE-Anbindung | VS Code verbindet sich |
| 6a.2 | Sandbox Container | Docker Ephemeral Sandbox für Self-Refactoring | Code-Änderung in Container isoliert |
| 6a.3 | File Access Control | Nur `workspace/skills/` + `config/` beschreibbar | `/etc/` Zugriff blockiert |
| 6a.4 | Refactoring Engine | Code-Analyse → Vorschlag → Apply | Automatisches Refactoring läuft |
| 6a.5 | Rollback Mechanism | Git-basierter Rollback bei fehlgeschlagenem Test | Auto-Revert bei Test-Failure |
| 6a.6 | Tests | Sandbox-Escape-Tests, Permission-Tests | 100% Pass, kein Escape möglich |
| 6a.7 | **@DEVOPS:** Sandbox Hardening | Network=none, no-privileged, non-root | Escape-Versuch scheitert |
| 6a.8 | **@SEC:** ACP Security Review | File-Access Audit, Permission Matrix | Sign-off für Self-Improvement |

### Sprint 6b – Soul Evolution (Woche 15–16)
| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 6b.1 | Log Analyzer | Wöchentliche Chat-Log-Analyse | Top-5 Themen identifiziert |
| 6b.2 | Persona Updater | `SOUL.md` Anpassungen vorschlagen | Diff-Vorschlag generiert |
| 6b.3 | Git PR Automation | Auto-PR für Soul-Änderungen | PR erstellt auf Branch |
| 6b.4 | Human Review Gate | Trainer muss PR approven | Kein Auto-Merge |
| 6b.5 | Metrics Dashboard | KPIs: Response Quality, Intent Accuracy | Dashboard zeigt Trends |
| 6b.6 | Tests | End-to-End Soul Evolution Pipeline | 100% Pass |

---

## Phase 7 – Hardening & Launch (aufgebrochen in 2×2-Wochen-Sprints)

### Sprint 7a – Security & Load Tests (Woche 17–18)
| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 7a.1 | Security Audit | Prompt Injection Tests, OWASP Checks | Keine kritischen Findings |
| 7a.2 | Load Testing | k6/Locust: 100 concurrent Users | <500ms p95 Response Time |
| 7a.3 | **@SEC:** DSGVO Final Review | Vollständiger Daten-Audit, Consent-Flows | Compliance-Report signiert |
| 7a.4 | Dependency Audit | `pip-audit`, License Check | Keine CVEs, Licenses OK |
| 7a.5 | **@DEVOPS:** Fallback Testing | Internet-Kill → Ollama Switchover | <3s Failover |
| 7a.6 | Pen Testing | One-Way-Door Bypass-Versuche | Alle Bypasses blockiert |
| 7a.7 | **@UX:** Final Persona Review | Arni-Konsistenz über alle Kanäle | Persona-Audit bestanden |

### Sprint 7b – Launch & Monitoring (Woche 19–20)
| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 7b.1 | Production Deploy | Docker Compose → VPS | System startet fehlerfrei |
| 7b.2 | Monitoring Stack | Sentry + Prometheus + Grafana | Alerts konfiguriert |
| 7b.3 | Runbook | Ops-Dokumentation für Störfälle | Runbook vollständig |
| 7b.4 | Beta Launch | 10 Test-User für 1 Woche | Feedback gesammelt |
| 7b.5 | Bug Bash | Critical Bugs fixen aus Beta | 0 Critical Bugs |
| 7b.6 | Go Live | Öffentlicher Launch + Announcement | System live 🚀 |

---

## Phase 8 – WhatsApp Web Bridge ✅
**Sprint 8 (Woche 21)**

| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 8.1 | Node.js Bridge | Baileys (`@whiskeysockets/baileys`) + Express | QR scanbar, Verbindung stabil |
| 8.2 | Live QR Viewer | `/qr` Endpoint mit HTML Auto-Refresh | QR im Browser scanbar |
| 8.3 | Inbound Pipeline | Message → Meta-kompatibles Payload → Gateway Webhook | `webhook.message_received` in Logs |
| 8.4 | `whatsapp.py` Refactor | Graph API → Bridge (`localhost:3000/send`) | Outbound über Bridge |
| 8.5 | Reply Loop | Webhook → SwarmRouter → Agent → Bridge → WhatsApp | User bekommt Antwort |
| 8.6 | Self-Message | `fromMe`-Filter entfernt | User kann sich selbst schreiben |
| 8.7 | `launch.sh` Update | Node Bridge Autostart | Ein Befehl startet alles |

---

## Phase 9 – Real-World Readiness 🟡
**Sprint 9 (Woche 22–23)**

| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 9.1 | LLM-Agenten | Alle 4 Agents → GPT-4o-mini | Natürliche Antworten statt Keywords |
| 9.2 | Stub Removal | Alle Mocks/Fake-Daten entfernt | `grep stub/fake/mock` = 0 Treffer |
| 9.3 | Bridge Production | Production/Self Mode via `.env` | Kunden-Nachrichten korrekt verarbeitet |
| 9.4 | SOUL.md Rewrite | Keyword-Listen → Persona-Definition | LLM-ready, wartbar |
| 9.5 | E2E Test | WhatsApp Nachricht → Antwort live | Roundtrip < 10s |
| 9.6 | Error Handling | Arni-Style Fehler statt Stack Traces | AGENTS.md §4 erfüllt |
| 9.7 | Telegram Alerts | Notfall → Admin-Telegram-Alert | Alert < 3s nach Erkennung |

---

## Phase 10 – Deep Integration & CRM (Sprint 10)
**Sprint 10 (Woche 24–25)**

| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 10.1 | Magicline Integration | `MagiclineClient` + `.env` Integration | Client authentifiziert sich gegen Sandbox |
| 10.2 | Ops Agent Live | Kursplan, Termine & Check-ins (`appointment_list`, `customer_checkins`) | "Wann ist Massage?", "War ich da?" |
| 10.3 | Sales Agent CRM | Member-Status Check (`customer_contracts`) | Erkennt Premium vs. Basic Member |
| 10.4 | Booking Prototype | `appointment_book` mit Confirmation Flow | Buchung landet im Sandbox-System |

---

## Phase 11 – Voice & Scale (Sprint 11+)
**Sprint 11 (Woche 26+)**

| # | Task | Beschreibung | Acceptance Criteria |
|---|------|-------------|---------------------|
| 11.1 | Voice Messages | Whisper STT + Arni + ElevenLabs TTS | Audio-zu-Audio Konversation |
| 11.2 | Multi-User Scale | Redis-Queue Optimierung für Last | 50 concurrent Users < 1s Latenz |
| 11.3 | Analytics Dashboard | Metriken zu Intent-Verteilung | Dashboard live |

---

## Phase 12 – Enterprise Premium (Sprint 14) ✅
**Goal:** Make Arni "Corporate Ready".
- [x] **Observability:** LangFuse Integration (Tracing/Spans).
- [x] **Evaluation:** DeepEval CI/CD Pipeline (Faithfulness/Relevancy).
- [x] **Guardrails:** Deterministic "Iron Dome" layer (PII/Jailbreak blocking).
- [x] **Search:** Hybrid Retrieval (Vector + Keyword RRF).

## Phase 13 – Production Scale (Sprint 15)
**Goal:** Deploy to Cloud & Scale.
- [ ] **Containerization:** Optimized Dockerfile.
- [ ] **Orchestration:** Kubernetes/Cloud Run Manifests.
- [ ] **Load Balancing:** Nginx/Traefik setup.
