import time

import pytest
from httpx import AsyncClient


async def _register_tenant(client: AsyncClient, suffix: str) -> str:
    unique = f"{suffix}-{int(time.time() * 1000)}"
    response = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Knowledge Tenant {unique}",
            "tenant_slug": f"knowledge-tenant-{unique}",
            "email": f"knowledge-{unique}@test.example",
            "password": "Password123",
            "full_name": "Knowledge Admin",
            "accept_tos": True,
            "accept_privacy": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_knowledge_and_member_memory_endpoints_are_available_for_tenant_admin(client: AsyncClient) -> None:
    token = await _register_tenant(client, "availability")
    headers = {"Authorization": f"Bearer {token}"}

    knowledge_response = await client.get("/admin/knowledge", headers=headers)
    memory_response = await client.get("/admin/member-memory", headers=headers)

    assert knowledge_response.status_code == 200
    assert isinstance(knowledge_response.json(), list)
    assert memory_response.status_code == 200
    assert isinstance(memory_response.json(), list)
