"""Magicline OpenAPI client — resource-oriented.

Structure mirrors n8n custom node design:
  Resource → Operation → Parameters

Resources:
  - customer: list, get, search, get_contracts, get_checkins, get_comm_prefs
  - appointment: list_bookable, get_bookable, get_slots, validate, book,
                 list_bookings, get_booking, cancel_booking
  - class_: list, get, list_slots, get_slot, validate_booking, book,
            list_bookings, get_booking, cancel_booking
  - studio: info, confirm_activation
"""
from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class MagiclineClient:
    """Low-level Magicline OpenAPI client.

    Every public method corresponds to exactly one API call.
    No business logic, no pagination loops — those belong in the
    workflow layer (Python prototype now, n8n nodes later).
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({
            "Accept": "application/json",
            "x-api-key": self.api_key,
        })

    def _raise_with_body(self, r: requests.Response) -> None:
        """Raise HTTPError with the actual response body included."""
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            # Attach response body so callers see the real error
            body = ""
            try:
                body = r.text[:500]
            except Exception:
                pass
            raise requests.HTTPError(
                f"{e} — Body: {body}",
                response=r,
            ) from e

    def _get(self, path: str, params: dict | None = None) -> Any:
        r = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        self._raise_with_body(r)
        return r.json()

    def _post(self, path: str, json_body: dict | None = None) -> Any:
        r = self.session.post(f"{self.base_url}{path}", json=json_body, timeout=self.timeout)
        self._raise_with_body(r)
        return r.json() if r.content else {}

    def _delete(self, path: str) -> int:
        r = self.session.delete(f"{self.base_url}{path}", timeout=self.timeout)
        self._raise_with_body(r)
        return r.status_code

    # ─── Studio ──────────────────────────────────────────────────────

    def studio_info(self) -> dict:
        """GET /v1/studios/information  (STUDIO_READ)"""
        return self._get("/v1/studios/information")

    def studio_confirm_activation(self) -> None:
        """POST /v1/studios/confirmActivation"""
        self.session.post(
            f"{self.base_url}/v1/studios/confirmActivation", timeout=self.timeout
        ).raise_for_status()

    # ─── Customer ────────────────────────────────────────────────────

    def customer_list(self, *, customer_status: str | None = None,
                      slice_size: int = 100, offset: str | None = None) -> dict:
        """GET /v1/customers  (CUSTOMER_READ)

        customer_status: MEMBER | PROSPECT  (default MEMBER)
        Magicline enforces minimum sliceSize=50.
        """
        params: dict[str, Any] = {"sliceSize": max(int(slice_size), 50)}
        if offset is not None:
            params["offset"] = offset
        if customer_status is not None:
            params["customerStatus"] = customer_status
        return self._get("/v1/customers", params)

    def customer_get(self, customer_id: int) -> dict:
        """GET /v1/customers/{customerId}  (CUSTOMER_READ)"""
        return self._get(f"/v1/customers/{int(customer_id)}")

    def customer_search(self, *, first_name: str | None = None,
                        last_name: str | None = None, email: str | None = None,
                        date_of_birth: str | None = None) -> list[dict]:
        """POST /v1/customers/search  (CUSTOMER_READ)"""
        body: dict[str, str] = {}
        if first_name:
            body["firstName"] = first_name
        if last_name:
            body["lastName"] = last_name
        if email:
            body["email"] = email
        if date_of_birth:
            body["dateOfBirth"] = date_of_birth
        return self._post("/v1/customers/search", body)

    def customer_get_by(self, *, customer_number: str | None = None,
                        card_number: str | None = None) -> dict:
        """GET /v1/customers/by  (CUSTOMER_READ)"""
        params: dict[str, str] = {}
        if customer_number:
            params["customerNumber"] = customer_number
        if card_number:
            params["cardNumber"] = card_number
        return self._get("/v1/customers/by", params)

    def customer_contracts(self, customer_id: int, *,
                           status: str | None = None) -> list[dict]:
        """GET /v1/customers/{customerId}/contracts  (CUSTOMER_CONTRACT_READ)

        status: ACTIVE | INACTIVE
        """
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        return self._get(f"/v1/customers/{int(customer_id)}/contracts", params or None)

    def customer_checkins(self, customer_id: int, *,
                          from_date: str | None = None, to_date: str | None = None,
                          slice_size: int = 20, offset: int | None = None) -> dict:
        """GET /v1/customers/{customerId}/activities/checkins  (CHECKIN_READ)

        from_date / to_date: YYYY-MM-DD (max span 365 days)
        """
        params: dict[str, Any] = {"sliceSize": int(slice_size)}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if offset is not None:
            params["offset"] = int(offset)
        return self._get(f"/v1/customers/{int(customer_id)}/activities/checkins", params)

    def customer_additional_info_fields(self) -> list[dict]:
        """GET /v1/customers/additional-information-fields  (ADDITIONAL_INFORMATION_READ)

        Returns field definitions that describe the additionalInformationFieldAssignments
        on customer objects (e.g. training goals, health notes, characteristics).
        """
        data = self._get("/v1/customers/additional-information-fields")
        return data if isinstance(data, list) else []

    def customer_comm_prefs(self, customer_id: int) -> list[dict]:
        """GET /v1/communications/{customerId}/communication-preferences"""
        data = self._get(f"/v1/communications/{int(customer_id)}/communication-preferences")
        return data if isinstance(data, list) else []

    # ─── Appointments (1:1 Personal Training / Beratung) ─────────────

    def appointment_list_bookable(self, *, slice_size: int = 100,
                                  offset: str | None = None) -> dict:
        """GET /v1/appointments/bookable  (BOOKABLE_APPOINTMENTS_READ)

        Returns bookable appointment types (not time slots).
        """
        # Some studios reject larger values with:
        # "errormessage.validation.max" / "The value is too large".
        params: dict[str, Any] = {"sliceSize": max(1, min(int(slice_size), 100))}
        if offset is not None:
            params["offset"] = offset
        return self._get("/v1/appointments/bookable", params)

    def appointment_get_bookable(self, bookable_id: int) -> dict:
        """GET /v1/appointments/bookable/{id}  (BOOKABLE_APPOINTMENTS_READ)"""
        return self._get(f"/v1/appointments/bookable/{int(bookable_id)}")

    def appointment_get_slots(self, bookable_id: int, *,
                              customer_id: int | None = None,
                              days_ahead: int | None = None,
                              slot_window_start_date: str | None = None) -> dict:
        """GET /v1/appointments/bookable/{id}/slots  (BOOKABLE_APPOINTMENTS_READ)

        Returns available time slots for a bookable appointment type.

        IMPORTANT: Magicline limits days_ahead to 1-3 (varies by studio config).
        For longer ranges, use appointment_get_slots_range() which slides the window.

        days_ahead: 1-3 (clamped automatically)
        slot_window_start_date: YYYY-MM-DD start date for slot window
        """
        params: dict[str, Any] = {}
        if customer_id is not None:
            params["customerId"] = int(customer_id)
        if days_ahead is not None:
            # Magicline enforces max=3 for most studios
            params["daysAhead"] = max(1, min(int(days_ahead), 3))
        if slot_window_start_date is not None:
            params["slotWindowStartDate"] = slot_window_start_date
        return self._get(f"/v1/appointments/bookable/{int(bookable_id)}/slots", params or None)

    def appointment_get_slots_range(self, bookable_id: int, *,
                                    customer_id: int | None = None,
                                    days_total: int = 14,
                                    start_date: str | None = None) -> list[dict]:
        """Fetch appointment slots over a longer range using sliding 3-day windows.

        This works around the Magicline daysAhead limit (max 3) by making
        multiple API calls with advancing slotWindowStartDate.

        Returns flat list of all slot objects found.
        """
        from datetime import date as _date, timedelta
        start = _date.fromisoformat(start_date) if start_date else _date.today()
        window = 3  # max Magicline allows
        all_slots: list[dict] = []
        seen_ids: set = set()

        current = start
        end = start + timedelta(days=days_total)
        while current < end:
            remaining = (end - current).days
            fetch_days = min(window, remaining) or 1
            res = self.appointment_get_slots(
                bookable_id,
                customer_id=customer_id,
                days_ahead=fetch_days,
                slot_window_start_date=current.isoformat(),
            )
            # Extract slots from response (structure may vary)
            items = res if isinstance(res, list) else res.get("result", []) if isinstance(res, dict) else []
            if isinstance(items, dict):
                items = [items]
            for slot in items:
                slot_key = (slot.get("startDateTime"), slot.get("endDateTime"))
                if slot_key not in seen_ids:
                    seen_ids.add(slot_key)
                    all_slots.append(slot)
            current += timedelta(days=fetch_days)

        return all_slots

    def appointment_validate(self, *, bookable_id: int, customer_id: int,
                             start_dt: str, end_dt: str,
                             instructor_ids: list[int] | None = None) -> dict:
        """POST /v1/appointments/bookable/validate  (APPOINTMENTS_WRITE)

        Validates whether a booking can be made. Always call before book().
        start_dt / end_dt: ISO-8601 datetime strings
        """
        body: dict[str, Any] = {
            "bookableAppointmentId": int(bookable_id),
            "customerId": int(customer_id),
            "startDateTime": start_dt,
            "endDateTime": end_dt,
        }
        if instructor_ids:
            body["instructorIds"] = [int(i) for i in instructor_ids]
        return self._post("/v1/appointments/bookable/validate", body)

    def appointment_book(self, *, bookable_id: int, customer_id: int,
                         start_dt: str, end_dt: str,
                         instructor_ids: list[int] | None = None) -> dict:
        """POST /v1/appointments/booking/book  (APPOINTMENTS_WRITE)

        Books an appointment. Call validate() first.
        """
        body: dict[str, Any] = {
            "bookableAppointmentId": int(bookable_id),
            "customerId": int(customer_id),
            "startDateTime": start_dt,
            "endDateTime": end_dt,
        }
        if instructor_ids:
            body["instructorIds"] = [int(i) for i in instructor_ids]
        return self._post("/v1/appointments/booking/book", body)

    def appointment_list_bookings(self, customer_id: int, *,
                                  slice_size: int = 200,
                                  offset: str | None = None) -> dict:
        """GET /v1/appointments/booking  (APPOINTMENTS_READ)

        Returns all appointment bookings for a customer.
        """
        params: dict[str, Any] = {
            "customerId": int(customer_id),
            "sliceSize": int(slice_size),
        }
        if offset is not None:
            params["offset"] = offset
        return self._get("/v1/appointments/booking", params)

    def appointment_get_booking(self, booking_id: int) -> dict:
        """GET /v1/appointments/booking/{bookingId}  (APPOINTMENTS_READ)"""
        return self._get(f"/v1/appointments/booking/{int(booking_id)}")

    def appointment_cancel(self, booking_id: int) -> int:
        """DELETE /v1/appointments/booking/{bookingId}  (APPOINTMENTS_WRITE)

        Returns HTTP status code (200/204 on success).
        """
        return self._delete(f"/v1/appointments/booking/{int(booking_id)}")

    # ─── Classes (Kurse / Gruppenkurse) ──────────────────────────────

    def class_list(self, *, slice_size: int = 100,
                   offset: str | None = None) -> dict:
        """GET /v1/classes  (CLASSES_READ)

        Returns classes with at least one scheduled slot.
        """
        params: dict[str, Any] = {"sliceSize": int(slice_size)}
        if offset is not None:
            params["offset"] = offset
        return self._get("/v1/classes", params)

    def class_get(self, class_id: int) -> dict:
        """GET /v1/classes/{classId}  (CLASSES_READ)"""
        return self._get(f"/v1/classes/{int(class_id)}")

    def class_list_all_slots(self, *, days_ahead: int | None = None,
                             slot_window_start_date: str | None = None,
                             slice_size: int = 100,
                             offset: str | None = None) -> dict:
        """GET /v1/classes/slots  (CLASSES_READ)

        Returns class slots across all classes within a time window.
        days_ahead: 1-3 (Magicline limit, clamped automatically)
        """
        params: dict[str, Any] = {"sliceSize": int(slice_size)}
        if days_ahead is not None:
            params["daysAhead"] = max(1, min(int(days_ahead), 3))
        if slot_window_start_date is not None:
            params["slotWindowStartDate"] = slot_window_start_date
        if offset is not None:
            params["offset"] = offset
        return self._get("/v1/classes/slots", params)

    def class_list_slots(self, class_id: int, *,
                         slice_size: int = 100,
                         offset: str | None = None) -> dict:
        """GET /v1/classes/{classId}/slots  (CLASSES_READ)

        Returns slots for a specific class.
        """
        params: dict[str, Any] = {"sliceSize": int(slice_size)}
        if offset is not None:
            params["offset"] = offset
        return self._get(f"/v1/classes/{int(class_id)}/slots", params)

    def class_get_slot(self, class_id: int, slot_id: int) -> dict:
        """GET /v1/classes/{classId}/slots/{slotId}  (CLASSES_READ)"""
        return self._get(f"/v1/classes/{int(class_id)}/slots/{int(slot_id)}")

    def class_validate_booking(self, *, slot_id: int, customer_id: int) -> dict:
        """POST /v1/classes/booking/validate  (CLASSES_WRITE)

        Check if customer can book this class slot. Always call before book().
        """
        return self._post("/v1/classes/booking/validate", {
            "classSlotId": int(slot_id),
            "customerId": int(customer_id),
        })

    def class_book(self, *, slot_id: int, customer_id: int) -> dict:
        """POST /v1/classes/booking/book  (CLASSES_WRITE)

        Book a class slot for a customer. Call validate first.
        """
        return self._post("/v1/classes/booking/book", {
            "classSlotId": int(slot_id),
            "customerId": int(customer_id),
        })

    def class_list_bookings(self, customer_id: int, *,
                            slice_size: int = 200,
                            offset: str | None = None) -> dict:
        """GET /v1/classes/booking  (CLASSES_READ)

        Returns all class bookings for a customer.
        """
        params: dict[str, Any] = {
            "customerId": int(customer_id),
            "sliceSize": int(slice_size),
        }
        if offset is not None:
            params["offset"] = offset
        return self._get("/v1/classes/booking", params)

    def class_get_booking(self, booking_id: int) -> dict:
        """GET /v1/classes/booking/{bookingId}  (CLASSES_READ)"""
        return self._get(f"/v1/classes/booking/{int(booking_id)}")

    def class_cancel_booking(self, booking_id: int) -> int:
        """DELETE /v1/classes/booking/{bookingId}  (CLASSES_WRITE)

        Returns HTTP status code.
        """
        return self._delete(f"/v1/classes/booking/{int(booking_id)}")

    # ─── Pagination helper (workflow layer) ──────────────────────────

    @staticmethod
    def iter_pages(fetch_fn, **kwargs) -> list[dict]:
        """Generic pagination loop. Works with any list endpoint.

        Usage:
            all_customers = MagiclineClient.iter_pages(
                client.customer_list, customer_status="MEMBER", slice_size=200
            )
        """
        results: list[dict] = []
        offset = None
        while True:
            res = fetch_fn(offset=offset, **kwargs)
            items = res.get("result") if isinstance(res, dict) else None
            if not isinstance(items, list):
                break
            results.extend(items)
            if not res.get("hasNext"):
                break
            offset = res.get("offset")
            if offset is None:
                break
        return results


# ─── Backward compatibility ──────────────────────────────────────────
# Map old method names so existing worker/initial_sync code doesn't break.

_COMPAT = {
    "get_customer": "customer_get",
    "get_customer_contracts": "customer_contracts",
    "get_comm_prefs": "customer_comm_prefs",
    "list_customers": "customer_list",
    "list_appointment_bookings_by_customer": "appointment_list_bookings",
    "get_appointment_booking": "appointment_get_booking",
    "list_class_bookings_by_customer": "class_list_bookings",
    "get_class_booking": "class_get_booking",
    "get_class_slot": "class_get_slot",
    "confirm_activation": "studio_confirm_activation",
}
for _old, _new in _COMPAT.items():
    if not hasattr(MagiclineClient, _old):
        setattr(MagiclineClient, _old, getattr(MagiclineClient, _new))
