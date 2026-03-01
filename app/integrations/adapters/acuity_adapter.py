"""ARIIA v2.0 – Acuity Scheduling Adapter.

@ARCH: Sprint 4 (Integration Roadmap), Task S4.3
Concrete adapter for Acuity Scheduling API.
Uses HTTP Basic Auth (User ID + API Key).

Supported Capabilities:
  - scheduling.appointments.list     → List appointments
  - scheduling.appointments.create   → Create a new appointment
  - scheduling.appointments.cancel   → Cancel an appointment
  - scheduling.appointments.reschedule → Reschedule an appointment
  - scheduling.availability.get      → Get available time slots
  - scheduling.calendars.list        → List calendars
  - scheduling.appointment_types.list → List appointment types
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class AcuityAdapter(BaseAdapter):
    """Adapter for Acuity Scheduling API.

    Handles appointments, availability, calendars, and appointment types.
    Uses HTTP Basic Auth with User ID and API Key.
    """

    ACUITY_API_BASE = "https://acuityscheduling.com/api/v1"

    @property
    def integration_id(self) -> str:
        return "acuity"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "scheduling.appointments.list",
            "scheduling.appointments.create",
            "scheduling.appointments.cancel",
            "scheduling.appointments.reschedule",
            "scheduling.availability.get",
            "scheduling.calendars.list",
            "scheduling.appointment_types.list",
        ]

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability calls to the appropriate Acuity method."""
        handlers = {
            "scheduling.appointments.list": self._list_appointments,
            "scheduling.appointments.create": self._create_appointment,
            "scheduling.appointments.cancel": self._cancel_appointment,
            "scheduling.appointments.reschedule": self._reschedule_appointment,
            "scheduling.availability.get": self._get_availability,
            "scheduling.calendars.list": self._list_calendars,
            "scheduling.appointment_types.list": self._list_appointment_types,
        }
        handler = handlers.get(capability_id)
        if handler:
            return await handler(tenant_id, **kwargs)
        return AdapterResult(success=False, error=f"Unknown capability: {capability_id}")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_credentials(self, tenant_id: int) -> tuple[str | None, str | None]:
        """Get Acuity credentials for a tenant.

        Returns (user_id, api_key).
        """
        try:
            from app.gateway.persistence import persistence

            user_id = (persistence.get_setting(f"acuity_user_id_{tenant_id}") or
                       persistence.get_setting("acuity_user_id", "")).strip()
            api_key = (persistence.get_setting(f"acuity_api_key_{tenant_id}") or
                       persistence.get_setting("acuity_api_key", "")).strip()

            return user_id or None, api_key or None
        except Exception:
            return None, None

    async def _acuity_request(
        self, tenant_id: int, method: str, path: str,
        json_data: dict | None = None, params: dict | None = None,
    ) -> tuple[Any | None, AdapterResult | None]:
        """Make an authenticated request to the Acuity API."""
        import httpx

        user_id, api_key = self._get_credentials(tenant_id)
        if not user_id or not api_key:
            return None, AdapterResult(
                success=False,
                error="Acuity-Zugangsdaten nicht konfiguriert. Bitte User ID und API Key in den Integrationseinstellungen hinterlegen.",
                error_code="ACUITY_NOT_CONFIGURED",
            )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method,
                    f"{self.ACUITY_API_BASE}{path}",
                    auth=(user_id, api_key),
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
                error=f"Acuity API error ({exc.response.status_code}): {error_body}",
                error_code=f"ACUITY_HTTP_{exc.response.status_code}",
            )
        except Exception as exc:
            return None, AdapterResult(
                success=False,
                error=f"Acuity request failed: {exc}",
                error_code="ACUITY_REQUEST_FAILED",
            )

    # ── scheduling.appointments.list ─────────────────────────────────────

    async def _list_appointments(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List appointments.

        Optional kwargs:
            min_date (str): Minimum date (YYYY-MM-DD).
            max_date (str): Maximum date (YYYY-MM-DD).
            calendar_id (int): Filter by calendar.
            email (str): Filter by client email.
            canceled (bool): Include canceled (default: False).
        """
        params: dict[str, Any] = {}
        if kwargs.get("min_date"):
            params["minDate"] = kwargs["min_date"]
        if kwargs.get("max_date"):
            params["maxDate"] = kwargs["max_date"]
        if kwargs.get("calendar_id"):
            params["calendarID"] = kwargs["calendar_id"]
        if kwargs.get("email"):
            params["email"] = kwargs["email"]
        if kwargs.get("canceled"):
            params["canceled"] = "true"

        data, err = await self._acuity_request(tenant_id, "GET", "/appointments", params=params)
        if err:
            return err

        appointments = []
        if isinstance(data, list):
            for apt in data:
                appointments.append({
                    "id": apt.get("id"),
                    "first_name": apt.get("firstName"),
                    "last_name": apt.get("lastName"),
                    "email": apt.get("email"),
                    "phone": apt.get("phone"),
                    "datetime": apt.get("datetime"),
                    "end_time": apt.get("endTime"),
                    "type": apt.get("type"),
                    "type_id": apt.get("appointmentTypeID"),
                    "calendar_id": apt.get("calendarID"),
                    "calendar": apt.get("calendar"),
                    "canceled": apt.get("canceled", False),
                    "can_client_cancel": apt.get("canClientCancel", False),
                    "can_client_reschedule": apt.get("canClientReschedule", False),
                    "location": apt.get("location", ""),
                    "notes": apt.get("notes", ""),
                    "confirmation_page": apt.get("confirmationPage"),
                })

        return AdapterResult(
            success=True,
            data=appointments,
            metadata={"count": len(appointments)},
        )

    # ── scheduling.appointments.create ───────────────────────────────────

    async def _create_appointment(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Create a new appointment.

        Required kwargs:
            appointment_type_id (int): The appointment type ID.
            datetime (str): ISO 8601 datetime (e.g., "2026-03-15T10:00:00+0100").
            first_name (str): Client first name.
            last_name (str): Client last name.
            email (str): Client email.
        Optional kwargs:
            phone (str): Client phone number.
            notes (str): Additional notes.
            calendar_id (int): Specific calendar ID.
            timezone (str): Client timezone.
        """
        appointment_type_id = kwargs.get("appointment_type_id")
        dt = kwargs.get("datetime")
        first_name = kwargs.get("first_name")
        last_name = kwargs.get("last_name")
        email = kwargs.get("email")

        if not all([appointment_type_id, dt, first_name, last_name, email]):
            return AdapterResult(
                success=False,
                error="Parameters 'appointment_type_id', 'datetime', 'first_name', 'last_name', 'email' are required",
                error_code="MISSING_PARAM",
            )

        body: dict[str, Any] = {
            "appointmentTypeID": appointment_type_id,
            "datetime": dt,
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
        }
        if kwargs.get("phone"):
            body["phone"] = kwargs["phone"]
        if kwargs.get("notes"):
            body["notes"] = kwargs["notes"]
        if kwargs.get("calendar_id"):
            body["calendarID"] = kwargs["calendar_id"]
        if kwargs.get("timezone"):
            body["timezone"] = kwargs["timezone"]

        data, err = await self._acuity_request(
            tenant_id, "POST", "/appointments", json_data=body
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "id": data.get("id"),
                "datetime": data.get("datetime"),
                "end_time": data.get("endTime"),
                "type": data.get("type"),
                "first_name": data.get("firstName"),
                "last_name": data.get("lastName"),
                "email": data.get("email"),
                "confirmation_page": data.get("confirmationPage"),
                "calendar": data.get("calendar"),
            },
        )

    # ── scheduling.appointments.cancel ───────────────────────────────────

    async def _cancel_appointment(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Cancel an appointment.

        Required kwargs:
            appointment_id (int): The appointment ID.
        Optional kwargs:
            cancel_note (str): Cancellation note.
            no_show (bool): Mark as no-show instead of cancel.
        """
        appointment_id = kwargs.get("appointment_id")
        if not appointment_id:
            return AdapterResult(
                success=False,
                error="Parameter 'appointment_id' is required",
                error_code="MISSING_PARAM",
            )

        body: dict[str, Any] = {}
        if kwargs.get("cancel_note"):
            body["cancelNote"] = kwargs["cancel_note"]
        if kwargs.get("no_show"):
            body["noShow"] = True

        data, err = await self._acuity_request(
            tenant_id, "PUT",
            f"/appointments/{appointment_id}/cancel",
            json_data=body if body else None,
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "appointment_id": appointment_id,
                "status": "cancelled",
                "action": "appointment_cancelled",
            },
        )

    # ── scheduling.appointments.reschedule ───────────────────────────────

    async def _reschedule_appointment(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Reschedule an appointment.

        Required kwargs:
            appointment_id (int): The appointment ID.
            new_datetime (str): New ISO 8601 datetime.
        Optional kwargs:
            calendar_id (int): New calendar ID.
        """
        appointment_id = kwargs.get("appointment_id")
        new_datetime = kwargs.get("new_datetime")

        if not appointment_id or not new_datetime:
            return AdapterResult(
                success=False,
                error="Parameters 'appointment_id' and 'new_datetime' are required",
                error_code="MISSING_PARAM",
            )

        body: dict[str, Any] = {"datetime": new_datetime}
        if kwargs.get("calendar_id"):
            body["calendarID"] = kwargs["calendar_id"]

        data, err = await self._acuity_request(
            tenant_id, "PUT",
            f"/appointments/{appointment_id}/reschedule",
            json_data=body,
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "appointment_id": appointment_id,
                "new_datetime": new_datetime,
                "status": "rescheduled",
                "action": "appointment_rescheduled",
                "datetime": data.get("datetime") if isinstance(data, dict) else new_datetime,
            },
        )

    # ── scheduling.availability.get ──────────────────────────────────────

    async def _get_availability(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get available time slots for an appointment type.

        Required kwargs:
            appointment_type_id (int): The appointment type ID.
            month (str): Month in YYYY-MM format.
        Optional kwargs:
            calendar_id (int): Specific calendar ID.
            timezone (str): Timezone (default: "Europe/Berlin").
        """
        appointment_type_id = kwargs.get("appointment_type_id")
        month = kwargs.get("month")

        if not appointment_type_id or not month:
            return AdapterResult(
                success=False,
                error="Parameters 'appointment_type_id' and 'month' are required",
                error_code="MISSING_PARAM",
            )

        # Get available dates first
        params: dict[str, Any] = {
            "appointmentTypeID": appointment_type_id,
            "month": month,
        }
        if kwargs.get("calendar_id"):
            params["calendarID"] = kwargs["calendar_id"]
        if kwargs.get("timezone"):
            params["timezone"] = kwargs["timezone"]

        dates_data, err = await self._acuity_request(
            tenant_id, "GET", "/availability/dates", params=params
        )
        if err:
            return err

        # Get available times for each date
        available_dates = []
        if isinstance(dates_data, list):
            for date_entry in dates_data:
                date_str = date_entry.get("date")
                if date_str:
                    time_params = {
                        "appointmentTypeID": appointment_type_id,
                        "date": date_str,
                    }
                    if kwargs.get("calendar_id"):
                        time_params["calendarID"] = kwargs["calendar_id"]
                    if kwargs.get("timezone"):
                        time_params["timezone"] = kwargs["timezone"]

                    times_data, time_err = await self._acuity_request(
                        tenant_id, "GET", "/availability/times", params=time_params
                    )
                    if not time_err and isinstance(times_data, list):
                        times = [t.get("time") for t in times_data if t.get("time")]
                        available_dates.append({
                            "date": date_str,
                            "slots": times,
                            "slot_count": len(times),
                        })

        return AdapterResult(
            success=True,
            data=available_dates,
            metadata={
                "month": month,
                "appointment_type_id": appointment_type_id,
                "total_dates": len(available_dates),
            },
        )

    # ── scheduling.calendars.list ────────────────────────────────────────

    async def _list_calendars(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List available calendars."""
        data, err = await self._acuity_request(tenant_id, "GET", "/calendars")
        if err:
            return err

        calendars = []
        if isinstance(data, list):
            for cal in data:
                calendars.append({
                    "id": cal.get("id"),
                    "name": cal.get("name"),
                    "email": cal.get("email"),
                    "description": cal.get("description"),
                    "timezone": cal.get("timezone"),
                    "thumbnail": cal.get("thumbnail"),
                })

        return AdapterResult(
            success=True,
            data=calendars,
            metadata={"count": len(calendars)},
        )

    # ── scheduling.appointment_types.list ────────────────────────────────

    async def _list_appointment_types(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List available appointment types."""
        data, err = await self._acuity_request(tenant_id, "GET", "/appointment-types")
        if err:
            return err

        types = []
        if isinstance(data, list):
            for at in data:
                types.append({
                    "id": at.get("id"),
                    "name": at.get("name"),
                    "description": at.get("description"),
                    "duration": at.get("duration"),
                    "price": at.get("price"),
                    "category": at.get("category"),
                    "color": at.get("color"),
                    "private": at.get("private", False),
                    "active": at.get("active", True),
                    "type": at.get("type"),
                    "calendar_ids": at.get("calendarIDs", []),
                })

        return AdapterResult(
            success=True,
            data=types,
            metadata={"count": len(types)},
        )

    # ── Health Check ─────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if Acuity is configured and accessible."""
        data, err = await self._acuity_request(tenant_id, "GET", "/me")
        if err:
            return AdapterResult(
                success=True,
                data={"status": "NOT_CONFIGURED", "reason": err.error},
            )

        if isinstance(data, dict):
            return AdapterResult(
                success=True,
                data={
                    "status": "CONNECTED",
                    "owner_name": f"{data.get('firstName', '')} {data.get('lastName', '')}".strip(),
                    "email": data.get("email"),
                    "timezone": data.get("timezone"),
                },
            )

        return AdapterResult(success=True, data={"status": "CONNECTED"})
