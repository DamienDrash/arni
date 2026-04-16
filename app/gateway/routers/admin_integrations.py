from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user
from app.gateway.admin_shared import require_system_admin, require_tenant_admin_or_system
from app.gateway.services.admin_integrations_service import service

router = APIRouter(
    prefix="/admin",
    tags=["admin-integrations"],
    dependencies=[Depends(get_current_user)],
)


class TelegramConfigUpdate(BaseModel):
    bot_token: str | None = None
    admin_chat_id: str | None = None
    webhook_secret: str | None = None


class WhatsAppConfigUpdate(BaseModel):
    mode: str | None = None
    meta_verify_token: str | None = None
    meta_access_token: str | None = None
    meta_app_secret: str | None = None
    meta_phone_number_id: str | None = None
    bridge_auth_dir: str | None = None


class MagiclineConfigUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    tenant_id: str | None = None
    auto_sync_enabled: str | None = None
    auto_sync_cron: str | None = None


class SmtpConfigUpdate(BaseModel):
    host: str | None = None
    port: str | None = None
    username: str | None = None
    password: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    use_starttls: str | None = None
    verification_subject: str | None = None


class IntegrationsConfigUpdate(BaseModel):
    telegram: TelegramConfigUpdate | None = None
    whatsapp: WhatsAppConfigUpdate | None = None
    magicline: MagiclineConfigUpdate | None = None
    smtp: SmtpConfigUpdate | None = None
    email_channel: dict[str, str | None] | None = None
    sms_channel: dict[str, str | None] | None = None
    voice_channel: dict[str, str | None] | None = None


class IntegrationTestRequest(BaseModel):
    config: dict[str, Any] | None = None


class ConnectorCreateRequest(BaseModel):
    id: str
    name: str
    category: str
    description: str = ""
    icon: str = "plug"
    fields: list[dict[str, Any]] = []
    setup_doc: str = ""


class ConnectorUpdateRequest(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    icon: str | None = None
    fields: list[dict[str, Any]] | None = None
    setup_doc: str | None = None


@router.get("/integrations/config")
async def get_integrations_config(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_integrations_config(user)


@router.put("/integrations/config")
async def update_integrations_config(
    body: IntegrationsConfigUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    return service.update_integrations_config(user, body)


@router.delete("/integrations/{provider}")
async def delete_integration_config(
    provider: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.delete_integration_config(user, provider)


@router.post("/integrations/test/{provider}")
async def test_integration_connector(
    provider: str,
    body: IntegrationTestRequest = Body(default=IntegrationTestRequest()),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return await service.test_integration_connector(user, provider, body.config)


@router.get("/integrations/health")
async def integrations_health(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return await service.integrations_health(user)


@router.get("/integrations/catalog")
async def get_integrations_catalog(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return service.get_connector_catalog(user)


@router.get("/integrations/connectors/{connector_id}/config")
async def get_connector_config(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_connector_config(user, connector_id)


@router.put("/integrations/connectors/{connector_id}/config")
async def update_connector_config(
    connector_id: str,
    body: dict[str, Any] = Body(default={}),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    return service.update_connector_config(user, connector_id, body)


@router.delete("/integrations/connectors/{connector_id}/config")
async def reset_connector_config(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    return service.reset_connector_config(user, connector_id)


@router.post("/integrations/connectors/{connector_id}/test")
async def test_connector_config(
    connector_id: str,
    body: IntegrationTestRequest = Body(default=IntegrationTestRequest()),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return await service.test_integration_connector(user, connector_id, body.config)


@router.get("/integrations/connectors/{connector_id}/docs")
async def get_connector_docs(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_connector_docs(connector_id)


@router.get("/integrations/docs/all")
async def get_all_connector_docs(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return service.get_all_connector_docs()


@router.get("/integrations/connectors/{connector_id}/webhook-info")
async def get_connector_webhook_info(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_connector_webhook_info(user, connector_id)


@router.get("/integrations/system/connectors")
async def system_list_connectors(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_system_admin(user)
    return service.system_list_connectors(user)


@router.post("/integrations/system/connectors")
async def system_create_connector(
    body: ConnectorCreateRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_system_admin(user)
    return service.system_create_connector(user, body)


@router.put("/integrations/system/connectors/{connector_id}")
async def system_update_connector(
    connector_id: str,
    body: ConnectorUpdateRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_system_admin(user)
    return service.system_update_connector(user, connector_id, body)


@router.delete("/integrations/system/connectors/{connector_id}")
async def system_delete_connector(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_system_admin(user)
    return service.system_delete_connector(user, connector_id)


@router.get("/integrations/system/usage-overview")
async def system_usage_overview(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_system_admin(user)
    return service.system_usage_overview(user)
