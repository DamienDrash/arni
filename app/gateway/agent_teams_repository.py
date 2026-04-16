from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.ai.models import AgentTeam


class AgentTeamsRepository:
    """Focused DB access for system-admin agent team CRUD."""

    def list_teams(self, db: Session) -> list[AgentTeam]:
        return db.query(AgentTeam).order_by(AgentTeam.display_name).all()

    def get_team_by_name(self, db: Session, *, team_name: str) -> AgentTeam | None:
        return db.query(AgentTeam).filter(AgentTeam.name == team_name).first()

    def add_team(self, db: Session, *, team: AgentTeam) -> AgentTeam:
        db.add(team)
        return team


agent_teams_repository = AgentTeamsRepository()
