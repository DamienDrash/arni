import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.gateway.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    login = await client.post("/auth/login", json={"email": "admin@ariia.local", "password": "password123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_knowledge_save_requires_reason(client: AsyncClient) -> None:
    headers = await _admin_headers(client)
    filename = f"governance-{int(time.time() * 1000)}.md"
    payload = {"content": "# Governance", "base_mtime": None}

    missing_reason = await client.post(f"/admin/knowledge/file/{filename}", json=payload, headers=headers)
    assert missing_reason.status_code == 422

    ok = await client.post(
        f"/admin/knowledge/file/{filename}",
        json={**payload, "reason": "Dokument für Governance-Test aktualisiert"},
        headers=headers,
    )
    assert ok.status_code == 200


@pytest.mark.anyio
async def test_member_memory_save_requires_reason(client: AsyncClient) -> None:
    headers = await _admin_headers(client)
    filename = f"member-{int(time.time() * 1000)}.md"
    payload = {"content": "# Memory", "base_mtime": None}

    missing_reason = await client.post(f"/admin/member-memory/file/{filename}", json=payload, headers=headers)
    assert missing_reason.status_code == 422

    ok = await client.post(
        f"/admin/member-memory/file/{filename}",
        json={**payload, "reason": "Member-Kontext manuell nachgeführt"},
        headers=headers,
    )
    assert ok.status_code == 200


@pytest.mark.anyio
async def test_prompt_saves_require_reason(client: AsyncClient) -> None:
    headers = await _admin_headers(client)
    ops_get = await client.get("/admin/prompts/ops-system", headers=headers)
    assert ops_get.status_code == 200
    ops = ops_get.json()

    ops_missing = await client.post(
        "/admin/prompts/ops-system",
        json={"content": ops["content"], "base_mtime": ops.get("mtime")},
        headers=headers,
    )
    assert ops_missing.status_code == 422

    ops_ok = await client.post(
        "/admin/prompts/ops-system",
        json={
            "content": ops["content"],
            "base_mtime": ops.get("mtime"),
            "reason": "Prompt-Governance Validierung",
        },
        headers=headers,
    )
    assert ops_ok.status_code == 200

    mem_get = await client.get("/admin/prompts/member-memory-instructions", headers=headers)
    assert mem_get.status_code == 200
    mem = mem_get.json()

    mem_missing = await client.post(
        "/admin/prompts/member-memory-instructions",
        json={"content": mem["content"], "base_mtime": mem.get("mtime")},
        headers=headers,
    )
    assert mem_missing.status_code == 422

    mem_ok = await client.post(
        "/admin/prompts/member-memory-instructions",
        json={
            "content": mem["content"],
            "base_mtime": mem.get("mtime"),
            "reason": "Extraktionsanweisung Governance-Check",
        },
        headers=headers,
    )
    assert mem_ok.status_code == 200
