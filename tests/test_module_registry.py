"""Epic 3 regression tests for capability resolution and router gating."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.feature_gates import FeatureGate
from app.core.module_registry import Capability, ModuleDefinition, ModuleRegistry


def _build_gate(
    *,
    plan_data: dict[str, object] | None = None,
    addon_slugs: set[str] | None = None,
) -> FeatureGate:
    gate = FeatureGate.__new__(FeatureGate)
    gate._tenant_id = 1
    gate._plan_data = plan_data or {}
    gate._addon_slugs = addon_slugs or set()
    return gate


def test_module_registry_runtime_activation_excludes_dormant_modules() -> None:
    registry = ModuleRegistry()
    registry.register(ModuleDefinition(
        name="support_core",
        description="active",
        required_capabilities=[Capability.SUPPORT_CORE],
    ))
    registry.register(ModuleDefinition(
        name="voice_pipeline",
        description="dormant",
        required_capabilities=[Capability.VOICE_PIPELINE],
    ))

    assert [module.name for module in registry.get_active_modules()] == ["support_core"]
    assert [module.name for module in registry.get_inactive_modules()] == ["voice_pipeline"]


def test_module_registry_filters_modules_for_tenant_capabilities() -> None:
    registry = ModuleRegistry()
    registry.register(ModuleDefinition(
        name="support_core",
        description="base module",
        required_capabilities=[Capability.SUPPORT_CORE],
    ))
    registry.register(ModuleDefinition(
        name="telegram",
        description="integration module",
        required_capabilities=[Capability.INTEGRATION_TELEGRAM],
    ))

    active = registry.get_active_modules({Capability.SUPPORT_CORE})
    assert [module.name for module in active] == ["support_core"]


def test_feature_gate_resolves_technical_capabilities_from_plan_and_addons() -> None:
    gate = _build_gate(
        plan_data={
            "ai_tier": "premium",
            "telegram_enabled": True,
            "max_channels": 2,
            "brand_style_enabled": False,
        },
        addon_slugs={"vision_ai"},
    )

    capabilities = gate.get_capabilities()

    assert Capability.SUPPORT_CORE in capabilities
    assert Capability.SUPPORT_L2 in capabilities
    assert Capability.CAMPAIGNS_OPT_IN in capabilities
    assert Capability.INTEGRATION_TELEGRAM in capabilities
    assert Capability.VISION_AI in capabilities
    assert Capability.MULTI_CHANNEL_ROUTING in capabilities
    assert Capability.BRAND_STYLE not in capabilities


def test_feature_gate_require_capability_rejects_missing_capability() -> None:
    gate = _build_gate(plan_data={"telegram_enabled": False, "ai_tier": "basic"})

    with pytest.raises(HTTPException) as exc:
        gate.require_capability(Capability.INTEGRATION_TELEGRAM)

    assert exc.value.status_code == 402
    assert Capability.INTEGRATION_TELEGRAM.value in str(exc.value.detail)


@pytest.mark.anyio
async def test_health_app_lists_runtime_active_modules_only(client) -> None:
    response = await client.get("/health/app")

    assert response.status_code == 200
    data = response.json()
    assert "support_core" in data["active_modules"]
    assert "voice_pipeline" not in data["active_modules"]


@pytest.mark.anyio
async def test_health_integrations_splits_active_and_dormant_modules(client) -> None:
    response = await client.get("/health/integrations")

    assert response.status_code == 200
    data = response.json()
    assert "integration_magicline" in data["active_integrations"]
    assert "integration_whatsapp_qr" in data["active_integrations"]
    assert "voice_pipeline" not in data["dormant_integrations"]
