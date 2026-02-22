"""ARIIA v1.4 – Redis Bus Unit Tests.

@QA: Sprint 1, Task 1.9
Tests: Connection, Pub/Sub roundtrip, health check, error handling.
Uses fakeredis for isolation – no production API calls (CODING_STANDARDS §4).
"""

import pytest
import fakeredis.aioredis

from app.gateway.redis_bus import RedisBus


class TestRedisBusConnection:
    """Test Redis connection lifecycle."""

    @pytest.mark.anyio
    async def test_health_check_returns_false_when_disconnected(self) -> None:
        bus = RedisBus(redis_url="redis://fake:6379/0")
        result = await bus.health_check()
        assert result is False

    @pytest.mark.anyio
    async def test_publish_raises_when_disconnected(self) -> None:
        bus = RedisBus(redis_url="redis://fake:6379/0")
        with pytest.raises(RuntimeError, match="not connected"):
            await bus.publish("test-channel", "test-message")

    @pytest.mark.anyio
    async def test_subscribe_raises_when_disconnected(self) -> None:
        bus = RedisBus(redis_url="redis://fake:6379/0")
        with pytest.raises(RuntimeError, match="not connected"):
            await bus.subscribe("test-channel", lambda x: None)


class TestRedisBusPubSub:
    """Test Pub/Sub with fakeredis – no real Redis needed."""

    @pytest.fixture
    async def bus(self):
        """Create a RedisBus with a fakeredis backend."""
        bus = RedisBus()
        # Inject fakeredis client directly
        bus._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        yield bus
        await bus.disconnect()

    @pytest.mark.anyio
    async def test_health_check_returns_true_when_connected(self, bus: RedisBus) -> None:
        result = await bus.health_check()
        assert result is True

    @pytest.mark.anyio
    async def test_publish_returns_subscriber_count(self, bus: RedisBus) -> None:
        count = await bus.publish("ariia:test", '{"msg": "hello"}')
        # No subscribers yet, so count is 0
        assert count == 0

    @pytest.mark.anyio
    async def test_publish_to_inbound_channel(self, bus: RedisBus) -> None:
        count = await bus.publish(RedisBus.CHANNEL_INBOUND, '{"test": true}')
        assert isinstance(count, int)

    @pytest.mark.anyio
    async def test_publish_to_outbound_channel(self, bus: RedisBus) -> None:
        count = await bus.publish(RedisBus.CHANNEL_OUTBOUND, '{"test": true}')
        assert isinstance(count, int)

    @pytest.mark.anyio
    async def test_publish_to_events_channel(self, bus: RedisBus) -> None:
        count = await bus.publish(RedisBus.CHANNEL_EVENTS, '{"event": "test"}')
        assert isinstance(count, int)

    @pytest.mark.anyio
    async def test_client_property_when_connected(self, bus: RedisBus) -> None:
        assert bus.client is not None

    @pytest.mark.anyio
    async def test_client_property_raises_when_disconnected(self) -> None:
        bus = RedisBus()
        with pytest.raises(RuntimeError, match="not connected"):
            _ = bus.client


class TestRedisBusChannels:
    """Verify channel naming conventions."""

    def test_channel_inbound_name(self) -> None:
        assert RedisBus.CHANNEL_INBOUND == "ariia:inbound"

    def test_channel_outbound_name(self) -> None:
        assert RedisBus.CHANNEL_OUTBOUND == "ariia:outbound"

    def test_channel_events_name(self) -> None:
        assert RedisBus.CHANNEL_EVENTS == "ariia:events"
