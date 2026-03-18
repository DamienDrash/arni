"""ARIIA Swarm v3 — Unit Tests for ConfirmationGate (Redis-backed).

Tests store/check/resolve flow, affirmative/negative patterns,
TTL expiry, and cross-tenant isolation using fakeredis.
"""

import json
import pytest
import fakeredis.aioredis

from app.swarm.contracts import AgentResult, TenantContext
from app.swarm.lead.confirmation_gate import (
    AFFIRMATIVE_PATTERNS,
    CONFIRMATION_TTL,
    ConfirmationGate,
    PendingConfirmation,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_context(
    tenant_id: int = 1,
    tenant_slug: str = "test-studio",
    member_id: str = "member-001",
) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        plan_slug="pro",
        active_integrations=frozenset(),
        settings={},
        member_id=member_id,
    )


def _make_result(
    agent_id: str = "ops",
    content: str = "Möchtest du den Kurs wirklich stornieren?",
    confirmation_prompt: str = "Kurs stornieren?",
    confirmation_action: str = '{"action": "cancel_booking", "booking_id": 42}',
) -> AgentResult:
    return AgentResult(
        agent_id=agent_id,
        content=content,
        confidence=0.9,
        requires_confirmation=True,
        confirmation_prompt=confirmation_prompt,
        confirmation_action=confirmation_action,
    )


@pytest.fixture
def redis_client():
    """Async fakeredis client for testing."""
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def gate(redis_client):
    """ConfirmationGate backed by fakeredis."""
    return ConfirmationGate(redis_client)


# ── Store Tests ──────────────────────────────────────────────────────────────


class TestStore:
    @pytest.mark.anyio
    async def test_store_creates_redis_key(self, gate, redis_client) -> None:
        """store() creates a Redis key with the correct TTL."""
        ctx = _make_context()
        result = _make_result()
        token = await gate.store(result, ctx)

        key = f"t{ctx.tenant_id}:confirm:{ctx.member_id}:{token}"
        raw = await redis_client.get(key)
        assert raw is not None

        data = json.loads(raw)
        assert data["token"] == token
        assert data["agent_id"] == "ops"
        assert data["tenant_id"] == ctx.tenant_id
        assert data["member_id"] == ctx.member_id

    @pytest.mark.anyio
    async def test_store_sets_ttl(self, gate, redis_client) -> None:
        """store() sets TTL of 300 seconds on the key."""
        ctx = _make_context()
        result = _make_result()
        token = await gate.store(result, ctx)

        key = f"t{ctx.tenant_id}:confirm:{ctx.member_id}:{token}"
        ttl = await redis_client.ttl(key)
        assert ttl > 0
        assert ttl <= CONFIRMATION_TTL

    @pytest.mark.anyio
    async def test_store_returns_token(self, gate) -> None:
        """store() returns a non-empty token string."""
        ctx = _make_context()
        result = _make_result()
        token = await gate.store(result, ctx)
        assert isinstance(token, str)
        assert len(token) == 12

    @pytest.mark.anyio
    async def test_store_parses_string_action(self, gate, redis_client) -> None:
        """store() parses JSON string confirmation_action into dict."""
        ctx = _make_context()
        result = _make_result(confirmation_action='{"action": "delete", "id": 99}')
        token = await gate.store(result, ctx)

        key = f"t{ctx.tenant_id}:confirm:{ctx.member_id}:{token}"
        raw = await redis_client.get(key)
        data = json.loads(raw)
        assert data["confirmation_action"] == {"action": "delete", "id": 99}

    @pytest.mark.anyio
    async def test_store_with_ttl_override(self, gate, redis_client) -> None:
        """store() uses the provided ttl_override."""
        ctx = _make_context()
        result = _make_result()
        custom_ttl = 120
        token = await gate.store(result, ctx, ttl_override=custom_ttl)

        key = f"t{ctx.tenant_id}:confirm:{ctx.member_id}:{token}"
        ttl = await redis_client.ttl(key)
        assert ttl > 0
        assert ttl <= custom_ttl


# ── Check Tests ──────────────────────────────────────────────────────────────


class TestCheck:
    @pytest.mark.anyio
    async def test_check_finds_pending(self, gate) -> None:
        """check() returns PendingConfirmation after store()."""
        ctx = _make_context()
        result = _make_result()
        token = await gate.store(result, ctx)

        pending = await gate.check(ctx)
        assert pending is not None
        assert isinstance(pending, PendingConfirmation)
        assert pending.token == token
        assert pending.agent_id == "ops"

    @pytest.mark.anyio
    async def test_check_none_when_empty(self, gate) -> None:
        """check() returns None when no pending confirmation exists."""
        ctx = _make_context()
        pending = await gate.check(ctx)
        assert pending is None

    @pytest.mark.anyio
    async def test_check_scoped_to_member(self, gate) -> None:
        """check() only finds confirmations for the correct member."""
        ctx_a = _make_context(member_id="member-001")
        ctx_b = _make_context(member_id="member-002")

        await gate.store(_make_result(), ctx_a)

        # Member B should not see Member A's confirmation
        pending_b = await gate.check(ctx_b)
        assert pending_b is None

        # Member A should see their own
        pending_a = await gate.check(ctx_a)
        assert pending_a is not None


# ── Resolve Tests ────────────────────────────────────────────────────────────


