"""ARIIA Swarm v3 — MagiclineMemberTool.

Handles member-related Magicline operations:
get_member_status, get_member_bookings, get_checkin_stats.
"""

from __future__ import annotations

from typing import Any

from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool
from app.swarm.tools.magicline import (
    get_member_status,
    get_member_bookings,
    get_member_profile,
    get_member_contracts,
    get_checkin_stats,
)


class MagiclineMemberTool(SkillTool):
    """Member info operations: status, bookings list, check-in statistics."""

    name = "magicline_member"
    description = (
        "Retrieve Magicline member information: membership status, "
        "current bookings, and check-in statistics for retention analysis."
    )
    required_integrations = frozenset({"magicline"})
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "get_member_status",
                    "get_member_profile",
                    "get_member_contracts",
                    "get_member_bookings",
                    "get_checkin_stats",
                ],
                "description": (
                    "The member action to perform.\n"
                    "'get_member_status' — active contract and end date.\n"
                    "'get_member_profile' — full contact data, address, active contracts.\n"
                    "'get_member_contracts' — all contracts (filter with status: ACTIVE | INACTIVE | all).\n"
                    "'get_member_bookings' — upcoming appointments and class bookings.\n"
                    "'get_checkin_stats' — visit frequency and last visit date."
                ),
            },
            "user_identifier": {
                "type": "string",
                "description": "User identifier (phone, email, or member ID).",
            },
            "date": {
                "type": "string",
                "description": "Date filter in YYYY-MM-DD format (for get_member_bookings).",
            },
            "query": {
                "type": "string",
                "description": "Fuzzy search query to filter bookings (for get_member_bookings).",
            },
            "days": {
                "type": "integer",
                "description": "Number of days for stats window (default: 90 for get_checkin_stats).",
            },
            "status": {
                "type": "string",
                "enum": ["ACTIVE", "INACTIVE", "all"],
                "description": "Contract status filter for get_member_contracts (default: ACTIVE).",
            },
        },
        "required": ["action", "user_identifier"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        action = params.get("action")
        tenant_id = context.tenant_id
        user_id = params.get("user_identifier") or context.member_id

        if not user_id:
            return ToolResult(success=False, error_message="Parameter 'user_identifier' is required.")

        try:
            if action == "get_member_status":
                result = get_member_status(user_identifier=user_id, tenant_id=tenant_id)

            elif action == "get_member_profile":
                result = get_member_profile(user_identifier=user_id, tenant_id=tenant_id)

            elif action == "get_member_contracts":
                result = get_member_contracts(
                    user_identifier=user_id,
                    status=params.get("status", "ACTIVE"),
                    tenant_id=tenant_id,
                )

            elif action == "get_member_bookings":
                result = get_member_bookings(
                    user_identifier=user_id,
                    date_str=params.get("date"),
                    query=params.get("query"),
                    tenant_id=tenant_id,
                )

            elif action == "get_checkin_stats":
                days = params.get("days", 90)
                result = get_checkin_stats(days=days, user_identifier=user_id, tenant_id=tenant_id)

            else:
                return ToolResult(success=False, error_message=f"Unknown action: {action}")

            is_error = result.startswith("Error:") or result.startswith("Fehler")
            return ToolResult(success=not is_error, data=result, error_message=result if is_error else None)

        except Exception as e:
            return ToolResult(success=False, error_message=str(e))
