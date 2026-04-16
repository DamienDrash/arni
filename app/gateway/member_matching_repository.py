from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.support.models import StudioMember


class MemberMatchingRepository:
    """Focused data access for phone-based member matching."""

    def list_members_with_phone(
        self,
        db: Session,
        *,
        tenant_id: int | None = None,
    ) -> list[StudioMember]:
        query = db.query(StudioMember).filter(StudioMember.phone_number.isnot(None))
        if tenant_id is not None:
            query = query.filter(StudioMember.tenant_id == tenant_id)
        return query.all()


member_matching_repository = MemberMatchingRepository()
