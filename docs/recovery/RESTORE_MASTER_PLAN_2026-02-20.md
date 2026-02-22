# ARNI Restore Master Plan (Post-Loss Recovery)
_Datum: 2026-02-20_

## Ziel
Rekonstruktion des Stands unmittelbar vor dem Löschvorfall inklusive Multi-Tenant-Auth, RBAC, Governance-UI, Member-Memory/Prompt-Management, Scheduler und Security-Hardening.

## Quellen (persistent)
- `MEMORY.md`
- `memory/2026-02-20.md`
- `docs/sprints/ROADMAP.md`
- aktueller Code-Stand (`app/`, `frontend/`, `tests/`)

## Soll-Zustand vor Löschpunkt
1. Tenant-Self-Registration + Login (Bearer Token)
2. Rollen: `system_admin`, `tenant_admin`, `tenant_user`
3. RBAC-geschützte Admin/API-Endpunkte
4. User-/Tenant-Verwaltung inkl. Tenant-Zuordnung
5. Audit-Log (Backend + Frontend)
6. Prompt-Editing für `app/prompts/templates/ops/system.j2`
7. Member-Memory Verwaltung (listen/edit/save)
8. Tägliche Member-Memory Analyse (Cron-Settings + Last-Run Status)
9. Integrationskonfiguration (Telegram/WhatsApp/Magicline) mit Secret-Redaction
10. Sidebar/IA konsolidiert

## Delivery-Sprints (Restore)

### Sprint R1 — Identity & Access (P0)
**Scope**
- Modelle: `Tenant`, `UserAccount`, `AuditLog`
- Token-Auth (HMAC Bearer), Passwort-Hashing
- `/auth/register`, `/auth/login`, `/auth/me`
- Seed `system` tenant + system admin

**Akzeptanz**
- Register/Login erfolgreich
- `401` ohne Token auf geschützten Endpunkten
- Rollen werden im Token und Kontext korrekt geführt

**Status**: ✅ umgesetzt

### Sprint R2 — RBAC & Governance APIs (P0)
**Scope**
- `/auth/users` (list/create)
- `/auth/tenants` (list/create)
- `/auth/audit`
- RBAC-Policy in Endpunkten (`require_role`, tenant scoping)

**Akzeptanz**
- System Admin sieht alle Tenants/User
- Tenant Admin sieht nur eigenen Tenant
- Tenant User kann keine privilegierten Mutationen

**Status**: ✅ umgesetzt (inkl. Legacy-Audit-Schema-Fix)

### Sprint R3 — Frontend Auth/Governance (P0)
**Scope**
- Seiten: `/login`, `/register`, `/users`, `/audit`
- Frontend-Token-Handling (`localStorage` + Auth Header)
- Protected Routing + Logout
- Sidebar: Governance-Navigation

**Akzeptanz**
- Unauth Zugriff leitet auf `/login`
- Login setzt Session und lädt geschützte Seiten
- User-Liste zeigt Tenant-Zuordnung

**Status**: ✅ umgesetzt

### Sprint R4 — Prompt & Member Memory (P1)
**Scope**
- API: `GET/POST /admin/prompts/ops-system`
- API: `GET/POST /admin/member-memory/{filename}`, list endpoint
- UI: `/system-prompt`, `/member-memory` (Editor)

**Akzeptanz**
- Prompt editierbar/speicherbar
- Member-Memory-Dateien sichtbar und editierbar

**Status**: ✅ umgesetzt

### Sprint R5 — Daily Member Analyzer (P1)
**Scope**
- Scheduler `member_memory_analyzer.py`
- Cron-Settings + Last-Run Status
- Fusion aus Chat-Signalen + Magicline-Daten in Member-Memory

**Akzeptanz**
- Scheduler läuft im Lifespan-Task
- Last-Run und Status in Settings persistiert

**Status**: ✅ umgesetzt

### Sprint R6 — Legacy-Kompatibilität & Stabilisierung (P1)
**Scope**
- SQLite-Migrationen für Legacy-Tabellen ergänzt
- Audit-Query robust gegen ältere Schemas
- Startup-Pfade + Knowledge-Ordner robust

