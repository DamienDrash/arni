"""ARIIA – Worker Entry-Point.

Usage:
    python -m app.worker.main                    # starts ingestion worker (default)
    python -m app.worker.main --worker ingestion
    python -m app.worker.main --worker campaign
    python -m app.worker.main --worker analytics
    python -m app.worker.main --worker automation
"""
import importlib
import sys

from arq import run_worker
import structlog

logger = structlog.get_logger()

WORKER_MAP = {
    "ingestion":  ("app.worker.ingestion_tasks", "WorkerSettings"),
    "campaign":   ("app.worker.campaign_tasks",  "CampaignWorkerSettings"),
    "analytics":  ("app.worker.campaign_tasks",  "CampaignWorkerSettings"),
    "automation": ("app.worker.campaign_tasks",  "CampaignWorkerSettings"),
}

if __name__ == "__main__":
    worker_type = "ingestion"
    if "--worker" in sys.argv:
        idx = sys.argv.index("--worker")
        if idx + 1 < len(sys.argv):
            worker_type = sys.argv[idx + 1]

    if worker_type not in WORKER_MAP:
        logger.error("worker.unknown_type", worker_type=worker_type, available=list(WORKER_MAP))
        sys.exit(1)

    module_path, class_name = WORKER_MAP[worker_type]
    logger.info("ariia.worker.starting", worker_type=worker_type, module=module_path)

    mod = importlib.import_module(module_path)
    settings_class = getattr(mod, class_name)
    run_worker(settings_class)
