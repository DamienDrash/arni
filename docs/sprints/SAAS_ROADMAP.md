# ARIIA – Multi-Tenant SaaS Finalisierungs-Roadmap
**Erstellt:** 2026-02-21
**Basis:** `docs/audits/SAAS_READINESS_AUDIT_2026-02-21.md`
**Ziel:** ARIIA von einem GetImpulse-spezifischen Einzelmieter-System zu einem vollständigen, produktionsreifen Multi-Tenant SaaS-Produkt transformieren.

---

## Übersicht

```
Sprint S1 (Woche 1–2)  → SECURITY HARDENING & REDIS-NAMESPACING
Sprint S2 (Woche 3–4)  → PROMPT-TEMPLATE-SYSTEM & AGENT-DYNAMISIERUNG
Sprint S3 (Woche 5–6)  → INTEGRATION-CONFIG-COMPLETENESS
Sprint S4 (Woche 7–9)  → BILLING & SUBSCRIPTION ENGINE
Sprint S5 (Woche 10–11) → ONBOARDING & TENANT LIFECYCLE
Sprint S6 (Woche 12–13) → WHITE-LABEL FRONTEND
Sprint S7 (Woche 14)   → AUDIT, HARDENING & LAUNCH-GATES
```

---

## Prioritäts-Prinzip

Jede Aufgabe wird in dieser Reihenfolge bewertet:
1. **Sicherheit vor Funktion** — kein unsicherer Code in Produktion
2. **Blocker zuerst** — nichts das einen Fremd-Tenant kaputtmacht
3. **Tests vor Commit** — jede Änderung hat einen Testfall
4. **Keine Breaking Changes ohne Migration** — bestehende GetImpulse-Daten bleiben intakt

---

## Sprint S1 — Security Hardening & Redis-Namespacing
**Dauer:** Woche 1–2
**Ziel:** Alle Sicherheitslücken schließen, die einen Betrieb mit Fremd-Tenants verbieten.

---

### Task S1.1 — Default-Admin-Passwort-Guard

**Was:** Startup-Fehler erzwingen wenn `SYSTEM_ADMIN_PASSWORD` nicht gesetzt oder schwach ist.

**Warum:** `app/core/auth.py:240` setzt standardmäßig `"password123"`. Beim ersten Start ohne `.env` ist das System mit diesem Passwort erreichbar.

**Dateien:**
- `app/core/auth.py`
- `config/settings.py`

**Durchführung:**
1. In `config/settings.py` ein neues Feld `system_admin_password: str` ohne Default anlegen. Pydantic löst automatisch einen `ValidationError` aus wenn die Umgebungsvariable fehlt.
2. Alternativ: Custom Validator hinzufügen der prüft ob das Passwort ≥ 16 Zeichen, mindestens einen Großbuchstaben, eine Zahl und ein Sonderzeichen enthält.
3. In `app/core/auth.py` bei `ensure_default_tenant_and_admin()` die Prüfung ergänzen: Wenn `SYSTEM_ADMIN_PASSWORD` dem Literal-String `"password123"` entspricht, sofortiger `sys.exit(1)` mit erklärender Fehlermeldung.
4. `.env.example` aktualisieren: `SYSTEM_ADMIN_PASSWORD=` ohne Default, mit Kommentar: `# REQUIRED: Min 16 chars, upper+lower+digit+special`.

**Test:** `tests/test_security_hardening.py` — neuen Testfall: `test_startup_fails_without_admin_password()`.

**Akzeptanzkriterium:** `uvicorn app.gateway.main:app` ohne `SYSTEM_ADMIN_PASSWORD` in `.env` bricht mit klarer Fehlermeldung ab.

---

### Task S1.2 — Redis-Key-Namespacing (Tenant-Scope)

**Was:** Alle Redis-Keys mit Tenant-Präfix versehen.

**Warum:** Aktuell: `token:{token}`, `user_token:{user_id}`, `human_mode:{user_id}`, `dialog:{user_id}`. Bei zwei Tenants mit demselben User-ID (WhatsApp-Nummer) überschreiben sich Tokens gegenseitig.

**Dateien:**
- `app/gateway/main.py` (Verifikationstoken-Logik)
- `app/memory/context.py` (Dialog-Context-Keys)
- `app/gateway/redis_bus.py` (Pub/Sub-Channels — separat betrachten)

**Durchführung:**
1. Hilfsfunktion `redis_key(tenant_id: int, *parts: str) -> str` in einem neuen Modul `app/core/redis_keys.py` anlegen:
   ```python
   def redis_key(tenant_id: int, *parts: str) -> str:
       return f"t{tenant_id}:" + ":".join(parts)
   ```
2. Alle `redis.set(f"token:{token}", ...)` ersetzen durch `redis.set(redis_key(tenant_id, "token", token), ...)`.
3. Alle `redis.get(f"user_token:{user_id}", ...)` ersetzen durch `redis.get(redis_key(tenant_id, "user_token", str(user_id)), ...)`.
4. Alle `human_mode:{user_id}` Keys ersetzen.
5. Dialog-Context-Keys in `app/memory/context.py`: `dialog:{user_id}` → `redis_key(tenant_id, "dialog", user_id)`.
6. Pub/Sub-Channels (`ariia:inbound`, `ariia:outbound`, `ariia:events`) bleiben vorerst global — sie transportieren vollständige Messages mit `tenant_id` im Payload. Dies ist akzeptabel für Phase 1.

**Migration:** Bestehende Redis-Keys von GetImpulse haben kein Präfix. Sie laufen nach TTL automatisch ab (max. 30 min für Dialog, 24h für Tokens). Keine aktive Migration notwendig — Nutzer müssen sich einmalig neu verifizieren.

