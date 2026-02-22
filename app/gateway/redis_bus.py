"""ARNI v1.4 – Redis Bus Connector.

@BACKEND: Redis Pub/Sub Integration (Sprint 1, Task 1.4)
Single Source of Truth: ALL messages pass through the Redis Bus.
"""

from typing import Any, Callable

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class RedisBus:
    """Async Redis Pub/Sub message bus.

    Connects the Gateway to the Swarm and all other services.
    Channels:
        - `arni:inbound`  – Incoming messages from all platforms
        - `arni:outbound` – Responses from Swarm back to platforms
        - `arni:events`   – System events (alerts, health, admin)
    """

    CHANNEL_INBOUND = "arni:inbound"
    CHANNEL_OUTBOUND = "arni:outbound"
    CHANNEL_EVENTS = "arni:events"
    CHANNEL_VOICE_QUEUE = "arni:voice_queue"

    def __init__(self, redis_url: str = "redis://127.0.0.1:6379/0") -> None:
        self._redis_url = redis_url
        self._client: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        self._client = redis.from_url(
            self._redis_url,
            decode_responses=True,
            retry_on_timeout=True,
        )
        await self._client.ping()
        logger.info("redis.connected", url=self._redis_url)

    async def disconnect(self) -> None:
        """Gracefully close Redis connection."""
        if self._pubsub:
            await self._pubsub.aclose()
        if self._client:
            await self._client.aclose()
        logger.info("redis.disconnected")

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except (redis.ConnectionError, redis.TimeoutError):
            logger.error("redis.health_check_failed")
            return False

    async def publish(self, channel: str, message: str) -> int:
        """Publish a message to a Redis channel.

        Args:
            channel: Target channel name.
            message: JSON-serialized message string.

        Returns:
            Number of subscribers that received the message.
        """
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        count = await self._client.publish(channel, message)
        logger.debug("redis.published", channel=channel, subscribers=count)
        return count

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[str], Any],
    ) -> None:
        """Subscribe to a Redis channel and process messages.

        Args:
            channel: Channel to subscribe to.
            callback: Async function called for each message.
        """
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")

        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(channel)
        logger.info("redis.subscribed", channel=channel)

        async for message in self._pubsub.listen():
            if message["type"] == "message":
                await callback(message["data"])

    async def push_to_queue(self, channel: str, message: str) -> int:
        """Push a message to a Redis Queue (List)."""
        if not self._client:
            raise RuntimeError("Redis not connected.")
        # RPUSH appends to end of list
        count = await self._client.rpush(channel, message)
        logger.debug("redis.queued", channel=channel, length=count)
        return count

    async def pop_from_queue(self, channel: str, timeout: int = 0) -> tuple[str, str] | None:
        """Pop a message from a Redis Queue (Blocking).
        
        Returns:
            (channel, message) tuple or None if timeout.
        """
        if not self._client:
            raise RuntimeError("Redis not connected.")
        # BLPOP removes from start of list (FIFO)
        result = await self._client.blpop(channel, timeout=timeout)
        if result:
            return result # (channel, data)
        return None

    @property
    def client(self) -> redis.Redis:
        """Direct access to Redis client for advanced operations."""
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
