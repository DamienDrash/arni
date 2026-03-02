"""ARIIA v2.1 – Automation Engine Worker.

Long-running worker process that polls for due automation runs
and executes them through the AutomationEngine.

Runs as a Docker container: ariia-automation-engine
"""
import asyncio
import logging
import os
import signal
import sys

import structlog

# Ensure app modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.campaign_engine.automation_engine import AutomationEngine

POLL_INTERVAL = int(os.environ.get("AUTOMATION_POLL_INTERVAL", "15"))

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger("ariia.automation_engine_worker")

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("automation_engine.shutdown_requested", signal=signum)
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


async def main():
    engine = AutomationEngine()
    logger.info(
        "automation_engine.started",
        poll_interval=POLL_INTERVAL,
    )

    while not _shutdown:
        db = SessionLocal()
        try:
            processed = await engine.process_due_runs(db)
            if processed > 0:
                logger.info("automation_engine.batch_processed", runs=processed)
        except Exception as e:
            logger.error("automation_engine.poll_error", error=str(e))
        finally:
            db.close()

        await asyncio.sleep(POLL_INTERVAL)

    logger.info("automation_engine.stopped")


if __name__ == "__main__":
    asyncio.run(main())
