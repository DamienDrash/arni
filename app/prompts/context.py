"""ARIIA – Jinja2 Tenant Context Builder (S2.5).

Provides a unified dict of tenant-specific values for Jinja2 template rendering.
Reads from the Settings table via persistence at call time — never cached.

Usage:
    from app.prompts.context import build_tenant_context
    from app.gateway.persistence import persistence

    ctx = build_tenant_context(persistence, tenant_id=7)
    rendered = engine.render_for_tenant("sales/system.j2", tenant_slug, **ctx)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import structlog

from app.core.prompt_builder import PROMPT_SETTINGS_DEFAULTS, PROMPT_SETTINGS_KEYS

logger = structlog.get_logger()

# All integration IDs that may appear as flags in the prompt context.
# This list is intentionally broad to cover current and future integrations.
KNOWN_INTEGRATION_IDS: list[str] = [
    "acuity",
    "calcom",
    "calendly",
    "deepgram",
    "elevenlabs",
    "facebook",
    "google_analytics",
    "google_business",
    "hubspot",
    "instagram",
    "magicline",
    "mollie",
    "openai_tts",
    "paypal",
    "postmark",
    "salesforce",
    "shopify",
    "sms",
    "smtp_email",
    "stripe",
    "telegram",
    "twilio_voice",
    "whatsapp",
    "woocommerce",
]


@dataclass
class IntegrationFlags:
    """Dynamic attribute container for integration enabled/disabled flags.

    Allows templates to use ``integrations.calendly_enabled``, etc.
    Unknown attributes return ``False`` by default.
    """

    _flags: dict[str, bool] = field(default_factory=dict)

    def __getattr__(self, name: str) -> bool:
        if name.startswith("_"):
            raise AttributeError(name)
        if name.endswith("_enabled"):
            return self._flags.get(name, False)
        return self._flags.get(f"{name}_enabled", False)

    def __repr__(self) -> str:
        enabled = [k for k, v in self._flags.items() if v]
        return f"IntegrationFlags(enabled={enabled})"

    def to_dict(self) -> dict[str, bool]:
        """Return all flags as a plain dict for serialization."""
        return dict(self._flags)


def _build_integration_flags(persistence: object, tenant_id: int) -> IntegrationFlags:
    """Build integration flags from the tenant's enabled integrations.

    Calls ``persistence.get_enabled_integrations(tenant_id)`` and creates
    a flag object where ``<integration_id>_enabled = True`` for each active
    integration and ``False`` for all others.
    """
    flags: dict[str, bool] = {}

    # Initialize all known integrations as disabled
    for integration_id in KNOWN_INTEGRATION_IDS:
        flags[f"{integration_id}_enabled"] = False

    # Enable the ones that are active for this tenant
    try:
        enabled_ids = persistence.get_enabled_integrations(tenant_id)  # type: ignore[attr-defined]
        for integration_id in enabled_ids:
            flags[f"{integration_id}_enabled"] = True
    except Exception as exc:
        logger.warning(
            "tenant_context.integration_flags_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    return IntegrationFlags(_flags=flags)


def build_tenant_context(persistence: object, tenant_id: int) -> dict[str, Any]:
    """Build a Jinja2 context dict from tenant settings.

    Includes all prompt setting keys plus convenience values like current_date.
    Unknown / unset keys fall back to PROMPT_SETTINGS_DEFAULTS.

    DYN-3: Now also includes an ``integrations`` object with boolean flags
    for each integration (e.g. ``integrations.calendly_enabled``).
    """
    ctx: dict[str, Any] = {key: PROMPT_SETTINGS_DEFAULTS.get(key, "") for key in PROMPT_SETTINGS_KEYS}
    ctx["current_date"] = date.today().isoformat()

    for key in PROMPT_SETTINGS_KEYS:
        try:
            val = persistence.get_setting(key, None, tenant_id=tenant_id)  # type: ignore[attr-defined]
            if val is not None:
                ctx[key] = str(val).strip()
        except Exception as exc:
            logger.warning("tenant_context.setting_load_failed", key=key, error=str(exc))

    # DYN-3: Integration flags for dynamic prompt rendering
    ctx["integrations"] = _build_integration_flags(persistence, tenant_id)

    # Also expose a flat list of enabled integration IDs for convenience
    try:
        ctx["enabled_integrations"] = persistence.get_enabled_integrations(tenant_id)  # type: ignore[attr-defined]
    except Exception:
        ctx["enabled_integrations"] = []

    return ctx
