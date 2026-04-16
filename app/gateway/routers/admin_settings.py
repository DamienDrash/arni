from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, get_current_user
from app.gateway.admin_shared import require_system_admin, require_tenant_admin_or_system
from app.gateway.services.admin_settings_service import service

router = APIRouter(
    prefix="/admin",
    tags=["admin-settings"],
    dependencies=[Depends(get_current_user)],
)


class PromptConfigUpdate(BaseModel):
    studio_name: str | None = None
    studio_short_name: str | None = None
    studio_business_type: str | None = None
    studio_owner_name: str | None = None
    studio_description: str | None = None
    agent_display_name: str | None = None
    persona_bio_text: str | None = None
    studio_locale: str | None = None
    studio_timezone: str | None = None
    studio_address: str | None = None
    studio_phone: str | None = None
    studio_email: str | None = None
    studio_website: str | None = None
    studio_emergency_number: str | None = None
    sales_prices_text: str | None = None
    sales_retention_rules: str | None = None
    sales_complaint_protocol: str | None = None
    medic_disclaimer_text: str | None = None
    health_advice_scope: str | None = None
    booking_instructions: str | None = None
    booking_cancellation_policy: str | None = None
    escalation_triggers: str | None = None
    escalation_contact: str | None = None


class SmtpTestRequest(BaseModel):
    host: str
    port: int
    user: str
    pass_: str = Field(..., alias="pass")
    from_name: str
    from_addr: str
    recipient: str


@router.get("/prompt-config")
async def get_prompt_config(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_prompt_config(user)


@router.put("/prompt-config")
async def update_prompt_config(
    body: PromptConfigUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    return service.update_prompt_config(user, payload)


@router.get("/prompt-config/schema")
async def get_prompt_config_schema(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_prompt_config_schema()


@router.post("/platform/email/test")
async def test_platform_email(
    body: SmtpTestRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_system_admin(user)
    return await service.test_platform_email(user, body)


@router.get("/platform/whatsapp/qr")
async def get_whatsapp_qr(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_whatsapp_qr(user)


@router.get("/platform/whatsapp/qr-image")
async def get_whatsapp_qr_image(user: AuthContext = Depends(get_current_user)) -> Response:
    require_tenant_admin_or_system(user)
    return await service.get_whatsapp_qr_image(user)


@router.post("/platform/whatsapp/reset")
async def reset_whatsapp_session(user: AuthContext = Depends(get_current_user)) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    return await service.reset_whatsapp_session(user)
