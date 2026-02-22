"""ARNI v1.4 – Pytest Configuration.

Shared fixtures for all tests.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.gateway.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async test client for the FastAPI gateway."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
