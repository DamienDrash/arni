"""Lazy per-member enrichment: check-in stats + recent bookings.

Fetches data from Magicline for a single member and caches it in the local DB.
TTL: 6 hours (configurable via ENRICHMENT_TTL_HOURS).

recent_bookings is stored as a dict:
  {
    "upcoming": [next 8 PLANNED sorted by date asc],
    "past":     [last 10 COMPLETED sorted by date desc],
  }
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog

from app.core.db import SessionLocal
from app.core.models import StudioMember
from app.integrations.magicline import get_client

logger = structlog.get_logger()

ENRICHMENT_TTL_HOURS = 6
CHECKIN_SLICE_SIZE = 50  # API max is ~50


def _extract_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, list):
            return [x for x in result if isinstance(x, dict)]
    return []


def _safe_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _compute_checkin_stats(checkins_90: list[dict], checkins_30: list[dict]) -> dict:
    today = date.today()
    total_90 = len(checkins_90)
    total_30 = len(checkins_30)
    avg_per_week = round(total_90 / 12.857, 1)  # 90 days / 7

    last_visit: str | None = None
    days_since = 999
    if checkins_90:
        sorted_ci = sorted(
            checkins_90,
            key=lambda c: c.get("checkInDateTime") or "",
            reverse=True,
        )
        raw_dt = sorted_ci[0].get("checkInDateTime")
        dt = _safe_dt(raw_dt)
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
    """Compute visit-frequency stats from completed appointment/class bookings.

    Used as fallback when the studio doesn't use the Magicline check-in system.
    """
    today = date.today()
    cutoff_30 = (today - timedelta(days=30)).isoformat()
    cutoff_90 = (today - timedelta(days=90)).isoformat()

    completed = [
        b for b in past_bookings
        if b.get("status", "").upper() in ("COMPLETED",)
    ]
    total_90 = len([b for b in completed if (b.get("start") or "") >= cutoff_90])
    total_30 = len([b for b in completed if (b.get("start") or "") >= cutoff_30])

    # Use actual date range of available data for more accurate weekly average
    if completed:
        starts = [str(b.get("start")) for b in completed if b.get("start")]
        oldest_dt = _safe_dt(min(starts)) if starts else None
        actual_days = (today - oldest_dt.date()).days + 1 if oldest_dt else 90
        weeks = max(actual_days / 7, 1)
    else:
        weeks = 12.857  # fallback: 90 days
    avg_per_week = round(len(completed) / weeks, 1)

    last_visit: str | None = None
    days_since = 999
    if completed:
        sorted_b = sorted(completed, key=lambda b: b.get("start") or "", reverse=True)
        dt = _safe_dt(sorted_b[0].get("start"))
        if dt:
            last_visit = dt.date().isoformat()
            days_since = (today - dt.date()).days

    # Most booked category
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
        "source": "bookings",  # distinguishes from check-in based stats
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
        dt = _safe_dt(row.get("start"))
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
    # Return all observed training days (Mon..Sun), not only top-2.
    preferred_weekdays = [
        weekday_map[idx]
        for idx in sorted(weekday_counts.keys())
        if 0 <= idx < len(weekday_map)
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
    last_pause_end = _safe_dt(pause_info.get("last_pause_end"))
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

    return {
        "score": score,
        "risk": risk,
        "reasons": reasons,
    }


def _fetch_recent_bookings(client, customer_id: int) -> dict:
    """Fetch and split bookings into upcoming (PLANNED) and past (COMPLETED/CANCELED).

    Returns::
        {
          "upcoming": [next 8 planned, sorted by date asc],
          "past":     [last 10 completed, sorted by date desc],
        }
    """
    today_str = date.today().isoformat()
    all_bookings: list[dict] = []

    # Appointment bookings
    try:
        apt_payload = client.appointment_list_bookings(customer_id, slice_size=50)
        for item in _extract_items(apt_payload):
            start = item.get("startDateTime")
            title = (
                item.get("title")
                or item.get("bookableAppointmentName")
                or item.get("name")
                or "Termin"
            )
            status = item.get("appointmentStatus") or item.get("bookingStatus") or ""
            all_bookings.append({
                "type": "appointment",
                "title": str(title),
                "start": start,
                "status": str(status).upper(),
            })
    except Exception as e:
        logger.wariiang("member_enrichment.appointments_failed", customer_id=customer_id, error=str(e))

    # Class bookings
    try:
        class_payload = client.class_list_bookings(customer_id, slice_size=50)
        for item in _extract_items(class_payload):
            class_info = item.get("classInformation") or {}
            class_details = item.get("classDetails") or {}
            title = (
                item.get("title")
                or (class_info.get("title") if isinstance(class_info, dict) else None)
                or (class_details.get("name") if isinstance(class_details, dict) else None)
                or item.get("className")
                or "Kurs"
            )
            start = item.get("startDateTime")
            status = item.get("classSlotStatus") or item.get("bookingStatus") or ""
            all_bookings.append({
                "type": "class",
                "title": str(title),
                "start": start,
                "status": str(status).upper(),
            })
    except Exception as e:
        logger.wariiang("member_enrichment.classes_failed", customer_id=customer_id, error=str(e))

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

    return {
        "upcoming": upcoming[:10],
        "past": past[:200],   # store full history for accurate stats
    }


def enrich_member(customer_id: int, force: bool = False, tenant_id: int | None = None) -> dict:
    """Fetch and cache check-in stats + recent bookings for a member.

    Skips enrichment if data is fresh (< ENRICHMENT_TTL_HOURS) unless force=True.
    Returns a dict with the enrichment data or an error/cached indicator.
    """
    db = SessionLocal()
    try:
        q = db.query(StudioMember).filter(StudioMember.customer_id == customer_id)
        if tenant_id is not None:
            q = q.filter(StudioMember.tenant_id == tenant_id)
        member = q.first()
        if not member:
            return {"error": f"Member {customer_id} not found"}

        # Check cache freshness
        if not force and member.enriched_at:
            age = datetime.now(timezone.utc) - member.enriched_at.replace(tzinfo=timezone.utc)
            if age < timedelta(hours=ENRICHMENT_TTL_HOURS):
                logger.debug(
                    "member_enrichment.cache_hit",
                    customer_id=customer_id,
                    age_minutes=int(age.total_seconds() / 60),
                )
                return {
                    "cached": True,
                    "enriched_at": member.enriched_at.isoformat(),
                    "checkin_stats": json.loads(member.checkin_stats) if member.checkin_stats else None,
                    "recent_bookings": json.loads(member.recent_bookings) if member.recent_bookings else None,
                }

        client = get_client(tenant_id=tenant_id)
        if not client:
            return {"error": "Magicline not configured"}

        today = date.today()

        # Read studio setting: is the Magicline check-in system active?
        from app.gateway.persistence import persistence as _persistence
        checkin_enabled = _persistence.get_setting("checkin_enabled", "true", tenant_id=tenant_id) == "true"

        # Fetch check-ins (only when enabled)
        checkins_90: list[dict] = []
        checkins_30: list[dict] = []
        if checkin_enabled:
            try:
                from_date = (today - timedelta(days=90)).isoformat()
                to_date = today.isoformat()
                cutoff_30 = (today - timedelta(days=30)).isoformat()
                offset = 0
                while True:
                    payload = client.customer_checkins(
                        customer_id,
                        from_date=from_date,
                        to_date=to_date,
                        slice_size=CHECKIN_SLICE_SIZE,
                        offset=offset,
                    )
                    page = _extract_items(payload)
                    checkins_90.extend(page)
                    has_next = payload.get("hasNext", False) if isinstance(payload, dict) else False
                    if not has_next or not page:
                        break
                    offset += CHECKIN_SLICE_SIZE
                checkins_30 = [c for c in checkins_90 if (c.get("checkInDateTime") or "") >= cutoff_30]
            except Exception as e:
                logger.wariiang("member_enrichment.checkins_failed", customer_id=customer_id, error=str(e))

        checkin_stats = _compute_checkin_stats(checkins_90, checkins_30)

        # Fetch bookings (past + upcoming split)
        bookings = _fetch_recent_bookings(client, customer_id)

        # Fallback: if check-ins disabled or studio has no check-in data, use booking-based stats.
        if checkin_stats["total_90d"] == 0 and bookings.get("past"):
            checkin_stats = _compute_booking_stats(bookings["past"])
            logger.info(
                "member_enrichment.booking_stats_fallback",
                customer_id=customer_id,
                completed=len(bookings["past"]),
            )

        checkin_stats["checkin_enabled"] = checkin_enabled
        pause_info: dict[str, Any] = {}
        if member.pause_info:
            try:
                pause_info = json.loads(member.pause_info)
            except Exception:
                pause_info = {}
        checkin_stats.update(_derive_training_preferences(bookings))
        checkin_stats["churn_prediction"] = _compute_churn_prediction(
            checkin_stats,
            bookings,
            member.is_paused,
            pause_info,
        )

        # Persist
        member.checkin_stats = json.dumps(checkin_stats, ensure_ascii=False)
        member.recent_bookings = json.dumps(bookings, ensure_ascii=False)
        member.enriched_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "member_enrichment.completed",
            customer_id=customer_id,
            checkins_90=len(checkins_90),
            past_bookings=len(bookings.get("past", [])),
            upcoming_bookings=len(bookings.get("upcoming", [])),
        )
        return {
            "cached": False,
            "enriched_at": member.enriched_at.isoformat(),
            "checkin_stats": checkin_stats,
            "recent_bookings": bookings,
        }

    except Exception as e:
        db.rollback()
        logger.error("member_enrichment.failed", customer_id=customer_id, error=str(e))
        return {"error": str(e)}
    finally:
        db.close()


def get_member_profile(customer_id: int, tenant_id: int | None = None) -> dict | None:
    """Return full member profile from DB including enrichment data (no API call)."""
    import json as _json
    db = SessionLocal()
    try:
        q = db.query(StudioMember).filter(StudioMember.customer_id == customer_id)
        if tenant_id is not None:
            q = q.filter(StudioMember.tenant_id == tenant_id)
        m = q.first()
        if not m:
            return None
        return {
            "customer_id": m.customer_id,
            "name": f"{m.first_name} {m.last_name}".strip(),
            "member_number": m.member_number,
            "gender": m.gender,
            "preferred_language": m.preferred_language,
            "member_since": m.member_since.date().isoformat() if m.member_since else None,
            "is_paused": m.is_paused,
            "pause_info": _json.loads(m.pause_info) if m.pause_info else None,
            "additional_info": _json.loads(m.additional_info) if m.additional_info else {},
            "checkin_stats": _json.loads(m.checkin_stats) if m.checkin_stats else None,
            "recent_bookings": _json.loads(m.recent_bookings) if m.recent_bookings else None,
            "enriched_at": m.enriched_at.isoformat() if m.enriched_at else None,
        }
    finally:
        db.close()
