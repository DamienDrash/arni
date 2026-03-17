"""ARIIA v2.0 – Contact Sync Scheduler.

@ARCH: Contacts-Sync Refactoring, Phase 3
Manages periodic sync execution based on tenant integration schedules.

Responsibilities:
  - Check which integrations are due for sync
  - Execute syncs in order (respecting rate limits)
  - Handle retry logic for failed syncs
  - Provide status API for monitoring

Design:
  - Runs as a background task in the FastAPI event loop
  - Checks every 60 seconds for due integrations
  - Uses last_sync_at + sync_interval_minutes to determine next run
  - Respects enabled/disabled state
  - Logs all activity to sync_logs
"""

from __future__ import annotations

import asyncio
import json
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import and_

from app.core.db import SessionLocal
from app.core.advisory_locks import advisory_lock_or_skip
from app.core.integration_models import TenantIntegration, SyncSchedule

logger = structlog.get_logger()


class SyncScheduler:
    """Background scheduler for periodic contact syncs."""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 60  # seconds between checks
        self._max_concurrent = 3   # max concurrent syncs
        self._active_syncs: Dict[str, datetime] = {}
        self._retry_delays = [60, 300, 900, 3600]  # 1m, 5m, 15m, 1h
        self._stats = {
            "started_at": None,
            "last_check_at": None,
            "total_checks": 0,
            "total_syncs_triggered": 0,
            "total_syncs_failed": 0,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "is_running": self._running,
            "active_syncs": len(self._active_syncs),
            "active_sync_details": {
                k: v.isoformat() for k, v in self._active_syncs.items()
            },
        }

    def start(self) -> None:
        """Start the scheduler background task."""
        if self._running:
            logger.warning("sync_scheduler.already_running")
            return

        self._running = True
        self._stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("sync_scheduler.started", check_interval=self._check_interval)

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("sync_scheduler.stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_and_execute()
            except Exception as e:
                logger.error("sync_scheduler.loop_error", error=str(e), traceback=traceback.format_exc())

            await asyncio.sleep(self._check_interval)

    async def _check_and_execute(self) -> None:
        """Check for due integrations and execute syncs."""
        self._stats["last_check_at"] = datetime.now(timezone.utc).isoformat()
        self._stats["total_checks"] += 1

        due_integrations = self._get_due_integrations()

        if not due_integrations:
            return

        logger.info("sync_scheduler.found_due", count=len(due_integrations))

        # Limit concurrent syncs
        available_slots = self._max_concurrent - len(self._active_syncs)
        if available_slots <= 0:
            logger.debug("sync_scheduler.max_concurrent_reached", active=len(self._active_syncs))
            return

        for ti in due_integrations[:available_slots]:
            sync_key = f"{ti.tenant_id}:{ti.integration_id}"
            if sync_key in self._active_syncs:
                continue

            # Check advisory lock to prevent concurrent execution across workers
            db = SessionLocal()
            try:
                lock_key = f"sync:{ti.tenant_id}:{ti.integration_id}"
                with advisory_lock_or_skip(db, lock_key) as acquired:
                    if not acquired:
                        logger.debug(
                            "sync.skipped_lock",
                            tenant_id=ti.tenant_id,
                            integration_id=ti.integration_id,
                        )
                        continue
            finally:
                db.close()

            self._active_syncs[sync_key] = datetime.now(timezone.utc)
            asyncio.create_task(self._execute_sync(ti, sync_key))

    def _get_due_integrations(self) -> List[TenantIntegration]:
        """Query DB for integrations that are due for sync."""
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)

            integrations = (
                db.query(TenantIntegration)
                .filter(
                    TenantIntegration.enabled == True,
                    TenantIntegration.status.in_(["connected", "configured", "error"]),
                )
                .all()
            )

            due = []
            for ti in integrations:
                interval = timedelta(minutes=ti.sync_interval_minutes or 60)

                if ti.last_sync_at is None:
                    # Never synced – due immediately
                    due.append(ti)
                    continue

                # Ensure last_sync_at is timezone-aware
                last_sync = ti.last_sync_at
                if last_sync.tzinfo is None:
                    last_sync = last_sync.replace(tzinfo=timezone.utc)

                next_sync = last_sync + interval
                if now >= next_sync:
                    # Check retry backoff for error state
                    if ti.last_sync_status == "error":
                        retry_count = self._get_consecutive_errors(ti)
                        if retry_count > 0:
                            delay_idx = min(retry_count - 1, len(self._retry_delays) - 1)
                            retry_delay = timedelta(seconds=self._retry_delays[delay_idx])
                            if now < last_sync + retry_delay:
                                continue  # Not yet time to retry

                    due.append(ti)

            return due

        except Exception as e:
            logger.error("sync_scheduler.query_error", error=str(e))
            return []
        finally:
            db.close()

    def _get_consecutive_errors(self, ti: TenantIntegration) -> int:
        """Count consecutive error syncs for retry backoff."""
        from app.core.integration_models import SyncLog
        db = SessionLocal()
        try:
            from sqlalchemy import desc
            logs = (
                db.query(SyncLog)
                .filter(
                    SyncLog.tenant_id == ti.tenant_id,
                    SyncLog.integration_id == ti.integration_id,
                )
                .order_by(desc(SyncLog.started_at))
                .limit(5)
                .all()
            )
            count = 0
            for log in logs:
                if log.status == "error":
                    count += 1
                else:
                    break
            return count
        except Exception:
            return 0
        finally:
            db.close()

    async def _execute_sync(self, ti: TenantIntegration, sync_key: str) -> None:
        """Execute a single sync and clean up."""
        try:
            logger.info(
                "sync_scheduler.executing",
                tenant_id=ti.tenant_id,
                integration_id=ti.integration_id,
            )

            from app.contacts.sync_core import sync_core

            result = await sync_core.run_sync(
                tenant_id=ti.tenant_id,
                integration_id=ti.integration_id,
                triggered_by="scheduler",
            )

            self._stats["total_syncs_triggered"] += 1

            if not result.get("success"):
                self._stats["total_syncs_failed"] += 1
                logger.warning(
                    "sync_scheduler.sync_failed",
                    tenant_id=ti.tenant_id,
                    integration_id=ti.integration_id,
                    error=result.get("error"),
                )
            else:
                logger.info(
                    "sync_scheduler.sync_completed",
                    tenant_id=ti.tenant_id,
                    integration_id=ti.integration_id,
                    records_created=result.get("records_created", 0),
                    records_updated=result.get("records_updated", 0),
                )

        except Exception as e:
            self._stats["total_syncs_failed"] += 1
            logger.error(
                "sync_scheduler.sync_error",
                tenant_id=ti.tenant_id,
                integration_id=ti.integration_id,
                error=str(e),
            )
        finally:
            self._active_syncs.pop(sync_key, None)


# Singleton
sync_scheduler = SyncScheduler()


def start_sync_scheduler() -> None:
    """Start the sync scheduler. Called from app startup."""
    try:
        sync_scheduler.start()
    except Exception as e:
        logger.error("sync_scheduler.start_failed", error=str(e))


def stop_sync_scheduler() -> None:
    """Stop the sync scheduler. Called from app shutdown."""
    sync_scheduler.stop()
