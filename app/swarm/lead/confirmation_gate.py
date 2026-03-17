"""ARIIA Swarm v3 — ConfirmationGate (Redis-backed).

One-way-door actions (cancellations, deletions) require explicit user
confirmation before execution.  The ConfirmationGate stores pending
confirmations in Redis with a 5-minute TTL and resolves them when the
user responds.

Flow:
1. ExpertAgent returns AgentResult with requires_confirmation=True
2. LeadAgent calls gate.store() -> token
3. User sees confirmation prompt, responds "ja" / "nein"
4. LeadAgent calls gate.resolve(token, confirmed) -> AgentResult
5. If confirmed: re-dispatch to ExpertAgent.execute_confirmed()
"""

from __future__ import annotations

import json
import time
import uuid
import structlog
from dataclasses import dataclass, field
from typing import Any

from app.swarm.contracts import AgentResult, TenantContext

logger = structlog.get_logger()

# TTL for pending confirmations in seconds (5 minutes)
CONFIRMATION_TTL = 300

# Send warning notification at 80% of TTL (i.e. 60 seconds before expiry)
CONFIRMATION_WARNING_OFFSET = 240

# Patterns that indicate user confirmation (German + English)
AFFIRMATIVE_PATTERNS: frozenset[str] = frozenset({
    "ja", "ja bitte", "bitte", "gerne", "ok", "okay",
    "mach das", "passt", "einverstanden", "yes", "klar",
    "sicher", "bestätigt", "mach weiter", "go", "do it",
    "ja mach", "genau", "richtig", "stimmt",
})


