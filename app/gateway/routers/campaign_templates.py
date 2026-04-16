"""ARIIA v2.1 – Campaign Template Management API.

Provides dedicated CRUD endpoints for managing reusable campaign templates
(email headers/footers, WhatsApp templates, SMS templates).

@ARCH: Campaign Refactoring Phase 1, Task 1.2
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import AuthContext, get_current_user
from app.domains.campaigns.models import CampaignTemplate
from app.gateway.campaign_templates_repository import campaign_templates_repository

logger = structlog.get_logger()
router = APIRouter(prefix="/v2/admin/templates", tags=["templates"])


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class TemplateCreateSchema(BaseModel):
    name: str = Field(..., max_length=100, description="Template name")
    description: Optional[str] = Field(None, max_length=500)
    type: str = Field("email", pattern=r"^(email|whatsapp|sms|telegram)$")
    header_html: Optional[str] = None
    footer_html: Optional[str] = None
    body_template: Optional[str] = None
    variables_json: Optional[str] = None
    primary_color: Optional[str] = Field("#6C5CE7", pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: Optional[str] = None
    is_default: bool = False


class TemplateUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    type: Optional[str] = Field(None, pattern=r"^(email|whatsapp|sms|telegram)$")
    header_html: Optional[str] = None
    footer_html: Optional[str] = None
    body_template: Optional[str] = None
    variables_json: Optional[str] = None
    primary_color: Optional[str] = None
    logo_url: Optional[str] = None
    is_default: Optional[bool] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
async def list_templates(
    type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all active templates for the tenant."""
    total = campaign_templates_repository.count_active_templates(
        db,
        tenant_id=user.tenant_id,
        template_type=type,
    )
    templates = campaign_templates_repository.list_active_templates(
        db,
        tenant_id=user.tenant_id,
        page=page,
        limit=limit,
        template_type=type,
    )

    return {
        "items": [_template_to_dict(t) for t in templates],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post("", status_code=201)
async def create_template(
    body: TemplateCreateSchema,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new campaign template."""
    if body.is_default:
        _unset_defaults(db, user.tenant_id, body.type)

    template = CampaignTemplate(
        tenant_id=user.tenant_id,
        **body.model_dump(),
    )
    campaign_templates_repository.add_template(db, template=template)
    db.commit()
    db.refresh(template)

    logger.info("template.created", template_id=template.id, tenant_id=user.tenant_id, type=body.type)
    return _template_to_dict(template)


@router.get("/defaults/by-type")
async def get_default_templates(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the default template for each channel type."""
    defaults = campaign_templates_repository.list_default_templates(db, tenant_id=user.tenant_id)
    return {t.type: _template_to_dict(t) for t in defaults}


@router.get("/{template_id}")
async def get_template(
    template_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single template by ID."""
    template = _get_template_or_404(db, user.tenant_id, template_id)
    return _template_to_dict(template)


@router.put("/{template_id}")
async def update_template(
    template_id: int,
    body: TemplateUpdateSchema,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing template."""
    template = _get_template_or_404(db, user.tenant_id, template_id)

    update_data = body.model_dump(exclude_unset=True)

    # If setting as default, unset other defaults of same type
    if update_data.get("is_default"):
        target_type = update_data.get("type", template.type)
        _unset_defaults(db, user.tenant_id, target_type)

    for field, value in update_data.items():
        setattr(template, field, value)

    template.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(template)

    logger.info("template.updated", template_id=template.id, tenant_id=user.tenant_id)
    return _template_to_dict(template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a template."""
    template = _get_template_or_404(db, user.tenant_id, template_id)
    template.is_active = False
    template.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("template.deleted", template_id=template.id, tenant_id=user.tenant_id)
    return {"status": "deleted", "id": template_id}


@router.post("/{template_id}/duplicate")
async def duplicate_template(
    template_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Duplicate an existing template."""
    source = _get_template_or_404(db, user.tenant_id, template_id)
    clone = CampaignTemplate(
        tenant_id=user.tenant_id,
        name=f"{source.name} (Kopie)",
        description=source.description,
        type=source.type,
        header_html=source.header_html,
        footer_html=source.footer_html,
        body_template=source.body_template,
        variables_json=source.variables_json,
        primary_color=source.primary_color,
        logo_url=source.logo_url,
        is_default=False,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)

    logger.info("template.duplicated", source_id=template_id, clone_id=clone.id, tenant_id=user.tenant_id)
    return _template_to_dict(clone)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_template_or_404(db: Session, tenant_id: int, template_id: int) -> CampaignTemplate:
    template = campaign_templates_repository.get_active_template_by_id(
        db,
        tenant_id=tenant_id,
        template_id=template_id,
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


def _unset_defaults(db: Session, tenant_id: int, template_type: str):
    campaign_templates_repository.unset_default_templates(
        db,
        tenant_id=tenant_id,
        template_type=template_type,
    )


def _template_to_dict(t: CampaignTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "type": t.type,
        "header_html": t.header_html,
        "footer_html": t.footer_html,
        "body_template": t.body_template,
        "variables_json": t.variables_json,
        "primary_color": t.primary_color,
        "logo_url": t.logo_url,
        "is_default": t.is_default,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