**Akzeptanz**
- `GET /auth/audit` ohne 500 auch bei Legacy-DB
- keine CWD-bedingten Pfadfehler

**Status**: ✅ umgesetzt

---

## Verifikationsmatrix (zuletzt 2026-02-20)
- `POST /auth/register` -> 200 ✅
- `POST /auth/login` -> 200 ✅
- `GET /auth/me` -> 200 ✅
- `GET /auth/users` -> 200 ✅
- `GET /auth/audit?limit=5` -> 200 ✅ (vorher 500, Legacy-Schema-Fix implementiert)
- `GET /admin/prompts/ops-system` -> 200 ✅
- `GET /admin/member-memory` -> 200 ✅

## Kritische Korrektur heute
- Problem: Legacy `audit_logs` ohne `actor_user_id`/`tenant_id` verursachte `500` auf `/auth/audit`.
- Fix:
  - Migration erweitert (`app/core/db.py`) um fehlende Audit-Spalten.
  - Runtime-DB im Container auf fehlende `tenant_id` korrigiert.
  - `/auth/audit` erfolgreich verifiziert.

## Noch offene Restore-Risiken (gegenüber Premium-Zielbild)
1. Vollständige Multi-Tenant-Datenisolation über alle Domänentabellen ist noch nicht vollständig durchgezogen.
2. Postgres-first Architektur (statt SQLite) ist noch offen.
3. Umfassende RBAC-Enforcement-Tests für alle Admin-Endpunkte können weiter ausgebaut werden.
4. Frontend-Lint im Gesamtprojekt enthält Altlasten in nicht-restorespezifischen Seiten (`/live`).

## Nächste Restore-Schritte
1. R7: Tenant-Isolation-Review über alle Admin-/Chat-/Knowledge-Endpunkte.
2. R8: Migration von SQLite auf Postgres als Standard-Pfad (inkl. Alembic-Migrationskette).
3. R9: RBAC-Testmatrix (system/tenant admin/user) automatisiert in CI.

## Tracking
- [x] R1 Identity & Access
- [x] R2 RBAC & Governance APIs
- [x] R3 Frontend Auth/Governance
- [x] R4 Prompt & Member Memory
- [x] R5 Daily Member Analyzer
- [x] R6 Legacy-Kompatibilität & Stabilisierung
- [ ] R7 Tenant-Isolation Review (deep)
- [ ] R8 Postgres-first Multi-Tenant Migration
- [ ] R9 RBAC CI Testmatrix

## Update 2026-02-20 (Premium Hardening + UX)

### Umgesetzt
1. **RBAC/Tenant-Hardening (P0)**
- `app/gateway/admin.py`: globale Admin-Endpoints sind jetzt `system_admin`-only.
- Ergebnis: Tenant-Admins sehen keine globalen Daten mehr (harter Leak-Stop).
- Verifiziert:
  - `tenant_admin -> GET /admin/settings = 403`
  - `system_admin -> GET /admin/settings = 200`

2. **Postgres-first Vorbereitung (P0)**
- `app/core/db.py`: `DATABASE_URL` unterstützt; SQLite nur noch Fallback.
- Nicht-SQLite Engines laufen mit `pool_pre_ping=True`.
- SQLite-only Runtime-Migrationen laufen nur bei SQLite.
- `docker-compose.yml`: `postgres` Service + `DATABASE_URL` env passthrough.
- `.env.example`: Postgres Defaults ergänzt.
- `pyproject.toml`: `psycopg[binary]` hinzugefügt.

3. **Frontend Auth/BasePath Stabilisierung (P0)**
- `/arni` basePath-safe Auth-Requests (`login/register/users/audit`).
- Legacy token fallback + 401 session reset in `apiFetch`.

4. **Premium UI/UX Upgrade (P1)**
- Neue Sidebar IA: klare Sektionen (`Operations`, `Customers`, `Knowledge`, `System`).
- Quick Actions im Sidebar-Bereich (`Live Monitor`, `Analytics`, `Einstellungen`).
- Premium Branding + visuelles Cleanup.
- Layout-Fonts auf hochwertigere Families umgestellt.
- Globales Background/Look konsolidiert.

