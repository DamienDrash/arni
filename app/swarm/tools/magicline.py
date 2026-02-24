"""Magicline tools for member-facing support use cases.

This module is intentionally "agent-facing":
- resolves the current member from ARIIA session context
- wraps low-level API calls into safe, user-readable outputs
- keeps write-actions explicit and traceable
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from typing import Any

import structlog

from app.gateway.persistence import persistence
from app.integrations.magicline import get_client
from app.integrations.magicline.member_enrichment import enrich_member

logger = structlog.get_logger()


@dataclass
class MemberContext:
    customer_id: int
    first_name: str
    last_name: str
    source: str

    @property
    def display_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or f"Kunde {self.customer_id}"


def _extract_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, list):
            return [x for x in result if isinstance(x, dict)]
        if isinstance(result, dict):
            return [result]
        return [payload]
    return []


def _first_item(payload: Any) -> dict | None:
    items = _extract_items(payload)
    return items[0] if items else None


def _looks_like_email(value: str) -> bool:
    return "@" in value and "." in value


def _safe_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _safe_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Accept both "Z" and explicit offsets
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _resolve_member_context(user_identifier: str, tenant_id: int | None = None) -> tuple[MemberContext | None, str | None]:
    client = get_client(tenant_id=tenant_id)
    if not client:
        return None, "Magicline Integration ist nicht konfiguriert."

    user_identifier = str(user_identifier).strip()
    session = persistence.get_session_by_user_id(user_identifier, tenant_id=tenant_id)
    email_candidates: list[str] = []
    member_id_candidates: list[str] = []

    if session:
        if session.member_id:
            member_id_candidates.append(str(session.member_id))
        if session.email:
            email_candidates.append(str(session.email))

    # Fallbacks from direct identifier
    if _looks_like_email(user_identifier):
        email_candidates.append(user_identifier)
    if user_identifier.isdigit():
        # Could be CRM customer number/member id from external systems
        member_id_candidates.append(user_identifier)

    # 1) Most reliable path: CRM member/customer number
    for member_id in dict.fromkeys(member_id_candidates):
        try:
            customer = client.customer_get_by(customer_number=member_id)
            item = _first_item(customer)
            if item and (item.get("id") or item.get("customerId")):
                cid = int(item.get("id") or item.get("customerId"))
                return MemberContext(
                    customer_id=cid,
                    first_name=str(item.get("firstName") or ""),
                    last_name=str(item.get("lastName") or ""),
                    source="member_id",
                ), None
        except Exception as e:
            logger.warning("magicline.resolve.member_id_failed", member_id=member_id, error=str(e))

    # 2) Email fallback
    for email in dict.fromkeys(email_candidates):
        try:
            matches = client.customer_search(email=email)
            item = _first_item(matches)
            if item and (item.get("id") or item.get("customerId")):
                cid = int(item.get("id") or item.get("customerId"))
                return MemberContext(
                    customer_id=cid,
                    first_name=str(item.get("firstName") or ""),
                    last_name=str(item.get("lastName") or ""),
                    source="email",
                ), None
        except Exception as e:
            logger.warning("magicline.resolve.email_failed", email=email, error=str(e))

    return (
        None,
        "Ich konnte dein Mitgliedsprofil nicht eindeutig zuordnen. Bitte zuerst Verifizierung mit Mitgliedsnummer durchführen.",
    )


def _normalize_booking(item: dict, booking_type: str) -> dict:
    booking_id = item.get("id") or item.get("bookingId")
    start = item.get("startDateTime") or item.get("start")
    end = item.get("endDateTime") or item.get("end")

    class_info = item.get("classInformation") if isinstance(item.get("classInformation"), dict) else {}
    class_details = item.get("classDetails") if isinstance(item.get("classDetails"), dict) else {}
    title = (
        item.get("title")
        or item.get("name")
        or item.get("bookableAppointmentName")
        or class_info.get("title")
        or class_details.get("name")
        or item.get("className")
        or ("Termin" if booking_type == "appointment" else "Kurs")
    )

    return {
        "type": booking_type,
        "booking_id": int(booking_id) if booking_id is not None else None,
        "title": str(title),
        "start": start,
        "end": end,
        "class_id": item.get("classId"),
        "slot_id": item.get("classSlotId"),
        "bookable_id": item.get("bookableAppointmentId"),
        "raw": item,
    }


def _member_bookings_for_date(client, customer_id: int, target_date: str | None = None) -> list[dict]:
    date_filter = _safe_date(target_date)
    bookings: list[dict] = []

    # Appointment bookings
    try:
        apt_payload = client.appointment_list_bookings(customer_id, slice_size=200)
        for item in _extract_items(apt_payload):
            bookings.append(_normalize_booking(item, "appointment"))
    except Exception as e:
        logger.warning("magicline.bookings.appointment_failed", customer_id=customer_id, error=str(e))

    # Class bookings
    try:
        class_payload = client.class_list_bookings(customer_id, slice_size=200)
        for item in _extract_items(class_payload):
            normalized = _normalize_booking(item, "class")
            # Some class list payloads are sparse; enrich from detail endpoint.
            if (not normalized["start"] or not normalized["title"]) and normalized["booking_id"]:
                try:
                    detail = client.class_get_booking(normalized["booking_id"])
                    merged = {**item, **(_first_item(detail) or detail if isinstance(detail, dict) else {})}
                    normalized = _normalize_booking(merged, "class")
                except Exception:
                    pass
            bookings.append(normalized)
    except Exception as e:
        logger.warning("magicline.bookings.class_failed", customer_id=customer_id, error=str(e))

    filtered: list[dict] = []
    # Statuses that mean the booking is essentially "gone" or "past" in a way we shouldn't act on it
    invalid_statuses = {"CANCELED", "ABSENT", "NO_SHOW", "REJECTED", "DELETED"}
    
    for b in bookings:
        # Check status in the raw payload
        raw = b.get("raw") or {}
        status = str(raw.get("appointmentStatus") or raw.get("bookingStatus") or raw.get("classSlotStatus") or "").upper()
        if status in invalid_statuses:
            continue

        dt = _safe_datetime(b["start"])
        if date_filter and dt and dt.date() != date_filter:
            continue
        filtered.append(b)

    filtered.sort(key=lambda x: _safe_datetime(x.get("start")) or datetime.max)
    return filtered


def _apply_title_filter(bookings: list[dict], query: str | None) -> list[dict]:
    if not query:
        return bookings
    q = query.strip().lower()
    if not q:
        return bookings

    # 1) Explicit booking id (e.g. "123456789")
    if q.isdigit():
        target_id = int(q)
        by_id = [b for b in bookings if b.get("booking_id") == target_id]
        if by_id:
            return by_id

    # 2) Time-based matching (e.g. "16:30" or "termin um 16:30")
    tm = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", q)
    if tm:
        target_hhmm = f"{int(tm.group(1)):02d}:{tm.group(2)}"
        by_time = []
        for b in bookings:
            start = _safe_datetime(b.get("start"))
            if start and start.strftime("%H:%M") == target_hhmm:
                by_time.append(b)
        if by_time:
            return by_time

    # 3) Fuzzy title matching after removing common filler words
    cleaned = re.sub(r"[^a-z0-9äöüß\s]", " ", q)
    tokens = [t for t in cleaned.split() if t and t not in {
        "bitte", "den", "dem", "die", "das", "mein", "meinen", "meine", "meiner",
        "termin", "termine", "kurs", "kurse", "um", "für", "fuer", "am", "heute",
        "morgen", "lösche", "loesche", "storniere", "absagen", "cancel",
    }]
    if not tokens:
        return bookings
    return [
        b for b in bookings
        if all(tok in str(b.get("title", "")).lower() for tok in tokens)
    ]


def _pick_latest_slot(slots: list[dict], target_date: date, now_dt: datetime | None = None) -> dict | None:
    candidates: list[tuple[datetime, dict]] = []
    for slot in slots:
        start = _safe_datetime(slot.get("startDateTime") or slot.get("start"))
        if not start or start.date() != target_date:
            continue
        if now_dt and start <= now_dt:
            continue
        free = slot.get("availableSlots", slot.get("freeCapacity"))
        if free is not None:
            try:
                if int(free) <= 0:
                    continue
            except (TypeError, ValueError):
                pass
        candidates.append((start, slot))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]


def get_class_schedule(date_str: str, tenant_id: int | None = None) -> str:
    """Fetch class schedule for a specific date (YYYY-MM-DD)."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    target_date = _safe_date(date_str)
    if not target_date:
        return "Ungültiges Datum. Bitte YYYY-MM-DD verwenden."

    try:
        slots_payload = client.class_list_all_slots(days_ahead=1, slot_window_start_date=target_date.isoformat())
        slots = _extract_items(slots_payload)
        slots.sort(key=lambda x: _safe_datetime(x.get("startDateTime")) or datetime.max)
        if not slots:
            return f"Keine Kurse für {target_date.isoformat()} gefunden."

        output = [f"Kursplan & Trainer für {target_date.isoformat()}:"]
        for slot in slots:
            start_dt = _safe_datetime(slot.get("startDateTime"))
            time_label = start_dt.strftime("%H:%M") if start_dt else "??:??"
            title = (
                (slot.get("classDetails") or {}).get("name")
                if isinstance(slot.get("classDetails"), dict)
                else None
            ) or slot.get("className") or slot.get("title") or "Kurs"
            instructor = slot.get("instructor")
            trainer_name = "Ein Trainer"
            if isinstance(instructor, dict):
                trainer_name = f"{instructor.get('firstName', '')} {instructor.get('lastName', '')}".strip() or "Ein Trainer"
            
            free = slot.get("availableSlots", slot.get("freeCapacity", "?"))
            output.append(f"- {time_label} Uhr: {title} | Trainer: {trainer_name} | Frei: {free}")

        return "\n".join(output)
    except Exception as e:
        logger.error("magicline.get_class_schedule.failed", error=str(e))
        return f"Fehler beim Abrufen des Kursplans: {e}"


