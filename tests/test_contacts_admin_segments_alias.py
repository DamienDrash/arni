import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_admin_segments_alias_returns_segment_list(client: AsyncClient) -> None:
    login = await client.post(
        "/auth/login",
        json={"email": "admin@ariia.local", "password": "Password123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = await client.get(
        "/v2/admin/contacts/segments",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "total" in payload
