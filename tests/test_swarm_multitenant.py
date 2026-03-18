"""ARIIA Swarm v3 — Multi-Tenant Isolation Tests.

Verifies that swarm components (tool registry, confirmation gate,
agent configs, tenant context) enforce strict tenant isolation.
No data may leak across tenant boundaries.
"""

import json
import pytest
import fakeredis.aioredis

from app.swarm.contracts import AgentResult, TenantContext
from app.swarm.lead.confirmation_gate import ConfirmationGate
from app.swarm.tools.registry import (
    AGENT_TOOL_MAP,
    TOOL_CATALOGUE,
    TenantToolRegistry,
)
from app.swarm.tools.base import SkillTool, ToolResult
from typing import Any


# ── Test Fixtures ────────────────────────────────────────────────────────────


def _ctx(
    tenant_id: int,
    tenant_slug: str,
    plan_slug: str = "pro",
    active_integrations: frozenset[str] = frozenset(),
    member_id: str = "member-001",
    settings: dict | None = None,
) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        plan_slug=plan_slug,
        active_integrations=active_integrations,
        settings=settings or {},
        member_id=member_id,
    )


CTX_A = _ctx(tenant_id=100, tenant_slug="studio-alpha", active_integrations=frozenset({"magicline"}))
CTX_B = _ctx(tenant_id=200, tenant_slug="studio-beta", active_integrations=frozenset({"shopify"}))


# ── Dummy tools for testing ──────────────────────────────────────────────────


class _MagiclineTool(SkillTool):
    name = "mt_magicline_booking"
    description = "Magicline booking"
    parameters_schema = {"type": "object"}
    required_integrations = frozenset({"magicline"})
    min_plan_tier = "starter"
    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        return ToolResult(success=True, data=f"booking for tenant {context.tenant_id}")


class _ShopifyTool(SkillTool):
    name = "mt_shopify_orders"
    description = "Shopify orders"
    parameters_schema = {"type": "object"}
    required_integrations = frozenset({"shopify"})
    min_plan_tier = "starter"
    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        return ToolResult(success=True, data=f"orders for tenant {context.tenant_id}")


class _SharedTool(SkillTool):
    name = "mt_knowledge_search"
    description = "Knowledge search"
    parameters_schema = {"type": "object"}
    required_integrations = frozenset()
    min_plan_tier = "starter"
    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        return ToolResult(success=True, data=f"knowledge for tenant {context.tenant_id}")


@pytest.fixture(autouse=True)
def _register_mt_tools():
    saved_catalogue = dict(TOOL_CATALOGUE)
    saved_map = {k: list(v) for k, v in AGENT_TOOL_MAP.items()}

    TOOL_CATALOGUE["mt_magicline_booking"] = _MagiclineTool
    TOOL_CATALOGUE["mt_shopify_orders"] = _ShopifyTool
    TOOL_CATALOGUE["mt_knowledge_search"] = _SharedTool
    AGENT_TOOL_MAP["mt_ops"] = ["mt_magicline_booking", "mt_shopify_orders", "mt_knowledge_search"]

    yield

    TOOL_CATALOGUE.clear()
    TOOL_CATALOGUE.update(saved_catalogue)
    AGENT_TOOL_MAP.clear()
    AGENT_TOOL_MAP.update(saved_map)


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis()


# ── Tool Registry Isolation Tests ────────────────────────────────────────────