### Verifikation
- `pytest -q tests/test_auth_restore.py tests/test_security_hardening.py` -> 4 passed.
- Frontend: `eslint` + `tsc --noEmit` grün.
- API Smoke:
  - `/auth/login` (system_admin) -> 200
  - `/arni/api/auth/login` -> 200
  - RBAC-Guard siehe oben.

### Update 2026-02-20 (Tenant UX + Postgres Cutover)
- Sidebar role-aware gemacht: system-only Bereiche werden für Tenant-Admins ausgeblendet.
- RBAC-Test erweitert: Tenant-Admin bekommt 403 auf `/admin/knowledge` und `/admin/stats`.
- SQLite -> Postgres Migrationsscript hinzugefügt:
  - `scripts/data/migrate_sqlite_to_postgres.py`
  - Unterstützt `--dry-run` und `--reset-target` (Legacy-Schema-kompatibel).
- Datenmigration nach Postgres erfolgreich durchgeführt (7 Kern-Tabellen).
- Laufendes Backend auf Postgres umgestellt via `.env` `DATABASE_URL`.
- Live verifiziert: Login + `/auth/users`, `/admin/settings`, `/admin/knowledge` = 200 als system_admin.

## Update 2026-02-20 (Restore Fortsetzung: Knowledge UX + Telegram Stabilisierung)
- **Knowledge Editor Lesbarkeit final gehärtet**
  - `frontend/components/TiptapEditor.tsx`: eigenes, kontraststarkes Farbschema für Toolbar + Editorfläche.
  - `frontend/app/globals.css`: `.arni-editor` Regeln mit expliziter dunkler Schriftfarbe (`#11142d`) für alle relevanten Rich-Text-Elemente.
  - Ziel: Keine unlesbaren Texte mehr in `/knowledge`, `/member-memory`, `/system-prompt`.
- **Telegram Worker Health nachhaltig gefixt**
  - Root cause: gemeinsamer Image-Healthcheck prüfte `http://localhost:8000/health`, aber der Polling-Worker bietet keinen HTTP-Port.
  - `docker-compose.yml`: eigener `healthcheck` für `arni-telegram` via Python-Check auf `/proc/1/cmdline` (`telegram_polling_worker.py`).
  - Ergebnis: `arni-telegram` läuft jetzt `healthy` statt permanent `unhealthy`.
- **Verifikation**
  - Frontend: `npx tsc --noEmit` ✅
  - Frontend: `npx eslint components/TiptapEditor.tsx --max-warnings=0` ✅
  - Backend-Regression: `.venv/bin/pytest -q tests/test_auth_restore.py tests/test_security_hardening.py` => `4 passed` ✅

## Update 2026-02-20 (R7 Deepening: Tenant/Role Guardrails)
### Umgesetzt
- `app/gateway/auth.py`
  - `audit`-Schema-Erkennung DB-agnostisch gemacht (`inspect(db.get_bind())`) mit sauberem SQLite-Fallback.
  - `register` und `create_tenant`: reservierte Slugs (`system`, `admin`, `api`) werden jetzt mit `422` abgewiesen.
  - `create_user` RBAC/Tenant-Regeln verschärft:
    - `system_admin`-User dürfen nur dem `system`-Tenant zugeordnet sein.
    - Bei Erstellung von `tenant_admin`/`tenant_user` durch `system_admin` ist `tenant_id` jetzt Pflicht.
    - `tenant_user` darf weiterhin keine User anlegen.
- Live-Fix bestätigt:
  - `/auth/audit` war auf Postgres mit `ProgrammingError` fehlerhaft -> nach Fix + Core-Restart wieder `200`.

### Tests erweitert
- `tests/test_auth_restore.py`
  - Neue Fälle für tenant/role constraints bei User-Erstellung.
  - Neuer Fall für reservierten Tenant-Slug.
- Teststatus:
  - `.venv/bin/pytest -q tests/test_auth_restore.py tests/test_security_hardening.py` -> `6 passed`.

