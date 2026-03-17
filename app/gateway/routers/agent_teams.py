"""Admin API for Agent Teams — CRUD management of named agent groups."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import get_db
from app.core.models import AgentTeam, AgentDefinition

router = APIRouter(prefix="/admin/agent-teams", tags=["agent-teams"])

VALID_STATES = {"ACTIVE", "PAUSED", "DISABLED"}


class TeamBody(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    agent_ids: list[str] = []
    orchestrator_name: str | None = None


class TeamPatchBody(BaseModel):
    display_name: str | None = None
    description: str | None = None
    agent_ids: list[str] | None = None
    orchestrator_name: str | None = None


class StateBody(BaseModel):
    state: str


def _team_out(t: AgentTeam) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "display_name": t.display_name,
        "description": t.description,
        "agent_ids": t.agent_ids or [],
        "orchestrator_name": t.orchestrator_name,
        "state": t.state,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("")
def list_teams(user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, {"system_admin"})
    return [_team_out(t) for t in db.query(AgentTeam).order_by(AgentTeam.display_name).all()]


@router.post("", status_code=201)
def create_team(body: TeamBody, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, {"system_admin"})
    if db.query(AgentTeam).filter(AgentTeam.name == body.name).first():
        raise HTTPException(409, f"Team '{body.name}' already exists")
    now = datetime.now(timezone.utc)
    team = AgentTeam(
        id=str(uuid.uuid4()),
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        agent_ids=body.agent_ids,
        orchestrator_name=body.orchestrator_name,
        state="ACTIVE",
        created_at=now,
        updated_at=now,
        created_by=user.user_id,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return _team_out(team)


@router.get("/{team_name}")
def get_team(team_name: str, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, {"system_admin"})
    team = db.query(AgentTeam).filter(AgentTeam.name == team_name).first()
    if not team:
        raise HTTPException(404, f"Team '{team_name}' not found")
    return _team_out(team)


@router.patch("/{team_name}")
def update_team(team_name: str, body: TeamPatchBody, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, {"system_admin"})
    team = db.query(AgentTeam).filter(AgentTeam.name == team_name).first()
    if not team:
        raise HTTPException(404, f"Team '{team_name}' not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(team, k, v)
    team.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(team)
    return _team_out(team)


@router.post("/{team_name}/state")
def set_team_state(team_name: str, body: StateBody, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, {"system_admin"})
    if body.state not in VALID_STATES:
        raise HTTPException(422, f"state must be one of {VALID_STATES}")
    team = db.query(AgentTeam).filter(AgentTeam.name == team_name).first()
    if not team:
        raise HTTPException(404, f"Team '{team_name}' not found")
    team.state = body.state
    team.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok", "new_state": body.state}


@router.delete("/{team_name}", status_code=204)
def delete_team(team_name: str, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, {"system_admin"})
    team = db.query(AgentTeam).filter(AgentTeam.name == team_name).first()
    if not team:
        raise HTTPException(404, f"Team '{team_name}' not found")
    db.delete(team)
    db.commit()