**Test:** `tests/test_redis_namespacing.py` — neuen Testfall:
- Zwei Tenants, gleiche User-ID → Keys dürfen sich nicht überschreiben
- `redis_key()` gibt korrektes Format zurück

**Akzeptanzkriterium:** `grep -r "redis.set(f\"token:" app/` liefert 0 Treffer.

---

### Task S1.3 — `tenant_id` NOT NULL in Kerntabellen

**Was:** `ChatSession.tenant_id`, `ChatMessage.tenant_id`, `StudioMember.tenant_id` von `nullable=True` auf `nullable=False` ändern.

**Warum:** Nullable `tenant_id` ermöglicht Sessions ohne Tenant-Zuordnung. Diese landen via `_backfill_legacy_settings_tenant_ids()` beim System-Tenant — eine stille, fehlerhafte Datenmigration.

**Dateien:**
- `app/core/models.py`
- `alembic/versions/` (neue Migration anlegen)

**Durchführung:**
1. Alembic-Migration erstellen: `alembic revision --autogenerate -m "tenant_id_not_null_core_tables"`.
2. In der Migration: Zunächst alle NULL-Werte auf den System-Tenant-ID backfüllen (SELECT system tenant ID, UPDATE WHERE tenant_id IS NULL), dann NOT NULL Constraint setzen.
3. `app/core/models.py` anpassen: `nullable=False` für alle drei Felder.
4. Alle Codepfade prüfen die `tenant_id=None` übergeben könnten — besonders in `app/gateway/main.py` die `_resolve_tenant_id()` Aufrufe.

**Test:** SQLAlchemy wirft `IntegrityError` wenn versucht wird eine Session ohne `tenant_id` zu erstellen.

**Akzeptanzkriterium:** `nullable=False` in allen drei Modellen; Migration läuft ohne Fehler durch.

---

### Task S1.4 — Session-Invalidierung bei User-Deaktivierung

**Was:** Token-Blacklist via Redis implementieren.

**Warum:** Aktuell bleiben HMAC-Tokens bis zu 12 Stunden gültig, auch wenn der User deaktiviert wurde.

**Dateien:**
- `app/core/auth.py`
- `app/gateway/auth.py` (User-Deaktivierungs-Endpoint)
- `app/core/redis_keys.py` (neu aus S1.2)

**Durchführung:**
1. Redis-Key-Schema für Blacklist: `redis_key(tenant_id, "token_blacklist", token_jti)` mit TTL = `AUTH_TOKEN_TTL_HOURS * 3600`.
2. Jedes Token bekommt ein `jti`-Feld (UUID) im Payload beim Erstellen.
3. `get_current_user()` in `app/core/auth.py` prüft nach erfolgreicher HMAC-Verifikation ob `jti` in der Blacklist ist.
4. `PUT /auth/users/{user_id}` (User deaktivieren): Wenn `is_active` auf `False` gesetzt wird, alle aktiven Token des Users in die Blacklist aufnehmen. Da Token-Liste nicht gespeichert wird, den User-spezifischen Blacklist-Key `redis_key(tenant_id, "user_blacklisted", user_id)` setzen — `get_current_user()` prüft auch diesen Key.

**Test:** `tests/test_auth_restore.py` — Testfall: User deaktivieren, Token validieren → muss 401 zurückgeben.

**Akzeptanzkriterium:** Deaktivierter User erhält innerhalb von 1 Sekunde einen 401 auf allen Endpoints.

---

### Sprint S1 — Abnahmekriterien

- [ ] `uvicorn` startet nicht ohne starkes `SYSTEM_ADMIN_PASSWORD`
- [ ] Alle Redis-Keys haben Tenant-Präfix `t{tenant_id}:`
- [ ] `tenant_id` ist NOT NULL in `chat_sessions`, `chat_messages`, `studio_members`
- [ ] Deaktivierter User erhält sofort 401
- [ ] Alle bestehenden Tests laufen weiterhin durch
- [ ] `pytest tests/ -v` → 0 Failures

---

## Sprint S2 — Prompt-Template-System & Agent-Dynamisierung
**Dauer:** Woche 3–4
**Ziel:** Alle Agent-System-Prompts dynamisieren. Kein Agent nennt mehr "GetImpulse Berlin".

---

### Task S2.1 — Tenant-Prompt-Config in Settings

**Was:** Settings-Keys für Tenant-spezifische Prompt-Variablen definieren und befüllen.

**Warum:** Agents brauchen zur Laufzeit Zugriff auf `studio_name`, `agent_name`, `prices_text`, `locale`, `emergency_number` etc.

**Dateien:**
- `app/gateway/persistence.py` (Default-Settings bei Tenant-Erstellung)
- `app/gateway/admin.py` (Settings-API)

**Durchführung:**
1. Neue Settings-Keys definieren (als Konstanten in `app/core/prompt_config.py`):
   ```python
   PROMPT_SETTINGS_KEYS = [
       "studio_name",           # "GetImpulse Berlin" | "SportPark München"
       "studio_short_name",     # "GetImpulse" | "SportPark"
       "agent_display_name",    # "ARIIA" | "SPORTIE" | beliebig
       "studio_locale",         # "de-DE" | "en-US" | "de-AT"
       "studio_timezone",       # "Europe/Berlin" | "Europe/Vienna"
       "studio_emergency_number", # "112" | "911" | "999"
       "studio_address",        # "Musterstraße 1, 10115 Berlin"
       "sales_prices_text",     # Freitext Tarifbeschreibung (Markdown)
       "sales_retention_rules", # Freitext Retentionsregeln (Markdown)
       "medic_disclaimer_text", # Gesundheitlicher Haftungsausschluss
       "persona_bio_text",      # Agenten-Persönlichkeitsbeschreibung
   ]
   ```
