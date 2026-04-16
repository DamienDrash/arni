from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Query, Session

from app.domains.campaigns.models import CampaignTemplate


class CampaignTemplatesRepository:
    """Focused DB access for tenant-scoped campaign template CRUD."""

    def build_active_templates_query(
        self,
        db: Session,
        *,
        tenant_id: int,
        template_type: str | None = None,
    ) -> Query[CampaignTemplate]:
        query = db.query(CampaignTemplate).filter(
            CampaignTemplate.tenant_id == tenant_id,
            CampaignTemplate.is_active.is_(True),
        )
        if template_type:
            query = query.filter(CampaignTemplate.type == template_type)
        return query

    def list_active_templates(
        self,
        db: Session,
        *,
        tenant_id: int,
        page: int,
        limit: int,
        template_type: str | None = None,
    ) -> list[CampaignTemplate]:
        query = self.build_active_templates_query(
            db,
            tenant_id=tenant_id,
            template_type=template_type,
        )
        return query.order_by(desc(CampaignTemplate.created_at)).offset((page - 1) * limit).limit(limit).all()

    def count_active_templates(
        self,
        db: Session,
        *,
        tenant_id: int,
        template_type: str | None = None,
    ) -> int:
        return self.build_active_templates_query(
            db,
            tenant_id=tenant_id,
            template_type=template_type,
        ).count()

    def list_default_templates(self, db: Session, *, tenant_id: int) -> list[CampaignTemplate]:
        return (
            db.query(CampaignTemplate)
            .filter(
                CampaignTemplate.tenant_id == tenant_id,
                CampaignTemplate.is_default.is_(True),
                CampaignTemplate.is_active.is_(True),
            )
            .all()
        )

    def get_active_template_by_id(
        self,
        db: Session,
        *,
        tenant_id: int,
        template_id: int,
    ) -> CampaignTemplate | None:
        return (
            db.query(CampaignTemplate)
            .filter(
                CampaignTemplate.id == template_id,
                CampaignTemplate.tenant_id == tenant_id,
                CampaignTemplate.is_active.is_(True),
            )
            .first()
        )

    def unset_default_templates(
        self,
        db: Session,
        *,
        tenant_id: int,
        template_type: str,
    ) -> None:
        (
            db.query(CampaignTemplate)
            .filter(
                CampaignTemplate.tenant_id == tenant_id,
                CampaignTemplate.type == template_type,
                CampaignTemplate.is_default.is_(True),
            )
            .update({"is_default": False})
        )

    def add_template(self, db: Session, *, template: CampaignTemplate) -> CampaignTemplate:
        db.add(template)
        return template


campaign_templates_repository = CampaignTemplatesRepository()
