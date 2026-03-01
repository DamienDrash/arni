"""ARIIA v2.0 – Magicline Integration Adapter.

@ARCH: Phase 2, Meilenstein 2.3 – Integration & Skills
Concrete adapter for the Magicline CRM/Booking system. Maps abstract
capabilities to the existing Magicline client API calls.

This adapter wraps the existing `app.swarm.tools.magicline` functions
into the new BaseAdapter interface, providing:
  - Standardized capability routing
  - Structured AdapterResult responses
  - Tenant-scoped client resolution
  - Error handling and logging

Supported Capabilities:
  - crm.customer.search       → Find member by email/name/phone
  - crm.customer.status       → Get member status and contract info
  - booking.class.schedule     → Get class schedule for a date
  - booking.class.book         → Book a class slot
  - booking.appointment.slots  → Get available appointment slots
  - booking.appointment.book   → Book an appointment by time
  - booking.member.bookings    → Get member's bookings
  - booking.member.cancel      → Cancel a member's booking
  - booking.member.reschedule  → Reschedule to latest available slot
  - analytics.checkin.history  → Get check-in history
  - analytics.checkin.stats    → Get check-in statistics
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class MagiclineAdapter(BaseAdapter):
    """Adapter for the Magicline CRM and booking system.

    Routes capability calls to the existing magicline tools module,
    wrapping results in the standardized AdapterResult format.
    """

    @property
    def integration_id(self) -> str:
        return "magicline"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "crm.customer.search",
            "crm.customer.status",
            "booking.class.schedule",
            "booking.class.book",
            "booking.appointment.slots",
            "booking.appointment.book",
            "booking.member.bookings",
            "booking.member.cancel",
            "booking.member.reschedule",
            "analytics.checkin.history",
            "analytics.checkin.stats",
        ]

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability to the appropriate Magicline tool function."""
        # Lazy import to avoid circular dependencies
        from app.swarm.tools import magicline as ml_tools

        # Capability → handler mapping
        handlers = {
            "crm.customer.search": self._customer_search,
            "crm.customer.status": self._customer_status,
            "booking.class.schedule": self._class_schedule,
            "booking.class.book": self._class_book,
            "booking.appointment.slots": self._appointment_slots,
            "booking.appointment.book": self._appointment_book,
            "booking.member.bookings": self._member_bookings,
            "booking.member.cancel": self._member_cancel,
            "booking.member.reschedule": self._member_reschedule,
            "analytics.checkin.history": self._checkin_history,
            "analytics.checkin.stats": self._checkin_stats,
        }

        handler = handlers.get(capability_id)
        if not handler:
            return AdapterResult(
                success=False,
                error=f"No handler for capability '{capability_id}'",
                error_code="NO_HANDLER",
            )

        return await handler(tenant_id, **kwargs)

    # ─── CRM Capabilities ────────────────────────────────────────────────

    async def _customer_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Search for a customer by email, name, or phone."""
        from app.swarm.tools.magicline import get_member_status

        user_identifier = kwargs.get("email") or kwargs.get("name") or kwargs.get("phone") or kwargs.get("query", "")
        if not user_identifier:
            return AdapterResult(
                success=False,
                error="Bitte geben Sie eine E-Mail, einen Namen oder eine Telefonnummer an.",
                error_code="MISSING_IDENTIFIER",
            )

        try:
            result = get_member_status(user_identifier=user_identifier, tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SEARCH_FAILED")

    async def _customer_status(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get detailed member status and contract information."""
        from app.swarm.tools.magicline import get_member_status

        user_identifier = kwargs.get("user_identifier") or kwargs.get("email") or kwargs.get("name", "")
        if not user_identifier:
            return AdapterResult(
                success=False,
                error="Bitte geben Sie einen Kundenbezeichner an.",
                error_code="MISSING_IDENTIFIER",
            )

        try:
            result = get_member_status(user_identifier=user_identifier, tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="STATUS_FAILED")

    # ─── Booking Capabilities ─────────────────────────────────────────────

    async def _class_schedule(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get class schedule for a given date."""
        from app.swarm.tools.magicline import get_class_schedule

        date_str = kwargs.get("date", "")
        try:
            result = get_class_schedule(date_str=date_str, tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SCHEDULE_FAILED")

    async def _class_book(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Book a class slot for a member."""
        from app.swarm.tools.magicline import class_book

        slot_id = kwargs.get("slot_id")
        user_identifier = kwargs.get("user_identifier")
        if not slot_id:
            return AdapterResult(
                success=False,
                error="slot_id ist erforderlich.",
                error_code="MISSING_SLOT_ID",
            )

        try:
            result = class_book(slot_id=int(slot_id), user_identifier=user_identifier, tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="BOOK_FAILED")

    async def _appointment_slots(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get available appointment slots."""
        from app.swarm.tools.magicline import get_appointment_slots

        category = kwargs.get("category", "all")
        days = kwargs.get("days", 3)
        try:
            result = get_appointment_slots(category=category, days=int(days), tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SLOTS_FAILED")

    async def _appointment_book(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Book an appointment by time."""
        from app.swarm.tools.magicline import book_appointment_by_time

        required = ["category", "date", "time"]
        missing = [k for k in required if not kwargs.get(k)]
        if missing:
            return AdapterResult(
                success=False,
                error=f"Fehlende Parameter: {', '.join(missing)}",
                error_code="MISSING_PARAMS",
            )

        try:
            result = book_appointment_by_time(
                category=kwargs["category"],
                date_str=kwargs["date"],
                time_str=kwargs["time"],
                user_identifier=kwargs.get("user_identifier"),
                tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="APPOINTMENT_BOOK_FAILED")

    async def _member_bookings(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get a member's current bookings."""
        from app.swarm.tools.magicline import get_member_bookings

        try:
            result = get_member_bookings(
                user_identifier=kwargs.get("user_identifier"),
                date_str=kwargs.get("date"),
                query=kwargs.get("query"),
                tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="BOOKINGS_FAILED")

    async def _member_cancel(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Cancel a member's booking."""
        from app.swarm.tools.magicline import cancel_member_booking

        booking_id = kwargs.get("booking_id")
        booking_type = kwargs.get("booking_type", "class")
        if not booking_id:
            return AdapterResult(
                success=False,
                error="booking_id ist erforderlich.",
                error_code="MISSING_BOOKING_ID",
            )

        try:
            result = cancel_member_booking(
                booking_id=int(booking_id),
                booking_type=booking_type,
                user_identifier=kwargs.get("user_identifier"),
                tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="CANCEL_FAILED")

    async def _member_reschedule(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Reschedule a member's booking to the latest available slot."""
        from app.swarm.tools.magicline import reschedule_member_booking_to_latest

        booking_id = kwargs.get("booking_id")
        if not booking_id:
            return AdapterResult(
                success=False,
                error="booking_id ist erforderlich.",
                error_code="MISSING_BOOKING_ID",
            )

        try:
            result = reschedule_member_booking_to_latest(
                booking_id=int(booking_id),
                user_identifier=kwargs.get("user_identifier"),
                tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="RESCHEDULE_FAILED")

    # ─── Analytics Capabilities ───────────────────────────────────────────

    async def _checkin_history(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get check-in history for a member."""
        from app.swarm.tools.magicline import get_checkin_history

        try:
            result = get_checkin_history(
                days=int(kwargs.get("days", 7)),
                user_identifier=kwargs.get("user_identifier"),
                tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="CHECKIN_HISTORY_FAILED")

    async def _checkin_stats(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get check-in statistics for a member."""
        from app.swarm.tools.magicline import get_checkin_stats

        try:
            result = get_checkin_stats(
                days=int(kwargs.get("days", 90)),
                user_identifier=kwargs.get("user_identifier"),
                tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="CHECKIN_STATS_FAILED")

    # ─── Health Check ─────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if the Magicline API is reachable for this tenant."""
        try:
            from app.integrations.magicline import get_client
            client = get_client(tenant_id=tenant_id)
            if client:
                return AdapterResult(success=True, data={"status": "ok", "adapter": "magicline"})
            return AdapterResult(success=False, error="Magicline client not configured", error_code="NOT_CONFIGURED")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
