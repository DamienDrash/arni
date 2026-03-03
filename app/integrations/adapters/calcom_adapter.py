"""ARIIA v2.0 – Cal.com Scheduling Adapter.

@ARCH: Sprint 4 (Integration Roadmap), Task S4.2
Concrete adapter for Cal.com API v2 scheduling integration.
Open-source, self-hostable scheduling infrastructure.

Supported Capabilities:
  - scheduling.event_types.list    → List available event types
  - scheduling.bookings.list       → List bookings
  - scheduling.bookings.create     → Create a new booking
  - scheduling.bookings.cancel     → Cancel a booking
  - scheduling.bookings.reschedule → Reschedule a booking
  - scheduling.availability.get    → Get user availability
  - scheduling.slots.list          → List available time slots
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class CalComAdapter(BaseAdapter):
    """Adapter for Cal.com API v2 scheduling integration.

    Handles event types, bookings, availability, and time slots.
    Supports both Cal.com Cloud and self-hosted instances.
    """

    DEFAULT_BASE_URL = "https://api.cal.com/v1"

    @property
    def integration_id(self) -> str:
        return "calcom"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "scheduling.event_types.list",
            "scheduling.bookings.list",
            "scheduling.bookings.create",
            "scheduling.bookings.cancel",
            "scheduling.bookings.reschedule",
            "scheduling.availability.get",
            "scheduling.slots.list",
        ]

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "Cal.com"

    @property
    def category(self) -> str:
        return "scheduling"

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "required": True,
                    "help_text": "Cal.com API Key aus den Einstellungen.",
                },
                {
                    "key": "base_url",
                    "label": "Base URL",
                    "type": "text",
                    "required": False,
                    "help_text": "Cal.com Instance URL (Standard: https://api.cal.com).",
                },
            ],
        }

    async def get_contacts(
        self,
        tenant_id: int,
        config: dict,
        last_sync_at=None,
        sync_mode=None,
    ) -> "SyncResult":
        from app.integrations.adapters.base import SyncResult
        return SyncResult(
            success=True,
            records_fetched=0,
            contacts=[],
            metadata={"note": "Cal.com does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="Cal.com-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability calls to the appropriate Cal.com method."""
        handlers = {
            "scheduling.event_types.list": self._list_event_types,
            "scheduling.bookings.list": self._list_bookings,
            "scheduling.bookings.create": self._create_booking,
            "scheduling.bookings.cancel": self._cancel_booking,
            "scheduling.bookings.reschedule": self._reschedule_booking,
            "scheduling.availability.get": self._get_availability,
            "scheduling.slots.list": self._list_slots,
        }
        handler = handlers.get(capability_id)
        if handler:
            return await handler(tenant_id, **kwargs)
        return AdapterResult(success=False, error=f"Unknown capability: {capability_id}")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_credentials(self, tenant_id: int) -> tuple[str | None, str]:
        """Get Cal.com credentials for a tenant.

        Returns (api_key, base_url).
        """
        try:
            from app.gateway.persistence import persistence

            api_key = (persistence.get_setting(f"calcom_api_key_{tenant_id}") or
                       persistence.get_setting("calcom_api_key", "")).strip()
            base_url = (persistence.get_setting(f"calcom_base_url_{tenant_id}") or
                        persistence.get_setting("calcom_base_url", "")).strip()

            return api_key or None, base_url or self.DEFAULT_BASE_URL
        except Exception:
            return None, self.DEFAULT_BASE_URL

    async def _calcom_request(
        self, tenant_id: int, method: str, path: str,
        json_data: dict | None = None, params: dict | None = None,
    ) -> tuple[dict | None, AdapterResult | None]:
        """Make an authenticated request to the Cal.com API."""
        import httpx

        api_key, base_url = self._get_credentials(tenant_id)
        if not api_key:
            return None, AdapterResult(
                success=False,
                error="Cal.com-Zugangsdaten nicht konfiguriert. Bitte API Key in den Integrationseinstellungen hinterlegen.",
                error_code="CALCOM_NOT_CONFIGURED",
            )

        if params is None:
            params = {}
        params["apiKey"] = api_key

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method,
                    f"{base_url}{path}",
                    headers={"Content-Type": "application/json"},
                    json=json_data,
                    params=params,
                )
                resp.raise_for_status()
                return resp.json() if resp.content else {}, None
        except httpx.HTTPStatusError as exc:
            error_body = exc.response.text[:500] if exc.response else "No response"
            return None, AdapterResult(
                success=False,
                error=f"Cal.com API error ({exc.response.status_code}): {error_body}",
                error_code=f"CALCOM_HTTP_{exc.response.status_code}",
            )
        except Exception as exc:
            return None, AdapterResult(
                success=False,
                error=f"Cal.com request failed: {exc}",
                error_code="CALCOM_REQUEST_FAILED",
            )

    # ── scheduling.event_types.list ──────────────────────────────────────

    async def _list_event_types(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List available event types."""
        data, err = await self._calcom_request(tenant_id, "GET", "/event-types")
        if err:
            return err

        event_types = []
        for et in data.get("event_types", []):
            event_types.append({
                "id": et.get("id"),
                "title": et.get("title"),
                "slug": et.get("slug"),
                "description": et.get("description"),
                "length": et.get("length"),
                "hidden": et.get("hidden", False),
                "position": et.get("position"),
                "locations": et.get("locations", []),
                "recurring": et.get("recurringEvent"),
            })

        return AdapterResult(
            success=True,
            data=event_types,
            metadata={"count": len(event_types)},
        )

    # ── scheduling.bookings.list ─────────────────────────────────────────

    async def _list_bookings(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List bookings.

        Optional kwargs:
            status (str): "upcoming", "recurring", "past", "cancelled", "unconfirmed".
        """
        params: dict[str, Any] = {}
        if kwargs.get("status"):
            params["status"] = kwargs["status"]

        data, err = await self._calcom_request(tenant_id, "GET", "/bookings", params=params)
        if err:
            return err

        bookings = []
        for b in data.get("bookings", []):
            bookings.append({
                "id": b.get("id"),
                "uid": b.get("uid"),
                "title": b.get("title"),
                "description": b.get("description"),
                "start_time": b.get("startTime"),
                "end_time": b.get("endTime"),
                "status": b.get("status"),
                "attendees": [
                    {"name": a.get("name"), "email": a.get("email"), "timezone": a.get("timeZone")}
                    for a in b.get("attendees", [])
                ],
                "event_type_id": b.get("eventTypeId"),
                "created_at": b.get("createdAt"),
            })

        return AdapterResult(
            success=True,
            data=bookings,
            metadata={"count": len(bookings)},
        )

    # ── scheduling.bookings.create ───────────────────────────────────────

    async def _create_booking(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Create a new booking.

        Required kwargs:
            event_type_id (int): The event type ID.
            start (str): ISO 8601 start datetime.
            name (str): Attendee name.
            email (str): Attendee email.
        Optional kwargs:
            timezone (str): Attendee timezone (default: "Europe/Berlin").
            notes (str): Additional notes.
            metadata (dict): Custom metadata.
            language (str): Language code (default: "de").
        """
        event_type_id = kwargs.get("event_type_id")
        start = kwargs.get("start")
        name = kwargs.get("name")
        email = kwargs.get("email")

        if not all([event_type_id, start, name, email]):
            return AdapterResult(
                success=False,
                error="Parameters 'event_type_id', 'start', 'name', 'email' are required",
                error_code="MISSING_PARAM",
            )

        booking_body: dict[str, Any] = {
            "eventTypeId": event_type_id,
            "start": start,
            "responses": {
                "name": name,
                "email": email,
                "notes": kwargs.get("notes", ""),
            },
            "timeZone": kwargs.get("timezone", "Europe/Berlin"),
            "language": kwargs.get("language", "de"),
            "metadata": kwargs.get("metadata", {}),
        }

        data, err = await self._calcom_request(
            tenant_id, "POST", "/bookings", json_data=booking_body
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "id": data.get("id"),
                "uid": data.get("uid"),
                "title": data.get("title"),
                "start_time": data.get("startTime"),
                "end_time": data.get("endTime"),
                "status": data.get("status"),
                "attendees": data.get("attendees", []),
            },
        )

    # ── scheduling.bookings.cancel ───────────────────────────────────────

    async def _cancel_booking(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Cancel a booking.

        Required kwargs:
            booking_id (int): The booking ID.
        Optional kwargs:
            reason (str): Cancellation reason.
        """
        booking_id = kwargs.get("booking_id")
        if not booking_id:
            return AdapterResult(success=False, error="Parameter 'booking_id' is required", error_code="MISSING_PARAM")

        cancel_body: dict[str, Any] = {"id": booking_id}
        if kwargs.get("reason"):
            cancel_body["reason"] = kwargs["reason"]

        _, err = await self._calcom_request(
            tenant_id, "DELETE", f"/bookings/{booking_id}", json_data=cancel_body
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "booking_id": booking_id,
                "status": "cancelled",
                "action": "booking_cancelled",
                "reason": kwargs.get("reason", ""),
            },
        )

    # ── scheduling.bookings.reschedule ───────────────────────────────────

    async def _reschedule_booking(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Reschedule a booking.

        Required kwargs:
            booking_id (int): The booking ID.
            new_start (str): New ISO 8601 start datetime.
        Optional kwargs:
            reason (str): Reschedule reason.
        """
        booking_id = kwargs.get("booking_id")
        new_start = kwargs.get("new_start")

        if not booking_id or not new_start:
            return AdapterResult(
                success=False,
                error="Parameters 'booking_id' and 'new_start' are required",
                error_code="MISSING_PARAM",
            )

        reschedule_body: dict[str, Any] = {
            "start": new_start,
            "reason": kwargs.get("reason", ""),
        }

        data, err = await self._calcom_request(
            tenant_id, "PATCH", f"/bookings/{booking_id}", json_data=reschedule_body
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "booking_id": booking_id,
                "new_start": new_start,
                "status": "rescheduled",
                "action": "booking_rescheduled",
            },
        )

    # ── scheduling.availability.get ──────────────────────────────────────

    async def _get_availability(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get user availability.

        Optional kwargs:
            date_from (str): Start date (YYYY-MM-DD).
            date_to (str): End date (YYYY-MM-DD).
            event_type_id (int): Filter by event type.
        """
        params: dict[str, Any] = {}
        if kwargs.get("date_from"):
            params["dateFrom"] = kwargs["date_from"]
        if kwargs.get("date_to"):
            params["dateTo"] = kwargs["date_to"]
        if kwargs.get("event_type_id"):
            params["eventTypeId"] = kwargs["event_type_id"]

        data, err = await self._calcom_request(tenant_id, "GET", "/availability", params=params)
        if err:
            return err

        return AdapterResult(
            success=True,
            data=data,
        )

    # ── scheduling.slots.list ────────────────────────────────────────────

    async def _list_slots(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List available time slots for an event type.

        Required kwargs:
            event_type_id (int): The event type ID.
            start_time (str): ISO 8601 start datetime.
            end_time (str): ISO 8601 end datetime.
        Optional kwargs:
            timezone (str): Timezone (default: "Europe/Berlin").
        """
        event_type_id = kwargs.get("event_type_id")
        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")

        if not all([event_type_id, start_time, end_time]):
            return AdapterResult(
                success=False,
                error="Parameters 'event_type_id', 'start_time', 'end_time' are required",
                error_code="MISSING_PARAM",
            )

        params: dict[str, Any] = {
            "eventTypeId": event_type_id,
            "startTime": start_time,
            "endTime": end_time,
            "timeZone": kwargs.get("timezone", "Europe/Berlin"),
        }

        data, err = await self._calcom_request(tenant_id, "GET", "/slots", params=params)
        if err:
            return err

        slots = data.get("slots", {})
        formatted_slots = []
        for date_key, day_slots in slots.items():
            for slot in day_slots:
                formatted_slots.append({
                    "date": date_key,
                    "time": slot.get("time"),
                })

        return AdapterResult(
            success=True,
            data=formatted_slots,
            metadata={"count": len(formatted_slots), "event_type_id": event_type_id},
        )

    # ── Health Check ─────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if Cal.com is configured and accessible."""
        data, err = await self._calcom_request(tenant_id, "GET", "/me")
        if err:
            return AdapterResult(
                success=True,
                data={"status": "NOT_CONFIGURED", "reason": err.error},
            )

        return AdapterResult(
            success=True,
            data={
                "status": "CONNECTED",
                "user_name": data.get("name"),
                "email": data.get("email"),
                "username": data.get("username"),
            },
        )
