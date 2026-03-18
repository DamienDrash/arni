"""Image provider management API (system admin + tenant BYOK)."""
from __future__ import annotations
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import AuthContext, get_current_user

logger = structlog.get_logger()
router = APIRouter(tags=["image-providers"])


class ProviderCreate(BaseModel):
    slug: str
    name: str
    provider_type: str
    api_base_url: str
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    priority: int = 100
    is_active: bool = True


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class TenantOverrideCreate(BaseModel):
    provider_id: int
    api_key: Optional[str] = None
    preferred_model: Optional[str] = None


# ── System Admin Endpoints ─────────────────────────────────────────────────

@router.get("/admin/system/image-providers")
async def list_image_providers(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin access required")
    from app.ai_config.image_service import ImageConfigService
    svc = ImageConfigService(db)
    providers = svc.list_providers()
    return [_provider_to_dict(p) for p in providers]


@router.post("/admin/system/image-providers", status_code=201)
async def create_image_provider(
    body: ProviderCreate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin access required")
    from app.ai_config.image_service import ImageConfigService
    svc = ImageConfigService(db)
    data = body.model_dump()
    provider = svc.create_provider(data)
    return _provider_to_dict(provider)


@router.put("/admin/system/image-providers/{provider_id}")
async def update_image_provider(
    provider_id: int,
    body: ProviderUpdate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin access required")
    from app.ai_config.image_service import ImageConfigService
    svc = ImageConfigService(db)
    data = body.model_dump(exclude_unset=True)
    provider = svc.update_provider(provider_id, data)
    return _provider_to_dict(provider)


@router.delete("/admin/system/image-providers/{provider_id}")
async def deactivate_image_provider(
    provider_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin access required")
    from app.ai_config.image_service import ImageConfigService
    svc = ImageConfigService(db)
    svc.deactivate_provider(provider_id)
    return {"status": "deactivated", "id": provider_id}


# ── Tenant BYOK Endpoints ──────────────────────────────────────────────────

@router.get("/admin/tenant/image-providers")
async def get_tenant_image_provider(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.tenant_id:
        return {"override": None}
    from app.ai_config.image_service import ImageConfigService
    svc = ImageConfigService(db)
    override = svc.get_tenant_override(user.tenant_id)
    if not override:
        return {"override": None}
    return {"override": _tenant_override_to_dict(override)}


@router.post("/admin/tenant/image-providers", status_code=201)
async def set_tenant_image_provider(
    body: TenantOverrideCreate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.ai_config.image_service import ImageConfigService
    svc = ImageConfigService(db)
    data = body.model_dump()
    override = svc.set_tenant_override(user.tenant_id, data)
    return _tenant_override_to_dict(override)


@router.delete("/admin/tenant/image-providers/{override_id}")
async def remove_tenant_image_provider(
    override_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.ai_config.image_service import ImageConfigService
    svc = ImageConfigService(db)
    svc.remove_tenant_override(user.tenant_id, override_id)
    return {"status": "removed", "id": override_id}


def _provider_to_dict(p) -> dict:
    return {
        "id": p.id,
        "slug": p.slug,
        "name": p.name,
        "provider_type": p.provider_type,
        "api_base_url": p.api_base_url,
        "default_model": p.default_model,
        "priority": p.priority,
        "is_active": p.is_active,
    }


def _tenant_override_to_dict(o) -> dict:
    return {
        "id": o.id,
        "provider_id": o.provider_id,
        "preferred_model": o.preferred_model,
        "is_active": o.is_active,
    }
