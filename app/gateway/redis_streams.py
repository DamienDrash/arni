"""ARIIA v2.0 – Redis Streams Bus.

Replaces the fragile Pub/Sub model with Redis Streams for guaranteed
message delivery, consumer groups, acknowledgment, and dead-letter handling.

Architecture:
    Producer → XADD to stream → Consumer Group reads → ACK on success
    Failed messages → retry with backoff → Dead-Letter stream after max retries

Streams:
    - ariia:stream:inbound       – Incoming messages from all platforms
    - ariia:stream:outbound      – Responses back to platforms
    - ariia:stream:events        – System events (alerts, health, admin)
    - ariia:stream:librarian     – Librarian archival tasks
    - ariia:stream:dlq           – Dead-letter queue for failed messages
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
import structlog
import redis.asyncio as aioredis
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = structlog.get_logger()


# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_CONSUMER_GROUP = "ariia-workers"
DEFAULT_BLOCK_MS = 5000  # 5 seconds blocking read
MAX_RETRY_COUNT = 5
RETRY_BACKOFF_BASE = 2  # seconds
DLQ_STREAM = "ariia:stream:dlq"
CLAIM_IDLE_MS = 60_000  # 60 seconds – reclaim idle messages


class StreamName(str, Enum):
    """Well-known stream names."""
    INBOUND = "ariia:stream:inbound"
    OUTBOUND = "ariia:stream:outbound"
    EVENTS = "ariia:stream:events"
    LIBRARIAN = "ariia:stream:librarian"
    VOICE = "ariia:stream:voice"
    DLQ = "ariia:stream:dlq"

    @staticmethod
    def tenant_stream(base: str, tenant_id: int) -> str:
        """Create a tenant-namespaced stream name."""
        return f"t{tenant_id}:{base}"


@dataclass
class StreamMessage:
    """A message read from a Redis Stream."""
    message_id: str
    stream: str
    data: dict[str, Any]
    retry_count: int = 0
    created_at: float = field(default_factory=time.time)

    @property
    def payload(self) -> dict:
        """Parse the JSON payload from the data field."""
        raw = self.data.get("payload", "{}")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
        return raw

    @property
    def tenant_id(self) -> Optional[int]:
        """Extract tenant_id from message data."""
        tid = self.data.get("tenant_id")
        if tid is not None:
            return int(tid)
        return None

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "stream": self.stream,
            "data": self.data,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
        }


class RedisStreamsBus:
    """Redis Streams-based message bus with guaranteed delivery.

    Features:
    - Consumer groups for load balancing across workers
    - Automatic acknowledgment on successful processing
    - Retry with exponential backoff for failed messages
    - Dead-letter queue for permanently failed messages
    - Pending message reclamation for crashed consumers
    - Stream trimming to prevent unbounded growth
    """

    def __init__(
        self,
        redis_url: str = "redis://127.0.0.1:6379/0",
        consumer_group: str = DEFAULT_CONSUMER_GROUP,
        consumer_name: Optional[str] = None,
        max_stream_length: int = 100_000,
    ) -> None:
        self._redis_url = redis_url
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name or f"worker-{uuid.uuid4().hex[:8]}"
        self._max_stream_length = max_stream_length
        self._client: Optional[aioredis.Redis] = None
        self._running = False
        self._handlers: dict[str, Callable] = {}

    # ─── Connection Management ────────────────────────────────────────

    async def connect(self) -> None:
        """Establish connection to Redis."""
        self._client = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
            retry_on_timeout=True,
        )
        await self._client.ping()
        logger.info(
            "streams.connected",
            url=self._redis_url,
            consumer_group=self._consumer_group,
            consumer_name=self._consumer_name,
        )

    async def disconnect(self) -> None:
        """Gracefully close connection."""
        self._running = False
        if self._client:
            await self._client.aclose()
        logger.info("streams.disconnected")

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    @property
    def client(self) -> aioredis.Redis:
        """Direct access to Redis client."""
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    # ─── Stream Setup ─────────────────────────────────────────────────

    async def ensure_stream(self, stream: str) -> None:
        """Ensure a stream and its consumer group exist."""
        try:
            await self._client.xgroup_create(
                stream, self._consumer_group, id="0", mkstream=True,
            )
            logger.info("streams.group_created", stream=stream, group=self._consumer_group)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                pass  # Group already exists
            else:
                raise

    async def setup_streams(self, streams: Optional[list[str]] = None) -> None:
        """Initialize all well-known streams with consumer groups."""
        target_streams = streams or [s.value for s in StreamName]
        for stream in target_streams:
            await self.ensure_stream(stream)
        logger.info("streams.setup_complete", count=len(target_streams))

    # ─── Publishing ───────────────────────────────────────────────────

    async def publish(
        self,
        stream: str,
        payload: dict[str, Any],
        tenant_id: Optional[int] = None,
        message_type: str = "default",
        max_len: Optional[int] = None,
    ) -> str:
        """Publish a message to a Redis Stream.

        Args:
            stream: Target stream name.
            payload: Message payload (will be JSON-serialized).
            tenant_id: Optional tenant ID for routing.
            message_type: Message type identifier.
            max_len: Optional max stream length (approximate trimming).

        Returns:
            The message ID assigned by Redis.
        """
        if not self._client:
            raise RuntimeError("Redis not connected.")

        message_data = {
            "payload": json.dumps(payload),
            "type": message_type,
            "timestamp": str(time.time()),
            "retry_count": "0",
        }
        if tenant_id is not None:
            message_data["tenant_id"] = str(tenant_id)

        msg_id = await self._client.xadd(
            stream,
            message_data,
            maxlen=max_len or self._max_stream_length,
            approximate=True,
        )

        logger.debug(
            "streams.published",
            stream=stream,
            message_id=msg_id,
            type=message_type,
            tenant_id=tenant_id,
        )
        return msg_id

    # ─── Consuming ────────────────────────────────────────────────────

    def register_handler(self, stream: str, handler: Callable) -> None:
        """Register a message handler for a stream.

        The handler should be an async function accepting a StreamMessage.
        """
        self._handlers[stream] = handler
        logger.info("streams.handler_registered", stream=stream)

    async def consume(
        self,
        streams: list[str],
        block_ms: int = DEFAULT_BLOCK_MS,
    ) -> None:
        """Start consuming messages from multiple streams.

        This is the main consumer loop. It:
        1. Reads new messages from the consumer group
        2. Processes them via registered handlers
        3. ACKs on success, retries on failure
        4. Sends to DLQ after max retries
        """
        self._running = True

        # Ensure all streams have consumer groups
        for stream in streams:
            await self.ensure_stream(stream)

        # First, process any pending (unacknowledged) messages
        await self._process_pending(streams)

        logger.info(
            "streams.consuming",
            streams=streams,
            group=self._consumer_group,
            consumer=self._consumer_name,
        )

        while self._running:
            try:
                # Read new messages (> means only new, undelivered messages)
                stream_keys = {s: ">" for s in streams}
                results = await self._client.xreadgroup(
                    self._consumer_group,
                    self._consumer_name,
                    streams=stream_keys,
                    count=10,
                    block=block_ms,
                )

                if not results:
                    continue

                for stream_name, messages in results:
                    for msg_id, msg_data in messages:
                        await self._handle_message(stream_name, msg_id, msg_data)

            except aioredis.ConnectionError:
                logger.error("streams.connection_lost")
                await asyncio.sleep(5)
                try:
                    await self.connect()
                except Exception:
                    pass

            except asyncio.CancelledError:
                self._running = False
                break

            except Exception as e:
                logger.error("streams.consume_error", error=str(e))
                await asyncio.sleep(1)

    async def _handle_message(
        self,
        stream: str,
        msg_id: str,
        msg_data: dict,
    ) -> None:
        """Process a single message with error handling and retry logic."""
        retry_count = int(msg_data.get("retry_count", 0))

        message = StreamMessage(
            message_id=msg_id,
            stream=stream,
            data=msg_data,
            retry_count=retry_count,
        )

        handler = self._handlers.get(stream)
        if not handler:
            logger.warning("streams.no_handler", stream=stream, message_id=msg_id)
            await self._ack(stream, msg_id)
            return

        try:
            await handler(message)
            await self._ack(stream, msg_id)

            logger.debug(
                "streams.processed",
                stream=stream,
                message_id=msg_id,
            )

        except Exception as e:
            logger.error(
                "streams.processing_failed",
                stream=stream,
                message_id=msg_id,
                retry_count=retry_count,
                error=str(e),
            )

            if retry_count >= MAX_RETRY_COUNT:
                await self._send_to_dlq(stream, msg_id, msg_data, str(e))
                await self._ack(stream, msg_id)
            else:
                # Will be retried on next pending scan
                pass

    async def _ack(self, stream: str, msg_id: str) -> None:
        """Acknowledge a message as processed."""
        await self._client.xack(stream, self._consumer_group, msg_id)

    async def _send_to_dlq(
        self,
        source_stream: str,
        msg_id: str,
        msg_data: dict,
        error: str,
    ) -> None:
        """Send a permanently failed message to the dead-letter queue."""
        dlq_data = {
            "original_stream": source_stream,
            "original_id": msg_id,
            "payload": msg_data.get("payload", ""),
            "type": msg_data.get("type", "unknown"),
            "tenant_id": msg_data.get("tenant_id", ""),
            "error": error,
            "retry_count": msg_data.get("retry_count", "0"),
            "failed_at": str(time.time()),
        }

        await self._client.xadd(
            DLQ_STREAM,
            dlq_data,
            maxlen=10_000,
            approximate=True,
        )

        logger.warning(
            "streams.sent_to_dlq",
            source_stream=source_stream,
            message_id=msg_id,
            error=error,
        )

    # ─── Pending Message Recovery ─────────────────────────────────────

    async def _process_pending(self, streams: list[str]) -> None:
        """Process pending (unacknowledged) messages from previous runs.

        This handles messages that were delivered but not ACKed
        (e.g., due to a worker crash).
        """
        for stream in streams:
            try:
                # Read pending messages for this consumer
                pending = await self._client.xreadgroup(
                    self._consumer_group,
                    self._consumer_name,
                    streams={stream: "0"},
                    count=100,
                )

                if not pending:
                    continue

                for stream_name, messages in pending:
                    for msg_id, msg_data in messages:
                        if msg_data:  # Non-empty means unprocessed
                            retry_count = int(msg_data.get("retry_count", 0)) + 1
                            msg_data["retry_count"] = str(retry_count)
                            await self._handle_message(stream_name, msg_id, msg_data)

                logger.info(
                    "streams.pending_processed",
                    stream=stream,
                )

            except Exception as e:
                logger.error("streams.pending_error", stream=stream, error=str(e))

    async def claim_idle_messages(
        self,
        stream: str,
        idle_ms: int = CLAIM_IDLE_MS,
    ) -> list[StreamMessage]:
        """Claim idle messages from other consumers that may have crashed.

        This implements the XCLAIM pattern for consumer failure recovery.
        """
        claimed = []
        try:
            # Get pending entries info
            pending_info = await self._client.xpending_range(
                stream, self._consumer_group,
                min="-", max="+", count=100,
            )

            for entry in pending_info:
                entry_id = entry["message_id"]
                idle_time = entry.get("time_since_delivered", 0)
                delivery_count = entry.get("times_delivered", 0)

                if idle_time >= idle_ms:
                    # Claim the message
                    result = await self._client.xclaim(
                        stream, self._consumer_group, self._consumer_name,
                        min_idle_time=idle_ms, message_ids=[entry_id],
                    )

                    for msg_id, msg_data in result:
                        if msg_data:
                            claimed.append(StreamMessage(
                                message_id=msg_id,
                                stream=stream,
                                data=msg_data,
                                retry_count=delivery_count,
                            ))

            if claimed:
                logger.info(
                    "streams.claimed_idle",
                    stream=stream,
                    count=len(claimed),
                )

        except Exception as e:
            logger.error("streams.claim_error", stream=stream, error=str(e))

        return claimed

    # ─── Stream Info & Management ─────────────────────────────────────

    async def get_stream_info(self, stream: str) -> dict:
        """Get information about a stream."""
        try:
            info = await self._client.xinfo_stream(stream)
            groups = await self._client.xinfo_groups(stream)
            return {
                "stream": stream,
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "groups": [
                    {
                        "name": g.get("name"),
                        "consumers": g.get("consumers", 0),
                        "pending": g.get("pending", 0),
                        "last_delivered_id": g.get("last-delivered-id"),
                    }
                    for g in groups
                ],
            }
        except aioredis.ResponseError:
            return {"stream": stream, "length": 0, "groups": []}

    async def get_dlq_messages(
        self,
        count: int = 50,
        start: str = "-",
        end: str = "+",
    ) -> list[dict]:
        """Read messages from the dead-letter queue for inspection."""
        try:
            messages = await self._client.xrange(DLQ_STREAM, start, end, count=count)
            return [
                {"id": msg_id, **msg_data}
                for msg_id, msg_data in messages
            ]
        except aioredis.ResponseError:
            return []

    async def retry_dlq_message(self, dlq_msg_id: str) -> Optional[str]:
        """Re-publish a DLQ message back to its original stream for retry."""
        try:
            messages = await self._client.xrange(DLQ_STREAM, dlq_msg_id, dlq_msg_id)
            if not messages:
                return None

            _, msg_data = messages[0]
            original_stream = msg_data.get("original_stream")
            if not original_stream:
                return None

            # Re-publish with reset retry count
            new_id = await self.publish(
                original_stream,
                json.loads(msg_data.get("payload", "{}")),
                tenant_id=int(msg_data["tenant_id"]) if msg_data.get("tenant_id") else None,
                message_type=msg_data.get("type", "retry"),
            )

            # Remove from DLQ
            await self._client.xdel(DLQ_STREAM, dlq_msg_id)

            logger.info(
                "streams.dlq_retried",
                dlq_id=dlq_msg_id,
                new_id=new_id,
                stream=original_stream,
            )
            return new_id

        except Exception as e:
            logger.error("streams.dlq_retry_failed", error=str(e))
            return None

    async def trim_stream(self, stream: str, max_len: int) -> int:
        """Manually trim a stream to a maximum length."""
        trimmed = await self._client.xtrim(stream, maxlen=max_len, approximate=True)
        logger.info("streams.trimmed", stream=stream, trimmed=trimmed)
        return trimmed

    # ─── Backward Compatibility ───────────────────────────────────────

    async def publish_compat(self, channel: str, message: str) -> str:
        """Backward-compatible publish that maps old Pub/Sub channels to streams.

        Maps:
            ariia:inbound  → ariia:stream:inbound
            ariia:outbound → ariia:stream:outbound
            ariia:events   → ariia:stream:events
        """
        stream_map = {
            "ariia:inbound": StreamName.INBOUND.value,
            "ariia:outbound": StreamName.OUTBOUND.value,
            "ariia:events": StreamName.EVENTS.value,
            "ariia:voice_queue": StreamName.VOICE.value,
        }

        # Check for tenant-prefixed channels
        stream = stream_map.get(channel)
        if not stream:
            # Try tenant-prefixed: t1:ariia:inbound → t1:ariia:stream:inbound
            for old, new in stream_map.items():
                if channel.endswith(old):
                    prefix = channel[: len(channel) - len(old)]
                    stream = f"{prefix}{new}"
                    break

        if not stream:
            stream = f"ariia:stream:{channel}"

        payload = message if isinstance(message, dict) else {"raw": message}
        if isinstance(message, str):
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                payload = {"raw": message}

        return await self.publish(stream, payload)

    async def subscribe_compat(
        self,
        channel: str,
        callback: Callable,
    ) -> None:
        """Backward-compatible subscribe that maps to stream consumption."""
        stream_map = {
            "ariia:inbound": StreamName.INBOUND.value,
            "ariia:outbound": StreamName.OUTBOUND.value,
            "ariia:events": StreamName.EVENTS.value,
        }
        stream = stream_map.get(channel, f"ariia:stream:{channel}")

        async def wrapper(msg: StreamMessage):
            await callback(json.dumps(msg.payload))

        self.register_handler(stream, wrapper)
        await self.consume([stream])
