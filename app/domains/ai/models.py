from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint

from app.core.db import Base, TenantScopedMixin


class TenantLLMConfig(Base, TenantScopedMixin):
    __tablename__ = "tenant_llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(String, nullable=False)
    provider_name = Column(String, nullable=False)
    model_id = Column(String, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ToolDefinition(Base):
    __tablename__ = "tool_definitions"

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    required_integration = Column(String, nullable=True)
    min_plan_tier = Column(String, nullable=False, default="starter")
    config_schema = Column(Text, nullable=True)
    is_system = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    default_tools = Column(Text, nullable=True)
    max_turns = Column(Integer, nullable=False, default=5)
    qa_profile = Column(String, nullable=True)
    min_plan_tier = Column(String, nullable=False, default="starter")
    is_system = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TenantAgentConfig(Base, TenantScopedMixin):
    __tablename__ = "tenant_agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agent_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    system_prompt_override = Column(Text, nullable=True)
    tool_overrides = Column(Text, nullable=True)
    extra_config = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_id", name="uq_swarm_tenant_agent_config"),
    )


class TenantToolConfig(Base, TenantScopedMixin):
    __tablename__ = "tenant_tool_configs"

    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(String, ForeignKey("tool_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    config = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "tool_id", name="uq_tenant_tool_config"),
    )


class AgentTeam(Base, TenantScopedMixin):
    __tablename__ = "agent_teams"

    id = Column(String(36), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    name = Column(String(64), nullable=False, index=True)
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    agent_ids = Column(JSON, nullable=False, default=list)
    orchestrator_name = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("name", "tenant_id", name="uq_agent_team_name_tenant"),
    )


__all__ = [
    "AgentDefinition",
    "AgentTeam",
    "TenantAgentConfig",
    "TenantLLMConfig",
    "TenantToolConfig",
    "ToolDefinition",
]
