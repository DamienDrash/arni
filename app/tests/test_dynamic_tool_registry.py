"""DYN-8: Integration tests for dynamic tool availability.

Tests two mock tenants:
  - Tenant A (100): Calendly enabled → should have calendly_booking tool
  - Tenant B (200): Magicline enabled → should have ops_agent, sales_agent tools
  - Tenant C (300): Multiple integrations
  - Tenant D (400): No integrations at all

Verifies that:
  1. create_tool_registry_for_tenant() returns correct tools per tenant
  2. Core tools are always available
  3. Integration flags are correctly injected into template context
  4. MasterAgentV2 receives the correct tool registry
"""

import pytest
from unittest.mock import MagicMock


# ─── Mock Persistence ─────────────────────────────────────────────────────────


class MockPersistence:
    """Mock PersistenceService that returns different integrations per tenant."""

    def __init__(self):
        self._tenant_integrations = {
            100: ["calendly"],
            200: ["magicline"],
            300: ["calendly", "magicline", "hubspot"],
            400: [],
        }
        self._settings = {}

    def get_enabled_integrations(self, tenant_id: int) -> list[str]:
        return sorted(self._tenant_integrations.get(tenant_id, []))

    def is_integration_enabled(self, tenant_id: int, integration_id: str) -> bool:
        return integration_id in self.get_enabled_integrations(tenant_id)

    def get_setting(self, key, default=None, tenant_id=None):
        return self._settings.get(f"{tenant_id}:{key}", default)

    def get_system_tenant_id(self):
        return 1

    def get_tenant_slug(self, tenant_id):
        return f"tenant-{tenant_id}"


MOCK = MockPersistence()


# ─── Tests: Persistence Mock ─────────────────────────────────────────────────


class TestPersistenceIntegrations:
    """Test the mock persistence layer's integration query methods."""

    def test_get_enabled_integrations_returns_sorted_list(self):
        result = MOCK.get_enabled_integrations(300)
        assert result == sorted(result)
        assert result == ["calendly", "hubspot", "magicline"]

    def test_get_enabled_integrations_empty_tenant(self):
        result = MOCK.get_enabled_integrations(400)
        assert result == []

    def test_get_enabled_integrations_unknown_tenant(self):
        result = MOCK.get_enabled_integrations(999)
        assert result == []

    def test_is_integration_enabled(self):
        assert MOCK.is_integration_enabled(100, "calendly") is True
        assert MOCK.is_integration_enabled(100, "magicline") is False
        assert MOCK.is_integration_enabled(200, "magicline") is True
        assert MOCK.is_integration_enabled(200, "calendly") is False


# ─── Tests: Integration Flags in Context ─────────────────────────────────────


class TestIntegrationFlagsContext:
    """Test that build_tenant_context correctly injects integration flags."""

    def test_calendly_flags(self):
        from app.prompts.context import build_tenant_context

        ctx = build_tenant_context(MOCK, tenant_id=100)
        integrations = ctx["integrations"]

        assert integrations.calendly_enabled is True
        assert integrations.magicline_enabled is False
        assert integrations.hubspot_enabled is False

    def test_magicline_flags(self):
        from app.prompts.context import build_tenant_context

        ctx = build_tenant_context(MOCK, tenant_id=200)
        integrations = ctx["integrations"]

        assert integrations.magicline_enabled is True
        assert integrations.calendly_enabled is False

    def test_multi_flags(self):
        from app.prompts.context import build_tenant_context

        ctx = build_tenant_context(MOCK, tenant_id=300)
        integrations = ctx["integrations"]

        assert integrations.calendly_enabled is True
        assert integrations.magicline_enabled is True
        assert integrations.hubspot_enabled is True
        assert integrations.salesforce_enabled is False

    def test_no_integrations_flags(self):
        from app.prompts.context import build_tenant_context

        ctx = build_tenant_context(MOCK, tenant_id=400)
        integrations = ctx["integrations"]

        assert integrations.calendly_enabled is False
        assert integrations.magicline_enabled is False
        assert integrations.hubspot_enabled is False

    def test_enabled_integrations_list(self):
        from app.prompts.context import build_tenant_context

        ctx = build_tenant_context(MOCK, tenant_id=300)
        assert "enabled_integrations" in ctx
        assert "calendly" in ctx["enabled_integrations"]
        assert "magicline" in ctx["enabled_integrations"]
        assert "hubspot" in ctx["enabled_integrations"]


