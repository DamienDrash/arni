"""ARNI v1.4 – Consent Manager (GDPR Art. 6 + Art. 17).

@SEC: Sprint 4, Task 4.7
Enforces consent checks before data processing and cascade deletion.
"""

import structlog

from app.memory.database import MemoryDB
from app.memory.repository import SessionRepository
from app.memory.knowledge import KnowledgeStore
from app.memory.graph import FactGraph
from app.memory.context import ConversationContext

logger = structlog.get_logger()


class ConsentManager:
    """GDPR consent enforcement across all memory tiers.

    Art. 6: Lawful processing requires consent.
    Art. 17: Right to Erasure – cascade delete on revocation.
    """

    def __init__(
        self,
        repo: SessionRepository,
        knowledge: KnowledgeStore,
        graph: FactGraph,
        context: ConversationContext,
    ) -> None:
        self._repo = repo
        self._knowledge = knowledge
        self._graph = graph
        self._context = context

    async def check_consent(self, user_id: str, platform: str) -> bool:
        """Check if a user has granted consent (Art. 6).

        Args:
            user_id: User identifier.
            platform: Platform name.

        Returns:
            True if consent is granted or no session exists (new user).
        """
        session = await self._repo.get_session_by_user(user_id, platform)
        if not session:
            return True  # New user, no session yet
        return session.get("consent_status") == "granted"

    async def grant_consent(self, user_id: str, platform: str) -> str:
        """Grant consent for data processing.

        Creates a new session if none exists, or updates existing.

        Returns:
            Session ID.
        """
        session = await self._repo.get_session_by_user(user_id, platform)
        if session:
            await self._repo.update_session(
                session["session_id"],
                consent_status="granted",
            )
            logger.info("consent.granted", user_id=user_id, session_id=session["session_id"])
            return session["session_id"]
        else:
            session_id = await self._repo.create_session(
                user_id=user_id,
                platform=platform,
                consent_status="granted",
            )
            logger.info("consent.granted_new", user_id=user_id, session_id=session_id)
            return session_id

    async def revoke_consent(self, user_id: str, platform: str) -> dict[str, int]:
        """Revoke consent and cascade delete all user data (Art. 17).

        Deletes:
        1. RAM context
        2. SQLite sessions + messages
        3. Knowledge files
        4. Graph nodes

        Returns:
            Dict with counts of deleted items per tier.
        """
        result = {
            "context_cleared": 0,
            "sessions_deleted": 0,
            "knowledge_deleted": 0,
            "graph_removed": 0,
        }

        # 1. Clear RAM context
        self._context.clear(user_id)
        result["context_cleared"] = 1

        # 2. Delete all sessions (cascade to messages)
        count = await self._repo.delete_user_sessions(user_id)
        result["sessions_deleted"] = count

        # 3. Delete knowledge file
        if self._knowledge.delete_member(user_id):
            result["knowledge_deleted"] = 1

        # 4. Remove from graph
        if self._graph.remove_user(user_id):
            result["graph_removed"] = 1

        logger.critical(
            "consent.revoked_cascade",
            user_id=user_id,
            platform=platform,
            **result,
        )
        return result
