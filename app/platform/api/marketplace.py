"""app/platform/api/marketplace.py — Integration Marketplace API.

Provides tenant admins with a self-service marketplace to discover, activate,
configure, and deactivate integrations. Bridges the Integration Registry
(Phase 2) with the Tenant Portal (Phase 5).

Endpoints (prefix /api/v1/marketplace):
    GET  /catalog                    → Browse available integrations (with plan filtering)
    GET  /catalog/{integration_id}   → Integration detail with capabilities
    GET  /my-integrations            → Tenant's active integrations
    POST /activate/{integration_id}  → Activate an integration for this tenant
    POST /deactivate/{integration_id}→ Deactivate an integration
    PUT  /configure/{integration_id} → Update integration credentials/config
    POST /test/{integration_id}      → Test integration connectivity
    GET  /capabilities/{integration_id} → List capabilities for an integration
    PUT  /capabilities/{integration_id}/{cap_id} → Enable/disable a capability
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import Tenant, Subscription, Plan, AuditLog, TenantConfig

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _require_tenant_admin(user: AuthContext) -> AuthContext:
    require_role(user, {"system_admin", "tenant_admin"})
    return user


def _get_tenant_plan(db, tenant_id: int) -> Optional[str]:
    """Get the current plan slug for a tenant."""
    sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
    if sub and sub.plan_id:
        plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
        return plan.slug if plan else None
    return None


def _plan_tier_value(slug: Optional[str]) -> int:
    """Convert plan slug to numeric tier for comparison."""
    tiers = {
        "free": 0, "starter": 1, "professional": 2,
        "pro": 2, "business": 3, "enterprise": 4,
    }
    return tiers.get(slug or "free", 0)


def _get_integration_registry(db):
    """Load integration definitions from the registry (Phase 2 models)."""
    try:
        from app.core.integration_models import (
            IntegrationDefinition, CapabilityDefinition, TenantIntegration,
            IntegrationStatus,
        )
        return IntegrationDefinition, CapabilityDefinition, TenantIntegration, IntegrationStatus
    except ImportError:
        return None, None, None, None


def _audit(db, tenant_id: int, user_id: int, action: str, details: dict) -> None:
    try:
        db.add(AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            details=json.dumps(details, ensure_ascii=False, default=str),
            created_at=datetime.now(timezone.utc),
        ))
    except Exception:
        logger.warning("audit_log.write_failed", action=action)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class ActivateRequest(BaseModel):
    """Request to activate an integration."""
    credentials: Optional[dict] = Field(None, description="Integration credentials (API keys, tokens)")
    config: Optional[dict] = Field(None, description="Integration-specific configuration")


class ConfigureRequest(BaseModel):
    """Request to update integration configuration."""
    credentials: Optional[dict] = Field(None, description="Updated credentials")
    config: Optional[dict] = Field(None, description="Updated configuration")


class CapabilityToggle(BaseModel):
    """Request to enable/disable a capability."""
    enabled: bool = Field(..., description="Whether the capability is enabled")


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS: CATALOG
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/catalog")
async def browse_catalog(
    user: AuthContext = Depends(get_current_user),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name"),
) -> dict[str, Any]:
    """Browse available integrations in the marketplace."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        IntDef, CapDef, TenantInt, IntStatus = _get_integration_registry(db)

        if IntDef is None:
            # Fallback: return from connector registry
            from app.integrations.connector_registry import list_connectors
            connectors = list_connectors()
            tenant_plan = _get_tenant_plan(db, user.tenant_id)
            tenant_tier = _plan_tier_value(tenant_plan)

            catalog = []
            for c in connectors:
                min_tier = _plan_tier_value(c.get("min_plan", "starter"))
                available = tenant_tier >= min_tier
                catalog.append({
                    "id": c.get("id", c.get("name", "").lower()),
                    "name": c.get("name", ""),
                    "description": c.get("description", ""),
                    "category": c.get("category", "general"),
                    "icon": c.get("icon", ""),
                    "available_for_plan": available,
                    "min_plan": c.get("min_plan", "starter"),
                    "status": "available",
                })

            if category:
                catalog = [c for c in catalog if c["category"] == category]
            if search:
                search_lower = search.lower()
                catalog = [c for c in catalog
                          if search_lower in c["name"].lower()
                          or search_lower in c["description"].lower()]

            return {"catalog": catalog, "total": len(catalog)}

        # Use Integration Registry (Phase 2)
        query = db.query(IntDef).filter(IntDef.is_active == True)
        if category:
            query = query.filter(IntDef.category == category)

        integrations = query.all()
        tenant_plan = _get_tenant_plan(db, user.tenant_id)
        tenant_tier = _plan_tier_value(tenant_plan)

        # Get tenant's active integrations
        active_ids = set()
        if TenantInt:
            active = db.query(TenantInt).filter(
                TenantInt.tenant_id == user.tenant_id,
                TenantInt.status != "inactive",
            ).all()
            active_ids = {a.integration_id for a in active}

        catalog = []
        for integ in integrations:
            min_tier = _plan_tier_value(getattr(integ, "min_plan", "starter"))
            available = tenant_tier >= min_tier

            caps = []
            if CapDef:
                caps = db.query(CapDef).filter(
                    CapDef.integration_id == integ.id
                ).all()

            item = {
                "id": integ.id,
                "name": integ.name,
                "slug": integ.slug,
                "description": integ.description,
                "category": integ.category,
                "version": getattr(integ, "version", "1.0"),
                "icon_url": getattr(integ, "icon_url", ""),
                "available_for_plan": available,
                "min_plan": getattr(integ, "min_plan", "starter"),
                "is_activated": integ.id in active_ids,
                "capabilities_count": len(caps),
            }

            if search:
                search_lower = search.lower()
                if (search_lower not in item["name"].lower()
                        and search_lower not in (item.get("description") or "").lower()):
                    continue

            catalog.append(item)

        return {"catalog": catalog, "total": len(catalog)}
    finally:
        db.close()