def get_appointment_slots(category: str = "all", days: int = 3, tenant_id: int | None = None) -> str:
    """Fetch available appointment slots for bookable appointment types."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    days = max(1, min(int(days), 14))
    try:
        bookables_payload = client.appointment_list_bookable(slice_size=100)
        bookables = _extract_items(bookables_payload)

        output = [f"Verfügbare Termine (nächste {days} Tage):"]
        found_any = False
        processed = 0
        
        # Clean category for matching
        q = category.lower().strip() if category else "all"
        if q in ("all", "*", ""): q = "all"

        for b in bookables:
            b_name = str(b.get("name") or b.get("title") or "Termin")
            b_id = b.get("id") or b.get("bookableAppointmentId")
            if b_id is None:
                continue
            
            # Fuzzy match: "cardio" matches "CARDIO TRAINING"
            if q != "all" and q not in b_name.lower():
                continue

            try:
                if days <= 3:
                    slots_payload = client.appointment_get_slots(
                        int(b_id),
                        days_ahead=days,
                        slot_window_start_date=date.today().isoformat(),
                    )
                    slots = _extract_items(slots_payload)
                else:
                    slots = client.appointment_get_slots_range(int(b_id), days_total=days)
            except Exception as e:
                logger.warning(
                    "magicline.get_appointment_slots.bookable_failed",
                    bookable_id=b_id,
                    name=b_name,
                    error=str(e),
                )
                continue

            if not slots:
                continue
            processed += 1
            found_any = True
            output.append(f"\n- {b_name} (ID: {b_id})")
            # Show up to 10 slots per category for better selection
            for slot in slots[:10]:
                start = slot.get("startDateTime", "")
                output.append(f"  • {start[:10]} {start[11:16]}")
            if len(slots) > 10:
                output.append(f"  • ... und {len(slots) - 10} weitere")
            if processed >= 10:
                output.append("\n  • ... weitere Terminarten verfügbar")
                break

        if not found_any:
            return "Keine freien Termine gefunden."
        return "\n".join(output)
    except Exception as e:
        logger.error("magicline.get_appointment_slots.failed", error=str(e))
        return "Fehler beim Abrufen der Termine."


def get_member_bookings(
    user_identifier: str,
    date_str: str | None = None,
    query: str | None = None,
    tenant_id: int | None = None,
) -> str:
    """List current member bookings (class + appointment), optionally filtered by date/query."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    member, err = _resolve_member_context(user_identifier, tenant_id=tenant_id)
    if not member:
        return err or "Mitglied konnte nicht aufgelöst werden."

    bookings = _member_bookings_for_date(client, member.customer_id, date_str)
    bookings = _apply_title_filter(bookings, query)
    if not bookings:
        if date_str:
            return f"Keine Termine für {member.display_name} am {date_str} gefunden."
        return f"Keine Termine für {member.display_name} gefunden."

    lines = [f"Termine für {member.display_name}:"]
    for b in bookings:
        start = _safe_datetime(b.get("start"))
        time_label = start.strftime("%Y-%m-%d %H:%M") if start else str(b.get("start") or "unbekannt")
        kind = "Termin" if b["type"] == "appointment" else "Kurs"
        lines.append(f"- [{kind}] {time_label} | {b['title']} | Buchung-ID: {b['booking_id']}")
    return "\n".join(lines)


