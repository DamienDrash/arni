"""ARIIA v2.0 – Magicline Integration Adapter.

@ARCH: Contacts-Sync Refactoring
Concrete adapter for the Magicline CRM/Booking system. Implements both
the capability execution interface (for the agent runtime) AND the
contact sync interface (for the sync engine).

Contact Sync Data Points (MANDATORY – preserved from legacy):
  - Contract/Plan: name, status, start/end, cancellation
  - Pause Info: currently paused, until, reason, paused days (180d)
  - Check-in Stats: 30d/90d totals, avg/week, last visit, days since
  - Churn Prediction: score (0-100), risk level, reasons
  - Training Preferences: preferred sessions, days, time of day
  - Bookings: upcoming (next 10), past (last 200)
  - Additional Fields: training goals, health notes, comm prefs
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog

from app.integrations.adapters.base import (
    AdapterResult,
    BaseAdapter,
    ConnectionTestResult,
    NormalizedContact,
    SyncDirection,
    SyncMode,
    SyncResult,
)

logger = structlog.get_logger()

# ─── Magicline-specific helpers (migrated from contact_sync.py) ──────────────

_FALLBACK_FIELD_NAMES: dict[int, str] = {
    1229489651: "Trainingsziele",
    1229489650: "Anamnese_Hinweise",
}


def _safe_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _safe_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _pick_phone(payload: dict[str, Any]) -> str | None:
    for key in ("phonePrivateMobile", "phonePrivate", "phoneBusinessMobile", "phoneBusiness"):
        v = payload.get(key)
        if v:
            return str(v).strip()
    return None


def _overlap_days(start: date, end: date, window_start: date, window_end: date) -> int:
    a = max(start, window_start)
    b = min(end, window_end)
    return max(0, (b - a).days + 1) if b >= a else 0


def _build_pause_info(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Build structured pause info from Magicline idle periods."""
    periods = raw.get("idlePeriods") or []
    if not periods:
        return None

    today = date.today()
    window_start = today - timedelta(days=180)
    paused_days_180 = 0
    is_currently_paused = False
    pause_until: str | None = None
    pause_reason: str | None = None

    for p in periods:
        if not isinstance(p, dict):
            continue
        start = _safe_iso_date(p.get("startDate"))
        if not start:
            continue
        unlimited = bool(p.get("unlimited", False))
        end = _safe_iso_date(p.get("endDate")) or (today if unlimited else None)
        reason = (
            str(p.get("reason") or p.get("description") or p.get("comment") or "").strip()
            or None
        )

        if end:
            paused_days_180 += _overlap_days(start, end, window_start, today)

        if start <= today and (unlimited or (end and today <= end)):
            is_currently_paused = True
            if not unlimited and end:
                if pause_until is None or end.isoformat() > pause_until:
                    pause_until = end.isoformat()
            if reason:
                pause_reason = reason

    return {
        "is_currently_paused": is_currently_paused,
        "pause_until": pause_until,
        "pause_reason": pause_reason,
        "paused_days_180": max(0, paused_days_180),
    }


def _resolve_additional_info(raw: dict[str, Any], field_defs: dict[int, str]) -> dict[str, Any]:
    """Map additionalInformationFieldAssignments to {field_name: value}."""
    assignments = raw.get("additionalInformationFieldAssignments") or []
    result: dict[str, Any] = {}
    for a in assignments:
        fid = a.get("additionalInformationFieldId")
        val = a.get("value")
        if fid is not None and val is not None:
            fid_int = int(fid)
            name = field_defs.get(fid_int) or _FALLBACK_FIELD_NAMES.get(fid_int) or f"field_{fid_int}"
            result[name] = val
    return result


def _build_contract_info(client: Any, customer_id: int) -> dict[str, Any] | None:
    """Fetch active contracts for a member and return structured info."""
    try:
        contracts = client.customer_contracts(customer_id, status="ACTIVE")
        if not contracts:
            return None
        c = contracts[0]
        return {
            "plan_name": c.get("rateName") or c.get("name") or "Unbekannt",
            "status": "ACTIVE",
            "start_date": c.get("startDate"),
            "end_date": c.get("endDate"),
            "is_canceled": bool(c.get("cancellationDate")),
        }
    except Exception:
        return None


