"""ARIIA Swarm v3 — Integration Tests for Swarm Admin API.

Tests CRUD for agents/tools, tenant config, RBAC enforcement,
system agent protection, and Redis pub/sub cache invalidation.
"""

import time
import json
import pytest
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.core.db import SessionLocal
from app.core.models import AgentDefinition, ToolDefinition, TenantAgentConfig, TenantToolConfig


# ── Helpers ──────────────────────────────────────────────────────────────────


def _system_admin_token() -> str:
    """Create a system_admin access token for testing."""
    return create_access_token(
        user_id=1,
        email="admin@ariia.local",
        tenant_id=1,
        tenant_slug="default",
        role="system_admin",
    )


def _tenant_admin_token() -> str:
    """Create a tenant_admin access token (non-system-admin)."""
    return create_access_token(
        user_id=2,
        email="tenantadmin@test.local",
        tenant_id=1,
        tenant_slug="default",
        role="tenant_admin",
    )


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}"


@pytest.fixture
async def client():
    from app.gateway.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_headers():
    return _auth_headers(_system_admin_token())


@pytest.fixture
def tenant_admin_headers():
    return _auth_headers(_tenant_admin_token())


def _cleanup_agent(agent_id: str):
    """Remove test agent from DB after test."""
    db = SessionLocal()
    try:
        db.query(TenantAgentConfig).filter(TenantAgentConfig.agent_id == agent_id).delete()
        db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).delete()
        db.commit()
    finally:
        db.close()


def _cleanup_tool(tool_id: str):
    """Remove test tool from DB after test."""
    db = SessionLocal()
    try:
        db.query(TenantToolConfig).filter(TenantToolConfig.tool_id == tool_id).delete()
        db.query(ToolDefinition).filter(ToolDefinition.id == tool_id).delete()
        db.commit()
    finally:
        db.close()


# ── Agent CRUD Tests ─────────────────────────────────────────────────────────