def cancel_member_booking(
    user_identifier: str,
    date_str: str,
    query: str | None = None,
    tenant_id: int | None = None,
) -> str:
    """Cancel exactly one booking for a member on a given date."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    member, err = _resolve_member_context(user_identifier, tenant_id=tenant_id)
    if not member:
        return err or "Mitglied konnte nicht aufgelöst werden."

    target_date = _safe_date(date_str)
    if not target_date:
        return "Ungültiges Datum. Bitte YYYY-MM-DD verwenden."

    candidates = _apply_title_filter(_member_bookings_for_date(client, member.customer_id, target_date.isoformat()), query)
    if not candidates:
        return f"Keinen passenden Termin am {target_date.isoformat()} gefunden."
    if len(candidates) > 1:
        choices = []
        for c in candidates[:5]:
            start = _safe_datetime(c.get("start"))
            time_str = start.strftime("%H:%M") if start else "unbekannt"
            choices.append(f"- {c['title']} um {time_str} Uhr (ID: {c['booking_id']})")
        
        return (
            "Ich habe mehrere passende Termine gefunden. Welchen meinst du?\n"
            + "\n".join(choices)
        )

    target = candidates[0]
    if not target.get("booking_id"):
        return "Der Termin konnte nicht eindeutig identifiziert werden."

    try:
        if target["type"] == "appointment":
            client.appointment_cancel(int(target["booking_id"]))
        else:
            client.class_cancel_booking(int(target["booking_id"]))
        
        # Invalidate cache so assistant sees updated list
        try:
            enrich_member(member.customer_id, force=True, tenant_id=tenant_id)
        except Exception:
            pass

        return (
            f"Termin gelöscht: {target['title']} am "
            f"{(_safe_datetime(target.get('start')) or datetime.min).strftime('%Y-%m-%d %H:%M')}."
        )
    except Exception as e:
        err_text = str(e)
        err_lower = err_text.lower()
        if "already canceled" in err_lower or "already_canceled" in err_lower:
            return "Der Termin wurde bereits storniert."
        if "404" in err_lower or "not found" in err_lower:
            return "Der Termin wurde im CRM nicht gefunden. Er wurde evtl. schon gelöscht."
        if "409" in err_lower or "conflict" in err_lower:
            return "Der Termin konnte nicht gelöscht werden, weil er bereits geändert wurde. Bitte kurz neu anfragen."
        logger.error("magicline.cancel_member_booking.failed", error=str(e), booking=target)
        return "Beim Löschen des Termins gab es einen technischen Fehler. Bitte versuche es in 30 Sekunden erneut."


def reschedule_member_booking_to_latest(
    user_identifier: str,
    date_str: str,
    query: str | None = None,
    tenant_id: int | None = None,
) -> str:
    """Move one booking on the given date to the latest possible slot on that date."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    member, err = _resolve_member_context(user_identifier, tenant_id=tenant_id)
    if not member:
        return err or "Mitglied konnte nicht aufgelöst werden."

    target_date = _safe_date(date_str)
    if not target_date:
        return "Ungültiges Datum. Bitte YYYY-MM-DD verwenden."

    candidates = _apply_title_filter(_member_bookings_for_date(client, member.customer_id, target_date.isoformat()), query)
    if not candidates:
        return f"Keinen passenden Termin am {target_date.isoformat()} gefunden."
    if len(candidates) > 1:
        choices = "\n".join(
            f"- {c['title']} (ID: {c['booking_id']}, Typ: {c['type']})" for c in candidates[:5]
        )
        return (
            "Ich habe mehrere passende Termine gefunden. Bitte genauer benennen, welcher verschoben werden soll:\n"
            f"{choices}"
        )

    target = candidates[0]
    old_start = _safe_datetime(target.get("start"))
    now_dt = datetime.now(old_start.tzinfo) if old_start and old_start.tzinfo else datetime.now()

    try:
        if target["type"] == "appointment":
            details = target["raw"]
            if not details.get("bookableAppointmentId") and target.get("booking_id"):
                details = client.appointment_get_booking(int(target["booking_id"]))
                details = _first_item(details) or details if isinstance(details, dict) else target["raw"]

            bookable_id = details.get("bookableAppointmentId")
            if not bookable_id:
                return "Umbuchen nicht möglich: bookableAppointmentId fehlt im CRM-Datensatz."

            slots_payload = client.appointment_get_slots(
                int(bookable_id),
                customer_id=member.customer_id,
                days_ahead=3,
                slot_window_start_date=target_date.isoformat(),
            )
            latest_slot = _pick_latest_slot(_extract_items(slots_payload), target_date, now_dt if target_date == date.today() else None)
            if not latest_slot:
                return "Kein späterer freier Zeitslot gefunden."

            start_dt = latest_slot.get("startDateTime")
            end_dt = latest_slot.get("endDateTime")
            if not start_dt or not end_dt:
                return "Ungültiger Slot vom CRM erhalten (fehlende Start/Endzeit)."

            client.appointment_validate(
                bookable_id=int(bookable_id),
                customer_id=member.customer_id,
                start_dt=start_dt,
                end_dt=end_dt,
            )
            new_booking = client.appointment_book(
                bookable_id=int(bookable_id),
                customer_id=member.customer_id,
                start_dt=start_dt,
                end_dt=end_dt,
            )
            if target.get("booking_id"):
                client.appointment_cancel(int(target["booking_id"]))

            # Invalidate cache
            try:
                enrich_member(member.customer_id, force=True, tenant_id=tenant_id)
            except Exception:
                pass

            new_id = (_first_item(new_booking) or new_booking).get("id") if isinstance(new_booking, dict) else None
            return (
                f"Termin geändert: {target['title']} von {old_start.strftime('%H:%M') if old_start else 'unbekannt'} "
                f"auf {_safe_datetime(start_dt).strftime('%H:%M')} Uhr. Neue Buchung-ID: {new_id}."
            )

        # Class reschedule
        details = target["raw"]
        class_id = details.get("classId") or target.get("class_id")
        if not class_id:
            return "Umbuchen nicht möglich: classId fehlt im CRM-Datensatz."

        slots_payload = client.class_list_slots(int(class_id), slice_size=200)
        latest_slot = _pick_latest_slot(_extract_items(slots_payload), target_date, now_dt if target_date == date.today() else None)
        if not latest_slot:
            return "Kein späterer freier Kursslot gefunden."

        new_slot_id = latest_slot.get("id") or latest_slot.get("classSlotId")
        old_slot_id = target.get("slot_id")
        if not new_slot_id:
            return "Ungültiger Kursslot aus CRM erhalten."
        if old_slot_id and int(new_slot_id) == int(old_slot_id):
            return "Der aktuelle Termin ist bereits der spätestmögliche Slot."

        client.class_validate_booking(slot_id=int(new_slot_id), customer_id=member.customer_id)
        new_booking = client.class_book(slot_id=int(new_slot_id), customer_id=member.customer_id)
        if target.get("booking_id"):
            client.class_cancel_booking(int(target["booking_id"]))

        new_id = (_first_item(new_booking) or new_booking).get("id") if isinstance(new_booking, dict) else None
        start_dt = latest_slot.get("startDateTime")
        return (
            f"Kurstermin geändert: {target['title']} auf {_safe_datetime(start_dt).strftime('%H:%M') if start_dt else 'späteren Slot'} "
            f"Uhr. Neue Buchung-ID: {new_id}."
        )
    except Exception as e:
        logger.error("magicline.reschedule_member_booking.failed", error=str(e), booking=target)
        return f"Fehler beim Umbuchen: {e}"


