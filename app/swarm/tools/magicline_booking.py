"""ARIIA Swarm v3 — MagiclineBookingTool.

Handles all booking-related Magicline operations:
get_class_schedule, get_appointment_slots, book_appointment_by_time,
class_book, cancel_member_booking, reschedule_member_booking_to_latest.
"""

from __future__ import annotations

from typing import Any

from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool
from app.swarm.tools.magicline import (
    get_class_schedule,
    get_appointment_slots,
    book_appointment_by_time,
    class_book,
    cancel_member_booking,
    reschedule_member_booking_to_latest,
)


class MagiclineBookingTool(SkillTool):
    """Booking operations: schedule lookup, slot availability, book/cancel/reschedule."""

    name = "magicline_booking"
    description = (
        "Manage Magicline bookings: view class schedules, find appointment slots, "
        "book classes or appointments, cancel bookings, and reschedule to a later slot."
    )
    required_integrations = frozenset({"magicline"})
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "get_class_schedule",
                    "get_appointment_slots",
                    "book_appointment_by_time",
                    "class_book",
                    "cancel_member_booking",
                    "reschedule_member_booking_to_latest",
                ],
                "description": "The booking action to perform.",
            },
            "date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format.",
            },
            "user_identifier": {
                "type": "string",
                "description": "User identifier (phone, email, or member ID).",
            },
            "time": {
                "type": "string",
                "description": "Time in HH:MM format (for book_appointment_by_time).",
            },
            "category": {
                "type": "string",
                "description": "Appointment category filter (default: 'all').",
            },
            "days": {
                "type": "integer",
                "description": "Number of days to look ahead (for get_appointment_slots).",
            },
            "slot_id": {
                "type": "integer",
                "description": "Class slot ID (for class_book).",
            },
            "query": {
                "type": "string",
                "description": "Fuzzy search query to filter bookings by title/time.",
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        action = params.get("action")
        tenant_id = context.tenant_id
        user_id = params.get("user_identifier") or context.member_id

        try:
            if action == "get_class_schedule":
                date_str = params.get("date")
                if not date_str:
                    return ToolResult(success=False, error_message="Parameter 'date' is required.")
                result = get_class_schedule(date_str, tenant_id=tenant_id)

            elif action == "get_appointment_slots":
                category = params.get("category", "all")
                days = params.get("days", 3)
                result = get_appointment_slots(category=category, days=days, tenant_id=tenant_id)

            elif action == "book_appointment_by_time":
                if not user_id:
                    return ToolResult(success=False, error_message="Parameter 'user_identifier' is required.")
                time_str = params.get("time")
                if not time_str:
                    return ToolResult(success=False, error_message="Parameter 'time' is required.")
                result = book_appointment_by_time(
                    user_identifier=user_id,
                    time_str=time_str,
                    date_str=params.get("date"),
                    category=params.get("category", "all"),
                    tenant_id=tenant_id,
                )

            elif action == "class_book":
                slot_id = params.get("slot_id")
                if not slot_id:
                    return ToolResult(success=False, error_message="Parameter 'slot_id' is required.")
                result = class_book(
                    slot_id=int(slot_id),
                    user_identifier=user_id,
                    tenant_id=tenant_id,
                )

            elif action == "cancel_member_booking":
                if not user_id:
                    return ToolResult(success=False, error_message="Parameter 'user_identifier' is required.")
                date_str = params.get("date")
                if not date_str:
                    return ToolResult(success=False, error_message="Parameter 'date' is required.")
                result = cancel_member_booking(
                    user_identifier=user_id,
                    date_str=date_str,
                    query=params.get("query"),
                    tenant_id=tenant_id,
                )

            elif action == "reschedule_member_booking_to_latest":
                if not user_id:
                    return ToolResult(success=False, error_message="Parameter 'user_identifier' is required.")
                date_str = params.get("date")
                if not date_str:
                    return ToolResult(success=False, error_message="Parameter 'date' is required.")
                result = reschedule_member_booking_to_latest(
                    user_identifier=user_id,
                    date_str=date_str,
                    query=params.get("query"),
                    tenant_id=tenant_id,
                )

            else:
                return ToolResult(success=False, error_message=f"Unknown action: {action}")

            is_error = result.startswith("Error:") or result.startswith("Fehler")
            return ToolResult(success=not is_error, data=result, error_message=result if is_error else None)

        except Exception as e:
            return ToolResult(success=False, error_message=str(e))
