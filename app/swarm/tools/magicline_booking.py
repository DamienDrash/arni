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
    get_appointment_types,
    get_class_types,
    get_class_slots_range,
    get_member_bookings,
    book_appointment_by_time,
    class_book,
    cancel_member_booking,
    cancel_booking_by_id,
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
                    "get_appointment_types",
                    "get_class_types",
                    "get_class_slots",
                    "get_class_schedule",
                    "get_appointment_slots",
                    "get_member_bookings",
                    "book_appointment_by_time",
                    "class_book",
                    "cancel_member_booking",
                    "cancel_booking_by_id",
                    "reschedule_member_booking_to_latest",
                ],
                "description": (
                    "The booking action to perform.\n"
                    "CATALOG: 'get_appointment_types' lists all bookable appointment types; "
                    "'get_class_types' lists all class types; "
                    "'get_class_slots' lists class time slots over a date range.\n"
                    "SCHEDULE: 'get_class_schedule' shows the public studio timetable for one day; "
                    "pass 'query' to filter by class name (e.g. query='Krafttraining').\n"
                    "SLOTS: 'get_appointment_slots' shows free appointment slots (optionally filtered by category/days).\n"
                    "MEMBER BOOKINGS: 'get_member_bookings' shows a member's personal bookings — use this for "
                    "'when is my training', NOT get_class_schedule.\n"
                    "BOOK: 'book_appointment_by_time' books by HH:MM time; 'class_book' books by slot_id.\n"
                    "CANCEL: 'cancel_member_booking' cancels by date+query; 'cancel_booking_by_id' cancels by booking_id.\n"
                    "RESCHEDULE: 'reschedule_member_booking_to_latest' moves a booking to the latest free slot."
                ),
            },
            "date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format.",
            },
            "start_date": {
                "type": "string",
                "description": "Start date for date-range queries (YYYY-MM-DD). Defaults to today.",
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
                "description": "Number of days to look ahead (for get_appointment_slots, get_class_slots). Default: 3.",
            },
            "slot_id": {
                "type": "integer",
                "description": "Class slot ID (for class_book).",
            },
            "booking_id": {
                "type": "integer",
                "description": "Specific booking ID (for cancel_booking_by_id).",
            },
            "booking_type": {
                "type": "string",
                "enum": ["appointment", "class"],
                "description": "Type of booking for cancel_booking_by_id (appointment or class).",
            },
            "class_id": {
                "type": "integer",
                "description": "Filter get_class_slots to a specific class type by ID.",
            },
            "query": {
                "type": "string",
                "description": "Filter by name/title: for get_class_schedule filters by class name (e.g. 'Krafttraining'), for get_member_bookings filters by booking title/time.",
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        action = params.get("action")
        tenant_id = context.tenant_id
        user_id = params.get("user_identifier") or context.member_id or context.phone_number

        try:
            if action == "get_appointment_types":
                result = get_appointment_types(tenant_id=tenant_id)

            elif action == "get_class_types":
                result = get_class_types(tenant_id=tenant_id)

            elif action == "get_class_slots":
                result = get_class_slots_range(
                    days=params.get("days", 7),
                    start_date=params.get("start_date"),
                    class_id=params.get("class_id"),
                    tenant_id=tenant_id,
                )

            elif action == "get_class_schedule":
                date_str = params.get("date")
                if not date_str:
                    return ToolResult(success=False, error_message="Parameter 'date' is required.")
                result = get_class_schedule(date_str, query=params.get("query"), tenant_id=tenant_id)

            elif action == "get_appointment_slots":
                category = params.get("category", "all")
                days = params.get("days", 3)
                result = get_appointment_slots(category=category, days=days, tenant_id=tenant_id)

            elif action == "get_member_bookings":
                if not user_id:
                    return ToolResult(success=False, error_message="Parameter 'user_identifier' is required.")
                result = get_member_bookings(
                    user_identifier=user_id,
                    date_str=params.get("date"),
                    query=params.get("query"),
                    tenant_id=tenant_id,
                )

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

            elif action == "cancel_booking_by_id":
                booking_id = params.get("booking_id")
                if not booking_id:
                    return ToolResult(success=False, error_message="Parameter 'booking_id' is required.")
                result = cancel_booking_by_id(
                    booking_id=int(booking_id),
                    booking_type=params.get("booking_type", "appointment"),
                    user_identifier=user_id,
                    tenant_id=tenant_id,
                )

            else:
                return ToolResult(success=False, error_message=f"Unknown action: {action}")

            _ERROR_SIGNALS = (
                "Error:",
                "Fehler",
                "technischen Fehler",
                "nicht konfiguriert",
                "Umbuchen nicht möglich",
                "nicht aufgelöst werden",
                "nicht eindeutig zuordnen",
            )
            is_error = any(sig in result for sig in _ERROR_SIGNALS)
            return ToolResult(success=not is_error, data=result, error_message=result if is_error else None)

        except Exception as e:
            return ToolResult(success=False, error_message=str(e))