2. Diese Keys mit GetImpulse-Werten als Default in `_seed_default_settings()` befüllen (damit bestehende Daten erhalten bleiben).
3. Neuer Admin-Endpoint `GET /admin/prompt-config` gibt alle Prompt-Settings des aktuellen Tenants zurück.
4. Neuer Admin-Endpoint `PUT /admin/prompt-config` aktualisiert beliebige Prompt-Settings (nur tenant_admin+).

**Test:** `tests/test_prompt_config.py`:
- Zwei Tenants haben unterschiedliche `studio_name` Werte
- GET liefert korrekten tenant-spezifischen Wert

**Akzeptanzkriterium:** Jeder Tenant hat eigene, änderbare Prompt-Konfiguration in der Datenbank.

---

### Task S2.2 — Prompt-Template-Engine implementieren

**Was:** Zentrales Modul das System-Prompts aus Templates + Tenant-Config zusammenbaut.

**Dateien:**
- `app/core/prompt_builder.py` (neu anlegen)

**Durchführung:**
1. `PromptBuilder`-Klasse anlegen:
   ```python
   class PromptBuilder:
       def __init__(self, persistence: PersistenceService, tenant_id: int):
           self._ps = persistence
           self._tid = tenant_id
           self._cache: dict[str, str] = {}

       def _get(self, key: str, fallback: str = "") -> str:
           if key not in self._cache:
               val = self._ps.get_setting(key, tenant_id=self._tid)
               self._cache[key] = val or fallback
           return self._cache[key]

       def build(self, template: str) -> str:
           """Ersetzt alle {placeholder} in template mit Tenant-Werten."""
           return template.format(
               studio_name=self._get("studio_name", "Fitnessstudio"),
               studio_short_name=self._get("studio_short_name", "Studio"),
               agent_name=self._get("agent_display_name", "ARIIA"),
               locale=self._get("studio_locale", "de-DE"),
               emergency_number=self._get("studio_emergency_number", "112"),
               prices_text=self._get("sales_prices_text", ""),
               retention_rules=self._get("sales_retention_rules", ""),
               disclaimer=self._get("medic_disclaimer_text", ""),
               persona_bio=self._get("persona_bio_text", ""),
           )
   ```
2. Cache-TTL: Bei jedem neuen Request-Kontext frisch gebaut (kein persistent Cache, da Settings sich ändern können). Alternativ: 60s TTL via `functools.lru_cache` mit `tenant_id` als Cache-Key.

**Test:** Unit-Test der `build()` Methode mit Mock-PersistenceService.

**Akzeptanzkriterium:** `PromptBuilder.build("Hallo von {studio_name}")` gibt bei Tenant A `"Hallo von GetImpulse Berlin"` und bei Tenant B `"Hallo von SportPark München"` zurück.

---

### Task S2.3 — Alle Agent-Prompts auf Templates umstellen

**Was:** Hardcoded Strings in allen 5 Agenten durch Templates ersetzen.

**Dateien:**
- `app/swarm/agents/sales.py`
- `app/swarm/agents/medic.py`
- `app/swarm/agents/persona.py`
- `app/swarm/agents/vision.py`
- `app/swarm/router/intents.py`
- `app/swarm/base.py` (PromptBuilder-Integration)

**Durchführung Schritt für Schritt:**

**1. Sales-Agent (`app/swarm/agents/sales.py`):**
```python
# VORHER (Zeile 19-47):
SALES_SYSTEM_PROMPT = """Du bist ARIIA, der Retention-Agent von GetImpulse Berlin...
Tarife GetImpulse Berlin:
- Flex: 29,90€/Monat..."""

# NACHHER:
SALES_SYSTEM_PROMPT_TEMPLATE = """Du bist {agent_name}, der Retention-Agent von {studio_name}.

Dein Ziel: Mitglieder HALTEN und MOTIVIEREN.

{prices_text}

{retention_rules}

Stil: Empathisch aber motivierend. Max 3-4 Sätze."""
```

**2. Medic-Agent (`app/swarm/agents/medic.py`):**
```python
MEDIC_SYSTEM_PROMPT_TEMPLATE = """Du bist {agent_name}, der Gesundheits- und Fitness-Coach-Agent von {studio_name}.

WICHTIG: {disclaimer}

Bei Notfällen: Sofort {emergency_number} empfehlen."""
```

**3. Persona-Agent (`app/swarm/agents/persona.py`):**
```python
PERSONA_SYSTEM_PROMPT_TEMPLATE = """Du bist {agent_name}, der digitale Fitness-Buddy von {studio_name}.

{persona_bio}

Tonalität: Freundlich, motivierend, max 3 Sätze."""
```

**4. Intent-Router (`app/swarm/router/intents.py`):**
```python
INTENT_SYSTEM_PROMPT_TEMPLATE = """Du bist der Intent-Classifier für {agent_name}, den KI-Assistenten von {studio_name}..."""
```

**5. `BaseAgent.handle()` anpassen:**
- `BaseAgent` bekommt `tenant_id: int` als Konstruktor-Parameter
- Vor `_call_llm()` wird `PromptBuilder(persistence, tenant_id).build(TEMPLATE)` aufgerufen
- Das gebaute Prompt wird als `system_prompt` übergeben

