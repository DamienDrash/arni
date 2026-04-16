"""Orchestration Governance Service.

Implements the service layer for managing Orchestrators and Agent Teams with
versioned configuration snapshots and multi-tenant isolation.
"""
from __future__ import annotations

import uuid
import json
import copy
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException

from app.domains.ai.models import AgentTeam
from app.orchestration.models import OrchestratorDefinition, OrchestratorVersion

logger = structlog.get_logger()

class OrchestrationService:
    """Service for managing orchestrators and agent teams with governance features."""

    def __init__(self, db: Session):
        self.db = db

    async def get_orchestrator(self, name_or_id: str) -> Optional[OrchestratorDefinition]:
        """Retrieve an orchestrator by name or UUID."""
        return self.db.query(OrchestratorDefinition).filter(
            or_(
                OrchestratorDefinition.id == name_or_id,
                OrchestratorDefinition.name == name_or_id
            )
        ).first()

    async def update_orchestrator(
        self, 
        id: str, 
        updates: Dict[str, Any], 
        updated_by: Optional[int] = None
    ) -> OrchestratorDefinition:
        """Update orchestrator attributes and create a snapshot if config changes."""
        orch = await self.get_orchestrator(id)
        if not orch:
            raise HTTPException(status_code=404, detail=f"Orchestrator '{id}' not found")

        config_changed = "config_current" in updates and updates["config_current"] != orch.config_current
        
        # If config is changing, snapshot the CURRENT state before applying updates
        if config_changed:
            await self._create_snapshot(orch.id, updated_by)
            orch.config_version += 1

        for key, value in updates.items():
            if hasattr(orch, key) and key not in ["id", "config_version"]:
                setattr(orch, key, value)
        
        orch.updated_at = datetime.now(timezone.utc)
        if updated_by:
            orch.updated_by = updated_by

        self.db.commit()
        self.db.refresh(orch)

        await self._broadcast_change("orchestrator", orch.id)
        
        logger.info("orchestration.orchestrator_updated", 
                    id=orch.id, name=orch.name, config_changed=config_changed)
        return orch

    async def _create_snapshot(self, orchestrator_id: str, changed_by: Optional[int] = None) -> OrchestratorVersion:
        """Internal method to create a version snapshot of current configuration."""
        orch = self.db.query(OrchestratorDefinition).filter(OrchestratorDefinition.id == orchestrator_id).first()
        if not orch:
             raise HTTPException(status_code=404, detail=f"Orchestrator '{orchestrator_id}' not found")

        version = OrchestratorVersion(
            id=str(uuid.uuid4()),
            orchestrator_id=orch.id,
            version=orch.config_version,
            config_snapshot=copy.deepcopy(orch.config_current),
            changed_by=changed_by,
            changed_at=datetime.now(timezone.utc),
            rollback_safe=True,
            change_summary=f"Snapshot of version {orch.config_version}"
        )
        self.db.add(version)
        # Caller is responsible for commit
        return version

    async def rollback_orchestrator(
        self, 
        orchestrator_id: str, 
        version_id: str, 
        changed_by: Optional[int] = None
    ) -> OrchestratorDefinition:
        """Roll back an orchestrator to a specific version."""
        orch = await self.get_orchestrator(orchestrator_id)
        if not orch:
            raise HTTPException(status_code=404, detail=f"Orchestrator '{orchestrator_id}' not found")

        # Try to find version by ID or by version number
        version = self.db.query(OrchestratorVersion).filter(
            OrchestratorVersion.orchestrator_id == orch.id,
            or_(
                OrchestratorVersion.id == version_id,
                OrchestratorVersion.version.cast(Any) == version_id  # Cast for comparison if string provided
            )
        ).first()
        
        if not version:
            raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found for orchestrator")

        if not version.rollback_safe:
            raise HTTPException(status_code=400, detail=f"Version '{version_id}' is not marked as rollback-safe")

        # Create snapshot of current state before rolling back
        await self._create_snapshot(orch.id, changed_by)
        
        orch.config_current = copy.deepcopy(version.config_snapshot)
        orch.config_version += 1
        orch.updated_at = datetime.now(timezone.utc)
        if changed_by:
            orch.updated_by = changed_by

        self.db.commit()
        self.db.refresh(orch)
        
        await self._broadcast_change("orchestrator", orch.id)
        
        logger.info("orchestration.orchestrator_rolled_back", 
                    id=orch.id, to_version=version.version, new_version=orch.config_version)
        return orch

    async def get_team(self, name_or_id: str) -> Optional[AgentTeam]:
        """Retrieve an agent team by name or UUID."""
        return self.db.query(AgentTeam).filter(
            or_(
                AgentTeam.id == name_or_id,
                AgentTeam.name == name_or_id
            )
        ).first()

    async def update_team(self, id: str, updates: Dict[str, Any]) -> AgentTeam:
        """Update agent team attributes."""
        team = await self.get_team(id)
        if not team:
            raise HTTPException(status_code=404, detail=f"AgentTeam '{id}' not found")

        for key, value in updates.items():
            if hasattr(team, key) and key != "id":
                setattr(team, key, value)
        
        team.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(team)

        await self._broadcast_change("team", team.id)
        
        logger.info("orchestration.team_updated", id=team.id, name=team.name)
        return team

    async def set_orchestrator_state(
        self, 
        id: str, 
        state: str, 
        updated_by: Optional[int] = None
    ) -> OrchestratorDefinition:
        """Update orchestrator status with transition validation."""
        VALID_STATES = ["ACTIVE", "PAUSED", "DRAINING", "DISABLED"]
        if state not in VALID_STATES:
            raise HTTPException(status_code=422, detail=f"Invalid state: {state}. Must be one of {VALID_STATES}")

        orch = await self.get_orchestrator(id)
        if not orch:
            raise HTTPException(status_code=404, detail=f"Orchestrator '{id}' not found")

        current_status = orch.status
        valid_transitions = {
            "ACTIVE": ["PAUSED", "DRAINING", "DISABLED"],
            "PAUSED": ["ACTIVE", "DISABLED"],
            "DRAINING": ["ACTIVE", "DISABLED", "PAUSED"],
            "DISABLED": ["ACTIVE"]
        }
        
        if state != current_status and state not in valid_transitions.get(current_status, []):
             raise HTTPException(
                 status_code=422, 
                 detail=f"Invalid transition from {current_status} to {state}"
             )

        orch.status = state
        orch.updated_at = datetime.now(timezone.utc)
        if updated_by:
            orch.updated_by = updated_by

        self.db.commit()
        self.db.refresh(orch)

        await self._broadcast_change("orchestrator", orch.id)
        
        logger.info("orchestration.orchestrator_state_changed", id=orch.id, from_state=current_status, to_state=state)
        return orch

    async def _broadcast_change(self, type: str, id: str):
        """Internal method to broadcast configuration changes via Redis Pub/Sub."""
        from app.gateway.dependencies import redis_bus
        payload = {
            "type": type,
            "id": id
        }
        try:
            # Broadcast to swarm:config:updated as requested
            await redis_bus.publish("swarm:config:updated", json.dumps(payload))
        except Exception as e:
            logger.error("orchestration.broadcast_failed", type=type, id=id, error=str(e))