### R7 Status
- **Teil 1 abgeschlossen**: Identity-/Governance-Ebene (Auth/User/Tenant/Audit) tenant-sicher gehärtet.
- **Nächster R7-Block**: Datenebene (`chat_sessions`/`chat_messages` tenant scope) und Domain-Queries systematisch tenant-fähig machen.

## Update 2026-02-20 (R7 Data Layer: Tenant Scope in Chat Persistence)
### Umgesetzt
- `app/core/models.py`
  - `chat_sessions.tenant_id` hinzugefügt.
  - `chat_messages.tenant_id` hinzugefügt.
- `app/core/db.py`
  - `run_migrations()` DB-agnostisch gemacht (SQLite + Postgres via Inspector).
  - Idempotente Column-Migrationen erweitert um:
    - `chat_sessions.tenant_id`
    - `chat_messages.tenant_id`
- `app/gateway/persistence.py`
  - Tenant-aware Persistenz eingeführt (`tenant_id` optional in Session-/Message-Methoden).
  - Standard-Tenant-Resolution auf `system` implementiert (Fallback für bestehenden Flow).
  - Legacy-Backcompat für bestehende Sessions ohne tenant_id eingebaut.
  - Stats/History/Reset um tenant-scope-fähige Query-Pfade erweitert.

### Verifikation
- Core Restart + Live-Introspection:
  - `chat_sessions` enthält `tenant_id` ✅
  - `chat_messages` enthält `tenant_id` ✅
  - `audit_logs` enthält `tenant_id` ✅
- API Live:
  - `/health` 200 ✅
  - `/auth/audit` 200 ✅
- Tests:
  - `.venv/bin/pytest -q tests/test_auth_restore.py tests/test_security_hardening.py` -> `6 passed` ✅

### Residual Risk / Next
- Aktuell ist `chat_sessions.user_id` weiterhin global unique.
- Für echte Tenant-Hard-Isolation muss auf `(tenant_id, user_id)` umgestellt werden (Schema + Migrationspfad + Router/Service-Read-Paths).

## Update 2026-02-20 (R7 Data Layer: Composite Session Key Prep)
- `app/core/models.py`: `ChatSession.user_id` nicht mehr als uniques Feld modelliert.
- `app/core/db.py` Migration ergänzt (Postgres):
  - `DROP INDEX IF EXISTS ix_chat_sessions_user_id`
  - `CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id ON chat_sessions(user_id)`
  - `CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_sessions_tenant_user ON chat_sessions(tenant_id, user_id)`
- Live verifiziert über `pg_indexes`:
  - `ix_chat_sessions_user_id` ist non-unique ✅
  - `uq_chat_sessions_tenant_user` ist unique composite ✅
- Regression-Tests weiterhin grün (`6 passed`).

## Update 2026-02-20 (R7 End-to-End Read-Path Tenant Propagation)
### Umgesetzt
- Tenant-Kontext im Messaging-Schema ergänzt:
  - `app/gateway/schemas.py`: `tenant_id` in `InboundMessage` + `OutboundMessage`.
- Gateway-Pipeline tenant-aware gemacht:
  - `app/gateway/main.py`:
    - `_resolve_tenant_id(...)` eingeführt (metadata->int, sonst system-tenant fallback).
    - WhatsApp/Telegram Inbound erhalten `tenant_id`.
    - Alle relevanten `persistence.save_message(...)` Aufrufe geben jetzt `tenant_id` weiter.
    - Verifizierungs-/Session-Reads (`get_or_create_session`) tenant-aware aufgerufen.
    - Outbound-Event übernimmt `tenant_id` aus Inbound.
- Persistence wrapper aktualisiert:
  - `app/gateway/persistence_helpers.py`: `save_inbound_to_db` / `save_outbound_to_db` propagieren `tenant_id`.
- Swarm History-Reads tenant-aware gemacht:
  - `app/swarm/base.py`: `_chat(..., tenant_id=...)` und History-Load mit tenant scope.
  - `app/swarm/router/router.py`:
    - `_classify`, `_has_recent_booking_context`, `_recent_context_for_router` tenant-aware.
  - `app/swarm/agents/{ops,persona,sales,medic}.py`:
    - `_chat` Aufrufe mit `tenant_id=message.tenant_id`.
    - `AgentOps`: Session lookup tenant-aware.
