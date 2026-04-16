"""Support domain runtime assembly.

Keeps the active support-core HTTP surface in one place so the edge registry
does not need to know individual gateway/contact router details.
"""

from __future__ import annotations

from typing import Any

from app.core.module_registry import WorkerDefinition


def get_support_routers() -> list[Any]:
    from app.contacts.router import admin_router as contacts_admin
    from app.contacts.router import router as contacts
    from app.gateway.routers.agent_teams import router as teams
    from app.gateway.routers.chats import router as chats
    from app.gateway.routers.consent import router as consent
    from app.gateway.routers.contact_sync_api import router as sync
    from app.gateway.routers.contact_sync_api import webhook_router as sync_webhooks
    from app.gateway.routers.feedback import router as feedback
    from app.gateway.routers.members_crud import router as members

    return [
        contacts,
        contacts_admin,
        members,
        sync,
        sync_webhooks,
        chats,
        teams,
        feedback,
        consent,
    ]


def get_support_workers() -> list[WorkerDefinition]:
    return [
        WorkerDefinition(
            name="contact-sync-scheduler",
            module_path="app.worker_runtime.support_loops",
            class_name="run_contact_sync_scheduler_forever",
            kind="async",
        ),
        WorkerDefinition(
            name="member-memory-scheduler",
            module_path="app.worker_runtime.support_loops",
            class_name="run_member_memory_scheduler_forever",
            kind="async",
        ),
    ]


__all__ = ["get_support_routers", "get_support_workers"]