class TestToolRegistryIsolation:
    def test_tenant_a_cannot_use_tenant_b_tools(self) -> None:
        """Tenant A (magicline) cannot see Shopify tools; Tenant B (shopify) cannot see Magicline."""
        registry = TenantToolRegistry()

        tools_a = registry.get_tools_for_agent("mt_ops", CTX_A)
        tools_b = registry.get_tools_for_agent("mt_ops", CTX_B)

        names_a = {t.name for t in tools_a}
        names_b = {t.name for t in tools_b}

        # Tenant A has magicline, not shopify
        assert "mt_magicline_booking" in names_a
        assert "mt_shopify_orders" not in names_a

        # Tenant B has shopify, not magicline
        assert "mt_shopify_orders" in names_b
        assert "mt_magicline_booking" not in names_b

    def test_shared_tool_available_to_both(self) -> None:
        """Tools without required_integrations are available to both tenants."""
        registry = TenantToolRegistry()

        tools_a = registry.get_tools_for_agent("mt_ops", CTX_A)
        tools_b = registry.get_tools_for_agent("mt_ops", CTX_B)

        assert any(t.name == "mt_knowledge_search" for t in tools_a)
        assert any(t.name == "mt_knowledge_search" for t in tools_b)

    def test_tenant_tool_config_isolated(self) -> None:
        """TenantToolConfig for Tenant A does not affect Tenant B."""
        # Tenant A disables knowledge_search; Tenant B enables it
        registry_a = TenantToolRegistry(
            tenant_tool_configs={"mt_knowledge_search": {"is_enabled": False}}
        )
        registry_b = TenantToolRegistry(
            tenant_tool_configs={"mt_knowledge_search": {"is_enabled": True}}
        )

        tools_a = registry_a.get_tools_for_agent("mt_ops", CTX_A)
        tools_b = registry_b.get_tools_for_agent("mt_ops", CTX_B)

        assert not any(t.name == "mt_knowledge_search" for t in tools_a)
        assert any(t.name == "mt_knowledge_search" for t in tools_b)


# ── Tenant Prompt Override Isolation ─────────────────────────────────────────


class TestPromptOverrideIsolation:
    def test_tenant_prompt_override_isolated(self) -> None:
        """Tenant A's system_prompt_override in TenantAgentConfig must not affect Tenant B.

        This test verifies the data model supports isolation — each TenantAgentConfig
        row is scoped to (tenant_id, agent_id).
        """
        from app.core.db import SessionLocal
        from app.core.models import AgentDefinition, TenantAgentConfig

        db = SessionLocal()
        try:
            # Ensure a test agent exists
            agent = db.query(AgentDefinition).filter(AgentDefinition.id == "ops").first()
            if not agent:
                agent = AgentDefinition(id="ops", display_name="Ops Agent", min_plan_tier="starter")
                db.add(agent)
                db.commit()

            # Clean up any existing test configs
            db.query(TenantAgentConfig).filter(
                TenantAgentConfig.agent_id == "ops",
                TenantAgentConfig.tenant_id.in_([100, 200]),
            ).delete(synchronize_session=False)
            db.commit()

            # Set different overrides per tenant
            cfg_a = TenantAgentConfig(
                tenant_id=100, agent_id="ops", is_enabled=True,
                system_prompt_override="Du bist der Alpha-Studio Assistent",
            )
            cfg_b = TenantAgentConfig(
                tenant_id=200, agent_id="ops", is_enabled=True,
                system_prompt_override="Du bist der Beta-Studio Assistent",
            )
            db.add_all([cfg_a, cfg_b])
            db.commit()

            # Query back and verify isolation
            result_a = (
                db.query(TenantAgentConfig)
                .filter(TenantAgentConfig.tenant_id == 100, TenantAgentConfig.agent_id == "ops")
                .first()
            )
            result_b = (
                db.query(TenantAgentConfig)
                .filter(TenantAgentConfig.tenant_id == 200, TenantAgentConfig.agent_id == "ops")
                .first()
            )

            assert result_a.system_prompt_override == "Du bist der Alpha-Studio Assistent"
            assert result_b.system_prompt_override == "Du bist der Beta-Studio Assistent"
            assert result_a.system_prompt_override != result_b.system_prompt_override
        finally:
            # Cleanup
            db.query(TenantAgentConfig).filter(
                TenantAgentConfig.agent_id == "ops",
                TenantAgentConfig.tenant_id.in_([100, 200]),
            ).delete(synchronize_session=False)
            db.commit()
            db.close()


# ── Agent Enable Isolation ───────────────────────────────────────────────────