- Admin Chat-Reads tenant-aware vorbereitet:
  - `app/gateway/admin.py`: `get_stats/get_recent_sessions/get_chat_history/reset_chat` mit `tenant_id=user.tenant_id`.

### Verifikation
- Compile aller geänderten Module: ✅
- Tests: `.venv/bin/pytest -q tests/test_auth_restore.py tests/test_security_hardening.py` -> `6 passed` ✅
- Live nach Core-Restart:
  - `/health` -> 200 ✅
  - `/auth/audit` -> 200 ✅

### R7 Status
- **Identity/Governance + Chat Data/Read Propagation**: weitgehend abgeschlossen.
- **Restarbeit für vollständige SaaS-Hard-Isolation**:
  - Tenant-Auflösung je Kanal/Endpoint nicht nur fallback-basiert, sondern aus echter Tenant-Route/Auth ableiten.
  - Domaindaten (`studio_members`, knowledge files, member memories) tenantisiert (statt global/system-only Scope).

## Update 2026-02-20 (R9 Seed: Tenant-Scope Test Coverage erweitert)
- Neue Tests hinzugefügt: `tests/test_persistence_tenant_scope.py`
  - `test_chat_history_is_tenant_scoped_for_same_user_id`
  - `test_recent_sessions_are_tenant_scoped`
- Verifiziert explizit:
  - gleiche externe `user_id` in zwei Tenants bleibt in History/Session-Lookups sauber getrennt.
- Testlauf:
  - `.venv/bin/pytest -q tests/test_persistence_tenant_scope.py tests/test_auth_restore.py tests/test_security_hardening.py`
  - Ergebnis: `8 passed` ✅

## Update 2026-02-20 (Domain Tenantization: StudioMember)
### Umgesetzt
- `StudioMember` tenant-scoped gemacht:
  - `app/core/models.py`: `tenant_id` ergänzt; global unique auf `customer_id` im Modell entfernt.
- Runtime-Migrationen erweitert (`app/core/db.py`):
  - `studio_members.tenant_id` wird idempotent hinzugefügt.
  - Postgres: Backfill `tenant_id` auf `system` für Legacy-Daten.
  - Postgres: global unique auf `customer_id` ersetzt durch composite unique `(tenant_id, customer_id)`.
  - Non-unique Suchindex auf `customer_id` bleibt erhalten.
- Startup-Härtung:
  - `app/gateway/main.py`: explizites `run_migrations()` im Lifespan, damit Migrationsausführung beim Boot garantiert ist.
- Member-Sync/Enrichment tenant-aware:
  - `app/integrations/magicline/members_sync.py`: `sync_members_from_magicline(tenant_id=...)`, Upsert/Delete tenant-scoped.
  - `app/integrations/magicline/member_enrichment.py`: `enrich_member(..., tenant_id)` + `get_member_profile(..., tenant_id)`.
- Admin Member Endpoints tenant-scoped:
  - `app/gateway/admin.py`: `/members*` nutzt `user.tenant_id` für stats/list/detail/enrich/sync.
- Verification matching tenant-scoped:
  - `app/gateway/member_matching.py`: `match_member_by_phone(..., tenant_id)`.
  - `app/gateway/main.py`: Aufrufe im Verifizierungsflow übergeben `message.tenant_id`.
- Ops-Agent member profile lookup tenant-scoped:
  - `app/swarm/agents/ops.py`.

### Verifikation
- DB live verifiziert (Postgres):
  - `studio_members.tenant_id` vorhanden ✅
  - `uq_studio_members_tenant_customer` vorhanden ✅
  - `tenant_id IS NULL` Rows = `0` ✅
- API live:
  - `/admin/members/stats` als system_admin -> `200` ✅
- Tests:
  - `.venv/bin/pytest -q tests/test_persistence_tenant_scope.py tests/test_auth_restore.py tests/test_security_hardening.py`
  - Ergebnis: `8 passed` ✅
