"""ARIIA Swarm v3 — Unit Tests for TenantToolRegistry 3-Gate Permission System.

Tests all three permission gates (plan tier, integration availability,
tenant config) plus tool overrides and cross-tenant isolation.
"""

import pytest
from typing import Any

from app.swarm.contracts import TenantContext
from app.swarm.tools.base import SkillTool, ToolResult
from app.swarm.tools.registry import (
    PLAN_TIER,
    TOOL_CATALOGUE,
    AGENT_TOOL_MAP,
    TenantToolRegistry,
    register_tool,
)


# ── Test Fixtures ────────────────────────────────────────────────────────────


def _make_context(
    tenant_id: int = 1,
    tenant_slug: str = "test-studio",
    plan_slug: str = "starter",
    active_integrations: frozenset[str] = frozenset(),
) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        plan_slug=plan_slug,
        active_integrations=active_integrations,
        settings={},
    )


class _DummyToolStarter(SkillTool):
    """Tool available on starter plan, no integrations required."""
    name = "test_starter_tool"
    description = "Test tool for starter"
    parameters_schema = {"type": "object", "properties": {}}
    required_integrations = frozenset()
    min_plan_tier = "starter"

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        return ToolResult(success=True, data="ok")


class _DummyToolPro(SkillTool):
    """Tool requiring pro plan."""
    name = "test_pro_tool"
    description = "Test tool for pro"
    parameters_schema = {"type": "object", "properties": {}}
    required_integrations = frozenset()
    min_plan_tier = "pro"

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        return ToolResult(success=True, data="ok")


class _DummyToolEnterprise(SkillTool):
    """Tool requiring enterprise plan."""
    name = "test_enterprise_tool"
    description = "Test tool for enterprise"
    parameters_schema = {"type": "object", "properties": {}}
    required_integrations = frozenset()
    min_plan_tier = "enterprise"

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        return ToolResult(success=True, data="ok")


class _DummyToolMagicline(SkillTool):
    """Tool requiring magicline integration."""
    name = "test_magicline_tool"
    description = "Test tool requiring magicline"
    parameters_schema = {"type": "object", "properties": {}}
    required_integrations = frozenset({"magicline"})
    min_plan_tier = "starter"

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        return ToolResult(success=True, data="ok")


class _DummyToolCalendly(SkillTool):
    """Tool requiring calendly integration."""
    name = "test_calendly_tool"
    description = "Test tool requiring calendly"
    parameters_schema = {"type": "object", "properties": {}}
    required_integrations = frozenset({"calendly"})
    min_plan_tier = "starter"

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        return ToolResult(success=True, data="ok")


class _DummyToolAllGates(SkillTool):
    """Tool requiring pro plan AND magicline integration."""
    name = "test_all_gates_tool"
    description = "Test tool needing all gates"
    parameters_schema = {"type": "object", "properties": {}}
    required_integrations = frozenset({"magicline"})
    min_plan_tier = "pro"

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        return ToolResult(success=True, data="ok")


@pytest.fixture(autouse=True)
def _register_test_tools():
    """Register test tools in catalogue and clean up after each test."""
    saved = dict(TOOL_CATALOGUE)
    saved_agent_map = {k: list(v) for k, v in AGENT_TOOL_MAP.items()}

    TOOL_CATALOGUE["test_starter_tool"] = _DummyToolStarter
    TOOL_CATALOGUE["test_pro_tool"] = _DummyToolPro
    TOOL_CATALOGUE["test_enterprise_tool"] = _DummyToolEnterprise
    TOOL_CATALOGUE["test_magicline_tool"] = _DummyToolMagicline
    TOOL_CATALOGUE["test_calendly_tool"] = _DummyToolCalendly
    TOOL_CATALOGUE["test_all_gates_tool"] = _DummyToolAllGates

    AGENT_TOOL_MAP["test_agent"] = [
        "test_starter_tool",
        "test_pro_tool",
        "test_enterprise_tool",
        "test_magicline_tool",
        "test_calendly_tool",
        "test_all_gates_tool",
    ]

    yield

    TOOL_CATALOGUE.clear()
    TOOL_CATALOGUE.update(saved)
    AGENT_TOOL_MAP.clear()
    AGENT_TOOL_MAP.update(saved_agent_map)


