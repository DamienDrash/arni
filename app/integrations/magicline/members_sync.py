"""Magicline member sync for admin/member lookup use cases."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal, engine
from app.core.models import StudioMember
from app.integrations.magicline import get_client
from app.integrations.magicline.client import MagiclineClient

logger = structlog.get_logger()

# Fields included in upsert diffing
_SYNC_FIELDS = (
    "member_number", "first_name", "last_name", "date_of_birth",
    "phone_number", "email",
    "gender", "preferred_language", "member_since", "is_paused", "pause_info", "contract_info", "additional_info",
)

# Fallback mapping observed in production data when field-def endpoint is not permitted.
# 1229489651 values are mostly training goals, 1229489650 contains notes/health/context.
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


def _pick_phone(payload: dict[str, Any]) -> str | None:
    for key in ("phonePrivateMobile", "phonePrivate", "phoneBusinessMobile", "phoneBusiness"):
        v = payload.get(key)
        if v:
            return str(v).strip()
    return None


def _is_paused(raw: dict[str, Any]) -> bool:
    """Return True if the member has an active idle/pause period today."""
    today = date.today().isoformat()
    for period in raw.get("idlePeriods") or []:
        start = str(period.get("startDate") or "")
        end = period.get("endDate")
        unlimited = period.get("unlimited", False)
        if start and start <= today and (unlimited or (end and today <= end)):
            return True
    return False


def _safe_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _overlap_days(start: date, end: date, window_start: date, window_end: date) -> int:
    a = max(start, window_start)
    b = min(end, window_end)
    if b < a:
        return 0
    return (b - a).days + 1


def _build_pause_info(raw: dict[str, Any]) -> str | None:
    periods = raw.get("idlePeriods") or []
    if not periods:
        return None

    today = date.today()
    window_start = today - timedelta(days=180)
    paused_days_180 = 0
    is_currently_paused = False
    pause_until: str | None = None
    pause_reason: str | None = None
    last_pause_end: date | None = None
    last_pause_reason: str | None = None

    for p in periods:
        if not isinstance(p, dict):
            continue
        start = _safe_iso_date(p.get("startDate"))
        if not start:
            continue
        unlimited = bool(p.get("unlimited", False))
        end = _safe_iso_date(p.get("endDate")) or (today if unlimited else None)
        reason = (
            str(
                p.get("reason")
                or p.get("description")
                or p.get("comment")
                or p.get("note")
                or p.get("title")
                or ""
            ).strip()
            or None
        )

        if end:
            paused_days_180 += _overlap_days(start, end, window_start, today)
            if end <= today and (last_pause_end is None or end > last_pause_end):
                last_pause_end = end
                last_pause_reason = reason

        if start <= today and (unlimited or (end and today <= end)):
            is_currently_paused = True
            if unlimited:
                pause_until = None
            elif end:
                if pause_until is None or end.isoformat() > pause_until:
                    pause_until = end.isoformat()
            if reason:
                pause_reason = reason

    payload = {
        "is_currently_paused": is_currently_paused,
        "pause_until": pause_until,
        "pause_reason": pause_reason,
        "paused_days_180": max(0, paused_days_180),
        "last_pause_end": last_pause_end.isoformat() if last_pause_end else None,
        "last_pause_reason": last_pause_reason,
    }
    return json.dumps(payload, ensure_ascii=False)


def _resolve_additional_info(
    raw: dict[str, Any],
    field_defs: dict[int, str],
) -> str | None:
    """Map additionalInformationFieldAssignments to {field_name: value} JSON."""
    assignments = raw.get("additionalInformationFieldAssignments") or []
    if not assignments:
        return None
    result: dict[str, Any] = {}
    for a in assignments:
        fid = a.get("additionalInformationFieldId")
        val = a.get("value")
        if fid is not None and val is not None:
            fid_int = int(fid)
            name = field_defs.get(fid_int) or _FALLBACK_FIELD_NAMES.get(fid_int) or f"field_{fid_int}"
            result[name] = val
    return json.dumps(result, ensure_ascii=False) if result else None


def _build_contract_info(client: MagiclineClient, customer_id: int) -> str | None:
    """Fetch active contracts for a member and return summarized JSON."""
    try:
        contracts = client.customer_contracts(customer_id, status="ACTIVE")
        if not contracts:
            return None
        
        # We take the most relevant active contract
        c = contracts[0]
        payload = {
            "plan_name": c.get("rateName") or c.get("name") or "Unbekannt",
            "status": "ACTIVE",
            "start_date": c.get("startDate"),
            "end_date": c.get("endDate"),
            "is_canceled": bool(c.get("cancellationDate")),
            "cancellation_date": c.get("cancellationDate"),
        }
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return None


def _normalize_member(
    raw: dict[str, Any],
    field_defs: dict[int, str],
    client: MagiclineClient | None = None,
) -> dict[str, Any] | None:
    customer_id = raw.get("id")
    if customer_id is None:
        return None
    try:
        customer_id = int(customer_id)
    except (TypeError, ValueError):
        return None

    first_name = str(raw.get("firstName") or "").strip()
    last_name = str(raw.get("lastName") or "").strip()
    if not first_name and not last_name:
        return None

    lang_obj = raw.get("preferredLanguage") or {}
    preferred_language = (
        str(lang_obj.get("languageCode") or "").strip().lower() or None
        if isinstance(lang_obj, dict) else None
    )

    return {
        "customer_id": customer_id,
        "member_number": str(raw.get("customerNumber") or "").strip() or None,
        "first_name": first_name or "-",
        "last_name": last_name or "-",
        "date_of_birth": _safe_date(raw.get("dateOfBirth")),
        "phone_number": _pick_phone(raw),
        "email": (str(raw.get("email") or "").strip() or None),
        "gender": (str(raw.get("gender") or "").strip() or None),
        "preferred_language": preferred_language,
        "member_since": _safe_datetime(raw.get("createdDateTime")),
        "is_paused": _is_paused(raw),
        "pause_info": _build_pause_info(raw),
        "contract_info": _build_contract_info(client, customer_id) if client else None,
        "additional_info": _resolve_additional_info(raw, field_defs),
    }


def _align_studio_members_sequence(db) -> None:
    """Realign Postgres sequence after imports/restores."""
    if engine.dialect.name != "postgresql":
        return
    db.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence('studio_members', 'id'),
                COALESCE((SELECT MAX(id) FROM studio_members), 1),
                true
            )
            """
        )
    ).fetchone()  # consume cursor so setval is sent to the server before any INSERT


