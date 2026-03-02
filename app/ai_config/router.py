"""ARIIA AI Config Management – API Router.

Provides REST endpoints for managing AI configuration:
- /admin/ai/providers       → LLM Provider CRUD (system_admin)
- /admin/ai/budgets         → Plan Budget Management (system_admin)
- /admin/ai/prompts         → Prompt Template & Version Management (system_admin)
- /admin/ai/agents          → Agent Definition Management (system_admin)
- /admin/ai/audit           → Configuration Audit Log (system_admin)
- /api/v1/tenant/ai/...     → Tenant-scoped config (tenant_admin)
"""

from __future__ import annotations
import json
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.ai_config.service import AIConfigService
from app.ai_config.schemas import (
    LLMProviderCreate, LLMProviderUpdate, LLMProviderResponse,
    TenantLLMProviderCreate, TenantLLMProviderUpdate, TenantLLMProviderResponse,
    PlanAIBudgetCreate, PlanAIBudgetUpdate, PlanAIBudgetResponse,
    PromptTemplateCreate, PromptTemplateResponse,
    PromptVersionCreate, PromptVersionResponse,
    PromptDeployRequest, PromptDeployResponse,
    PromptTestRequest, PromptTestResponse,
    AgentDefinitionCreate, AgentDefinitionUpdate, AgentDefinitionResponse,
    TenantAgentConfigCreate, TenantAgentConfigUpdate, TenantAgentConfigResponse,
    AIConfigAuditLogResponse,
)

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTER (system_admin only)
# ═══════════════════════════════════════════════════════════════════════════════

admin_router = APIRouter(prefix="/admin/ai", tags=["ai-config-admin"])


def _get_service():
    db = SessionLocal()
    try:
        yield AIConfigService(db)
    finally:
        db.close()


def _require_system_admin(user: AuthContext = Depends(get_current_user)) -> AuthContext:
    require_role(user, {"system_admin"})
    return user


def _require_tenant_admin(user: AuthContext = Depends(get_current_user)) -> AuthContext:
    require_role(user, {"system_admin", "tenant_admin"})
    return user


# ── LLM Providers ────────────────────────────────────────────────────────────

