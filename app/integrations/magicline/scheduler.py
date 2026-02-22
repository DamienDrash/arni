from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone

import structlog

from app.core.db import SessionLocal
from app.core.models import StudioMember, Tenant
from app.gateway.persistence import persistence
from app.integrations.magicline.member_enrichment import enrich_member
from app.integrations.magicline.members_sync import sync_members_from_magicline

logger = structlog.get_logger()


def _enrich_tenant_members(tenant_id: int) -> None:
    """Background enrichment: fetch check-in stats + bookings for all tenant members."""
    db = SessionLocal()
    try:
        ids = [
            row.customer_id
            for row in db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id).all()
        ]
    finally:
        db.close()

    ok = err = skipped = 0
    for cid in ids:
        try:
            result = enrich_member(cid, force=False, tenant_id=tenant_id)
            if result.get("cached"):
                skipped += 1
            elif "error" in result:
                err += 1
            else:
                ok += 1
        except Exception as e:
            logger.error("magicline.scheduler.enrich_member_failed", tenant_id=tenant_id, customer_id=cid, error=str(e))
            err += 1

    logger.info(
        "magicline.scheduler.enrich_completed",
        tenant_id=tenant_id,
        ok=ok,
        skipped=skipped,
        err=err,
        total=len(ids),
    )


def _field_match(expr: str, value: int) -> bool:
    token = (expr or "*").strip()
    if token == "*":
        return True
    if token.startswith("*/"):
        try:
            step = int(token[2:])
            return step > 0 and (value % step == 0)
        except Exception:
            return False
    try:
        return int(token) == value
    except Exception:
        return False


def _cron_due_utc(expr: str, now: datetime) -> bool:
    parts = [p.strip() for p in (expr or "").split()]
    if len(parts) != 5:
        return False
    minute, hour, _dom, _month, _dow = parts
    return _field_match(minute, now.minute) and _field_match(hour, now.hour)


def _active_tenant_ids() -> list[int]:
    db = SessionLocal()
    try:
        rows = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
        return [int(r.id) for r in rows]
    finally:
        db.close()


async def magicline_sync_scheduler_loop() -> None:
    logger.info("magicline.scheduler.started")
    last_tick_by_tenant: dict[int, str] = {}
    while True:
        now = datetime.now(timezone.utc)
        tick_key = now.strftime("%Y-%m-%dT%H:%M")
        try:
            for tenant_id in _active_tenant_ids():
                enabled = (
                    persistence.get_setting("magicline_auto_sync_enabled", "false", tenant_id=tenant_id)
                    or "false"
                ).strip().lower() in {"1", "true", "yes", "on"}
                if not enabled:
                    continue
                cron = persistence.get_setting("magicline_auto_sync_cron", "0 */6 * * *", tenant_id=tenant_id) or "0 */6 * * *"
                last_sync_at = (persistence.get_setting("magicline_last_sync_at", "", tenant_id=tenant_id) or "").strip()
                never_synced = not last_sync_at
                # Run immediately if never synced; otherwise only on cron schedule
                if not never_synced and not _cron_due_utc(cron, now):
                    continue
                if last_tick_by_tenant.get(tenant_id) == tick_key:
                    continue

                last_tick_by_tenant[tenant_id] = tick_key
                started_at = datetime.now(timezone.utc).isoformat()
                try:
                    result = await asyncio.to_thread(sync_members_from_magicline, tenant_id)
                    persistence.upsert_setting("magicline_last_sync_at", started_at, tenant_id=tenant_id)
                    persistence.upsert_setting("magicline_last_sync_status", "ok", tenant_id=tenant_id)
                    persistence.upsert_setting("magicline_last_sync_error", "", tenant_id=tenant_id)
                    logger.info("magicline.scheduler.synced", tenant_id=tenant_id, result=result)
                    # Kick off enrichment in background — non-blocking, respects 6h TTL cache
                    threading.Thread(
                        target=_enrich_tenant_members,
                        args=(tenant_id,),
                        daemon=True,
                        name=f"enrich-t{tenant_id}",
                    ).start()
                    logger.info("magicline.scheduler.enrich_started", tenant_id=tenant_id)
                except Exception as e:
                    detail = f"{e.__class__.__name__}: {e}"
                    persistence.upsert_setting("magicline_last_sync_at", started_at, tenant_id=tenant_id)
                    persistence.upsert_setting("magicline_last_sync_status", "error", tenant_id=tenant_id)
                    persistence.upsert_setting("magicline_last_sync_error", detail[:1200], tenant_id=tenant_id)
                    logger.error("magicline.scheduler.sync_failed", tenant_id=tenant_id, error=detail)
        except Exception as e:
            logger.error("magicline.scheduler.loop_failed", error=str(e))
        await asyncio.sleep(60)

