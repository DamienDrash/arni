from app.core.models import (
    AgentDefinition,
    AgentTeam,
    TenantAgentConfig,
    TenantLLMConfig,
    TenantToolConfig,
    ToolDefinition,
)
from app.domains.ai.models import (
    AgentDefinition as DomainAgentDefinition,
    AgentTeam as DomainAgentTeam,
    TenantAgentConfig as DomainTenantAgentConfig,
    TenantLLMConfig as DomainTenantLLMConfig,
    TenantToolConfig as DomainTenantToolConfig,
    ToolDefinition as DomainToolDefinition,
)


def test_core_models_reexports_ai_domain_models() -> None:
    assert TenantLLMConfig is DomainTenantLLMConfig
    assert ToolDefinition is DomainToolDefinition
    assert AgentDefinition is DomainAgentDefinition
    assert TenantAgentConfig is DomainTenantAgentConfig
    assert TenantToolConfig is DomainTenantToolConfig
    assert AgentTeam is DomainAgentTeam


def test_ai_models_keep_legacy_table_names() -> None:
    assert TenantLLMConfig.__tablename__ == "tenant_llm_configs"
    assert ToolDefinition.__tablename__ == "tool_definitions"
    assert AgentDefinition.__tablename__ == "agent_definitions"
    assert TenantAgentConfig.__tablename__ == "tenant_agent_configs"
    assert TenantToolConfig.__tablename__ == "tenant_tool_configs"
    assert AgentTeam.__tablename__ == "agent_teams"
