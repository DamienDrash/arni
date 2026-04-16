from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.core.db import SessionLocal
from app.core.models import CampaignTemplate


def _tenant_admin_headers() -> dict[str, str]:
    token = create_access_token(
        user_id=2,
        email="tenantadmin@test.local",
        tenant_id=1,
        tenant_slug="default",
        role="tenant_admin",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def tenant_admin_client() -> AsyncClient:
    from app.edge.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=_tenant_admin_headers(),
    ) as client:
        yield client


def _cleanup_template(name: str) -> None:
    db = SessionLocal()
    try:
        db.query(CampaignTemplate).filter(
            CampaignTemplate.tenant_id == 1,
            CampaignTemplate.name.in_([name, f"{name} (Kopie)"]),
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_create_and_list_templates_returns_tenant_items(
    tenant_admin_client: AsyncClient,
) -> None:
    name = f"Template {int(time.time() * 1000)}"
    try:
        create_response = await tenant_admin_client.post(
            "/v2/admin/templates",
            json={
                "name": name,
                "type": "email",
                "body_template": "Hallo {{first_name}}",
                "is_default": True,
            },
        )
        assert create_response.status_code == 201
        assert create_response.json()["name"] == name

        list_response = await tenant_admin_client.get("/v2/admin/templates")
        assert list_response.status_code == 200
        names = {item["name"] for item in list_response.json()["items"]}
        assert name in names
    finally:
        _cleanup_template(name)


@pytest.mark.anyio
async def test_duplicate_and_defaults_by_type_follow_repository_backed_paths(
    tenant_admin_client: AsyncClient,
) -> None:
    name = f"Template {int(time.time() * 1000)}"
    try:
        create_response = await tenant_admin_client.post(
            "/v2/admin/templates",
            json={
                "name": name,
                "type": "telegram",
                "body_template": "Hey",
                "is_default": True,
            },
        )
        assert create_response.status_code == 201
        template_id = create_response.json()["id"]

        duplicate_response = await tenant_admin_client.post(f"/v2/admin/templates/{template_id}/duplicate")
        assert duplicate_response.status_code == 200
        assert duplicate_response.json()["name"] == f"{name} (Kopie)"

        defaults_response = await tenant_admin_client.get("/v2/admin/templates/defaults/by-type")
        assert defaults_response.status_code == 200
        assert defaults_response.json()["telegram"]["name"] == name
    finally:
        _cleanup_template(name)