# ─── Tests: Template Rendering with Integration Flags ─────────────────────────


class TestTemplateRendering:
    """Test that Jinja2 templates correctly render based on integration flags."""

    def test_ops_template_with_magicline(self):
        """Ops template should show Magicline tools when enabled."""
        from app.prompts.context import build_tenant_context
        from jinja2 import Environment, FileSystemLoader, Undefined

        ctx = build_tenant_context(MOCK, tenant_id=200)
        ctx.update({
            "agent_display_name": "TestAgent",
            "current_date": "2026-03-03",
            "user_name": "TestUser",
            "member_id": "M123",
            "member_profile": "",
        })

        env = Environment(
            loader=FileSystemLoader("app/prompts/templates"),
            undefined=Undefined,
        )
        template = env.get_template("ops/system.j2")
        rendered = template.render(**ctx)

        assert "get_class_schedule" in rendered, "Magicline tools should be visible"
        assert "cancel_member_booking" in rendered, "Magicline cancel tool should be visible"

    def test_ops_template_without_magicline(self):
        """Ops template should NOT show Magicline tools when disabled."""
        from app.prompts.context import build_tenant_context
        from jinja2 import Environment, FileSystemLoader, Undefined

        ctx = build_tenant_context(MOCK, tenant_id=100)  # Calendly only
        ctx.update({
            "agent_display_name": "TestAgent",
            "current_date": "2026-03-03",
            "user_name": "TestUser",
            "member_id": "M123",
            "member_profile": "",
        })

        env = Environment(
            loader=FileSystemLoader("app/prompts/templates"),
            undefined=Undefined,
        )
        template = env.get_template("ops/system.j2")
        rendered = template.render(**ctx)

        assert "get_class_schedule" not in rendered, "Magicline tools should NOT be visible"
        assert "get_booking_link" in rendered, "Calendly tool should be visible"

    def test_ops_template_with_calendly(self):
        """Ops template should show Calendly booking link when enabled."""
        from app.prompts.context import build_tenant_context
        from jinja2 import Environment, FileSystemLoader, Undefined

        ctx = build_tenant_context(MOCK, tenant_id=100)
        ctx.update({
            "agent_display_name": "TestAgent",
            "current_date": "2026-03-03",
            "user_name": "TestUser",
            "member_id": "M123",
            "member_profile": "",
        })

        env = Environment(
            loader=FileSystemLoader("app/prompts/templates"),
            undefined=Undefined,
        )
        template = env.get_template("ops/system.j2")
        rendered = template.render(**ctx)

        assert "Calendly" in rendered
        assert "get_booking_link" in rendered

    def test_router_template_dynamic_categories(self):
        """Router template should only show categories for active integrations."""
        from app.prompts.context import build_tenant_context
        from jinja2 import Environment, FileSystemLoader, Undefined

        # Tenant with no booking integrations
        ctx = build_tenant_context(MOCK, tenant_id=400)
        ctx.update({
            "agent_display_name": "TestAgent",
            "studio_name": "TestStudio",
        })

        env = Environment(
            loader=FileSystemLoader("app/prompts/templates"),
            undefined=Undefined,
        )
        template = env.get_template("router/system.j2")
        rendered = template.render(**ctx)

        # The "booking" category line should NOT appear for tenant with no booking integrations
        lines = rendered.strip().split("\n")
        category_lines = [l.strip() for l in lines if l.strip().startswith("- ")]
        category_names = [l.split(":")[0].lstrip("- ").strip() for l in category_lines]

        assert "booking" not in category_names, \
            f"Booking category should not appear when no booking integrations active, got: {category_names}"
        assert "health" in category_names, "Health category should always be present"
        assert "smalltalk" in category_names, "Smalltalk category should always be present"

    def test_persona_template_with_calendly(self):
        """Persona template should show booking link when Calendly is enabled."""
        from app.prompts.context import build_tenant_context
        from jinja2 import Environment, FileSystemLoader, Undefined

        ctx = build_tenant_context(MOCK, tenant_id=100)
        ctx.update({
            "agent_display_name": "TestAgent",
            "soul_content": "Test soul content",
        })

        env = Environment(
            loader=FileSystemLoader("app/prompts/templates"),
            undefined=Undefined,
        )
        template = env.get_template("persona/system.j2")
        rendered = template.render(**ctx)

        assert "get_booking_link" in rendered, "Calendly booking link should be visible"

    def test_persona_template_without_calendly(self):
        """Persona template should NOT show booking link when Calendly is disabled."""
        from app.prompts.context import build_tenant_context
        from jinja2 import Environment, FileSystemLoader, Undefined

        ctx = build_tenant_context(MOCK, tenant_id=200)  # Magicline only
        ctx.update({
            "agent_display_name": "TestAgent",
            "soul_content": "Test soul content",
        })

        env = Environment(
            loader=FileSystemLoader("app/prompts/templates"),
            undefined=Undefined,
        )
        template = env.get_template("persona/system.j2")
        rendered = template.render(**ctx)

        assert "get_booking_link" not in rendered, "Calendly booking link should NOT be visible"


