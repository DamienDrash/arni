"""ARIIA AI Config Management – Database Models.

Defines the complete data model for the refactored AI configuration system:
- LLM Provider Registry (platform-level)
- Tenant LLM Configurations (BYOK)
- Plan Budget Controls
- Prompt Templates & Versions (versioned, immutable)
- Prompt Deployments (environment-based)
- Agent Definitions & Tenant Overrides
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, Float,
    ForeignKey, UniqueConstraint, Index, JSON,
)
from app.core.db import Base


# ═══════════════════════════════════════════════════════════════════════════════
# 1. LLM PROVIDER REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

class LLMProvider(Base):
    """Platform-level catalog of available LLM providers.

    Stores the master configuration for each provider (OpenAI, Anthropic, etc.)
    including the base URL, supported models, and the encrypted platform API key.
    """
    __tablename__ = "ai_llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)  # "openai", "anthropic"
    name = Column(String(128), nullable=False)                          # "OpenAI"
    provider_type = Column(String(32), nullable=False, default="openai_compatible")  # openai_compatible, gemini, anthropic
    api_base_url = Column(String(512), nullable=False)                  # "https://api.openai.com/v1"
    api_key_encrypted = Column(Text, nullable=True)                     # Platform master key (encrypted)
    supported_models_json = Column(Text, nullable=True)                 # JSON: ["gpt-4o", "gpt-4o-mini", ...]
    default_model = Column(String(128), nullable=True)                  # Default model for this provider
    is_active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=100)             # Lower = higher priority for fallback
    max_retries = Column(Integer, nullable=False, default=2)
    timeout_seconds = Column(Integer, nullable=False, default=60)
    metadata_json = Column(Text, nullable=True)                         # Extra config (headers, etc.)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class TenantLLMProvider(Base):
    """Tenant-specific LLM provider configuration (BYOK – Bring Your Own Key).

    Allows tenants to override the platform provider with their own API keys
    and model preferences. Implements hierarchical config resolution:
    Tenant Override → Plan Default → Platform Default.
    """
    __tablename__ = "ai_tenant_llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("ai_llm_providers.id"), nullable=False)
    api_key_encrypted = Column(Text, nullable=True)                     # Tenant's own key (encrypted)
    preferred_model = Column(String(128), nullable=True)                # Tenant's preferred model
    is_active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=100)             # Tenant-level priority

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_id", name="uq_tenant_llm_provider"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PLAN BUDGET CONTROLS
# ═══════════════════════════════════════════════════════════════════════════════

class PlanAIBudget(Base):
    """AI budget and rate limits per subscription plan.

    Defines the monthly token budget, cost ceiling, and rate limits
    for each plan tier (Starter, Pro, Enterprise).
    """
    __tablename__ = "ai_plan_budgets"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False, unique=True)
    monthly_token_limit = Column(Integer, nullable=True)                # NULL = unlimited
    monthly_budget_cents = Column(Integer, nullable=True)               # Budget in USD cents, NULL = unlimited
    requests_per_minute = Column(Integer, nullable=True, default=60)    # Rate limit
    requests_per_day = Column(Integer, nullable=True)                   # Daily limit
    max_tokens_per_request = Column(Integer, nullable=False, default=4096)
    allowed_providers_json = Column(Text, nullable=True)                # JSON: ["openai", "anthropic"] or NULL = all
    allowed_models_json = Column(Text, nullable=True)                   # JSON: ["gpt-4o-mini"] or NULL = all
    overage_enabled = Column(Boolean, nullable=False, default=False)    # Allow overage billing
    overage_cost_per_1k_tokens_cents = Column(Integer, nullable=True)   # Overage price

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class TenantAIBudgetOverride(Base):
    """Tenant-specific budget overrides (e.g., custom enterprise deals)."""
    __tablename__ = "ai_tenant_budget_overrides"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True)
    monthly_token_limit = Column(Integer, nullable=True)
    monthly_budget_cents = Column(Integer, nullable=True)
    requests_per_minute = Column(Integer, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)                                # "Enterprise deal Q1 2026"

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PROMPT MANAGEMENT (Versioned)
# ═══════════════════════════════════════════════════════════════════════════════

class PromptTemplate(Base):
    """Master record for a prompt template.

    Each template has a unique slug (e.g., "sales/system", "persona/greeting")
    and can have multiple immutable versions.
    """
    __tablename__ = "ai_prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(128), unique=True, nullable=False, index=True)  # "sales/system", "router/system"
    name = Column(String(256), nullable=False)                           # "Sales Agent System Prompt"
    description = Column(Text, nullable=True)
    category = Column(String(64), nullable=False, default="agent")       # agent, persona, greeting, system
    agent_type = Column(String(64), nullable=True)                       # "sales", "ops", "medic", "persona", "router"
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class PromptVersion(Base):
    """Immutable version of a prompt template.

    Once created, a version's content cannot be changed. New edits create
    new versions. Supports semantic versioning (v1.0.0, v1.1.0, etc.).
    """
    __tablename__ = "ai_prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("ai_prompt_templates.id"), nullable=False, index=True)
    version = Column(String(32), nullable=False)                         # "1.0.0", "1.1.0"
    content = Column(Text, nullable=False)                               # The actual prompt text (Jinja2)
    variables_json = Column(Text, nullable=True)                         # JSON: ["studio_name", "agent_display_name"]
    change_notes = Column(Text, nullable=True)                           # "Improved retention strategy"
    created_by = Column(String(256), nullable=True)                      # Email of creator
    status = Column(String(32), nullable=False, default="draft")         # draft, published, archived

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_prompt_version"),
    )


class PromptDeployment(Base):
    """Links a prompt version to an environment and optionally a tenant.

    Enables environment-based deployment (dev → staging → prod) and
    tenant-specific prompt overrides.
    """
    __tablename__ = "ai_prompt_deployments"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("ai_prompt_versions.id"), nullable=False)
    environment = Column(String(32), nullable=False, default="production")  # dev, staging, production
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)    # NULL = platform default
    is_active = Column(Boolean, nullable=False, default=True)
    deployed_by = Column(String(256), nullable=True)
    deployed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Only one active deployment per template+environment+tenant
        Index("ix_prompt_deploy_lookup", "version_id", "environment", "tenant_id"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. AGENT CONFIGURATION REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

class AgentDefinition(Base):
    """Catalog of all available AI agent types.

    Stores the default configuration for each agent (model, temperature,
    tools, etc.). This is the "Agent Card" in the registry pattern.
    """
    __tablename__ = "ai_agent_definitions"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)   # "sales", "ops", "medic", "persona"
    name = Column(String(128), nullable=False)                           # "Sales & Retention Agent"
    description = Column(Text, nullable=True)
    agent_class = Column(String(256), nullable=False)                    # "app.swarm.agents.sales.AgentSales"
    default_provider_slug = Column(String(64), nullable=True)            # "openai" (FK-like reference)
    default_model = Column(String(128), nullable=False, default="gpt-4o-mini")
    default_temperature = Column(Float, nullable=False, default=0.7)
    default_max_tokens = Column(Integer, nullable=False, default=1000)
    default_tools_json = Column(Text, nullable=True)                     # JSON: ["knowledge_base", "magicline"]
    prompt_template_slug = Column(String(128), nullable=True)            # FK-like to ai_prompt_templates.slug
    is_active = Column(Boolean, nullable=False, default=True)
    is_visible_to_tenants = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class TenantAgentConfig(Base):
    """Tenant-specific overrides for agent configuration.

    Allows tenants to customize agent behavior (model, temperature, tools,
    display name) without modifying the global agent definition.
    """
    __tablename__ = "ai_tenant_agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    agent_definition_id = Column(Integer, ForeignKey("ai_agent_definitions.id"), nullable=False)
    override_provider_slug = Column(String(64), nullable=True)
    override_model = Column(String(128), nullable=True)
    override_temperature = Column(Float, nullable=True)
    override_max_tokens = Column(Integer, nullable=True)
    override_tools_json = Column(Text, nullable=True)
    custom_display_name = Column(String(128), nullable=True)             # Tenant's custom agent name
    custom_persona_text = Column(Text, nullable=True)                    # Tenant's custom persona
    is_enabled = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_definition_id", name="uq_tenant_agent_config"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. AI CONFIGURATION AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════════

class AIConfigAuditLog(Base):
    """Audit trail for all AI configuration changes.

    Records who changed what, when, and the before/after values.
    """
    __tablename__ = "ai_config_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    actor_email = Column(String(256), nullable=True)
    action = Column(String(64), nullable=False, index=True)              # "provider.created", "prompt.deployed", etc.
    entity_type = Column(String(64), nullable=False)                     # "provider", "prompt", "agent", "budget"
    entity_id = Column(Integer, nullable=True)
    before_json = Column(Text, nullable=True)                            # JSON snapshot before change
    after_json = Column(Text, nullable=True)                             # JSON snapshot after change
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
