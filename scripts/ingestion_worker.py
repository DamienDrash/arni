"""ARIIA Ingestion Worker — ARQ async task queue entrypoint.

Processes heavy background tasks (PDF parsing, ChromaDB embedding) in a
separate process, isolated from the FastAPI API server.

Usage:
    python scripts/ingestion_worker.py

Docker (see docker-compose.yml):
    ariia-ingestion-worker:
      command: python scripts/ingestion_worker.py

Concurrency: 2 simultaneous jobs (configurable via WorkerSettings.max_jobs).
Scale by running additional worker replicas — ARQ handles job locking via Redis.
"""
import sys
import os

# Ensure /app is on the path when run from the scripts/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import arq
import structlog

from app.worker.ingestion_tasks import ingest_file_task, ingest_text_task
from app.worker.settings import WorkerSettings

logger = structlog.get_logger()

# Register task functions with the worker settings class
WorkerSettings.functions = [ingest_file_task, ingest_text_task]

if __name__ == "__main__":
    logger.info("ingestion_worker.starting", max_jobs=WorkerSettings.max_jobs, queue=WorkerSettings.queue_name)
    arq.run_worker(WorkerSettings)