**6. `SwarmRouter` anpassen:**
- `tenant_id` aus `InboundMessage` extrahieren und an Agent-Konstruktor weitergeben

**Test:** `tests/test_agent_prompts.py`:
- Mock-Settings für Tenant A und B
- `AgentSales.handle(message)` mit Tenant A → Prompt enthält `"GetImpulse Berlin"`
- `AgentSales.handle(message)` mit Tenant B → Prompt enthält `"SportPark München"`
- Suche nach Literal-String `"GetImpulse Berlin"` in Agent-Dateien → 0 Treffer

**Akzeptanzkriterium:**
```bash
grep -r "GetImpulse Berlin" app/swarm/ → 0 Treffer
grep -r "GetImpulse Berlin" app/integrations/ → 0 Treffer
```

---

### Task S2.4 — Prompt-Config UI im Frontend

**Was:** Admin-Seite zum Bearbeiten aller Prompt-Konfigurationswerte des Tenants.

**Dateien:**
- `frontend/app/settings/prompts/page.tsx` (neu)
- `frontend/components/settings/SettingsSubnav.tsx`

**Durchführung:**
1. Neue Seite `frontend/app/settings/prompts/page.tsx` anlegen.
2. Formular mit Feldern für alle `PROMPT_SETTINGS_KEYS` (Textarea für lange Texte, Input für kurze).
3. `GET /admin/prompt-config` für initiale Befüllung, `PUT /admin/prompt-config` für Speichern.
4. Nur `tenant_admin` und `system_admin` können diese Seite sehen (RBAC-Guard).
5. `SettingsSubnav.tsx` um Link "Agent-Konfiguration" erweitern.

**Akzeptanzkriterium:** Tenant-Admin kann `studio_name` ändern, nach Speichern antworten Agents mit neuem Namen.

---

### Sprint S2 — Abnahmekriterien

- [ ] `grep -r "GetImpulse Berlin" app/swarm/` → 0 Treffer
- [ ] `grep -r "GetImpulse Berlin" app/integrations/` → 0 Treffer
- [ ] `grep -r "getimpulse" config/settings.py` → 0 Treffer (nur als kommentiertes Beispiel erlaubt)
- [ ] Zwei Test-Tenants mit unterschiedlichen Studio-Namen produzieren unterschiedliche Agent-Antworten
- [ ] Prompt-Config UI in Frontend erreichbar und funktionsfähig
- [ ] Alle bestehenden Tests noch grün

---

## Sprint S3 — Integration-Config-Completeness
**Dauer:** Woche 5–6
**Ziel:** Jeder Tenant kann vollständig eigene Integrationen konfigurieren. Keine globalen Singletons mehr für tenant-spezifische Services.

---

### Task S3.1 — Magicline Studio-ID per Tenant konfigurierbar machen

**Was:** `magicline_tenant_id` aus globalen `config/settings.py` in Tenant-Settings verschieben.

**Warum:** Aktuell wird der Wert `"getimpulse"` für alle Tenants verwendet. Tenant B mit eigenem Magicline-Vertrag und eigener Studio-ID kann nicht konfiguriert werden.

**Dateien:**
- `config/settings.py`
- `app/integrations/magicline/member_enrichment.py`
- `app/integrations/magicline/members_sync.py`
- `app/gateway/admin.py` (Integrations-Settings-UI)
- `app/gateway/persistence.py` (Default-Seeds)

**Durchführung:**
1. `magicline_tenant_id` aus `config/settings.py` entfernen.
2. In `app/gateway/persistence.py` den Seed-Wert für neue Tenants hinzufügen: `("magicline_studio_id", "", "Magicline Studio/Tenant ID")` — leer als Default.
3. In der Integrations-Settings-Seite (Admin) das Feld `magicline_studio_id` hinzufügen (neben `magicline_base_url` und `magicline_api_key`).
4. Alle Aufrufe in `member_enrichment.py` und `members_sync.py` die `settings.magicline_tenant_id` verwenden, umstellen auf `persistence.get_setting("magicline_studio_id", tenant_id=tenant_id)`.
5. Wenn `magicline_studio_id` leer ist: Synchronisation wird übersprungen, Warnung geloggt.

**Test:** Mock zwei Tenants mit unterschiedlichen `magicline_studio_id` Werten → Member-Sync ruft Magicline mit korrekter Studio-ID auf.

**Akzeptanzkriterium:** `grep -r "magicline_tenant_id" config/` → 0 Treffer.

---

### Task S3.2 — WhatsApp & Telegram Webhook-Routing absichern

**Was:** Tenant-Auflösung für WhatsApp und Telegram von unsicherem Payload-Parsing auf robustes Token-basiertes Routing umstellen.

**Warum:** Aktuell: Wenn `tenant_id` fehlt im Payload, landet die Message beim System-Tenant. Das ist eine stille Fehlerrouting-Gefahr.

**Dateien:**
- `app/gateway/main.py`
- `app/gateway/schemas.py`

**Durchführung (WhatsApp):**
1. WhatsApp-Webhook-Signature-Prüfung (`HMAC-SHA256`) findet bereits statt.
2. Zusätzlich: `wa_phone_number_id` aus dem Payload extrahieren.
3. Neuer Settings-Key `wa_phone_number_id` (bereits als Tenant-Setting vorhanden laut Audit).
4. Lookup: `SELECT tenant_id FROM settings WHERE key = 'wa_phone_number_id' AND value = ?` → Tenant gefunden.
5. Wenn kein Tenant gefunden: HTTP 404 mit Log-Eintrag `"unroutable_wa_message"`, nicht stillen Fallback.
6. Tenant-ID aus Lookup verwenden, nicht aus Payload.

