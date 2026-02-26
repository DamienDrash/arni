"""LLM provider config per tenant + token purchase tracking.

Revision ID: 202602260001
Revises: 202602250001
Create Date: 2026-02-26

Changes:
  tenant_llm_configs   — new table: per-tenant LLM provider/model selection
  token_purchases      — new table: token top-up purchases
  usage_records        — add llm_tokens_purchased column
  plans                — add allowed_llm_providers_json, allowed_llm_models_json columns
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '202602260001'
down_revision: Union[str, None] = '202602250001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table: str) -> bool:
    try:
        insp = inspect(conn)
        return table in insp.get_table_names()
    except Exception:
        return False


def _table_has_column(conn, table: str, column: str) -> bool:
    try:
        insp = inspect(conn)
        cols = {c["name"] for c in insp.get_columns(table)}
        return column in cols
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create tenant_llm_configs table ──────────────────────────────
    if not _table_exists(conn, "tenant_llm_configs"):
        op.create_table(
            "tenant_llm_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("provider_id", sa.String(), nullable=False),
            sa.Column("provider_name", sa.String(), nullable=False),
            sa.Column("model_id", sa.String(), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_tenant_llm_configs_tenant", "tenant_llm_configs", ["tenant_id"])

    # ── 2. Create token_purchases table ─────────────────────────────────
    if not _table_exists(conn, "token_purchases"):
        op.create_table(
            "token_purchases",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("tokens_amount", sa.Integer(), nullable=False),
            sa.Column("price_cents", sa.Integer(), nullable=False),
            sa.Column("stripe_payment_intent_id", sa.String(), nullable=True),
            sa.Column("stripe_checkout_session_id", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_token_purchases_tenant", "token_purchases", ["tenant_id"])

    # ── 3. Extend usage_records ─────────────────────────────────────────
    if _table_exists(conn, "usage_records"):
        with op.batch_alter_table("usage_records") as batch_op:
            if not _table_has_column(conn, "usage_records", "llm_tokens_purchased"):
                batch_op.add_column(
                    sa.Column("llm_tokens_purchased", sa.Integer(), nullable=False, server_default=sa.text("0"))
                )

    # ── 4. Extend plans with allowed LLM providers/models ──────────────
    if _table_exists(conn, "plans"):
        with op.batch_alter_table("plans") as batch_op:
            if not _table_has_column(conn, "plans", "allowed_llm_providers_json"):
                batch_op.add_column(
                    sa.Column("allowed_llm_providers_json", sa.Text(), nullable=True)
                )
            if not _table_has_column(conn, "plans", "allowed_llm_models_json"):
                batch_op.add_column(
                    sa.Column("allowed_llm_models_json", sa.Text(), nullable=True)
                )
            if not _table_has_column(conn, "plans", "token_price_per_1k_cents"):
                batch_op.add_column(
                    sa.Column("token_price_per_1k_cents", sa.Integer(), nullable=True, server_default=sa.text("10"))
                )

    # ── 5. Set default allowed providers per plan tier ──────────────────
    if _table_exists(conn, "plans") and _table_has_column(conn, "plans", "allowed_llm_providers_json"):
        import json
        # Starter: only groq (free tier)
        conn.execute(sa.text(
            "UPDATE plans SET allowed_llm_providers_json = :val WHERE slug = 'starter' AND allowed_llm_providers_json IS NULL"
        ), {"val": json.dumps(["groq"])})
        # Pro: groq + mistral + openai
        conn.execute(sa.text(
            "UPDATE plans SET allowed_llm_providers_json = :val WHERE slug = 'pro' AND allowed_llm_providers_json IS NULL"
        ), {"val": json.dumps(["groq", "mistral", "openai"])})
        # Business: all
        conn.execute(sa.text(
            "UPDATE plans SET allowed_llm_providers_json = :val WHERE slug = 'business' AND allowed_llm_providers_json IS NULL"
        ), {"val": json.dumps(["groq", "mistral", "openai", "anthropic", "gemini"])})
        # Enterprise: all
        conn.execute(sa.text(
            "UPDATE plans SET allowed_llm_providers_json = :val WHERE slug = 'enterprise' AND allowed_llm_providers_json IS NULL"
        ), {"val": json.dumps(["groq", "mistral", "openai", "anthropic", "gemini"])})

        # Token pricing per plan
        conn.execute(sa.text(
            "UPDATE plans SET token_price_per_1k_cents = 15 WHERE slug = 'starter' AND token_price_per_1k_cents IS NULL"
        ))
        conn.execute(sa.text(
            "UPDATE plans SET token_price_per_1k_cents = 10 WHERE slug = 'pro' AND token_price_per_1k_cents IS NULL"
        ))
        conn.execute(sa.text(
            "UPDATE plans SET token_price_per_1k_cents = 7 WHERE slug = 'business' AND token_price_per_1k_cents IS NULL"
        ))
        conn.execute(sa.text(
            "UPDATE plans SET token_price_per_1k_cents = 5 WHERE slug = 'enterprise' AND token_price_per_1k_cents IS NULL"
        ))


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "tenant_llm_configs"):
        op.drop_index("ix_tenant_llm_configs_tenant", table_name="tenant_llm_configs")
        op.drop_table("tenant_llm_configs")

    if _table_exists(conn, "token_purchases"):
        op.drop_index("ix_token_purchases_tenant", table_name="token_purchases")
        op.drop_table("token_purchases")

    if _table_exists(conn, "usage_records"):
        with op.batch_alter_table("usage_records") as batch_op:
            if _table_has_column(conn, "usage_records", "llm_tokens_purchased"):
                batch_op.drop_column("llm_tokens_purchased")

    if _table_exists(conn, "plans"):
        with op.batch_alter_table("plans") as batch_op:
            for col in ["allowed_llm_providers_json", "allowed_llm_models_json", "token_price_per_1k_cents"]:
                if _table_has_column(conn, "plans", col):
                    batch_op.drop_column(col)
