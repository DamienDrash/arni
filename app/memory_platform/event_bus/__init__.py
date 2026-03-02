"""Internal async event bus for the Memory Platform.

This module provides a lightweight, in-process event bus that decouples
services within the memory platform.  When Kafka is available, events are
also forwarded to Kafka topics for external consumers and durability.
For single-process deployments (the current ARIIA setup), the internal
bus is sufficient and avoids the operational overhead of a full Kafka cluster.

Usage:
    from app.memory_platform.event_bus import get_event_bus

    bus = get_event_bus()
    bus.subscribe("ingestion.raw", my_handler)
    await bus.publish(event)
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable

import structlog

from app.memory_platform.models import MemoryEvent

logger = structlog.get_logger()

# Type alias for event handlers
EventHandler = Callable[[MemoryEvent], Awaitable[None]]


class InternalEventBus:
    """Lightweight async event bus for intra-process communication.

    Supports topic-based pub/sub with async handlers.  Handlers are
    invoked concurrently via ``asyncio.gather`` for maximum throughput.
    Failed handlers are logged but do not block other subscribers.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._event_log: list[MemoryEvent] = []
        self._max_log_size: int = 10_000
        self._running: bool = False
        self._queue: asyncio.Queue[MemoryEvent] = asyncio.Queue()
        self._processor_task: asyncio.Task[None] | None = None

    # ── Subscription ─────────────────────────────────────────────────

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register *handler* for events of *event_type*."""
        self._subscribers[event_type].append(handler)
        logger.debug(
            "event_bus.subscribed",
            event_type=event_type,
            handler=handler.__qualname__,
        )

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove *handler* from *event_type* subscribers."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    # ── Publishing ───────────────────────────────────────────────────

    async def publish(self, event: MemoryEvent) -> None:
        """Publish *event* to all registered handlers for its type.

        Events are processed asynchronously.  If the background processor
        is running, the event is queued; otherwise it is dispatched inline.
        """
        # Append to rolling log
        self._event_log.append(event)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

        if self._running:
            await self._queue.put(event)
        else:
            await self._dispatch(event)

    async def _dispatch(self, event: MemoryEvent) -> None:
        """Dispatch *event* to all matching handlers."""
        handlers = self._subscribers.get(event.event_type, [])
        if not handlers:
            logger.debug("event_bus.no_handlers", event_type=event.event_type)
            return

        logger.info(
            "event_bus.dispatching",
            event_type=event.event_type,
            event_id=event.event_id,
            handler_count=len(handlers),
        )

        tasks = []
        for handler in handlers:
            tasks.append(self._safe_call(handler, event))
        await asyncio.gather(*tasks)

    async def _safe_call(self, handler: EventHandler, event: MemoryEvent) -> None:
        """Call *handler* with *event*, catching and logging exceptions."""
        try:
            await handler(event)
        except Exception as exc:
            logger.error(
                "event_bus.handler_error",
                handler=handler.__qualname__,
                event_type=event.event_type,
                event_id=event.event_id,
                error=str(exc),
            )

    # ── Background processor ─────────────────────────────────────────

    async def start(self) -> None:
        """Start the background event processor."""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_loop())
        logger.info("event_bus.started")

    async def stop(self) -> None:
        """Stop the background event processor and drain the queue."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
        logger.info("event_bus.stopped")

    async def _process_loop(self) -> None:
        """Continuously process events from the internal queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("event_bus.process_error", error=str(exc))

    # ── Introspection ────────────────────────────────────────────────

    @property
    def subscriber_count(self) -> dict[str, int]:
        """Return a mapping of event_type → number of subscribers."""
        return {k: len(v) for k, v in self._subscribers.items()}

    @property
    def recent_events(self) -> list[MemoryEvent]:
        """Return the most recent events (up to max_log_size)."""
        return list(self._event_log)

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()


# ── Singleton ────────────────────────────────────────────────────────

_bus: InternalEventBus | None = None


def get_event_bus() -> InternalEventBus:
    """Return the singleton event bus instance."""
    global _bus
    if _bus is None:
        _bus = InternalEventBus()
    return _bus