def _determine_lifecycle(raw: dict[str, Any], contract_info: dict | None) -> str:
    """Determine lifecycle stage from Magicline data."""
    if contract_info and contract_info.get("status") == "ACTIVE":
        if contract_info.get("is_canceled"):
            return "churned"
        return "customer"
    status = raw.get("customerStatus") or raw.get("status")
    if status == "MEMBER":
        return "customer"
    if status == "LEAD":
        return "lead"
    return "subscriber"


def _extract_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, list):
            return [x for x in result if isinstance(x, dict)]
    return []


def _compute_checkin_stats(checkins_90: list[dict], checkins_30: list[dict]) -> dict:
    today = date.today()
    total_90 = len(checkins_90)
    total_30 = len(checkins_30)
    avg_per_week = round(total_90 / 12.857, 1)

    last_visit: str | None = None
    days_since = 999
    if checkins_90:
        sorted_ci = sorted(checkins_90, key=lambda c: c.get("checkInDateTime") or "", reverse=True)
        raw_dt = sorted_ci[0].get("checkInDateTime")
        dt = _safe_datetime(raw_dt)
        if dt:
            last_visit = dt.date().isoformat()
            days_since = (today - dt.date()).days

    status = "AKTIV" if days_since <= 30 else "INAKTIV"

    return {
        "total_30d": total_30,
        "total_90d": total_90,
        "avg_training_30d_per_week": round(total_30 / 4.285, 1),
        "avg_training_90d_per_week": round(total_90 / 12.857, 1),
        "avg_per_week": avg_per_week,
        "last_visit": last_visit,
        "days_since_last": days_since,
        "status": status,
        "source": "checkins",
    }


def _compute_booking_stats(past_bookings: list[dict]) -> dict:
    """Compute visit-frequency stats from completed bookings (fallback)."""
    today = date.today()
    cutoff_30 = (today - timedelta(days=30)).isoformat()
    cutoff_90 = (today - timedelta(days=90)).isoformat()

    completed = [b for b in past_bookings if b.get("status", "").upper() in ("COMPLETED",)]
    total_90 = len([b for b in completed if (b.get("start") or "") >= cutoff_90])
    total_30 = len([b for b in completed if (b.get("start") or "") >= cutoff_30])

    if completed:
        starts = [str(b.get("start")) for b in completed if b.get("start")]
        oldest_dt = _safe_datetime(min(starts)) if starts else None
        actual_days = (today - oldest_dt.date()).days + 1 if oldest_dt else 90
        weeks = max(actual_days / 7, 1)
    else:
        weeks = 12.857
    avg_per_week = round(len(completed) / weeks, 1)

    last_visit: str | None = None
    days_since = 999
    if completed:
        sorted_b = sorted(completed, key=lambda b: b.get("start") or "", reverse=True)
        dt = _safe_datetime(sorted_b[0].get("start"))
        if dt:
            last_visit = dt.date().isoformat()
            days_since = (today - dt.date()).days

    categories: dict[str, int] = {}
    for b in completed:
        t = b.get("title") or "?"
        categories[t] = categories.get(t, 0) + 1
    top_category = max(categories, key=lambda k: categories[k]) if categories else None

    status = "AKTIV" if days_since <= 30 else "INAKTIV"

    return {
        "total_30d": total_30,
        "total_90d": total_90,
        "avg_training_30d_per_week": round(total_30 / 4.285, 1),
        "avg_training_90d_per_week": round(total_90 / 12.857, 1),
        "avg_per_week": avg_per_week,
        "last_visit": last_visit,
        "days_since_last": days_since,
        "status": status,
        "top_category": top_category,
        "source": "bookings",
    }


