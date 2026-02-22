"""ARIIA v1.4 – Pytest Configuration.

Shared fixtures for all tests.
"""

import os

# Force testing mode to allow SQLite fallback in app/core/db.py
os.environ["ENVIRONMENT"] = "testing"
if "DATABASE_URL" in os.environ:
    del os.environ["DATABASE_URL"]
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock

from app.gateway.main import app


@pytest.fixture(autouse=True)
def mock_redis_bus():
    """Mock RedisBus for all tests."""
    from app.gateway.dependencies import redis_bus
    
    redis_bus.connect = AsyncMock()
    redis_bus.disconnect = AsyncMock()
    redis_bus.publish = AsyncMock()
    redis_bus.health_check = AsyncMock(return_value=True)
    return redis_bus


@pytest.fixture(autouse=True)
def seed_system_tenant():
    """Ensure system tenant exists for tests."""
    from app.core.auth import ensure_default_tenant_and_admin
    try:
        ensure_default_tenant_and_admin()
    except Exception:
        pass


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async test client for the FastAPI gateway."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
