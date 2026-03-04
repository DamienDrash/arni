"""ARIIA – Tenant-aware Prompt Builder (S2.2 → v2).

Every agent system-prompt is a Jinja2 template with {{ placeholders }}.
This module fills those placeholders from the tenant's Settings table at
call time, so each tenant gets its own branded, configured agent personality.

v2 Changes (Q2 2026):
- Business-type-agnostic variables (no more "studio_*" hardcoding)
- Extended variable set: owner, contact, booking, escalation
- Grouped variable categories for the Admin UI
- Backward compatibility: old "studio_*" keys still work

Usage:
    from app.core.prompt_builder import PromptBuilder
    from app.gateway.persistence import persistence

    builder = PromptBuilder(persistence, tenant_id=7)
    final_prompt = builder.build(SALES_SYSTEM_PROMPT_TEMPLATE)
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════════
# VARIABLE CATEGORIES – Used by the Admin UI to group settings
# ═══════════════════════════════════════════════════════════════════════════════

VARIABLE_CATEGORIES: list[dict] = [
    {
        "id": "business",
        "label": "Unternehmen",
        "description": "Grundlegende Informationen über dein Unternehmen",
        "icon": "Building2",
    },
    {
        "id": "agent",
        "label": "Agent-Identität",
        "description": "Name und Persönlichkeit deines KI-Assistenten",
        "icon": "Bot",
    },
    {
        "id": "contact",
        "label": "Kontakt & Standort",
        "description": "Kontaktdaten und Adresse für den Agenten",
        "icon": "MapPin",
    },
    {
        "id": "sales",
        "label": "Sales & Retention",
        "description": "Preise, Pakete und Kundenbindungs-Regeln",
        "icon": "TrendingUp",
    },
    {
        "id": "health",
        "label": "Gesundheit & Sicherheit",
        "description": "Disclaimer und Gesundheitsberatungs-Regeln",
        "icon": "HeartPulse",
    },
    {
        "id": "booking",
        "label": "Buchung & Termine",
        "description": "Buchungsanweisungen und Stornierungsregeln",
        "icon": "Calendar",
    },
    {
        "id": "escalation",
        "label": "Eskalation",
        "description": "Regeln für die Weiterleitung an menschliche Mitarbeiter",
        "icon": "AlertTriangle",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT SETTINGS – All keys that feed into prompt templates
# ═══════════════════════════════════════════════════════════════════════════════

# Each entry: (key, label, help_text, category, multiline, default_value)
PROMPT_SETTINGS_SCHEMA: list[dict] = [
    # ── Business ──────────────────────────────────────────────────────────
    {
        "key": "studio_name",
        "label": "Unternehmensname (vollständig)",
        "help": 'z.B. "Athletik Movement", "ARIIA Solutions GmbH"',
        "category": "business",
        "multiline": False,
        "default": "Mein Unternehmen",
    },
    {
        "key": "studio_short_name",
        "label": "Kurzname",
        "help": 'z.B. "Athletik Movement", "ARIIA"',
        "category": "business",
        "multiline": False,
        "default": "Unternehmen",
    },
    {
        "key": "studio_business_type",
        "label": "Geschäftstyp",
        "help": 'z.B. "personal_training", "gym", "physiotherapy", "wellness", "clinic"',
        "category": "business",
        "multiline": False,
        "default": "business",
    },
    {
        "key": "studio_owner_name",
        "label": "Inhaber / Ansprechpartner",
        "help": 'z.B. "Niklas Jauch", "Max Mustermann"',
        "category": "business",
        "multiline": False,
        "default": "",
    },
    {
        "key": "studio_description",
        "label": "Unternehmensbeschreibung",
        "help": "Kurze Beschreibung deines Unternehmens (2-3 Sätze). Wird dem Agenten als Kontext gegeben.",
        "category": "business",
        "multiline": True,
        "default": "",
    },
    # ── Agent Identity ────────────────────────────────────────────────────
    {
        "key": "agent_display_name",
        "label": "Agent-Name",
        "help": 'Name des Assistenten, z.B. "ARIIA", "Mia", "Coach Alex"',
        "category": "agent",
        "multiline": False,
        "default": "ARIIA",
    },
    {
        "key": "persona_bio_text",
        "label": "Agent-Persönlichkeit",
        "help": "Charakterbeschreibung / Persona des Assistenten. Definiert Tonalität, Stil und Verhalten.",
        "category": "agent",
        "multiline": True,
        "default": (
            "Persönlichkeit: Professionell, freundlich, hilfsbereit, kompetent. "
            "Sprache: Deutsch (primär), klare und verständliche Sätze. "
            "Du bist ein kompetenter Assistent, kein generischer Chatbot."
        ),
    },
    {
        "key": "studio_locale",
        "label": "Sprache / Locale",
        "help": 'BCP-47 Locale, z.B. "de-DE", "en-US"',
        "category": "agent",
        "multiline": False,
        "default": "de-DE",
    },
    {
        "key": "studio_timezone",
        "label": "Zeitzone",
        "help": 'IANA-Zeitzone, z.B. "Europe/Berlin"',
        "category": "agent",
        "multiline": False,
        "default": "Europe/Berlin",
    },
    # ── Contact & Location ────────────────────────────────────────────────
    {
        "key": "studio_address",
        "label": "Adresse",
        "help": "Physische Adresse für Agent-Antworten",
        "category": "contact",
        "multiline": False,
        "default": "",
    },
    {
        "key": "studio_phone",
        "label": "Telefonnummer",
        "help": 'z.B. "+49 30 12345678"',
        "category": "contact",
        "multiline": False,
        "default": "",
    },
    {
        "key": "studio_email",
        "label": "E-Mail-Adresse",
        "help": 'z.B. "info@example.com"',
        "category": "contact",
        "multiline": False,
        "default": "",
    },
    {
        "key": "studio_website",
        "label": "Website",
        "help": 'z.B. "https://example.com"',
        "category": "contact",
        "multiline": False,
        "default": "",
    },
    {
        "key": "studio_emergency_number",
        "label": "Notrufnummer",
        "help": 'z.B. "112" (DE) oder "911" (US)',
        "category": "contact",
        "multiline": False,
        "default": "112",
    },
    # ── Sales & Retention ─────────────────────────────────────────────────
    {
        "key": "sales_prices_text",
        "label": "Preise & Pakete (Markdown)",
        "help": "Preisliste die der Sales-Agent nutzt. Markdown-Format.",
        "category": "sales",
        "multiline": True,
        "default": (
            "Bitte konfiguriere hier deine Preise und Pakete.\n"
            "Beispiel:\n"
            "- Einzelsitzung: 89€\n"
            "- 10er-Karte: 790€\n"
            "- Monatspaket: 299€/Monat"
        ),
    },
    {
        "key": "sales_retention_rules",
        "label": "Retention-Regeln",
        "help": "Regeln für den Sales-Agent zur Kundenbindung und Beschwerdemanagement.",
        "category": "sales",
        "multiline": True,
        "default": (
            "RETENTION-REGELN:\n"
            "1. Inaktiv (>30 Tage): Frage nach dem Befinden und biete Unterstützung an.\n"
            "2. Sehr aktiv: Bedanke dich und frage nach Feedback.\n"
            "3. Kündigungswunsch: Frage nach dem Grund und biete Alternativen an."
        ),
    },
    {
        "key": "sales_complaint_protocol",
        "label": "Beschwerde-Protokoll",
        "help": "Anweisungen für den Umgang mit Beschwerden und negativem Feedback.",
        "category": "sales",
        "multiline": True,
        "default": (
            "BESCHWERDE-PROTOKOLL:\n"
            "1. VALIDIEREN: Zeige Verständnis für das Anliegen.\n"
            "2. ENTSCHULDIGEN: Aufrichtig entschuldigen.\n"
            "3. LÖSUNG: Konkrete Lösung oder Weiterleitung anbieten.\n"
            "4. NACHFASSEN: Anbieten, dass sich jemand persönlich meldet."
        ),
    },
    # ── Health & Safety ───────────────────────────────────────────────────
    {
        "key": "medic_disclaimer_text",
        "label": "Gesundheits-Disclaimer",
        "help": "Pflicht-Disclaimer der Gesundheitsantworten angehängt wird.",
        "category": "health",
        "multiline": True,
        "default": (
            "⚠️ _Ich bin kein Arzt und kein Ersatz für medizinische Beratung. "
            "Bei echten Beschwerden bitte immer einen Arzt aufsuchen!_"
        ),
    },
    {
        "key": "health_advice_scope",
        "label": "Beratungsumfang Gesundheit",
        "help": "Definiert, wozu der Health-Agent beraten darf (z.B. Bewegung, Ernährung, Prävention).",
        "category": "health",
        "multiline": True,
        "default": (
            "Du darfst beraten zu: Bewegung, Dehnung, Mobilität, allgemeine Fitness-Tipps, Prävention.\n"
            "Du darfst NICHT beraten zu: Diagnosen, Medikamente, Therapien, psychische Erkrankungen."
        ),
    },
    # ── Booking ───────────────────────────────────────────────────────────
    {
        "key": "booking_instructions",
        "label": "Buchungsanweisungen",
        "help": "Spezielle Anweisungen für den Buchungsprozess (z.B. Vorlaufzeit, Bestätigung).",
        "category": "booking",
        "multiline": True,
        "default": "",
    },
    {
        "key": "booking_cancellation_policy",
        "label": "Stornierungsregeln",
        "help": "Regeln für Stornierungen und Umbuchungen.",
        "category": "booking",
        "multiline": True,
        "default": "",
    },
    # ── Escalation ────────────────────────────────────────────────────────
    {
        "key": "escalation_triggers",
        "label": "Eskalations-Auslöser",
        "help": "Situationen, in denen der Agent an einen Menschen weiterleiten soll.",
        "category": "escalation",
        "multiline": True,
        "default": (
            "Eskaliere an einen menschlichen Mitarbeiter wenn:\n"
            "- Der Kunde explizit nach einem Menschen fragt\n"
            "- Du die Frage nach 2 Versuchen nicht beantworten kannst\n"
            "- Es um rechtliche, vertragliche oder finanzielle Streitigkeiten geht\n"
            "- Der Kunde emotional aufgebracht oder verärgert ist"
        ),
    },
    {
        "key": "escalation_contact",
        "label": "Eskalations-Kontakt",
        "help": "Kontaktdaten für die Weiterleitung (Name, Telefon, E-Mail).",
        "category": "escalation",
        "multiline": True,
        "default": "",
    },
]

# Flat list of all setting keys (for backward compatibility)
PROMPT_SETTINGS_KEYS: list[str] = [s["key"] for s in PROMPT_SETTINGS_SCHEMA]

# Default values dict (for backward compatibility)
PROMPT_SETTINGS_DEFAULTS: dict[str, str] = {s["key"]: s["default"] for s in PROMPT_SETTINGS_SCHEMA}


class PromptBuilder:
    """Fills agent prompt templates with tenant-specific configuration values.

    One instance per request/message — do not cache across requests as
    tenant admins may update settings at any time.
    """

    def __init__(self, persistence: object, tenant_id: int) -> None:
        self._ps = persistence
        self._tid = tenant_id
        self._cache: dict[str, str] = {}

    def _get(self, key: str) -> str:
        if key not in self._cache:
            try:
                val = self._ps.get_setting(key, None, tenant_id=self._tid)  # type: ignore[attr-defined]
                self._cache[key] = str(val).strip() if val else PROMPT_SETTINGS_DEFAULTS.get(key, "")
            except Exception:
                self._cache[key] = PROMPT_SETTINGS_DEFAULTS.get(key, "")
        return self._cache[key]

    def build(self, template: str) -> str:
        """Replace all {placeholder} tokens in *template* with tenant values.

        Unknown placeholders are left as-is (no KeyError raised).
        """
        replacements = {key: self._get(key) for key in PROMPT_SETTINGS_KEYS}
        try:
            return template.format_map(_SafeDict(replacements))
        except Exception as exc:
            logger.warning("prompt_builder.format_failed", error=str(exc))
            return template

    def get_all(self) -> dict[str, str]:
        """Return all prompt settings as a flat dict (for Jinja2 context)."""
        return {key: self._get(key) for key in PROMPT_SETTINGS_KEYS}

    # Convenience accessors
    @property
    def studio_name(self) -> str:
        return self._get("studio_name")

    @property
    def business_type(self) -> str:
        return self._get("studio_business_type")

    @property
    def owner_name(self) -> str:
        return self._get("studio_owner_name")

    @property
    def agent_name(self) -> str:
        return self._get("agent_display_name")

    @property
    def emergency_number(self) -> str:
        return self._get("studio_emergency_number")

    @property
    def medic_disclaimer(self) -> str:
        return self._get("medic_disclaimer_text")


class _SafeDict(dict):  # type: ignore[type-arg]
    """dict subclass that returns '{key}' for missing keys instead of raising KeyError."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def seed_prompt_settings(persistence: object, tenant_id: int) -> None:
    """Seed prompt config keys for a new tenant with system defaults.

    Safe to call multiple times — only writes keys that don't yet exist.
    """
    for key, default in PROMPT_SETTINGS_DEFAULTS.items():
        try:
            existing = persistence.get_setting(key, None, tenant_id=tenant_id)  # type: ignore[attr-defined]
            if existing is None:
                persistence.set_setting(key, default, tenant_id=tenant_id)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning("prompt_builder.seed_failed", key=key, error=str(exc))
