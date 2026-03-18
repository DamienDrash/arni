"""PostgreSQL advisory locks for preventing concurrent execution of the same job."""
from __future__ import annotations
import asyncio
import contextlib
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = structlog.get_logger()

# In-memory fallback for SQLite (development)
_sqlite_locks: dict[str, asyncio.Lock] = {}


def try_advisory_lock(db: Session, lock_key: str) -> bool:
    """Attempt to acquire a PostgreSQL advisory lock. Returns True if acquired.

    For SQLite (dev), uses an in-memory asyncio.Lock as fallback.
    Lock is automatically released on transaction commit or rollback.
    """
    dialect = db.bind.dialect.name if db.bind else "postgresql"

    if dialect == "postgresql":
        try:
            result = db.execute(
                text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"),
                {"key": lock_key}
            ).scalar()
            return bool(result)
        except Exception as e:
            logger.warning("advisory_lock.pg_error", key=lock_key, error=str(e))
            return True  # fail-open: don't block if lock system fails
    else:
        # SQLite fallback: non-blocking in-memory check
        if lock_key not in _sqlite_locks:
            _sqlite_locks[lock_key] = asyncio.Lock()
        lock = _sqlite_locks[lock_key]
        acquired = not lock.locked()
        return acquired


@contextlib.contextmanager
def advisory_lock_or_skip(db: Session, lock_key: str):
    """Context manager: yields True if lock acquired, False if another worker holds it."""
    acquired = try_advisory_lock(db, lock_key)
    yield acquired
