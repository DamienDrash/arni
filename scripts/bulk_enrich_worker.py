import time
import structlog
from datetime import datetime, timezone, timedelta

from config.settings import get_settings
from app.core.db import SessionLocal
from app.core.models import StudioMember, Tenant
from app.gateway.persistence import persistence
from app.integrations.magicline.member_enrichment import enrich_member

logger = structlog.get_logger()

def queue_key(tid: int) -> str:
    return f"tenant:{tid}:enrich_queue"

def get_active_tenants():
    db = SessionLocal()
    try:
        return [t.id for t in db.query(Tenant).filter(Tenant.is_active.is_(True)).all()]
    finally:
        db.close()

def _populate_due_enrichments(r, tenant_id: int):
    # Every 6h for members with enriched_at < now - 24h
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        members = db.query(StudioMember).filter(
            StudioMember.tenant_id == tenant_id,
            (StudioMember.enriched_at < threshold) | (StudioMember.enriched_at.is_(None))
        ).all()
        ids = [m.customer_id for m in members]
        if ids:
            r.sadd(queue_key(tenant_id), *ids)
            logger.info("bulk_enrich.auto_queued", tenant_id=tenant_id, count=len(ids))
    finally:
        db.close()

def main():
    import redis
    logger.info("bulk_enrich_worker.started")
    r = redis.from_url(get_settings().redis_url, decode_responses=True)
    last_auto_check: dict[int, datetime] = {}

    while True:
        try:
            tenants = get_active_tenants()
            processed_any = False
            for tid in tenants:
                enabled = persistence.get_setting("magicline_auto_sync_enabled", "false", tenant_id=tid).lower() in ("true", "1")
                if not enabled:
                    continue
                
                # Check if we should auto-populate
                now = datetime.now(timezone.utc)
                if tid not in last_auto_check or (now - last_auto_check[tid]).total_seconds() > 3600 * 6:
                    if r.scard(queue_key(tid)) == 0:
                        _populate_due_enrichments(r, tid)
                        last_auto_check[tid] = now
                        
                # Process one member
                cid = r.spop(queue_key(tid))
                if cid:
                    try:
                        enrich_member(int(cid), force=False, tenant_id=tid)
                    except Exception as e:
                        logger.error("bulk_enrich.enrich_failed", tenant_id=tid, customer_id=cid, error=str(e))
                    time.sleep(6) # 10 req/minute per tenant
                    processed_any = True

            if not processed_any:
                time.sleep(10)
        except Exception as e:
            logger.error("bulk_enrich_worker.loop_failed", error=str(e))
            time.sleep(10)

if __name__ == "__main__":
    main()
