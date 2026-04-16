"""Legacy gateway entrypoint kept as a thin compatibility wrapper.

Epic 4 moves application assembly to `app.edge.app`. This module now preserves
legacy imports (`app.gateway.main:app`) while keeping only the small set of
compatibility exports and routes that existing tests and integrations still use.
"""

from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException
from app.edge.app import create_app
from app.edge.health import build_legacy_health
from app.core.module_registry import registry
from app.gateway.dependencies import active_websockets
from app.gateway.routers.voice import router as legacy_voice_router
from app.gateway.routers.webhooks import webhook_telegram_tenant
from app.gateway.routers.websocket import router as websocket_router
from app.gateway.utils import broadcast_to_admins
from config.settings import Settings, get_settings


class _LegacySettingsProxy:
    def __init__(self, base: Settings) -> None:
        object.__setattr__(self, "_base", base)
        object.__setattr__(
            self,
            "_extra",
            {
                "telegram_webhook_secret": "",
                "meta_app_secret": "",
                "meta_verify_token": "",
            },
        )

    def __getattr__(self, name: str) -> Any:
        extra = object.__getattribute__(self, "_extra")
        if name in extra:
            return extra[name]
        return getattr(object.__getattribute__(self, "_base"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        extra = object.__getattribute__(self, "_extra")
        if name in extra:
            extra[name] = value
            return
        setattr(object.__getattribute__(self, "_base"), name, value)


settings = _LegacySettingsProxy(get_settings())
app = create_app()


class _WhatsAppVerifier:
    """Compatibility proxy for legacy tests that patch the app secret."""

    def __init__(self) -> None:
        self._app_secret: str = ""


_whatsapp_verifier = _WhatsAppVerifier()


def _has_route(app_instance: Any, path: str) -> bool:
    return any(getattr(route, "path", None) == path for route in app_instance.routes)


def _has_route_on_default_app(path: str) -> bool:
    return any(getattr(route, "path", None) == path for route in app.routes)


def _has_active_module(name: str) -> bool:
    return any(module.name == name for module in registry.get_active_modules())


def apply_legacy_compat_routes(app_instance: Any) -> Any:
    if settings.enable_legacy_ws_control and not _has_route(app_instance, "/ws/control"):
        app_instance.include_router(websocket_router)

    if (
        settings.enable_legacy_voice_routes
        and _has_active_module("voice_pipeline")
        and not _has_route(app_instance, "/voice/incoming/{tenant_slug}")
    ):
        app_instance.include_router(legacy_voice_router)

    if settings.enable_legacy_health_endpoint and not _has_route(app_instance, "/health"):
        @app_instance.get("/health")
        async def health_check() -> dict[str, Any]:
            """Legacy flat health endpoint retained for backwards compatibility."""
            return await build_legacy_health()

    if settings.enable_legacy_telegram_webhook_alias and not _has_route(app_instance, "/webhook/telegram"):
        @app_instance.post("/webhook/telegram")
        async def telegram_webhook_legacy(
            payload: dict[str, Any],
            x_telegram_webhook_secret: str | None = Header(default=None, alias="x-telegram-webhook-secret"),
        ) -> dict[str, str]:
            """Legacy single-tenant alias retained for existing tests/integrations."""
            if settings.telegram_webhook_secret:
                if (x_telegram_webhook_secret or "").strip() != settings.telegram_webhook_secret.strip():
                    raise HTTPException(status_code=403, detail="Invalid webhook secret")
            return await webhook_telegram_tenant(
                tenant_slug="system",
                payload=payload,
                x_telegram_webhook_secret=x_telegram_webhook_secret,
            )

    return app_instance


apply_legacy_compat_routes(app)
