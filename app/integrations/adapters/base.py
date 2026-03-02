"""ARIIA v2.0 – Base Integration Adapter.

@ARCH: Contacts-Sync Refactoring
Abstract base class for all integration adapters. Each concrete adapter
(MagiclineAdapter, ShopifyAdapter, etc.) inherits from this class and
implements both capability execution AND contact sync methods.

Design Principles:
  - Adapters are stateless; credentials come from TenantContext / Vault
  - Each adapter maps abstract capability IDs to concrete API calls
  - Results are always returned in a standardized format
  - Errors are caught and returned as structured error responses
  - Contact sync is a first-class concern with dedicated abstract methods
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


# ─── Data Transfer Objects ───────────────────────────────────────────────────

class SyncDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class SyncMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


@dataclass
class NormalizedContact:
    """Standardized contact representation across all integrations.

    Every adapter's `get_contacts()` method must return a list of these.
    The `custom_fields` dict holds integration-specific data (e.g.,
    Magicline contract info, Shopify order data, etc.).
    """
    external_id: str
    source: str  # e.g., "magicline", "shopify"
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_zip: Optional[str] = None
    address_country: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    lifecycle_stage: Optional[str] = None
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    raw_data: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "external_id": self.external_id,
            "source": self.source,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "address_street": self.address_street,
            "address_city": self.address_city,
            "address_zip": self.address_zip,
            "address_country": self.address_country,
            "date_of_birth": self.date_of_birth,
            "gender": self.gender,
            "tags": self.tags,
            "lifecycle_stage": self.lifecycle_stage,
            "custom_fields": self.custom_fields,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class SyncResult:
    """Result of a contact sync operation."""
    success: bool
    records_fetched: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_deleted: int = 0
    records_unchanged: int = 0
    records_failed: int = 0
    contacts: List[NormalizedContact] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


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


@dataclass
class ConnectionTestResult:
    """Result of a connection test."""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0


# ─── Base Adapter ────────────────────────────────────────────────────────────

class BaseAdapter(ABC):
    """Abstract base class for integration adapters.

    Subclasses must implement:
      - `execute_capability(...)` for agent/capability execution
      - `get_contacts(...)` for contact sync
      - `test_connection(...)` for connection validation
      - `get_config_schema()` for dynamic config form generation

    Usage:
        adapter = MagiclineAdapter()
        result = await adapter.get_contacts(tenant_id=1, config={...})
        test = await adapter.test_connection(config={...})
    """

    @property
    @abstractmethod
    def integration_id(self) -> str:
        """The unique integration ID (e.g., 'magicline')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g., 'Magicline')."""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """Integration category (e.g., 'fitness', 'ecommerce')."""
        ...

    @property
    @abstractmethod
    def supported_capabilities(self) -> list[str]:
        """List of capability IDs this adapter supports."""
        ...

    @property
    def supported_sync_directions(self) -> list[SyncDirection]:
        """Sync directions supported by this adapter."""
        return [SyncDirection.INBOUND]

    @property
    def supports_incremental_sync(self) -> bool:
        """Whether this adapter supports incremental (delta) sync."""
        return False

    @property
    def supports_webhooks(self) -> bool:
        """Whether this adapter supports webhook-based real-time sync."""
        return False

    # ── Contact Sync Methods ─────────────────────────────────────────────

    @abstractmethod
    async def get_contacts(
        self,
        tenant_id: int,
        config: Dict[str, Any],
        last_sync_at: Optional[datetime] = None,
        sync_mode: SyncMode = SyncMode.FULL,
    ) -> SyncResult:
        """Fetch contacts from the external system.

        Args:
            tenant_id: The tenant performing the sync.
            config: Decrypted integration configuration.
            last_sync_at: Timestamp of last successful sync (for incremental).
            sync_mode: FULL or INCREMENTAL.

        Returns:
            SyncResult with normalized contacts and statistics.
        """
        ...

    @abstractmethod
    async def test_connection(
        self,
        config: Dict[str, Any],
    ) -> ConnectionTestResult:
        """Test whether the provided configuration is valid.

        This should make a lightweight API call to verify credentials
        without fetching large amounts of data.

        Args:
            config: The integration configuration to test.

        Returns:
            ConnectionTestResult indicating success or failure.
        """
        ...

    @abstractmethod
    def get_config_schema(self) -> Dict[str, Any]:
        """Return JSON Schema for the configuration form.

        This schema is used by the frontend to dynamically render
        the setup wizard fields. Example:
        {
            "fields": [
                {"key": "api_key", "label": "API Key", "type": "password", "required": True},
                {"key": "studio_id", "label": "Studio ID", "type": "text", "required": True},
            ]
        }
        """
        ...

    # ── Capability Execution (Agent Runtime) ─────────────────────────────

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
        """Internal execution logic. Override in subclasses."""
        ...

    # ── Health Check ─────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int, config: Dict[str, Any]) -> AdapterResult:
        """Health check for the integration.

        Default implementation delegates to test_connection.
        Override in subclasses for more sophisticated checks.
        """
        test = await self.test_connection(config)
        return AdapterResult(
            success=test.success,
            data={
                "status": "healthy" if test.success else "unhealthy",
                "adapter": self.integration_id,
                "message": test.message,
                "latency_ms": test.latency_ms,
            },
        )

    # ── Optional: Push contacts to external system ───────────────────────

    async def push_contacts(
        self,
        tenant_id: int,
        config: Dict[str, Any],
        contacts: List[NormalizedContact],
    ) -> SyncResult:
        """Push contacts to the external system (for outbound sync).

        Default implementation raises NotImplementedError.
        Override in adapters that support outbound sync.
        """
        raise NotImplementedError(
            f"{self.integration_id} does not support outbound contact sync."
        )

    # ── Optional: Handle incoming webhook ────────────────────────────────

    async def handle_webhook(
        self,
        tenant_id: int,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> SyncResult:
        """Process an incoming webhook event.

        Default implementation raises NotImplementedError.
        Override in adapters that support webhooks.
        """
        raise NotImplementedError(
            f"{self.integration_id} does not support webhook processing."
        )
