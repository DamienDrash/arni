"""ARIIA v1.4 – Pytest Configuration.

Shared fixtures for all tests.
"""

# Exclude legacy sprint-style test scripts (they contain sys.exit() at module
# level which kills the pytest process) and other non-pytest test files.
collect_ignore_glob = [
    "test_sprint*.py",
    "test_phase2_refactoring.py",
    "run_all_qa.py",
    "test_memory_platform.py",
]

import os

# Force testing mode to allow SQLite fallback in app/core/db.py
os.environ["ENVIRONMENT"] = "testing"
if "DATABASE_URL" in os.environ:
    del os.environ["DATABASE_URL"]
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
# Set a known admin password for tests (matches admin@ariia.local login in test files)
os.environ.setdefault("SYSTEM_ADMIN_PASSWORD", "Password123")

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock

from app.edge.app import app


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
    """Ensure system tenant and admin exist with the correct test password.

    Also resets the admin lockout state before each test so that failed login
    attempts from one test do not poison subsequent tests.
    """
    import os
    import asyncio
    from app.core.auth import ensure_default_tenant_and_admin, hash_password
    from app.core.feature_gates import seed_plans
    from app.billing.seed import seed_billing_v2
    from app.core.db import SessionLocal
    from app.gateway.auth import UserAccount
    try:
        ensure_default_tenant_and_admin()
    except Exception:
        pass
    try:
        seed_plans()
    except Exception:
        pass
    try:
        db = SessionLocal()
        try:
            asyncio.run(seed_billing_v2(db))
        finally:
            db.close()
    except Exception:
        pass
    # Ensure admin has the test password and no lockout
    try:
        db = SessionLocal()
        admin = db.query(UserAccount).filter(UserAccount.email == "admin@ariia.local").first()
        if admin:
            admin_password = os.getenv("SYSTEM_ADMIN_PASSWORD", "")
            if admin_password:
                admin.password_hash = hash_password(admin_password)
            admin.failed_login_attempts = 0
            admin.locked_until = None
            admin.is_active = True
            db.commit()
        db.close()
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
