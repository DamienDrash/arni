"""ARIIA v2.0 – Async Magicline Client.

@ARCH: Phase 1, Meilenstein 1.3 – Asynchrone & Resiliente I/O
Async wrapper around the Magicline OpenAPI using httpx and Circuit Breaker.
Replaces the synchronous `requests`-based client for all runtime operations.

The sync client (client.py) is preserved for migrations and CLI tools.
This async client is used by the agent swarm and webhook processing.

Features:
- Fully async (httpx.AsyncClient)
- Circuit breaker per tenant
- Automatic retry with exponential backoff
- Connection pooling
- Structured logging
"""

from __future__ import annotations

from typing import Any, Optional

import structlog

from app.core.resilience import CircuitBreakerConfig, ResilientHTTPClient

logger = structlog.get_logger()


class AsyncMagiclineClient:
    """Async Magicline OpenAPI client with circuit breaker.

    Drop-in async replacement for MagiclineClient.
    Method signatures match the sync client for easy migration.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        tenant_id: int | None = None,
        timeout: float = 20.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id

        cb_name = f"magicline_t{tenant_id}" if tenant_id else "magicline"
        self._http = ResilientHTTPClient(
            base_url=self.base_url,
            circuit_breaker_name=cb_name,
            timeout=timeout,
            max_retries=3,
            retry_backoff=1.0,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
            },
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=60.0,
            ),
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.close()

    async def _get(self, path: str, params: dict | None = None) -> Any:
        """GET request with error handling."""
        resp = await self._http.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json_body: dict | None = None) -> Any:
        """POST request with error handling."""
        resp = await self._http.post(path, json=json_body)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    async def _delete(self, path: str) -> int:
        """DELETE request with error handling."""
        resp = await self._http.delete(path)
        resp.raise_for_status()
        return resp.status_code

    # ─── Studio ──────────────────────────────────────────────────────

    async def studio_info(self) -> dict:
        """GET /v1/studios/information"""
        return await self._get("/v1/studios/information")

    # ─── Customer ────────────────────────────────────────────────────

    async def customer_list(
        self,
        *,
        customer_status: str | None = None,
        slice_size: int = 100,
        offset: str | None = None,
    ) -> dict:
        """GET /v1/customers"""
        params: dict[str, Any] = {"sliceSize": max(int(slice_size), 50)}
        if offset is not None:
            params["offset"] = offset
        if customer_status is not None:
            params["customerStatus"] = customer_status
        return await self._get("/v1/customers", params)

    async def customer_get(self, customer_id: int) -> dict:
        """GET /v1/customers/{customerId}"""
        return await self._get(f"/v1/customers/{int(customer_id)}")

    async def customer_search(
        self,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        date_of_birth: str | None = None,
    ) -> list[dict]:
        """POST /v1/customers/search"""
        body: dict[str, str] = {}
        if first_name:
            body["firstName"] = first_name
        if last_name:
            body["lastName"] = last_name
        if email:
            body["email"] = email
        if date_of_birth:
            body["dateOfBirth"] = date_of_birth
        return await self._post("/v1/customers/search", body)

    async def customer_get_by(
        self,
        *,
        customer_number: str | None = None,
        card_number: str | None = None,
    ) -> dict:
        """GET /v1/customers/by"""
        params: dict[str, str] = {}
        if customer_number:
            params["customerNumber"] = customer_number
        if card_number:
            params["cardNumber"] = card_number
        return await self._get("/v1/customers/by", params)

    async def customer_contracts(
        self, customer_id: int, *, status: str | None = None
    ) -> list[dict]:
        """GET /v1/customers/{customerId}/contracts"""
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        return await self._get(
            f"/v1/customers/{int(customer_id)}/contracts", params or None
        )

    async def customer_checkins(
        self,
        customer_id: int,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        slice_size: int = 20,
        offset: int | None = None,
    ) -> dict:
        """GET /v1/customers/{customerId}/activities/checkins"""
        params: dict[str, Any] = {"sliceSize": int(slice_size)}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if offset is not None:
            params["offset"] = int(offset)
        return await self._get(
            f"/v1/customers/{int(customer_id)}/activities/checkins", params
        )

    async def customer_comm_prefs(self, customer_id: int) -> list[dict]:
        """GET /v1/communications/{customerId}/communication-preferences"""
        data = await self._get(
            f"/v1/communications/{int(customer_id)}/communication-preferences"
        )
        return data if isinstance(data, list) else []

    # ─── Appointments ────────────────────────────────────────────────

    async def appointment_list_bookable(
        self, *, slice_size: int = 100, offset: str | None = None
    ) -> dict:
        """GET /v1/appointments/bookable"""
        params: dict[str, Any] = {"sliceSize": max(1, min(int(slice_size), 100))}
        if offset is not None:
            params["offset"] = offset
        return await self._get("/v1/appointments/bookable", params)

    async def appointment_get_slots(
        self,
        bookable_id: int,
        *,
        customer_id: int | None = None,
        days_ahead: int | None = None,
        slot_window_start_date: str | None = None,
    ) -> dict:
        """GET /v1/appointments/bookable/{id}/slots"""
        params: dict[str, Any] = {}
        if customer_id is not None:
            params["customerId"] = int(customer_id)
        if days_ahead is not None:
            params["daysAhead"] = max(1, min(int(days_ahead), 3))
        if slot_window_start_date is not None:
            params["slotWindowStartDate"] = slot_window_start_date
        return await self._get(
            f"/v1/appointments/bookable/{int(bookable_id)}/slots", params or None
        )

    async def appointment_validate(
        self,
        *,
        bookable_id: int,
        customer_id: int,
        start_dt: str,
        end_dt: str,
        instructor_ids: list[int] | None = None,
    ) -> dict:
        """POST /v1/appointments/bookable/validate"""
        body: dict[str, Any] = {
            "bookableAppointmentId": int(bookable_id),
            "customerId": int(customer_id),
            "startDateTime": start_dt,
            "endDateTime": end_dt,
        }
        if instructor_ids:
            body["instructorIds"] = [int(i) for i in instructor_ids]
        return await self._post("/v1/appointments/bookable/validate", body)

    async def appointment_book(
        self,
        *,
        bookable_id: int,
        customer_id: int,
        start_dt: str,
        end_dt: str,
        instructor_ids: list[int] | None = None,
    ) -> dict:
        """POST /v1/appointments/booking/book"""
        body: dict[str, Any] = {
            "bookableAppointmentId": int(bookable_id),
            "customerId": int(customer_id),
            "startDateTime": start_dt,
            "endDateTime": end_dt,
        }
        if instructor_ids:
            body["instructorIds"] = [int(i) for i in instructor_ids]
        return await self._post("/v1/appointments/booking/book", body)

    async def appointment_list_bookings(
        self, customer_id: int, *, slice_size: int = 200, offset: str | None = None
    ) -> dict:
        """GET /v1/appointments/booking"""
        params: dict[str, Any] = {
            "customerId": int(customer_id),
            "sliceSize": int(slice_size),
        }
        if offset is not None:
            params["offset"] = offset
        return await self._get("/v1/appointments/booking", params)

    async def appointment_cancel(self, booking_id: int) -> int:
        """DELETE /v1/appointments/booking/{bookingId}"""
        return await self._delete(f"/v1/appointments/booking/{int(booking_id)}")

    # ─── Classes ─────────────────────────────────────────────────────

    async def class_list(
        self, *, slice_size: int = 100, offset: str | None = None
    ) -> dict:
        """GET /v1/classes"""
        params: dict[str, Any] = {"sliceSize": int(slice_size)}
        if offset is not None:
            params["offset"] = offset
        return await self._get("/v1/classes", params)

    async def class_list_all_slots(
        self,
        *,
        days_ahead: int | None = None,
        slot_window_start_date: str | None = None,
        slice_size: int = 100,
        offset: str | None = None,
    ) -> dict:
        """GET /v1/classes/slots"""
        params: dict[str, Any] = {"sliceSize": int(slice_size)}
        if days_ahead is not None:
            params["daysAhead"] = max(1, min(int(days_ahead), 3))
        if slot_window_start_date is not None:
            params["slotWindowStartDate"] = slot_window_start_date
        if offset is not None:
            params["offset"] = offset
        return await self._get("/v1/classes/slots", params)

    async def class_validate_booking(
        self, *, slot_id: int, customer_id: int
    ) -> dict:
        """POST /v1/classes/booking/validate"""
        return await self._post(
            "/v1/classes/booking/validate",
            {"classSlotId": int(slot_id), "customerId": int(customer_id)},
        )

    async def class_book(self, *, slot_id: int, customer_id: int) -> dict:
        """POST /v1/classes/booking/book"""
        return await self._post(
            "/v1/classes/booking/book",
            {"classSlotId": int(slot_id), "customerId": int(customer_id)},
        )

    async def class_list_bookings(
        self, customer_id: int, *, slice_size: int = 200, offset: str | None = None
    ) -> dict:
        """GET /v1/classes/booking"""
        params: dict[str, Any] = {
            "customerId": int(customer_id),
            "sliceSize": int(slice_size),
        }
        if offset is not None:
            params["offset"] = offset
        return await self._get("/v1/classes/booking", params)

    async def class_cancel_booking(self, booking_id: int) -> int:
        """DELETE /v1/classes/booking/{bookingId}"""
        return await self._delete(f"/v1/classes/booking/{int(booking_id)}")
