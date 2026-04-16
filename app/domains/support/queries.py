from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domains.support.models import ChatSession


class SupportQueries:
    """Cross-domain read access for support-owned entities."""

    def count_conversations_since(self, db: Session, *, tenant_id: int, since: datetime) -> int:
        return (
            db.query(ChatSession)
            .filter(ChatSession.tenant_id == tenant_id, ChatSession.created_at >= since)
            .count()
        )


support_queries = SupportQueries()
