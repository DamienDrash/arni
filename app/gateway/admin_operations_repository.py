from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.domains.support.models import ChatSession, StudioMember


class AdminOperationsRepository:
    """Read/query repository for admin operations surfaces."""

    def get_member_stats(self, db: Session, *, tenant_id: int) -> dict[str, int]:
        base_q = db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id)
        today = date.today()
        return {
            "total_members": base_q.count(),
            "new_today": base_q.filter(func.date(StudioMember.created_at) == today).count(),
            "with_email": base_q.filter(StudioMember.email.isnot(None)).count(),
            "with_phone": base_q.filter(StudioMember.phone_number.isnot(None)).count(),
            "with_both": base_q.filter(
                and_(
                    StudioMember.email.isnot(None),
                    StudioMember.phone_number.isnot(None),
                )
            ).count(),
        }

    def get_member_chat_summary(self, db: Session, *, tenant_id: int) -> dict[str, dict[str, Any]]:
        rows = (
            db.query(
                ChatSession.member_id,
                func.count(ChatSession.id).label("sessions"),
                func.max(ChatSession.last_message_at).label("last_chat_at"),
            )
            .filter(ChatSession.tenant_id == tenant_id)
            .filter(ChatSession.member_id.isnot(None))
            .group_by(ChatSession.member_id)
            .all()
        )
        result: dict[str, dict[str, Any]] = {}
        for member_id, sessions_count, last_chat_at in rows:
            if not member_id:
                continue
            result[str(member_id).strip()] = {
                "chat_sessions": int(sessions_count or 0),
                "last_chat_at": last_chat_at.isoformat() if last_chat_at else None,
            }
        return result

    def list_members(
        self,
        db: Session,
        *,
        tenant_id: int,
        limit: int,
        search: str | None,
    ) -> list[StudioMember]:
        query = db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id)
        if search:
            token = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    StudioMember.first_name.ilike(token),
                    StudioMember.last_name.ilike(token),
                    StudioMember.member_number.ilike(token),
                    StudioMember.email.ilike(token),
                    StudioMember.phone_number.ilike(token),
                )
            )
        return (
            query.order_by(StudioMember.last_name.asc(), StudioMember.first_name.asc())
            .limit(max(1, min(limit, 2000)))
            .all()
        )

    def get_enrichment_stats(self, db: Session, *, tenant_id: int) -> dict[str, Any]:
        base_q = db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id)
        lang_rows = (
            base_q.with_entities(StudioMember.preferred_language, func.count(StudioMember.customer_id))
            .group_by(StudioMember.preferred_language)
            .all()
        )
        return {
            "total": base_q.count(),
            "enriched": base_q.filter(StudioMember.enriched_at.isnot(None)).count(),
            "paused": base_q.filter(StudioMember.is_paused == True).count(),
            "languages": {(row[0] or "unknown"): row[1] for row in lang_rows},
        }

    def list_member_customer_ids(self, db: Session, *, tenant_id: int) -> list[int]:
        return [
            row.customer_id
            for row in db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id).all()
        ]

    def search_members_for_link(
        self,
        db: Session,
        *,
        tenant_id: int,
        query_text: str,
    ) -> list[StudioMember]:
        query = db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id)
        if query_text.strip():
            term = f"%{query_text.strip()}%"
            query = query.filter(
                (StudioMember.first_name.ilike(term))
                | (StudioMember.last_name.ilike(term))
                | (StudioMember.email.ilike(term))
                | (StudioMember.phone_number.ilike(term))
                | (StudioMember.member_number.ilike(term))
            )
        return query.limit(20).all()


admin_operations_repository = AdminOperationsRepository()
