"""ARIIA v2.2 – Analytics Processing Worker.

Continuously reads tracking events from the Redis queue and
processes them via the AnalyticsProcessor. Runs as a dedicated
Docker container (ariia_analytics_worker).

@ARCH: Campaign Refactoring Phase 3, Task 3.4
"""
import json
import os
import sys
import time

import structlog

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = structlog.get_logger()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://ariia:ariia_dev_password@ariia-postgres:5432/ariia",
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://ariia-redis:6379/0")
REDIS_QUEUE_KEY = "campaign:analytics:events"
BATCH_SIZE = int(os.environ.get("ANALYTICS_BATCH_SIZE", "50"))
POLL_INTERVAL = float(os.environ.get("ANALYTICS_POLL_INTERVAL", "2.0"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=3)
SessionLocal = sessionmaker(bind=engine)


def get_redis():
    """Create a Redis connection."""
    import redis
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def process_batch(redis_client, processor):
    """Read and process a batch of events from the Redis queue."""
    from app.campaign_engine.analytics_processor import AnalyticsProcessor

    db = SessionLocal()
    processed = 0
    errors = 0

    try:
        for _ in range(BATCH_SIZE):
            raw = redis_client.lpop(REDIS_QUEUE_KEY)
            if not raw:
                break

            try:
                event = json.loads(raw)
                if processor.process_event(db, event):
                    processed += 1
                else:
                    errors += 1
            except json.JSONDecodeError:
                logger.warning("analytics_worker.invalid_json", raw=raw[:200])
                errors += 1
            except Exception as e:
                logger.error("analytics_worker.event_error", error=str(e))
                errors += 1
                db.rollback()

    except Exception as e:
        logger.error("analytics_worker.batch_error", error=str(e))
    finally:
        db.close()

    return processed, errors


def main():
    """Main entry point – continuously processes events from Redis."""
    from app.campaign_engine.analytics_processor import AnalyticsProcessor

    logger.info(
        "analytics_worker.started",
        database=DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "configured",
        redis=REDIS_URL.split("@")[-1] if "@" in REDIS_URL else REDIS_URL,
        batch_size=BATCH_SIZE,
        poll_interval=POLL_INTERVAL,
    )

    redis_client = get_redis()
    processor = AnalyticsProcessor()

    total_processed = 0
    total_errors = 0
    last_report = time.time()

    while True:
        try:
            # Check queue length
            queue_len = redis_client.llen(REDIS_QUEUE_KEY)

            if queue_len > 0:
                processed, errors = process_batch(redis_client, processor)
                total_processed += processed
                total_errors += errors

                if processed > 0:
                    logger.debug(
                        "analytics_worker.batch_done",
                        processed=processed,
                        errors=errors,
                        queue_remaining=queue_len - processed,
                    )

            # Periodic status report (every 5 minutes)
            now = time.time()
            if now - last_report >= 300:
                logger.info(
                    "analytics_worker.status",
                    total_processed=total_processed,
                    total_errors=total_errors,
                    queue_length=redis_client.llen(REDIS_QUEUE_KEY),
                )
                last_report = now

            # Sleep if queue was empty or small
            if queue_len <= BATCH_SIZE:
                time.sleep(POLL_INTERVAL)

        except Exception as e:
            logger.error("analytics_worker.loop_error", error=str(e))
            time.sleep(5)


if __name__ == "__main__":
    main()
