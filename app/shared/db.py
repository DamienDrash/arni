from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from typing import Callable, Iterator

from sqlalchemy.orm import Session

from app.core.db import SessionLocal

SessionFactory = Callable[[], Session]


def open_session(session_factory: SessionFactory = SessionLocal) -> Session:
    """Create a dedicated sync session for explicit compatibility call sites."""
    return session_factory()


@contextmanager
def session_scope(session_factory: SessionFactory = SessionLocal) -> Iterator[Session]:
    """Yield a dedicated sync session and close it deterministically."""
    db = open_session(session_factory)
    try:
        yield db
    finally:
        db.close()


@contextmanager
def transaction_scope(session_factory: SessionFactory = SessionLocal) -> Iterator[Session]:
    """Yield a sync session and wrap it in commit/rollback semantics."""
    with session_scope(session_factory) as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


class UnitOfWork(AbstractContextManager["UnitOfWork"]):
    """Small sync Unit of Work for explicit transactional call sites."""

    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        return self

    def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork session has not been started")
        self.session.commit()

    def rollback(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork session has not been started")
        self.session.rollback()

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self.session is None:
            return None
        try:
            if exc_type is not None:
                self.session.rollback()
        finally:
            self.session.close()
            self.session = None
        return None