# ── Gate 1: Plan Tier Tests ──────────────────────────────────────────────────


class TestGate1PlanTier:
    def test_plan_blocks_higher_tier_tool(self) -> None:
        """Starter tenant cannot access pro tool."""
        ctx = _make_context(plan_slug="starter")
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_pro_tool" not in tool_names

    def test_plan_allows_matching_tier_tool(self) -> None:
        """Pro tenant can access pro tool."""
        ctx = _make_context(plan_slug="pro", active_integrations=frozenset({"magicline"}))
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_pro_tool" in tool_names

    def test_plan_allows_lower_tier_tool(self) -> None:
        """Enterprise tenant can access starter tool."""
        ctx = _make_context(plan_slug="enterprise", active_integrations=frozenset({"magicline", "calendly"}))
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_starter_tool" in tool_names

    def test_starter_blocks_enterprise_tool(self) -> None:
        """Starter tenant cannot access enterprise tool."""
        ctx = _make_context(plan_slug="starter")
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_enterprise_tool" not in tool_names

    def test_enterprise_allows_all_plan_tiers(self) -> None:
        """Enterprise tenant can access starter, pro, and enterprise tools."""
        ctx = _make_context(
            plan_slug="enterprise",
            active_integrations=frozenset({"magicline", "calendly"}),
        )
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_starter_tool" in tool_names
        assert "test_pro_tool" in tool_names
        assert "test_enterprise_tool" in tool_names


# ── Gate 2: Integration Availability Tests ───────────────────────────────────


class TestGate2Integration:
    def test_integration_blocks_when_missing(self) -> None:
        """Tool requiring magicline blocked when tenant only has calendly."""
        ctx = _make_context(plan_slug="enterprise", active_integrations=frozenset({"calendly"}))
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_magicline_tool" not in tool_names

    def test_integration_allows_when_present(self) -> None:
        """Tool requiring magicline passes when tenant has magicline."""
        ctx = _make_context(plan_slug="enterprise", active_integrations=frozenset({"magicline"}))
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_magicline_tool" in tool_names

    def test_no_integration_required_always_passes(self) -> None:
        """Tool with no required_integrations is not blocked by Gate 2."""
        ctx = _make_context(plan_slug="starter", active_integrations=frozenset())
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_starter_tool" in tool_names


# ── Gate 3: Tenant Config (enable/disable) Tests ────────────────────────────


class TestGate3TenantConfig:
    def test_disabled_tool_not_in_list(self) -> None:
        """Tool explicitly disabled in tenant config is excluded."""
        ctx = _make_context(plan_slug="starter")
        registry = TenantToolRegistry(
            tenant_tool_configs={"test_starter_tool": {"is_enabled": False}}
        )
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_starter_tool" not in tool_names

    def test_enabled_tool_in_list(self) -> None:
        """Tool explicitly enabled in tenant config is included."""
        ctx = _make_context(plan_slug="starter")
        registry = TenantToolRegistry(
            tenant_tool_configs={"test_starter_tool": {"is_enabled": True}}
        )
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_starter_tool" in tool_names

    def test_no_config_defaults_to_enabled(self) -> None:
        """Tool with no tenant config entry defaults to enabled."""
        ctx = _make_context(plan_slug="starter")
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_starter_tool" in tool_names


# ── All Gates Must Pass ──────────────────────────────────────────────────────


