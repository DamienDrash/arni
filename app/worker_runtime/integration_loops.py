"""Long-running integration scheduler entrypoints for the worker runtime."""

from __future__ import annotations

from app.worker_runtime.loop_supervisor import run_supervised_loop


async def run_magicline_sync_scheduler_forever() -> None:
    from app.integrations.magicline.scheduler import magicline_sync_scheduler_loop

    await run_supervised_loop("magicline-sync-scheduler", magicline_sync_scheduler_loop)
