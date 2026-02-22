"""ARIIA v1.4 – Session Repository.

@BACKEND: Sprint 4, Task 4.3
Async Repository Pattern for Session/Message CRUD.
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from app.memory.database import MemoryDB

logger = structlog.get_logger()


class SessionRepository:
    """CRUD repository for sessions and messages.

    Supports GDPR Art. 17 cascade deletion.
    """

    def __init__(self, db: MemoryDB) -> None:
        self._db = db

    async def create_session(
        self,
        user_id: str,
        platform: str,
        consent_status: str = "granted",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new session.

        Returns:
            Session ID.
        """
        session_id = f"sess-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        await self._db.db.execute(
            """INSERT INTO sessions (session_id, platform, user_id, consent_status, last_interaction, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, platform, user_id, consent_status, now, json.dumps(metadata or {})),
        )
        await self._db.db.commit()
        logger.info("session.created", session_id=session_id, user_id=user_id)
        return session_id

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get a session by ID."""
        cursor = await self._db.db.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

    async def get_session_by_user(self, user_id: str, platform: str) -> dict[str, Any] | None:
        """Get the latest session for a user on a platform."""
        cursor = await self._db.db.execute(
            """SELECT * FROM sessions WHERE user_id = ? AND platform = ?
               ORDER BY last_interaction DESC LIMIT 1""",
            (user_id, platform),
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

    async def update_session(self, session_id: str, **kwargs: Any) -> bool:
        """Update session fields.

        Supported kwargs: consent_status, metadata, last_interaction.
        """
        allowed = {"consent_status", "metadata", "last_interaction"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        if "metadata" in updates and isinstance(updates["metadata"], dict):
            updates["metadata"] = json.dumps(updates["metadata"])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [session_id]
        await self._db.db.execute(
            f"UPDATE sessions SET {set_clause} WHERE session_id = ?",  # nosec B608
            values,
        )
        await self._db.db.commit()
        return True

    async def delete_session(self, session_id: str) -> bool:
        """Delete session and cascade to messages (GDPR Art. 17).

        Returns:
            True if session existed and was deleted.
        """
        cursor = await self._db.db.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        await self._db.db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("session.deleted", session_id=session_id, reason="art17_erasure")
        return deleted

    async def delete_user_sessions(self, user_id: str) -> int:
        """Delete ALL sessions for a user (GDPR Art. 17 full erasure).

        Returns:
            Number of deleted sessions.
        """
        cursor = await self._db.db.execute(
            "DELETE FROM sessions WHERE user_id = ?", (user_id,)
        )
        await self._db.db.commit()
        logger.info("session.user_deleted", user_id=user_id, count=cursor.rowcount)
        return cursor.rowcount

    # ── Message CRUD ──────────────────────────

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> str:
        """Add a message to a session.

        Returns:
            Message ID.
        """
        msg_id = f"msg-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        await self._db.db.execute(
            """INSERT INTO messages (id, session_id, role, content, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (msg_id, session_id, role, content, now),
        )
        # Update session last_interaction
        await self._db.db.execute(
            "UPDATE sessions SET last_interaction = ? WHERE session_id = ?",
            (now, session_id),
        )
        await self._db.db.commit()
        return msg_id

    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get messages for a session, ordered by timestamp.

        Args:
            session_id: Session identifier.
            limit: Max messages to return.

        Returns:
            List of message dicts.
        """
        cursor = await self._db.db.execute(
            """SELECT * FROM messages WHERE session_id = ?
               ORDER BY timestamp ASC LIMIT ?""",
            (session_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_message_count(self, session_id: str) -> int:
        """Get number of messages in a session."""
        cursor = await self._db.db.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_recent_global_messages(self, limit: int = 100) -> list[str]:
        """Get recent user messages from all sessions for analysis.

        Returns:
            List of message contents (User role only).
        """
        cursor = await self._db.db.execute(
            "SELECT content FROM messages WHERE role = 'user' ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