def get_checkin_history(days: int = 7, user_identifier: str | None = None, tenant_id: int | None = None) -> str:
    """Get check-ins for the resolved member."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    member, err = _resolve_member_context(user_identifier or "", tenant_id=tenant_id)
    if not member:
        return err or "Mitglied konnte nicht aufgelöst werden."

    try:
        today = date.today()
        from_date = (today - timedelta(days=max(1, int(days)))).isoformat()
        checkins = client.customer_checkins(member.customer_id, from_date=from_date)
        items = _extract_items(checkins)
        if not items:
            return f"{member.display_name} war in den letzten {days} Tagen nicht eingecheckt."

        lines = [f"Check-ins von {member.display_name} (letzte {days} Tage):"]
        for c in items:
            dt = c.get("checkInDateTime") or c.get("checkinTime") or c.get("timestamp")
            ts = _safe_datetime(dt)
            lines.append(f"- {ts.strftime('%Y-%m-%d %H:%M') if ts else str(dt)}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("magicline.get_checkin_history.failed", error=str(e))
        return "Fehler beim Abrufen der Check-ins."


def get_member_status(user_identifier: str, tenant_id: int | None = None) -> str:
    """Check membership status and active contracts."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    member, err = _resolve_member_context(user_identifier, tenant_id=tenant_id)
    if not member:
        return err or "Mitglied konnte nicht aufgelöst werden."

    try:
        contracts = client.customer_contracts(member.customer_id, status="ACTIVE")
        if not contracts:
            return f"Mitglied {member.display_name}: Kein aktiver Vertrag."

        contract_names = [str(c.get("rateName") or c.get("name") or "Tarif") for c in contracts]
        end_date = contracts[0].get("endDate", "unbekannt")
        return f"Mitglied {member.display_name}: Aktiv ({', '.join(contract_names)}). Vertragsende: {end_date}."
    except Exception as e:
        logger.error("magicline.get_member_status.failed", error=str(e))
        return f"Fehler beim Abrufen des Mitgliederstatus: {e}"


