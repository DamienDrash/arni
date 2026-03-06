# Roadmap: Codebase-Analyse – Verbleibende 10%

**Stand:** 2026-03-05
**Ziel:** CLAUDE.md auf vollständige Korrektheit und operativen Mehrwert bringen. Die erste Analyse (90%) hat die Kernarchitektur abgedeckt. Diese Roadmap schließt die verbleibenden Lücken systematisch.

---

## Was wurde bereits analysiert (90%)

| Bereich | Status |
|---------|--------|
| `app/gateway/main.py` – App-Einstieg, Lifespan, Router-Registrierung | ✅ |
| `app/core/models.py` – Vollständiges DB-Schema | ✅ |
| `app/swarm/` – Router, MasterAgent, Sub-Agents | ✅ |
| `app/core/auth.py` – Token, Refresh, RBAC, Impersonation | ✅ |
| `app/core/feature_gates.py` – Plan-Enforcement | ✅ |
| `app/core/redis_keys.py` – Tenant-Schlüssel-Schema | ✅ |
| `app/core/tenant_context.py` – ContextVar-Propagation, RLS | ✅ |
| `app/core/db.py` – PostgreSQL-Pflicht, Pooling, SQLite-Testfallback | ✅ |
| `app/billing/webhook_processor.py` – 9 Stripe Events | ✅ |
| `app/contacts/router.py` – 35+ Endpoints, Segmente, Custom Fields | ✅ |
| `app/ai_config/service.py` + `gateway.py` – Hierarchische LLM-Config | ✅ |
| `app/acp/server.py` – WebSocket Code-Sandbox | ✅ |
| `app/campaign_engine/send_queue.py` – Redis Queue Pattern | ✅ |
| `app/memory_platform/notion_service.py` – Shared OAuth, DB-backed | ✅ |
| `app/integrations/connector_registry.py` – Adapter-Catalog | ✅ |
| `app/prompts/` – Jinja2-Engine, Tenant-Overrides | ✅ |
| `config/settings.py` – Pydantic Settings | ✅ |
| `docker-compose.yml` – 9 Worker-Container, 3 Profile | ✅ |
| `frontend/lib/auth.ts` – sessionStorage, kein localStorage | ✅ |
| `frontend/lib/rbac.ts` – Role-to-Page-Matrix | ✅ |
| `frontend/lib/api.ts` + `api-hooks.ts` – Proxy, CSRF, Auto-Refresh | ✅ |
| `frontend/lib/server/proxy.ts` – Cookie→Bearer, Route-Mapping | ✅ |
| `.antigravity/environment.md` + `gemini.md` – VPS, BMAD-Cycle | ✅ |

---

## Phase 1: Schema & Migrations (Woche 1)

**Ziel:** Vollständige Kenntnis der Datenbank-Evolutionshistorie und offener Tech-Debt.

### Was zu lesen ist
- `alembic/versions/*.py` – alle ~20 Migrations-Dateien
- `alembic/env.py` – Migration-Konfiguration
- `app/core/db.py` `run_migrations()` – idempotente Inline-Migrationen

### Erkenntnisziele
- Welche Tabellen wurden nach dem initialen Schema noch verändert?
- Gibt es `head`-Konflikte oder manuell gepatchte Versionen?
- Welche Spalten-Backfills laufen beim Start via `run_migrations()`?
- Gibt es Tabellen im Code, die noch keine Migration haben?

### Output
- Abschnitt "Schema-Evolutionshistorie" in CLAUDE.md
- Liste offener Tech-Debt (verwaiste Spalten, fehlende Indizes)

---

## Phase 2: Test-Suite-Abdeckung (Woche 1–2)

**Ziel:** Wissen, welche Module gut getestet sind, wo Lücken sind, und ob CI zuverlässig grünt.

### Was zu lesen ist
- `tests/conftest.py` ✅ (bekannt)
- `tests/test_multitenant_isolation.py` – Isolation-Tests
- `tests/test_security_hardening.py` – Security-Tests
- `tests/test_phase1_refactoring.py` bis `test_phase6_refactoring.py` – Refactoring-Abdeckung
- `tests/test_billing_webhook.py` – Stripe-Webhook-Tests
- `tests/evals/test_faithfulness.py` – LLM-Eval-Tests
- `tests/locustfile.py` – Load-Test-Profil

