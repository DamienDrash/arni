"""ARNI v1.4 – SQLite Session Database.

@BACKEND: Sprint 4, Task 4.2
Async SQLite with sessions + messages tables. 90-day retention.
"""

import aiosqlite
import structlog
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = structlog.get_logger()

DEFAULT_DB_PATH = "data/sessions.db"
RETENTION_DAYS = 90

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    user_id TEXT NOT NULL,
    consent_status TEXT NOT NULL DEFAULT 'granted',
    last_interaction DATETIME NOT NULL,
    metadata JSON DEFAULT '{}',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last ON sessions(last_interaction);
"""


class MemoryDB:
    """Async SQLite database for session and message persistence.

    Schema follows MEMORY.md specification.
    Supports 90-day auto-cleanup and cascade deletion for GDPR Art. 17.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Initialize database: create tables and run cleanup."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info("memorydb.initialized", path=self._db_path)

        # Auto-cleanup expired sessions
        await self.cleanup_expired()

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Get active database connection."""
        if not self._db:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._db

    async def cleanup_expired(self) -> int:
        """Delete sessions older than RETENTION_DAYS.

        Returns:
            Number of deleted sessions.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        cursor = await self.db.execute(
            "DELETE FROM sessions WHERE last_interaction < ?",
            (cutoff.isoformat(),),
        )
        await self.db.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info("memorydb.cleanup", deleted=deleted, retention_days=RETENTION_DAYS)
        return deleted
