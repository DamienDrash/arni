import pytest
import json
import uuid
import asyncio
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.db import Base, tenant_context
from app.orchestration.models import OrchestratorDefinition, OrchestratorVersion
from app.core.models import AgentTeam, UserAccount
from app.orchestration.service import OrchestrationService
from fastapi import HTTPException

# Setup in-memory SQLite for testing
engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    # Add a tenant user for updated_by
    user = UserAccount(id=1, email="admin@example.com", tenant_id=1)
    session.add(user)
    session.commit()
    token = tenant_context.set(1)
    yield session
    tenant_context.reset(token)
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_orchestration_service_snapshot_and_broadcast(db):
    # Create initial orchestrator
    orch_id = str(uuid.uuid4())
    orch = OrchestratorDefinition(
        id=orch_id,
        name="test_orch",
        display_name="Test Orchestrator",
        category="SWARM",
        scope="TENANT",
        status="ACTIVE",
        config_current={"model": "gpt-4o-mini"},
        config_version=1,
        tenant_id=1
    )
    db.add(orch)
    db.commit()

    service = OrchestrationService(db)
    
    # Mock redis_bus.publish
    with patch("app.orchestration.service.redis_bus.publish", new_callable=AsyncMock) as mock_publish:
        # Update config
        new_config = {"model": "gpt-4o"}
        updated_orch = await service.update_orchestrator(
            orch_id, 
            {"config_current": new_config},
            updated_by=1
        )
        
        # Verify snapshot created
        snapshots = db.query(OrchestratorVersion).filter(OrchestratorVersion.orchestrator_id == orch_id).all()
        assert len(snapshots) == 1
        assert snapshots[0].version == 1
        assert snapshots[0].config_snapshot == {"model": "gpt-4o-mini"}
        
        # Verify orch updated
        assert updated_orch.config_current == new_config
        assert updated_orch.config_version == 2
        
        # Verify redis broadcast
        mock_publish.assert_called_once()
        args, _ = mock_publish.call_args
        assert args[0] == "swarm:config:updated"
        payload = json.loads(args[1])
        assert payload["type"] == "orchestrator"
        assert payload["id"] == orch_id

@pytest.mark.asyncio
async def test_orchestration_service_state_transition(db):
    orch_id = str(uuid.uuid4())
    orch = OrchestratorDefinition(
        id=orch_id,
        name="test_orch_state",
        display_name="Test State",
        category="SWARM",
        scope="TENANT",
        status="ACTIVE",
        tenant_id=1
    )
    db.add(orch)
    db.commit()

    service = OrchestrationService(db)
    
    # ACTIVE -> PAUSED (Valid)
    await service.set_orchestrator_state(orch_id, "PAUSED")
    db.refresh(orch)
    assert orch.status == "PAUSED"
    
    # PAUSED -> ACTIVE (Valid)
    await service.set_orchestrator_state(orch_id, "ACTIVE")
    db.refresh(orch)
    assert orch.status == "ACTIVE"
    
    # ACTIVE -> DRAINING (Valid)
    await service.set_orchestrator_state(orch_id, "DRAINING")
    db.refresh(orch)
    assert orch.status == "DRAINING"
    
    # DRAINING -> DISABLED (Valid)
    await service.set_orchestrator_state(orch_id, "DISABLED")
    db.refresh(orch)
    assert orch.status == "DISABLED"

    # DISABLED -> ACTIVE (Valid)
    await service.set_orchestrator_state(orch_id, "ACTIVE")
    db.refresh(orch)
    assert orch.status == "ACTIVE"

    # ACTIVE -> INVALID (Invalid)
    with pytest.raises(HTTPException) as excinfo:
        await service.set_orchestrator_state(orch_id, "INVALID")
    assert excinfo.value.status_code == 422

@pytest.mark.asyncio
async def test_orchestration_service_team_update(db):
    team_id = str(uuid.uuid4())
    team = AgentTeam(
        id=team_id,
        name="test_team",
        display_name="Test Team",
        agent_ids=["agent1", "agent2"],
        status="ACTIVE",
        tenant_id=1
    )
    db.add(team)
    db.commit()

    service = OrchestrationService(db)
    
    with patch("app.orchestration.service.redis_bus.publish", new_callable=AsyncMock) as mock_publish:
        updated_team = await service.update_team(team_id, {"display_name": "Updated Team"})
        assert updated_team.display_name == "Updated Team"
        
        mock_publish.assert_called_once()
        args, _ = mock_publish.call_args
        payload = json.loads(args[1])
        assert payload["type"] == "team"
        assert payload["id"] == team_id

@pytest.mark.asyncio
async def test_orchestration_service_rollback(db):
    orch_id = str(uuid.uuid4())
    orch = OrchestratorDefinition(
        id=orch_id,
        name="rollback_orch",
        display_name="Rollback Test",
        category="SWARM",
        scope="TENANT",
        status="ACTIVE",
        config_current={"v": 1},
        config_version=1,
        tenant_id=1
    )
    db.add(orch)
    db.commit()

    service = OrchestrationService(db)
    
    # Update to v2
    await service.update_orchestrator(orch_id, {"config_current": {"v": 2}})
    assert orch.config_version == 2
    assert orch.config_current == {"v": 2}
    
    # Get version 1 snapshot
    v1 = db.query(OrchestratorVersion).filter(OrchestratorVersion.version == 1).first()
    assert v1 is not None
    
    # Rollback to v1
    await service.rollback_orchestrator(orch_id, str(v1.id))
    
    db.refresh(orch)
    assert orch.config_current == {"v": 1}
    assert orch.config_version == 3 # Increment on rollback
    
    # Verify snapshot of v2 was created before rollback
    v2 = db.query(OrchestratorVersion).filter(OrchestratorVersion.version == 2).first()
    assert v2 is not None
    assert v2.config_snapshot == {"v": 2}