def _derive_training_preferences(bookings: dict[str, list[dict]]) -> dict[str, Any]:
    upcoming = bookings.get("upcoming") or []
    past = bookings.get("past") or []
    last_appointment = past[0] if past else None
    next_appointment = upcoming[0] if upcoming else None

    title_counts: dict[str, int] = {}
    weekday_counts: dict[int, int] = {}
    daytime_counts: dict[str, int] = {"morning": 0, "afternoon": 0, "evening": 0}
    for row in past:
        title = str(row.get("title") or "?").strip()
        if title:
            title_counts[title] = title_counts.get(title, 0) + 1
        dt = _safe_datetime(row.get("start"))
        if not dt:
            continue
        weekday_counts[dt.weekday()] = weekday_counts.get(dt.weekday(), 0) + 1
        hour = dt.hour
        if hour < 12:
            daytime_counts["morning"] += 1
        elif hour < 17:
            daytime_counts["afternoon"] += 1
        else:
            daytime_counts["evening"] += 1

    preferred_sessions = [k for k, _ in sorted(title_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]]
    weekday_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    preferred_weekdays = [
        weekday_map[idx] for idx in sorted(weekday_counts.keys()) if 0 <= idx < len(weekday_map)
    ]
    preferred_daytime = max(daytime_counts, key=lambda k: daytime_counts[k]) if sum(daytime_counts.values()) > 0 else None

    return {
        "next_appointment": next_appointment,
        "last_appointment": last_appointment,
        "preferred_training_sessions": preferred_sessions,
        "preferred_training_days": preferred_weekdays,
        "preferred_training_time": preferred_daytime,
    }


