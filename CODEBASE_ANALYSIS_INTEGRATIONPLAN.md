# Integrationsplan: Codebase-Analyse → CLAUDE.md

**Stand:** 2026-03-05

Dieses Dokument definiert, wie die Erkenntnisse aus den verbleibenden Analyse-Phasen strukturiert in die CLAUDE.md integriert werden — ohne bestehende Inhalte zu zerstören und ohne Duplikate zu erzeugen.

---

## Prinzipien

1. **Additive Integration**: Bestehende CLAUDE.md-Abschnitte werden erweitert, nicht ersetzt.
2. **Verifikation vor Eintrag**: Jeder Satz in CLAUDE.md muss durch konkreten Code belegt sein. Keine Vermutungen.
3. **Präzise Verlinkung**: Neue Erkenntnisse referenzieren Datei + Zeilennummer wo sinnvoll.
4. **Kein Rauschen**: Erkenntnisse die für tägliche Entwicklungsarbeit irrelevant sind, kommen nicht in CLAUDE.md (sondern optional in eigene Doku-Dateien).

---

## Phase 1 → CLAUDE.md: Schema & Migrations

**Zieldatei:** `CLAUDE.md`, Abschnitt `### Database` (bereits vorhanden)

**Zu ergänzen:**
```markdown
### Schema-Evolution (Alembic)

Migrationsreihenfolge und kritische Änderungen:
- `4f31e5c56744` – Initial Schema
- `42f8a7fcb1f9` – Schema Backfill + Default-1-Removal
- `2026_02_22` – RLS Policies aktiviert
- `2026_02_24` – All-Features Batch
- `2026_02_25` – Stripe Integration
- `2026_02_26` – Campaigns System + LLM Providers
- `2026_03_01` – Contacts Refactoring
- `2026_03_02` – AI Config, Campaign Phases 1–4, Auth Refactoring, Billing v2
- `2026_03_03` – DYN-7, Notion, Merge-Head

Idempotente Inline-Migrationen (laufen bei jedem Start via `run_migrations()`):
[Zu befüllen nach Phase-1-Analyse]

Bekannter Tech-Debt:
[Zu befüllen nach Phase-1-Analyse]
```

---

## Phase 2 → CLAUDE.md: Test-Abdeckung

**Zieldatei:** `CLAUDE.md`, neuer Abschnitt `## Testing`

**Struktur nach Integration:**
```markdown
## Testing

### Abdeckung (Stand: 2026-03-05)
- CI-Threshold: 50% (pyproject.toml `--cov-fail-under=50`)
- Gut abgedeckt: [Zu befüllen]
- Lücken: [Zu befüllen]

### Test-Patterns
- Alle Tests in `tests/` erben implizit `conftest.py`-Fixtures
- `mock_redis_bus`: Autouse-Fixture, mockt RedisBus für alle Tests
- `seed_system_tenant`: Autouse-Fixture, erstellt Default-Tenant
- SQLite-Fallback: Automatisch wenn `ENVIRONMENT=testing`

### Eval-Tests (LLM-Qualität)
- `tests/evals/test_faithfulness.py` – LLM-Response-Qualität
- `tests/golden_dataset.json` – Referenz-Datensatz
- Ausführung: `pytest tests/evals/ -v` (separat, nicht im CI)

### Load Tests
- `tests/locustfile.py` – Ausführung: `locust -f tests/locustfile.py`
- Ignoriert im Standard-CI: `--ignore=tests/locustfile.py`
```

---

## Phase 3 → CLAUDE.md: Security & Resilience

**Zieldatei:** `CLAUDE.md`, neuer Unterabschnitt unter `## Engineering Rules`