**Durchführung (Telegram):**
1. Bot-Token aus Telegram-Webhook-Secret-Header extrahieren.
2. Lookup: `SELECT tenant_id FROM settings WHERE key = 'telegram_bot_token' AND value = ?`.
3. Wenn kein Tenant: HTTP 404.

**Alternativ-Ansatz (einfacher, sicherer):**
Zwei neue Endpunkte einführen analog zu SMS/Email:
```
POST /webhook/whatsapp/{tenant_slug}
POST /webhook/telegram/{tenant_slug}
```
Und alte Endpunkte als Deprecated markieren (noch 30 Tage erreichbar, dann entfernen). Dies ist der bevorzugte Ansatz da er das Muster von SMS/Email konsistent fortsetzt.

**Test:** Request ohne gültigen Tenant → 404. Request mit gültigem Tenant → 200.

**Akzeptanzkriterium:** `_resolve_tenant_id()` Fallback auf System-Tenant wird für eingehende Messages nicht mehr verwendet.

---

### Task S3.3 — Integration-Health-Check per Tenant

**Was:** Neuer Endpoint `GET /admin/integrations/health` der alle konfigurierten Integrationen des Tenants prüft.

**Dateien:**
- `app/gateway/admin.py`
- `frontend/app/settings/integrations/page.tsx`

**Durchführung:**
1. Endpoint gibt JSON zurück:
   ```json
   {
     "magicline": {"configured": true, "reachable": true, "last_sync": "2026-02-21T10:00:00Z"},
     "whatsapp": {"configured": true, "phone_number_id": "123456"},
     "telegram": {"configured": true, "bot_username": "@ariia_bot"},
     "smtp": {"configured": true, "reachable": false, "error": "Connection timeout"}
   }
   ```
2. Frontend: Status-Badges neben jeder Integration auf der Integrations-Seite (grün/gelb/rot).

**Akzeptanzkriterium:** Tenant-Admin sieht auf einen Blick welche Integrationen korrekt konfiguriert sind.

---

### Sprint S3 — Abnahmekriterien

- [ ] `magicline_studio_id` ist per-Tenant konfigurierbar, kein Global-Default
- [ ] WhatsApp/Telegram Webhooks routen via `{tenant_slug}` URL-Parameter
- [ ] Webhook ohne gültigen Tenant → HTTP 404 (kein stiller Fallback)
- [ ] Integration-Health-Check Endpoint funktioniert
- [ ] Alle Member-Sync-Tests weiterhin grün

---

## Sprint S4 — Billing & Subscription Engine
**Dauer:** Woche 7–9 (3 Wochen, da komplexeste Sprint)
**Ziel:** Vollständiges Subscription-Management, Plan-basierte Feature-Gates, Stripe-Integration.

---

### Task S4.1 — Datenmodell: Subscriptions & Plans

**Was:** Neue Datenbanktabellen für Pläne, Subscriptions und Usage-Records.

**Dateien:**
- `app/core/models.py`
- `alembic/versions/` (neue Migration)

**Durchführung:**

**Neues Model `Plan`:**
```python
class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)          # "Starter" | "Pro" | "Enterprise"
    slug = Column(String, unique=True, nullable=False)  # "starter" | "pro" | "enterprise"
    stripe_price_id = Column(String, nullable=True)     # Stripe Price ID für Billing
    price_monthly_cents = Column(Integer, nullable=False)  # 0 für Free
    # Feature Limits:
    max_members = Column(Integer, nullable=True)         # NULL = unbegrenzt
    max_monthly_messages = Column(Integer, nullable=True) # NULL = unbegrenzt
    max_channels = Column(Integer, nullable=False, default=1)
    whatsapp_enabled = Column(Boolean, default=True)
    telegram_enabled = Column(Boolean, default=False)
    sms_enabled = Column(Boolean, default=False)
    email_enabled = Column(Boolean, default=False)
    voice_enabled = Column(Boolean, default=False)
    memory_analyzer_enabled = Column(Boolean, default=False)
    custom_prompts_enabled = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, ...)
```

**Neues Model `Subscription`:**
```python
class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    status = Column(String, nullable=False)  # "active"|"trialing"|"past_due"|"canceled"
    stripe_subscription_id = Column(String, nullable=True, unique=True)
    stripe_customer_id = Column(String, nullable=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, ...)
    updated_at = Column(DateTime, ...)
```

**Neues Model `UsageRecord`:**
```python
class UsageRecord(Base):
    __tablename__ = "usage_records"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)      # 1-12
    messages_inbound = Column(Integer, default=0)
    messages_outbound = Column(Integer, default=0)
    active_members = Column(Integer, default=0)        # Peak in diesem Monat
    llm_tokens_used = Column(Integer, default=0)
    UniqueConstraint("tenant_id", "period_year", "period_month")
```

**Alembic-Migration:**
```bash
alembic revision --autogenerate -m "add_billing_models"
alembic upgrade head
```

**Seed-Daten:** Drei initiale Pläne in einer separaten Seed-Funktion:
- **Starter:** Kostenlos, 1 Channel (WA), max 500 Members, max 1000 Messages/Monat
- **Pro:** 99€/Monat, WA + TG + Email, max 5000 Members, unbegrenzte Messages, Custom Prompts
- **Enterprise:** Auf Anfrage, alle Features, unbegrenzt

**Akzeptanzkriterium:** Alembic-Migration läuft auf Clean-DB und auf bestehender GetImpulse-DB ohne Fehler durch.

---

### Task S4.2 — Feature-Gate-System

