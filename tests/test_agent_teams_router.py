from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.core.db import SessionLocal
from app.core.models import AgentTeam


def _system_admin_headers() -> dict[str, str]:
    token = create_access_token(
        user_id=1,
        email="sysadmin@test.local",
        tenant_id=1,
        tenant_slug="system",
        role="system_admin",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def system_admin_client() -> AsyncClient:
    from app.edge.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=_system_admin_headers(),
    ) as client:
        yield client


def _cleanup_team(name: str) -> None:
    db = SessionLocal()
    try:
        db.query(AgentTeam).filter(AgentTeam.name == name).delete()
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_create_and_list_agent_teams(
    system_admin_client: AsyncClient,
) -> None:
    name = f"team_{int(time.time() * 1000)}"
    try:
        create_response = await system_admin_client.post(
            "/admin/agent-teams",
            json={
                "name": name,
                "display_name": "Support Team",
                "agent_ids": [],
            },
        )
        assert create_response.status_code == 201
        assert create_response.json()["name"] == name

        list_response = await system_admin_client.get("/admin/agent-teams")
        assert list_response.status_code == 200
        assert name in {item["name"] for item in list_response.json()}
    finally:
        _cleanup_team(name)


@pytest.mark.anyio
async def test_duplicate_and_state_update_use_repository_backed_paths(
    system_admin_client: AsyncClient,
) -> None:
    name = f"team_{int(time.time() * 1000)}"
    try:
        create_response = await system_admin_client.post(
            "/admin/agent-teams",
            json={
                "name": name,
                "display_name": "Operations Team",
                "agent_ids": [],
            },
        )
        assert create_response.status_code == 201

        duplicate_response = await system_admin_client.post(
            "/admin/agent-teams",
            json={
                "name": name,
                "display_name": "Operations Team",
                "agent_ids": [],
            },
        )
        assert duplicate_response.status_code == 409

        state_response = await system_admin_client.post(
            f"/admin/agent-teams/{name}/state",
            json={"state": "PAUSED"},
        )
        assert state_response.status_code == 200
        assert state_response.json()["new_state"] == "PAUSED"
    finally:
        _cleanup_team(name)
