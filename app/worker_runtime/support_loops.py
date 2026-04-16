"""Long-running support-side scheduler entrypoints for the worker runtime."""

from __future__ import annotations

import asyncio

from app.worker_runtime.loop_supervisor import run_supervised_loop

async def _contact_sync_scheduler_loop() -> None:
    from app.contacts.sync_scheduler import sync_scheduler

    sync_scheduler.start()
    try:
        await asyncio.Event().wait()
    finally:
        sync_scheduler.stop()


async def run_contact_sync_scheduler_forever() -> None:
    await run_supervised_loop("contact-sync-scheduler", _contact_sync_scheduler_loop)


async def run_member_memory_scheduler_forever() -> None:
    from app.memory.member_memory_analyzer import scheduler_loop

    await run_supervised_loop("member-memory-scheduler", scheduler_loop)
