"""ARIIA – Capability & Module Registry (Epic 1/2).

Defines the central capability catalog and module definitions for the
Domain-Driven Modular Monolith refactoring. The HTTP edge and Worker runtimes
will use this registry to selectively activate features based on tenant entitlements.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable

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
    get_workers: Callable[[], list[Any]] = field(default=list)
    get_event_handlers: Callable[[], list[Any]] = field(default=list)
    get_health_checks: Callable[[], list[Any]] = field(default=list)
    
    @property
    def is_active(self) -> bool:
        """Determines if the module is globally active in the current deployment.
        
        A module is inactive if ANY of its required capabilities are in the dormant list.
        """
        # Define the truly dormant features based on Epic 1 Product Core definition
        dormant_caps = {
            Capability.VOICE_PIPELINE,
            Capability.VISION_AI,
            Capability.CHURN_PREDICTION,
            Capability.ADVANCED_ANALYTICS,
            Capability.BRAND_STYLE,
            Capability.MULTI_CHANNEL_ROUTING,
        }
        for cap in self.required_capabilities:
            if cap in dormant_caps:
                return False
        return True


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

    def get_active_modules(self) -> list[ModuleDefinition]:
        """Return only modules that are not dormant."""
        return [m for m in self._modules.values() if m.is_active]

    def clear(self) -> None:
        """Reset the registry (mostly for testing)."""
        self._modules.clear()

# Global singleton registry
registry = ModuleRegistry()
