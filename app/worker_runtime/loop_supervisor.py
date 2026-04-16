"""Shared restart/failure semantics for async worker-runtime loops."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import structlog

from app.worker_runtime.runtime_state import runtime_state

logger = structlog.get_logger()

LoopFactory = Callable[[], Awaitable[None]]

_BASE_BACKOFF_SECONDS = 5
_MAX_BACKOFF_SECONDS = 300


def compute_restart_backoff(failure_count: int) -> int:
    exponent = max(failure_count - 1, 0)
    return min(_BASE_BACKOFF_SECONDS * (2 ** exponent), _MAX_BACKOFF_SECONDS)


async def run_supervised_loop(name: str, loop_factory: LoopFactory) -> None:
    """Run a long-lived async loop with shared restart semantics."""
    while True:
        runtime_state.mark_started(name)
        logger.info("worker_runtime.loop_started", worker=name)
        try:
            await loop_factory()
            runtime_state.mark_stopped(name)
            logger.info("worker_runtime.loop_stopped", worker=name)
            return
        except asyncio.CancelledError:
            runtime_state.mark_stopped(name)
            logger.info("worker_runtime.loop_cancelled", worker=name)
            raise
        except Exception as exc:
            runtime_state.mark_failed(name, str(exc))
            failure_count = next(
                (
                    worker["failure_count"]
                    for worker in runtime_state.snapshot()
                    if worker["name"] == name
                ),
                1,
            )
            backoff = compute_restart_backoff(int(failure_count))
            logger.error(
                "worker_runtime.loop_failed",
                worker=name,
                error=str(exc),
                failure_count=failure_count,
                restart_in_seconds=backoff,
            )
            await asyncio.sleep(backoff)

