"""app/platform/api/marketplace.py — Integration Marketplace API.

Provides tenant admins with a self-service marketplace to discover, activate,
configure, and deactivate integrations. Bridges the Integration Registry
with the tenant self-service surface.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.integration_models import TenantIntegration
from app.domains.identity.models import AuditLog
from app.platform.api.marketplace_repository import marketplace_repository
from app.shared.db import open_session

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


def _require_tenant_admin(user: AuthContext) -> AuthContext:
    require_role(user, {"system_admin", "tenant_admin"})
    return user


def _plan_tier_value(slug: Optional[str]) -> int:
    tiers = {
        "free": 0,
        "trial": 0,
        "starter": 1,
        "professional": 2,
        "pro": 2,
        "business": 3,
        "enterprise": 4,
    }
    return tiers.get(slug or "free", 0)


def _get_integration_registry():
    """Load the Phase-2 registry models if available."""
    try:
        from app.core.integration_models import CapabilityDefinition, IntegrationStatus

        return CapabilityDefinition, IntegrationStatus
    except ImportError:
        return None, None


def _audit(db, tenant_id: int, user_id: str, action: str, details: dict[str, Any]) -> None:
    try:
        db.add(
            AuditLog(
                actor_user_id=int(user_id) if str(user_id).isdigit() else None,
                tenant_id=tenant_id,
                action=action,
                category="marketplace",
                target_type="integration",
                target_id=str(details.get("integration_id", "")) or None,
                details_json=json.dumps(details, ensure_ascii=False, default=str),
                created_at=datetime.now(timezone.utc),
            )
        )
    except Exception:
        logger.warning("audit_log.write_failed", action=action)


def _read_config_meta(tenant_integration: TenantIntegration | None) -> dict[str, Any]:
    if tenant_integration is None:
        return {}

    raw = getattr(tenant_integration, "config_meta", None)
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _read_enabled_capabilities(tenant_integration: TenantIntegration | None) -> list[str]:
    if tenant_integration is None:
        return []

    legacy = getattr(tenant_integration, "enabled_capabilities", None)
    if isinstance(legacy, str) and legacy:
        try:
            parsed = json.loads(legacy)
        except Exception:
            parsed = []
        if isinstance(parsed, list):
            return [str(item) for item in parsed]

    enabled = _read_config_meta(tenant_integration).get("enabled_capabilities", [])
    if isinstance(enabled, list):
        return [str(item) for item in enabled]
    return []


def _write_enabled_capabilities(tenant_integration: TenantIntegration, capability_ids: list[str]) -> None:
    if hasattr(tenant_integration, "enabled_capabilities"):
        tenant_integration.enabled_capabilities = json.dumps(capability_ids)
        return

    config_meta = _read_config_meta(tenant_integration)
    config_meta["enabled_capabilities"] = capability_ids
    tenant_integration.config_meta = config_meta


def _write_config_meta(tenant_integration: TenantIntegration, config: dict[str, Any]) -> None:
    if hasattr(tenant_integration, "settings"):
        tenant_integration.settings = json.dumps(config)
        return

    config_meta = dict(config)
    enabled_capabilities = _read_config_meta(tenant_integration).get("enabled_capabilities")
    if isinstance(enabled_capabilities, list):
        config_meta["enabled_capabilities"] = enabled_capabilities
    tenant_integration.config_meta = config_meta


class ActivateRequest(BaseModel):
    credentials: Optional[dict] = Field(None, description="Integration credentials")
    config: Optional[dict] = Field(None, description="Integration-specific configuration")


class ConfigureRequest(BaseModel):
    credentials: Optional[dict] = Field(None, description="Updated credentials")
    config: Optional[dict] = Field(None, description="Updated configuration")


class CapabilityToggle(BaseModel):
    enabled: bool = Field(..., description="Whether the capability is enabled")


@router.get("/catalog")
async def browse_catalog(
    user: AuthContext = Depends(get_current_user),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name"),
) -> dict[str, Any]:
    _require_tenant_admin(user)
    db = open_session()
    try:
        CapabilityDefinition, IntegrationStatus = _get_integration_registry()

        if CapabilityDefinition is None:
            from app.integrations.connector_registry import list_connectors

            connectors = list_connectors()
            tenant_plan = marketplace_repository.get_tenant_plan_slug(db, user.tenant_id)
            tenant_tier = _plan_tier_value(tenant_plan)

            catalog = []
            for connector in connectors:
                min_tier = _plan_tier_value(connector.get("min_plan", "starter"))
                available = tenant_tier >= min_tier
                catalog.append(
                    {
                        "id": connector.get("id", connector.get("name", "").lower()),
                        "name": connector.get("name", ""),
                        "description": connector.get("description", ""),
                        "category": connector.get("category", "general"),
                        "icon": connector.get("icon", ""),
                        "available_for_plan": available,
                        "min_plan": connector.get("min_plan", "starter"),
                        "status": "available",
                    }
                )

            if category:
                catalog = [item for item in catalog if item["category"] == category]
            if search:
                needle = search.lower()
                catalog = [
                    item
                    for item in catalog
                    if needle in item["name"].lower() or needle in item["description"].lower()
                ]
            return {"catalog": catalog, "total": len(catalog)}

        integrations = marketplace_repository.list_active_integrations(db, category=category)
        tenant_plan = marketplace_repository.get_tenant_plan_slug(db, user.tenant_id)
        tenant_tier = _plan_tier_value(tenant_plan)
        active_ids = marketplace_repository.list_active_tenant_integration_ids(
            db, tenant_id=user.tenant_id
        )

        catalog = []
        for integration in integrations:
            min_plan = getattr(integration, "min_plan", "starter")
            caps = marketplace_repository.list_capability_ids(db, integration_id=integration.id)

            item = {
                "id": integration.id,
                "name": integration.name,
                "slug": integration.id,
                "description": integration.description,
                "category": integration.category,
                "version": getattr(integration, "version", "1.0"),
                "icon_url": getattr(integration, "logo_url", ""),
                "available_for_plan": tenant_tier >= _plan_tier_value(min_plan),
                "min_plan": min_plan,
                "is_activated": integration.id in active_ids,
                "capabilities_count": len(caps),
            }

            if search:
                needle = search.lower()
                if needle not in item["name"].lower() and needle not in (item["description"] or "").lower():
                    continue

            catalog.append(item)

        return {"catalog": catalog, "total": len(catalog)}
    finally:
        db.close()


@router.get("/catalog/{integration_id}")
async def get_integration_detail(
    integration_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_tenant_admin(user)
    db = open_session()
    try:
        CapabilityDefinition, IntegrationStatus = _get_integration_registry()
        if CapabilityDefinition is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integration = marketplace_repository.get_integration(db, integration_id=integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        capabilities = marketplace_repository.list_capabilities(db, integration_id=integration.id)
        tenant_integration = marketplace_repository.get_tenant_integration(
            db,
            tenant_id=user.tenant_id,
            integration_id=integration.id,
        )

        return {
            "integration": {
                "id": integration.id,
                "name": integration.name,
                "slug": integration.id,
                "description": integration.description,
                "category": integration.category,
                "version": getattr(integration, "version", "1.0"),
                "adapter_class": getattr(integration, "adapter_class", ""),
                "config_schema": getattr(integration, "config_schema", {}) or {},
                "icon_url": getattr(integration, "logo_url", ""),
                "documentation_url": getattr(integration, "documentation_url", ""),
            },
            "capabilities": [
                {
                    "id": capability.id,
                    "name": capability.name,
                    "slug": capability.id,
                    "description": capability.description,
                    "tool_name": getattr(capability, "tool_name", ""),
                }
                for capability in capabilities
            ],
            "tenant_status": {
                "is_activated": tenant_integration is not None and tenant_integration.status != "inactive",
                "status": tenant_integration.status if tenant_integration else "inactive",
                "activated_at": (
                    str(tenant_integration.created_at)
                    if tenant_integration and getattr(tenant_integration, "created_at", None)
                    else None
                ),
                "enabled_capabilities": _read_enabled_capabilities(tenant_integration),
            },
        }
    finally:
        db.close()


@router.post("/activate/{integration_id}")
async def activate_integration(
    integration_id: str,
    body: ActivateRequest = ActivateRequest(),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_tenant_admin(user)
    db = open_session()
    try:
        CapabilityDefinition, IntegrationStatus = _get_integration_registry()
        if CapabilityDefinition is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integration = marketplace_repository.get_integration(db, integration_id=integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        tenant_plan = marketplace_repository.get_tenant_plan_slug(db, user.tenant_id)
        min_plan = getattr(integration, "min_plan", "starter")
        if _plan_tier_value(tenant_plan) < _plan_tier_value(min_plan):
            raise HTTPException(
                status_code=403,
                detail=f"Your plan '{tenant_plan}' does not include this integration. Minimum: '{min_plan}'",
            )

        existing = marketplace_repository.get_tenant_integration(
            db,
            tenant_id=user.tenant_id,
            integration_id=integration_id,
        )
        if existing and existing.status == "active" and getattr(existing, "enabled", True):
            return {"status": "already_active", "integration": integration.name}

        cap_ids = marketplace_repository.list_capability_ids(db, integration_id=integration.id)
        if existing:
            existing.status = "active"
            existing.enabled = True
            existing.config_encrypted = json.dumps(body.credentials or {})
            _write_config_meta(existing, body.config or {})
            _write_enabled_capabilities(existing, cap_ids)
        else:
            db.add(
                TenantIntegration(
                    tenant_id=user.tenant_id,
                    integration_id=integration_id,
                    status="active",
                    enabled=True,
                    config_encrypted=json.dumps(body.credentials or {}),
                    config_meta={**(body.config or {}), "enabled_capabilities": cap_ids},
                )
            )

        _audit(
            db,
            user.tenant_id,
            user.user_id,
            "integration.activated",
            {
                "integration_id": integration_id,
                "integration_name": integration.name,
                "capabilities": len(cap_ids),
            },
        )
        db.commit()
        logger.info(
            "marketplace.integration_activated",
            tenant_id=user.tenant_id,
            integration=integration.name,
        )
        return {
            "status": "activated",
            "integration": integration.name,
            "capabilities_enabled": len(cap_ids),
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Activation failed: {str(exc)}")
    finally:
        db.close()


@router.post("/deactivate/{integration_id}")
async def deactivate_integration(
    integration_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_tenant_admin(user)
    db = open_session()
    try:
        CapabilityDefinition, IntegrationStatus = _get_integration_registry()
        if CapabilityDefinition is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integration = marketplace_repository.get_integration(db, integration_id=integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        existing = marketplace_repository.get_tenant_integration(
            db,
            tenant_id=user.tenant_id,
            integration_id=integration_id,
        )
        if not existing or existing.status == "inactive":
            return {"status": "already_inactive", "integration": integration.name}

        existing.status = "inactive"
        existing.enabled = False
        _audit(
            db,
            user.tenant_id,
            user.user_id,
            "integration.deactivated",
            {
                "integration_id": integration_id,
                "integration_name": integration.name,
            },
        )
        db.commit()
        logger.info(
            "marketplace.integration_deactivated",
            tenant_id=user.tenant_id,
            integration=integration.name,
        )
        return {"status": "deactivated", "integration": integration.name}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Deactivation failed: {str(exc)}")
    finally:
        db.close()


@router.get("/my-integrations")
async def get_my_integrations(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_tenant_admin(user)
    db = open_session()
    try:
        CapabilityDefinition, IntegrationStatus = _get_integration_registry()
        if CapabilityDefinition is None:
            return {"integrations": [], "total": 0}

        tenant_integrations = marketplace_repository.list_tenant_integrations(
            db,
            tenant_id=user.tenant_id,
        )
        result = []
        for tenant_integration in tenant_integrations:
            integration = marketplace_repository.get_integration(
                db,
                integration_id=tenant_integration.integration_id,
            )
            if not integration:
                continue

            cap_ids = marketplace_repository.list_capability_ids(db, integration_id=integration.id)
            enabled_ids = _read_enabled_capabilities(tenant_integration)
            result.append(
                {
                    "integration_id": integration.id,
                    "name": integration.name,
                    "slug": integration.id,
                    "category": integration.category,
                    "status": tenant_integration.status,
                    "capabilities_total": len(cap_ids),
                    "capabilities_enabled": len(enabled_ids),
                    "activated_at": (
                        str(tenant_integration.created_at)
                        if getattr(tenant_integration, "created_at", None)
                        else None
                    ),
                }
            )

        return {"integrations": result, "total": len(result)}
    finally:
        db.close()


@router.put("/configure/{integration_id}")
async def configure_integration(
    integration_id: str,
    body: ConfigureRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_tenant_admin(user)
    db = open_session()
    try:
        CapabilityDefinition, IntegrationStatus = _get_integration_registry()
        if CapabilityDefinition is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        existing = marketplace_repository.get_tenant_integration(
            db,
            tenant_id=user.tenant_id,
            integration_id=integration_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Integration not activated for this tenant")

        updated_fields: list[str] = []
        if body.credentials is not None:
            existing.config_encrypted = json.dumps(body.credentials)
            updated_fields.append("credentials")
        if body.config is not None:
            _write_config_meta(existing, body.config)
            updated_fields.append("config")

        _audit(
            db,
            user.tenant_id,
            user.user_id,
            "integration.configured",
            {"integration_id": integration_id, "updated_fields": updated_fields},
        )
        db.commit()
        logger.info(
            "marketplace.integration_configured",
            tenant_id=user.tenant_id,
            integration_id=integration_id,
        )
        return {"status": "configured", "updated_fields": updated_fields}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Configuration failed: {str(exc)}")
    finally:
        db.close()


@router.post("/test/{integration_id}")
async def test_integration(
    integration_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_tenant_admin(user)
    db = open_session()
    try:
        CapabilityDefinition, IntegrationStatus = _get_integration_registry()
        if CapabilityDefinition is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integration = marketplace_repository.get_integration(db, integration_id=integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        tenant_integration = marketplace_repository.get_tenant_integration(
            db,
            tenant_id=user.tenant_id,
            integration_id=integration_id,
        )
        if not tenant_integration:
            raise HTTPException(status_code=404, detail="Integration not activated")

        try:
            from app.integrations.adapters.registry import AdapterRegistry

            registry = AdapterRegistry()
            adapter_class = registry.get_adapter(integration.id)
            if adapter_class:
                credentials = (
                    json.loads(tenant_integration.config_encrypted)
                    if tenant_integration.config_encrypted
                    else {}
                )
                adapter = adapter_class(credentials=credentials, tenant_id=user.tenant_id)
                if hasattr(adapter, "health_check"):
                    health = (
                        await adapter.health_check()
                        if asyncio.iscoroutinefunction(adapter.health_check)
                        else adapter.health_check()
                    )
                    return {
                        "status": "success" if health else "failed",
                        "integration": integration.name,
                        "message": "Connection successful" if health else "Connection failed",
                    }

            return {
                "status": "unknown",
                "integration": integration.name,
                "message": "No health check available for this adapter",
            }
        except Exception as exc:
            return {
                "status": "failed",
                "integration": integration.name,
                "message": f"Connection test failed: {str(exc)[:200]}",
            }
    finally:
        db.close()


@router.get("/capabilities/{integration_id}")
async def get_capabilities(
    integration_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_tenant_admin(user)
    db = open_session()
    try:
        CapabilityDefinition, IntegrationStatus = _get_integration_registry()
        if CapabilityDefinition is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        integration = marketplace_repository.get_integration(db, integration_id=integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        capabilities = marketplace_repository.list_capabilities(db, integration_id=integration.id)
        tenant_integration = marketplace_repository.get_tenant_integration(
            db,
            tenant_id=user.tenant_id,
            integration_id=integration_id,
        )
        enabled_ids = set(_read_enabled_capabilities(tenant_integration))

        return {
            "integration": integration.name,
            "capabilities": [
                {
                    "id": capability.id,
                    "name": capability.name,
                    "slug": capability.id,
                    "description": capability.description,
                    "tool_name": getattr(capability, "tool_name", ""),
                    "enabled": capability.id in enabled_ids,
                }
                for capability in capabilities
            ],
        }
    finally:
        db.close()


@router.put("/capabilities/{integration_id}/{capability_id}")
async def toggle_capability(
    integration_id: str,
    capability_id: str,
    body: CapabilityToggle,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_tenant_admin(user)
    db = open_session()
    try:
        CapabilityDefinition, IntegrationStatus = _get_integration_registry()
        if CapabilityDefinition is None:
            raise HTTPException(status_code=501, detail="Integration Registry not available")

        tenant_integration = marketplace_repository.get_tenant_integration(
            db,
            tenant_id=user.tenant_id,
            integration_id=integration_id,
        )
        if not tenant_integration:
            raise HTTPException(status_code=404, detail="Integration not activated")

        capability = next(
            (
                item
                for item in marketplace_repository.list_capabilities(db, integration_id=integration_id)
                if item.id == capability_id
            ),
            None,
        )
        if not capability:
            raise HTTPException(status_code=404, detail="Capability not found")

        enabled_ids = set(_read_enabled_capabilities(tenant_integration))
        if body.enabled:
            enabled_ids.add(capability_id)
        else:
            enabled_ids.discard(capability_id)
        _write_enabled_capabilities(tenant_integration, sorted(enabled_ids))

        _audit(
            db,
            user.tenant_id,
            user.user_id,
            "capability.toggled",
            {
                "integration_id": integration_id,
                "capability_id": capability_id,
                "capability_name": capability.name,
                "enabled": body.enabled,
            },
        )
        db.commit()
        logger.info(
            "marketplace.capability_toggled",
            tenant_id=user.tenant_id,
            capability=capability.name,
            enabled=body.enabled,
        )
        return {"status": "updated", "capability": capability.name, "enabled": body.enabled}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Toggle failed: {str(exc)}")
    finally:
        db.close()