@dataclass
class PendingConfirmation:
    """A pending one-way-door action awaiting user confirmation."""

    token: str
    agent_id: str
    confirmation_prompt: str
    confirmation_action: dict[str, Any]
    tenant_id: int
    member_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ConfirmationGate:
    """Redis-backed confirmation gate for one-way-door actions.

    Keys follow the tenant-namespaced pattern:
        t{tenant_id}:confirm:{member_id}:{token}
    """

    def __init__(self, redis_client):
        """Initialize with an aioredis-compatible client.

        Args:
            redis_client: Async Redis client (from app.gateway.redis_bus or aioredis).
        """
        self._redis = redis_client

    def _key(self, tenant_id: int, member_id: str, token: str) -> str:
        """Build the Redis key for a confirmation."""
        return f"t{tenant_id}:confirm:{member_id}:{token}"

    def _scan_pattern(self, tenant_id: int, member_id: str) -> str:
        """Build the scan pattern to find pending confirmations."""
        return f"t{tenant_id}:confirm:{member_id}:*"

    async def store(self, result: AgentResult, context: TenantContext) -> str:
        """Store a pending confirmation in Redis.

        Args:
            result: AgentResult with requires_confirmation=True.
            context: TenantContext for key scoping.

        Returns:
            Confirmation token (UUID).
        """
        token = uuid.uuid4().hex[:12]
        member_id = context.member_id or "unknown"

        pending = PendingConfirmation(
            token=token,
            agent_id=result.agent_id,
            confirmation_prompt=result.confirmation_prompt or "",
            confirmation_action=json.loads(result.confirmation_action)
            if isinstance(result.confirmation_action, str)
            else (result.confirmation_action or {}),
            tenant_id=context.tenant_id,
            member_id=member_id,
            metadata=result.metadata,
        )

        key = self._key(context.tenant_id, member_id, token)
        payload = json.dumps({
            "token": pending.token,
            "agent_id": pending.agent_id,
            "confirmation_prompt": pending.confirmation_prompt,
            "confirmation_action": pending.confirmation_action,
            "tenant_id": pending.tenant_id,
            "member_id": pending.member_id,
            "metadata": pending.metadata,
        })

        await self._redis.setex(key, CONFIRMATION_TTL, payload)

        # Register TTL warning and expiry notification jobs
        now = time.time()
        try:
            # Warning job (at 80% of TTL — 60 seconds before expiry)
            await self._redis.zadd("orch:pending_notifications", {
                json.dumps({
                    "tenant_id": context.tenant_id,
                    "member_id": member_id,
                    "channel": "whatsapp",
                    "message": "\u26a0\ufe0f Deine ausstehende Best\u00e4tigung l\u00e4uft in 60 Sekunden ab. Bitte jetzt antworten.",
                    "type": "confirmation_warning",
                }): now + CONFIRMATION_WARNING_OFFSET,
            })

            # Expiry notification (1 second after TTL)
            await self._redis.zadd("orch:pending_notifications", {
                json.dumps({
                    "tenant_id": context.tenant_id,
                    "member_id": member_id,
                    "channel": "whatsapp",
                    "message": "Best\u00e4tigungsanfrage abgelaufen. Bitte Aktion erneut anfordern.",
                    "type": "confirmation_expired",
                }): now + CONFIRMATION_TTL + 1,
            })
        except Exception as notif_err:
            logger.warning(
                "confirmation_gate.notification_schedule_failed",
                error=str(notif_err),
                token=token,
            )

        logger.info(
            "confirmation_gate.stored",
            token=token,
            agent_id=result.agent_id,
            tenant_id=context.tenant_id,
            member_id=member_id,
        )

        return token

    async def check(self, context: TenantContext) -> PendingConfirmation | None:
        """Check if there is a pending confirmation for this tenant+member.

        Args:
            context: TenantContext with tenant_id and member_id.

        Returns:
            PendingConfirmation if found, None otherwise.
        """
        member_id = context.member_id or "unknown"
        pattern = self._scan_pattern(context.tenant_id, member_id)

        # Use SCAN to find matching keys (avoids KEYS in production)
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=10)
            if keys:
                # Return the first (most recent) pending confirmation
                raw = await self._redis.get(keys[0])
                if raw:
                    data = json.loads(raw)
                    return PendingConfirmation(
                        token=data["token"],
                        agent_id=data["agent_id"],
                        confirmation_prompt=data["confirmation_prompt"],
                        confirmation_action=data["confirmation_action"],
                        tenant_id=data["tenant_id"],
                        member_id=data["member_id"],
                        metadata=data.get("metadata", {}),
                    )
            if cursor == 0:
                break

        return None

    async def resolve(
        self,
        token: str,
        user_confirmed: bool,
        context: TenantContext,
    ) -> AgentResult:
        """Resolve a pending confirmation.

        If confirmed: re-dispatches to the expert agent's execute_confirmed().
        If denied: returns a cancellation message.
        Always deletes the Redis key after resolution.

        Args:
            token: The confirmation token.
            user_confirmed: Whether the user confirmed the action.
            context: TenantContext for key scoping.

        Returns:
            AgentResult from the re-dispatched agent or cancellation message.
        """
        member_id = context.member_id or "unknown"
        key = self._key(context.tenant_id, member_id, token)

        raw = await self._redis.get(key)
        if not raw:
            logger.warning(
                "confirmation_gate.expired_or_missing",
                token=token,
                tenant_id=context.tenant_id,
            )
            return AgentResult(
                agent_id="confirmation_gate",
                content="Die Bestätigung ist abgelaufen oder wurde nicht gefunden. Bitte starte den Vorgang erneut.",
                confidence=0.8,
            )

        # Always delete the key after retrieval
        await self._redis.delete(key)

        data = json.loads(raw)
        agent_id = data["agent_id"]
        action = data["confirmation_action"]

        if not user_confirmed:
            logger.info(
                "confirmation_gate.denied",
                token=token,
                agent_id=agent_id,
                tenant_id=context.tenant_id,
            )
            return AgentResult(
                agent_id=agent_id,
                content="Alles klar, ich habe den Vorgang abgebrochen.",
                confidence=1.0,
            )

        # Re-dispatch to the expert agent
        logger.info(
            "confirmation_gate.confirmed",
            token=token,
            agent_id=agent_id,
            tenant_id=context.tenant_id,
        )

        try:
            from app.swarm.lead.agent_loader import get_agent_loader
            loader = get_agent_loader()
            agent = loader.get_agent(agent_id)
            if agent is None:
                return AgentResult(
                    agent_id=agent_id,
                    content="Der zuständige Agent ist nicht mehr verfügbar.",
                    confidence=0.3,
                )
            return await agent.execute_confirmed(action, context)
        except Exception as e:
            logger.error(
                "confirmation_gate.re_dispatch_failed",
                agent_id=agent_id,
                error=str(e),
            )
            return AgentResult(
                agent_id=agent_id,
                content="Fehler bei der Ausführung der bestätigten Aktion. Bitte versuche es erneut.",
                confidence=0.3,
            )

    @staticmethod
    def is_affirmative(message: str) -> bool:
        """Check if a user message is an affirmative confirmation.

        Args:
            message: Raw user message text.

        Returns:
            True if the message matches an affirmative pattern.
        """
        normalized = message.strip().lower().rstrip("!.,?")
        return normalized in AFFIRMATIVE_PATTERNS
