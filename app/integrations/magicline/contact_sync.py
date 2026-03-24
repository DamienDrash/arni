"""Magicline → Contact sync (v2).

@ARCH: Contacts Refactoring – Integration Sync
Replaces the legacy members_sync.py by writing directly into the
new `contacts` table via the ContactSyncService.

Reuses the existing Magicline client and normalization helpers
from members_sync.py, but outputs NormalizedContact objects
instead of StudioMember rows.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog

from app.contacts.sync_service import NormalizedContact, SyncResult, contact_sync_service
from app.integrations.magicline import get_client
from app.integrations.magicline.client import MagiclineClient

logger = structlog.get_logger()

# ─── Helper functions (reused from members_sync.py) ─────────────────────────

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


def _resolve_additional_info(
    raw: dict[str, Any],
    field_defs: dict[int, str],
) -> dict[str, Any]:
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


def _build_contract_info(
    client: MagiclineClient,
    customer_id: int,
    customer_status: str | None = None,
) -> dict[str, Any] | None:
    """Fetch the most relevant contract snapshot for a customer."""
    candidate_statuses: list[str] = ["ACTIVE"]
    if customer_status == "FORMER_MEMBER":
        candidate_statuses.append("INACTIVE")

    for requested_status in candidate_statuses:
        try:
            contracts = client.customer_contracts(customer_id, status=requested_status)
        except Exception:
            continue
        if not contracts:
            continue
        c = contracts[0]
        return {
            "plan_name": c.get("rateName") or c.get("name") or "Unbekannt",
            "status": c.get("status") or requested_status,
            "start_date": c.get("startDate"),
            "end_date": c.get("endDate"),
            "is_canceled": bool(c.get("cancellationDate")),
        }

    return None


def _determine_lifecycle(raw: dict[str, Any], contract_info: dict | None) -> str:
    """Determine lifecycle stage from Magicline data."""
    status = raw.get("customerStatus") or raw.get("status")
    if status == "MEMBER":
        return "customer"
    if status == "PROSPECT":
        return "lead"
    if status == "FORMER_MEMBER":
        return "churned"
    if contract_info and contract_info.get("status") == "ACTIVE":
        return "customer"
    return "subscriber"


def _fetch_customers_for_status(
    client: MagiclineClient,
    customer_status: str,
) -> list[dict[str, Any]]:
    return MagiclineClient.iter_pages(
        client.customer_list,
        customer_status=customer_status,
        slice_size=200,
    )


# ─── Main Sync Function ─────────────────────────────────────────────────────


def sync_contacts_from_magicline(tenant_id: int) -> dict[str, Any]:
    """Sync customers from Magicline into the contacts table.

    This is the v2 replacement for sync_members_from_magicline().
    It uses the ContactSyncService for clean upsert into the new data model.

    Returns:
        Dict with sync statistics (fetched, created, updated, etc.)
    """
    client = get_client(tenant_id=tenant_id)
    if not client:
        logger.warning("magicline.contact_sync.client_unavailable")
        return {"fetched": 0, "created": 0, "updated": 0, "errors": 0}

    # Load additional-info field definitions (best-effort)
    field_defs: dict[int, str] = {}
    try:
        defs = client.customer_additional_info_fields()
        for d in defs:
            fid = d.get("id")
            name = str(d.get("name") or d.get("abbreviation") or "").strip()
            if fid is not None and name:
                field_defs[int(fid)] = name
        logger.info("magicline.contact_sync.field_defs_loaded", count=len(field_defs))
    except Exception as e:
        logger.warning("magicline.contact_sync.field_defs_failed", error=str(e))

    # Fetch all supported customer statuses from Magicline
    try:
        rows_by_id: dict[int, dict[str, Any]] = {}
        fetched_counts: dict[str, int] = {}
        for customer_status in ("MEMBER", "PROSPECT", "FORMER_MEMBER"):
            status_rows = _fetch_customers_for_status(client, customer_status)
            fetched_counts[customer_status] = len(status_rows)
            for row in status_rows:
                customer_id = row.get("id")
                try:
                    customer_id_int = int(customer_id)
                except (TypeError, ValueError):
                    continue
                normalized_row = dict(row)
                normalized_row["status"] = normalized_row.get("status") or customer_status
                rows_by_id[customer_id_int] = normalized_row
        rows = list(rows_by_id.values())
    except Exception as e:
        msg = str(e)
        if "403" in msg or "permission" in msg.lower():
            logger.error("magicline.contact_sync.permission_denied", error=msg)
            raise ValueError(
                "Magicline API-Zugriff verweigert (403). "
                "Bitte sicherstellen, dass der API-Key die Berechtigung 'CUSTOMER_READ' besitzt."
            )
        if "401" in msg:
            logger.error("magicline.contact_sync.auth_failed", error=msg)
            raise ValueError("Magicline Authentifizierung fehlgeschlagen (401). API-Key ungültig.")
        raise

    # Convert Magicline records to NormalizedContact objects
    normalized_contacts: List[NormalizedContact] = []

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

        lang_obj = raw.get("preferredLanguage") or {}
        preferred_language = (
            str(lang_obj.get("languageCode") or "").strip().lower() or "de"
            if isinstance(lang_obj, dict) else "de"
        )

        # Build structured metadata
        magicline_status = str(raw.get("status") or raw.get("customerStatus") or "").strip().upper() or None
        contract_info = _build_contract_info(client, customer_id, magicline_status)
        pause_info = _build_pause_info(raw)
        additional_info = _resolve_additional_info(raw, field_defs)
        member_number = str(raw.get("customerNumber") or "").strip() or None

        # Build custom fields from Magicline-specific data
        custom_fields: Dict[str, Any] = {}
        if magicline_status:
            custom_fields["magicline_status"] = magicline_status
        if contract_info:
            custom_fields["vertrag"] = contract_info.get("plan_name", "")
            custom_fields["vertrag_status"] = contract_info.get("status", "")
            custom_fields["vertrag_gekuendigt"] = contract_info.get("is_canceled", False)
            if contract_info.get("start_date"):
                custom_fields["vertrag_start"] = contract_info["start_date"]
            if contract_info.get("end_date"):
                custom_fields["vertrag_ende"] = contract_info["end_date"]
        if pause_info:
            custom_fields["pausiert"] = pause_info.get("is_currently_paused", False)
            if pause_info.get("pause_until"):
                custom_fields["pause_bis"] = pause_info["pause_until"]
            if pause_info.get("pause_reason"):
                custom_fields["pause_grund"] = pause_info["pause_reason"]
        if additional_info:
            custom_fields.update(additional_info)

        # Build external IDs
        external_ids: Dict[str, str] = {"magicline": str(customer_id)}
        if member_number:
            external_ids["member_number"] = member_number

        # Build tags from Magicline data
        tags: List[str] = ["magicline"]
        lifecycle = _determine_lifecycle(raw, contract_info)
        if magicline_status:
            tags.append(f"magicline:{magicline_status.lower()}")
        if pause_info and pause_info.get("is_currently_paused"):
            tags.append("pausiert")
        if contract_info and contract_info.get("is_canceled"):
            tags.append("gekündigt")

        nc = NormalizedContact(
            source_id=str(customer_id),
            first_name=first_name or "-",
            last_name=last_name or "-",
            email=str(raw.get("email") or "").strip() or None,
            phone=_pick_phone(raw),
            date_of_birth=_safe_date(raw.get("dateOfBirth")),
            gender=str(raw.get("gender") or "").strip() or None,
            preferred_language=preferred_language,
            lifecycle_stage=lifecycle,
            tags=tags,
            custom_fields=custom_fields,
            external_ids=external_ids,
        )
        normalized_contacts.append(nc)

    logger.info(
        "magicline.contact_sync.normalized",
        tenant_id=tenant_id,
        fetched=len(rows),
        fetched_by_status=fetched_counts,
        normalized=len(normalized_contacts),
    )

    # Sync into contacts table
    sync_result = contact_sync_service.sync_contacts(
        tenant_id=tenant_id,
        source="magicline",
        contacts=normalized_contacts,
        full_sync=True,
        delete_missing=True,
        performed_by_name="Magicline Sync",
    )

    return {
        "fetched": len(rows),
        **sync_result.to_dict(),
    }
