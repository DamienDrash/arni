"""ARIIA v2.0 – arq Worker Settings.

Configures Redis connection and worker behaviour for the async task queue.
Priority queues are mapped to subscription plan tiers so enterprise tenants
receive faster processing.
"""
from __future__ import annotations

import urllib.parse

from arq.connections import RedisSettings

from config.settings import get_settings


def get_worker_redis_settings() -> RedisSettings:
    """Parse REDIS_URL from application settings and return arq RedisSettings."""
    settings = get_settings()
    parsed = urllib.parse.urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or "0"),
        password=parsed.password,
    )


class WorkerSettings:
    """arq WorkerSettings for the ARIIA ingestion worker process.

    ``functions`` is populated by ``ingestion_tasks.py`` at import time so
    that this module can be imported without triggering a circular dependency.
    """

    functions: list = []  # populated in ingestion_tasks.py
    redis_settings = get_worker_redis_settings()
    max_jobs = 20
    job_timeout = 600       # 10 minutes max per job
    keep_result = 3600      # keep results for 1 hour
    retry_jobs = True
    max_tries = 3

    queue_read_limit = 10

    # Priority-Queue mapping (plan slug → Redis queue name)
    QUEUE_MAP: dict[str, str] = {
        "enterprise": "ariia:ingest:priority_high",
        "pro": "ariia:ingest:priority_normal",
        "business": "ariia:ingest:priority_normal",
        "starter": "ariia:ingest:priority_low",
        "trial": "ariia:ingest:priority_low",
    }

    @staticmethod
    def get_queue_for_plan(plan_slug: str) -> str:
        """Return the Redis queue name for the given plan slug."""
        return WorkerSettings.QUEUE_MAP.get(plan_slug, "ariia:ingest:priority_low")
