"""ARIIA v2.0 – Database Configuration.

@ARCH: Phase 1, Meilenstein 1.2 – Strikte Datenisolation
Provides both sync and async database sessions with tenant context
propagation for Row-Level Security (RLS).
"""

from __future__ import annotations

import contextvars
import os
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, event, text, Column, Integer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker, Query

# Tenant context for Row Level Security (RLS) or logging
tenant_context = contextvars.ContextVar("tenant_context", default=None)

class TenantScopedMixin:
    """Mixin to add tenant_id to models and mark them as tenant-scoped."""
    __tenant_scoped__ = True
    tenant_id = Column(Integer, index=True, nullable=True)

class TenantQuery(Query):
    """Custom Query class that automatically filters by tenant_id."""

    def _where_tenant(self):
        # We check if we have already applied the tenant filter to avoid recursion.
        # However, _where_tenant returns a new Query object, so we must be careful.
        # Instead of overriding methods and calling them again, we can just return
        # the filtered query and ensure we don't call the same overridden method.
        
        tid = tenant_context.get()
        if tid is not None:
            for desc in self.column_descriptions:
                entity = desc.get("entity")
                if entity and getattr(entity, "__tenant_scoped__", False):
                    # Check if the filter is already applied by looking at the statement
                    # This is complex in SQLAlchemy, a simpler way is to use a flag on the query.
                    if getattr(self, "_tenant_filtered", False):
                        return self
                    
                    filtered_query = self.filter(entity.tenant_id == tid)
                    filtered_query._tenant_filtered = True
                    return filtered_query
        return self

    def __iter__(self):
        return super(TenantQuery, self._where_tenant()).__iter__()

    def all(self):
        return super(TenantQuery, self._where_tenant()).all()

    def first(self):
        return super(TenantQuery, self._where_tenant()).first()

    def count(self):
        return super(TenantQuery, self._where_tenant()).count()

# Mandatory PostgreSQL Connection
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Special case for local testing/CI
IS_TEST = os.getenv("PYTEST_CURRENT_TEST") is not None or os.getenv("ENVIRONMENT") == "testing"

if (not SQLALCHEMY_DATABASE_URL or not SQLALCHEMY_DATABASE_URL.startswith("postgresql")) and not IS_TEST:
    raise RuntimeError(
        "CRITICAL: DATABASE_URL must be a valid PostgreSQL connection string. "
        "SQLite is no longer supported for ARIIA v2.0 production/dev environments."
    )

if IS_TEST and not SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test_ariia.db"

# Optimized PostgreSQL Engine with Pooling
if SQLALCHEMY_DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
else:
    # SQLite for testing
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# Sync SessionLocal
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    query_cls=TenantQuery
)


# ─── Async Engine (for request handling) ─────────────────────────────────────────

_async_engine = None
_async_session_factory = None


def _get_async_url() -> str:
    """Convert sync DB URL to async driver URL."""
    url = SQLALCHEMY_DATABASE_URL
    if url.startswith("postgresql+psycopg://"):
        return url  # psycopg3 supports async natively
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def get_async_engine():
    """Get or create the async engine (lazy initialization)."""
    global _async_engine
    if _async_engine is None:
        async_url = _get_async_url()
        if "postgresql" in async_url:
            _async_engine = create_async_engine(
                async_url,
                pool_size=20,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True,
            )
        else:
            _async_engine = create_async_engine(async_url)
    return _async_engine


def get_async_session_factory():
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory

@event.listens_for(engine, "checkout")
def set_tenant_id_context(dbapi_connection, connection_record, connection_proxy):
    """Propagate the current tenant_id to PostgreSQL for RLS policies."""
    tid = tenant_context.get()
    cursor = dbapi_connection.cursor()
    try:
        if tid is not None:
            cursor.execute("SET LOCAL app.current_tenant_id = %s", (str(tid),))
        else:
            cursor.execute("RESET app.current_tenant_id;")
    except Exception:
        pass  # Best effort for context propagation
    finally:
        cursor.close()

from sqlalchemy.types import TypeDecorator, JSON as sa_JSON
try:
    from sqlalchemy.dialects.postgresql import JSONB as sa_JSONB
except ImportError:
    sa_JSONB = sa_JSON

# Flexible JSON type for cross-db compatibility (JSONB on Postgres, JSON on SQLite)
FlexibleJSON = sa_JSONB if engine.name == "postgresql" else sa_JSON

# Base class for models
Base = declarative_base()

def run_migrations():
    """Bootstrap the database schema and run pending Alembic migrations."""
    Base.metadata.create_all(bind=engine)
    try:
        from alembic.config import Config
        from alembic import command
        import os
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)
        command.upgrade(alembic_cfg, "2026_03_18_merge_heads")
    except Exception as _alembic_err:
        import structlog
        structlog.get_logger().warning("db.alembic_upgrade_failed", error=str(_alembic_err))


# Register tenant isolation interceptor on the sync session factory
from app.core.tenant_interceptor import register_tenant_interceptor

register_tenant_interceptor(SessionLocal)

# ─── FastAPI Dependencies ─────────────────────────────────────────────────────────


def get_db() -> Generator[Session, None, None]:
    """Sync DB session dependency (legacy compatibility)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async DB session dependency with tenant context propagation.

    Sets the PostgreSQL session variable for RLS before yielding.
    """
    factory = get_async_session_factory()
    async with factory() as session:
        tid = tenant_context.get()
        if tid is not None:
            await session.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": str(tid)})
        try:
            yield session
        finally:
            await session.close()
