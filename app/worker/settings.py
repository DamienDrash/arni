"""ARQ Worker settings — Redis connection, concurrency, timeouts, retry policy.

Designed for on-prem (Docker Compose) and cloud (AWS ElastiCache / GCP Memorystore).
To migrate: just change REDIS_URL in .env — no code changes needed.
"""
from __future__ import annotations

import urllib.parse

from arq.connections import RedisSettings as ArqRedisSettings


def get_arq_redis_settings() -> ArqRedisSettings:
    """Parse REDIS_URL env var into ARQ RedisSettings.

    ARQ uses redis-py async client internally. This converts the URL-style
    connection string (same as used by the Redis bus) into host/port/db params.
    """
    import os
    url = os.environ.get("REDIS_URL", "redis://ariia-redis:6379/0")
    parsed = urllib.parse.urlparse(url)
    return ArqRedisSettings(
        host=parsed.hostname or "ariia-redis",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or 0),
        password=parsed.password or None,
    )


# ── ARQ Queue Name ─────────────────────────────────────────────────────────────
# Namespaced to avoid collision with RedisBus keys (ariia:inbound, ariia:outbound, ...)
INGESTION_QUEUE = "ariia:ingestion_queue"


class WorkerSettings:
    """ARQ WorkerSettings for the ARIIA ingestion worker.

    Concurrency cap: 2 simultaneous jobs.
    Rationale: pdfplumber + ChromaDB embedding each use ~200-400MB RAM.
    2 concurrent jobs = ~800MB peak — safe on 4GB+ hosts.
    Scale by running more worker containers, not raising max_jobs.
    """

    # Import task functions after module is available
    functions: list = []  # populated by scripts/ingestion_worker.py

    redis_settings = get_arq_redis_settings()

    # Queue name — must match enqueue_job calls in the API
    queue_name = INGESTION_QUEUE

    # Concurrency: 2 simultaneous heavy jobs max (PDF parsing + embedding)
    max_jobs = 2

    # Hard job timeout: 10 minutes.
    # The PDF parser itself has a 5-min asyncio.wait_for; this is the outer wall.
    job_timeout = 600  # seconds

    # Retry policy: 3 attempts, 30s between retries
    max_tries = 3
    retry_delay = 30.0  # seconds

    # How fast the worker polls Redis for new jobs (sub-second for responsive UX)
    poll_delay = 0.5  # seconds

    # Keep job results in Redis for 24h (secondary debug source; .meta.json is primary)
    keep_result = 86_400  # seconds
    keep_result_forever = False

    # Health check logging interval
    health_check_interval = 60  # seconds
