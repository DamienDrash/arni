from __future__ import annotations

import json
from types import SimpleNamespace

from app.core.db import SessionLocal
from app.core.models import AuditLog
from app.swarm.qa.escalation_router import (
    EscalationHandler,
    _get_configured_handler,
    _handle_dead_letter,
)


def test_get_configured_handler_reads_quality_gate_config(monkeypatch) -> None:
    from app.orchestration import manager as orchestrator_manager

    class _FakeManager:
        def __init__(self, db) -> None:
            self.db = db

        def get_config(self, key: str) -> dict[str, str]:
            assert key == "quality-gate"
            return {"escalation_handler": EscalationHandler.DEAD_LETTER}

    monkeypatch.setattr(orchestrator_manager, "OrchestratorManager", _FakeManager)
    assert _get_configured_handler() == EscalationHandler.DEAD_LETTER


async def test_handle_dead_letter_writes_audit_log() -> None:
    result = SimpleNamespace(
        agent_id="qa-agent",
        content="This answer needs escalation.",
        metadata={"escalation_reason": "low_confidence"},
    )

    await _handle_dead_letter(result, tenant_id=1)

    db = SessionLocal()
    try:
        entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == 1,
                AuditLog.action == "qa_escalation_dead_letter",
                AuditLog.target_id == "qa-agent",
            )
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert entry is not None
        payload = json.loads(entry.details_json or "{}")
        assert payload["reason"] == "low_confidence"
        assert "content_preview" in payload
    finally:
        db.close()
