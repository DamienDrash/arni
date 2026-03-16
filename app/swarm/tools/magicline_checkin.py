"""ARIIA Swarm v3 — MagiclineCheckinTool.

Handles check-in related Magicline operations:
get_checkin_history.
"""

from __future__ import annotations

from typing import Any

from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool
from app.swarm.tools.magicline import get_checkin_history


class MagiclineCheckinTool(SkillTool):
    """Check-in history lookup for members."""

    name = "magicline_checkin"
    description = "Retrieve check-in history for a gym member from Magicline."
    required_integrations = frozenset({"magicline"})
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "user_identifier": {
                "type": "string",
                "description": "User identifier (phone, email, or member ID).",
            },
            "days": {
                "type": "integer",
                "description": "Number of days to look back (default: 7).",
            },
        },
        "required": ["user_identifier"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        tenant_id = context.tenant_id
        user_id = params.get("user_identifier") or context.member_id

        if not user_id:
            return ToolResult(success=False, error_message="Parameter 'user_identifier' is required.")

        try:
            days = params.get("days", 7)
            result = get_checkin_history(days=days, user_identifier=user_id, tenant_id=tenant_id)

            is_error = result.startswith("Error:") or result.startswith("Fehler")
            return ToolResult(success=not is_error, data=result, error_message=result if is_error else None)

        except Exception as e:
            return ToolResult(success=False, error_message=str(e))