def _is_studio_members_pk_sequence_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "studio_members_pkey" in msg and "duplicate key value violates unique constraint" in msg


def sync_members_from_magicline(tenant_id: int | None = None) -> dict[str, int]:
    """Sync MEMBER status customers from Magicline into local studio_members table."""
    client = get_client(tenant_id=tenant_id)
    if not client:
        logger.warning("magicline.members_sync.client_unavailable")
        return {"fetched": 0, "upserted": 0, "deleted": 0}

    # Fetch additional-info field definitions once (best-effort; continue if unavailable)
    field_defs: dict[int, str] = {}
    try:
        defs = client.customer_additional_info_fields()
        for d in defs:
            fid = d.get("id")
            name = str(d.get("name") or d.get("abbreviation") or "").strip()
            if fid is not None and name:
                field_defs[int(fid)] = name
        logger.info("magicline.members_sync.field_defs_loaded", count=len(field_defs))
    except Exception as e:
        logger.warning("magicline.members_sync.field_defs_failed", error=str(e))

    try:
        rows = MagiclineClient.iter_pages(
            client.customer_list,
            customer_status="MEMBER",
            slice_size=200,
        )
    except Exception as e:
        msg = str(e)
        if "403" in msg or "permission" in msg.lower():
            logger.error("magicline.members_sync.permission_denied", error=msg)
            raise ValueError("Magicline API-Zugriff verweigert (403). Bitte sicherstellen, dass der API-Key die Berechtigung 'CUSTOMER_READ' besitzt.")
        if "401" in msg:
            logger.error("magicline.members_sync.auth_failed", error=msg)
            raise ValueError("Magicline Authentifizierung fehlgeschlagen (401). API-Key ungültig.")
        raise

    normalized = [m for m in (_normalize_member(row, field_defs, client=client) for row in rows) if m]
    incoming_ids = {m["customer_id"] for m in normalized}

    upserted = 0
    deleted = 0

    for attempt in range(2):
        db = SessionLocal()
        try:
            if tenant_id is None:
                tenant_row = db.execute(text("SELECT id FROM tenants WHERE slug = 'system' LIMIT 1")).first()
                tenant_id = int(tenant_row[0]) if tenant_row else None

            # Pre-emptive sequence realignment for Postgres restore/import scenarios.
            _align_studio_members_sequence(db)

            base_q = db.query(StudioMember)
            if tenant_id is not None:
                base_q = base_q.filter(StudioMember.tenant_id == tenant_id)

            existing = {row.customer_id: row for row in base_q.all()}
            upserted = 0
            deleted = 0

            for item in normalized:
                current = existing.get(item["customer_id"])
                if current is None:
                    db.add(StudioMember(tenant_id=tenant_id, **item))
                    upserted += 1
                    continue

                changed = False
                for field in _SYNC_FIELDS:
                    if getattr(current, field) != item[field]:
                        setattr(current, field, item[field])
                        changed = True
                if changed:
                    upserted += 1

            for row in existing.values():
                if row.customer_id not in incoming_ids:
                    db.delete(row)
                    deleted += 1

            db.commit()
            logger.info(
                "magicline.members_sync.completed",
                fetched=len(rows),
                normalized=len(normalized),
                upserted=upserted,
                deleted=deleted,
            )
            return {"fetched": len(rows), "upserted": upserted, "deleted": deleted}
        except IntegrityError as e:
            db.rollback()
            if attempt == 0 and _is_studio_members_pk_sequence_error(e):
                logger.warning("magicline.members_sync.sequence_realign_retry", error=str(e))
                try:
                    _align_studio_members_sequence(db)
                    db.commit()
                except Exception:
                    db.rollback()
                continue
            logger.error("magicline.members_sync.failed", error=str(e))
            raise
        except Exception as e:
            db.rollback()
            logger.error("magicline.members_sync.failed", error=str(e))
            raise
        finally:
            db.close()

    raise RuntimeError("magicline.members_sync.failed_unexpected_retry_exit")
