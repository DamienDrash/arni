"""ARIIA v1.4 – Platform Maintenance & Data Retention.

Handles periodic cleanup of old messages and audit logs based on 
platform-wide retention policies.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
import structlog

from app.core.db import SessionLocal
from app.core.models import ChatMessage, AuditLog
from app.gateway.persistence import persistence
from app.memory.librarian import Librarian

logger = structlog.get_logger()

async def run_data_retention_cleanup() -> dict:
    """Purge old data across all tenants based on platform settings."""
    db = SessionLocal()
    results = {"messages_deleted": 0, "audit_deleted": 0}
    
    try:
        # 1. Archive old sessions via Librarian (Titan Upgrade)
        librarian = Librarian()
        await librarian.run_archival_cycle()
        
        # 2. Load retention settings from system tenant
        # Default to 90 days for messages and 365 for audit if not set
        msg_days = int(persistence.get_setting("platform_data_retention_days", "90") or 90)
        audit_days = int(persistence.get_setting("platform_audit_retention_days", "365") or 365)
        
        now = datetime.now(timezone.utc)
        msg_cutoff = now - timedelta(days=msg_days)
        audit_cutoff = now - timedelta(days=audit_days)
        
        # 3. Cleanup Chat Messages
        msg_q = db.query(ChatMessage).filter(ChatMessage.timestamp < msg_cutoff)
        results["messages_deleted"] = msg_q.delete(synchronize_session=False)
        
        # 4. Cleanup Audit Logs
        audit_q = db.query(AuditLog).filter(AuditLog.created_at < audit_cutoff)
        results["audit_deleted"] = audit_q.delete(synchronize_session=False)
        
        db.commit()
        
        if results["messages_deleted"] > 0 or results["audit_deleted"] > 0:
            logger.info(
                "maintenance.retention_cleanup_completed", 
                **results,
                msg_days=msg_days,
                audit_days=audit_days
            )
            
    except Exception as e:
        db.rollback()
        logger.error("maintenance.retention_cleanup_failed", error=str(e))
    finally:
        db.close()
        
    return results

async def maintenance_loop():
    """Background loop that runs maintenance tasks once every 24 hours."""
    logger.info("maintenance.loop_started")
    while True:
        await run_data_retention_cleanup()
        # Sleep for 24 hours
        await asyncio.sleep(86400)
