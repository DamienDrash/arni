"""app/swarm/run_models.py — Agent Team Run Persistence Models.

Every execution of an AgentTeam is stored here for history and debugging.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Index
from app.core.db import Base


class AgentTeamRun(Base):
    """Single execution record for an agent team."""
    __tablename__ = "agent_team_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)

    team_slug = Column(String(64), nullable=False, index=True)
    team_id = Column(Integer, nullable=True)                       # FK snapshot (nullable for safety)

    # Execution context
    triggered_by_user_id = Column(Integer, nullable=True)         # Admin user who ran it
    trigger_source = Column(String(32), nullable=False, default="api")  # "api", "scheduler", "webhook"

    # Payload & Output
    payload_json = Column(Text, nullable=True)                    # Input JSON passed to team
    output_json = Column(Text, nullable=True)                     # Final output JSON

    # Step-level detail (JSON list of PipelineStep-like dicts)
    steps_json = Column(Text, nullable=True)                      # [{name, status, duration_ms, error}, ...]

    # Result metadata
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_run_tenant_team", "tenant_id", "team_slug"),
        Index("ix_run_started_at", "started_at"),
        Index("ix_run_tenant_started", "tenant_id", "started_at"),
        Index("ix_run_tenant_success", "tenant_id", "success"),
    )
