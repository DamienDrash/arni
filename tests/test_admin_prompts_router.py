import time

import pytest
from httpx import AsyncClient


async def _register_tenant(client: AsyncClient, suffix: str) -> str:
    unique = f"{suffix}-{int(time.time() * 1000)}"
    response = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Prompt Tenant {unique}",
            "tenant_slug": f"prompt-tenant-{unique}",
            "email": f"prompt-{unique}@test.example",
            "password": "Password123",
            "full_name": "Prompt Admin",
            "accept_tos": True,
            "accept_privacy": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_agent_template_endpoint_is_available_for_tenant_admin(client: AsyncClient) -> None:
    token = await _register_tenant(client, "template")
    response = await client.get(
        "/admin/prompts/agent/ops",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "ops"
    assert "content" in payload
