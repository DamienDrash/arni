"""upgrade ops and booking agents to gpt-5-mini

Revision ID: b3c4d5e6f7a8
Revises: fadf7c20edd1
Create Date: 2026-03-25 00:00:00.000000

Updates the default_model for the ops and booking AgentDefinition records
from gpt-4o-mini to gpt-5-mini. Also adds gpt-5-mini and o4-mini to the
OpenAI provider's supported_models_json.
"""
from typing import Sequence, Union

import json
from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = '2026_03_18_merge_heads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Update ops and booking agent default_model
    conn.execute(
        sa.text(
            "UPDATE ai_agent_definitions SET default_model = 'gpt-5-mini' "
            "WHERE slug IN ('ops', 'booking') AND default_model = 'gpt-4o-mini'"
        )
    )

    # Add gpt-5-mini and o4-mini to OpenAI provider supported_models_json
    row = conn.execute(
        sa.text("SELECT supported_models_json FROM ai_llm_providers WHERE slug = 'openai'")
    ).fetchone()

    if row and row[0]:
        try:
            models = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            models = []
        for m in ["gpt-5-mini", "o4-mini"]:
            if m not in models:
                models.append(m)
        conn.execute(
            sa.text(
                "UPDATE ai_llm_providers SET supported_models_json = :models WHERE slug = 'openai'"
            ),
            {"models": json.dumps(models)},
        )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "UPDATE ai_agent_definitions SET default_model = 'gpt-4o-mini' "
            "WHERE slug IN ('ops', 'booking') AND default_model = 'gpt-5-mini'"
        )
    )
