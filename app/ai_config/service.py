"""ARIIA AI Config Management – Service Layer.

Central business logic for AI configuration management.
Implements hierarchical config resolution, CRUD operations,
budget enforcement, and audit logging.
"""

from __future__ import annotations
import json
import time
import structlog
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy.orm import Session

from app.ai_config.models import (
    LLMProvider, TenantLLMProvider, PlanAIBudget, TenantAIBudgetOverride,
    PromptTemplate, PromptVersion, PromptDeployment,
    AgentDefinition, TenantAgentConfig, AIConfigAuditLog,
)
from app.ai_config.schemas import ResolvedLLMConfig
from app.ai_config.encryption import encrypt_api_key, decrypt_api_key
from app.domains.billing.models import Plan, Subscription, UsageRecord

logger = structlog.get_logger()

# ── In-Memory Cache ───────────────────────────────────────────────────────────
_provider_cache: dict[str, LLMProvider] = {}
_provider_cache_ts: float = 0.0
_agent_cache: dict[str, AgentDefinition] = {}
_agent_cache_ts: float = 0.0
CACHE_TTL = 120  # 2 minutes


class AIConfigService:
    """Central service for AI configuration management.

    All database operations go through this service. The service handles
    encryption, caching, audit logging, and hierarchical resolution.
    """

    def __init__(self, db: Session):
        self.db = db

    # ═══════════════════════════════════════════════════════════════════════
    # LLM PROVIDER MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def list_providers(self, active_only: bool = False) -> list[LLMProvider]:
        """List all LLM providers, optionally filtered by active status."""
        q = self.db.query(LLMProvider)
        if active_only:
            q = q.filter(LLMProvider.is_active.is_(True))
        return q.order_by(LLMProvider.priority.asc()).all()

    def get_provider(self, provider_id: int) -> Optional[LLMProvider]:
        return self.db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()

    def get_provider_by_slug(self, slug: str) -> Optional[LLMProvider]:
        return self.db.query(LLMProvider).filter(LLMProvider.slug == slug).first()

    def create_provider(self, data: dict, actor_email: str = None) -> LLMProvider:
        """Create a new LLM provider with encrypted API key."""
        api_key = data.pop("api_key", None)
        models_list = data.pop("supported_models", [])

        provider = LLMProvider(
            slug=data["slug"],
            name=data["name"],
            provider_type=data.get("provider_type", "openai_compatible"),
            api_base_url=data["api_base_url"],
            api_key_encrypted=encrypt_api_key(api_key) if api_key else None,
            supported_models_json=json.dumps(models_list) if models_list else None,
            default_model=data.get("default_model"),
            is_active=data.get("is_active", True),
            priority=data.get("priority", 100),
            max_retries=data.get("max_retries", 2),
            timeout_seconds=data.get("timeout_seconds", 60),
        )
        self.db.add(provider)
        self.db.flush()

        self._audit("provider.created", "provider", provider.id, None, self._provider_to_dict(provider), actor_email)
        self.db.commit()
        self._invalidate_provider_cache()
        return provider

    def update_provider(self, provider_id: int, data: dict, actor_email: str = None) -> Optional[LLMProvider]:
        """Update an existing LLM provider."""
        provider = self.get_provider(provider_id)
        if not provider:
            return None

        before = self._provider_to_dict(provider)

        if "api_key" in data and data["api_key"] is not None:
            provider.api_key_encrypted = encrypt_api_key(data.pop("api_key"))
        elif "api_key" in data:
            data.pop("api_key")

        if "supported_models" in data and data["supported_models"] is not None:
            provider.supported_models_json = json.dumps(data.pop("supported_models"))
        elif "supported_models" in data:
            data.pop("supported_models")

        for key, value in data.items():
            if value is not None and hasattr(provider, key):
                setattr(provider, key, value)

        self._audit("provider.updated", "provider", provider.id, before, self._provider_to_dict(provider), actor_email)
        self.db.commit()
        self._invalidate_provider_cache()
        return provider

    def delete_provider(self, provider_id: int, actor_email: str = None) -> bool:
        """Delete an LLM provider (soft-delete by deactivating)."""
        provider = self.get_provider(provider_id)
        if not provider:
            return False

        before = self._provider_to_dict(provider)
        provider.is_active = False
        self._audit("provider.deleted", "provider", provider.id, before, None, actor_email)
        self.db.commit()
        self._invalidate_provider_cache()
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # TENANT LLM PROVIDER (BYOK)
    # ═══════════════════════════════════════════════════════════════════════

    def list_tenant_providers(self, tenant_id: int) -> list[dict]:
        """List all LLM providers configured for a tenant (with platform info)."""
        rows = (
            self.db.query(TenantLLMProvider, LLMProvider)
            .join(LLMProvider, TenantLLMProvider.provider_id == LLMProvider.id)
            .filter(TenantLLMProvider.tenant_id == tenant_id)
            .order_by(TenantLLMProvider.priority.asc())
            .all()
        )
        results = []
        for tp, p in rows:
            results.append({
                "id": tp.id,
                "tenant_id": tp.tenant_id,
                "provider_id": tp.provider_id,
                "provider_slug": p.slug,
                "provider_name": p.name,
                "has_own_key": bool(tp.api_key_encrypted),
                "preferred_model": tp.preferred_model,
                "is_active": tp.is_active,
                "priority": tp.priority,
                "created_at": tp.created_at,
                "updated_at": tp.updated_at,
            })
        return results

    def create_tenant_provider(self, tenant_id: int, data: dict, actor_email: str = None) -> TenantLLMProvider:
        """Add a provider configuration for a tenant."""
        api_key = data.pop("api_key", None)
        tp = TenantLLMProvider(
            tenant_id=tenant_id,
            provider_id=data["provider_id"],
            api_key_encrypted=encrypt_api_key(api_key) if api_key else None,
            preferred_model=data.get("preferred_model"),
            is_active=data.get("is_active", True),
            priority=data.get("priority", 100),
        )
        self.db.add(tp)
        self.db.flush()
        self._audit("tenant_provider.created", "tenant_provider", tp.id, None, {"tenant_id": tenant_id, "provider_id": data["provider_id"]}, actor_email, tenant_id)
        self.db.commit()
        return tp

    def update_tenant_provider(self, tenant_id: int, tp_id: int, data: dict, actor_email: str = None) -> Optional[TenantLLMProvider]:
        """Update a tenant's provider configuration."""
        tp = self.db.query(TenantLLMProvider).filter(
            TenantLLMProvider.id == tp_id,
            TenantLLMProvider.tenant_id == tenant_id,
        ).first()
        if not tp:
            return None

        if "api_key" in data and data["api_key"] is not None:
            tp.api_key_encrypted = encrypt_api_key(data.pop("api_key"))
        elif "api_key" in data:
            data.pop("api_key")

        for key, value in data.items():
            if value is not None and hasattr(tp, key):
                setattr(tp, key, value)

        self._audit("tenant_provider.updated", "tenant_provider", tp.id, None, {"tenant_id": tenant_id}, actor_email, tenant_id)
        self.db.commit()
        return tp

    def delete_tenant_provider(self, tenant_id: int, tp_id: int, actor_email: str = None) -> bool:
        """Remove a tenant's provider configuration."""
        tp = self.db.query(TenantLLMProvider).filter(
            TenantLLMProvider.id == tp_id,
            TenantLLMProvider.tenant_id == tenant_id,
        ).first()
        if not tp:
            return False
        self._audit("tenant_provider.deleted", "tenant_provider", tp.id, {"tenant_id": tenant_id}, None, actor_email, tenant_id)
        self.db.delete(tp)
        self.db.commit()
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # HIERARCHICAL CONFIG RESOLUTION
    # ═══════════════════════════════════════════════════════════════════════

    def resolve_llm_config(
        self,
        tenant_id: int,
        agent_slug: Optional[str] = None,
    ) -> ResolvedLLMConfig:
        """Resolve the effective LLM configuration for a tenant + agent.

        Resolution hierarchy (highest priority first):
        1. Tenant Agent Override (ai_tenant_agent_configs)
        2. Tenant Provider Override (ai_tenant_llm_providers)
        3. Agent Definition Default (ai_agent_definitions)
        4. Plan Budget Constraints (ai_plan_budgets)
        5. Platform Provider Default (ai_llm_providers)

        Returns a fully resolved config with decrypted API key.
        """
        # Step 1: Get agent definition defaults
        agent_def = None
        if agent_slug:
            agent_def = self.db.query(AgentDefinition).filter(
                AgentDefinition.slug == agent_slug,
                AgentDefinition.is_active.is_(True),
            ).first()

        default_provider_slug = agent_def.default_provider_slug if agent_def else None
        default_model = agent_def.default_model if agent_def else "gpt-4o-mini"
        default_temperature = agent_def.default_temperature if agent_def else 0.7
        default_max_tokens = agent_def.default_max_tokens if agent_def else 1000

        # Step 2: Check tenant agent override
        tenant_agent = None
        if agent_def:
            tenant_agent = self.db.query(TenantAgentConfig).filter(
                TenantAgentConfig.tenant_id == tenant_id,
                TenantAgentConfig.agent_definition_id == agent_def.id,
                TenantAgentConfig.is_enabled.is_(True),
            ).first()

        if tenant_agent:
            if tenant_agent.override_provider_slug:
                default_provider_slug = tenant_agent.override_provider_slug
            if tenant_agent.override_model:
                default_model = tenant_agent.override_model
            if tenant_agent.override_temperature is not None:
                default_temperature = tenant_agent.override_temperature
            if tenant_agent.override_max_tokens is not None:
                default_max_tokens = tenant_agent.override_max_tokens

        # Step 3: Resolve provider (tenant BYOK → platform default)
        is_byok = False
        api_key = ""
        provider = None

        # Check tenant-specific provider first
        if default_provider_slug:
            platform_provider = self.get_provider_by_slug(default_provider_slug)
            if platform_provider:
                tenant_provider = self.db.query(TenantLLMProvider).filter(
                    TenantLLMProvider.tenant_id == tenant_id,
                    TenantLLMProvider.provider_id == platform_provider.id,
                    TenantLLMProvider.is_active.is_(True),
                ).first()

                if tenant_provider and tenant_provider.api_key_encrypted:
                    api_key = decrypt_api_key(tenant_provider.api_key_encrypted)
                    is_byok = True
                    if tenant_provider.preferred_model:
                        default_model = tenant_provider.preferred_model
                    provider = platform_provider
                elif platform_provider.api_key_encrypted:
                    api_key = decrypt_api_key(platform_provider.api_key_encrypted)
                    provider = platform_provider

        # Fallback: first active platform provider
        if not provider:
            provider = self.db.query(LLMProvider).filter(
                LLMProvider.is_active.is_(True),
            ).order_by(LLMProvider.priority.asc()).first()

            if provider:
                default_provider_slug = provider.slug
                if not default_model:
                    default_model = provider.default_model or "gpt-4o-mini"
                if provider.api_key_encrypted:
                    api_key = decrypt_api_key(provider.api_key_encrypted)

        if not provider:
            # Ultimate fallback to env variable
            from config.settings import get_settings
            settings = get_settings()
            return ResolvedLLMConfig(
                provider_slug="openai",
                provider_type="openai_compatible",
                api_base_url="https://api.openai.com/v1",
                api_key=settings.openai_api_key,
                model=default_model or "gpt-4o-mini",
                temperature=default_temperature,
                max_tokens=default_max_tokens,
                is_byok=False,
            )

        # Step 4: Apply plan budget constraints
        budget_remaining_tokens = None
        budget_remaining_cents = None
        sub = self.db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
        if sub:
            plan_budget = self.db.query(PlanAIBudget).filter(PlanAIBudget.plan_id == sub.plan_id).first()
            if plan_budget:
                if plan_budget.max_tokens_per_request:
                    default_max_tokens = min(default_max_tokens, plan_budget.max_tokens_per_request)

                # Check budget override
                override = self.db.query(TenantAIBudgetOverride).filter(
                    TenantAIBudgetOverride.tenant_id == tenant_id,
                ).first()
                effective_token_limit = override.monthly_token_limit if override and override.monthly_token_limit else plan_budget.monthly_token_limit

                if effective_token_limit:
                    now = datetime.now(timezone.utc)
                    usage = self.db.query(UsageRecord).filter(
                        UsageRecord.tenant_id == tenant_id,
                        UsageRecord.period_year == now.year,
                        UsageRecord.period_month == now.month,
                    ).first()
                    used_tokens = usage.llm_tokens_used if usage else 0
                    budget_remaining_tokens = max(0, effective_token_limit - used_tokens)

        return ResolvedLLMConfig(
            provider_slug=provider.slug,
            provider_type=provider.provider_type,
            api_base_url=provider.api_base_url,
            api_key=api_key,
            model=default_model,
            temperature=default_temperature,
            max_tokens=default_max_tokens,
            is_byok=is_byok,
            budget_remaining_tokens=budget_remaining_tokens,
            budget_remaining_cents=budget_remaining_cents,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # PLAN BUDGET MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def get_plan_budget(self, plan_id: int) -> Optional[PlanAIBudget]:
        return self.db.query(PlanAIBudget).filter(PlanAIBudget.plan_id == plan_id).first()

    def list_plan_budgets(self) -> list[PlanAIBudget]:
        return self.db.query(PlanAIBudget).all()

    def upsert_plan_budget(self, data: dict, actor_email: str = None) -> PlanAIBudget:
        """Create or update a plan's AI budget."""
        plan_id = data["plan_id"]
        budget = self.get_plan_budget(plan_id)

        allowed_providers = data.pop("allowed_providers", None)
        allowed_models = data.pop("allowed_models", None)

        if budget:
            before = {"plan_id": plan_id}
            for key, value in data.items():
                if value is not None and hasattr(budget, key) and key != "plan_id":
                    setattr(budget, key, value)
            if allowed_providers is not None:
                budget.allowed_providers_json = json.dumps(allowed_providers)
            if allowed_models is not None:
                budget.allowed_models_json = json.dumps(allowed_models)
            self._audit("budget.updated", "budget", budget.id, before, data, actor_email)
        else:
            budget = PlanAIBudget(
                plan_id=plan_id,
                monthly_token_limit=data.get("monthly_token_limit"),
                monthly_budget_cents=data.get("monthly_budget_cents"),
                requests_per_minute=data.get("requests_per_minute", 60),
                requests_per_day=data.get("requests_per_day"),
                max_tokens_per_request=data.get("max_tokens_per_request", 4096),
                allowed_providers_json=json.dumps(allowed_providers) if allowed_providers else None,
                allowed_models_json=json.dumps(allowed_models) if allowed_models else None,
                overage_enabled=data.get("overage_enabled", False),
                overage_cost_per_1k_tokens_cents=data.get("overage_cost_per_1k_tokens_cents"),
            )
            self.db.add(budget)
            self.db.flush()
            self._audit("budget.created", "budget", budget.id, None, data, actor_email)

        self.db.commit()
        return budget

    # ═══════════════════════════════════════════════════════════════════════
    # PROMPT MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def list_prompt_templates(self, category: Optional[str] = None) -> list[PromptTemplate]:
        q = self.db.query(PromptTemplate).filter(PromptTemplate.is_active.is_(True))
        if category:
            q = q.filter(PromptTemplate.category == category)
        return q.order_by(PromptTemplate.slug.asc()).all()

    def get_prompt_template(self, template_id: int) -> Optional[PromptTemplate]:
        return self.db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()

    def get_prompt_template_by_slug(self, slug: str) -> Optional[PromptTemplate]:
        return self.db.query(PromptTemplate).filter(PromptTemplate.slug == slug).first()

    def create_prompt_template(self, data: dict, actor_email: str = None) -> PromptTemplate:
        template = PromptTemplate(
            slug=data["slug"],
            name=data["name"],
            description=data.get("description"),
            category=data.get("category", "agent"),
            agent_type=data.get("agent_type"),
        )
        self.db.add(template)
        self.db.flush()
        self._audit("prompt.created", "prompt", template.id, None, data, actor_email)
        self.db.commit()
        return template

    def create_prompt_version(self, template_id: int, data: dict, actor_email: str = None) -> PromptVersion:
        """Create a new immutable version for a prompt template.

        Auto-increments the version number (1.0.0 → 1.1.0 → 1.2.0).
        """
        # Determine next version
        latest = (
            self.db.query(PromptVersion)
            .filter(PromptVersion.template_id == template_id)
            .order_by(PromptVersion.created_at.desc())
            .first()
        )

        if latest:
            parts = latest.version.split(".")
            try:
                parts[1] = str(int(parts[1]) + 1)
                next_version = ".".join(parts)
            except (IndexError, ValueError):
                next_version = "1.1.0"
        else:
            next_version = "1.0.0"

        variables = data.pop("variables", None)
        version = PromptVersion(
            template_id=template_id,
            version=next_version,
            content=data["content"],
            variables_json=json.dumps(variables) if variables else None,
            change_notes=data.get("change_notes"),
            created_by=actor_email,
            status="draft",
        )
        self.db.add(version)
        self.db.flush()
        self._audit("prompt_version.created", "prompt_version", version.id, None, {"version": next_version, "template_id": template_id}, actor_email)
        self.db.commit()
        return version

    def list_prompt_versions(self, template_id: int) -> list[PromptVersion]:
        return (
            self.db.query(PromptVersion)
            .filter(PromptVersion.template_id == template_id)
            .order_by(PromptVersion.created_at.desc())
            .all()
        )

    def publish_prompt_version(self, version_id: int, actor_email: str = None) -> Optional[PromptVersion]:
        """Mark a version as published."""
        version = self.db.query(PromptVersion).filter(PromptVersion.id == version_id).first()
        if not version:
            return None
        version.status = "published"
        self._audit("prompt_version.published", "prompt_version", version.id, {"status": "draft"}, {"status": "published"}, actor_email)
        self.db.commit()
        return version

    def deploy_prompt(self, data: dict, actor_email: str = None) -> PromptDeployment:
        """Deploy a prompt version to an environment.

        Deactivates any existing deployment for the same template+env+tenant.
        """
        version = self.db.query(PromptVersion).filter(PromptVersion.id == data["version_id"]).first()
        if not version:
            raise ValueError(f"Prompt version {data['version_id']} not found")

        # Deactivate existing deployments for same template+env+tenant
        existing = (
            self.db.query(PromptDeployment)
            .join(PromptVersion, PromptDeployment.version_id == PromptVersion.id)
            .filter(
                PromptVersion.template_id == version.template_id,
                PromptDeployment.environment == data.get("environment", "production"),
                PromptDeployment.tenant_id == data.get("tenant_id"),
                PromptDeployment.is_active.is_(True),
            )
            .all()
        )
        for dep in existing:
            dep.is_active = False

        deployment = PromptDeployment(
            version_id=data["version_id"],
            environment=data.get("environment", "production"),
            tenant_id=data.get("tenant_id"),
            is_active=True,
            deployed_by=actor_email,
        )
        self.db.add(deployment)
        self.db.flush()
        self._audit("prompt.deployed", "prompt_deployment", deployment.id, None, {"version_id": data["version_id"], "environment": data.get("environment", "production")}, actor_email, data.get("tenant_id"))
        self.db.commit()
        return deployment

    def resolve_prompt(self, template_slug: str, tenant_id: Optional[int] = None, environment: str = "production") -> Optional[PromptVersion]:
        """Resolve the active prompt version for a template + environment + tenant.

        Resolution order:
        1. Tenant-specific deployment for this environment
        2. Platform default deployment for this environment
        3. Latest published version
        """
        template = self.get_prompt_template_by_slug(template_slug)
        if not template:
            return None

        # 1. Tenant-specific deployment
        if tenant_id:
            deployment = (
                self.db.query(PromptDeployment)
                .join(PromptVersion, PromptDeployment.version_id == PromptVersion.id)
                .filter(
                    PromptVersion.template_id == template.id,
                    PromptDeployment.environment == environment,
                    PromptDeployment.tenant_id == tenant_id,
                    PromptDeployment.is_active.is_(True),
                )
                .order_by(PromptDeployment.deployed_at.desc())
                .first()
            )
            if deployment:
                return self.db.query(PromptVersion).filter(PromptVersion.id == deployment.version_id).first()

        # 2. Platform default deployment
        deployment = (
            self.db.query(PromptDeployment)
            .join(PromptVersion, PromptDeployment.version_id == PromptVersion.id)
            .filter(
                PromptVersion.template_id == template.id,
                PromptDeployment.environment == environment,
                PromptDeployment.tenant_id.is_(None),
                PromptDeployment.is_active.is_(True),
            )
            .order_by(PromptDeployment.deployed_at.desc())
            .first()
        )
        if deployment:
            return self.db.query(PromptVersion).filter(PromptVersion.id == deployment.version_id).first()

        # 3. Latest published version
        return (
            self.db.query(PromptVersion)
            .filter(
                PromptVersion.template_id == template.id,
                PromptVersion.status == "published",
            )
            .order_by(PromptVersion.created_at.desc())
            .first()
        )

    # ═══════════════════════════════════════════════════════════════════════
    # AGENT DEFINITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def list_agent_definitions(self, active_only: bool = False) -> list[AgentDefinition]:
        q = self.db.query(AgentDefinition)
        if active_only:
            q = q.filter(AgentDefinition.is_active.is_(True))
        return q.order_by(AgentDefinition.slug.asc()).all()

    def get_agent_definition(self, agent_id: int) -> Optional[AgentDefinition]:
        return self.db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()

    def get_agent_definition_by_slug(self, slug: str) -> Optional[AgentDefinition]:
        return self.db.query(AgentDefinition).filter(AgentDefinition.slug == slug).first()

    def create_agent_definition(self, data: dict, actor_email: str = None) -> AgentDefinition:
        tools = data.pop("default_tools", None)
        agent = AgentDefinition(
            slug=data["slug"],
            name=data["name"],
            description=data.get("description"),
            agent_class=data["agent_class"],
            default_provider_slug=data.get("default_provider_slug"),
            default_model=data.get("default_model", "gpt-4o-mini"),
            default_temperature=data.get("default_temperature", 0.7),
            default_max_tokens=data.get("default_max_tokens", 1000),
            default_tools_json=json.dumps(tools) if tools else None,
            prompt_template_slug=data.get("prompt_template_slug"),
            is_active=data.get("is_active", True),
            is_visible_to_tenants=data.get("is_visible_to_tenants", True),
        )
        self.db.add(agent)
        self.db.flush()
        self._audit("agent.created", "agent", agent.id, None, data, actor_email)
        self.db.commit()
        self._invalidate_agent_cache()
        return agent

    def update_agent_definition(self, agent_id: int, data: dict, actor_email: str = None) -> Optional[AgentDefinition]:
        agent = self.get_agent_definition(agent_id)
        if not agent:
            return None

        before = {"slug": agent.slug, "name": agent.name}
        tools = data.pop("default_tools", None)

        for key, value in data.items():
            if value is not None and hasattr(agent, key):
                setattr(agent, key, value)

        if tools is not None:
            agent.default_tools_json = json.dumps(tools)

        self._audit("agent.updated", "agent", agent.id, before, data, actor_email)
        self.db.commit()
        self._invalidate_agent_cache()
        return agent

    # ═══════════════════════════════════════════════════════════════════════
    # TENANT AGENT CONFIG
    # ═══════════════════════════════════════════════════════════════════════

    def list_tenant_agent_configs(self, tenant_id: int) -> list[dict]:
        rows = (
            self.db.query(TenantAgentConfig, AgentDefinition)
            .join(AgentDefinition, TenantAgentConfig.agent_definition_id == AgentDefinition.id)
            .filter(TenantAgentConfig.tenant_id == tenant_id)
            .all()
        )
        results = []
        for tac, ad in rows:
            tools = None
            if tac.override_tools_json:
                try:
                    tools = json.loads(tac.override_tools_json)
                except (json.JSONDecodeError, TypeError):
                    tools = None

            results.append({
                "id": tac.id,
                "tenant_id": tac.tenant_id,
                "agent_definition_id": tac.agent_definition_id,
                "agent_slug": ad.slug,
                "agent_name": ad.name,
                "override_provider_slug": tac.override_provider_slug,
                "override_model": tac.override_model,
                "override_temperature": tac.override_temperature,
                "override_max_tokens": tac.override_max_tokens,
                "override_tools": tools,
                "custom_display_name": tac.custom_display_name,
                "custom_persona_text": tac.custom_persona_text,
                "is_enabled": tac.is_enabled,
                "created_at": tac.created_at,
                "updated_at": tac.updated_at,
            })
        return results

    def upsert_tenant_agent_config(self, tenant_id: int, data: dict, actor_email: str = None) -> TenantAgentConfig:
        agent_def_id = data["agent_definition_id"]
        existing = self.db.query(TenantAgentConfig).filter(
            TenantAgentConfig.tenant_id == tenant_id,
            TenantAgentConfig.agent_definition_id == agent_def_id,
        ).first()

        tools = data.pop("override_tools", None)

        if existing:
            for key, value in data.items():
                if value is not None and hasattr(existing, key) and key != "agent_definition_id":
                    setattr(existing, key, value)
            if tools is not None:
                existing.override_tools_json = json.dumps(tools)
            self._audit("tenant_agent.updated", "tenant_agent", existing.id, None, data, actor_email, tenant_id)
            self.db.commit()
            return existing
        else:
            tac = TenantAgentConfig(
                tenant_id=tenant_id,
                agent_definition_id=agent_def_id,
                override_provider_slug=data.get("override_provider_slug"),
                override_model=data.get("override_model"),
                override_temperature=data.get("override_temperature"),
                override_max_tokens=data.get("override_max_tokens"),
                override_tools_json=json.dumps(tools) if tools else None,
                custom_display_name=data.get("custom_display_name"),
                custom_persona_text=data.get("custom_persona_text"),
                is_enabled=data.get("is_enabled", True),
            )
            self.db.add(tac)
            self.db.flush()
            self._audit("tenant_agent.created", "tenant_agent", tac.id, None, data, actor_email, tenant_id)
            self.db.commit()
            return tac

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIT LOG
    # ═══════════════════════════════════════════════════════════════════════

    def list_audit_log(self, tenant_id: Optional[int] = None, limit: int = 50) -> list[AIConfigAuditLog]:
        q = self.db.query(AIConfigAuditLog)
        if tenant_id:
            q = q.filter(AIConfigAuditLog.tenant_id == tenant_id)
        return q.order_by(AIConfigAuditLog.created_at.desc()).limit(limit).all()

    def _audit(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[int],
        before: Optional[dict],
        after: Optional[dict],
        actor_email: Optional[str] = None,
        tenant_id: Optional[int] = None,
    ) -> None:
        """Write an audit log entry."""
        try:
            log = AIConfigAuditLog(
                tenant_id=tenant_id,
                actor_email=actor_email,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                before_json=json.dumps(before, default=str) if before else None,
                after_json=json.dumps(after, default=str) if after else None,
            )
            self.db.add(log)
        except Exception as e:
            logger.warning("ai_config.audit_failed", error=str(e))

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _provider_to_dict(p: LLMProvider) -> dict:
        return {
            "slug": p.slug,
            "name": p.name,
            "provider_type": p.provider_type,
            "api_base_url": p.api_base_url,
            "is_active": p.is_active,
            "priority": p.priority,
        }

    @staticmethod
    def _invalidate_provider_cache():
        global _provider_cache_ts
        _provider_cache_ts = 0.0

    @staticmethod
    def _invalidate_agent_cache():
        global _agent_cache_ts
        _agent_cache_ts = 0.0