@router.get("/catalog/{integration_id}")
async def get_integration_detail(
    integration_id: int,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Get detailed information about a specific integration."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        IntDef, CapDef, TenantInt, IntStatus = _get_integration_registry(db)
        if IntDef is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integ = db.query(IntDef).filter(IntDef.id == integration_id).first()
        if not integ:
            raise HTTPException(status_code=404, detail="Integration not found")

        caps = []
        if CapDef:
            caps = db.query(CapDef).filter(CapDef.integration_id == integ.id).all()

        # Check if tenant has this activated
        tenant_int = None
        if TenantInt:
            tenant_int = db.query(TenantInt).filter(
                TenantInt.tenant_id == user.tenant_id,
                TenantInt.integration_id == integ.id,
            ).first()

        return {
            "integration": {
                "id": integ.id,
                "name": integ.name,
                "slug": integ.slug,
                "description": integ.description,
                "category": integ.category,
                "version": getattr(integ, "version", "1.0"),
                "adapter_class": getattr(integ, "adapter_class", ""),
                "config_schema": getattr(integ, "config_schema", {}),
                "icon_url": getattr(integ, "icon_url", ""),
                "documentation_url": getattr(integ, "documentation_url", ""),
            },
            "capabilities": [
                {
                    "id": c.id,
                    "name": c.name,
                    "slug": c.slug,
                    "description": c.description,
                    "tool_name": getattr(c, "tool_name", ""),
                }
                for c in caps
            ],
            "tenant_status": {
                "is_activated": tenant_int is not None,
                "status": tenant_int.status if tenant_int else "inactive",
                "activated_at": str(tenant_int.created_at) if tenant_int and hasattr(tenant_int, "created_at") else None,
                "enabled_capabilities": json.loads(tenant_int.enabled_capabilities)
                    if tenant_int and hasattr(tenant_int, "enabled_capabilities") and tenant_int.enabled_capabilities
                    else [],
            },
        }
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS: ACTIVATION / DEACTIVATION
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/activate/{integration_id}")
async def activate_integration(
    integration_id: int,
    body: ActivateRequest = ActivateRequest(),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Activate an integration for this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        IntDef, CapDef, TenantInt, IntStatus = _get_integration_registry(db)
        if IntDef is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integ = db.query(IntDef).filter(IntDef.id == integration_id).first()
        if not integ:
            raise HTTPException(status_code=404, detail="Integration not found")

        # Plan check
        tenant_plan = _get_tenant_plan(db, user.tenant_id)
        min_plan = getattr(integ, "min_plan", "starter")
        if _plan_tier_value(tenant_plan) < _plan_tier_value(min_plan):
            raise HTTPException(
                status_code=403,
                detail=f"Your plan '{tenant_plan}' does not include this integration. Minimum: '{min_plan}'",
            )

        # Check if already activated
        existing = db.query(TenantInt).filter(
            TenantInt.tenant_id == user.tenant_id,
            TenantInt.integration_id == integration_id,
        ).first()

        if existing and existing.status == "active":
            return {"status": "already_active", "integration": integ.name}

        # Get all capabilities for this integration
        caps = db.query(CapDef).filter(CapDef.integration_id == integ.id).all()
        cap_ids = [c.id for c in caps]

        if existing:
            existing.status = "active"
            existing.config_encrypted = json.dumps(body.credentials or {})
            existing.settings = json.dumps(body.config or {})
            existing.enabled_capabilities = json.dumps(cap_ids)
        else:
            new_ti = TenantInt(
                tenant_id=user.tenant_id,
                integration_id=integration_id,
                status="active",
                config_encrypted=json.dumps(body.credentials or {}),
                settings=json.dumps(body.config or {}),
                enabled_capabilities=json.dumps(cap_ids),
            )
            db.add(new_ti)

        _audit(db, user.tenant_id, user.user_id, "integration.activated", {
            "integration_id": integration_id,
            "integration_name": integ.name,
            "capabilities": len(cap_ids),
        })

        db.commit()
        logger.info("marketplace.integration_activated",
                     tenant_id=user.tenant_id, integration=integ.name)

        return {
            "status": "activated",
            "integration": integ.name,
            "capabilities_enabled": len(cap_ids),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Activation failed: {str(e)}")
    finally:
        db.close()


@router.post("/deactivate/{integration_id}")
async def deactivate_integration(
    integration_id: int,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Deactivate an integration for this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        IntDef, CapDef, TenantInt, IntStatus = _get_integration_registry(db)
        if IntDef is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integ = db.query(IntDef).filter(IntDef.id == integration_id).first()
        if not integ:
            raise HTTPException(status_code=404, detail="Integration not found")

        existing = db.query(TenantInt).filter(
            TenantInt.tenant_id == user.tenant_id,
            TenantInt.integration_id == integration_id,
        ).first()

        if not existing or existing.status == "inactive":
            return {"status": "already_inactive", "integration": integ.name}

        existing.status = "inactive"

        _audit(db, user.tenant_id, user.user_id, "integration.deactivated", {
            "integration_id": integration_id,
            "integration_name": integ.name,
        })

        db.commit()
        logger.info("marketplace.integration_deactivated",
                     tenant_id=user.tenant_id, integration=integ.name)

        return {"status": "deactivated", "integration": integ.name}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Deactivation failed: {str(e)}")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS: CONFIGURATION & TESTING
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/my-integrations")
async def get_my_integrations(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """List all integrations activated by this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        IntDef, CapDef, TenantInt, IntStatus = _get_integration_registry(db)
        if IntDef is None:
            return {"integrations": [], "total": 0}

        tenant_ints = db.query(TenantInt).filter(
            TenantInt.tenant_id == user.tenant_id,
        ).all()

        result = []
        for ti in tenant_ints:
            integ = db.query(IntDef).filter(IntDef.id == ti.integration_id).first()
            if not integ:
                continue

            caps = db.query(CapDef).filter(CapDef.integration_id == integ.id).all()
            enabled_caps = json.loads(ti.enabled_capabilities) if ti.enabled_capabilities else []

            result.append({
                "integration_id": integ.id,
                "name": integ.name,
                "slug": integ.slug,
                "category": integ.category,
                "status": ti.status,
                "capabilities_total": len(caps),
                "capabilities_enabled": len(enabled_caps),
                "activated_at": str(ti.created_at) if hasattr(ti, "created_at") else None,
            })

        return {"integrations": result, "total": len(result)}
    finally:
        db.close()


@router.put("/configure/{integration_id}")
async def configure_integration(
    integration_id: int,
    body: ConfigureRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Update credentials or configuration for an activated integration."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        IntDef, CapDef, TenantInt, IntStatus = _get_integration_registry(db)
        if IntDef is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        existing = db.query(TenantInt).filter(
            TenantInt.tenant_id == user.tenant_id,
            TenantInt.integration_id == integration_id,
        ).first()

        if not existing:
            raise HTTPException(status_code=404, detail="Integration not activated for this tenant")

        updated_fields = []
        if body.credentials is not None:
            existing.config_encrypted = json.dumps(body.credentials)
            updated_fields.append("credentials")

        if body.config is not None:
            existing.settings = json.dumps(body.config)
            updated_fields.append("config")

        _audit(db, user.tenant_id, user.user_id, "integration.configured", {
            "integration_id": integration_id,
            "updated_fields": updated_fields,
        })

        db.commit()
        logger.info("marketplace.integration_configured",
                     tenant_id=user.tenant_id, integration_id=integration_id)

        return {"status": "configured", "updated_fields": updated_fields}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Configuration failed: {str(e)}")
    finally:
        db.close()


@router.post("/test/{integration_id}")
async def test_integration(
    integration_id: int,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Test connectivity for an activated integration."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        IntDef, CapDef, TenantInt, IntStatus = _get_integration_registry(db)
        if IntDef is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integ = db.query(IntDef).filter(IntDef.id == integration_id).first()
        if not integ:
            raise HTTPException(status_code=404, detail="Integration not found")

        existing = db.query(TenantInt).filter(
            TenantInt.tenant_id == user.tenant_id,
            TenantInt.integration_id == integration_id,
        ).first()

        if not existing:
            raise HTTPException(status_code=404, detail="Integration not activated")

        # Try to load the adapter and run health check
        try:
            from app.integrations.adapters.registry import AdapterRegistry
            registry = AdapterRegistry()
            adapter_class = registry.get_adapter(integ.slug)

            if adapter_class:
                credentials = json.loads(existing.config_encrypted) if existing.config_encrypted else {}
                adapter = adapter_class(credentials=credentials, tenant_id=user.tenant_id)

                if hasattr(adapter, "health_check"):
                    health = await adapter.health_check() if asyncio.iscoroutinefunction(adapter.health_check) else adapter.health_check()
                    return {
                        "status": "success" if health else "failed",
                        "integration": integ.name,
                        "message": "Connection successful" if health else "Connection failed",
                    }

            return {
                "status": "unknown",
                "integration": integ.name,
                "message": "No health check available for this adapter",
            }
        except Exception as e:
            return {
                "status": "failed",
                "integration": integ.name,
                "message": f"Connection test failed: {str(e)[:200]}",
            }
    finally:
        db.close()


@router.get("/capabilities/{integration_id}")
async def get_capabilities(
    integration_id: int,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """List all capabilities for an integration with their enabled status."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        IntDef, CapDef, TenantInt, IntStatus = _get_integration_registry(db)
        if IntDef is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integ = db.query(IntDef).filter(IntDef.id == integration_id).first()
        if not integ:
            raise HTTPException(status_code=404, detail="Integration not found")

        caps = db.query(CapDef).filter(CapDef.integration_id == integ.id).all()

        # Get enabled capabilities for this tenant
        enabled_ids = set()
        tenant_int = db.query(TenantInt).filter(
            TenantInt.tenant_id == user.tenant_id,
            TenantInt.integration_id == integration_id,
        ).first()
        if tenant_int and tenant_int.enabled_capabilities:
            enabled_ids = set(json.loads(tenant_int.enabled_capabilities))

        return {
            "integration": integ.name,
            "capabilities": [
                {
                    "id": c.id,
                    "name": c.name,
                    "slug": c.slug,
                    "description": c.description,
                    "tool_name": getattr(c, "tool_name", ""),
                    "enabled": c.id in enabled_ids,
                }
                for c in caps
            ],
        }
    finally:
        db.close()


@router.put("/capabilities/{integration_id}/{capability_id}")
async def toggle_capability(
    integration_id: int,
    capability_id: int,
    body: CapabilityToggle,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Enable or disable a specific capability for an integration."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        IntDef, CapDef, TenantInt, IntStatus = _get_integration_registry(db)
        if IntDef is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        tenant_int = db.query(TenantInt).filter(
            TenantInt.tenant_id == user.tenant_id,
            TenantInt.integration_id == integration_id,
        ).first()

        if not tenant_int:
            raise HTTPException(status_code=404, detail="Integration not activated")

        # Verify capability exists
        cap = db.query(CapDef).filter(
            CapDef.id == capability_id,
            CapDef.integration_id == integration_id,
        ).first()
        if not cap:
            raise HTTPException(status_code=404, detail="Capability not found")

        enabled_ids = set(json.loads(tenant_int.enabled_capabilities)) if tenant_int.enabled_capabilities else set()

        if body.enabled:
            enabled_ids.add(capability_id)
        else:
            enabled_ids.discard(capability_id)

        tenant_int.enabled_capabilities = json.dumps(list(enabled_ids))

        _audit(db, user.tenant_id, user.user_id, "capability.toggled", {
            "integration_id": integration_id,
            "capability_id": capability_id,
            "capability_name": cap.name,
            "enabled": body.enabled,
        })

        db.commit()
        logger.info("marketplace.capability_toggled",
                     tenant_id=user.tenant_id, capability=cap.name, enabled=body.enabled)

        return {
            "status": "updated",
            "capability": cap.name,
            "enabled": body.enabled,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Toggle failed: {str(e)}")
    finally:
        db.close()
