# Refactoring Roadmap: Domain-Driven Modular Monolith

## Epic 1 — Scope & Capability Freeze
- [x] 1.1 Feature Inventory finalisieren (Active / Disabled / Coming Soon / Sunset)
- [x] 1.2 Product Core definieren (Support, Campaigns, Knowledge, WA, Telegram, Calendly, Magicline)
- [x] 1.3 Capability Catalog erstellen (Abhängigkeiten, technische Bezeichner)
- [x] 1.4 Plan/Add-on-Modell festziehen (Base Plans, Add-ons, Tenant Entitlements)
- [x] **Verification Gate**: Scope-Review mit dem Produkt-Owner, keine technischen Änderungen.

## Epic 2 — Architecture Guardrails
- [x] 2.1 Architekturregeln definieren (Kein DB-Direktzugriff, keine Fremdmodell-Imports)
- [x] 2.2 Architekturtests (pytest) einführen zur statischen Code-Überprüfung
- [x] 2.3 Modul-Registry-Schema (deklarativ: Capabilities, Router, Worker, Handler) einführen
- [x] **Verification Gate**: `pytest tests/architecture/` läuft lokal durch (zeigt initial noch X Failures an).

## Epic 3 — Capability Wiring (Runtime Shutdown Layer)
- [/] 3.1 Tenant Entitlement Resolver bauen
- [/] 3.2 Router-Gating (nur aktive Module registrieren HTTP-Endpunkte)
- [/] 3.3 Worker-/Event-Gating (kein Startup von Background-Jobs für inaktive Features)
- [ ] 3.4 Frontend Feature-Gating (Coming Soon, Hidden)
- [ ] **Verification Gate**: Inaktive Subsysteme (API, Worker, UI) werden nicht mehr geladen. Startup-Performance verbessert.

## Epic 4 — Gateway/Edge Refactor
- [ ] 4.1 Thin `edge/app.py` einführen (Middleware, Lifecycle, Router-Registry)
- [ ] 4.2 [gateway/main.py](file:///opt/ariia/production/app/gateway/main.py) entschlacken (try/except-Hölle auflösen, Business Logik entfernen)
- [ ] 4.3 Standardisierte Health Checks einführen (App, DB, Integrationen, Worker)
- [ ] **Verification Gate**: App startet fehlerfrei. E2E Ping-Test läuft erfolgreich. Keine "silent fails" beim Startup mehr.

## Epic 5 — Admin Decomposition
- [ ] 5.1 [gateway/admin.py](file:///opt/ariia/production/app/gateway/admin.py) auflösen: Domain-Router anlegen (Billing, Support, Campaigns etc.)
- [ ] 5.2 Admin Use-Cases sauber in Application Layer verlagern
- [ ] 5.3 Alte [admin.py](file:///opt/ariia/production/app/gateway/admin.py) ausgliedern/löschen
- [ ] **Verification Gate**: Frontend-Admin-Bereich ist zu 100% funktionsfähig.

## Epic 6 — Persistence Refactor
- [ ] 6.1 `shared/db` einführen (Session Factory, UoW, Transaction Helpers)
- [ ] 6.2 Direkte `SessionLocal()` Nutzung inventarisieren (345 Aufrufe)
- [ ] 6.3 Repositories für aktive Module implementieren
- [ ] 6.4 `SessionLocal()` Hotspots in Campaigns, Support, Knowledge ablösen
- [ ] **Verification Gate**: Unit-Tests laufen fehlerfrei mit DI-Sessions, keine direkten DB-Lock-Probleme mehr.

## Epic 7 — Model Ownership Refactor
- [ ] 7.1 Entity-Mapping (Alt -> Neu) definieren
- [ ] 7.2 [core/models.py](file:///opt/ariia/production/app/core/models.py) in Domain-Modelle aufteilen (Tenant, Support, Campaigns, Billing, Knowledge)
- [ ] 7.3 Cross-Domain-Reads über Query-Services abstrahieren anstatt Fremd-Modelle direkt zu importieren
- [ ] **Verification Gate**: Alembic DB-Migration check (keine Schema-Veränderungen, nur Code-Verschiebungen).

## Epic 8 — Active Product Core Migration
- [ ] 8.1 `support` Modul isolieren und aufbauen
- [ ] 8.2 `campaigns` Modul konsolidieren (Opt-In Workflow fokussieren)
- [ ] 8.3 [knowledge](file:///opt/ariia/production/app/gateway/admin.py#728-750) Modul (Wissensbasis + Ingestion) abgrenzen
- [ ] 8.4 [integrations](file:///opt/ariia/production/app/gateway/admin.py#2222-2286) (WA, Telegram, Calendly, Magicline) vom Kern entkoppeln
- [ ] 8.5 `tenant_management` (Plan/Addon Capability) sauber migrieren
- [ ] **Verification Gate**: Alle aktiven Produktfunktionalitäten laufen E2E-getestet durch.

## Epic 9 — Worker Runtime Separation
- [ ] 9.1 Eigene `worker_runtime/main.py` als Startpunkt schaffen (Capability-aware boot)
- [ ] 9.2 Campaign-, Ingestion- und Sync-Worker aus der API-Runtime verschieben
- [ ] 9.3 Idempotency und Failure-Handling standardisieren
- [ ] **Verification Gate**: `docker-compose up` zeigt getrennte API- und Worker-Container, die unabhängig skalieren können.

## Epic 10 — Dormant / Coming Soon Strategy
- [ ] 10.1 Nicht-fokussierte Features vollständig dormant setzen
- [ ] 10.2 Frontend-UI-Status final als "Coming Soon" markieren
- [ ] 10.3 Sunset Backlog für späteren Code-Abriss generieren
- [ ] **Verification Gate**: Gesamte Test-Suite läuft grün inkl. RBAC Vertragtests. Finaler Launch-Check.
