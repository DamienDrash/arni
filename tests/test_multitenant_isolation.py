"""Multi-Tenant Isolation Tests (S7).

Verifies that tenant data never leaks across tenant boundaries.
Each test registers two independent tenants (A & B) and asserts that
actions taken on Tenant A are not visible to Tenant B and vice versa.
"""

import time

import pytest
from httpx import AsyncClient


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _register_tenant(client: AsyncClient, suffix: str) -> tuple[str, int]:
    """Register a new tenant, return (access_token, tenant_id)."""
    unique = f"{suffix}-{int(time.time() * 1000)}"
    resp = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Test Tenant {unique}",
            "tenant_slug": f"test-tenant-{unique}",
            "email": f"admin-{unique}@test.example",
            "password": "password123",
            "full_name": "Test Admin",
        },
    )
    assert resp.status_code == 200, f"Register failed: {resp.text}"
    data = resp.json()
    return data["access_token"], data["user"]["tenant_id"]


# ── Tenant Preferences Isolation ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_tenant_preferences_are_isolated(client: AsyncClient) -> None:
    """Tenant A's preferences must not be visible to Tenant B."""
    token_a, _ = await _register_tenant(client, "pref-a")
    token_b, _ = await _register_tenant(client, "pref-b")

    # Tenant A sets a unique display name and branding color
    put_a = await client.put(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"tenant_display_name": "Studio Alpha", "tenant_primary_color": "#AABBCC"},
    )
    assert put_a.status_code == 200

    # Tenant B reads its own preferences — must not see Studio Alpha
    get_b = await client.get(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_b.status_code == 200
    b_prefs = get_b.json()
    assert b_prefs.get("tenant_display_name") != "Studio Alpha"
    assert b_prefs.get("tenant_primary_color") != "#AABBCC"

    # Tenant A reads its own preferences — must see Studio Alpha
    get_a = await client.get(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert get_a.status_code == 200
    a_prefs = get_a.json()
    assert a_prefs.get("tenant_display_name") == "Studio Alpha"
    assert a_prefs.get("tenant_primary_color") == "#AABBCC"


@pytest.mark.anyio
async def test_tenant_user_cannot_write_tenant_preferences(client: AsyncClient) -> None:
    """A tenant_user must be blocked from writing tenant preferences (needs tenant_admin)."""
    admin_login = await client.post(
        "/auth/login",
        json={"email": "admin@arni.local", "password": "password123"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    token_a, tid_a = await _register_tenant(client, "prefs-write-guard")

    unique = int(time.time() * 1000)
    user_resp = await client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": f"prefs-user-{unique}@test.example",
            "password": "password123",
            "role": "tenant_user",
            "tenant_id": tid_a,
        },
    )
    assert user_resp.status_code == 200

    user_login = await client.post(
        "/auth/login",
        json={"email": f"prefs-user-{unique}@test.example", "password": "password123"},
    )
    assert user_login.status_code == 200
    user_token = user_login.json()["access_token"]

    put_resp = await client.put(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"tenant_display_name": "ShouldBeBlocked"},
    )
    assert put_resp.status_code == 403

    get_resp = await client.get(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert get_resp.status_code == 403


# ── Billing Isolation ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_billing_subscription_is_per_tenant(client: AsyncClient) -> None:
    """Each tenant sees only its own subscription/plan data."""
    token_a, tid_a = await _register_tenant(client, "billing-a")
    token_b, tid_b = await _register_tenant(client, "billing-b")

    assert tid_a != tid_b

    sub_a = await client.get(
        "/admin/billing/subscription",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert sub_a.status_code == 200
    data_a = sub_a.json()

    sub_b = await client.get(
        "/admin/billing/subscription",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert sub_b.status_code == 200
    data_b = sub_b.json()

    # Both tenants should have a subscription (auto-seeded Starter on registration)
    assert data_a.get("plan") is not None
    assert data_b.get("plan") is not None

    # Subscription records must not reference the other tenant's ID
    if "tenant_id" in data_a:
        assert data_a["tenant_id"] == tid_a
    if "tenant_id" in data_b:
        assert data_b["tenant_id"] == tid_b


@pytest.mark.anyio
async def test_billing_usage_is_per_tenant(client: AsyncClient) -> None:
    """Usage counters are scoped per tenant and start at zero."""
    token_a, _ = await _register_tenant(client, "usage-a")
    token_b, _ = await _register_tenant(client, "usage-b")

    usage_a = await client.get(
        "/admin/billing/usage",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert usage_a.status_code == 200
    usage_b = await client.get(
        "/admin/billing/usage",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert usage_b.status_code == 200

    # Fresh tenants must have zero usage
    a = usage_a.json()
    b = usage_b.json()
    assert a.get("messages_inbound", 0) == 0
    assert b.get("messages_inbound", 0) == 0


# ── Role-Based Access Control ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_tenant_user_cannot_access_admin_endpoints(client: AsyncClient) -> None:
    """A tenant_user must not be able to access admin-only endpoints."""
    admin_login = await client.post(
        "/auth/login",
        json={"email": "admin@arni.local", "password": "password123"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    token_a, tid_a = await _register_tenant(client, "rbac-a")

    # Create a tenant_user under Tenant A
    unique = int(time.time() * 1000)
    user_resp = await client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": f"user-rbac-{unique}@test.example",
            "password": "password123",
            "role": "tenant_user",
            "tenant_id": tid_a,
        },
    )
    assert user_resp.status_code == 200

    user_login = await client.post(
        "/auth/login",
        json={
            "email": f"user-rbac-{unique}@test.example",
            "password": "password123",
        },
    )
    assert user_login.status_code == 200
    user_token = user_login.json()["access_token"]

    # tenant_user must not access settings
    settings_resp = await client.get(
        "/admin/settings",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert settings_resp.status_code == 403

    # tenant_user must not access tenant preferences
    prefs_resp = await client.get(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert prefs_resp.status_code == 403

    # tenant_user must not access billing
    billing_resp = await client.get(
        "/admin/billing/subscription",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert billing_resp.status_code == 403


@pytest.mark.anyio
async def test_tenant_admin_can_access_own_data_but_not_global_endpoints(client: AsyncClient) -> None:
    """tenant_admin can access per-tenant endpoints; global system_admin endpoints remain blocked."""
    token_a, _ = await _register_tenant(client, "sysadmin-guard")

    # tenant_admin CAN read their own settings
    settings_resp = await client.get("/admin/settings", headers={"Authorization": f"Bearer {token_a}"})
    assert settings_resp.status_code == 200

    # tenant_admin CAN read their own member stats
    member_stats_resp = await client.get("/admin/members/stats", headers={"Authorization": f"Bearer {token_a}"})
    assert member_stats_resp.status_code == 200

    # tenant_admin CAN access their own knowledge base
    knowledge_resp = await client.get("/admin/knowledge", headers={"Authorization": f"Bearer {token_a}"})
    assert knowledge_resp.status_code == 200

    # tenant_admin CAN access their own member memory
    memory_resp = await client.get("/admin/member-memory", headers={"Authorization": f"Bearer {token_a}"})
    assert memory_resp.status_code == 200

    # Global dashboard stats (system_admin only) — must be blocked
    stats_resp = await client.get("/admin/stats", headers={"Authorization": f"Bearer {token_a}"})
    assert stats_resp.status_code == 403


# ── Prompt Template Isolation ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_prompt_variable_settings_are_isolated(client: AsyncClient) -> None:
    """Prompt-setting writes by Tenant A are not visible to Tenant B."""
    token_a, _ = await _register_tenant(client, "prompt-a")
    token_b, _ = await _register_tenant(client, "prompt-b")

    # Tenant A writes a unique agent display name via settings
    put_a = await client.put(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"tenant_app_title": "AlphaAgent Studio"},
    )
    assert put_a.status_code == 200

    # Tenant B must not see AlphaAgent Studio
    get_b = await client.get(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_b.status_code == 200
    assert get_b.json().get("tenant_app_title") != "AlphaAgent Studio"


# ── Cross-Tenant Token Reuse ──────────────────────────────────────────────────

@pytest.mark.anyio
async def test_jwt_tenant_id_cannot_be_substituted(client: AsyncClient) -> None:
    """Tenant A's JWT must not grant access to Tenant B's admin scope.

    The backend derives tenant context exclusively from the token's tenant_id
    claim, so there is no request parameter to spoof.  This test verifies that
    Tenant A's token, when used to write preferences, only affects Tenant A's
    data and that Tenant B's data remains unchanged.
    """
    token_a, _ = await _register_tenant(client, "jwt-a")
    token_b, _ = await _register_tenant(client, "jwt-b")

    # Set a sentinel on Tenant B first
    await client.put(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"tenant_display_name": "Tenant B Original"},
    )

    # Tenant A writes its own preferences — should only affect A
    await client.put(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"tenant_display_name": "Tenant A Overwrite Attempt"},
    )

    # Tenant B's display name must still be its own
    get_b = await client.get(
        "/admin/tenant-preferences",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_b.status_code == 200
    assert get_b.json().get("tenant_display_name") == "Tenant B Original"