**Struktur nach Integration:**
```markdown
### Security Details

**Rate Limiting** (`app/core/security.py`):
- [Zu befüllen: IP-Limits, Tenant-Limits, Whitelist-Pfade]
- Endpunkte: Webhook-Pfade primär, konfigurierbar

**Circuit Breaker** (`app/core/resilience.py`):
- [Zu befüllen: Threshold, Half-Open-Logik, betroffene Integrations]
- Redis-Key: `t{id}:circuit_breaker:{integration}`

**LLM Guardrails** (`app/core/guardrails.py`):
- [Zu befüllen: Was wird geblockt, wie wird PII erkannt]

**MFA** (`app/core/mfa.py`):
- [Zu befüllen: TOTP-Bibliothek, Backup-Code-Mechanismus]
```

---

## Phase 4 → CLAUDE.md: Platform API

**Zieldatei:** `CLAUDE.md`, neuer Abschnitt `## Admin & Platform API`

**Struktur nach Integration:**
```markdown
## Admin & Platform API

### Admin-Endpunkte (app/gateway/admin.py)
[Zu befüllen: vollständige Endpunkt-Liste]

### Platform APIs (app/platform/api/)
| Modul | Prefix | Zweck |
|-------|--------|-------|
| `public_api.py` | `/api/v1/` | Öffentliche REST API für externe Integrationen |
| `tenant_portal.py` | [Zu befüllen] | Self-Service Portal |
| `marketplace.py` | [Zu befüllen] | Integrations-Marketplace |
| `analytics.py` | [Zu befüllen] | Platform-weite Analytics |

### Ghost Mode v2 (app/platform/ghost_mode_v2.py)
[Zu befüllen: WebSocket-Protokoll, Human-Handoff-Flow]
```

**Außerdem:** Erkenntnisse aus `.antigravity/team/` in neuen Abschnitt `## Team-Konventionen`:
```markdown
## Team-Konventionen (.antigravity/team/)

[Zu befüllen aus: FRONTEND.md, DEVOPS.md, QA.md, SEC.md, PO.md, UX.md, DOCS.md]
```

---

## Phase 5 → CLAUDE.md: Business Logic

**Zieldatei:** `CLAUDE.md`, Abschnitte `### Contacts v2 API` und `### Billing` erweitern

**Zu ergänzen im Contacts-Abschnitt:**
```markdown
**Duplikat-Erkennung** (`app/contacts/conflict_resolver.py`):
- [Zu befüllen: Algorithmus (Fuzzy-Match? Exakt?), Felder die verglichen werden]
- [Zu befüllen: Merge-Strategie bei Konflikten]

**Sync-Architektur** (`app/contacts/sync_core.py`):
- [Zu befüllen: Wie unterscheidet sich Magicline-Sync von Shopify/HubSpot-Sync?]
```

**Zu ergänzen im Billing-Abschnitt:**
```markdown
**Downgrade-Verhalten** (`app/billing/subscription_service.py`):
- [Zu befüllen: Was passiert mit Daten über Plan-Limit bei Downgrade?]

**v1 vs. v2 Feature-Gates**:
- `app/core/feature_gates.py` (v1): Verwendet von SwarmRouter und Webhooks
- `app/billing/gating_service.py` (v2): [Zu befüllen: Unterschied, Koexistenz]
```

---

## Nicht in CLAUDE.md (separate Dateien)

Erkenntnisse, die zu detailliert für CLAUDE.md sind, kommen in eigene Dateien:

| Erkenntnis | Zieldatei |
|------------|-----------|
| Vollständige Admin-API-Referenz | `docs/api/ADMIN_API.md` (neu) |
| Alembic-Migrations-Log | `docs/SCHEMA_HISTORY.md` (neu) |
| Test-Coverage-Report | `docs/TEST_COVERAGE.md` (neu) |
| Team-Persona-Zusammenfassung | `.antigravity/SUMMARY.md` (neu) |

---

## Qualitätssicherung

Nach jeder Phase wird geprüft:
- [ ] Kein Satz in CLAUDE.md ist unbelegt (Datei-Referenz vorhanden)
- [ ] Keine Duplikate zwischen altem und neuem Inhalt
- [ ] Neue Abschnitte folgen dem bestehenden Stil (Tabellen statt Prosa wo möglich)
- [ ] CLAUDE.md bleibt unter 300 Zeilen (aktuell: ~175 Zeilen, Puffer vorhanden)
