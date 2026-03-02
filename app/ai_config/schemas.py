"""ARIIA AI Config Management – Pydantic Schemas.

Request/Response models for all AI configuration endpoints.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# LLM PROVIDER SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class LLMProviderCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64, description="Unique provider slug, e.g. 'openai'")
    name: str = Field(..., min_length=1, max_length=128, description="Display name, e.g. 'OpenAI'")
    provider_type: str = Field("openai_compatible", description="Protocol type: openai_compatible, gemini, anthropic")
    api_base_url: str = Field(..., description="Base URL for the provider API")
    api_key: Optional[str] = Field(None, description="Platform master API key (will be encrypted)")
    supported_models: list[str] = Field(default_factory=list, description="List of supported model IDs")
    default_model: Optional[str] = Field(None, description="Default model for this provider")
    is_active: bool = True
    priority: int = Field(100, ge=1, le=999, description="Lower = higher priority for fallback")
    max_retries: int = Field(2, ge=0, le=10)
    timeout_seconds: int = Field(60, ge=5, le=300)


class LLMProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    api_base_url: Optional[str] = None
    api_key: Optional[str] = Field(None, description="New API key (leave None to keep existing)")
    supported_models: Optional[list[str]] = None
    default_model: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    max_retries: Optional[int] = None
    timeout_seconds: Optional[int] = None


class LLMProviderResponse(BaseModel):
    id: int
    slug: str
    name: str
    provider_type: str
    api_base_url: str
    has_api_key: bool
    supported_models: list[str]
    default_model: Optional[str]
    is_active: bool
    priority: int
    max_retries: int
    timeout_seconds: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# TENANT LLM PROVIDER SCHEMAS (BYOK)
# ═══════════════════════════════════════════════════════════════════════════════

class TenantLLMProviderCreate(BaseModel):
    provider_id: int = Field(..., description="ID of the platform LLM provider")
    api_key: Optional[str] = Field(None, description="Tenant's own API key (BYOK)")
    preferred_model: Optional[str] = None
    is_active: bool = True
    priority: int = 100


class TenantLLMProviderUpdate(BaseModel):
    api_key: Optional[str] = None
    preferred_model: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class TenantLLMProviderResponse(BaseModel):
    id: int
    tenant_id: int
    provider_id: int
    provider_slug: str
    provider_name: str
    has_own_key: bool
    preferred_model: Optional[str]
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN BUDGET SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class PlanAIBudgetCreate(BaseModel):
    plan_id: int
    monthly_token_limit: Optional[int] = None
    monthly_budget_cents: Optional[int] = None
    requests_per_minute: Optional[int] = 60
    requests_per_day: Optional[int] = None
    max_tokens_per_request: int = 4096
    allowed_providers: Optional[list[str]] = None
    allowed_models: Optional[list[str]] = None
    overage_enabled: bool = False
    overage_cost_per_1k_tokens_cents: Optional[int] = None


class PlanAIBudgetUpdate(BaseModel):
    monthly_token_limit: Optional[int] = None
    monthly_budget_cents: Optional[int] = None
    requests_per_minute: Optional[int] = None
    requests_per_day: Optional[int] = None
    max_tokens_per_request: Optional[int] = None
    allowed_providers: Optional[list[str]] = None
    allowed_models: Optional[list[str]] = None
    overage_enabled: Optional[bool] = None
    overage_cost_per_1k_tokens_cents: Optional[int] = None


class PlanAIBudgetResponse(BaseModel):
    id: int
    plan_id: int
    monthly_token_limit: Optional[int]
    monthly_budget_cents: Optional[int]
    requests_per_minute: Optional[int]
    requests_per_day: Optional[int]
    max_tokens_per_request: int
    allowed_providers: Optional[list[str]]
    allowed_models: Optional[list[str]]
    overage_enabled: bool
    overage_cost_per_1k_tokens_cents: Optional[int]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT TEMPLATE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class PromptTemplateCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = None
    category: str = Field("agent", description="agent, persona, greeting, system")
    agent_type: Optional[str] = None


class PromptTemplateResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str]
    category: str
    agent_type: Optional[str]
    is_active: bool
    versions_count: int = 0
    active_version: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptVersionCreate(BaseModel):
    content: str = Field(..., min_length=1, description="The prompt template content (Jinja2)")
    variables: Optional[list[str]] = None
    change_notes: Optional[str] = None


class PromptVersionResponse(BaseModel):
    id: int
    template_id: int
    version: str
    content: str
    variables: Optional[list[str]]
    change_notes: Optional[str]
    created_by: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PromptDeployRequest(BaseModel):
    version_id: int
    environment: str = Field("production", description="dev, staging, production")
    tenant_id: Optional[int] = Field(None, description="NULL = platform default")


class PromptDeployResponse(BaseModel):
    id: int
    version_id: int
    version: str
    environment: str
    tenant_id: Optional[int]
    is_active: bool
    deployed_by: Optional[str]
    deployed_at: datetime

    class Config:
        from_attributes = True


class PromptTestRequest(BaseModel):
    content: str = Field(..., description="Prompt template content to test")
    variables: dict[str, str] = Field(default_factory=dict, description="Variable values for rendering")


class PromptTestResponse(BaseModel):
    rendered: str
    variables_used: list[str]
    token_estimate: int


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT DEFINITION SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class AgentDefinitionCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    agent_class: str = Field(..., description="Full Python class path")
    default_provider_slug: Optional[str] = None
    default_model: str = "gpt-4o-mini"
    default_temperature: float = Field(0.7, ge=0.0, le=2.0)
    default_max_tokens: int = Field(1000, ge=1, le=32000)
    default_tools: Optional[list[str]] = None
    prompt_template_slug: Optional[str] = None
    is_active: bool = True
    is_visible_to_tenants: bool = True


class AgentDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_provider_slug: Optional[str] = None
    default_model: Optional[str] = None
    default_temperature: Optional[float] = None
    default_max_tokens: Optional[int] = None
    default_tools: Optional[list[str]] = None
    prompt_template_slug: Optional[str] = None
    is_active: Optional[bool] = None
    is_visible_to_tenants: Optional[bool] = None


class AgentDefinitionResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str]
    agent_class: str
    default_provider_slug: Optional[str]
    default_model: str
    default_temperature: float
    default_max_tokens: int
    default_tools: Optional[list[str]]
    prompt_template_slug: Optional[str]
    is_active: bool
    is_visible_to_tenants: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantAgentConfigCreate(BaseModel):
    agent_definition_id: int
    override_provider_slug: Optional[str] = None
    override_model: Optional[str] = None
    override_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    override_max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    override_tools: Optional[list[str]] = None
    custom_display_name: Optional[str] = None
    custom_persona_text: Optional[str] = None
    is_enabled: bool = True


class TenantAgentConfigUpdate(BaseModel):
    override_provider_slug: Optional[str] = None
    override_model: Optional[str] = None
    override_temperature: Optional[float] = None
    override_max_tokens: Optional[int] = None
    override_tools: Optional[list[str]] = None
    custom_display_name: Optional[str] = None
    custom_persona_text: Optional[str] = None
    is_enabled: Optional[bool] = None


class TenantAgentConfigResponse(BaseModel):
    id: int
    tenant_id: int
    agent_definition_id: int
    agent_slug: str
    agent_name: str
    override_provider_slug: Optional[str]
    override_model: Optional[str]
    override_temperature: Optional[float]
    override_max_tokens: Optional[int]
    override_tools: Optional[list[str]]
    custom_display_name: Optional[str]
    custom_persona_text: Optional[str]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# RESOLVED CONFIG SCHEMA (for runtime use)
# ═══════════════════════════════════════════════════════════════════════════════

class ResolvedLLMConfig(BaseModel):
    """The fully resolved LLM configuration for a specific agent + tenant.

    Represents the final merged result of: Agent Default → Plan Limits → Tenant Override.
    """
    provider_slug: str
    provider_type: str
    api_base_url: str
    api_key: str  # Decrypted key (never exposed via API)
    model: str
    temperature: float
    max_tokens: int
    is_byok: bool = False  # True if tenant's own key is used
    budget_remaining_tokens: Optional[int] = None
    budget_remaining_cents: Optional[int] = None


class AIConfigAuditLogResponse(BaseModel):
    id: int
    tenant_id: Optional[int]
    actor_email: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
