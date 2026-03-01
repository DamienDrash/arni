"""ARIIA v2.0 – Base Integration Adapter.

@ARCH: Phase 2, Meilenstein 2.3 – Integration & Skills
Abstract base class for all integration adapters. Each concrete adapter
(MagiclineAdapter, ShopifyAdapter, etc.) inherits from this class and
implements the `execute_capability` method.

Design Principles:
  - Adapters are stateless; credentials come from TenantContext
  - Each adapter maps abstract capability IDs to concrete API calls
  - Results are always returned in a standardized format
  - Errors are caught and returned as structured error responses
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class AdapterResult:
    """Standardized result from an adapter capability execution.

    Every adapter method returns this, ensuring consistent handling
    by the agent runtime regardless of the underlying integration.
    """
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    execution_time_ms: float = 0.0

    def to_agent_response(self) -> str:
        """Convert to a human-readable string for the agent."""
        if self.success:
            if isinstance(self.data, str):
                return self.data
            elif isinstance(self.data, dict):
                return self._format_dict(self.data)
            elif isinstance(self.data, list):
                if not self.data:
                    return "Keine Ergebnisse gefunden."
                return "\n\n".join(
                    self._format_dict(item) if isinstance(item, dict) else str(item)
                    for item in self.data
                )
            return str(self.data) if self.data is not None else "Aktion erfolgreich ausgeführt."
        else:
            return f"Fehler: {self.error or 'Unbekannter Fehler'}"

    @staticmethod
    def _format_dict(d: dict) -> str:
        """Format a dictionary as a readable string."""
        lines = []
        for key, value in d.items():
            if value is not None and value != "":
                label = key.replace("_", " ").title()
                lines.append(f"- **{label}:** {value}")
        return "\n".join(lines) if lines else str(d)


class BaseAdapter(ABC):
    """Abstract base class for integration adapters.

    Subclasses must implement:
      - `execute_capability(capability_id, tenant_context, **kwargs) -> AdapterResult`
      - `supported_capabilities` property

    Usage:
        adapter = MagiclineAdapter()
        result = await adapter.execute_capability(
            "crm.customer.search",
            tenant_context,
            email="max@example.com"
        )
    """

    @property
    @abstractmethod
    def integration_id(self) -> str:
        """The unique integration ID (e.g., 'magicline')."""
        ...

    @property
    @abstractmethod
    def supported_capabilities(self) -> list[str]:
        """List of capability IDs this adapter supports."""
        ...

    async def execute_capability(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Execute a capability and return a standardized result.

        This method handles timing, logging, and error wrapping.
        Subclasses should override `_execute` for the actual logic.
        """
        if capability_id not in self.supported_capabilities:
            return AdapterResult(
                success=False,
                error=f"Capability '{capability_id}' is not supported by {self.integration_id}",
                error_code="UNSUPPORTED_CAPABILITY",
            )

        start = time.monotonic()
        try:
            result = await self._execute(capability_id, tenant_id, **kwargs)
            result.execution_time_ms = (time.monotonic() - start) * 1000
            logger.info(
                "adapter.capability_executed",
                adapter=self.integration_id,
                capability=capability_id,
                tenant_id=tenant_id,
                success=result.success,
                time_ms=round(result.execution_time_ms, 1),
            )
            return result
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error(
                "adapter.capability_error",
                adapter=self.integration_id,
                capability=capability_id,
                tenant_id=tenant_id,
                error=str(e),
                time_ms=round(elapsed, 1),
            )
            return AdapterResult(
                success=False,
                error=str(e),
                error_code="ADAPTER_ERROR",
                execution_time_ms=elapsed,
            )

    @abstractmethod
    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Internal execution logic. Override in subclasses.

        Args:
            capability_id: The capability to execute.
            tenant_id: The tenant ID for credential/context lookup.
            **kwargs: Capability-specific parameters.

        Returns:
            AdapterResult with the execution outcome.
        """
        ...

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Optional health check for the integration.

        Override in subclasses to implement integration-specific health checks.
        """
        return AdapterResult(success=True, data={"status": "ok", "adapter": self.integration_id})