class TestAllGatesMustPass:
    def test_all_gates_pass(self) -> None:
        """Tool passes when plan, integration, and config all satisfied."""
        ctx = _make_context(plan_slug="pro", active_integrations=frozenset({"magicline"}))
        registry = TenantToolRegistry(
            tenant_tool_configs={"test_all_gates_tool": {"is_enabled": True}}
        )
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_all_gates_tool" in tool_names

    def test_gate1_blocks_even_when_others_pass(self) -> None:
        """Tool blocked by plan tier even if integration + config pass."""
        ctx = _make_context(plan_slug="starter", active_integrations=frozenset({"magicline"}))
        registry = TenantToolRegistry(
            tenant_tool_configs={"test_all_gates_tool": {"is_enabled": True}}
        )
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_all_gates_tool" not in tool_names

    def test_gate2_blocks_even_when_others_pass(self) -> None:
        """Tool blocked by missing integration even if plan + config pass."""
        ctx = _make_context(plan_slug="pro", active_integrations=frozenset())
        registry = TenantToolRegistry(
            tenant_tool_configs={"test_all_gates_tool": {"is_enabled": True}}
        )
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_all_gates_tool" not in tool_names

    def test_gate3_blocks_even_when_others_pass(self) -> None:
        """Tool blocked by tenant config even if plan + integration pass."""
        ctx = _make_context(plan_slug="pro", active_integrations=frozenset({"magicline"}))
        registry = TenantToolRegistry(
            tenant_tool_configs={"test_all_gates_tool": {"is_enabled": False}}
        )
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]
        assert "test_all_gates_tool" not in tool_names


# ── Tool Overrides ───────────────────────────────────────────────────────────


class TestToolOverrides:
    def test_override_add_extra_tool(self) -> None:
        """Override list can include tools not in default AGENT_TOOL_MAP."""
        ctx = _make_context(plan_slug="starter")
        registry = TenantToolRegistry()
        # Use override to give only test_starter_tool (not the default list)
        tools = registry.get_tools_for_agent(
            "some_other_agent", ctx, tool_overrides=["test_starter_tool"]
        )
        assert len(tools) == 1
        assert tools[0].name == "test_starter_tool"

    def test_override_remove_default_tool(self) -> None:
        """Override list replaces defaults, so default tools not in override are absent."""
        ctx = _make_context(plan_slug="enterprise", active_integrations=frozenset({"magicline", "calendly"}))
        registry = TenantToolRegistry()
        # Override with only starter tool (removing all others from test_agent defaults)
        tools = registry.get_tools_for_agent(
            "test_agent", ctx, tool_overrides=["test_starter_tool"]
        )
        assert len(tools) == 1
        assert tools[0].name == "test_starter_tool"

    def test_override_empty_list_gives_no_tools(self) -> None:
        """Empty override list results in no tools."""
        ctx = _make_context(plan_slug="enterprise", active_integrations=frozenset({"magicline", "calendly"}))
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("test_agent", ctx, tool_overrides=[])
        assert tools == []


# ── Cross-Tenant Isolation ───────────────────────────────────────────────────