class TestCreateAgent:
    @pytest.mark.anyio
    async def test_create_agent_via_api(self, client, admin_headers) -> None:
        """POST /admin/swarm/agents creates AgentDefinition in DB."""
        agent_id = _unique_id("test_agent")
        try:
            resp = await client.post(
                "/admin/swarm/agents",
                json={
                    "id": agent_id,
                    "display_name": "Test Agent",
                    "description": "A test agent",
                    "min_plan_tier": "starter",
                    "max_turns": 5,
                },
                headers=admin_headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["id"] == agent_id
            assert data["display_name"] == "Test Agent"
            assert data["is_system"] is False

            # Verify in DB
            db = SessionLocal()
            try:
                agent = db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
                assert agent is not None
                assert agent.display_name == "Test Agent"
            finally:
                db.close()
        finally:
            _cleanup_agent(agent_id)

    @pytest.mark.anyio
    async def test_create_duplicate_agent_409(self, client, admin_headers) -> None:
        """Creating agent with existing ID returns 409."""
        agent_id = _unique_id("dup_agent")
        try:
            resp1 = await client.post(
                "/admin/swarm/agents",
                json={"id": agent_id, "display_name": "First"},
                headers=admin_headers,
            )
            assert resp1.status_code == 201

            resp2 = await client.post(
                "/admin/swarm/agents",
                json={"id": agent_id, "display_name": "Second"},
                headers=admin_headers,
            )
            assert resp2.status_code == 409
        finally:
            _cleanup_agent(agent_id)


# ── Tool CRUD Tests ──────────────────────────────────────────────────────────


class TestCreateTool:
    @pytest.mark.anyio
    async def test_create_tool_via_api(self, client, admin_headers) -> None:
        """POST /admin/swarm/tools creates ToolDefinition in DB."""
        tool_id = _unique_id("test_tool")
        try:
            resp = await client.post(
                "/admin/swarm/tools",
                json={
                    "id": tool_id,
                    "display_name": "Test Tool",
                    "description": "A test tool",
                    "category": "testing",
                    "min_plan_tier": "starter",
                },
                headers=admin_headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["id"] == tool_id
            assert data["display_name"] == "Test Tool"
            assert data["category"] == "testing"

            # Verify in DB
            db = SessionLocal()
            try:
                tool = db.query(ToolDefinition).filter(ToolDefinition.id == tool_id).first()
                assert tool is not None
                assert tool.display_name == "Test Tool"
            finally:
                db.close()
        finally:
            _cleanup_tool(tool_id)


# ── Tenant Config Tests ──────────────────────────────────────────────────────


class TestTenantAgentConfig:
    @pytest.mark.anyio
    async def test_enable_agent_for_tenant(self, client, admin_headers) -> None:
        """POST /admin/swarm/tenants/{id}/agents/{aid}/configure creates TenantAgentConfig."""
        agent_id = _unique_id("cfg_agent")
        try:
            # Create agent first
            await client.post(
                "/admin/swarm/agents",
                json={"id": agent_id, "display_name": "Config Agent"},
                headers=admin_headers,
            )

            # Configure for tenant
            resp = await client.post(
                f"/admin/swarm/tenants/1/agents/{agent_id}/configure",
                json={
                    "is_enabled": True,
                    "system_prompt_override": "Custom prompt for tenant",
                },
                headers=admin_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["is_enabled"] is True

            # Verify in DB
            db = SessionLocal()
            try:
                cfg = (
                    db.query(TenantAgentConfig)
                    .filter(
                        TenantAgentConfig.tenant_id == 1,
                        TenantAgentConfig.agent_id == agent_id,
                    )
                    .first()
                )
                assert cfg is not None
                assert cfg.is_enabled is True
                assert cfg.system_prompt_override == "Custom prompt for tenant"
            finally:
                db.close()
        finally:
            _cleanup_agent(agent_id)


class TestTenantToolConfig:
    @pytest.mark.anyio
    async def test_enable_tool_for_tenant_with_config(self, client, admin_headers) -> None:
        """POST /admin/swarm/tenants/{id}/tools/{tid}/configure stores tool config."""
        tool_id = _unique_id("cfg_tool")
        try:
            # Create tool first
            await client.post(
                "/admin/swarm/tools",
                json={"id": tool_id, "display_name": "Config Tool"},
                headers=admin_headers,
            )

            # Configure for tenant with custom config
            resp = await client.post(
                f"/admin/swarm/tenants/1/tools/{tool_id}/configure",
                json={
                    "is_enabled": True,
                    "config": {"api_key": "test-key-123", "timeout": 30},
                },
                headers=admin_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["is_enabled"] is True

            # Verify in DB
            db = SessionLocal()
            try:
                cfg = (
                    db.query(TenantToolConfig)
                    .filter(
                        TenantToolConfig.tenant_id == 1,
                        TenantToolConfig.tool_id == tool_id,
                    )
                    .first()
                )
                assert cfg is not None
                assert cfg.is_enabled is True
                config_data = json.loads(cfg.config)
                assert config_data["api_key"] == "test-key-123"
            finally:
                db.close()
        finally:
            _cleanup_tool(tool_id)


# ── Cache Invalidation Tests ────────────────────────────────────────────────


class TestCacheInvalidation:
    @pytest.mark.anyio
    async def test_cache_invalidation_on_update(self, client, admin_headers, mock_redis_bus) -> None:
        """PATCH agent publishes 'swarm:config:updated' to Redis."""
        agent_id = _unique_id("cache_agent")
        try:
            await client.post(
                "/admin/swarm/agents",
                json={"id": agent_id, "display_name": "Cache Agent"},
                headers=admin_headers,
            )
            mock_redis_bus.publish.reset_mock()

            await client.patch(
                f"/admin/swarm/agents/{agent_id}",
                json={"display_name": "Updated Cache Agent"},
                headers=admin_headers,
            )

            # Verify Redis publish was called with config update event
            mock_redis_bus.publish.assert_called()
            call_args = mock_redis_bus.publish.call_args
            assert call_args[0][0] == "swarm:config:updated"
            payload = json.loads(call_args[0][1])
            assert payload["event"] == "swarm:config:updated"
            assert f"agent_updated:{agent_id}" in payload["detail"]
        finally:
            _cleanup_agent(agent_id)

    @pytest.mark.anyio
    async def test_cache_invalidation_on_create(self, client, admin_headers, mock_redis_bus) -> None:
        """POST agent publishes config update event."""
        agent_id = _unique_id("cache_create")
        try:
            mock_redis_bus.publish.reset_mock()
            await client.post(
                "/admin/swarm/agents",
                json={"id": agent_id, "display_name": "New Agent"},
                headers=admin_headers,
            )
            mock_redis_bus.publish.assert_called()
            call_args = mock_redis_bus.publish.call_args
            payload = json.loads(call_args[0][1])
            assert f"agent_created:{agent_id}" in payload["detail"]
        finally:
            _cleanup_agent(agent_id)


# ── System Agent Protection Tests ────────────────────────────────────────────


class TestSystemAgentProtection:
    @pytest.mark.anyio
    async def test_delete_system_agent_forbidden(self, client, admin_headers) -> None:
        """DELETE on is_system=True agent returns 403."""
        agent_id = _unique_id("sys_agent")
        try:
            # Create system agent
            await client.post(
                "/admin/swarm/agents",
                json={"id": agent_id, "display_name": "System Agent", "is_system": True},
                headers=admin_headers,
            )

            resp = await client.delete(
                f"/admin/swarm/agents/{agent_id}",
                headers=admin_headers,
            )
            assert resp.status_code == 403
            assert "system" in resp.json()["detail"].lower()

            # Verify still in DB
            db = SessionLocal()
            try:
                agent = db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
                assert agent is not None
            finally:
                db.close()
        finally:
            # Force cleanup by setting is_system=False first
            db = SessionLocal()
            try:
                agent = db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
                if agent:
                    agent.is_system = False
                    db.commit()
            finally:
                db.close()
            _cleanup_agent(agent_id)

    @pytest.mark.anyio
    async def test_delete_system_tool_forbidden(self, client, admin_headers) -> None:
        """DELETE on is_system=True tool returns 403."""
        tool_id = _unique_id("sys_tool")
        try:
            await client.post(
                "/admin/swarm/tools",
                json={"id": tool_id, "display_name": "System Tool", "is_system": True},
                headers=admin_headers,
            )

            resp = await client.delete(
                f"/admin/swarm/tools/{tool_id}",
                headers=admin_headers,
            )
            assert resp.status_code == 403
        finally:
            db = SessionLocal()
            try:
                tool = db.query(ToolDefinition).filter(ToolDefinition.id == tool_id).first()
                if tool:
                    tool.is_system = False
                    db.commit()
            finally:
                db.close()
            _cleanup_tool(tool_id)

    @pytest.mark.anyio
    async def test_delete_non_system_agent_succeeds(self, client, admin_headers) -> None:
        """DELETE on non-system agent returns 204."""
        agent_id = _unique_id("del_agent")
        await client.post(
            "/admin/swarm/agents",
            json={"id": agent_id, "display_name": "Deletable Agent", "is_system": False},
            headers=admin_headers,
        )

        resp = await client.delete(
            f"/admin/swarm/agents/{agent_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 204

        # Verify removed from DB
        db = SessionLocal()
        try:
            agent = db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
            assert agent is None
        finally:
            db.close()


# ── RBAC Tests ───────────────────────────────────────────────────────────────


class TestRBAC:
    @pytest.mark.anyio
    async def test_tenant_admin_cannot_access_swarm_admin(self, client, tenant_admin_headers) -> None:
        """tenant_admin role cannot call /admin/swarm/* endpoints -> 403."""
        resp = await client.get("/admin/swarm/agents", headers=tenant_admin_headers)
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_tenant_admin_cannot_create_agent(self, client, tenant_admin_headers) -> None:
        """tenant_admin cannot create agents."""
        resp = await client.post(
            "/admin/swarm/agents",
            json={"id": "should_fail", "display_name": "Nope"},
            headers=tenant_admin_headers,
        )
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_invalid_token_rejected(self, client) -> None:
        """Invalid token -> 401."""
        resp = await client.get(
            "/admin/swarm/agents",
            headers={"Authorization": "Bearer invalid_garbage_token"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.anyio
    async def test_system_admin_can_list_agents(self, client, admin_headers) -> None:
        """system_admin can access /admin/swarm/agents."""
        resp = await client.get("/admin/swarm/agents", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.anyio
    async def test_system_admin_can_list_tools(self, client, admin_headers) -> None:
        """system_admin can access /admin/swarm/tools."""
        resp = await client.get("/admin/swarm/tools", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── Agent Update Tests ───────────────────────────────────────────────────────


class TestAgentUpdate:
    @pytest.mark.anyio
    async def test_patch_agent_updates_fields(self, client, admin_headers) -> None:
        """PATCH /admin/swarm/agents/{id} updates specified fields."""
        agent_id = _unique_id("patch_agent")
        try:
            await client.post(
                "/admin/swarm/agents",
                json={"id": agent_id, "display_name": "Original Name", "max_turns": 5},
                headers=admin_headers,
            )

            resp = await client.patch(
                f"/admin/swarm/agents/{agent_id}",
                json={"display_name": "Updated Name", "max_turns": 10},
                headers=admin_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["display_name"] == "Updated Name"
            assert data["max_turns"] == 10
        finally:
            _cleanup_agent(agent_id)

    @pytest.mark.anyio
    async def test_get_nonexistent_agent_404(self, client, admin_headers) -> None:
        """GET /admin/swarm/agents/{id} for missing agent returns 404."""
        resp = await client.get(
            "/admin/swarm/agents/nonexistent_agent_xyz",
            headers=admin_headers,
        )
        assert resp.status_code == 404
