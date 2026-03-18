"""ARIIA Swarm v3 — CalendlyTool (SkillTool wrapper)."""

from __future__ import annotations

from typing import Any

from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool


class CalendlyTool(SkillTool):
    """Schedule and manage Calendly appointments."""

    name = "calendly"
    description = "Get booking links, list event types, and view upcoming Calendly events."
    required_integrations = frozenset({"calendly"})
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_booking_link", "list_event_types", "get_upcoming_events"],
                "description": "The Calendly action to perform.",
            },
            "event_type_name": {
                "type": "string",
                "description": "Name of the event type (for get_booking_link).",
            },
            "count": {
                "type": "integer",
                "description": "Max number of events to return (for get_upcoming_events, default: 5).",
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        from app.swarm.tools.calendly_tools import (
            get_booking_link,
            list_event_types,
            get_upcoming_events,
        )

        action = params.get("action")
        tenant_id = context.tenant_id

        try:
            if action == "get_booking_link":
                result = await get_booking_link(
                    event_type_name=params.get("event_type_name", ""),
                    tenant_id=tenant_id,
                )
            elif action == "list_event_types":
                result = await list_event_types(tenant_id=tenant_id)
            elif action == "get_upcoming_events":
                count = params.get("count", 5)
                result = await get_upcoming_events(tenant_id=tenant_id, count=count)
            else:
                return ToolResult(success=False, error_message=f"Unknown action: {action}")

            is_error = result.startswith("Fehler") or result.startswith("Leider")
            return ToolResult(success=not is_error, data=result, error_message=result if is_error else None)

        except Exception as e:
            return ToolResult(success=False, error_message=str(e))