class TestCrossTenantIsolation:
    def test_no_cross_tenant_tool_leak(self) -> None:
        """Tools configured for Tenant A must not appear for Tenant B."""
        ctx_a = _make_context(tenant_id=1, tenant_slug="studio-a", plan_slug="pro",
                              active_integrations=frozenset({"magicline"}))
        ctx_b = _make_context(tenant_id=2, tenant_slug="studio-b", plan_slug="starter",
                              active_integrations=frozenset())

        # Tenant A has the all_gates_tool enabled; Tenant B has it disabled
        registry_a = TenantToolRegistry(
            tenant_tool_configs={"test_all_gates_tool": {"is_enabled": True}}
        )
        registry_b = TenantToolRegistry(
            tenant_tool_configs={"test_all_gates_tool": {"is_enabled": False}}
        )

        tools_a = registry_a.get_tools_for_agent("test_agent", ctx_a)
        tools_b = registry_b.get_tools_for_agent("test_agent", ctx_b)

        tool_names_a = [t.name for t in tools_a]
        tool_names_b = [t.name for t in tools_b]

        assert "test_all_gates_tool" in tool_names_a
        assert "test_all_gates_tool" not in tool_names_b

    def test_different_plans_different_tools(self) -> None:
        """Two tenants on different plans see different tool sets."""
        ctx_starter = _make_context(tenant_id=1, tenant_slug="basic-studio", plan_slug="starter")
        ctx_enterprise = _make_context(
            tenant_id=2, tenant_slug="premium-studio", plan_slug="enterprise",
            active_integrations=frozenset({"magicline", "calendly"}),
        )

        registry = TenantToolRegistry()
        tools_starter = registry.get_tools_for_agent("test_agent", ctx_starter)
        tools_enterprise = registry.get_tools_for_agent("test_agent", ctx_enterprise)

        starter_names = {t.name for t in tools_starter}
        enterprise_names = {t.name for t in tools_enterprise}

        # Starter can only see starter-tier, no-integration tools
        assert "test_starter_tool" in starter_names
        assert "test_pro_tool" not in starter_names
        assert "test_enterprise_tool" not in starter_names

        # Enterprise sees everything
        assert "test_starter_tool" in enterprise_names
        assert "test_pro_tool" in enterprise_names
        assert "test_enterprise_tool" in enterprise_names


# ── Misc / Edge Cases ────────────────────────────────────────────────────────


class TestRegistryEdgeCases:
    def test_unknown_agent_returns_empty(self) -> None:
        """Agent not in AGENT_TOOL_MAP gets empty tool list."""
        ctx = _make_context(plan_slug="enterprise")
        registry = TenantToolRegistry()
        tools = registry.get_tools_for_agent("nonexistent_agent", ctx)
        assert tools == []

    def test_tool_not_in_catalogue_skipped(self) -> None:
        """Tool ID in map but not in TOOL_CATALOGUE is silently skipped."""
        AGENT_TOOL_MAP["ghost_agent"] = ["ghost_tool_that_does_not_exist"]
        try:
            ctx = _make_context(plan_slug="enterprise")
            registry = TenantToolRegistry()
            tools = registry.get_tools_for_agent("ghost_agent", ctx)
            assert tools == []
        finally:
            del AGENT_TOOL_MAP["ghost_agent"]

    def test_register_tool_decorator(self) -> None:
        """register_tool() adds class to TOOL_CATALOGUE."""
        class _TempTool(SkillTool):
            name = "temp_registered_tool"
            description = "temp"
            parameters_schema = {}
            async def execute(self, params, context):
                return ToolResult(success=True)

        register_tool(_TempTool)
        assert "temp_registered_tool" in TOOL_CATALOGUE
        assert TOOL_CATALOGUE["temp_registered_tool"] is _TempTool
        del TOOL_CATALOGUE["temp_registered_tool"]

    def test_get_openai_schemas(self) -> None:
        """get_openai_schemas returns valid OpenAI function schemas."""
        ctx = _make_context(plan_slug="starter")
        registry = TenantToolRegistry()
        schemas = registry.get_openai_schemas("test_agent", ctx)
        assert len(schemas) >= 1
        for schema in schemas:
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]

    def test_from_db_rows(self) -> None:
        """from_db_rows() constructs registry from ORM-like objects."""
        class FakeRow:
            def __init__(self, tool_id, is_enabled, config=None):
                self.tool_id = tool_id
                self.is_enabled = is_enabled
                self.config = config

        rows = [
            FakeRow("test_starter_tool", True, '{"key": "val"}'),
            FakeRow("test_pro_tool", False, None),
        ]
        registry = TenantToolRegistry.from_db_rows(rows)

        ctx = _make_context(plan_slug="pro", active_integrations=frozenset({"magicline"}))
        tools = registry.get_tools_for_agent("test_agent", ctx)
        tool_names = [t.name for t in tools]

        assert "test_starter_tool" in tool_names
        assert "test_pro_tool" not in tool_names  # disabled by config
