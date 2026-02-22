"""ARIIA – Jinja2 Prompt Engine (S2.5).

Renders LLM system prompts from Jinja2 templates with per-tenant override support.

Template resolution order:
1. data/knowledge/tenants/{tenant_slug}/prompts/{agent}/system.j2   (tenant custom)
2. app/prompts/templates/{agent}/system.j2                           (system default)

Usage:
    from app.prompts.engine import get_engine
    from app.prompts.context import build_tenant_context
    from app.gateway.persistence import persistence

    engine = get_engine()
    ctx = build_tenant_context(persistence, tenant_id=7)
    prompt = engine.render_for_tenant("sales/system.j2", tenant_slug="acme", **ctx)
"""

from __future__ import annotations

import structlog
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger()

# Base path for system-wide default templates
_TEMPLATE_BASE = Path(__file__).parent / "templates"

# Base path for per-tenant template overrides (runtime data dir)
_TENANT_DATA_BASE = Path(__file__).resolve().parents[2] / "data" / "knowledge" / "tenants"


class PromptEngine:
    """Jinja2-backed prompt renderer with per-tenant template override support.

    Responsibilities:
    1. Load templates from app/prompts/templates (system defaults).
    2. Check per-tenant override in data/knowledge/tenants/{slug}/prompts/ first.
    3. Render final prompt string with the provided context dict.
    """

    def __init__(self, template_dir: str | Path = _TEMPLATE_BASE) -> None:
        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(enabled_extensions=()),  # disabled for LLM prompts
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render(self, template_name: str, **context: Any) -> str:
        """Render a system default template.

        Args:
            template_name: Relative path, e.g. "sales/system.j2".
            **context: Variables injected into the template.
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as exc:
            logger.error("prompt_engine.render_failed", template=template_name, error=str(exc))
            return f"[PromptEngine error rendering '{template_name}': {exc}]"

    def render_for_tenant(self, template_name: str, tenant_slug: str, **context: Any) -> str:
        """Render a template with per-tenant override support.

        Checks data/knowledge/tenants/{tenant_slug}/prompts/{template_name} first.
        Falls back to the system default template.

        Args:
            template_name: Relative path, e.g. "sales/system.j2".
            tenant_slug: The tenant's URL slug (used to locate override files).
            **context: Variables injected into the template.
        """
        if tenant_slug:
            tenant_override = _TENANT_DATA_BASE / tenant_slug / "prompts" / template_name
            if tenant_override.exists():
                try:
                    raw = tenant_override.read_text(encoding="utf-8")
                    return self.env.from_string(raw).render(**context)
                except Exception as exc:
                    logger.warning(
                        "prompt_engine.tenant_override_failed",
                        template=template_name,
                        tenant=tenant_slug,
                        error=str(exc),
                    )
                    # Fall through to system default

        return self.render(template_name, **context)

    def tenant_template_path(self, template_name: str, tenant_slug: str) -> Path:
        """Return the expected per-tenant override path for a template."""
        return _TENANT_DATA_BASE / tenant_slug / "prompts" / template_name

    def default_template_path(self, template_name: str) -> Path:
        """Return the system default path for a template."""
        return self.template_dir / template_name


# Module-level singleton
_engine: PromptEngine | None = None


def get_engine() -> PromptEngine:
    """Return the module-level PromptEngine singleton."""
    global _engine
    if _engine is None:
        _engine = PromptEngine(_TEMPLATE_BASE)
    return _engine