class TestResolve:
    @pytest.mark.anyio
    async def test_resolve_denied(self, gate, redis_client) -> None:
        """resolve() with user_confirmed=False returns cancellation message and deletes key."""
        ctx = _make_context()
        result = _make_result()
        token = await gate.store(result, ctx)

        resolved = await gate.resolve(token, user_confirmed=False, context=ctx)

        assert isinstance(resolved, AgentResult)
        assert "abgebrochen" in resolved.content.lower()
        assert resolved.agent_id == "ops"

        # Key should be deleted
        key = f"t{ctx.tenant_id}:confirm:{ctx.member_id}:{token}"
        assert await redis_client.get(key) is None

    @pytest.mark.anyio
    async def test_expired_token(self, gate) -> None:
        """resolve() with non-existent token returns expiry message."""
        ctx = _make_context()
        resolved = await gate.resolve("nonexistent_token", user_confirmed=True, context=ctx)

        assert isinstance(resolved, AgentResult)
        assert "abgelaufen" in resolved.content.lower()
        assert resolved.agent_id == "confirmation_gate"

    @pytest.mark.anyio
    async def test_resolve_deletes_key(self, gate, redis_client) -> None:
        """resolve() always deletes the Redis key, whether confirmed or denied."""
        ctx = _make_context()
        token = await gate.store(_make_result(), ctx)

        key = f"t{ctx.tenant_id}:confirm:{ctx.member_id}:{token}"
        assert await redis_client.get(key) is not None

        # Deny
        await gate.resolve(token, user_confirmed=False, context=ctx)
        assert await redis_client.get(key) is None


# ── Affirmative / Negative Pattern Tests ─────────────────────────────────────


class TestPatterns:
    @pytest.mark.parametrize("msg", [
        "ja", "Ja", "JA", "ja bitte", "bitte", "ok", "okay",
        "gerne", "klar", "yes", "sicher", "bestätigt", "go",
        "mach das", "mach weiter", "do it", "genau", "richtig",
        "passt", "einverstanden", "ja mach", "stimmt",
    ])
    def test_affirmative_patterns(self, msg: str) -> None:
        """All affirmative patterns are recognized as confirmed."""
        assert ConfirmationGate.is_affirmative(msg) is True

    @pytest.mark.parametrize("msg", [
        "ja!", "ok.", "bitte!!", "gerne?",
    ])
    def test_affirmative_with_punctuation(self, msg: str) -> None:
        """Affirmative patterns with trailing punctuation are still recognized."""
        assert ConfirmationGate.is_affirmative(msg) is True

    @pytest.mark.parametrize("msg", [
        "nein", "abbrechen", "stop", "lass das", "auf keinen fall",
        "nein danke", "cancel", "vergiss es", "nicht jetzt",
    ])
    def test_negative_patterns(self, msg: str) -> None:
        """Negative/rejection messages are NOT recognized as affirmative."""
        assert ConfirmationGate.is_affirmative(msg) is False

    def test_empty_string_not_affirmative(self) -> None:
        """Empty string is not affirmative."""
        assert ConfirmationGate.is_affirmative("") is False

    def test_random_text_not_affirmative(self) -> None:
        """Random text is not affirmative."""
        assert ConfirmationGate.is_affirmative("xyz quantum physics") is False


# ── Cross-Tenant Isolation Tests ─────────────────────────────────────────────


class TestCrossTenantIsolation:
    @pytest.mark.anyio
    async def test_tenant_a_cannot_resolve_tenant_b(self, gate) -> None:
        """Tenant A cannot resolve Tenant B's confirmation."""
        ctx_a = _make_context(tenant_id=1, tenant_slug="studio-a", member_id="member-001")
        ctx_b = _make_context(tenant_id=2, tenant_slug="studio-b", member_id="member-001")

        # Store confirmation for Tenant A
        token = await gate.store(_make_result(), ctx_a)

        # Try to resolve with Tenant B context
        resolved = await gate.resolve(token, user_confirmed=True, context=ctx_b)

        # Should fail (key not found because different tenant_id in key)
        assert "abgelaufen" in resolved.content.lower()

    @pytest.mark.anyio
    async def test_tenant_a_cannot_check_tenant_b(self, gate) -> None:
        """Tenant A's check() does not find Tenant B's pending confirmations."""
        ctx_a = _make_context(tenant_id=1, tenant_slug="studio-a", member_id="member-001")
        ctx_b = _make_context(tenant_id=2, tenant_slug="studio-b", member_id="member-001")

        # Store for Tenant A
        await gate.store(_make_result(), ctx_a)

        # Check from Tenant B
        pending = await gate.check(ctx_b)
        assert pending is None

        # Check from Tenant A (should find it)
        pending_a = await gate.check(ctx_a)
        assert pending_a is not None


# ── Edge Cases ───────────────────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_unknown_member_id_defaults(self, gate, redis_client) -> None:
        """Context with member_id=None uses 'unknown' in key."""
        ctx = _make_context(member_id=None)
        # TenantContext has member_id as optional, replace with None
        ctx = TenantContext(
            tenant_id=ctx.tenant_id,
            tenant_slug=ctx.tenant_slug,
            plan_slug=ctx.plan_slug,
            active_integrations=ctx.active_integrations,
            settings=ctx.settings,
            member_id=None,
        )
        token = await gate.store(_make_result(), ctx)

        key = f"t{ctx.tenant_id}:confirm:unknown:{token}"
        raw = await redis_client.get(key)
        assert raw is not None

    @pytest.mark.anyio
    async def test_pending_confirmation_dataclass(self) -> None:
        """PendingConfirmation dataclass stores all fields correctly."""
        pending = PendingConfirmation(
            token="abc123",
            agent_id="ops",
            confirmation_prompt="Sure?",
            confirmation_action={"action": "cancel"},
            tenant_id=1,
            member_id="m1",
            metadata={"extra": "data"},
        )
        assert pending.token == "abc123"
        assert pending.agent_id == "ops"
        assert pending.metadata == {"extra": "data"}