**Was:** Middleware/Dependency die Plan-Limits durchsetzt bevor Requests verarbeitet werden.

**Dateien:**
- `app/core/feature_gates.py` (neu)
- `app/gateway/main.py` (Gates einbauen)
- `app/swarm/router/` (Channel-Gates)

**Durchführung:**
1. `FeatureGate`-Service anlegen:
   ```python
   class FeatureGate:
       def __init__(self, persistence: PersistenceService, tenant_id: int):
           self._plan = self._load_plan(tenant_id)

       def require(self, feature: str) -> None:
           """Wirft HTTPException(402) wenn Feature nicht im Plan."""
           if not getattr(self._plan, f"{feature}_enabled", False):
               raise HTTPException(402, f"Feature '{feature}' not available on current plan")

       def check_message_limit(self, tenant_id: int) -> None:
           """Wirft HTTPException(429) wenn Monats-Limit erreicht."""
           usage = self._get_current_usage(tenant_id)
           if self._plan.max_monthly_messages and usage >= self._plan.max_monthly_messages:
               raise HTTPException(429, "Monthly message limit reached. Please upgrade.")
   ```
2. Usage-Counter nach jeder verarbeiteten Message inkrementieren: `UPDATE usage_records SET messages_inbound = messages_inbound + 1 WHERE tenant_id = ? AND period_year = ? AND period_month = ?`.
3. In `SwarmRouter`: Vor Agent-Dispatch `feature_gate.check_message_limit(tenant_id)` aufrufen.
4. In Webhook-Endpoints: Kanal-spezifische Gates prüfen (`telegram_enabled`, `sms_enabled` etc.).

**Test:** `tests/test_feature_gates.py`:
- Tenant mit Starter-Plan versucht Telegram-Message → 402
- Tenant mit erschöpftem Message-Limit → 429
- Tenant mit Pro-Plan und Telegram → 200

**Akzeptanzkriterium:** Starter-Tenant kann keine SMS-Nachrichten verarbeiten.

---

### Task S4.3 — Stripe-Integration für Platform-Billing

**Was:** Stripe-Checkout für neue Subscriptions und Webhook-Handler für Payment-Events.

**Dateien:**
- `app/billing/stripe_service.py` (neu, Modul `app/billing/` anlegen)
- `app/billing/webhook_handler.py` (neu)
- `app/gateway/main.py` (Billing-Endpoints registrieren)
- `pyproject.toml` (Stripe-Dependency hinzufügen: `stripe>=10.0.0`)

**Durchführung:**

**`app/billing/stripe_service.py`:**
```python
import stripe

class StripeService:
    def __init__(self, api_key: str):
        stripe.api_key = api_key

    def create_checkout_session(
        self, tenant_id: int, plan: Plan, success_url: str, cancel_url: str
    ) -> str:
        """Erstellt Stripe Checkout Session, gibt URL zurück."""
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"tenant_id": str(tenant_id)},
        )
        return session.url

    def cancel_subscription(self, stripe_subscription_id: str) -> None:
        stripe.Subscription.cancel(stripe_subscription_id)
```

**Neue Endpoints in `app/gateway/main.py`:**
- `POST /billing/checkout` → Erstellt Checkout-Session für aktuellen Tenant
- `POST /billing/portal` → Erstellt Customer-Portal-Session für Self-Service
- `POST /webhook/stripe` → Stripe-Event-Handler (keine Auth, nur Stripe-Signature)

**Webhook-Handler Events:**
- `checkout.session.completed` → Subscription in DB anlegen, Plan aktivieren
- `customer.subscription.updated` → Status updaten (z. B. `past_due`)
- `customer.subscription.deleted` → Auf Starter-Plan downgraden

**Test:** Stripe-Webhook mit Mock-Events via `stripe-mock` oder Fixture-Daten testen.

**Wichtig:** `STRIPE_SECRET_KEY` und `STRIPE_WEBHOOK_SECRET` als Umgebungsvariablen, nicht in DB.

**Akzeptanzkriterium:** Neuer Tenant kann sich via Checkout auf Pro upgraden, `subscription.status = "active"` wird gesetzt.

---

### Task S4.4 — Billing-Dashboard im Frontend

**Was:** Neue Seite `frontend/app/settings/billing/page.tsx`.

**Durchführung:**
1. Zeigt aktuellen Plan und Status (Active/Trialing/Past Due).
2. Zeigt aktuellen Monat Usage: Messages x/y, Members x/y.
3. "Upgrade"-Button öffnet Stripe Checkout.
4. "Manage Subscription"-Button öffnet Stripe Customer Portal.
5. Tabelle der verfügbaren Pläne mit Feature-Vergleich.

**Akzeptanzkriterium:** Tenant-Admin sieht Plan, Usage und kann upgraden ohne Support-Kontakt.

---

### Sprint S4 — Abnahmekriterien

- [ ] `Plan`, `Subscription`, `UsageRecord` Tabellen existieren in DB
- [ ] Message-Counter wird nach jeder verarbeiteten Message inkrementiert
- [ ] Starter-Plan-Tenant kann Telegram-Webhook nicht nutzen (402)
- [ ] Tenant über Message-Limit erhält 429
- [ ] Stripe-Checkout erstellt Subscription in DB
- [ ] Stripe-Webhook aktualisiert Subscription-Status

---

## Sprint S5 — Onboarding & Tenant Lifecycle
**Dauer:** Woche 10–11
**Ziel:** Sicherer, verifizierter Tenant-Onboarding-Flow mit Plan-Auswahl.

---

### Task S5.1 — E-Mail-Verifizierung bei Registrierung

