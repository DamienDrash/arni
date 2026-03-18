"""Admin API for OrchestratorManager — CRUD, versioning, state transitions, tenant overrides."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import get_db
from app.orchestration.manager import OrchestratorManager, get_orchestrator_manager
from app.orchestration.models import OrchestratorTenantOverride

router = APIRouter(prefix="/admin/orchestrators", tags=["orchestrators"])


# ── Pydantic schemas ──────────────────────────────────────────────────────

class ConfigPatchBody(BaseModel):
    patch: dict[str, Any]
    change_summary: str = ""

class StateBody(BaseModel):
    state: str

class RollbackBody(BaseModel):
    target_version: int

class TenantOverrideBody(BaseModel):
    config_override: dict[str, Any]

class CreateOrchestratorBody(BaseModel):
    name: str
    display_name: str
    category: str = "SWARM"
    scope: str = "SYSTEM"
    config: dict[str, Any] = {}
    guardrails: dict[str, Any] | None = None


# ── Helpers ───────────────────────────────────────────────────────────────

def _orch_summary(orch) -> dict:
    return {
        "id": orch.id,
        "name": orch.name,
        "display_name": orch.display_name,
        "category": orch.category,
        "scope": orch.scope,
        "state": orch.status,
        "config_version": orch.config_version,
        "updated_at": orch.updated_at.isoformat() if orch.updated_at else None,
    }


def _version_summary(v) -> dict:
    return {
        "id": v.id,
        "version": v.version,
        "changed_by": v.changed_by,
        "changed_at": v.changed_at.isoformat() if v.changed_at else None,
        "rollback_safe": v.rollback_safe,
        "change_summary": v.change_summary,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("")
def create_orchestrator(
    body: CreateOrchestratorBody,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, {"system_admin"})
    from fastapi import HTTPException
    existing = db.query(OrchestratorDefinition).filter(OrchestratorDefinition.name == body.name).first()
    if existing:
        raise HTTPException(409, f"Orchestrator '{body.name}' already exists")
    valid_categories = {"SWARM", "CAMPAIGN", "AUTOMATION", "SYNC"}
    if body.category not in valid_categories:
        raise HTTPException(422, f"category must be one of {valid_categories}")
    valid_scopes = {"SYSTEM", "TENANT"}
    if body.scope not in valid_scopes:
        raise HTTPException(422, f"scope must be one of {valid_scopes}")
    now = datetime.now(timezone.utc)
    orch = OrchestratorDefinition(
        name=body.name,
        display_name=body.display_name,
        category=body.category,
        scope=body.scope,
        state="ACTIVE",
        config_current=body.config,
        guardrails=body.guardrails,
        config_version=1,
        created_at=now,
        updated_at=now,
        updated_by=user.user_id,
    )
    db.add(orch)
    db.commit()
    db.refresh(orch)
    return {**_orch_summary(orch), "status": "created"}


@router.delete("/{name}")
def delete_orchestrator(
    name: str,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, {"system_admin"})
    from fastapi import HTTPException
    mgr = get_orchestrator_manager(db)
    orch = mgr._get_or_404(name)
    db.delete(orch)
    db.commit()
    return {"status": "deleted", "name": name}


@router.get("")
def list_orchestrators(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, {"system_admin"})
    mgr = get_orchestrator_manager(db)
    return [_orch_summary(o) for o in mgr.list_all()]


@router.get("/{name}")
def get_orchestrator(
    name: str,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, {"system_admin"})
    mgr = get_orchestrator_manager(db)
    config = mgr.get_config(name)
    orch = mgr._get_or_404(name)
    return {**_orch_summary(orch), "config_current": config, "guardrails": orch.guardrails}


@router.put("/{name}/config")
def update_orchestrator_config(
    name: str,
    body: ConfigPatchBody,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, {"system_admin"})
    mgr = get_orchestrator_manager(db)
    version = mgr.update_config(name, body.patch, user.user_id, body.change_summary)
    return {"status": "updated", "version": _version_summary(version)}


@router.post("/{name}/state")
def set_orchestrator_state(
    name: str,
    body: StateBody,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, {"system_admin"})
    mgr = get_orchestrator_manager(db)
    mgr.set_state(name, body.state, user.user_id)
    return {"status": "ok", "new_state": body.state}


@router.get("/{name}/versions")
def list_orchestrator_versions(
    name: str,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, {"system_admin"})
    mgr = get_orchestrator_manager(db)
    return [_version_summary(v) for v in mgr.list_versions(name)]


@router.post("/{name}/rollback")
def rollback_orchestrator(
    name: str,
    body: RollbackBody,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, {"system_admin"})
    mgr = get_orchestrator_manager(db)
    version = mgr.rollback(name, body.target_version, user.user_id)
    return {"status": "rolled_back", "version": _version_summary(version)}


# ── Tenant Override ───────────────────────────────────────────────────────

tenant_override_router = APIRouter(prefix="/admin/tenants", tags=["orchestrators"])


@tenant_override_router.put("/{tenant_id}/orchestrators/{name}")
def set_tenant_override(
    tenant_id: int,
    name: str,
    body: TenantOverrideBody,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, {"system_admin", "tenant_admin"})
    # Tenant admins can only modify their own tenant
    if user.role == "tenant_admin" and user.tenant_id != tenant_id:
        from fastapi import HTTPException
        raise HTTPException(403, "Cannot modify another tenant's overrides")
    mgr = get_orchestrator_manager(db)
    orch = mgr._get_or_404(name)
    override = db.query(OrchestratorTenantOverride).filter(
        OrchestratorTenantOverride.orchestrator_id == orch.id,
        OrchestratorTenantOverride.tenant_id == tenant_id,
    ).first()
    now = datetime.now(timezone.utc)
    if override:
        override.config_override = body.config_override
        override.updated_at = now
    else:
        override = OrchestratorTenantOverride(
            orchestrator_id=orch.id,
            tenant_id=tenant_id,
            config_override=body.config_override,
            created_at=now,
            updated_at=now,
        )
        db.add(override)
    db.commit()
    return {"status": "ok", "tenant_id": tenant_id, "orchestrator": name}
