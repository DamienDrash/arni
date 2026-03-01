"""ARIIA v2.0 – Integration Registry API.

@ARCH: Phase 2, Meilenstein 2.1 – Integration & Skills
CRUD endpoints for managing the Integration Registry:
  - IntegrationDefinitions (admin-only)
  - CapabilityDefinitions (admin-only)
  - TenantIntegrations (tenant-scoped)

These endpoints are consumed by:
  1. The System Admin panel (managing the global catalog)
  2. The Tenant Portal (marketplace: activate/configure integrations)
  3. The DynamicToolResolver (reading active integrations at runtime)
"""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.integration_models import (
    AuthType,
    CapabilityDefinition,
    IntegrationCapability,
    IntegrationCategory,
    IntegrationDefinition,
    IntegrationStatus,
    TenantIntegration,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class IntegrationCreate(BaseModel):
    id: str = Field(..., max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    category: str = IntegrationCategory.CUSTOM.value
    logo_url: Optional[str] = None
    auth_type: str = AuthType.API_KEY.value
    config_schema: Optional[dict] = None
    adapter_class: Optional[str] = None
    skill_file: Optional[str] = None
    is_public: bool = True
    min_plan: Optional[str] = "professional"


class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    logo_url: Optional[str] = None
    auth_type: Optional[str] = None
    config_schema: Optional[dict] = None
    adapter_class: Optional[str] = None
    skill_file: Optional[str] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None
    min_plan: Optional[str] = None


class IntegrationOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category: str
    logo_url: Optional[str]
    auth_type: str
    config_schema: Optional[dict]
    adapter_class: Optional[str]
    skill_file: Optional[str]
    is_public: bool
    is_active: bool
    min_plan: Optional[str]
    version: Optional[str]
    capabilities: list[str] = []

    class Config:
        from_attributes = True


class CapabilityCreate(BaseModel):
    id: str = Field(..., max_length=64, pattern=r"^[a-z][a-z0-9_.]*$")
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    is_destructive: bool = False
    category: Optional[str] = None


class CapabilityOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    input_schema: Optional[dict]
    output_schema: Optional[dict]
    is_destructive: bool
    category: Optional[str]

    class Config:
        from_attributes = True


class TenantIntegrationCreate(BaseModel):
    integration_id: str
    config_meta: Optional[dict] = None


class TenantIntegrationUpdate(BaseModel):
    enabled: Optional[bool] = None
    config_meta: Optional[dict] = None
    status: Optional[str] = None


class TenantIntegrationOut(BaseModel):
    id: int
    tenant_id: int
    integration_id: str
    status: str
    config_meta: Optional[dict]
    enabled: bool
    last_health_check: Optional[str]
    last_error: Optional[str]
    integration_name: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Definitions (Admin-only CRUD)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/definitions", response_model=list[IntegrationOut])
def list_integrations(
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List all integration definitions (marketplace catalog)."""
    query = select(IntegrationDefinition).where(IntegrationDefinition.is_active == True)
    if category:
        query = query.where(IntegrationDefinition.category == category)
    if is_public is not None:
        query = query.where(IntegrationDefinition.is_public == is_public)

    integrations = db.execute(query).scalars().all()
    result = []
    for integ in integrations:
        caps = db.execute(
            select(IntegrationCapability.capability_id)
            .where(IntegrationCapability.integration_id == integ.id)
        ).scalars().all()
        out = IntegrationOut(
            id=integ.id,
            name=integ.name,
            description=integ.description,
            category=integ.category,
            logo_url=integ.logo_url,
            auth_type=integ.auth_type,
            config_schema=integ.config_schema,
            adapter_class=integ.adapter_class,
            skill_file=integ.skill_file,
            is_public=integ.is_public,
            is_active=integ.is_active,
            min_plan=integ.min_plan,
            version=integ.version,
            capabilities=list(caps),
        )
        result.append(out)
    return result


@router.get("/definitions/{integration_id}", response_model=IntegrationOut)
def get_integration(integration_id: str, db: Session = Depends(get_db)):
    """Get a single integration definition by ID."""
    integ = db.get(IntegrationDefinition, integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    caps = db.execute(
        select(IntegrationCapability.capability_id)
        .where(IntegrationCapability.integration_id == integ.id)
    ).scalars().all()
    return IntegrationOut(
        id=integ.id,
        name=integ.name,
        description=integ.description,
        category=integ.category,
        logo_url=integ.logo_url,
        auth_type=integ.auth_type,
        config_schema=integ.config_schema,
        adapter_class=integ.adapter_class,
        skill_file=integ.skill_file,
        is_public=integ.is_public,
        is_active=integ.is_active,
        min_plan=integ.min_plan,
        version=integ.version,
        capabilities=list(caps),
    )


@router.post("/definitions", response_model=IntegrationOut, status_code=201)
def create_integration(data: IntegrationCreate, db: Session = Depends(get_db)):
    """Create a new integration definition (admin-only)."""
    existing = db.get(IntegrationDefinition, data.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Integration '{data.id}' already exists")

    integ = IntegrationDefinition(**data.model_dump())
    db.add(integ)
    db.commit()
    db.refresh(integ)
    logger.info("integration_registry.created", integration_id=integ.id)
    return IntegrationOut(
        id=integ.id, name=integ.name, description=integ.description,
        category=integ.category, logo_url=integ.logo_url, auth_type=integ.auth_type,
        config_schema=integ.config_schema, adapter_class=integ.adapter_class,
        skill_file=integ.skill_file, is_public=integ.is_public, is_active=integ.is_active,
        min_plan=integ.min_plan, version=integ.version, capabilities=[],
    )


@router.patch("/definitions/{integration_id}", response_model=IntegrationOut)
def update_integration(integration_id: str, data: IntegrationUpdate, db: Session = Depends(get_db)):
    """Update an integration definition (admin-only)."""
    integ = db.get(IntegrationDefinition, integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(integ, field, value)
    db.commit()
    db.refresh(integ)
    logger.info("integration_registry.updated", integration_id=integ.id)

    caps = db.execute(
        select(IntegrationCapability.capability_id)
        .where(IntegrationCapability.integration_id == integ.id)
    ).scalars().all()
    return IntegrationOut(
        id=integ.id, name=integ.name, description=integ.description,
        category=integ.category, logo_url=integ.logo_url, auth_type=integ.auth_type,
        config_schema=integ.config_schema, adapter_class=integ.adapter_class,
        skill_file=integ.skill_file, is_public=integ.is_public, is_active=integ.is_active,
        min_plan=integ.min_plan, version=integ.version, capabilities=list(caps),
    )


@router.delete("/definitions/{integration_id}", status_code=204)
def delete_integration(integration_id: str, db: Session = Depends(get_db)):
    """Delete an integration definition (admin-only)."""
    integ = db.get(IntegrationDefinition, integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    db.delete(integ)
    db.commit()
    logger.info("integration_registry.deleted", integration_id=integration_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Capability Definitions (Admin-only CRUD)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/capabilities", response_model=list[CapabilityOut])
def list_capabilities(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all capability definitions."""
    query = select(CapabilityDefinition)
    if category:
        query = query.where(CapabilityDefinition.category == category)
    return db.execute(query).scalars().all()


@router.post("/capabilities", response_model=CapabilityOut, status_code=201)
def create_capability(data: CapabilityCreate, db: Session = Depends(get_db)):
    """Create a new capability definition (admin-only)."""
    existing = db.get(CapabilityDefinition, data.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Capability '{data.id}' already exists")

    cap = CapabilityDefinition(**data.model_dump())
    db.add(cap)
    db.commit()
    db.refresh(cap)
    logger.info("capability_registry.created", capability_id=cap.id)
    return cap


@router.delete("/capabilities/{capability_id}", status_code=204)
def delete_capability(capability_id: str, db: Session = Depends(get_db)):
    """Delete a capability definition (admin-only)."""
    cap = db.get(CapabilityDefinition, capability_id)
    if not cap:
        raise HTTPException(status_code=404, detail=f"Capability '{capability_id}' not found")
    db.delete(cap)
    db.commit()
    logger.info("capability_registry.deleted", capability_id=capability_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Integration ↔ Capability Links
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/definitions/{integration_id}/capabilities/{capability_id}", status_code=201)
def link_capability(integration_id: str, capability_id: str, db: Session = Depends(get_db)):
    """Link a capability to an integration."""
    if not db.get(IntegrationDefinition, integration_id):
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    if not db.get(CapabilityDefinition, capability_id):
        raise HTTPException(status_code=404, detail=f"Capability '{capability_id}' not found")

    existing = db.execute(
        select(IntegrationCapability)
        .where(IntegrationCapability.integration_id == integration_id)
        .where(IntegrationCapability.capability_id == capability_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Link already exists")

    link = IntegrationCapability(integration_id=integration_id, capability_id=capability_id)
    db.add(link)
    db.commit()
    logger.info("integration_capability.linked", integration_id=integration_id, capability_id=capability_id)
    return {"status": "linked"}


@router.delete("/definitions/{integration_id}/capabilities/{capability_id}", status_code=204)
def unlink_capability(integration_id: str, capability_id: str, db: Session = Depends(get_db)):
    """Unlink a capability from an integration."""
    link = db.execute(
        select(IntegrationCapability)
        .where(IntegrationCapability.integration_id == integration_id)
        .where(IntegrationCapability.capability_id == capability_id)
    ).scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Tenant Integrations (tenant-scoped)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/tenant/{tenant_id}", response_model=list[TenantIntegrationOut])
def list_tenant_integrations(tenant_id: int, db: Session = Depends(get_db)):
    """List all integrations activated by a tenant."""
    query = (
        select(TenantIntegration)
        .where(TenantIntegration.tenant_id == tenant_id)
    )
    results = db.execute(query).scalars().all()
    out = []
    for ti in results:
        integ = db.get(IntegrationDefinition, ti.integration_id)
        out.append(TenantIntegrationOut(
            id=ti.id,
            tenant_id=ti.tenant_id,
            integration_id=ti.integration_id,
            status=ti.status,
            config_meta=ti.config_meta,
            enabled=ti.enabled,
            last_health_check=str(ti.last_health_check) if ti.last_health_check else None,
            last_error=ti.last_error,
            integration_name=integ.name if integ else None,
        ))
    return out


@router.post("/tenant/{tenant_id}", response_model=TenantIntegrationOut, status_code=201)
def activate_integration(tenant_id: int, data: TenantIntegrationCreate, db: Session = Depends(get_db)):
    """Activate an integration for a tenant (marketplace action)."""
    integ = db.get(IntegrationDefinition, data.integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{data.integration_id}' not found")
    if not integ.is_active:
        raise HTTPException(status_code=400, detail=f"Integration '{data.integration_id}' is not active")

    existing = db.execute(
        select(TenantIntegration)
        .where(TenantIntegration.tenant_id == tenant_id)
        .where(TenantIntegration.integration_id == data.integration_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Integration already activated for this tenant")

    ti = TenantIntegration(
        tenant_id=tenant_id,
        integration_id=data.integration_id,
        config_meta=data.config_meta,
        status=IntegrationStatus.PENDING_SETUP.value,
    )
    db.add(ti)
    db.commit()
    db.refresh(ti)
    logger.info("tenant_integration.activated", tenant_id=tenant_id, integration_id=data.integration_id)
    return TenantIntegrationOut(
        id=ti.id, tenant_id=ti.tenant_id, integration_id=ti.integration_id,
        status=ti.status, config_meta=ti.config_meta, enabled=ti.enabled,
        last_health_check=None, last_error=None, integration_name=integ.name,
    )


@router.patch("/tenant/{tenant_id}/{integration_id}", response_model=TenantIntegrationOut)
def update_tenant_integration(
    tenant_id: int,
    integration_id: str,
    data: TenantIntegrationUpdate,
    db: Session = Depends(get_db),
):
    """Update a tenant's integration configuration."""
    ti = db.execute(
        select(TenantIntegration)
        .where(TenantIntegration.tenant_id == tenant_id)
        .where(TenantIntegration.integration_id == integration_id)
    ).scalar_one_or_none()
    if not ti:
        raise HTTPException(status_code=404, detail="Tenant integration not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ti, field, value)
    db.commit()
    db.refresh(ti)
    logger.info("tenant_integration.updated", tenant_id=tenant_id, integration_id=integration_id)
    integ = db.get(IntegrationDefinition, ti.integration_id)
    return TenantIntegrationOut(
        id=ti.id, tenant_id=ti.tenant_id, integration_id=ti.integration_id,
        status=ti.status, config_meta=ti.config_meta, enabled=ti.enabled,
        last_health_check=str(ti.last_health_check) if ti.last_health_check else None,
        last_error=ti.last_error, integration_name=integ.name if integ else None,
    )


@router.delete("/tenant/{tenant_id}/{integration_id}", status_code=204)
def deactivate_integration(tenant_id: int, integration_id: str, db: Session = Depends(get_db)):
    """Deactivate an integration for a tenant."""
    ti = db.execute(
        select(TenantIntegration)
        .where(TenantIntegration.tenant_id == tenant_id)
        .where(TenantIntegration.integration_id == integration_id)
    ).scalar_one_or_none()
    if not ti:
        raise HTTPException(status_code=404, detail="Tenant integration not found")
    db.delete(ti)
    db.commit()
    logger.info("tenant_integration.deactivated", tenant_id=tenant_id, integration_id=integration_id)