class TestAgentEnableIsolation:
    def test_tenant_agent_enable_isolated(self) -> None:
        """Enabling an agent for Tenant A does not enable it for Tenant B."""
        from app.core.db import SessionLocal
        from app.core.models import AgentDefinition, TenantAgentConfig

        db = SessionLocal()
        try:
            agent = db.query(AgentDefinition).filter(AgentDefinition.id == "ops").first()
            if not agent:
                agent = AgentDefinition(id="ops", display_name="Ops Agent", min_plan_tier="starter")
                db.add(agent)
                db.commit()

            db.query(TenantAgentConfig).filter(
                TenantAgentConfig.agent_id == "ops",
                TenantAgentConfig.tenant_id.in_([100, 200]),
            ).delete(synchronize_session=False)
            db.commit()

            # Enable for Tenant A, disable for Tenant B
            db.add(TenantAgentConfig(tenant_id=100, agent_id="ops", is_enabled=True))
            db.add(TenantAgentConfig(tenant_id=200, agent_id="ops", is_enabled=False))
            db.commit()

            cfg_a = db.query(TenantAgentConfig).filter(
                TenantAgentConfig.tenant_id == 100, TenantAgentConfig.agent_id == "ops"
            ).first()
            cfg_b = db.query(TenantAgentConfig).filter(
                TenantAgentConfig.tenant_id == 200, TenantAgentConfig.agent_id == "ops"
            ).first()

            assert cfg_a.is_enabled is True
            assert cfg_b.is_enabled is False
        finally:
            db.query(TenantAgentConfig).filter(
                TenantAgentConfig.agent_id == "ops",
                TenantAgentConfig.tenant_id.in_([100, 200]),
            ).delete(synchronize_session=False)
            db.commit()
            db.close()


# ── Confirmation Gate Isolation ──────────────────────────────────────────────


class TestConfirmationGateIsolation:
    @pytest.mark.anyio
    async def test_confirmation_gate_cross_tenant_isolated(self, redis_client) -> None:
        """Confirmation stored for Tenant A cannot be resolved by Tenant B."""
        gate = ConfirmationGate(redis_client)

        result = AgentResult(
            agent_id="ops",
            content="Stornieren?",
            requires_confirmation=True,
            confirmation_prompt="Wirklich stornieren?",
            confirmation_action='{"action": "cancel"}',
        )

        # Store for Tenant A
        token = await gate.store(result, CTX_A)

        # Tenant B cannot check it
        pending_b = await gate.check(CTX_B)
        assert pending_b is None

        # Tenant B cannot resolve it
        resolved_b = await gate.resolve(token, user_confirmed=True, context=CTX_B)
        assert "abgelaufen" in resolved_b.content.lower()

        # Tenant A can still check it
        pending_a = await gate.check(CTX_A)
        assert pending_a is not None
        assert pending_a.token == token

    @pytest.mark.anyio
    async def test_same_member_different_tenant_isolated(self, redis_client) -> None:
        """Same member_id but different tenant_id are isolated."""
        gate = ConfirmationGate(redis_client)

        ctx_a = _ctx(tenant_id=100, tenant_slug="alpha", member_id="shared-member")
        ctx_b = _ctx(tenant_id=200, tenant_slug="beta", member_id="shared-member")

        result = AgentResult(
            agent_id="sales",
            content="Kündigen?",
            requires_confirmation=True,
            confirmation_action='{"action": "terminate"}',
        )

        await gate.store(result, ctx_a)

        # Same member_id in different tenant => no access
        pending_b = await gate.check(ctx_b)
        assert pending_b is None


# ── TenantContext Immutability ───────────────────────────────────────────────


class TestTenantContextImmutable:
    def test_tenant_context_frozen(self) -> None:
        """TenantContext(frozen=True) prevents mutation."""
        ctx = CTX_A
        with pytest.raises(AttributeError):
            ctx.tenant_id = 999  # type: ignore
        with pytest.raises(AttributeError):
            ctx.tenant_slug = "hacked"  # type: ignore
        with pytest.raises(AttributeError):
            ctx.plan_slug = "enterprise"  # type: ignore

    def test_tenant_context_different_instances(self) -> None:
        """Two different tenant contexts are distinct objects."""
        assert CTX_A.tenant_id != CTX_B.tenant_id
        assert CTX_A.tenant_slug != CTX_B.tenant_slug
        assert CTX_A is not CTX_B
