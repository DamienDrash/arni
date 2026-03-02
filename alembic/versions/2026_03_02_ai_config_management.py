"""AI Configuration Management – Complete Schema.

Creates all tables for the refactored AI configuration system:
- ai_llm_providers: Platform-level LLM provider catalog
- ai_tenant_llm_providers: Tenant BYOK configurations
- ai_plan_budgets: Plan-level AI budget controls
- ai_tenant_budget_overrides: Tenant-specific budget overrides
- ai_prompt_templates: Master prompt template records
- ai_prompt_versions: Immutable prompt versions
- ai_prompt_deployments: Environment-based prompt deployments
- ai_agent_definitions: Agent type catalog
- ai_tenant_agent_configs: Tenant agent overrides
- ai_config_audit_log: Configuration change audit trail

Revision ID: ai_config_001
Revises: (standalone, applied after existing migrations)
"""

from alembic import op
import sqlalchemy as sa

revision = "ai_config_001"
down_revision = None
branch_labels = ("ai_config",)
depends_on = None


def upgrade() -> None:
    # ── 1. LLM Provider Registry ──────────────────────────────────────────
    op.create_table(
        "ai_llm_providers",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider_type", sa.String(32), nullable=False, server_default="openai_compatible"),
        sa.Column("api_base_url", sa.String(512), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("supported_models_json", sa.Text, nullable=True),
        sa.Column("default_model", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("100")),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default=sa.text("2")),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default=sa.text("60")),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── 2. Tenant LLM Providers (BYOK) ───────────────────────────────────
    op.create_table(
        "ai_tenant_llm_providers",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("ai_llm_providers.id"), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("preferred_model", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("100")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "provider_id", name="uq_tenant_llm_provider"),
    )

    # ── 3. Plan AI Budgets ────────────────────────────────────────────────
    op.create_table(
        "ai_plan_budgets",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("plans.id"), nullable=False, unique=True),
        sa.Column("monthly_token_limit", sa.Integer, nullable=True),
        sa.Column("monthly_budget_cents", sa.Integer, nullable=True),
        sa.Column("requests_per_minute", sa.Integer, nullable=True, server_default=sa.text("60")),
        sa.Column("requests_per_day", sa.Integer, nullable=True),
        sa.Column("max_tokens_per_request", sa.Integer, nullable=False, server_default=sa.text("4096")),
        sa.Column("allowed_providers_json", sa.Text, nullable=True),
        sa.Column("allowed_models_json", sa.Text, nullable=True),
        sa.Column("overage_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("overage_cost_per_1k_tokens_cents", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── 4. Tenant Budget Overrides ────────────────────────────────────────
    op.create_table(
        "ai_tenant_budget_overrides",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("monthly_token_limit", sa.Integer, nullable=True),
        sa.Column("monthly_budget_cents", sa.Integer, nullable=True),
        sa.Column("requests_per_minute", sa.Integer, nullable=True),
        sa.Column("valid_from", sa.DateTime, nullable=True),
        sa.Column("valid_until", sa.DateTime, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── 5. Prompt Templates ───────────────────────────────────────────────
    op.create_table(
        "ai_prompt_templates",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("slug", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(64), nullable=False, server_default="agent"),
        sa.Column("agent_type", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── 6. Prompt Versions ────────────────────────────────────────────────
    op.create_table(
        "ai_prompt_versions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("ai_prompt_templates.id"), nullable=False, index=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("variables_json", sa.Text, nullable=True),
        sa.Column("change_notes", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("template_id", "version", name="uq_prompt_version"),
    )

    # ── 7. Prompt Deployments ─────────────────────────────────────────────
    op.create_table(
        "ai_prompt_deployments",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("version_id", sa.Integer, sa.ForeignKey("ai_prompt_versions.id"), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False, server_default="production"),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("deployed_by", sa.String(256), nullable=True),
        sa.Column("deployed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Index("ix_prompt_deploy_lookup", "version_id", "environment", "tenant_id"),
    )

    # ── 8. Agent Definitions ──────────────────────────────────────────────
    op.create_table(
        "ai_agent_definitions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("agent_class", sa.String(256), nullable=False),
        sa.Column("default_provider_slug", sa.String(64), nullable=True),
        sa.Column("default_model", sa.String(128), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("default_temperature", sa.Float, nullable=False, server_default=sa.text("0.7")),
        sa.Column("default_max_tokens", sa.Integer, nullable=False, server_default=sa.text("1000")),
        sa.Column("default_tools_json", sa.Text, nullable=True),
        sa.Column("prompt_template_slug", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_visible_to_tenants", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── 9. Tenant Agent Configs ───────────────────────────────────────────
    op.create_table(
        "ai_tenant_agent_configs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("agent_definition_id", sa.Integer, sa.ForeignKey("ai_agent_definitions.id"), nullable=False),
        sa.Column("override_provider_slug", sa.String(64), nullable=True),
        sa.Column("override_model", sa.String(128), nullable=True),
        sa.Column("override_temperature", sa.Float, nullable=True),
        sa.Column("override_max_tokens", sa.Integer, nullable=True),
        sa.Column("override_tools_json", sa.Text, nullable=True),
        sa.Column("custom_display_name", sa.String(128), nullable=True),
        sa.Column("custom_persona_text", sa.Text, nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "agent_definition_id", name="uq_tenant_agent_config"),
    )

    # ── 10. AI Config Audit Log ───────────────────────────────────────────
    op.create_table(
        "ai_config_audit_log",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("actor_email", sa.String(256), nullable=True),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer, nullable=True),
        sa.Column("before_json", sa.Text, nullable=True),
        sa.Column("after_json", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("ai_config_audit_log")
    op.drop_table("ai_tenant_agent_configs")
    op.drop_table("ai_agent_definitions")
    op.drop_table("ai_prompt_deployments")
    op.drop_table("ai_prompt_versions")
    op.drop_table("ai_prompt_templates")
    op.drop_table("ai_tenant_budget_overrides")
    op.drop_table("ai_plan_budgets")
    op.drop_table("ai_tenant_llm_providers")
    op.drop_table("ai_llm_providers")
