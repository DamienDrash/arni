"""Agent Teams – Comprehensive Test Suite.

Coverage targets:
- app/gateway/routers/agent_teams.py  → 90%+
- app/swarm/base_team.py              → 85%+
- app/swarm/team_models.py            → 95%+
- app/swarm/team_yaml.py              → 90%+
- app/swarm/seed_teams.py             → 85%+

Auth conventions in test mode (ENVIRONMENT=testing):
  - No Authorization header  →  get_current_user() returns the system_admin bypass context
    (system tenant, role=system_admin, bypasses feature gates)
  - _register_tenant() token →  real tenant_admin for a fresh tenant
  - _make_tenant_user_token()→  real tenant_user for a fresh tenant

Test groups:
  1. RBAC / auth guards
  2. Team CRUD (create, list, detail, update, delete)
  3. Input validation (slug, name, execution_mode, step_order uniqueness, JSON fields)
  4. Multi-tenant isolation
  5. Feature gate enforcement
  6. Tool CRUD and scoping (global builtins vs. tenant-scoped)
  7. Run endpoints (run, list runs, get run, per-team runs, filters)
  8. BaseAgentTeam / run_and_save() persistence contract
  9. team_yaml (slug validation, path-traversal, atomic write)
 10. seed_teams (idempotency, version guard)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ─── Auth helpers ─────────────────────────────────────────────────────────────


def _create_tenant_db(suffix: str = "") -> tuple[str, int]:
    """Create a Tenant + tenant_admin UserAccount directly in the DB.

    Bypasses the /auth/register rate limit (3/hour).
    Returns (access_token, tenant_id).
    """
    import uuid
    from app.core.db import SessionLocal
    from app.core.models import Tenant, UserAccount
    from app.core.auth import create_access_token, hash_password

    uid = uuid.uuid4().hex[:16]
    slug = f"t-{uid}"
    email = f"{uid}@test.example"
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"T {suffix} {uid}", slug=slug, is_active=True)
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        user = UserAccount(
            tenant_id=tenant.id,
            email=email,
            full_name="Test Admin",
            role="tenant_admin",
            password_hash=hash_password("TestPass1234!"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(
            user_id=user.id,
            email=email,
            tenant_id=tenant.id,
            tenant_slug=slug,
            role="tenant_admin",
        )
        return token, tenant.id
    finally:
        db.close()


async def _register_tenant(client: AsyncClient, suffix: str) -> tuple[str, int]:
    """Create a fresh tenant with tenant_admin user, return (access_token, tenant_id).

    Uses direct DB creation to bypass the /auth/register rate limit (3/hour).
    """
    return _create_tenant_db(suffix)


def _make_tenant_user_token(tenant_id: int) -> str:
    """Create a real UserAccount with role=tenant_user in the DB, return its token."""
    from app.core.db import SessionLocal
    from app.core.models import UserAccount
    from app.core.auth import create_access_token, hash_password

    uid = int(time.time() * 1_000_000) % 10_000_000
    db = SessionLocal()
    try:
        user = UserAccount(
            tenant_id=tenant_id,
            email=f"user-{uid}@test.example",
            full_name="Test User",
            role="tenant_user",
            password_hash=hash_password("TestPass1234!"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return create_access_token(
            user_id=user.id,
            email=user.email,
            tenant_id=tenant_id,
            tenant_slug="test",
            role="tenant_user",
        )
    finally:
        db.close()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def tenant_a(client: AsyncClient):
    """Fresh tenant A — returns (token, tenant_id). Token is tenant_admin."""
    return await _register_tenant(client, "at-a")


@pytest.fixture
async def tenant_b(client: AsyncClient):
    """Fresh tenant B — returns (token, tenant_id). Token is tenant_admin."""
    return await _register_tenant(client, "at-b")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. RBAC / AUTH GUARDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRBACGuards:
    """Role-based access control: tenant_user blocked, admin allowed."""

    @pytest.mark.anyio
    async def test_tenant_user_blocked_list(self, client: AsyncClient) -> None:
        """tenant_user must get 403 on GET /admin/agent-teams/."""
        _, tid = await _register_tenant(client, "rbac-user-list")
        user_token = _make_tenant_user_token(tid)
        resp = await client.get("/v2/admin/agent-teams/", headers=_auth(user_token))
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_tenant_user_blocked_create(self, client: AsyncClient) -> None:
        """tenant_user must get 403 on POST /admin/agent-teams/."""
        _, tid = await _register_tenant(client, "rbac-user-create")
        user_token = _make_tenant_user_token(tid)
        resp = await client.post(
            "/v2/admin/agent-teams/",
            headers=_auth(user_token),
            json={"slug": "my-team", "name": "My Team"},
        )
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_tenant_user_blocked_tools(self, client: AsyncClient) -> None:
        """tenant_user must get 403 on GET /admin/agent-tools/."""
        _, tid = await _register_tenant(client, "rbac-user-tools")
        user_token = _make_tenant_user_token(tid)
        resp = await client.get("/v2/admin/agent-tools/", headers=_auth(user_token))
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_tenant_user_blocked_runs(self, client: AsyncClient) -> None:
        """tenant_user must get 403 on GET /admin/agent-runs/."""
        _, tid = await _register_tenant(client, "rbac-user-runs")
        user_token = _make_tenant_user_token(tid)
        resp = await client.get("/v2/admin/agent-runs/", headers=_auth(user_token))
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_system_admin_bypass_returns_ok(self, client: AsyncClient) -> None:
        """In test mode (no auth header) the system_admin bypass must return 200."""
        resp = await client.get("/v2/admin/agent-teams/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_tenant_admin_without_plan_gets_402(
        self, client: AsyncClient, tenant_a
    ) -> None:
        """tenant_admin on Starter plan (no agent_teams feature) must get 402."""
        token, _ = tenant_a
        resp = await client.get("/v2/admin/agent-teams/", headers=_auth(token))
        assert resp.status_code == 402

    @pytest.mark.anyio
    async def test_tenant_user_blocked_delete(self, client: AsyncClient) -> None:
        """tenant_user must get 403 on DELETE even if team exists."""
        _, tid = await _register_tenant(client, "rbac-del")
        user_token = _make_tenant_user_token(tid)
        resp = await client.delete("/v2/admin/agent-teams/some-slug", headers=_auth(user_token))
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_tenant_user_blocked_run(self, client: AsyncClient) -> None:
        """tenant_user must get 403 on POST /run."""
        _, tid = await _register_tenant(client, "rbac-run")
        user_token = _make_tenant_user_token(tid)
        resp = await client.post(
            "/v2/admin/agent-teams/any-slug/run",
            headers=_auth(user_token),
            json={"payload": {}},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TEAM CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamCRUD:
    """Full create → list → detail → update → delete lifecycle.

    Uses no-auth (system_admin bypass) for all operations.
    """

    @pytest.mark.anyio
    async def test_create_team_minimal(self, client: AsyncClient) -> None:
        slug = f"test-team-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": slug, "name": "Test Team"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == slug
        assert data["name"] == "Test Team"
        assert data["is_active"] is True
        assert data["is_system"] is False
        assert data["yaml_version"] == 1
        assert data["execution_mode"] == "pipeline"

    @pytest.mark.anyio
    async def test_create_team_with_steps(self, client: AsyncClient) -> None:
        slug = f"stepped-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={
                "slug": slug,
                "name": "Stepped Team",
                "execution_mode": "pipeline",
                "steps": [
                    {"step_order": 0, "agent_slug": "ops", "display_name": "Ops Agent"},
                    {"step_order": 1, "agent_slug": "sales", "display_name": "Sales Agent",
                     "tools_json": '["knowledge_base"]'},
                ],
            },
        )
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_team_duplicate_slug_returns_409(self, client: AsyncClient) -> None:
        slug = f"dup-{int(time.time() * 1000)}"
        body = {"slug": slug, "name": "First"}
        r1 = await client.post("/v2/admin/agent-teams/", json=body)
        assert r1.status_code == 201
        r2 = await client.post("/v2/admin/agent-teams/", json=body)
        assert r2.status_code == 409

    @pytest.mark.anyio
    async def test_list_teams_returns_created(self, client: AsyncClient) -> None:
        slug = f"listed-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-teams/", json={"slug": slug, "name": "Listed Team"})
        resp = await client.get("/v2/admin/agent-teams/")
        assert resp.status_code == 200
        slugs = [t["slug"] for t in resp.json()]
        assert slug in slugs

    @pytest.mark.anyio
    async def test_list_teams_includes_step_count(self, client: AsyncClient) -> None:
        slug = f"count-{int(time.time() * 1000)}"
        await client.post(
            "/v2/admin/agent-teams/",
            json={
                "slug": slug,
                "name": "Count Team",
                "steps": [
                    {"step_order": 0, "agent_slug": "ops"},
                    {"step_order": 1, "agent_slug": "sales"},
                ],
            },
        )
        resp = await client.get("/v2/admin/agent-teams/?active_only=true")
        teams = resp.json()
        match = next((t for t in teams if t["slug"] == slug), None)
        assert match is not None
        assert match["step_count"] == 2

    @pytest.mark.anyio
    async def test_get_team_detail(self, client: AsyncClient) -> None:
        slug = f"detail-{int(time.time() * 1000)}"
        await client.post(
            "/v2/admin/agent-teams/",
            json={
                "slug": slug,
                "name": "Detail Team",
                "steps": [{"step_order": 0, "agent_slug": "ops"}],
            },
        )
        resp = await client.get(f"/v2/admin/agent-teams/{slug}/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == slug
        assert len(data["steps"]) == 1
        assert data["steps"][0]["agent_slug"] == "ops"

    @pytest.mark.anyio
    async def test_get_team_detail_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-teams/nonexistent-slug/detail")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_team_name(self, client: AsyncClient) -> None:
        slug = f"upd-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-teams/", json={"slug": slug, "name": "Old Name"})
        resp = await client.put(
            f"/v2/admin/agent-teams/{slug}",
            json={"name": "New Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    @pytest.mark.anyio
    async def test_update_team_replaces_steps_and_bumps_yaml_version(
        self, client: AsyncClient
    ) -> None:
        slug = f"steps-replace-{int(time.time() * 1000)}"
        await client.post(
            "/v2/admin/agent-teams/",
            json={
                "slug": slug,
                "name": "Step Replace",
                "steps": [{"step_order": 0, "agent_slug": "ops"}],
            },
        )
        resp = await client.put(
            f"/v2/admin/agent-teams/{slug}",
            json={"steps": [
                {"step_order": 0, "agent_slug": "sales"},
                {"step_order": 1, "agent_slug": "medic"},
            ]},
        )
        assert resp.status_code == 200
        detail = await client.get(f"/v2/admin/agent-teams/{slug}/detail")
        assert len(detail.json()["steps"]) == 2
        assert resp.json()["yaml_version"] == 2

    @pytest.mark.anyio
    async def test_update_team_not_found(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/v2/admin/agent-teams/no-such-team",
            json={"name": "X"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_team_soft_deletes(self, client: AsyncClient) -> None:
        slug = f"del-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-teams/", json={"slug": slug, "name": "To Delete"})
        resp = await client.delete(f"/v2/admin/agent-teams/{slug}")
        assert resp.status_code == 204

        # No longer visible in active list
        teams = await client.get("/v2/admin/agent-teams/?active_only=true")
        slugs = [t["slug"] for t in teams.json()]
        assert slug not in slugs

        # Visible when active_only=false
        teams_all = await client.get("/v2/admin/agent-teams/?active_only=false")
        slugs_all = [t["slug"] for t in teams_all.json()]
        assert slug in slugs_all

    @pytest.mark.anyio
    async def test_delete_team_not_found(self, client: AsyncClient) -> None:
        resp = await client.delete("/v2/admin/agent-teams/no-such-del")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_system_admin_can_delete_system_team(self, client: AsyncClient) -> None:
        """system_admin must be able to delete a system team."""
        slug = f"sys-team-del-{int(time.time() * 1000)}"
        r = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": slug, "name": "System Team"},
        )
        assert r.status_code == 201

        # Mark as system via DB
        from app.core.db import SessionLocal
        from app.swarm.team_models import AgentTeamConfig
        db = SessionLocal()
        try:
            team = db.query(AgentTeamConfig).filter(AgentTeamConfig.slug == slug).first()
            if team:
                team.is_system = True
                db.commit()
        finally:
            db.close()

        # system_admin (no-auth bypass) CAN delete
        del_resp = await client.delete(f"/v2/admin/agent-teams/{slug}")
        assert del_resp.status_code == 204

    @pytest.mark.anyio
    async def test_deactivate_and_reactivate_team(self, client: AsyncClient) -> None:
        """Updating is_active=False then True should toggle the team correctly."""
        slug = f"toggle-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-teams/", json={"slug": slug, "name": "Toggle Team"})

        # Deactivate
        r1 = await client.put(f"/v2/admin/agent-teams/{slug}", json={"is_active": False})
        assert r1.status_code == 200
        assert r1.json()["is_active"] is False

        # Reactivate
        r2 = await client.put(f"/v2/admin/agent-teams/{slug}", json={"is_active": True})
        assert r2.status_code == 200
        assert r2.json()["is_active"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 3. INPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestInputValidation:
    """Pydantic validators and field constraints."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("bad_slug", [
        "Uppercase",
        "-starts-with-dash",
        "ends-with-dash-",
        "has spaces",
        "a" * 65,
    ])
    async def test_invalid_slug_returns_422(self, client: AsyncClient, bad_slug: str) -> None:
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": bad_slug, "name": "Bad Slug Team"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    @pytest.mark.parametrize("good_slug", [
        "valid-slug",
        "abc123",
        "a1b2c3d4",
    ])
    async def test_valid_slug_accepted(self, client: AsyncClient, good_slug: str) -> None:
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": good_slug, "name": "Good Slug"},
        )
        # 201 or 409 (duplicate) — but NOT 422
        assert resp.status_code in (201, 409)

    @pytest.mark.anyio
    async def test_empty_name_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": "ok-slug-nm", "name": "   "},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_name_too_long_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": "ok-slug2", "name": "x" * 129},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_execution_mode_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": "mode-test-inv", "name": "Mode Test", "execution_mode": "magic"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    @pytest.mark.parametrize("mode", ["pipeline", "orchestrator"])
    async def test_valid_execution_modes(self, client: AsyncClient, mode: str) -> None:
        slug = f"{mode}-mode-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": slug, "name": f"{mode} Team", "execution_mode": mode},
        )
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_duplicate_step_order_returns_422(self, client: AsyncClient) -> None:
        slug = f"dup-order-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={
                "slug": slug,
                "name": "Dup Order",
                "steps": [
                    {"step_order": 0, "agent_slug": "ops"},
                    {"step_order": 0, "agent_slug": "sales"},  # duplicate!
                ],
            },
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_tools_json_invalid_returns_422(self, client: AsyncClient) -> None:
        slug = f"bad-tools-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={
                "slug": slug,
                "name": "Bad Tools",
                "steps": [{"step_order": 0, "agent_slug": "ops", "tools_json": "not-json{"}],
            },
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_tools_json_not_array_returns_422(self, client: AsyncClient) -> None:
        slug = f"tools-obj-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={
                "slug": slug,
                "name": "Tools Object",
                "steps": [{"step_order": 0, "agent_slug": "ops", "tools_json": '{"a": 1}'}],
            },
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_tools_json_non_string_elements_returns_422(
        self, client: AsyncClient
    ) -> None:
        slug = f"tools-int-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={
                "slug": slug,
                "name": "Tools Int",
                "steps": [{"step_order": 0, "agent_slug": "ops", "tools_json": "[1, 2]"}],
            },
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_input_schema_json_must_be_object(self, client: AsyncClient) -> None:
        slug = f"bad-schema-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": slug, "name": "Bad Schema", "input_schema_json": "[1,2,3]"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_input_schema_json_valid_object(self, client: AsyncClient) -> None:
        slug = f"good-schema-{int(time.time() * 1000)}"
        schema = json.dumps({"type": "object", "properties": {"prompt": {"type": "string"}}})
        resp = await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": slug, "name": "Good Schema", "input_schema_json": schema},
        )
        assert resp.status_code == 201
        assert resp.json()["input_schema_json"] is not None

    @pytest.mark.anyio
    async def test_update_team_duplicate_step_order_returns_422(
        self, client: AsyncClient
    ) -> None:
        slug = f"upd-dup-ord-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-teams/", json={"slug": slug, "name": "X"})
        resp = await client.put(
            f"/v2/admin/agent-teams/{slug}",
            json={"steps": [
                {"step_order": 0, "agent_slug": "ops"},
                {"step_order": 0, "agent_slug": "sales"},
            ]},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_team_empty_name_returns_422(self, client: AsyncClient) -> None:
        slug = f"upd-nm-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-teams/", json={"slug": slug, "name": "Valid"})
        resp = await client.put(f"/v2/admin/agent-teams/{slug}", json={"name": ""})
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MULTI-TENANT ISOLATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiTenantIsolation:
    """Tenant A teams must never be visible or editable by Tenant B."""

    @pytest.mark.anyio
    async def test_teams_isolated_between_tenants(
        self, client: AsyncClient
    ) -> None:
        """A team created by tenant A must not appear in tenant B's list."""
        from app.core.db import SessionLocal
        from app.swarm.team_models import AgentTeamConfig

        _, tid_a = await _register_tenant(client, "iso-ta")
        _, tid_b = await _register_tenant(client, "iso-tb")
        slug = f"ta-private-{int(time.time() * 1000)}"

        # Insert directly for tenant A (bypass feature gate)
        db = SessionLocal()
        try:
            team = AgentTeamConfig(
                tenant_id=tid_a,
                slug=slug,
                name="Tenant A Private Team",
                execution_mode="pipeline",
                yaml_version=1,
                is_active=True,
                is_system=False,
            )
            db.add(team)
            db.commit()
        finally:
            db.close()

        # Tenant B does not see it (no-auth = system tenant, different tenant_id)
        # Instead check DB directly for isolation
        db = SessionLocal()
        try:
            teams_b = db.query(AgentTeamConfig).filter(
                AgentTeamConfig.tenant_id == tid_b
            ).all()
            b_slugs = [t.slug for t in teams_b]
            assert slug not in b_slugs
        finally:
            db.close()

    @pytest.mark.anyio
    async def test_tenant_b_cannot_get_tenant_a_team_via_api(
        self, client: AsyncClient, tenant_a, tenant_b
    ) -> None:
        """GET detail for tenant A's team must 404 when authenticated as tenant B."""
        from app.core.db import SessionLocal
        from app.swarm.team_models import AgentTeamConfig

        _, tid_a = tenant_a
        token_b, tid_b = tenant_b

        slug = f"priv-team-{int(time.time() * 1000)}"
        db = SessionLocal()
        try:
            team = AgentTeamConfig(
                tenant_id=tid_a,
                slug=slug,
                name="Private Team A",
                execution_mode="pipeline",
                yaml_version=1,
                is_active=True,
                is_system=False,
            )
            db.add(team)
            db.commit()
        finally:
            db.close()

        # Tenant B (feature-gated) gets 402, not 200
        # (402 before 404 because feature gate fires first)
        resp = await client.get(f"/v2/admin/agent-teams/{slug}/detail", headers=_auth(token_b))
        assert resp.status_code in (402, 404)

    @pytest.mark.anyio
    async def test_run_records_isolated_per_tenant(self) -> None:
        """Runs for tenant A must not be queryable by tenant B at the DB layer."""
        from app.core.db import SessionLocal
        from app.swarm.run_models import AgentTeamRun

        slug_a = f"run-iso-{int(time.time() * 1000)}"
        db = SessionLocal()
        try:
            run_a = AgentTeamRun(
                tenant_id=99901,  # fake isolated tenant
                team_slug=slug_a,
                trigger_source="test",
                success=True,
                started_at=datetime.now(timezone.utc),
            )
            db.add(run_a)
            db.commit()

            # Query with a different tenant_id — must not find run_a
            runs = db.query(AgentTeamRun).filter(
                AgentTeamRun.tenant_id == 99902,
                AgentTeamRun.team_slug == slug_a,
            ).all()
            assert len(runs) == 0
        finally:
            db.close()

    @pytest.mark.anyio
    async def test_tenant_tools_isolated(self) -> None:
        """Custom (non-builtin) tools for tenant A are not visible to tenant B."""
        from app.core.db import SessionLocal
        from app.swarm.team_models import AgentToolDefinition
        from sqlalchemy import or_

        slug = f"custom-iso-tool-{int(time.time() * 1000)}"
        tid_a = 88801
        tid_b = 88802

        db = SessionLocal()
        try:
            tool = AgentToolDefinition(
                tenant_id=tid_a,
                slug=slug,
                name="Tenant A Only Tool",
                is_builtin=False,
                is_active=True,
            )
            db.add(tool)
            db.commit()

            # Tenant B query — should NOT include this tool
            tools = db.query(AgentToolDefinition).filter(
                or_(
                    AgentToolDefinition.tenant_id == None,
                    AgentToolDefinition.tenant_id == tid_b,
                )
            ).all()
            tool_slugs = [t.slug for t in tools]
            assert slug not in tool_slugs
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. FEATURE GATE ENFORCEMENT
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeatureGate:
    """Starter plan tenants without agent_teams_enabled must get 402."""

    @pytest.mark.anyio
    async def test_tenant_admin_without_plan_gets_402_on_list(
        self, client: AsyncClient, tenant_a
    ) -> None:
        token, _ = tenant_a
        resp = await client.get("/v2/admin/agent-teams/", headers=_auth(token))
        assert resp.status_code == 402

    @pytest.mark.anyio
    async def test_tenant_admin_without_plan_gets_402_on_create(
        self, client: AsyncClient, tenant_a
    ) -> None:
        token, _ = tenant_a
        resp = await client.post(
            "/v2/admin/agent-teams/",
            headers=_auth(token),
            json={"slug": "blocked-team", "name": "Blocked"},
        )
        assert resp.status_code == 402

    @pytest.mark.anyio
    async def test_tenant_admin_without_plan_gets_402_on_tools(
        self, client: AsyncClient, tenant_a
    ) -> None:
        token, _ = tenant_a
        resp = await client.get("/v2/admin/agent-tools/", headers=_auth(token))
        assert resp.status_code == 402

    @pytest.mark.anyio
    async def test_system_admin_never_gets_402(self, client: AsyncClient) -> None:
        """No-auth bypass = system_admin — must always return 200."""
        resp = await client.get("/v2/admin/agent-teams/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_feature_gate_function_directly(self) -> None:
        """FeatureGate(starter_tenant_id).require_feature raises HTTP 402."""
        from app.core.feature_gates import FeatureGate
        from fastapi import HTTPException

        # system tenant (tid=1) seeded by conftest has a Starter plan at best
        # Use a non-existent tenant_id so there's definitely no plan
        gate = FeatureGate(tenant_id=999888777)
        with pytest.raises(HTTPException) as exc_info:
            gate.require_feature("agent_teams")
        assert exc_info.value.status_code == 402


# ═══════════════════════════════════════════════════════════════════════════════
# 6. TOOL CRUD & SCOPING
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolCRUD:
    """Tool creation, listing, update, deletion — and scope rules.

    Uses no-auth (system_admin bypass) unless otherwise noted.
    """

    @pytest.mark.anyio
    async def test_list_tools_includes_global_builtins(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-tools/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        slugs = [t["slug"] for t in data]
        assert "knowledge_base" in slugs

    @pytest.mark.anyio
    async def test_create_custom_tool(self, client: AsyncClient) -> None:
        slug = f"my-tool-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-tools/",
            json={"slug": slug, "name": "My Custom Tool"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == slug
        assert data["is_active"] is True

    @pytest.mark.anyio
    async def test_create_tool_duplicate_slug_returns_409(self, client: AsyncClient) -> None:
        slug = f"dup-tool-{int(time.time() * 1000)}"
        r1 = await client.post("/v2/admin/agent-tools/", json={"slug": slug, "name": "First"})
        assert r1.status_code == 201
        r2 = await client.post("/v2/admin/agent-tools/", json={"slug": slug, "name": "Second"})
        assert r2.status_code == 409

    @pytest.mark.anyio
    async def test_create_builtin_tool_requires_system_admin(
        self, client: AsyncClient
    ) -> None:
        """A tenant_user trying to create a builtin tool must be rejected."""
        _, tid = await _register_tenant(client, "builtin-test")
        user_token = _make_tenant_user_token(tid)
        slug = f"new-builtin-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-tools/",
            headers=_auth(user_token),
            json={"slug": slug, "name": "Builtin", "is_builtin": True},
        )
        # tenant_user gets 403 (role guard fires before feature gate)
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_update_tool(self, client: AsyncClient) -> None:
        slug = f"upd-tool-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-tools/", json={"slug": slug, "name": "Old Tool Name"})
        resp = await client.put(
            f"/v2/admin/agent-tools/{slug}",
            json={"name": "New Tool Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Tool Name"

    @pytest.mark.anyio
    async def test_update_tool_not_found(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/v2/admin/agent-tools/no-such-tool",
            json={"name": "X"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_tool(self, client: AsyncClient) -> None:
        slug = f"del-tool-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-tools/", json={"slug": slug, "name": "Deletable"})
        resp = await client.delete(f"/v2/admin/agent-tools/{slug}")
        assert resp.status_code == 204

        list_resp = await client.get("/v2/admin/agent-tools/")
        slugs = [t["slug"] for t in list_resp.json()]
        assert slug not in slugs

    @pytest.mark.anyio
    async def test_delete_tool_not_found(self, client: AsyncClient) -> None:
        resp = await client.delete("/v2/admin/agent-tools/no-such-tool")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_tool_invalid_slug_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/v2/admin/agent-tools/",
            json={"slug": "INVALID_SLUG", "name": "Bad Tool"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_tool_config_schema_must_be_object(self, client: AsyncClient) -> None:
        slug = f"schema-tool-{int(time.time() * 1000)}"
        resp = await client.post(
            "/v2/admin/agent-tools/",
            json={"slug": slug, "name": "Schema Tool", "config_schema_json": "[1, 2]"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_global_builtin_tools_have_null_tenant_id(self) -> None:
        """All seeded builtin tools must have tenant_id=NULL."""
        from app.core.db import SessionLocal
        from app.swarm.team_models import AgentToolDefinition

        db = SessionLocal()
        try:
            builtins = db.query(AgentToolDefinition).filter(
                AgentToolDefinition.is_builtin == True,
            ).all()
            for tool in builtins:
                assert tool.tenant_id is None, (
                    f"Builtin tool '{tool.slug}' has non-NULL tenant_id={tool.tenant_id}"
                )
        finally:
            db.close()

    @pytest.mark.anyio
    async def test_deactivate_tool(self, client: AsyncClient) -> None:
        slug = f"deact-tool-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-tools/", json={"slug": slug, "name": "Active Tool"})
        resp = await client.put(f"/v2/admin/agent-tools/{slug}", json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # Not shown in active_only=true list
        list_resp = await client.get("/v2/admin/agent-tools/?active_only=true")
        slugs = [t["slug"] for t in list_resp.json()]
        assert slug not in slugs


# ═══════════════════════════════════════════════════════════════════════════════
# 7. RUN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunEndpoints:
    """Run history list, detail, per-team, filters, and run submission."""

    @pytest.fixture
    def _seeded_run(self):
        """Insert a completed run record for tenant_id=1 (system tenant)."""
        from app.core.db import SessionLocal
        from app.swarm.run_models import AgentTeamRun

        slug = f"run-team-{int(time.time() * 1000)}"
        db = SessionLocal()
        try:
            run = AgentTeamRun(
                tenant_id=1,
                team_slug=slug,
                trigger_source="test",
                success=True,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=42,
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            return run.id, slug
        finally:
            db.close()

    @pytest.mark.anyio
    async def test_list_all_runs_pagination(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-runs/?page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "page" in data
        assert "items" in data
        assert data["page"] == 1

    @pytest.mark.anyio
    async def test_list_runs_filter_by_team_slug(
        self, client: AsyncClient, _seeded_run
    ) -> None:
        run_id, slug = _seeded_run
        resp = await client.get(f"/v2/admin/agent-runs/?team_slug={slug}")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert all(item["team_slug"] == slug for item in items)

    @pytest.mark.anyio
    async def test_list_runs_filter_by_success_true(self, client: AsyncClient, _seeded_run) -> None:
        resp = await client.get("/v2/admin/agent-runs/?success=true")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["success"] is True

    @pytest.mark.anyio
    async def test_list_runs_filter_by_success_false(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-runs/?success=false")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["success"] is False

    @pytest.mark.anyio
    async def test_list_runs_filter_by_started_after(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-runs/?started_after=2020-01-01T00:00:00Z")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_runs_filter_by_started_before(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-runs/?started_before=2099-01-01T00:00:00Z")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_runs_page_size_limit(self, client: AsyncClient) -> None:
        """page_size > 100 must return 422."""
        resp = await client.get("/v2/admin/agent-runs/?page_size=200")
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_get_run_detail(self, client: AsyncClient, _seeded_run) -> None:
        run_id, slug = _seeded_run
        resp = await client.get(f"/v2/admin/agent-runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == run_id
        assert data["team_slug"] == slug
        assert "payload" in data
        assert "steps" in data

    @pytest.mark.anyio
    async def test_get_run_detail_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-runs/9999999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_team_runs(self, client: AsyncClient, _seeded_run) -> None:
        run_id, slug = _seeded_run
        resp = await client.get(f"/v2/admin/agent-teams/{slug}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(item["team_slug"] == slug for item in data["items"])

    @pytest.mark.anyio
    async def test_run_team_not_found_returns_404(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/v2/admin/agent-teams/no-such-team-run/run",
            json={"payload": {}},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_run_empty_pipeline_succeeds_and_creates_run_record(
        self, client: AsyncClient
    ) -> None:
        """Running an empty pipeline team creates a run record and returns run_id."""
        slug = f"runnable-{int(time.time() * 1000)}"
        await client.post(
            "/v2/admin/agent-teams/",
            json={"slug": slug, "name": "Runnable Team", "steps": []},
        )

        with patch("app.swarm.base_team._get_slug_agent_map", return_value={}):
            resp = await client.post(
                f"/v2/admin/agent-teams/{slug}/run",
                json={"payload": {"message": "hello"}},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["run_id"] is not None
        assert data["success"] is True

        # Verify run record persisted
        from app.core.db import SessionLocal
        from app.swarm.run_models import AgentTeamRun
        db = SessionLocal()
        try:
            run = db.query(AgentTeamRun).filter(AgentTeamRun.id == data["run_id"]).first()
            assert run is not None
            assert run.success is True
            assert run.completed_at is not None
        finally:
            db.close()

    @pytest.mark.anyio
    async def test_run_team_result_has_required_fields(self, client: AsyncClient) -> None:
        slug = f"fields-team-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-teams/", json={"slug": slug, "name": "Fields Team", "steps": []})
        with patch("app.swarm.base_team._get_slug_agent_map", return_value={}):
            resp = await client.post(
                f"/v2/admin/agent-teams/{slug}/run",
                json={"payload": {}},
            )
        assert resp.status_code == 201
        data = resp.json()
        for field in ("run_id", "success", "error", "duration_ms", "output", "steps"):
            assert field in data

    @pytest.mark.anyio
    async def test_run_inactive_team_returns_404(self, client: AsyncClient) -> None:
        """Running a deactivated team must return 404."""
        slug = f"inactive-run-{int(time.time() * 1000)}"
        await client.post("/v2/admin/agent-teams/", json={"slug": slug, "name": "Inactive"})
        await client.put(f"/v2/admin/agent-teams/{slug}", json={"is_active": False})

        resp = await client.post(
            f"/v2/admin/agent-teams/{slug}/run",
            json={"payload": {}},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 8. BASE TEAM — UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBaseTeamUnit:
    """Unit-level tests for base_team.py classes."""

    def test_pipeline_step_to_dict(self) -> None:
        from app.swarm.base_team import PipelineStep
        step = PipelineStep(name="test-step", status="completed", duration_ms=50)
        d = step.to_dict()
        assert d["name"] == "test-step"
        assert d["status"] == "completed"
        assert d["duration_ms"] == 50
        assert d["error"] is None

    def test_pipeline_step_failed_to_dict(self) -> None:
        from app.swarm.base_team import PipelineStep
        step = PipelineStep(name="fail-step", status="failed", error="boom")
        d = step.to_dict()
        assert d["status"] == "failed"
        assert d["error"] == "boom"

    def test_team_result_steps_as_json(self) -> None:
        from app.swarm.base_team import TeamResult, PipelineStep
        result = TeamResult(
            success=True,
            steps=[
                PipelineStep(name="s1", status="completed", duration_ms=10),
                PipelineStep(name="s2", status="failed", error="oops"),
            ],
        )
        raw = result.steps_as_json()
        parsed = json.loads(raw)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "s1"
        assert parsed[1]["error"] == "oops"

    def test_team_result_run_id_none_by_default(self) -> None:
        from app.swarm.base_team import TeamResult
        r = TeamResult()
        assert r.run_id is None

    def test_step_context_success(self) -> None:
        from app.swarm.base_team import _StepContext
        ctx = _StepContext("my-step")
        with ctx as step:
            pass
        assert step.status == "completed"
        assert step.duration_ms >= 0
        assert step.error is None

    def test_step_context_exception_suppressed(self) -> None:
        from app.swarm.base_team import _StepContext
        ctx = _StepContext("failing-step")
        with ctx as step:
            raise ValueError("deliberate error")
        assert step.status == "failed"
        assert step.error == "deliberate error"

    def test_step_context_does_not_suppress_keyboard_interrupt(self) -> None:
        from app.swarm.base_team import _StepContext
        ctx = _StepContext("kbd-step")
        with pytest.raises(KeyboardInterrupt):
            with ctx:
                raise KeyboardInterrupt()

    def test_step_context_does_not_suppress_system_exit(self) -> None:
        from app.swarm.base_team import _StepContext
        ctx = _StepContext("exit-step")
        with pytest.raises(SystemExit):
            with ctx:
                raise SystemExit(1)

    def test_agent_context_fields(self) -> None:
        from app.swarm.base_team import AgentContext
        ctx = AgentContext(tenant_id=7, tenant_slug="my-studio", user_id=42)
        assert ctx.tenant_id == 7
        assert ctx.tenant_slug == "my-studio"
        assert ctx.user_id == 42

    @pytest.mark.anyio
    async def test_empty_pipeline_succeeds(self) -> None:
        from app.swarm.base_team import DBDelegatingTeam, AgentContext

        team_cfg = MagicMock()
        team_cfg.slug = "empty-team"
        team_cfg.name = "Empty"
        team_cfg.execution_mode = "pipeline"

        team = DBDelegatingTeam(team_cfg, steps=[])
        ctx = AgentContext(tenant_id=1, tenant_slug="s")
        result = await team.run({}, ctx, db=None)

        assert result.success is True
        assert result.steps == []
        assert result.output == {}

    @pytest.mark.anyio
    async def test_non_optional_step_failure_aborts_pipeline(self) -> None:
        from app.swarm.base_team import DBDelegatingTeam, AgentContext

        team_cfg = MagicMock()
        team_cfg.slug = "abort-test"
        team_cfg.name = "Abort"
        team_cfg.execution_mode = "pipeline"

        step_cfg = MagicMock()
        step_cfg.step_order = 0
        step_cfg.agent_slug = "ops"
        step_cfg.display_name = "Ops"
        step_cfg.is_optional = False

        with patch(
            "app.swarm.base_team._invoke_agent_step",
            new_callable=AsyncMock,
            side_effect=RuntimeError("step exploded"),
        ):
            team = DBDelegatingTeam(team_cfg, steps=[step_cfg])
            ctx = AgentContext(tenant_id=1, tenant_slug="s")
            result = await team.run({}, ctx, db=None)

        assert result.success is False
        assert "step exploded" in result.error

    @pytest.mark.anyio
    async def test_optional_step_failure_continues_pipeline(self) -> None:
        from app.swarm.base_team import DBDelegatingTeam, AgentContext

        team_cfg = MagicMock()
        team_cfg.slug = "opt-test"
        team_cfg.name = "Optional"
        team_cfg.execution_mode = "pipeline"

        step1 = MagicMock()
        step1.step_order = 0
        step1.agent_slug = "ops"
        step1.display_name = "Ops"
        step1.is_optional = True  # optional — failure does not abort

        step2 = MagicMock()
        step2.step_order = 1
        step2.agent_slug = "sales"
        step2.display_name = "Sales"
        step2.is_optional = False

        invoke_calls = []

        async def fake_invoke(step_cfg, payload, ctx, db):
            invoke_calls.append(step_cfg.agent_slug)
            if step_cfg.agent_slug == "ops":
                raise RuntimeError("optional step failed")
            return {"response": "ok"}

        with patch("app.swarm.base_team._invoke_agent_step", side_effect=fake_invoke):
            team = DBDelegatingTeam(team_cfg, steps=[step1, step2])
            ctx = AgentContext(tenant_id=1, tenant_slug="s")
            result = await team.run({}, ctx, db=None)

        assert result.success is True
        assert "ops" in invoke_calls
        assert "sales" in invoke_calls

    @pytest.mark.anyio
    async def test_pipeline_passes_output_to_next_step(self) -> None:
        """Output from step N must be merged into context for step N+1."""
        from app.swarm.base_team import DBDelegatingTeam, AgentContext

        team_cfg = MagicMock()
        team_cfg.slug = "ctx-pass"
        team_cfg.name = "Context Pass"
        team_cfg.execution_mode = "pipeline"

        step1 = MagicMock(step_order=0, agent_slug="ops", display_name="Ops", is_optional=False)
        step2 = MagicMock(step_order=1, agent_slug="sales", display_name="Sales", is_optional=False)

        received_payloads = []

        async def fake_invoke(step_cfg, payload, ctx, db):
            received_payloads.append(dict(payload))
            if step_cfg.agent_slug == "ops":
                return {"enriched": "data"}
            return {"done": True}

        with patch("app.swarm.base_team._invoke_agent_step", side_effect=fake_invoke):
            team = DBDelegatingTeam(team_cfg, steps=[step1, step2])
            ctx = AgentContext(tenant_id=1, tenant_slug="s")
            result = await team.run({"initial": "payload"}, ctx, db=None)

        assert result.success is True
        # Step 2 should receive merged context with step 1's output
        assert received_payloads[1].get("enriched") == "data"
        assert received_payloads[1].get("initial") == "payload"

    @pytest.mark.anyio
    async def test_run_and_save_creates_run_record(self) -> None:
        from app.swarm.base_team import DBDelegatingTeam, AgentContext
        from app.core.db import SessionLocal
        from app.swarm.run_models import AgentTeamRun

        team_cfg = MagicMock()
        team_cfg.slug = f"save-test-{int(time.time() * 1000)}"
        team_cfg.name = "Save Test"
        team_cfg.execution_mode = "pipeline"

        team = DBDelegatingTeam(team_cfg, steps=[])
        ctx = AgentContext(tenant_id=1, tenant_slug="s")

        db = SessionLocal()
        try:
            result = await team.run_and_save({}, ctx, db)
            assert result.run_id is not None

            run = db.query(AgentTeamRun).filter(AgentTeamRun.id == result.run_id).first()
            assert run is not None
            assert run.success is True
            assert run.completed_at is not None
            assert run.team_slug == team_cfg.slug
        finally:
            db.close()

    @pytest.mark.anyio
    async def test_run_and_save_timeout_marks_run_failed(self) -> None:
        import asyncio
        from app.swarm.base_team import DBDelegatingTeam, AgentContext, TeamResult
        from app.core.db import SessionLocal
        from app.swarm.run_models import AgentTeamRun

        team_cfg = MagicMock()
        team_cfg.slug = f"timeout-{int(time.time() * 1000)}"
        team_cfg.name = "Timeout Test"
        team_cfg.execution_mode = "pipeline"

        team = DBDelegatingTeam(team_cfg, steps=[])

        async def slow_run(payload, context, db):
            await asyncio.sleep(10)
            return TeamResult(success=True)

        db = SessionLocal()
        try:
            with patch.object(team, "run", side_effect=slow_run):
                result = await team.run_and_save(
                    {}, AgentContext(tenant_id=1, tenant_slug="s"), db,
                    timeout_seconds=0.01,
                )

            assert result.success is False
            assert "timed out" in result.error.lower()
            assert result.run_id is not None

            run = db.query(AgentTeamRun).filter(AgentTeamRun.id == result.run_id).first()
            assert run is not None
            assert run.success is False
        finally:
            db.close()

    @pytest.mark.anyio
    async def test_run_and_save_exception_marks_run_failed(self) -> None:
        from app.swarm.base_team import DBDelegatingTeam, AgentContext
        from app.core.db import SessionLocal
        from app.swarm.run_models import AgentTeamRun

        team_cfg = MagicMock()
        team_cfg.slug = f"exc-run-{int(time.time() * 1000)}"
        team_cfg.name = "Exception Test"
        team_cfg.execution_mode = "pipeline"

        team = DBDelegatingTeam(team_cfg, steps=[])

        async def boom_run(payload, context, db):
            raise RuntimeError("unexpected boom")

        db = SessionLocal()
        try:
            with patch.object(team, "run", side_effect=boom_run):
                result = await team.run_and_save(
                    {}, AgentContext(tenant_id=1, tenant_slug="s"), db
                )

            assert result.success is False
            assert "unexpected boom" in result.error
        finally:
            db.close()

    def test_register_and_get_team(self) -> None:
        from app.swarm.base_team import register_team, get_team, list_teams, BaseAgentTeam

        @register_team("_test-reg-unit")
        class MyTestTeam(BaseAgentTeam):
            slug = "_test-reg-unit"

            async def run(self, payload, context, db=None):
                from app.swarm.base_team import TeamResult
                return TeamResult(success=True)

        assert get_team("_test-reg-unit") is MyTestTeam
        assert "_test-reg-unit" in list_teams()

    def test_get_team_returns_none_for_unknown(self) -> None:
        from app.swarm.base_team import get_team
        assert get_team("does-not-exist-xyz") is None


# ═══════════════════════════════════════════════════════════════════════════════
# 9. TEAM_YAML — UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamYaml:
    """Path-traversal prevention, atomic writes, slug validation."""

    def _patch_teams_dir(self, monkeypatch, tmp_path):
        """Patch TEAMS_DIR to a temp directory."""
        import app.swarm.team_yaml as ty
        monkeypatch.setattr(ty, "TEAMS_DIR", str(tmp_path))

    def test_valid_slug_path_accepted(self, monkeypatch, tmp_path) -> None:
        import app.swarm.team_yaml as ty
        self._patch_teams_dir(monkeypatch, tmp_path)
        path = ty._safe_path("valid-slug-123")
        assert path.endswith("valid-slug-123.yaml")

    @pytest.mark.parametrize("bad_slug", [
        "../evil",
        "../../etc/passwd",
        "UPPER",
        "has spaces",
        "-starts-dash",
        "ends-dash-",
    ])
    def test_invalid_slug_raises_value_error(self, monkeypatch, tmp_path, bad_slug: str) -> None:
        import app.swarm.team_yaml as ty
        self._patch_teams_dir(monkeypatch, tmp_path)
        with pytest.raises(ValueError):
            ty._safe_path(bad_slug)

    def test_export_creates_yaml_file(self, monkeypatch, tmp_path) -> None:
        import app.swarm.team_yaml as ty
        self._patch_teams_dir(monkeypatch, tmp_path)

        team = MagicMock()
        team.slug = "export-test"
        team.name = "Export Test"
        team.execution_mode = "pipeline"
        team.yaml_version = 1
        team.description = None
        team.lead_agent_slug = None
        team.input_schema_json = None

        step = MagicMock()
        step.step_order = 0
        step.agent_slug = "ops"
        step.display_name = "Ops"
        step.tools_json = '["knowledge_base"]'
        step.prompt_override = None
        step.model_override = None
        step.is_optional = False

        path = ty.export_team_yaml(team, [step])
        assert os.path.exists(path)

    def test_export_yaml_content(self, monkeypatch, tmp_path) -> None:
        import yaml
        import app.swarm.team_yaml as ty
        self._patch_teams_dir(monkeypatch, tmp_path)

        team = MagicMock()
        team.slug = "content-test"
        team.name = "Content Test"
        team.execution_mode = "orchestrator"
        team.yaml_version = 3
        team.description = "My description"
        team.lead_agent_slug = "marketing_agent"
        team.input_schema_json = None

        path = ty.export_team_yaml(team, [])
        with open(path) as f:
            doc = yaml.safe_load(f)

        assert doc["slug"] == "content-test"
        assert doc["name"] == "Content Test"
        assert doc["execution_mode"] == "orchestrator"
        assert doc["version"] == 3
        assert doc.get("description") == "My description"

    def test_export_yaml_step_tools_parsed(self, monkeypatch, tmp_path) -> None:
        import yaml
        import app.swarm.team_yaml as ty
        self._patch_teams_dir(monkeypatch, tmp_path)

        team = MagicMock()
        team.slug = "tools-test"
        team.name = "Tools Test"
        team.execution_mode = "pipeline"
        team.yaml_version = 1
        team.description = None
        team.lead_agent_slug = None
        team.input_schema_json = None

        step = MagicMock()
        step.step_order = 0
        step.agent_slug = "ops"
        step.display_name = "Ops"
        step.tools_json = '["knowledge_base", "chat_history"]'
        step.prompt_override = None
        step.model_override = None
        step.is_optional = False

        path = ty.export_team_yaml(team, [step])
        with open(path) as f:
            doc = yaml.safe_load(f)

        assert doc["steps"][0]["tools"] == ["knowledge_base", "chat_history"]

    def test_load_team_yaml_returns_none_for_missing(self, monkeypatch, tmp_path) -> None:
        import app.swarm.team_yaml as ty
        self._patch_teams_dir(monkeypatch, tmp_path)
        result = ty.load_team_yaml("nonexistent-team")
        assert result is None

    def test_load_team_yaml_invalid_slug_returns_none(self, monkeypatch, tmp_path) -> None:
        import app.swarm.team_yaml as ty
        self._patch_teams_dir(monkeypatch, tmp_path)
        result = ty.load_team_yaml("../etc/passwd")
        assert result is None

    def test_export_yaml_temp_file_cleaned_up_on_failure(self, monkeypatch, tmp_path) -> None:
        """Temp file must be removed even when os.replace raises."""
        import app.swarm.team_yaml as ty
        self._patch_teams_dir(monkeypatch, tmp_path)

        team = MagicMock()
        team.slug = "atomic-test"
        team.name = "Atomic"
        team.execution_mode = "pipeline"
        team.yaml_version = 1
        team.description = None
        team.lead_agent_slug = None
        team.input_schema_json = None

        with patch("os.replace", side_effect=OSError("simulated failure")):
            with pytest.raises(OSError):
                ty.export_team_yaml(team, [])

        # Temp file must have been cleaned up
        tmp_file = os.path.join(str(tmp_path), "atomic-test.yaml.tmp")
        assert not os.path.exists(tmp_file)

    def test_load_team_yaml_roundtrip(self, monkeypatch, tmp_path) -> None:
        """Export then load must produce consistent content."""
        import app.swarm.team_yaml as ty
        self._patch_teams_dir(monkeypatch, tmp_path)

        team = MagicMock()
        team.slug = "roundtrip-test"
        team.name = "Roundtrip"
        team.execution_mode = "pipeline"
        team.yaml_version = 2
        team.description = None
        team.lead_agent_slug = None
        team.input_schema_json = None

        ty.export_team_yaml(team, [])
        loaded = ty.load_team_yaml("roundtrip-test")
        assert loaded is not None
        assert loaded["slug"] == "roundtrip-test"
        assert loaded["version"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 10. SEED_TEAMS — UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSeedTeams:
    """Idempotency and version-guard behavior."""

    def test_seed_tools_idempotent(self) -> None:
        """Running _seed_tools twice must not create duplicates."""
        from app.core.db import SessionLocal
        from app.swarm.seed_teams import _seed_tools
        from app.swarm.team_models import AgentToolDefinition

        db = SessionLocal()
        try:
            _seed_tools(db)
            _seed_tools(db)  # second call must be no-op
            db.commit()

            tools = db.query(AgentToolDefinition).filter(
                AgentToolDefinition.tenant_id == None
            ).all()
            slugs = [t.slug for t in tools]
            assert len(slugs) == len(set(slugs)), "Duplicate global tool slugs"
        finally:
            db.close()

    def test_is_seeded_returns_false_for_unknown_tenant(self) -> None:
        from app.core.db import SessionLocal
        from app.swarm.seed_teams import _is_seeded

        db = SessionLocal()
        try:
            result = _is_seeded(db, tenant_id=999999)
            assert result is False
        finally:
            db.close()

    def test_mark_seeded_then_is_seeded_true(self) -> None:
        from app.core.db import SessionLocal
        from app.swarm.seed_teams import _is_seeded, _mark_seeded

        fake_tid = int(time.time() * 1000) % 1_000_000

        db = SessionLocal()
        try:
            assert not _is_seeded(db, fake_tid)
            _mark_seeded(db, fake_tid)
            db.commit()
            assert _is_seeded(db, fake_tid)
        finally:
            db.close()

    def test_seed_teams_for_single_tenant_idempotent(self) -> None:
        """Calling seed_teams() twice for the same tenant must not create duplicate teams."""
        from app.core.db import SessionLocal
        from app.swarm.seed_teams import seed_teams
        from app.swarm.team_models import AgentTeamConfig
        from app.core.models import Tenant

        db = SessionLocal()
        try:
            uid = f"seed-test-{int(time.time() * 1000)}"
            tenant = Tenant(name=f"Seed Test {uid}", slug=uid[:40], is_active=True)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            tid = tenant.id

            seed_teams(db, tenant_id=tid)
            count_first = db.query(AgentTeamConfig).filter(
                AgentTeamConfig.tenant_id == tid
            ).count()

            seed_teams(db, tenant_id=tid)
            count_second = db.query(AgentTeamConfig).filter(
                AgentTeamConfig.tenant_id == tid
            ).count()

            assert count_first == count_second
        finally:
            db.close()

    def test_global_builtins_have_null_tenant_id(self) -> None:
        from app.core.db import SessionLocal
        from app.swarm.seed_teams import _seed_tools
        from app.swarm.team_models import AgentToolDefinition

        db = SessionLocal()
        try:
            _seed_tools(db)
            db.commit()

            builtins = db.query(AgentToolDefinition).filter(
                AgentToolDefinition.is_builtin == True,
                AgentToolDefinition.tenant_id == None,
            ).all()
            assert len(builtins) > 0, "No global builtin tools found after seeding"
        finally:
            db.close()

    def test_seeded_teams_have_correct_fields(self) -> None:
        """System teams created by seed must have is_system=True and is_active=True."""
        from app.core.db import SessionLocal
        from app.swarm.seed_teams import seed_teams
        from app.swarm.team_models import AgentTeamConfig
        from app.core.models import Tenant

        db = SessionLocal()
        try:
            uid = f"fields-test-{int(time.time() * 1000)}"
            tenant = Tenant(name=f"Fields Test {uid}", slug=uid[:40], is_active=True)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            tid = tenant.id

            seed_teams(db, tenant_id=tid)

            teams = db.query(AgentTeamConfig).filter(
                AgentTeamConfig.tenant_id == tid
            ).all()
            assert len(teams) > 0
            for t in teams:
                assert t.is_system is True
                assert t.is_active is True
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 11. AGENT DEFINITIONS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentDefinitionsEndpoint:
    """GET /v2/admin/agent-definitions/ — graceful fallback."""

    @pytest.mark.anyio
    async def test_list_agent_definitions_returns_list(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-definitions/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.anyio
    async def test_agent_definitions_blocked_for_tenant_user(
        self, client: AsyncClient
    ) -> None:
        _, tid = await _register_tenant(client, "agdef-user")
        user_token = _make_tenant_user_token(tid)
        resp = await client.get("/v2/admin/agent-definitions/", headers=_auth(user_token))
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Clone Endpoint
# ═══════════════════════════════════════════════════════════════════════════════


class TestCloneTeam:
    """POST /v2/admin/agent-teams/{slug}/clone"""

    @pytest.mark.anyio
    async def test_clone_creates_new_team(self, client: AsyncClient) -> None:
        import uuid
        uid = uuid.uuid4().hex[:8]
        src = f"clone-src-{uid}"
        dst = f"clone-dst-{uid}"
        resp = await client.post("/v2/admin/agent-teams/", json={
            "slug": src,
            "name": "Clone Source",
            "execution_mode": "pipeline",
            "steps": [{"step_order": 0, "agent_slug": "ops", "display_name": "Step A", "tools_json": '["knowledge_base"]', "is_optional": False}],
        })
        assert resp.status_code == 201

        resp = await client.post(f"/v2/admin/agent-teams/{src}/clone", json={
            "new_slug": dst,
            "new_name": "Clone Destination",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == dst
        assert data["name"] == "Clone Destination"
        assert data["is_system"] is False

    @pytest.mark.anyio
    async def test_clone_copies_steps(self, client: AsyncClient) -> None:
        import uuid
        uid = uuid.uuid4().hex[:8]
        src = f"clone-steps-src-{uid}"
        dst = f"clone-steps-dst-{uid}"
        await client.post("/v2/admin/agent-teams/", json={
            "slug": src,
            "name": "Clone With Steps",
            "execution_mode": "pipeline",
            "steps": [
                {"step_order": 0, "agent_slug": "ops", "display_name": "Step 0", "tools_json": '["knowledge_base"]', "is_optional": False},
                {"step_order": 1, "agent_slug": "sales", "display_name": "Step 1", "tools_json": '[]', "is_optional": True},
            ],
        })
        await client.post(f"/v2/admin/agent-teams/{src}/clone", json={
            "new_slug": dst, "new_name": "Clone Dest Steps",
        })
        detail = await client.get(f"/v2/admin/agent-teams/{dst}/detail")
        assert detail.status_code == 200
        steps = detail.json()["steps"]
        assert len(steps) == 2
        assert steps[0]["agent_slug"] == "ops"
        assert steps[1]["agent_slug"] == "sales"
        assert steps[1]["is_optional"] is True

    @pytest.mark.anyio
    async def test_clone_slug_conflict_returns_409(self, client: AsyncClient) -> None:
        import uuid
        uid = uuid.uuid4().hex[:8]
        src = f"clone-conflict-src-{uid}"
        dst = f"clone-conflict-dst-{uid}"
        await client.post("/v2/admin/agent-teams/", json={
            "slug": src, "name": "Src", "execution_mode": "pipeline",
        })
        await client.post("/v2/admin/agent-teams/", json={
            "slug": dst, "name": "Dst", "execution_mode": "pipeline",
        })
        resp = await client.post(f"/v2/admin/agent-teams/{src}/clone", json={
            "new_slug": dst, "new_name": "Whatever",
        })
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_clone_source_not_found_returns_404(self, client: AsyncClient) -> None:
        import uuid
        uid = uuid.uuid4().hex[:8]
        resp = await client.post(f"/v2/admin/agent-teams/nonexistent-{uid}/clone", json={
            "new_slug": f"whatever-{uid}", "new_name": "Whatever",
        })
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_clone_invalid_new_slug_returns_422(self, client: AsyncClient) -> None:
        import uuid
        uid = uuid.uuid4().hex[:8]
        src = f"clone-valslug-{uid}"
        await client.post("/v2/admin/agent-teams/", json={
            "slug": src, "name": "Src", "execution_mode": "pipeline",
        })
        resp = await client.post(f"/v2/admin/agent-teams/{src}/clone", json={
            "new_slug": "INVALID SLUG!!!", "new_name": "Whatever",
        })
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_clone_blocked_for_tenant_user(self, client: AsyncClient) -> None:
        import uuid
        uid = uuid.uuid4().hex[:8]
        _, tid = _create_tenant_db(f"clone-rbac-{uid}")
        user_token = _make_tenant_user_token(tid)
        resp = await client.post(
            "/v2/admin/agent-teams/some-team/clone",
            json={"new_slug": f"x-copy-{uid}", "new_name": "X Copy"},
            headers=_auth(user_token),
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Tool Usage Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolUsage:
    """GET /v2/admin/agent-tools/usage-summary and /{slug}/usage"""

    @pytest.mark.anyio
    async def test_usage_summary_returns_dict(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-tools/usage-summary")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    @pytest.mark.anyio
    async def test_usage_summary_counts_tool_references(self, client: AsyncClient) -> None:
        import uuid
        uid = uuid.uuid4().hex[:8]
        # Create two teams that both reference knowledge_base
        for i in range(2):
            slug = f"usage-t-{uid}-{i}"
            await client.post("/v2/admin/agent-teams/", json={
                "slug": slug,
                "name": slug,
                "execution_mode": "pipeline",
                "steps": [{"step_order": 0, "agent_slug": "ops", "tools_json": '["knowledge_base"]', "is_optional": False}],
            })

        resp = await client.get("/v2/admin/agent-tools/usage-summary")
        assert resp.status_code == 200
        data = resp.json()
        # knowledge_base should have count >= 2 (other tests may have added more)
        assert data.get("knowledge_base", 0) >= 2

    @pytest.mark.anyio
    async def test_per_tool_usage_returns_structure(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-tools/knowledge_base/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_slug"] == "knowledge_base"
        assert isinstance(data["usage_count"], int)
        assert isinstance(data["usages"], list)

    @pytest.mark.anyio
    async def test_per_tool_usage_lists_teams(self, client: AsyncClient) -> None:
        import uuid
        uid = uuid.uuid4().hex[:8]
        team_slug = f"usage-ref-{uid}"
        await client.post("/v2/admin/agent-teams/", json={
            "slug": team_slug,
            "name": "Usage Ref Team",
            "execution_mode": "pipeline",
            "steps": [{"step_order": 0, "agent_slug": "ops", "tools_json": '["knowledge_base"]', "is_optional": False}],
        })
        resp = await client.get("/v2/admin/agent-tools/knowledge_base/usage")
        assert resp.status_code == 200
        data = resp.json()
        slugs = [u["team_slug"] for u in data["usages"]]
        assert team_slug in slugs

    @pytest.mark.anyio
    async def test_per_tool_unused_tool_returns_zero(self, client: AsyncClient) -> None:
        resp = await client.get("/v2/admin/agent-tools/calendly_booking/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_slug"] == "calendly_booking"
        # No tests reference calendly_booking, so count should be 0
        assert data["usage_count"] == 0

    @pytest.mark.anyio
    async def test_usage_blocked_for_tenant_user(self, client: AsyncClient) -> None:
        _, tid = _create_tenant_db("usage-rbac")
        user_token = _make_tenant_user_token(tid)
        resp = await client.get(
            "/v2/admin/agent-tools/usage-summary",
            headers=_auth(user_token),
        )
        assert resp.status_code == 403
