"""Active integration runtime assembly."""

from __future__ import annotations

from typing import Any

from app.core.module_registry import WorkerDefinition


def get_magicline_routers() -> list[Any]:
    from app.platform.api.integrations import router as integrations_sync

    return [integrations_sync]


def get_magicline_workers() -> list[WorkerDefinition]:
    return [
        WorkerDefinition(
            name="magicline-sync-scheduler",
            module_path="app.worker_runtime.integration_loops",
            class_name="run_magicline_sync_scheduler_forever",
            kind="async",
        )
    ]


def get_whatsapp_routers() -> list[Any]:
    from app.gateway.routers.webhooks import router as wa_webhooks

    return [wa_webhooks]


def get_telegram_routers() -> list[Any]:
    return []


def get_calendly_routers() -> list[Any]:
    return []


__all__ = [
    "get_calendly_routers",
    "get_magicline_workers",
    "get_magicline_routers",
    "get_telegram_routers",
    "get_whatsapp_routers",
]
