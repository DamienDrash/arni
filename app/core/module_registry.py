"""ARIIA – Capability & Module Registry (Epic 1/2).

Defines the central capability catalog and module definitions for the
Domain-Driven Modular Monolith refactoring. The HTTP edge and Worker runtimes
will use this registry to selectively activate features based on tenant entitlements.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

import structlog

logger = structlog.get_logger()


class Capability(str, enum.Enum):
    """The authoritative catalog of system capabilities (Product Core vs Dormant)."""

    # --- Active Product Core ---
    SUPPORT_CORE = "support_core"
    SUPPORT_L2 = "support_l2"
    CAMPAIGNS = "campaigns"
    CAMPAIGNS_OPT_IN = "campaigns_opt_in"
    KNOWLEDGE_BASE = "knowledge_base"

    # --- Active Integrations ---
    INTEGRATION_WHATSAPP_QR = "integration_whatsapp_qr"
    INTEGRATION_TELEGRAM = "integration_telegram"
    INTEGRATION_CALENDLY = "integration_calendly"
    INTEGRATION_MAGICLINE = "integration_magicline"

    # --- System / Foundation ---
    ADMIN_CONTROL_PLANE = "admin_control_plane"
    TENANT_MANAGEMENT = "tenant_management"
    IDENTITY_ACCESS = "identity_access"

    # --- Dormant / Sunset (Coming Soon) ---
    VOICE_PIPELINE = "voice_pipeline"
    VISION_AI = "vision_ai"
    CHURN_PREDICTION = "churn_prediction"
    ADVANCED_ANALYTICS = "advanced_analytics"
    BRAND_STYLE = "brand_style"
    MULTI_CHANNEL_ROUTING = "multi_channel_routing"


RUNTIME_ACTIVE_CAPABILITIES: frozenset[Capability] = frozenset({
    Capability.SUPPORT_CORE,
    Capability.SUPPORT_L2,
    Capability.CAMPAIGNS,
    Capability.CAMPAIGNS_OPT_IN,
    Capability.KNOWLEDGE_BASE,
    Capability.INTEGRATION_WHATSAPP_QR,
    Capability.INTEGRATION_TELEGRAM,
    Capability.INTEGRATION_CALENDLY,
    Capability.INTEGRATION_MAGICLINE,
    Capability.ADMIN_CONTROL_PLANE,
    Capability.TENANT_MANAGEMENT,
    Capability.IDENTITY_ACCESS,
})

DORMANT_CAPABILITIES: frozenset[Capability] = frozenset({
    Capability.VOICE_PIPELINE,
    Capability.VISION_AI,
    Capability.CHURN_PREDICTION,
    Capability.ADVANCED_ANALYTICS,
    Capability.BRAND_STYLE,
    Capability.MULTI_CHANNEL_ROUTING,
})


@dataclass(frozen=True)
class WorkerDefinition:
    """Declares a named worker boot target for the worker runtime."""

    name: str
    module_path: str
    class_name: str
    kind: str = "arq"

    def load_target(self) -> Any:
        from importlib import import_module

        module = import_module(self.module_path)
        return getattr(module, self.class_name)


@dataclass(frozen=True)
class ModuleDefinition:
    """Declares a Domain Module and its integration points.
    
    Modules only register their routers, workers, or handlers if the
    tenant (or global system) holds the required capabilities.
    """
    
    name: str
    description: str
    required_capabilities: list[Capability]
    
    # Lazy callables that return the actual objects (to avoid import side-effects)
    get_routers: Callable[[], list[Any]] = field(default=list)
    get_workers: Callable[[], list[WorkerDefinition]] = field(default=list)
    get_event_handlers: Callable[[], list[Any]] = field(default=list)
    get_health_checks: Callable[[], list[Any]] = field(default=list)

    def is_available_for(self, capabilities: Iterable[Capability]) -> bool:
        """Return whether all required capabilities are present."""
        capability_set = set(capabilities)
        return all(capability in capability_set for capability in self.required_capabilities)

    @property
    def is_active(self) -> bool:
        """Compatibility alias for runtime activation in the current deployment."""
        return self.is_available_for(RUNTIME_ACTIVE_CAPABILITIES)


class ModuleRegistry:
    """Central registry holding all defined modules.
    
    The Edge Runtime (app/edge/app.py) queries this to build the active API.
    """
    
    def __init__(self) -> None:
        self._modules: dict[str, ModuleDefinition] = {}

    def register(self, module: ModuleDefinition) -> None:
        """Register a new domain module."""
        if module.name in self._modules:
            logger.warning("module_registry.duplicate_registration", module=module.name)
        self._modules[module.name] = module
        logger.debug("module_registry.registered", module=module.name, active=module.is_active)

    def get_modules(self) -> list[ModuleDefinition]:
        """Return all registered modules in registration order."""
        return list(self._modules.values())

    def get_active_modules(
        self,
        capabilities: Iterable[Capability] | None = None,
    ) -> list[ModuleDefinition]:
        """Return modules available for the provided capabilities.

        When no capabilities are provided, this resolves against the deployment's
        active product-core footprint.
        """
        effective_capabilities = (
            set(RUNTIME_ACTIVE_CAPABILITIES)
            if capabilities is None
            else set(capabilities)
        )
        return [
            module
            for module in self._modules.values()
            if module.is_available_for(effective_capabilities)
        ]

    def get_inactive_modules(
        self,
        capabilities: Iterable[Capability] | None = None,
    ) -> list[ModuleDefinition]:
        """Return modules excluded for the provided capabilities."""
        active_names = {module.name for module in self.get_active_modules(capabilities)}
        return [
            module
            for module in self._modules.values()
            if module.name not in active_names
        ]

    def clear(self) -> None:
        """Reset the registry (mostly for testing)."""
        self._modules.clear()

# Global singleton registry
registry = ModuleRegistry()
