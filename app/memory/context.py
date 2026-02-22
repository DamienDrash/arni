"""ARNI v1.4 – Short-Term Memory (RAM Context).

@BACKEND: Sprint 4, Task 4.1
Per-user conversation context with 20-turn limit and TTL.
"""

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

DEFAULT_MAX_TURNS = 20
DEFAULT_TTL_SECONDS = 1800  # 30 minutes


@dataclass
class Turn:
    """A single conversation turn."""

    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationContext:
    """Per-user RAM conversation context.

    Stores the last N turns with TTL-based expiry.
    When context nears capacity, triggers Silent Flush.
    """

    def __init__(
        self,
        max_turns: int = DEFAULT_MAX_TURNS,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._max_turns = max_turns
        self._ttl_seconds = ttl_seconds
        self._contexts: dict[str, list[Turn]] = {}
        self._last_access: dict[str, float] = {}

    def add_turn(self, user_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a conversation turn for a user.

        Args:
            user_id: Unique user identifier.
            role: Message role (user/assistant/system/tool).
            content: Message content.
            metadata: Optional additional data.
        """
        self._cleanup_expired()

        if user_id not in self._contexts:
            self._contexts[user_id] = []

        turn = Turn(role=role, content=content, metadata=metadata or {})
        self._contexts[user_id].append(turn)
        self._last_access[user_id] = time.time()

        # Enforce turn limit
        if len(self._contexts[user_id]) > self._max_turns:
            removed = len(self._contexts[user_id]) - self._max_turns
            self._contexts[user_id] = self._contexts[user_id][-self._max_turns:]
            logger.debug("context.trimmed", user_id=user_id, removed=removed)

    def get_context(self, user_id: str) -> list[dict[str, str]]:
        """Get conversation context for LLM prompt.

        Args:
            user_id: User identifier.

        Returns:
            List of {role, content} dicts for the LLM.
        """
        self._cleanup_expired()
        turns = self._contexts.get(user_id, [])
        self._last_access[user_id] = time.time()
        return [{"role": t.role, "content": t.content} for t in turns]

    def get_turns(self, user_id: str) -> list[Turn]:
        """Get raw Turn objects for a user."""
        self._cleanup_expired()
        return list(self._contexts.get(user_id, []))

    def is_near_limit(self, user_id: str, threshold: float = 0.8) -> bool:
        """Check if context is near capacity (triggers Silent Flush).

        Args:
            user_id: User identifier.
            threshold: Fraction of max_turns (default 0.8 = 80%).

        Returns:
            True if current turns >= threshold * max_turns.
        """
        turns = self._contexts.get(user_id, [])
        return len(turns) >= int(self._max_turns * threshold)

    def clear(self, user_id: str) -> None:
        """Clear all context for a user."""
        self._contexts.pop(user_id, None)
        self._last_access.pop(user_id, None)
        logger.info("context.cleared", user_id=user_id)

    def replace_with_summary(self, user_id: str, summary: str, keep_last: int = 3) -> None:
        """Replace context with summary + last N turns (post-flush).

        Args:
            user_id: User identifier.
            summary: Compacted summary text.
            keep_last: Number of recent turns to preserve.
        """
        turns = self._contexts.get(user_id, [])
        recent = turns[-keep_last:] if len(turns) >= keep_last else turns

        self._contexts[user_id] = [
            Turn(role="system", content=f"[Zusammenfassung]: {summary}"),
            *recent,
        ]
        logger.info(
            "context.compacted",
            user_id=user_id,
            kept_turns=len(recent) + 1,
        )

    def get_user_count(self) -> int:
        """Get number of active user contexts."""
        self._cleanup_expired()
        return len(self._contexts)

    def _cleanup_expired(self) -> None:
        """Remove expired contexts (TTL exceeded)."""
        now = time.time()
        expired = [
            uid for uid, last in self._last_access.items()
            if now - last > self._ttl_seconds
        ]
        for uid in expired:
            self._contexts.pop(uid, None)
            self._last_access.pop(uid, None)
            logger.debug("context.expired", user_id=uid)
