"""ARIIA v2.0 – arq Worker Entry-Point.

Start with:
    python -m app.worker.main

Or via Docker:
    docker compose up ariia-ingestion-worker
"""
from arq import run_worker

import structlog

from app.worker.ingestion_tasks import WorkerSettings

logger = structlog.get_logger()

if __name__ == "__main__":
    logger.info("ariia.worker.starting")
    run_worker(WorkerSettings)