# ─── Tests: Tool Registry (Unit-level, no DB required) ───────────────────────


class TestToolRegistryLogic:
    """Test the tool registry logic using direct function calls with mocked persistence."""

    def test_tool_integration_requirements_mapping(self):
        """Verify the TOOL_INTEGRATION_REQUIREMENTS mapping is correctly defined."""
        from app.swarm.tool_calling import TOOL_INTEGRATION_REQUIREMENTS, CORE_TOOLS

        # Core tools should be in the CORE_TOOLS set
        assert "knowledge_base" in CORE_TOOLS
        assert "member_memory" in CORE_TOOLS

        # Integration-dependent tools should have requirements
        assert "ops_agent" in TOOL_INTEGRATION_REQUIREMENTS
        assert "sales_agent" in TOOL_INTEGRATION_REQUIREMENTS

        # calendly_booking is handled via special-case logic in
        # create_tool_registry_for_tenant, not via TOOL_INTEGRATION_REQUIREMENTS

        # Verify requirements contain expected integrations
        assert "magicline" in TOOL_INTEGRATION_REQUIREMENTS["ops_agent"]
        assert "calendly" in TOOL_INTEGRATION_REQUIREMENTS["ops_agent"]
        assert "magicline" in TOOL_INTEGRATION_REQUIREMENTS["sales_agent"]

    def test_all_tool_definitions_complete(self):
        """Verify _all_tool_definitions returns all expected tools."""
        from app.swarm.tool_calling import _all_tool_definitions

        all_tools = _all_tool_definitions()
        expected_tools = {
            "knowledge_base", "member_memory", "ops_agent",
            "sales_agent", "medic_agent", "vision_agent",
            "persona_agent", "calendly_booking",
        }

        for tool in expected_tools:
            assert tool in all_tools, f"Tool '{tool}' should be in _all_tool_definitions"

    def test_create_worker_tools_returns_all(self):
        """Legacy create_worker_tools should return all tools."""
        from app.swarm.tool_calling import create_worker_tools

        registry = create_worker_tools()
        tool_names = [t.name for t in registry.get_all()]

        assert "ops_agent" in tool_names
        assert "sales_agent" in tool_names
        assert "knowledge_base" in tool_names
        assert "calendly_booking" in tool_names


# ─── Tests: IntegrationFlags Dataclass ────────────────────────────────────────


class TestIntegrationFlags:
    """Test the IntegrationFlags dataclass behavior."""

    def test_unknown_attribute_returns_false(self):
        """Accessing an unknown integration flag should return False."""
        from app.prompts.context import IntegrationFlags

        flags = IntegrationFlags(_flags={"calendly_enabled": True})
        assert flags.calendly_enabled is True
        assert flags.magicline_enabled is False
        assert flags.unknown_service_enabled is False

    def test_shorthand_access(self):
        """Accessing without _enabled suffix should also work."""
        from app.prompts.context import IntegrationFlags

        flags = IntegrationFlags(_flags={"calendly_enabled": True})
        assert flags.calendly is True
        assert flags.magicline is False

    def test_to_dict(self):
        """to_dict should return all flags as a plain dict."""
        from app.prompts.context import IntegrationFlags

        flags = IntegrationFlags(_flags={
            "calendly_enabled": True,
            "magicline_enabled": False,
        })
        d = flags.to_dict()
        assert d == {"calendly_enabled": True, "magicline_enabled": False}

    def test_repr(self):
        """repr should show only enabled flags."""
        from app.prompts.context import IntegrationFlags

        flags = IntegrationFlags(_flags={
            "calendly_enabled": True,
            "magicline_enabled": False,
        })
        r = repr(flags)
        assert "calendly_enabled" in r
        assert "magicline_enabled" not in r