**Was:** Nach `POST /auth/register` bekommt der User eine Verifizierungs-Mail. Tenant ist erst nach Bestätigung aktiv.

**Dateien:**
- `app/gateway/auth.py`
- `app/core/models.py` (neues Feld `email_verified_at`)
- `app/integrations/smtp.py`

**Durchführung:**
1. `UserAccount` bekommt neues Feld: `email_verified_at = Column(DateTime, nullable=True)`.
2. `Tenant` bekommt neues Feld: `is_verified = Column(Boolean, default=False)`.
3. Nach Registrierung: SMTP-Mail mit Verifikationslink senden: `https://app.ariia.ai/verify?token={token}&tenant={tenant_slug}`.
4. Verifikationstoken: `HMAC-SHA256(email + tenant_id + timestamp, AUTH_SECRET)` mit 24h TTL in Redis.
5. Neuer Endpoint `GET /auth/verify?token=&tenant=` setzt `email_verified_at` und `tenant.is_verified = True`.
6. Tenants mit `is_verified = False` können sich zwar einloggen, aber Webhooks werden abgewiesen (HTTP 403 mit Hinweis auf Verifizierung).

**Test:** Registrierung → Token in Redis → GET /auth/verify → Tenant.is_verified = True.

---

### Task S5.2 — Plan-Auswahl im Signup-Flow

**Was:** Registrierung direkt mit Plan-Auswahl verbinden.

**Dateien:**
- `app/gateway/auth.py`
- `frontend/app/register/page.tsx` (falls vorhanden, sonst neu anlegen)

**Durchführung:**
1. `POST /auth/register` akzeptiert optionalen Parameter `plan_slug` (Default: `"starter"`).
2. Nach Tenant-Erstellung: Starter-Subscription direkt anlegen (kein Stripe nötig für Free Tier).
3. Für bezahlte Pläne: Nach Verifizierung direkt in Stripe-Checkout weiterleiten.
4. Registrierungsseite: Plan-Auswahl-Karten vor dem Formular.

---

### Task S5.3 — Tenant-Deaktivierung & Daten-Export

**Was:** System-Admin kann Tenant deaktivieren. DSGVO-konformer Daten-Export.

**Dateien:**
- `app/gateway/admin.py`
- `app/core/gdpr.py` (neu)

**Durchführung:**
1. `PUT /admin/tenants/{tenant_id}/deactivate` (system_admin only): Setzt `tenant.is_active = False`, alle User-Tokens invalidieren (User-Blacklist-Key in Redis).
2. `GET /admin/tenants/{tenant_id}/export` (system_admin only): Exportiert alle Daten des Tenants als JSON-ZIP.
3. `DELETE /admin/tenants/{tenant_id}` (system_admin only): Hard-Delete nach DSGVO Art. 17 (CASCADE, PII entfernen).

---

### Sprint S5 — Abnahmekriterien

- [ ] Neuer Tenant ohne E-Mail-Verifizierung kann keine Messages empfangen
- [ ] Verifizierungslink in Mail funktioniert
- [ ] Deaktivierter Tenant: alle Webhooks → 403
- [ ] Daten-Export als ZIP möglich

---

## Sprint S6 — White-Label Frontend
**Dauer:** Woche 12–13
**Ziel:** Jeder Tenant hat eigenes Branding im Dashboard. Grundlage für Subdomain-Routing.

---

### Task S6.1 — Branding-Settings per Tenant

**Was:** Studio-Logo, Primärfarbe, Dashboard-Titel als Tenant-Setting konfigurierbar.

**Neue Settings-Keys:**
```python
"branding_logo_url"       # URL zum Logo (CDN oder Base64-Data-URL)
"branding_primary_color"  # Hex-Farbe: "#FF6B35"
"branding_dashboard_title" # "GetImpulse Dashboard" | "SportPark Admin"
"branding_favicon_url"    # URL zum Favicon
```

**Frontend:**
1. `frontend/lib/branding.ts` — lädt Branding bei App-Start von `GET /admin/settings/branding`.
2. CSS Custom Properties setzen: `document.documentElement.style.setProperty("--color-primary", color)`.
3. `<title>` und `<link rel="icon">` dynamisch setzen.
4. Logo in NavShell ersetzen.
5. Neue Branding-Seite unter `frontend/app/settings/branding/page.tsx`.

---

### Task S6.2 — Subdomain-Routing (Grundlage)

**Was:** Tenant-Auflösung via Subdomain vorbereiten.

**Dateien:**
- `app/gateway/main.py`
- `app/core/auth.py`
- `frontend/middleware.ts` (Next.js)

**Durchführung:**
1. Backend: `X-Tenant-Slug` Header-Support in `get_current_user()` — wenn Header gesetzt, wird Tenant daraus aufgelöst (zusätzlich zu Token).
2. Frontend: Next.js Middleware liest `req.headers.host`, extrahiert Subdomain (`{slug}.ariia.app`), setzt `X-Tenant-Slug` Header für alle API-Requests.
3. DNS und Deployment (Nginx/Caddy): Wildcard-DNS `*.ariia.app → Server-IP` konfigurieren.

---

### Sprint S6 — Abnahmekriterien

- [ ] Logo und Primärfarbe können pro Tenant gesetzt werden
- [ ] Frontend zeigt tenant-spezifisches Branding
- [ ] `X-Tenant-Slug` Header wird vom Backend akzeptiert

---

## Sprint S7 — Audit, Hardening & Launch-Gates
**Dauer:** Woche 14
**Ziel:** Finale Verifikation aller Änderungen gegen die Baseline aus `SAAS_READINESS_AUDIT_2026-02-21.md`.

