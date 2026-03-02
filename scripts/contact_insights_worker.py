"""ARIIA v2.4 – Contact Insights Worker.

Runs once daily (or on demand) to compute channel affinity and optimal
send times for all contacts across all tenants.

This worker:
1. Iterates over all active tenants
2. For each tenant, runs ContactInsightsEngine.compute_all()
3. Logs results and sleeps until the next scheduled run

Usage:
    python scripts/contact_insights_worker.py

Environment:
    DATABASE_URL: PostgreSQL connection string
    INSIGHTS_INTERVAL_HOURS: Hours between runs (default: 24)
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

import structlog

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.campaign_engine.contact_insights import ContactInsightsEngine

logger = structlog.get_logger("contact_insights_worker")

INTERVAL_HOURS = int(os.getenv("INSIGHTS_INTERVAL_HOURS", "24"))


def run_insights_cycle():
    """Run a single insights computation cycle for all tenants."""
    db = SessionLocal()
    try:
        # Get all active tenants
        from sqlalchemy import text
        result = db.execute(text("SELECT id, name FROM tenants WHERE is_active = true"))
        tenants = result.fetchall()

        total_stats = {"tenants": 0, "processed": 0, "updated": 0, "errors": 0}

        for tenant_id, tenant_name in tenants:
            logger.info("insights_tenant_start", tenant_id=tenant_id, tenant_name=tenant_name)
            engine = ContactInsightsEngine(db)
            stats = engine.compute_all(tenant_id)

            total_stats["tenants"] += 1
            total_stats["processed"] += stats.get("processed", 0)
            total_stats["updated"] += stats.get("updated", 0)
            total_stats["errors"] += stats.get("errors", 0)

        logger.info("insights_cycle_complete", **total_stats)

    except Exception as e:
        logger.error("insights_cycle_error", error=str(e))
    finally:
        db.close()


def main():
    """Main loop: run insights, then sleep until next scheduled run."""
    logger.info(
        "contact_insights_worker_started",
        interval_hours=INTERVAL_HOURS,
    )

    while True:
        start = datetime.now(timezone.utc)
        logger.info("insights_cycle_start", timestamp=start.isoformat())

        try:
            run_insights_cycle()
        except Exception as e:
            logger.error("insights_cycle_fatal", error=str(e))

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        sleep_seconds = max(60, INTERVAL_HOURS * 3600 - elapsed)

        logger.info(
            "insights_sleeping",
            elapsed_seconds=round(elapsed, 1),
            sleep_hours=round(sleep_seconds / 3600, 1),
            next_run=(datetime.now(timezone.utc).timestamp() + sleep_seconds),
        )
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