def class_book(slot_id: int, user_identifier: str | None = None, tenant_id: int | None = None) -> str:
    """Book a class slot for the resolved member."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    member, err = _resolve_member_context(user_identifier or "", tenant_id=tenant_id)
    if not member:
        return err or "Mitglied konnte nicht aufgelöst werden."

    try:
        client.class_validate_booking(slot_id=int(slot_id), customer_id=member.customer_id)
        result = client.class_book(slot_id=int(slot_id), customer_id=member.customer_id)
        booking = _first_item(result) or (result if isinstance(result, dict) else {})
        booking_id = booking.get("id", "unknown")

        # Invalidate cache
        try:
            enrich_member(member.customer_id, force=True, tenant_id=tenant_id)
        except Exception:
            pass

        return f"Buchung erfolgreich für {member.display_name}. Buchung-ID: {booking_id}"
    except Exception as e:
        logger.error("magicline.class_book.failed", error=str(e), slot_id=slot_id)
        return f"Fehler bei der Buchung: {e}"


def book_appointment_by_time(
    user_identifier: str,
    time_str: str,
    date_str: str | None = None,
    category: str = "all",
    tenant_id: int | None = None,
) -> str:
    """Book an appointment slot by local time (HH:MM) for the resolved member."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    member, err = _resolve_member_context(user_identifier, tenant_id=tenant_id)
    if not member:
        return err or "Mitglied konnte nicht aufgelöst werden."

    target_date = _safe_date(date_str) if date_str else date.today()
    if not target_date:
        return "Ungültiges Datum. Bitte YYYY-MM-DD verwenden."

    try:
        if not isinstance(time_str, str) or len(time_str.strip()) < 4:
            return "Ungültige Uhrzeit. Bitte z. B. 16:30 angeben."
        normalized_time = time_str.strip()
        if len(normalized_time) == 4 and normalized_time[1] == ":":
            normalized_time = f"0{normalized_time}"

        # Number of days to scan from target_date (inclusive).
        days_total = max(1, min((target_date - date.today()).days + 1, 14))

        bookables_payload = client.appointment_list_bookable(slice_size=100)
        bookables = _extract_items(bookables_payload)
        if not bookables:
            return "Keine buchbaren Terminarten im CRM gefunden."

        candidates: list[tuple[str, int, dict]] = []
        for b in bookables:
            b_name = str(b.get("name") or b.get("title") or "Termin")
            b_id = b.get("id") or b.get("bookableAppointmentId")
            if b_id is None:
                continue
            if category != "all" and category.lower() not in b_name.lower():
                continue

            slots = client.appointment_get_slots_range(
                int(b_id),
                customer_id=member.customer_id,
                days_total=days_total,
                start_date=target_date.isoformat(),
            )
            for slot in slots:
                start_dt = _safe_datetime(slot.get("startDateTime"))
                if not start_dt or start_dt.date() != target_date:
                    continue
                if start_dt.strftime("%H:%M") != normalized_time:
                    continue
                free = slot.get("availableSlots", slot.get("freeCapacity"))
                if free is not None:
                    try:
                        if int(free) <= 0:
                            continue
                    except (TypeError, ValueError):
                        pass
                candidates.append((b_name, int(b_id), slot))

        if not candidates:
            return (
                f"Kein freier Termin um {normalized_time} am {target_date.isoformat()} gefunden. "
                "Frag gern nach den aktuell freien Uhrzeiten."
            )

        if len(candidates) > 1:
            names = ", ".join(sorted({c[0] for c in candidates})[:4])
            return (
                f"Ich habe um {normalized_time} mehrere Terminarten gefunden ({names}). "
                "Bitte kurz angeben, welche Terminart ich buchen soll."
            )

        title, bookable_id, slot = candidates[0]
        start_dt = slot.get("startDateTime")
        end_dt = slot.get("endDateTime")
        if not start_dt or not end_dt:
            return "Ungültiger Termin-Slot aus CRM erhalten."

        client.appointment_validate(
            bookable_id=bookable_id,
            customer_id=member.customer_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        result = client.appointment_book(
            bookable_id=bookable_id,
            customer_id=member.customer_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        booking = _first_item(result) or (result if isinstance(result, dict) else {})
        booking_id = booking.get("id", "unknown")

        # Invalidate cache
        try:
            enrich_member(member.customer_id, force=True, tenant_id=tenant_id)
        except Exception:
            pass

        return (
            f"Termin gebucht: {title} am {target_date.isoformat()} um {normalized_time}. "
            f"Buchung-ID: {booking_id}"
        )
    except Exception as e:
        err_text = str(e)
        err_lower = err_text.lower()
        if (
            "appointment.overlapping.in.given.period" in err_lower
            or "already booked an appointment in the given period" in err_lower
        ):
            try:
                todays = _member_bookings_for_date(client, member.customer_id, target_date.isoformat())
                overlaps: list[str] = []
                for b in todays:
                    start = _safe_datetime(b.get("start"))
                    if start and start.strftime("%H:%M") == normalized_time:
                        overlaps.append(f"{normalized_time} ({b.get('title', 'Termin')})")
                if overlaps:
                    return (
                        f"Du hast um {normalized_time} bereits einen Termin ({', '.join(overlaps)}). "
                        "Soll ich ihn stattdessen verschieben oder löschen?"
                    )
            except Exception:
                pass
            return (
                f"Du hast in diesem Zeitraum bereits einen Termin (um {normalized_time}). "
                "Soll ich ihn verschieben oder löschen?"
            )

        logger.error(
            "magicline.book_appointment_by_time.failed",
            error=str(e),
            user_identifier=user_identifier,
            time=time_str,
            date=target_date.isoformat(),
        )
        return f"Fehler bei der Terminbuchung: {e}"


def get_checkin_stats(days: int = 90, user_identifier: str | None = None, tenant_id: int | None = None) -> str:
    """Get check-in statistics for retention flows."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."

    member, err = _resolve_member_context(user_identifier or "", tenant_id=tenant_id)
    if not member:
        return err or "Mitglied konnte nicht aufgelöst werden."

    try:
        today = date.today()
        from_date = (today - timedelta(days=max(1, int(days)))).isoformat()
        checkins = client.customer_checkins(member.customer_id, from_date=from_date)
        entries = _extract_items(checkins)

        total_visits = len(entries)
        weeks = max(days / 7.0, 1.0)
        avg_visits = round(total_visits / weeks, 1)

        if entries:
            entries.sort(key=lambda x: x.get("checkInDateTime") or "", reverse=True)
            last_raw = entries[0].get("checkInDateTime")
            last_dt = _safe_datetime(last_raw)
            last_label = last_dt.strftime("%Y-%m-%d") if last_dt else str(last_raw)[:10]
            days_since = (today - (last_dt.date() if last_dt else today)).days
        else:
            last_label = "Nie"
            days_since = 999

        activity = "INAKTIV ⚠️" if days_since > 30 else "AKTIV ✅"
        return (
            f"Statistik für {member.display_name} (letzte {days} Tage):\n"
            f"- Besuche gesamt: {total_visits}\n"
            f"- Ø Besuche/Woche: {avg_visits}\n"
            f"- Letzter Besuch: {last_label} (vor {days_since} Tagen)\n"
            f"- Status: {activity}"
        )
    except Exception as e:
        logger.error("magicline.get_checkin_stats.failed", error=str(e))
        return f"Fehler beim Abrufen der Statistik: {e}"
