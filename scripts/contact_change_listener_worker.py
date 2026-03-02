"""ARIIA v2.1 – Contact Change Listener Worker.

Long-running worker process that polls the contact_activities table
for relevant changes and triggers matching automation workflows.

Runs as a Docker container: ariia-contact-listener
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
from app.campaign_engine.contact_change_listener import ContactChangeListener

POLL_INTERVAL = int(os.environ.get("LISTENER_POLL_INTERVAL", "10"))

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
logger = structlog.get_logger("ariia.contact_change_listener_worker")

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("contact_listener.shutdown_requested", signal=signum)
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


async def main():
    listener = ContactChangeListener()
    logger.info(
        "contact_listener.started",
        poll_interval=POLL_INTERVAL,
    )

    while not _shutdown:
        db = SessionLocal()
        try:
            triggered = await listener.poll(db)
            if triggered > 0:
                logger.info("contact_listener.workflows_triggered", count=triggered)
        except Exception as e:
            logger.error("contact_listener.poll_error", error=str(e))
        finally:
            db.close()

        await asyncio.sleep(POLL_INTERVAL)

    logger.info("contact_listener.stopped")


if __name__ == "__main__":
    asyncio.run(main())
