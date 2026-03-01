"""ARIIA v2.0 – Adapter Registry.

@ARCH: Phase 2, Meilenstein 2.3 – Integration & Skills
       Sprint 1 – Messaging Core Adapter Registration
Dynamic adapter loading and registration. Maps integration IDs to
their adapter classes, supporting both static registration and
dynamic loading via fully-qualified class names.

Usage:
    registry = AdapterRegistry()
    adapter = registry.get_adapter("magicline")
    result = await adapter.execute_capability("crm.customer.search", tenant_id, email="test@test.de")
"""

from __future__ import annotations

import importlib
from typing import Optional

import structlog

from app.integrations.adapters.base import BaseAdapter

logger = structlog.get_logger()


class AdapterRegistry:
    """Registry for integration adapters.

    Provides both static registration (for built-in adapters) and
    dynamic loading (for plugin adapters via adapter_class path).
    """

    def __init__(self) -> None:
        self._adapters: dict[str, BaseAdapter] = {}
        self._register_builtin_adapters()

    def _register_builtin_adapters(self) -> None:
        """Register all built-in adapters."""
        # ─── Phase 2 Adapters (CRM & E-Commerce) ────────────────────────
        try:
            from app.integrations.adapters.magicline_adapter import MagiclineAdapter
            self.register(MagiclineAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="magicline", error=str(e))

        try:
            from app.integrations.adapters.shopify_adapter import ShopifyAdapter
            self.register(ShopifyAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="shopify", error=str(e))

        try:
            from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
            self.register(ManualCrmAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="manual_crm", error=str(e))

        # ─── Sprint 1 Adapters (Messaging Core) ─────────────────────────
        try:
            from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
            self.register(WhatsAppAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="whatsapp", error=str(e))

        try:
            from app.integrations.adapters.telegram_adapter import TelegramAdapter
            self.register(TelegramAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="telegram", error=str(e))

        try:
            from app.integrations.adapters.email_adapter import EmailAdapter
            self.register(EmailAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="email", error=str(e))

        try:
            from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
            self.register(SmsVoiceAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="sms_voice", error=str(e))

        # ─── Sprint 2 Adapters (Agent Tools & Knowledge) ───────────────────
        try:
            from app.integrations.adapters.knowledge_adapter import KnowledgeAdapter
            self.register(KnowledgeAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="knowledge", error=str(e))

        try:
            from app.integrations.adapters.member_memory_adapter import MemberMemoryAdapter
            self.register(MemberMemoryAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="member_memory", error=str(e))

        # ─── Sprint 3 Adapters (Payment & Billing) ─────────────────────────
        try:
            from app.integrations.adapters.stripe_adapter import StripeAdapter
            self.register(StripeAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="stripe", error=str(e))

        try:
            from app.integrations.adapters.paypal_adapter import PayPalAdapter
            self.register(PayPalAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="paypal", error=str(e))

        try:
            from app.integrations.adapters.mollie_adapter import MollieAdapter
            self.register(MollieAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="mollie", error=str(e))

        # ─── Sprint 4 Adapters (Scheduling & Booking) ──────────────────────
        try:
            from app.integrations.adapters.calendly_adapter import CalendlyAdapter
            self.register(CalendlyAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="calendly", error=str(e))

        try:
            from app.integrations.adapters.calcom_adapter import CalComAdapter
            self.register(CalComAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="calcom", error=str(e))

        try:
            from app.integrations.adapters.acuity_adapter import AcuityAdapter
            self.register(AcuityAdapter())
        except ImportError as e:
            logger.warning("adapter_registry.builtin_import_failed", adapter="acuity", error=str(e))

    def register(self, adapter: BaseAdapter) -> None:
        """Register an adapter instance."""
        self._adapters[adapter.integration_id] = adapter
        logger.debug("adapter_registry.registered", integration_id=adapter.integration_id)

    def get_adapter(self, integration_id: str) -> Optional[BaseAdapter]:
        """Get a registered adapter by integration ID."""
        return self._adapters.get(integration_id)

    def get_or_load_adapter(self, integration_id: str, adapter_class_path: Optional[str] = None) -> Optional[BaseAdapter]:
        """Get a registered adapter, or dynamically load one from a class path.

        Args:
            integration_id: The integration ID to look up.
            adapter_class_path: Fully-qualified class name (e.g., "app.integrations.adapters.magicline_adapter.MagiclineAdapter").

        Returns:
            The adapter instance, or None if not found/loadable.
        """
        # Check static registry first
        adapter = self._adapters.get(integration_id)
        if adapter:
            return adapter

        # Try dynamic loading
        if adapter_class_path:
            try:
                adapter = self._load_adapter_class(adapter_class_path)
                if adapter:
                    self._adapters[integration_id] = adapter
                    logger.info("adapter_registry.dynamic_loaded", integration_id=integration_id, class_path=adapter_class_path)
                    return adapter
            except Exception as e:
                logger.error("adapter_registry.dynamic_load_failed", integration_id=integration_id, class_path=adapter_class_path, error=str(e))

        return None

    @staticmethod
    def _load_adapter_class(class_path: str) -> Optional[BaseAdapter]:
        """Dynamically load an adapter class from a fully-qualified path."""
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
            if not issubclass(adapter_class, BaseAdapter):
                logger.error("adapter_registry.not_base_adapter", class_path=class_path)
                return None
            return adapter_class()
        except (ImportError, AttributeError, ValueError) as e:
            logger.error("adapter_registry.import_failed", class_path=class_path, error=str(e))
            return None

    @property
    def registered_adapters(self) -> dict[str, str]:
        """Return a dict of integration_id → adapter class name."""
        return {k: type(v).__name__ for k, v in self._adapters.items()}

    def get_adapters_by_category(self, category: str) -> dict[str, BaseAdapter]:
        """Return all adapters matching a capability category prefix.

        Args:
            category: Capability prefix (e.g., 'messaging', 'crm', 'voice').

        Returns:
            Dict of integration_id → adapter for adapters with matching capabilities.
        """
        result = {}
        for integration_id, adapter in self._adapters.items():
            for cap in adapter.supported_capabilities:
                if cap.startswith(category):
                    result[integration_id] = adapter
                    break
        return result

    def __contains__(self, integration_id: str) -> bool:
        return integration_id in self._adapters

    def __len__(self) -> int:
        return len(self._adapters)


# Singleton instance
_adapter_registry: Optional[AdapterRegistry] = None


def get_adapter_registry() -> AdapterRegistry:
    """Get the global adapter registry singleton."""
    global _adapter_registry
    if _adapter_registry is None:
        _adapter_registry = AdapterRegistry()
    return _adapter_registry
