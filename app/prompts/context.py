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

from datetime import date

import structlog

from app.core.prompt_builder import PROMPT_SETTINGS_DEFAULTS, PROMPT_SETTINGS_KEYS

logger = structlog.get_logger()


def build_tenant_context(persistence: object, tenant_id: int) -> dict[str, object]:
    """Build a Jinja2 context dict from tenant settings.

    Includes all prompt setting keys plus convenience values like current_date.
    Unknown / unset keys fall back to PROMPT_SETTINGS_DEFAULTS.
    """
    ctx: dict[str, object] = {key: PROMPT_SETTINGS_DEFAULTS.get(key, "") for key in PROMPT_SETTINGS_KEYS}
    ctx["current_date"] = date.today().isoformat()

    for key in PROMPT_SETTINGS_KEYS:
        try:
            val = persistence.get_setting(key, None, tenant_id=tenant_id)  # type: ignore[attr-defined]
            if val is not None:
                ctx[key] = str(val).strip()
        except Exception as exc:
            logger.wariiang("tenant_context.setting_load_failed", key=key, error=str(exc))

    return ctx
