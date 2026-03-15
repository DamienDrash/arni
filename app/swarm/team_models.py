"""app/swarm/team_models.py — Agent Team Configuration Models.

DB models for the Agent Team Management System:
- AgentTeamConfig: Team definition with pipeline/orchestrator mode
- AgentTeamStep: Ordered steps in a pipeline team
- AgentToolDefinition: Tool/skill registry (global builtins + tenant-scoped custom tools)
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, UniqueConstraint, Index, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base


class AgentTeamConfig(Base):
    """Team definition — Source of Truth for a named agent pipeline or orchestrator."""
    __tablename__ = "agent_team_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)

    slug = Column(String(64), nullable=False, index=True)      # "campaign-generation"
    name = Column(String(128), nullable=False)                 # "Campaign Generation"
    description = Column(Text, nullable=True)

    lead_agent_slug = Column(String(64), nullable=True)        # "marketing_agent" or "ops"
    execution_mode = Column(String(32), nullable=False, default="pipeline")
    # "pipeline"     → generic sequential execution via DBDelegatingTeam
    # "orchestrator" → delegates to existing CampaignOrchestrator / MediaOrchestrator

    input_schema_json = Column(Text, nullable=True)           # JSON Schema for run payload
    yaml_version = Column(Integer, nullable=False, default=1) # Bumped on every save
    is_active = Column(Boolean, nullable=False, default=True)
    is_system = Column(Boolean, nullable=False, default=False) # True = seeded system team

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationship — cascade deletes steps when team is deleted
    steps = relationship(
        "AgentTeamStep",
        back_populates="team",
        cascade="all, delete-orphan",
        order_by="AgentTeamStep.step_order",
        lazy="select",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_agent_team_tenant_slug"),
        Index("ix_agent_team_tenant_active", "tenant_id", "is_active"),
    )


class AgentTeamStep(Base):
    """A single ordered step in an agent pipeline team."""
    __tablename__ = "agent_team_steps"

    id = Column(Integer, primary_key=True, index=True)
    # FK with CASCADE — deleting a team removes its steps automatically
    team_id = Column(
        Integer,
        ForeignKey("agent_team_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order = Column(Integer, nullable=False, default=0)    # 0-indexed, determines execution order

    agent_slug = Column(String(64), nullable=False)            # "sales", "ops", "marketing_agent"
    display_name = Column(String(128), nullable=True)          # Override label in UI

    tools_json = Column(Text, nullable=True)                   # JSON list: ["knowledge_base", "magicline"]
    prompt_override = Column(Text, nullable=True)              # System prompt override for this step
    model_override = Column(String(128), nullable=True)        # "gpt-4o" — overrides agent default

    is_optional = Column(Boolean, nullable=False, default=False)  # Step can fail without aborting run

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    team = relationship("AgentTeamConfig", back_populates="steps")

    __table_args__ = (
        UniqueConstraint("team_id", "step_order", name="uq_step_team_order"),
        Index("ix_step_team_id_order", "team_id", "step_order"),
    )


class AgentToolDefinition(Base):
    """Registry of available tools/skills assignable to pipeline steps.

    tenant_id = NULL  → global builtin (ships with ARIIA, all tenants can use)
    tenant_id = <id>  → tenant-scoped custom tool (only visible to that tenant)
    """
    __tablename__ = "agent_tool_definitions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)     # NULL = global builtin

    slug = Column(String(64), nullable=False, index=True)      # "knowledge_base"
    name = Column(String(128), nullable=False)                 # "Knowledge Base Search"
    description = Column(Text, nullable=True)
    tool_class = Column(String(256), nullable=True)            # "app.swarm.tools.knowledge_base.KnowledgeBaseTool"
    config_schema_json = Column(Text, nullable=True)           # JSON Schema for config

    is_builtin = Column(Boolean, nullable=False, default=True)  # True = ships with ARIIA
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Unique slug per tenant; NULL tenant_id = global scope.
        # Note: SQL NULL != NULL, so two global builtins with the same slug would NOT be caught
        # by this constraint — that case is prevented at application level in seed_tools().
        UniqueConstraint("tenant_id", "slug", name="uq_tool_tenant_slug"),
        Index("ix_tool_tenant_active", "tenant_id", "is_active"),
    )
