"""ARIIA v2.0 – SQLAlchemy Tenant Isolation Interceptor.

Automatically appends a `WHERE tenant_id = :tid` filter to all SELECT
queries targeting models marked with `__tenant_scoped__ = True`.

System admin context bypasses the filter to allow cross-tenant reads.
"""

from __future__ import annotations

import structlog
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.tenant_context import get_current_tenant_id, get_tenant_context_or_none

logger = structlog.get_logger()


def register_tenant_interceptor(session_factory) -> None:
    """Attach a `do_orm_execute` listener that enforces tenant isolation.

    Args:
        session_factory: The SQLAlchemy sessionmaker to instrument.
    """

    @event.listens_for(session_factory, "do_orm_execute")
    def _enforce_tenant_isolation(execute_state):
        if not execute_state.is_select:
            return

        ctx = get_tenant_context_or_none()
        if ctx is None:
            return  # No tenant context (system/admin scope) — skip

        try:
            for desc in execute_state.statement.column_descriptions:
                entity = desc.get("entity")
                if entity is None:
                    continue
                if not getattr(entity, "__tenant_scoped__", False):
                    continue

                tid = ctx.tenant_id
                if tid:
                    execute_state.statement = execute_state.statement.where(
                        entity.tenant_id == tid
                    )
                else:
                    logger.warning(
                        "tenant_isolation.missing_tenant_id",
                        table=getattr(entity, "__tablename__", "?"),
                    )
                return
        except Exception:
            pass
