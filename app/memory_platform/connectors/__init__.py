"""Connectors package – external data source integrations.

Each connector implements the BaseConnector interface and can be
registered with the ConnectorRegistry for unified management.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import structlog

logger = structlog.get_logger()


class BaseConnector(ABC):
    """Abstract base class for all external data source connectors."""

    connector_name: str = "base"
    connector_type: str = "generic"

    @abstractmethod
    async def connect(self, credentials: dict[str, Any]) -> bool:
        """Establish connection with the external service."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the external service."""
        ...

    @abstractmethod
    async def sync(self, tenant_id: int, **kwargs: Any) -> dict[str, Any]:
        """Perform a full or incremental sync."""
        ...

    @abstractmethod
    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        """Test the connection with given credentials."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the connector is currently connected."""
        ...


class ConnectorRegistry:
    """Central registry for all data source connectors."""

    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        """Register a connector."""
        self._connectors[connector.connector_name] = connector
        logger.info("connector_registry.registered", name=connector.connector_name)

    def get(self, name: str) -> BaseConnector | None:
        """Get a connector by name."""
        return self._connectors.get(name)

    @property
    def available_connectors(self) -> list[str]:
        """List all registered connector names."""
        return list(self._connectors.keys())


_registry: ConnectorRegistry | None = None


def get_connector_registry() -> ConnectorRegistry:
    """Return the singleton connector registry."""
    global _registry
    if _registry is None:
        _registry = ConnectorRegistry()
    return _registry
