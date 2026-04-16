"""Campaign domain runtime assembly."""

from __future__ import annotations

from typing import Any

from app.core.module_registry import WorkerDefinition


def get_campaign_routers() -> list[Any]:
    from app.gateway.routers.analytics_tracking import router as tracking
    from app.gateway.routers.campaign_offers import router as offers
    from app.gateway.routers.campaign_templates import router as templates
    from app.gateway.routers.campaign_webhooks import router as webhooks
    from app.gateway.routers.campaigns import router as campaigns
    from app.gateway.routers.public_subscribe import router as public_subscribe

    return [
        campaigns,
        templates,
        offers,
        webhooks,
        public_subscribe,
        tracking,
    ]


def get_campaign_workers() -> list[WorkerDefinition]:
    return [
        WorkerDefinition(
            name="campaign",
            module_path="app.worker.campaign_tasks",
            class_name="CampaignWorkerSettings",
        ),
        WorkerDefinition(
            name="analytics",
            module_path="app.worker.campaign_tasks",
            class_name="CampaignWorkerSettings",
        ),
        WorkerDefinition(
            name="automation",
            module_path="app.worker.campaign_tasks",
            class_name="CampaignWorkerSettings",
        ),
    ]


__all__ = ["get_campaign_routers", "get_campaign_workers"]
