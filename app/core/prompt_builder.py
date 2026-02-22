"""ARIIA – Tenant-aware Prompt Builder (S2.2).

Every agent system-prompt is a template with {placeholders}. This module
fills those placeholders from the tenant's Settings table at call time,
so each tenant gets its own branded, configured agent personality.

Usage:
    from app.core.prompt_builder import PromptBuilder
    from app.gateway.persistence import persistence

    builder = PromptBuilder(persistence, tenant_id=7)
    final_prompt = builder.build(SALES_SYSTEM_PROMPT_TEMPLATE)
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()

# All setting keys that feed into prompt templates.
# Seeded at tenant creation with sensible defaults.
PROMPT_SETTINGS_KEYS: list[str] = [
    "studio_name",             # Full studio name, e.g. "Mein Fitnessstudio GmbH"
    "studio_short_name",       # Short name, e.g. "MyStudio"
    "agent_display_name",      # Agent name shown to members: "ARIIA"
    "studio_locale",           # BCP-47 locale: "de-DE" | "en-US"
    "studio_timezone",         # IANA tz: "Europe/Berlin"
    "studio_emergency_number", # Emergency services: "112" | "911"
    "studio_address",          # Physical address shown in replies
    "sales_prices_text",       # Markdown tariff/price list
    "sales_retention_rules",   # Markdown retention strategy rules
    "medic_disclaimer_text",   # Legal health disclaimer appended to medic replies
    "persona_bio_text",        # Agent persona/character description
]

# Default values — new tenants start here and configure via Admin UI.
# New tenants start with empty strings and configure via the Admin UI.
PROMPT_SETTINGS_DEFAULTS: dict[str, str] = {
    "studio_name": "Mein Studio",
    "studio_short_name": "Studio",
    "agent_display_name": "ARIIA",
    "studio_locale": "de-DE",
    "studio_timezone": "Europe/Berlin",
    "studio_emergency_number": "112",
    "studio_address": "",
    "sales_prices_text": (
        "Tarife:\n"
        "- Flex: 29,90\u20ac/Monat (monatlich k\u00fcndbar)\n"
        "- Standard: 24,90\u20ac/Monat (12 Monate)\n"
        "- Premium: 39,90\u20ac/Monat (Kurse + Sauna + Personal Training)"
    ),
    "sales_retention_rules": (
        "RETENTION-REGELN:\n"
        "1. Inaktiv (>30 Tage): Biete kostenlosen Trainer-Check-Up an.\n"
        "2. Sehr aktiv (>2x/Woche): Biete Premium-Upgrade an.\n"
        "3. K\u00fcndigungswunsch: Pr\u00fcfe Status und frage nach dem Grund."
    ),
    "medic_disclaimer_text": (
        "\u26a95\ufe0f _Ich bin kein Arzt und kein Ersatz f\u00fcr medizinische Beratung. "
        "Bei echten Beschwerden bitte immer einen Arzt aufsuchen!_"
    ),
    "persona_bio_text": (
        "Pers\u00f6nlichkeit: Cool, motivierend, direkt, 'No Excuses', leicht humorvoll. "
        "Sprache: Deutsch (prim\u00e4r), kurze S\u00e4tze. "
        "Du bist wie ein cooler Kumpel im Gym, nicht wie ein Kundenservice-Bot."
    ),
}


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
            logger.wariiang("prompt_builder.format_failed", error=str(exc))
            return template

    # Convenience accessors
    @property
    def studio_name(self) -> str:
        return self._get("studio_name")

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
            logger.wariiang("prompt_builder.seed_failed", key=key, error=str(exc))
