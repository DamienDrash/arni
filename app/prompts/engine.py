"""ARIIA – Prompt Engine (Refactored for AI Config Management).

Renders LLM system prompts with hierarchical resolution:

1. DB Prompt Registry (ai_prompt_deployments → ai_prompt_versions)
   - Tenant-specific deployment for the environment
   - Platform default deployment for the environment
   - Latest published version
2. Filesystem fallback (backward compatibility)
   - data/knowledge/tenants/{tenant_slug}/prompts/{agent}/system.j2
   - app/prompts/templates/{agent}/system.j2

Usage:
    from app.prompts.engine import get_engine
    from app.prompts.context import build_tenant_context
    from app.gateway.persistence import persistence

    engine = get_engine()
    ctx = build_tenant_context(persistence, tenant_id=7)
    prompt = engine.render_for_tenant("sales/system.j2", tenant_slug="acme", tenant_id=7, **ctx)
"""

from __future__ import annotations

import structlog
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger()

# Base path for system-wide default templates (filesystem fallback)
_TEMPLATE_BASE = Path(__file__).parent / "templates"

# Base path for per-tenant template overrides (runtime data dir)
_TENANT_DATA_BASE = Path(__file__).resolve().parents[2] / "data" / "knowledge" / "tenants"


class PromptEngine:
    """Jinja2-backed prompt renderer with DB-first resolution.

    Resolution hierarchy:
    1. DB Prompt Registry (via AIConfigService.resolve_prompt)
    2. Per-tenant filesystem override
    3. System default filesystem template

    The engine maintains full backward compatibility with existing callers.
    """

    def __init__(self, template_dir: str | Path = _TEMPLATE_BASE) -> None:
        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render(self, template_name: str, **context: Any) -> str:
        """Render a system default template from filesystem.

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

    def render_for_tenant(
        self,
        template_name: str,
        tenant_slug: str,
        *,
        tenant_id: Optional[int] = None,
        environment: str = "production",
        **context: Any,
    ) -> str:
        """Render a template with hierarchical resolution.

        Resolution order:
        1. DB Prompt Registry (tenant-specific → platform default → latest published)
        2. Per-tenant filesystem override
        3. System default filesystem template

        Args:
            template_name: Relative path, e.g. "sales/system.j2".
            tenant_slug: The tenant's URL slug.
            tenant_id: The tenant's database ID (for DB resolution).
            environment: Deployment environment (dev/staging/production).
            **context: Variables injected into the template.
        """
        # ── Step 1: Try DB Prompt Registry ────────────────────────────────
        if tenant_id:
            db_content = self._resolve_from_db(template_name, tenant_id, environment)
            if db_content:
                try:
                    return self.env.from_string(db_content).render(**context)
                except Exception as exc:
                    logger.warning(
                        "prompt_engine.db_render_failed",
                        template=template_name,
                        tenant_id=tenant_id,
                        error=str(exc),
                    )
                    # Fall through to filesystem

        # ── Step 2: Try per-tenant filesystem override ────────────────────
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

        # ── Step 3: System default filesystem template ────────────────────
        return self.render(template_name, **context)

    def _resolve_from_db(
        self,
        template_name: str,
        tenant_id: int,
        environment: str = "production",
    ) -> Optional[str]:
        """Resolve prompt content from the DB Prompt Registry.

        Converts template_name (e.g. "sales/system.j2") to a slug (e.g. "sales/system").
        """
        try:
            from app.shared.db import open_session
            from app.ai_config.service import AIConfigService

            # Convert filename to slug: "sales/system.j2" → "sales/system"
            slug = template_name.replace(".j2", "").replace(".jinja2", "")

            db = open_session()
            try:
                svc = AIConfigService(db)
                version = svc.resolve_prompt(slug, tenant_id=tenant_id, environment=environment)
                if version and version.content:
                    logger.debug(
                        "prompt_engine.db_resolved",
                        slug=slug,
                        version=version.version,
                        tenant_id=tenant_id,
                    )
                    return version.content
            finally:
                db.close()
        except Exception as exc:
            logger.warning("prompt_engine.db_resolve_failed", template=template_name, error=str(exc))

        return None

    def render_from_string(self, content: str, **context: Any) -> str:
        """Render a prompt from a raw string template.

        Useful for testing and preview functionality.
        """
        try:
            return self.env.from_string(content).render(**context)
        except Exception as exc:
            logger.error("prompt_engine.string_render_failed", error=str(exc))
            return f"[PromptEngine error: {exc}]"

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
