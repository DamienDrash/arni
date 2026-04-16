"""app/orchestration/team_seed.py — Default agent team seeding.

Provides idempotent creation of the default agent team for a tenant.
Called on registration and used for backfilling existing tenants.
"""
from __future__ import annotations

import uuid
import structlog
from sqlalchemy.orm import Session

from app.domains.ai.models import AgentTeam
from app.domains.identity.models import Tenant

logger = structlog.get_logger()

# Agents included in the default team (all starter-tier agents)
DEFAULT_AGENT_IDS = ["ops", "sales", "medic", "persona", "knowledge"]

DEFAULT_TEAM_NAME = "default"
DEFAULT_ORCHESTRATOR = "swarm-orchestrator"


def seed_default_team_for_tenant(
    db: Session,
    tenant_id: int,
    created_by: int | None = None,
) -> AgentTeam:
    """Create the default agent team for a tenant if it doesn't exist yet.

    Idempotent — safe to call multiple times.
    Returns the existing or newly created team.
    """
    existing = db.query(AgentTeam).filter(
        AgentTeam.tenant_id == tenant_id,
        AgentTeam.name == DEFAULT_TEAM_NAME,
    ).first()

    if existing:
        # Ensure it's active
        if existing.status != "ACTIVE":
            existing.status = "ACTIVE"
            db.commit()
        return existing

    team = AgentTeam(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=DEFAULT_TEAM_NAME,
        display_name="Default Team",
        description="Standard agent team with ops, sales, medic, persona, and knowledge agents.",
        agent_ids=DEFAULT_AGENT_IDS,
        orchestrator_name=DEFAULT_ORCHESTRATOR,
        status="ACTIVE",
        created_by=created_by,
    )
    db.add(team)
    db.commit()
    logger.info("team_seed.created", tenant_id=tenant_id, team_id=team.id)
    return team


def backfill_default_teams(db: Session) -> int:
    """Create default teams for all tenants that don't have one.

    Returns the number of teams created.
    """
    tenants = db.query(Tenant).all()
    created = 0
    for tenant in tenants:
        existing = db.query(AgentTeam).filter(
            AgentTeam.tenant_id == tenant.id,
        ).first()
        if not existing:
            seed_default_team_for_tenant(db, tenant.id)
            created += 1
    logger.info("team_seed.backfill_completed", created=created, total=len(tenants))
    return created
