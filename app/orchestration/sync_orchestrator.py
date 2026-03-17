"""ARIIA v2.1 – Integration Sync Orchestrator.

Unified scheduler that replaces separate SyncScheduler and
MagiclineScheduler background loops with a single orchestrated loop.

Runs as a long-lived background task in the Gateway lifespan.
"""

from __future__ import annotations

import asyncio
import structlog

logger = structlog.get_logger()


class IntegrationSyncOrchestrator:
    """Unified integration sync scheduler.

    Delegates to existing sync implementations but provides a single
    control point for scheduling, concurrency, and monitoring.
    """

    def __init__(self):
        self._running = False

    async def run_forever(self, interval_seconds: int = 60) -> None:
        """Main loop: periodically trigger all due integration syncs.

        Args:
            interval_seconds: Seconds between sync checks (default: 60).
        """
        self._running = True
        logger.info(
            "sync_orchestrator.started",
            interval=interval_seconds,
        )

        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error("sync_orchestrator.tick_failed", error=str(e))

            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        self._running = False
        logger.info("sync_orchestrator.stopped")

    async def _tick(self) -> None:
        """Execute one sync cycle: contact syncs + Magicline syncs."""
        # 1. Contact integration syncs (via SyncScheduler)
        try:
            from app.contacts.sync_scheduler import sync_scheduler

            if not sync_scheduler.is_running:
                sync_scheduler.start()
        except Exception as e:
            logger.warning("sync_orchestrator.contact_sync_error", error=str(e))

        # 2. Magicline member sync is handled by its own scheduler loop
        # (magicline_sync_scheduler_loop) registered separately in main.py.
        # Future: migrate Magicline cron logic into this orchestrator.


# Singleton
_instance: IntegrationSyncOrchestrator | None = None


def get_integration_sync_orchestrator() -> IntegrationSyncOrchestrator:
    global _instance
    if _instance is None:
        _instance = IntegrationSyncOrchestrator()
    return _instance
