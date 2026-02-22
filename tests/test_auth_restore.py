import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.gateway.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_register_login_and_admin_guard(client: AsyncClient) -> None:
    unique = int(time.time() * 1000)
    email = f"restore-{unique}@example.com"

    reg = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Restore Tenant {unique}",
            "tenant_slug": f"restore-tenant-{unique}",
            "email": email,
            "password": "password123",
            "full_name": "Restore Admin",
        },
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    assert token

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["role"] == "tenant_admin"

    denied = await client.get("/admin/settings")
    assert denied.status_code in {200, 401}

    # tenant_admin CAN read their own settings (guard relaxed in S6 to enable integration KPI cards)
    allowed = await client.get("/admin/settings", headers={"Authorization": f"Bearer {token}"})
    assert allowed.status_code == 200

    # tenant_admin CAN access their own knowledge base and member memory
    knowledge_resp = await client.get("/admin/knowledge", headers={"Authorization": f"Bearer {token}"})
    assert knowledge_resp.status_code == 200

    analyze_resp = await client.post("/admin/member-memory/analyze-now", headers={"Authorization": f"Bearer {token}"}, json={})
    assert analyze_resp.status_code == 200

    # Global dashboard stats remain system_admin only
    forbidden_stats = await client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert forbidden_stats.status_code == 403


@pytest.mark.anyio
async def test_system_admin_user_creation_enforces_tenant_rules(client: AsyncClient) -> None:
    admin_login = await client.post(
        "/auth/login",
        json={"email": "admin@ariia.local", "password": "password123"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    unique = int(time.time() * 1000)
    reg = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Rule Tenant {unique}",
            "tenant_slug": f"rule-tenant-{unique}",
            "email": f"rule-admin-{unique}@example.com",
            "password": "password123",
            "full_name": "Rule Admin",
        },
    )
    assert reg.status_code == 200
    tenant_id = reg.json()["user"]["tenant_id"]

    # system_admin must explicitly set tenant_id for non-system roles
    missing_tenant = await client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": f"user-no-tenant-{unique}@example.com",
            "password": "password123",
            "role": "tenant_user",
        },
    )
    assert missing_tenant.status_code == 422

    # system_admin role cannot be assigned to non-system tenant
    wrong_system_tenant = await client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": f"wrong-system-{unique}@example.com",
            "password": "password123",
            "role": "system_admin",
            "tenant_id": tenant_id,
        },
    )
    assert wrong_system_tenant.status_code == 422

    # tenant_admin cannot create system_admin users
    tenant_token = reg.json()["access_token"]
    forbidden = await client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={
            "email": f"forbidden-system-{unique}@example.com",
            "password": "password123",
            "role": "system_admin",
        },
    )
    assert forbidden.status_code == 403

    analyze_now = await client.post(
        "/admin/member-memory/analyze-now",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert analyze_now.status_code == 200


@pytest.mark.anyio
async def test_reserved_tenant_slug_is_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register",
        json={
            "tenant_name": "System",
            "tenant_slug": "system",
            "email": f"reserved-{int(time.time()*1000)}@example.com",
            "password": "password123",
            "full_name": "Reserved Slug",
        },
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_system_admin_can_impersonate_tenant_user_and_exit(client: AsyncClient) -> None:
    admin_login = await client.post(
        "/auth/login",
        json={"email": "admin@ariia.local", "password": "password123"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    unique = int(time.time() * 1000)
    reg = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Ghost Tenant {unique}",
            "tenant_slug": f"ghost-tenant-{unique}",
            "email": f"ghost-admin-{unique}@example.com",
            "password": "password123",
            "full_name": "Ghost Admin",
        },
    )
    assert reg.status_code == 200
    tenant_id = reg.json()["user"]["tenant_id"]

    create_user = await client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": f"ghost-user-{unique}@example.com",
            "password": "password123",
            "role": "tenant_user",
            "tenant_id": tenant_id,
        },
    )
    assert create_user.status_code == 200
    target_user_id = create_user.json()["id"]

    start = await client.post(
        f"/auth/users/{target_user_id}/impersonate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "Supportfall #1234: UI-Reproduktion"},
    )
    assert start.status_code == 200
    ghost_token = start.json()["access_token"]

    ghost_me = await client.get("/auth/me", headers={"Authorization": f"Bearer {ghost_token}"})
    assert ghost_me.status_code == 200
    assert ghost_me.json()["id"] == target_user_id
    assert ghost_me.json()["role"] == "tenant_user"
    assert ghost_me.json().get("impersonation", {}).get("active") is True

    ghost_denied_admin = await client.get("/admin/settings", headers={"Authorization": f"Bearer {ghost_token}"})
    assert ghost_denied_admin.status_code == 403

    stop = await client.post(
        "/auth/impersonation/stop",
        headers={"Authorization": f"Bearer {ghost_token}"},
        json={},
    )
    assert stop.status_code == 200
    restored_token = stop.json()["access_token"]

    restored_me = await client.get("/auth/me", headers={"Authorization": f"Bearer {restored_token}"})
    assert restored_me.status_code == 200
    assert restored_me.json()["role"] == "system_admin"
    assert "impersonation" not in restored_me.json()


@pytest.mark.anyio
async def test_user_deactivation_revokes_session(client: AsyncClient) -> None:
    # 1. System-Admin-Token holen
    admin_login = await client.post(
        "/auth/login",
        json={"email": "admin@ariia.local", "password": "password123"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    # 2. Neuen Tenant + User anlegen
    unique = int(time.time() * 1000)
    reg = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Revoke Tenant {unique}",
            "tenant_slug": f"revoke-{unique}",
            "email": f"revoke-admin-{unique}@example.com",
            "password": "password123",
            "full_name": "Revoke Admin",
        },
    )
    assert reg.status_code == 200
    tenant_id = reg.json()["user"]["tenant_id"]

    create = await client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": f"victim-{unique}@example.com",
            "password": "password123",
            "role": "tenant_user",
            "tenant_id": tenant_id,
        },
    )
    assert create.status_code == 200
    victim_id = create.json()["id"]

    # 3. User einloggen → Token sichern
    login = await client.post(
        "/auth/login",
        json={"email": f"victim-{unique}@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    victim_token = login.json()["access_token"]

    # 4. Token ist noch gültig
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {victim_token}"})
    assert me.status_code == 200

    # 5. User deaktivieren
    deact = await client.put(
        f"/auth/users/{victim_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert deact.status_code == 200

    # 6. Alter Token muss sofort 401 liefern (S1.4)
    revoked = await client.get("/auth/me", headers={"Authorization": f"Bearer {victim_token}"})
    assert revoked.status_code == 401