### Erkenntnisziele
- Welche Module haben keine Tests?
- Werden alle Stripe-Events getestet?
- Sind Tenant-Isolation-Tests vollständig?
- Welcher CI-Coverage-Threshold gilt (aktuell: 50% — realistisch?)

### Output
- Abschnitt "Test-Abdeckung" in CLAUDE.md
- `CODEBASE_ANALYSIS_TASKS.md` – konkrete Test-Gap-Tasks

---

## Phase 3: Security & Resilience Module (Woche 2)

**Ziel:** Verstehen, wie Rate-Limiting, Circuit-Breaker und Security-Middleware konkret arbeiten.

### Was zu lesen ist
- `app/core/security.py` – `SecurityMiddleware`, `get_rate_limiter`
- `app/core/resilience.py` – Circuit-Breaker-Implementierung
- `app/core/guardrails.py` – LLM-Guardrails
- `app/core/mfa.py` – TOTP-Implementierung
- `app/core/crypto.py` – Verschlüsselung

### Erkenntnisziele
- Was wird rate-limited (IP, Tenant, User)?
- Welche Integrations haben Circuit-Breaker?
- Wie funktionieren LLM-Guardrails (Blocklists, PII-Checks)?
- Welche TOTP-Bibliothek? Backup-Codes-Mechanismus?

### Output
- Erweiterter Abschnitt "Security" in CLAUDE.md
- Bekannte Rate-Limit-Grenzen dokumentieren

---

## Phase 4: Platform API & Admin-Layer (Woche 2–3)

**Ziel:** Vollständige Kenntnis des Admin-Backends und der Platform-APIs.

### Was zu lesen ist
- `app/gateway/admin.py` – Admin-Router-Endpunkte
- `app/platform/api/public_api.py` – Public REST API
- `app/platform/api/tenant_portal.py` – Self-Service Portal
- `app/platform/api/marketplace.py` – Integrations-Marketplace
- `app/platform/api/analytics.py` – Platform-Analytics
- `app/platform/ghost_mode_v2.py` – Ghost-Mode (Human-Handoff)
- `.antigravity/team/*.md` – FRONTEND, DEVOPS, QA, SEC, PO, UX, DOCS Personas

### Erkenntnisziele
- Welche Admin-Endpunkte existieren (vollständige Liste)?
- Was ist der Unterschied zwischen Platform-Analytics und Tenant-Analytics?
- Wie funktioniert Ghost Mode v2 im Detail?
- Was definieren die Team-Personas als Konventionen?

### Output
- Admin-API-Referenz in CLAUDE.md
- Team-Konventionen-Abschnitt

---

## Phase 5: Contacts & Billing Business Logic (Woche 3)

**Ziel:** Verstehen, wie die Kern-Business-Logik unterhalb der Router-Schicht arbeitet.

### Was zu lesen ist
- `app/contacts/service.py` – Kontakt-Business-Logik
- `app/contacts/repository.py` – DB-Query-Schicht
- `app/contacts/conflict_resolver.py` – Duplikat-Merge-Logik
- `app/billing/subscription_service.py` – Abo-Management
- `app/billing/gating_service.py` – Feature-Gate v2
- `app/billing/metering_service.py` – Nutzungsmessung

### Erkenntnisziele
- Wie werden Duplikate erkannt (Algorithmus)?
- Welche Felder haben Merge-Priorität bei Konflikten?
- Wie wird Abo-Downgrade gehandhabt (Datenerhalt)?
- Überschneidung/Unterschied zwischen `feature_gates.py` (v1) und `gating_service.py` (v2)?

### Output
- Business-Logic-Abschnitt in CLAUDE.md
- Klärung v1 vs. v2 Billing Gate

---

## Gesamtplan

| Phase | Inhalt | Aufwand | Output |
|-------|--------|---------|--------|
| 1 | Migrations & Schema | 2–3h | CLAUDE.md Ergänzung |
| 2 | Test-Suite | 3–4h | CLAUDE.md + Tasks |
| 3 | Security & Resilience | 2–3h | CLAUDE.md Ergänzung |
| 4 | Platform API & Admin | 3–4h | CLAUDE.md + API-Referenz |
| 5 | Business Logic | 2–3h | CLAUDE.md Ergänzung |

**Gesamtaufwand:** ~12–17h
**Ergebnis:** CLAUDE.md ist vollständig, operativ korrekt und als alleinige Wissensquelle für neue Claude-Instanzen nutzbar.
