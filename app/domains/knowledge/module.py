"""Knowledge domain runtime assembly."""

from __future__ import annotations

from typing import Any

from app.core.module_registry import WorkerDefinition


def get_knowledge_routers() -> list[Any]:
    from app.gateway.routers.ingestion import router as ingestion
    from app.gateway.routers.media import router as media

    return [ingestion, media]


def get_knowledge_workers() -> list[WorkerDefinition]:
    return [
        WorkerDefinition(
            name="ingestion",
            module_path="app.worker.settings",
            class_name="WorkerSettings",
        )
    ]


__all__ = ["get_knowledge_routers", "get_knowledge_workers"]