@admin_router.get("/providers", response_model=list[LLMProviderResponse])
def list_providers(
    active_only: bool = Query(False),
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    """List all platform LLM providers."""
    providers = svc.list_providers(active_only=active_only)
    return [_provider_to_response(p) for p in providers]


@admin_router.get("/providers/{provider_id}", response_model=LLMProviderResponse)
def get_provider(
    provider_id: int,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    provider = svc.get_provider(provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    return _provider_to_response(provider)


@admin_router.post("/providers", response_model=LLMProviderResponse, status_code=201)
def create_provider(
    body: LLMProviderCreate,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    """Create a new LLM provider."""
    existing = svc.get_provider_by_slug(body.slug)
    if existing:
        raise HTTPException(409, f"Provider with slug '{body.slug}' already exists")
    provider = svc.create_provider(body.model_dump(), actor_email=user.email)
    return _provider_to_response(provider)


@admin_router.put("/providers/{provider_id}", response_model=LLMProviderResponse)
def update_provider(
    provider_id: int,
    body: LLMProviderUpdate,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    provider = svc.update_provider(provider_id, body.model_dump(exclude_unset=True), actor_email=user.email)
    if not provider:
        raise HTTPException(404, "Provider not found")
    return _provider_to_response(provider)


@admin_router.delete("/providers/{provider_id}")
def delete_provider(
    provider_id: int,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    if not svc.delete_provider(provider_id, actor_email=user.email):
        raise HTTPException(404, "Provider not found")
    return {"status": "deleted"}


# ── Plan Budgets ──────────────────────────────────────────────────────────────

@admin_router.get("/budgets", response_model=list[PlanAIBudgetResponse])
def list_budgets(
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    budgets = svc.list_plan_budgets()
    return [_budget_to_response(b) for b in budgets]


@admin_router.get("/budgets/{plan_id}", response_model=PlanAIBudgetResponse)
def get_budget(
    plan_id: int,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    budget = svc.get_plan_budget(plan_id)
    if not budget:
        raise HTTPException(404, "Budget not found for this plan")
    return _budget_to_response(budget)


@admin_router.put("/budgets", response_model=PlanAIBudgetResponse)
def upsert_budget(
    body: PlanAIBudgetCreate,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    budget = svc.upsert_plan_budget(body.model_dump(), actor_email=user.email)
    return _budget_to_response(budget)


# ── Prompt Templates ──────────────────────────────────────────────────────────

@admin_router.get("/prompts", response_model=list[PromptTemplateResponse])
def list_prompts(
    category: Optional[str] = Query(None),
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    templates = svc.list_prompt_templates(category=category)
    results = []
    for t in templates:
        versions = svc.list_prompt_versions(t.id)
        active_v = next((v for v in versions if v.status == "published"), None)
        results.append(PromptTemplateResponse(
            id=t.id,
            slug=t.slug,
            name=t.name,
            description=t.description,
            category=t.category,
            agent_type=t.agent_type,
            is_active=t.is_active,
            versions_count=len(versions),
            active_version=active_v.version if active_v else None,
            created_at=t.created_at,
            updated_at=t.updated_at,
        ))
    return results


@admin_router.post("/prompts", response_model=PromptTemplateResponse, status_code=201)
def create_prompt(
    body: PromptTemplateCreate,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    existing = svc.get_prompt_template_by_slug(body.slug)
    if existing:
        raise HTTPException(409, f"Prompt template '{body.slug}' already exists")
    template = svc.create_prompt_template(body.model_dump(), actor_email=user.email)
    return PromptTemplateResponse(
        id=template.id,
        slug=template.slug,
        name=template.name,
        description=template.description,
        category=template.category,
        agent_type=template.agent_type,
        is_active=template.is_active,
        versions_count=0,
        active_version=None,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@admin_router.get("/prompts/{template_id}/versions", response_model=list[PromptVersionResponse])
def list_prompt_versions(
    template_id: int,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    versions = svc.list_prompt_versions(template_id)
    return [_version_to_response(v) for v in versions]


@admin_router.post("/prompts/{template_id}/versions", response_model=PromptVersionResponse, status_code=201)
def create_prompt_version(
    template_id: int,
    body: PromptVersionCreate,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    template = svc.get_prompt_template(template_id)
    if not template:
        raise HTTPException(404, "Prompt template not found")
    version = svc.create_prompt_version(template_id, body.model_dump(), actor_email=user.email)
    return _version_to_response(version)


@admin_router.post("/prompts/versions/{version_id}/publish", response_model=PromptVersionResponse)
def publish_prompt_version(
    version_id: int,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    version = svc.publish_prompt_version(version_id, actor_email=user.email)
    if not version:
        raise HTTPException(404, "Version not found")
    return _version_to_response(version)


@admin_router.post("/prompts/deploy", response_model=PromptDeployResponse)
def deploy_prompt(
    body: PromptDeployRequest,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    try:
        deployment = svc.deploy_prompt(body.model_dump(), actor_email=user.email)
        version = svc.db.query(svc.db.query.__self__.query(type(deployment)).filter_by(id=deployment.id).first().__class__).first()
        # Get version info
        from app.ai_config.models import PromptVersion
        ver = svc.db.query(PromptVersion).filter(PromptVersion.id == deployment.version_id).first()
        return PromptDeployResponse(
            id=deployment.id,
            version_id=deployment.version_id,
            version=ver.version if ver else "unknown",
            environment=deployment.environment,
            tenant_id=deployment.tenant_id,
            is_active=deployment.is_active,
            deployed_by=deployment.deployed_by,
            deployed_at=deployment.deployed_at,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@admin_router.post("/prompts/test", response_model=PromptTestResponse)
def test_prompt(
    body: PromptTestRequest,
    user: AuthContext = Depends(_require_system_admin),
):
    """Test-render a prompt template with sample variables."""
    from jinja2 import Environment
    env = Environment()
    try:
        template = env.from_string(body.content)
        rendered = template.render(**body.variables)
        # Rough token estimate (1 token ≈ 4 chars for English)
        token_estimate = len(rendered) // 4
        # Extract used variables
        from jinja2 import meta
        ast = env.parse(body.content)
        variables_used = sorted(meta.find_undeclared_variables(ast))
        return PromptTestResponse(
            rendered=rendered,
            variables_used=variables_used,
            token_estimate=token_estimate,
        )
    except Exception as e:
        raise HTTPException(400, f"Template rendering error: {str(e)}")


# ── Agent Definitions ─────────────────────────────────────────────────────────

@admin_router.get("/agents", response_model=list[AgentDefinitionResponse])
def list_agents(
    active_only: bool = Query(False),
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    agents = svc.list_agent_definitions(active_only=active_only)
    return [_agent_to_response(a) for a in agents]


@admin_router.get("/agents/{agent_id}", response_model=AgentDefinitionResponse)
def get_agent(
    agent_id: int,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    agent = svc.get_agent_definition(agent_id)
    if not agent:
        raise HTTPException(404, "Agent definition not found")
    return _agent_to_response(agent)


@admin_router.post("/agents", response_model=AgentDefinitionResponse, status_code=201)
def create_agent(
    body: AgentDefinitionCreate,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    existing = svc.get_agent_definition_by_slug(body.slug)
    if existing:
        raise HTTPException(409, f"Agent '{body.slug}' already exists")
    agent = svc.create_agent_definition(body.model_dump(), actor_email=user.email)
    return _agent_to_response(agent)


@admin_router.put("/agents/{agent_id}", response_model=AgentDefinitionResponse)
def update_agent(
    agent_id: int,
    body: AgentDefinitionUpdate,
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    agent = svc.update_agent_definition(agent_id, body.model_dump(exclude_unset=True), actor_email=user.email)
    if not agent:
        raise HTTPException(404, "Agent definition not found")
    return _agent_to_response(agent)


# ── Audit Log ─────────────────────────────────────────────────────────────────

@admin_router.get("/audit", response_model=list[AIConfigAuditLogResponse])
def list_audit(
    tenant_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    user: AuthContext = Depends(_require_system_admin),
    svc: AIConfigService = Depends(_get_service),
):
    return svc.list_audit_log(tenant_id=tenant_id, limit=limit)


# ═══════════════════════════════════════════════════════════════════════════════
# TENANT ROUTER (tenant_admin)
# ═══════════════════════════════════════════════════════════════════════════════

tenant_router = APIRouter(prefix="/api/v1/tenant/ai", tags=["ai-config-tenant"])


@tenant_router.get("/providers", response_model=list[TenantLLMProviderResponse])
def tenant_list_providers(
    user: AuthContext = Depends(_require_tenant_admin),
    svc: AIConfigService = Depends(_get_service),
):
    """List LLM providers configured for the current tenant."""
    return svc.list_tenant_providers(user.tenant_id)


@tenant_router.post("/providers", response_model=TenantLLMProviderResponse, status_code=201)
def tenant_create_provider(
    body: TenantLLMProviderCreate,
    user: AuthContext = Depends(_require_tenant_admin),
    svc: AIConfigService = Depends(_get_service),
):
    """Add a provider configuration for the current tenant (BYOK)."""
    tp = svc.create_tenant_provider(user.tenant_id, body.model_dump(), actor_email=user.email)
    # Build response
    provider = svc.get_provider(body.provider_id)
    return TenantLLMProviderResponse(
        id=tp.id,
        tenant_id=tp.tenant_id,
        provider_id=tp.provider_id,
        provider_slug=provider.slug if provider else "unknown",
        provider_name=provider.name if provider else "Unknown",
        has_own_key=bool(tp.api_key_encrypted),
        preferred_model=tp.preferred_model,
        is_active=tp.is_active,
        priority=tp.priority,
        created_at=tp.created_at,
        updated_at=tp.updated_at,
    )


@tenant_router.put("/providers/{tp_id}", response_model=TenantLLMProviderResponse)
def tenant_update_provider(
    tp_id: int,
    body: TenantLLMProviderUpdate,
    user: AuthContext = Depends(_require_tenant_admin),
    svc: AIConfigService = Depends(_get_service),
):
    tp = svc.update_tenant_provider(user.tenant_id, tp_id, body.model_dump(exclude_unset=True), actor_email=user.email)
    if not tp:
        raise HTTPException(404, "Tenant provider config not found")
    provider = svc.get_provider(tp.provider_id)
    return TenantLLMProviderResponse(
        id=tp.id,
        tenant_id=tp.tenant_id,
        provider_id=tp.provider_id,
        provider_slug=provider.slug if provider else "unknown",
        provider_name=provider.name if provider else "Unknown",
        has_own_key=bool(tp.api_key_encrypted),
        preferred_model=tp.preferred_model,
        is_active=tp.is_active,
        priority=tp.priority,
        created_at=tp.created_at,
        updated_at=tp.updated_at,
    )


@tenant_router.delete("/providers/{tp_id}")
def tenant_delete_provider(
    tp_id: int,
    user: AuthContext = Depends(_require_tenant_admin),
    svc: AIConfigService = Depends(_get_service),
):
    if not svc.delete_tenant_provider(user.tenant_id, tp_id, actor_email=user.email):
        raise HTTPException(404, "Tenant provider config not found")
    return {"status": "deleted"}


@tenant_router.get("/agents", response_model=list[TenantAgentConfigResponse])
def tenant_list_agents(
    user: AuthContext = Depends(_require_tenant_admin),
    svc: AIConfigService = Depends(_get_service),
):
    """List agent configurations for the current tenant."""
    return svc.list_tenant_agent_configs(user.tenant_id)


@tenant_router.put("/agents", response_model=TenantAgentConfigResponse)
def tenant_upsert_agent(
    body: TenantAgentConfigCreate,
    user: AuthContext = Depends(_require_tenant_admin),
    svc: AIConfigService = Depends(_get_service),
):
    """Create or update an agent configuration for the current tenant."""
    tac = svc.upsert_tenant_agent_config(user.tenant_id, body.model_dump(), actor_email=user.email)
    agent_def = svc.get_agent_definition(tac.agent_definition_id)
    tools = None
    if tac.override_tools_json:
        try:
            tools = json.loads(tac.override_tools_json)
        except (json.JSONDecodeError, TypeError):
            tools = None
    return TenantAgentConfigResponse(
        id=tac.id,
        tenant_id=tac.tenant_id,
        agent_definition_id=tac.agent_definition_id,
        agent_slug=agent_def.slug if agent_def else "unknown",
        agent_name=agent_def.name if agent_def else "Unknown",
        override_provider_slug=tac.override_provider_slug,
        override_model=tac.override_model,
        override_temperature=tac.override_temperature,
        override_max_tokens=tac.override_max_tokens,
        override_tools=tools,
        custom_display_name=tac.custom_display_name,
        custom_persona_text=tac.custom_persona_text,
        is_enabled=tac.is_enabled,
        created_at=tac.created_at,
        updated_at=tac.updated_at,
    )


@tenant_router.get("/config/resolved")
def tenant_resolved_config(
    agent_slug: Optional[str] = Query(None),
    user: AuthContext = Depends(_require_tenant_admin),
    svc: AIConfigService = Depends(_get_service),
):
    """Get the fully resolved LLM configuration for the current tenant.

    Shows the effective config after hierarchical resolution
    (Agent Default → Plan Limits → Tenant Override).
    API key is masked in the response.
    """
    config = svc.resolve_llm_config(user.tenant_id, agent_slug=agent_slug)
    return {
        "provider_slug": config.provider_slug,
        "provider_type": config.provider_type,
        "api_base_url": config.api_base_url,
        "api_key_masked": config.api_key[:4] + "..." + config.api_key[-4:] if len(config.api_key) > 8 else "***",
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "is_byok": config.is_byok,
        "budget_remaining_tokens": config.budget_remaining_tokens,
        "budget_remaining_cents": config.budget_remaining_cents,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _provider_to_response(p) -> LLMProviderResponse:
    models = []
    if p.supported_models_json:
        try:
            models = json.loads(p.supported_models_json)
        except (json.JSONDecodeError, TypeError):
            models = []
    return LLMProviderResponse(
        id=p.id,
        slug=p.slug,
        name=p.name,
        provider_type=p.provider_type,
        api_base_url=p.api_base_url,
        has_api_key=bool(p.api_key_encrypted),
        supported_models=models,
        default_model=p.default_model,
        is_active=p.is_active,
        priority=p.priority,
        max_retries=p.max_retries,
        timeout_seconds=p.timeout_seconds,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _budget_to_response(b) -> PlanAIBudgetResponse:
    providers = None
    models = None
    if b.allowed_providers_json:
        try:
            providers = json.loads(b.allowed_providers_json)
        except (json.JSONDecodeError, TypeError):
            providers = None
    if b.allowed_models_json:
        try:
            models = json.loads(b.allowed_models_json)
        except (json.JSONDecodeError, TypeError):
            models = None
    return PlanAIBudgetResponse(
        id=b.id,
        plan_id=b.plan_id,
        monthly_token_limit=b.monthly_token_limit,
        monthly_budget_cents=b.monthly_budget_cents,
        requests_per_minute=b.requests_per_minute,
        requests_per_day=b.requests_per_day,
        max_tokens_per_request=b.max_tokens_per_request,
        allowed_providers=providers,
        allowed_models=models,
        overage_enabled=b.overage_enabled,
        overage_cost_per_1k_tokens_cents=b.overage_cost_per_1k_tokens_cents,
    )


def _version_to_response(v) -> PromptVersionResponse:
    variables = None
    if v.variables_json:
        try:
            variables = json.loads(v.variables_json)
        except (json.JSONDecodeError, TypeError):
            variables = None
    return PromptVersionResponse(
        id=v.id,
        template_id=v.template_id,
        version=v.version,
        content=v.content,
        variables=variables,
        change_notes=v.change_notes,
        created_by=v.created_by,
        status=v.status,
        created_at=v.created_at,
    )


def _agent_to_response(a) -> AgentDefinitionResponse:
    tools = None
    if a.default_tools_json:
        try:
            tools = json.loads(a.default_tools_json)
        except (json.JSONDecodeError, TypeError):
            tools = None
    return AgentDefinitionResponse(
        id=a.id,
        slug=a.slug,
        name=a.name,
        description=a.description,
        agent_class=a.agent_class,
        default_provider_slug=a.default_provider_slug,
        default_model=a.default_model,
        default_temperature=a.default_temperature,
        default_max_tokens=a.default_max_tokens,
        default_tools=tools,
        prompt_template_slug=a.prompt_template_slug,
        is_active=a.is_active,
        is_visible_to_tenants=a.is_visible_to_tenants,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )
