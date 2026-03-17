"""Tests for OrchestratorManager — CRUD, versioning, guardrails, state transitions, rollback."""

import os
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.orchestration.models import OrchestratorDefinition, OrchestratorVersion, OrchestratorTenantOverride
from app.orchestration.manager import OrchestratorManager


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
def db_session():
    """Create an in-memory SQLite DB with only orchestrator tables, yield a session.

    Uses per-table create() rather than Base.metadata.create_all() to avoid
    pulling in integration_models.py which uses JSONB (unsupported by SQLite).
    """
    engine = create_engine("sqlite:///:memory:")
    for tbl in [
        OrchestratorDefinition.__table__,
        OrchestratorVersion.__table__,
        OrchestratorTenantOverride.__table__,
    ]:
        tbl.create(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def seeded_db(db_session):
    """Seed a 'swarm-orchestrator' and 'quality-gate' definition."""
    now = datetime.now(timezone.utc)
    swarm = OrchestratorDefinition(
        name="swarm-orchestrator",
        display_name="Swarm Orchestrator",
        category="SWARM",
        scope="SYSTEM",
        state="ACTIVE",
        config_current={
            "intent_classifier": {"model": "gpt-4o-mini", "temperature": 0.0, "max_revision_rounds": 2},
            "qa_gate": {"enabled": True},
        },
        guardrails={},
        config_version=1,
        created_at=now,
        updated_at=now,
    )
    quality = OrchestratorDefinition(
        name="quality-gate",
        display_name="Quality Gate",
        category="SWARM",
        scope="SYSTEM",
        state="ACTIVE",
        config_current={"escalation_handler": "human_handoff", "max_revision_rounds": 2},
        guardrails={"enabled": {"immutable": True, "value": True}},
        config_version=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([swarm, quality])
    db_session.commit()
    return db_session


def _mgr(db_session) -> OrchestratorManager:
    """Create an OrchestratorManager with Redis invalidation mocked out."""
    mgr = OrchestratorManager(db_session)
    return mgr


# ── Tests ───────────────────────────────────────────────────────────────────

class TestGetConfig:
    def test_get_config_returns_defaults(self, seeded_db):
        mgr = _mgr(seeded_db)
        config = mgr.get_config("swarm-orchestrator")
        assert config["intent_classifier"]["model"] == "gpt-4o-mini"
        assert config["qa_gate"]["enabled"] is True

    def test_get_config_not_found_raises_404(self, seeded_db):
        mgr = _mgr(seeded_db)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            mgr.get_config("nonexistent")
        assert exc_info.value.status_code == 404


class TestUpdateConfig:
    @patch("app.orchestration.manager.OrchestratorManager._invalidate_cache")
    def test_update_config_increments_version(self, mock_cache, seeded_db):
        mgr = _mgr(seeded_db)
        mgr.update_config("swarm-orchestrator", {"new_key": "value"}, updated_by=1, change_summary="test")
        orch = seeded_db.query(OrchestratorDefinition).filter_by(name="swarm-orchestrator").first()
        assert orch.config_version == 2

    @patch("app.orchestration.manager.OrchestratorManager._invalidate_cache")
    def test_update_config_creates_version_record(self, mock_cache, seeded_db):
        mgr = _mgr(seeded_db)
        version = mgr.update_config("swarm-orchestrator", {"new_key": "value"}, updated_by=1, change_summary="add key")
        assert isinstance(version, OrchestratorVersion)
        assert version.version == 1  # snapshot of the old version number
        assert version.change_summary == "add key"
        assert version.rollback_safe is True

    @patch("app.orchestration.manager.OrchestratorManager._invalidate_cache")
    def test_update_config_merges_patch(self, mock_cache, seeded_db):
        mgr = _mgr(seeded_db)
        mgr.update_config("swarm-orchestrator", {"new_key": "value"}, updated_by=1)
        config = mgr.get_config("swarm-orchestrator")
        assert config["new_key"] == "value"
        # Original keys still present
        assert config["intent_classifier"]["model"] == "gpt-4o-mini"


class TestGuardrails:
    def test_guardrail_blocks_invalid_value(self, seeded_db):
        mgr = _mgr(seeded_db)
        from fastapi import HTTPException
        # IMMUTABLE_GUARDRAILS: quality-gate → qa_gate.enabled must be True
        with pytest.raises(HTTPException) as exc_info:
            mgr.update_config("quality-gate", {"qa_gate": {"enabled": False}}, updated_by=1)
        assert exc_info.value.status_code == 422
        assert "Guardrail violation" in str(exc_info.value.detail)

    @patch("app.orchestration.manager.OrchestratorManager._invalidate_cache")
    def test_max_guardrail_blocks_exceeding_value(self, mock_cache, seeded_db):
        mgr = _mgr(seeded_db)
        from fastapi import HTTPException
        # MAX_GUARDRAILS: swarm-orchestrator → intent_classifier.max_revision_rounds max=3
        with pytest.raises(HTTPException) as exc_info:
            mgr.update_config("swarm-orchestrator", {"intent_classifier": {"max_revision_rounds": 5}}, updated_by=1)
        assert exc_info.value.status_code == 422


class TestRollback:
    @patch("app.orchestration.manager.OrchestratorManager._invalidate_cache")
    def test_rollback_restores_config(self, mock_cache, seeded_db):
        mgr = _mgr(seeded_db)
        original_config = mgr.get_config("swarm-orchestrator").copy()

        # Update: override intent_classifier model
        mgr.update_config("swarm-orchestrator", {"intent_classifier": {"model": "gpt-4o"}}, updated_by=1, change_summary="v1→v2")
        config_after_update = mgr.get_config("swarm-orchestrator")
        assert config_after_update["intent_classifier"]["model"] == "gpt-4o"

        # Rollback to version 1 (snapshot = original config)
        mgr.rollback("swarm-orchestrator", target_version=1, changed_by=1)
        config = mgr.get_config("swarm-orchestrator")

        # The rollback applies the v1 snapshot, restoring the original model value
        assert config["intent_classifier"]["model"] == original_config["intent_classifier"]["model"]

    @patch("app.orchestration.manager.OrchestratorManager._invalidate_cache")
    def test_rollback_unsafe_blocked(self, mock_cache, seeded_db):
        mgr = _mgr(seeded_db)
        mgr.update_config("swarm-orchestrator", {"change": True}, updated_by=1)

        # Mark the version as not rollback-safe
        version = seeded_db.query(OrchestratorVersion).first()
        version.rollback_safe = False
        seeded_db.commit()

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            mgr.rollback("swarm-orchestrator", target_version=version.version, changed_by=1)
        assert exc_info.value.status_code == 409


class TestStateTransitions:
    def test_state_transition_valid(self, seeded_db):
        mgr = _mgr(seeded_db)
        mgr.set_state("swarm-orchestrator", "PAUSED", changed_by=1)
        orch = seeded_db.query(OrchestratorDefinition).filter_by(name="swarm-orchestrator").first()
        assert orch.state == "PAUSED"

    def test_state_transition_invalid(self, seeded_db):
        mgr = _mgr(seeded_db)
        # First move to PAUSED
        mgr.set_state("swarm-orchestrator", "PAUSED", changed_by=1)

        from fastapi import HTTPException
        # PAUSED → DRAINING is not a valid transition
        with pytest.raises(HTTPException) as exc_info:
            mgr.set_state("swarm-orchestrator", "DRAINING", changed_by=1)
        assert exc_info.value.status_code == 422

    def test_disabled_is_terminal(self, seeded_db):
        mgr = _mgr(seeded_db)
        mgr.set_state("swarm-orchestrator", "DISABLED", changed_by=1)

        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            mgr.set_state("swarm-orchestrator", "ACTIVE", changed_by=1)


class TestListAll:
    def test_list_all_returns_seeded(self, seeded_db):
        mgr = _mgr(seeded_db)
        results = mgr.list_all()
        names = [r.name for r in results]
        assert "swarm-orchestrator" in names
        assert "quality-gate" in names