---

### Task S7.1 — Regression-Test Multi-Tenant-Isolation

**Was:** Vollständige Test-Suite für Cross-Tenant-Datenleck-Erkennung.

**Dateien:**
- `tests/test_multitenant_isolation.py` (neu)

**Testfälle:**
```python
# 1. Chat-Session Isolation
def test_tenant_a_cannot_read_tenant_b_sessions():
    # Erstelle Sessions für Tenant A und B
    # GET /sessions mit Tenant-A-Token → nur Tenant-A-Sessions

# 2. Redis-Key Isolation
def test_redis_keys_are_tenant_scoped():
    # Token für Tenant A erstellen
    # Lookup mit Tenant-B-Scope → None

# 3. Settings Isolation
def test_settings_are_tenant_scoped():
    # studio_name = "A" für Tenant A, "B" für Tenant B
    # GET /admin/settings mit Tenant-A-Token → "A"

# 4. Member Isolation
def test_members_are_tenant_scoped():
    # Members für beide Tenants
    # GET /admin/members mit Tenant-A-Token → nur Tenant-A-Members

# 5. Agent-Prompt Isolation
def test_agent_uses_correct_tenant_prompt():
    # Message für Tenant A → Prompt enthält Tenant-A-Studio-Name
    # Message für Tenant B → Prompt enthält Tenant-B-Studio-Name
```

---

### Task S7.2 — Baseline-Vergleich durchführen

**Was:** Alle Metriken aus `SAAS_READINESS_AUDIT_2026-02-21.md` erneut messen.

**Checkliste:**
```bash
# Hardcoded Strings
grep -r "GetImpulse Berlin" app/   # → 0 Treffer erwartet
grep -r "getimpulse" config/       # → 0 Treffer erwartet
grep -r "password123" app/         # → 0 Treffer erwartet
grep -r "Europe/Berlin" app/       # → nur in Kommentaren erlaubt

# Redis-Key-Scope
grep -r 'f"token:{' app/           # → 0 Treffer erwartet
grep -r 'f"user_token:{' app/      # → 0 Treffer erwartet

# Nullable tenant_ids
grep -r "nullable=True" app/core/models.py  # → nur in AuditLog erlaubt

# Test Coverage
pytest tests/ --cov=app --cov-report=term-missing  # → ≥ 85%
```

**Ergebnis dokumentieren in:** `docs/audits/SAAS_READINESS_FINAL_YYYY-MM-DD.md`

---

### Task S7.3 — Security Audit

```bash
pip-audit                          # Python Dependency CVEs
bandit -r app/ -ll                 # Statische Sicherheitsanalyse
npm audit --prefix frontend        # Frontend Dependency CVEs
```

Alle Critical/High-Findings müssen behoben sein.

---

### Task S7.4 — Load-Test Multi-Tenant

**Was:** Locust-Szenario mit 3 gleichzeitigen Tenants.

**Szenario:**
- 50 concurrent Users auf Tenant A
- 50 concurrent Users auf Tenant B
- 10 concurrent Users auf Tenant C (Starter-Plan, limitiert)
- Dauer: 10 Minuten
- Ziel: < 200ms P95, 0 Cross-Tenant-Datenlecks in Logs

---

### Sprint S7 — Abnahmekriterien (= Launch-Gate)

- [ ] Alle 10 Baseline-Metriken aus `SAAS_READINESS_AUDIT_2026-02-21.md` erreicht
- [ ] `test_multitenant_isolation.py` → alle Tests grün
- [ ] 0 Critical/High in pip-audit und bandit
- [ ] Load-Test bestanden
- [ ] Finaler Audit-Report erstellt

---

## Gesamtübersicht Roadmap

| Sprint | Thema | Wochen | Kritische Deliverables |
|---|---|---|---|
| **S1** | Security & Redis-Namespacing | 1–2 | Redis-Keys mit Tenant-Scope, NOT NULL tenant_id, Session-Invalidierung |
| **S2** | Prompt-Templates & Agent-Dynamisierung | 3–4 | Kein hardcoded GetImpulse in Agents, Prompt-Config API + UI |
| **S3** | Integration-Config-Completeness | 5–6 | Magicline Studio-ID per Tenant, sichere Webhook-Routen |
| **S4** | Billing & Subscription Engine | 7–9 | Stripe-Integration, Feature-Gates, Usage-Metering |
| **S5** | Onboarding & Tenant Lifecycle | 10–11 | E-Mail-Verifizierung, Plan-Auswahl, Tenant-Deaktivierung |
| **S6** | White-Label Frontend | 12–13 | Branding per Tenant, Subdomain-Grundlage |
| **S7** | Audit & Launch-Gates | 14 | Baseline-Vergleich, Security Audit, Load-Test |

**Gesamtdauer:** 14 Wochen

---

## Invarianten (nie verletzen)

1. **GetImpulse-Daten bleiben intakt** — Alle Migrationen müssen auf der bestehenden DB ohne Datenverlust laufen.
2. **Tests müssen nach jedem Sprint grün sein** — Kein Sprint-Abschluss mit roten Tests.
3. **Kein Breaking Change ohne Migration** — Alembic für DB-Schema, Settings-Seeds für neue Config-Keys.
4. **Externe APIs werden in Tests gemockt** — Kein echter Magicline/Stripe/WhatsApp-Call in CI.
5. **BMAD-Zyklus** — Benchmark → Modularize → Architect → Deploy. Jede Aufgabe beginnt mit einer definierten Akzeptanzmetrik.