def _compute_churn_prediction(
    stats: dict[str, Any],
    bookings: dict[str, list[dict]],
    is_paused: bool | None,
    pause_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    raw_days_since = stats.get("days_since_last")
    days_since = int(raw_days_since) if raw_days_since is not None else 999
    total_30 = int(stats.get("total_30d") or 0)
    total_90 = int(stats.get("total_90d") or 0)
    upcoming_count = len(bookings.get("upcoming") or [])

    pause_info = pause_info or {}
    is_currently_paused = bool(pause_info.get("is_currently_paused") or is_paused)
    paused_days_180 = int(pause_info.get("paused_days_180") or 0)
    last_pause_end = _safe_datetime(pause_info.get("last_pause_end"))
    days_since_pause_end = (date.today() - last_pause_end.date()).days if last_pause_end else None
    recent_pause = days_since_pause_end is not None and days_since_pause_end <= 30

    if is_currently_paused:
        score += 10
        reasons.append("membership_paused_current")
    else:
        if days_since >= 45:
            score += 40
            reasons.append("no_recent_activity_45d")
        elif days_since >= 30:
            score += 25
            reasons.append("no_recent_activity_30d")
        elif days_since >= 14:
            score += 10
            reasons.append("declining_recent_activity")
        if total_30 == 0:
            score += 20
            reasons.append("zero_sessions_30d")
        elif total_30 <= 2:
            score += 10
            reasons.append("low_sessions_30d")
    if total_90 <= 4:
        score += 15
        reasons.append("low_sessions_90d")
    if upcoming_count == 0:
        score += 10
        reasons.append("no_upcoming_appointments")
    else:
        score -= min(10, upcoming_count * 3)

    if recent_pause:
        score = max(0, score - 20)
        reasons.append("recent_pause_grace")
    elif paused_days_180 >= 30:
        score = max(0, score - 10)
        reasons.append("extended_pause_context")

    score = max(0, min(100, score))
    if score >= 70:
        risk = "high"
    elif score >= 40:
        risk = "medium"
    else:
        risk = "low"

    return {"score": score, "risk": risk, "reasons": reasons}


def _fetch_recent_bookings(client: Any, customer_id: int) -> dict:
    """Fetch and split bookings into upcoming and past."""
    today_str = date.today().isoformat()
    all_bookings: list[dict] = []

    # Appointment bookings
    try:
        apt_payload = client.appointment_list_bookings(customer_id, slice_size=50)
        for item in _extract_items(apt_payload):
            start = item.get("startDateTime")
            title = (
                item.get("title") or item.get("bookableAppointmentName")
                or item.get("name") or "Termin"
            )
            status = item.get("appointmentStatus") or item.get("bookingStatus") or ""
            all_bookings.append({
                "type": "appointment", "title": str(title),
                "start": start, "status": str(status).upper(),
            })
    except Exception as e:
        logger.warning("magicline_adapter.appointments_failed", customer_id=customer_id, error=str(e))

    # Class bookings
    try:
        class_payload = client.class_list_bookings(customer_id, slice_size=50)
        for item in _extract_items(class_payload):
            class_info = item.get("classInformation") or {}
            class_details = item.get("classDetails") or {}
            title = (
                item.get("title")
                or (class_info.get("name") if isinstance(class_info, dict) else None)
                or (class_details.get("name") if isinstance(class_details, dict) else None)
                or item.get("className") or "Kurs"
            )
            start = item.get("startDateTime")
            status = item.get("classSlotStatus") or item.get("bookingStatus") or ""
            all_bookings.append({
                "type": "class", "title": str(title),
                "start": start, "status": str(status).upper(),
            })
    except Exception as e:
        logger.warning("magicline_adapter.classes_failed", customer_id=customer_id, error=str(e))

    completed_statuses = {"COMPLETED", "ATTENDED"}
    upcoming_statuses = {"BOOKED", "PLANNED", "CONFIRMED"}
    past = []
    upcoming = []
    for b in all_bookings:
        start = b.get("start") or ""
        status = str(b.get("status") or "").upper()
        if status in completed_statuses:
            past.append(b)
            continue
        if status in ("CANCELED", "ABSENT", "NO_SHOW"):
            continue
        if status in upcoming_statuses and start >= today_str:
            upcoming.append(b)
        elif start < today_str:
            past.append(b)

    past.sort(key=lambda b: b.get("start") or "", reverse=True)
    upcoming.sort(key=lambda b: b.get("start") or "")

    return {"upcoming": upcoming[:10], "past": past[:200]}


# ─── Adapter Class ───────────────────────────────────────────────────────────

class MagiclineAdapter(BaseAdapter):
    """Adapter for the Magicline CRM and booking system.

    Implements both capability execution (agent runtime) and contact sync
    (sync engine) with full enrichment data preservation.
    """

    @property
    def integration_id(self) -> str:
        return "magicline"

    @property
    def display_name(self) -> str:
        return "Magicline"

    @property
    def category(self) -> str:
        return "fitness"

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

    @property
    def supported_sync_directions(self) -> list[SyncDirection]:
        return [SyncDirection.INBOUND]

    @property
    def supports_incremental_sync(self) -> bool:
        return False  # Magicline API does not support delta queries

    def get_config_schema(self) -> Dict[str, Any]:
        """Return the configuration schema for Magicline setup."""
        return {
            "fields": [
                {
                    "key": "base_url",
                    "label": "Magicline API URL",
                    "type": "text",
                    "required": True,
                    "placeholder": "https://api.magicline.com/connect/v1",
                    "help_text": "Die Basis-URL der Magicline Open API für Ihr Studio.",
                },
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "required": True,
                    "help_text": "Ihr Magicline API-Schlüssel. Benötigt die Berechtigungen: CUSTOMER_READ, CONTRACT_READ, CHECKIN_READ, BOOKING_READ.",
                },
                {
                    "key": "studio_id",
                    "label": "Studio ID",
                    "type": "text",
                    "required": False,
                    "help_text": "Optionale Studio-ID für Multi-Studio-Setups.",
                },
                {
                    "key": "checkin_enabled",
                    "label": "Check-in-System aktiv",
                    "type": "toggle",
                    "required": False,
                    "default": True,
                    "help_text": "Aktivieren Sie dies, wenn Ihr Studio das Magicline Check-in-System nutzt. Andernfalls werden Buchungsdaten als Fallback verwendet.",
                },
                {
                    "key": "sync_members_only",
                    "label": "Nur aktive Mitglieder synchronisieren",
                    "type": "toggle",
                    "required": False,
                    "default": True,
                    "help_text": "Wenn aktiviert, werden nur Kunden mit Status 'MEMBER' synchronisiert. Deaktivieren für alle Kunden inkl. Leads.",
                },
                {
                    "key": "enrich_on_sync",
                    "label": "Enrichment bei Sync",
                    "type": "toggle",
                    "required": False,
                    "default": True,
                    "help_text": "Wenn aktiviert, werden Check-in-Statistiken, Buchungen, Churn-Score und Trainings-Präferenzen bei jedem Sync aktualisiert.",
                },
            ],
        }

    # ── Contact Sync ─────────────────────────────────────────────────────

    async def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        """Test the Magicline API connection with provided credentials."""
        from app.integrations.magicline.client import MagiclineClient

        base_url = config.get("base_url", "")
        api_key = config.get("api_key", "")

        if not base_url or not api_key:
            return ConnectionTestResult(
                success=False,
                message="API URL und API Key sind erforderlich.",
            )

        start = time.monotonic()
        try:
            client = MagiclineClient(base_url=base_url, api_key=api_key, timeout=10)
            # Try fetching a single customer to verify credentials
            result = client.customer_list(slice_size=1)
            latency = (time.monotonic() - start) * 1000

            if isinstance(result, dict) and "error" in result:
                return ConnectionTestResult(
                    success=False,
                    message=f"API-Fehler: {result.get('error', 'Unbekannt')}",
                    latency_ms=latency,
                )

            return ConnectionTestResult(
                success=True,
                message="Verbindung erfolgreich. Magicline API ist erreichbar.",
                details={"api_version": "v1", "records_available": True},
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            error_msg = str(e)
            if "401" in error_msg:
                return ConnectionTestResult(
                    success=False,
                    message="Authentifizierung fehlgeschlagen. Bitte API-Key überprüfen.",
                    latency_ms=latency,
                )
            if "403" in error_msg:
                return ConnectionTestResult(
                    success=False,
                    message="Zugriff verweigert. Bitte API-Berechtigungen überprüfen (CUSTOMER_READ benötigt).",
                    latency_ms=latency,
                )
            return ConnectionTestResult(
                success=False,
                message=f"Verbindungsfehler: {error_msg}",
                latency_ms=latency,
            )

    async def get_contacts(
        self,
        tenant_id: int,
        config: Dict[str, Any],
        last_sync_at: Optional[datetime] = None,
        sync_mode: SyncMode = SyncMode.FULL,
    ) -> SyncResult:
        """Fetch all contacts from Magicline with full enrichment.

        This method integrates the logic from:
          - contact_sync.py (basic contact data + contract + pause)
          - member_enrichment.py (check-ins, bookings, churn, preferences)
        """
        from app.integrations.magicline.client import MagiclineClient

        base_url = config.get("base_url", "")
        api_key = config.get("api_key", "")
        checkin_enabled = config.get("checkin_enabled", True)
        sync_members_only = config.get("sync_members_only", True)
        enrich_on_sync = config.get("enrich_on_sync", True)

        if not base_url or not api_key:
            return SyncResult(success=False, error_message="Magicline nicht konfiguriert: API URL und Key fehlen.")

        start_time = time.monotonic()
        client = MagiclineClient(base_url=base_url, api_key=api_key)

        # Load additional-info field definitions
        field_defs: dict[int, str] = {}
        try:
            defs = client.customer_additional_info_fields()
            for d in defs:
                fid = d.get("id")
                name = str(d.get("name") or d.get("abbreviation") or "").strip()
                if fid is not None and name:
                    field_defs[int(fid)] = name
        except Exception as e:
            logger.warning("magicline_adapter.field_defs_failed", error=str(e))

        # Fetch customers
        try:
            customer_status = "MEMBER" if sync_members_only else None
            rows = list(MagiclineClient.iter_pages(
                client.customer_list,
                customer_status=customer_status,
                slice_size=200,
            ))
        except Exception as e:
            msg = str(e)
            if "403" in msg or "permission" in msg.lower():
                return SyncResult(
                    success=False,
                    error_message="Magicline API-Zugriff verweigert (403). Bitte CUSTOMER_READ Berechtigung prüfen.",
                )
            if "401" in msg:
                return SyncResult(success=False, error_message="Magicline Authentifizierung fehlgeschlagen (401).")
            return SyncResult(success=False, error_message=f"Fehler beim Abrufen der Kunden: {msg}")

        # Convert to NormalizedContact objects
        contacts: List[NormalizedContact] = []
        errors: List[Dict[str, Any]] = []

        for raw in rows:
            customer_id = raw.get("id")
            if customer_id is None:
                continue
            try:
                customer_id = int(customer_id)
            except (TypeError, ValueError):
                continue

            first_name = str(raw.get("firstName") or "").strip()
            last_name = str(raw.get("lastName") or "").strip()
            if not first_name and not last_name:
                continue

            try:
                # Language
                lang_obj = raw.get("preferredLanguage") or {}
                preferred_language = (
                    str(lang_obj.get("languageCode") or "").strip().lower() or "de"
                    if isinstance(lang_obj, dict) else "de"
                )

                # Contract info
                contract_info = _build_contract_info(client, customer_id)
                pause_info = _build_pause_info(raw)
                additional_info = _resolve_additional_info(raw, field_defs)
                member_number = str(raw.get("customerNumber") or "").strip() or None

                # Address
                addr = raw.get("address") or {}
                address_street = None
                address_city = None
                address_zip = None
                address_country = None
                if isinstance(addr, dict):
                    street = str(addr.get("street") or "").strip()
                    house = str(addr.get("houseNumber") or "").strip()
                    address_street = f"{street} {house}".strip() or None
                    address_city = str(addr.get("city") or "").strip() or None
                    address_zip = str(addr.get("zipCode") or "").strip() or None
                    address_country = str(addr.get("country") or "").strip() or None

                # Communication preferences
                comm_prefs: list[str] = []
                try:
                    prefs = client.customer_comm_prefs(customer_id)
                    if prefs:
                        for p in prefs:
                            if p.get("allowed"):
                                comm_prefs.append(p.get("type", "Unknown"))
                except Exception:
                    pass

                # Build custom fields
                custom_fields: Dict[str, Any] = {}

                # Contract data
                if contract_info:
                    custom_fields["vertrag"] = contract_info.get("plan_name", "")
                    custom_fields["vertrag_status"] = contract_info.get("status", "")
                    if contract_info.get("start_date"):
                        custom_fields["vertrag_start"] = contract_info["start_date"]
                    if contract_info.get("end_date"):
                        custom_fields["vertrag_ende"] = contract_info["end_date"]
                    custom_fields["vertrag_gekuendigt"] = contract_info.get("is_canceled", False)

                # Pause data
                if pause_info:
                    custom_fields["pausiert"] = pause_info.get("is_currently_paused", False)
                    if pause_info.get("pause_until"):
                        custom_fields["pause_bis"] = pause_info["pause_until"]
                    if pause_info.get("pause_reason"):
                        custom_fields["pause_grund"] = pause_info["pause_reason"]
                    custom_fields["pausentage_180d"] = pause_info.get("paused_days_180", 0)

                # Additional info fields (training goals, health notes)
                if additional_info:
                    custom_fields.update(additional_info)

                # Communication preferences
                if comm_prefs:
                    custom_fields["kontakt_erlaubnis"] = ", ".join(comm_prefs)

                # Member number
                if member_number:
                    custom_fields["mitgliedsnummer"] = member_number

                # Preferred language
                custom_fields["sprache"] = preferred_language

                # ── Enrichment (check-ins, bookings, churn, preferences) ──
                if enrich_on_sync:
                    # Check-in stats
                    checkins_90: list[dict] = []
                    checkins_30: list[dict] = []
                    if checkin_enabled:
                        try:
                            today = date.today()
                            from_date = (today - timedelta(days=90)).isoformat()
                            to_date = today.isoformat()
                            cutoff_30 = (today - timedelta(days=30)).isoformat()
                            offset = 0
                            while True:
                                payload = client.customer_checkins(
                                    customer_id, from_date=from_date,
                                    to_date=to_date, slice_size=50, offset=offset,
                                )
                                page = _extract_items(payload)
                                checkins_90.extend(page)
                                has_next = payload.get("hasNext", False) if isinstance(payload, dict) else False
                                if not has_next or not page:
                                    break
                                offset += 50
                            checkins_30 = [c for c in checkins_90 if (c.get("checkInDateTime") or "") >= cutoff_30]
                        except Exception as e:
                            logger.warning("magicline_adapter.checkins_failed", customer_id=customer_id, error=str(e))

                    checkin_stats = _compute_checkin_stats(checkins_90, checkins_30)

                    # Bookings
                    bookings = _fetch_recent_bookings(client, customer_id)

                    # Fallback: booking-based stats if no check-in data
                    if checkin_stats["total_90d"] == 0 and bookings.get("past"):
                        checkin_stats = _compute_booking_stats(bookings["past"])

                    checkin_stats["checkin_enabled"] = checkin_enabled

                    # Training preferences
                    training_prefs = _derive_training_preferences(bookings)

                    # Churn prediction
                    churn = _compute_churn_prediction(
                        checkin_stats, bookings,
                        pause_info.get("is_currently_paused") if pause_info else False,
                        pause_info,
                    )

                    # Store enrichment in custom_fields
                    custom_fields["checkin_stats"] = checkin_stats
                    custom_fields["churn_prediction"] = churn
                    custom_fields["training_preferences"] = training_prefs
                    custom_fields["bookings_upcoming"] = bookings.get("upcoming", [])
                    custom_fields["bookings_past_count"] = len(bookings.get("past", []))

                # Build tags
                tags: List[str] = ["magicline"]
                lifecycle = _determine_lifecycle(raw, contract_info)
                if pause_info and pause_info.get("is_currently_paused"):
                    tags.append("pausiert")
                if contract_info and contract_info.get("is_canceled"):
                    tags.append("gekündigt")
                if enrich_on_sync and custom_fields.get("churn_prediction", {}).get("risk") == "high":
                    tags.append("churn-risiko-hoch")

                nc = NormalizedContact(
                    external_id=str(customer_id),
                    source="magicline",
                    first_name=first_name or "-",
                    last_name=last_name or "-",
                    email=str(raw.get("email") or "").strip() or None,
                    phone=_pick_phone(raw),
                    address_street=address_street,
                    address_city=address_city,
                    address_zip=address_zip,
                    address_country=address_country,
                    date_of_birth=str(raw.get("dateOfBirth") or "").strip() or None,
                    gender=str(raw.get("gender") or "").strip() or None,
                    tags=tags,
                    lifecycle_stage=lifecycle,
                    custom_fields=custom_fields,
                    raw_data=raw,
                )
                contacts.append(nc)

            except Exception as e:
                errors.append({
                    "customer_id": customer_id,
                    "error": str(e),
                })
                logger.warning("magicline_adapter.contact_error", customer_id=customer_id, error=str(e))

        duration = (time.monotonic() - start_time) * 1000

        logger.info(
            "magicline_adapter.sync_complete",
            tenant_id=tenant_id,
            fetched=len(rows),
            contacts=len(contacts),
            errors=len(errors),
            duration_ms=round(duration, 1),
        )

        return SyncResult(
            success=True,
            records_fetched=len(rows),
            contacts=contacts,
            errors=errors,
            records_failed=len(errors),
            duration_ms=duration,
            metadata={
                "source": "magicline",
                "enrichment_enabled": enrich_on_sync,
                "checkin_enabled": checkin_enabled,
                "members_only": sync_members_only,
            },
        )

    # ── Capability Execution (Agent Runtime) ─────────────────────────────

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Route capability to the appropriate Magicline tool function."""
        from app.swarm.tools import magicline as ml_tools

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
            return AdapterResult(success=False, error=f"No handler for '{capability_id}'", error_code="NO_HANDLER")
        return await handler(tenant_id, **kwargs)

    # ─── CRM Capabilities ────────────────────────────────────────────────

    async def _customer_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import get_member_status
        user_identifier = kwargs.get("email") or kwargs.get("name") or kwargs.get("phone") or kwargs.get("query", "")
        if not user_identifier:
            return AdapterResult(success=False, error="Bitte E-Mail, Name oder Telefonnummer angeben.", error_code="MISSING_IDENTIFIER")
        try:
            result = get_member_status(user_identifier=user_identifier, tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SEARCH_FAILED")

    async def _customer_status(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import get_member_status
        user_identifier = kwargs.get("user_identifier") or kwargs.get("email") or kwargs.get("name", "")
        if not user_identifier:
            return AdapterResult(success=False, error="Kundenbezeichner erforderlich.", error_code="MISSING_IDENTIFIER")
        try:
            result = get_member_status(user_identifier=user_identifier, tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="STATUS_FAILED")

    async def _class_schedule(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import get_class_schedule
        try:
            result = get_class_schedule(date_str=kwargs.get("date", ""), tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SCHEDULE_FAILED")

    async def _class_book(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import class_book
        slot_id = kwargs.get("slot_id")
        if not slot_id:
            return AdapterResult(success=False, error="slot_id erforderlich.", error_code="MISSING_SLOT_ID")
        try:
            result = class_book(slot_id=int(slot_id), user_identifier=kwargs.get("user_identifier"), tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="BOOK_FAILED")

    async def _appointment_slots(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import get_appointment_slots
        try:
            result = get_appointment_slots(category=kwargs.get("category", "all"), days=int(kwargs.get("days", 3)), tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SLOTS_FAILED")

    async def _appointment_book(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import book_appointment_by_time
        required = ["category", "date", "time"]
        missing = [k for k in required if not kwargs.get(k)]
        if missing:
            return AdapterResult(success=False, error=f"Fehlende Parameter: {', '.join(missing)}", error_code="MISSING_PARAMS")
        try:
            result = book_appointment_by_time(
                category=kwargs["category"], date_str=kwargs["date"],
                time_str=kwargs["time"], user_identifier=kwargs.get("user_identifier"), tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="APPOINTMENT_BOOK_FAILED")

    async def _member_bookings(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import get_member_bookings
        try:
            result = get_member_bookings(
                user_identifier=kwargs.get("user_identifier"), date_str=kwargs.get("date"),
                query=kwargs.get("query"), tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="BOOKINGS_FAILED")

    async def _member_cancel(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import cancel_member_booking
        booking_id = kwargs.get("booking_id")
        if not booking_id:
            return AdapterResult(success=False, error="booking_id erforderlich.", error_code="MISSING_BOOKING_ID")
        try:
            result = cancel_member_booking(
                booking_id=int(booking_id), booking_type=kwargs.get("booking_type", "class"),
                user_identifier=kwargs.get("user_identifier"), tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="CANCEL_FAILED")

    async def _member_reschedule(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import reschedule_member_booking_to_latest
        booking_id = kwargs.get("booking_id")
        if not booking_id:
            return AdapterResult(success=False, error="booking_id erforderlich.", error_code="MISSING_BOOKING_ID")
        try:
            result = reschedule_member_booking_to_latest(
                booking_id=int(booking_id), user_identifier=kwargs.get("user_identifier"), tenant_id=tenant_id,
            )
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="RESCHEDULE_FAILED")

    async def _checkin_history(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import get_checkin_history
        try:
            result = get_checkin_history(days=int(kwargs.get("days", 7)), user_identifier=kwargs.get("user_identifier"), tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="CHECKIN_HISTORY_FAILED")

    async def _checkin_stats(self, tenant_id: int, **kwargs) -> AdapterResult:
        from app.swarm.tools.magicline import get_checkin_stats
        try:
            result = get_checkin_stats(days=int(kwargs.get("days", 90)), user_identifier=kwargs.get("user_identifier"), tenant_id=tenant_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="CHECKIN_STATS_FAILED")
