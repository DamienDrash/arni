"""ARIIA v2.0 – Database Configuration.

@ARCH: Phase 1, Meilenstein 1.2 – Strikte Datenisolation
Provides both sync and async database sessions with tenant context
propagation for Row-Level Security (RLS).
"""

from __future__ import annotations

import contextvars
import os
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Tenant context for Row Level Security (RLS) or logging
tenant_context = contextvars.ContextVar("tenant_context", default=None)

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
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
            cursor.execute(f"SET LOCAL app.current_tenant_id = '{tid}';")
        else:
            cursor.execute("RESET app.current_tenant_id;")
    except Exception:
        pass  # Best effort for context propagation
    finally:
        cursor.close()

# Base class for models
Base = declarative_base()

def run_migrations():
    """Bootstrap the database schema. In production, use Alembic instead."""
    Base.metadata.create_all(bind=engine)
    _backfill_columns()


def _backfill_columns() -> None:
    """Add new columns to existing tables (idempotent). create_all() won't alter existing tables."""
    from sqlalchemy import inspect, text as _text
    inspector = inspect(engine)
    is_pg = SQLALCHEMY_DATABASE_URL.startswith("postgresql")

    def _add_column_if_missing(table: str, col: str, col_def: str) -> None:
        try:
            existing = {c["name"] for c in inspector.get_columns(table)}
        except Exception:
            return
        if col in existing:
            return
        try:
            with engine.connect() as conn:
                if is_pg:
                    conn.execute(_text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_def}"))
                else:
                    conn.execute(_text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
                conn.commit()
        except Exception:
            pass  # Column may have been added by a concurrent worker

    # Plans — monthly_image_credits (added for credit system)
    _add_column_if_missing("plans", "monthly_image_credits", "INTEGER DEFAULT 0")

    # ImageProvider — ELO + fal category enrichment (added for model sync)
    _add_column_if_missing("ai_image_providers", "fal_category", "VARCHAR(32)")
    _add_column_if_missing("ai_image_providers", "elo_score", "INTEGER")
    _add_column_if_missing("ai_image_providers", "elo_rank", "INTEGER")
    _add_column_if_missing("ai_image_providers", "price_per_image_cents", "INTEGER")

    # Backfill fal_category for existing seeded providers (slug-based heuristic)
    try:
        with engine.connect() as conn:
            conn.execute(_text("""
                UPDATE ai_image_providers
                SET fal_category = CASE
                    WHEN slug LIKE '%_edit' OR slug = 'flux_kontext_pro' THEN 'image-to-image'
                    ELSE 'text-to-image'
                END
                WHERE fal_category IS NULL
                  AND provider_type IN ('fal_ai', 'fal_ai_schnell', 'fal_generic', 'recraft_v3', 'ideogram_v2')
            """))
            conn.commit()
    except Exception:
        pass

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
            await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tid}'"))
        try:
            yield session
        finally:
            await session.close()
