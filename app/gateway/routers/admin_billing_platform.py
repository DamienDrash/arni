from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user
from app.gateway.admin_shared import require_system_admin, require_tenant_admin_or_system
from app.gateway.services.admin_billing_platform_service import service

router = APIRouter(
    prefix="/admin",
    tags=["admin-billing-platform"],
    dependencies=[Depends(get_current_user)],
)


class PlansConfigUpdate(BaseModel):
    plans: list[dict[str, Any]]
    providers: list[dict[str, Any]]
    default_provider: str = "stripe"


class StripeConnectorConfig(BaseModel):
    enabled: bool = False
    mode: str = "test"
    publishable_key: str | None = None
    secret_key: str | None = None
    webhook_secret: str | None = None


class BillingConnectorsUpdate(BaseModel):
    stripe: StripeConnectorConfig


class LlmProviderConfig(BaseModel):
    id: str
    name: str
    base_url: str
    models: list[str]
    api_key: Optional[str] = None


@router.get("/plans/config")
async def get_plans_config(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_system_admin(user)
    return service.get_plans_config(user)


@router.put("/plans/config")
async def update_plans_config(
    body: PlansConfigUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_system_admin(user)
    try:
        return service.update_plans_config(user, providers=body.providers or [], default_provider=body.default_provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/billing/connectors")
async def get_billing_connectors(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_system_admin(user)
    return service.get_billing_connectors(user)


@router.put("/billing/connectors")
async def update_billing_connectors(
    body: BillingConnectorsUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_system_admin(user)
    try:
        return service.update_billing_connectors(
            user,
            enabled=body.stripe.enabled,
            mode=body.stripe.mode,
            publishable_key=body.stripe.publishable_key,
            secret_key=body.stripe.secret_key,
            webhook_secret=body.stripe.webhook_secret,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/billing/connectors/stripe/test")
async def test_stripe_connector(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_system_admin(user)
    try:
        return await service.test_stripe_connector(user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/billing/subscription")
async def get_billing_subscription(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_billing_subscription(user)


@router.get("/billing/usage")
async def get_billing_usage(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_billing_usage(user)


@router.get("/platform/llm/predefined")
async def get_predefined_providers(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_system_admin(user)
    return service.get_predefined_providers()


@router.get("/platform/llm/providers")
async def get_platform_llm_providers(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_system_admin(user)
    return service.get_platform_llm_providers(user)


@router.post("/platform/llm/providers")
async def save_platform_llm_provider(
    body: LlmProviderConfig,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_system_admin(user)
    return service.save_platform_llm_provider(
        user,
        provider_id=body.id,
        name=body.name,
        base_url=body.base_url,
        models=body.models,
        api_key=body.api_key,
    )


@router.delete("/platform/llm/providers/{provider_id}")
async def delete_platform_llm_provider(
    provider_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_system_admin(user)
    return service.delete_platform_llm_provider(user, provider_id)


@router.post("/platform/llm/test-config")
async def test_llm_config(
    body: LlmProviderConfig,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_system_admin(user)
    return await service.test_llm_config(
        user,
        provider_id=body.id,
        api_key=body.api_key,
        base_url=body.base_url,
        models=body.models,
    )


@router.get("/platform/llm/status")
async def get_platform_llm_status(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_system_admin(user)
    return await service.get_platform_llm_status(user)


@router.put("/platform/llm/key/{provider_id}")
async def update_platform_llm_key(
    provider_id: str,
    key: str = Body(..., embed=True),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_system_admin(user)
    return service.update_platform_llm_key(user, provider_id, key)
