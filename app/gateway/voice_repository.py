from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.identity.models import Tenant


class VoiceRepository:
    """Focused DB reads for the voice ingress compatibility router."""

    def get_active_tenant_by_slug(
        self,
        db: Session,
        *,
        tenant_slug: str,
    ) -> Tenant | None:
        return (
            db.query(Tenant)
            .filter(
                Tenant.slug == tenant_slug,
                Tenant.is_active.is_(True),
            )
            .first()
        )


voice_repository = VoiceRepository()
