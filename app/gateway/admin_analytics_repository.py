from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domains.identity.models import AuditLog
from app.domains.support.models import ChatMessage, ChatSession, MemberFeedback


class AdminAnalyticsRepository:
    """Read-model queries for admin analytics surfaces."""

    def list_assistant_messages_since(
        self,
        db: Session,
        *,
        tenant_id: int,
        since: datetime,
    ) -> list[ChatMessage]:
        return (
            db.query(ChatMessage)
            .filter(
                ChatMessage.tenant_id == tenant_id,
                ChatMessage.role == "assistant",
                ChatMessage.timestamp >= since,
            )
            .all()
        )

    def get_feedback_summary(self, db: Session, *, tenant_id: int):
        return (
            db.query(
                func.avg(MemberFeedback.rating).label("avg_rating"),
                func.count(MemberFeedback.id).label("total_feedback"),
            )
            .filter(MemberFeedback.tenant_id == tenant_id)
            .first()
        )

    def list_recent_sessions(
        self,
        db: Session,
        *,
        tenant_id: int,
        limit: int,
    ) -> list[ChatSession]:
        return (
            db.query(ChatSession)
            .filter(ChatSession.tenant_id == tenant_id)
            .order_by(ChatSession.last_message_at.desc())
            .limit(limit)
            .all()
        )

    def list_messages_for_session_ids(
        self,
        db: Session,
        *,
        tenant_id: int,
        session_ids: list[str],
    ) -> list[ChatMessage]:
        if not session_ids:
            return []
        return (
            db.query(ChatMessage)
            .filter(
                ChatMessage.tenant_id == tenant_id,
                ChatMessage.session_id.in_(session_ids),
            )
            .order_by(ChatMessage.timestamp.desc())
            .all()
        )

    def count_audit_logs(self, db: Session, *, tenant_id: int) -> int:
        return db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id).count()

    def list_audit_logs(
        self,
        db: Session,
        *,
        tenant_id: int,
        limit: int,
        offset: int,
    ) -> list[AuditLog]:
        return (
            db.query(AuditLog)
            .filter(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )


admin_analytics_repository = AdminAnalyticsRepository()
