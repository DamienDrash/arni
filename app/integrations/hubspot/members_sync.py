"""HubSpot contact → StudioMember sync.

Fetches all contacts from HubSpot CRM and upserts them into the local database.
Matching is done by source='hubspot' + source_id=hubspot_contact_id.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from app.core.db import SessionLocal
from app.core.models import MemberImportLog, StudioMember
from app.gateway.persistence import get_setting

from .client import HubSpotClient

logger = structlog.get_logger()


def _get_hubspot_client(tenant_id: int) -> HubSpotClient:
    """Build a HubSpotClient from tenant settings."""
    access_token = get_setting("hubspot_access_token", tenant_id=tenant_id)
    if not access_token:
        raise ValueError(
            "HubSpot ist nicht konfiguriert. Bitte Access Token "
            "unter Settings → Integrations eintragen."
        )
    return HubSpotClient(access_token=access_token)


def _normalize_contact(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a HubSpot contact to StudioMember fields."""
    props = raw.get("properties") or {}

    first_name = (props.get("firstname") or "").strip() or "-"
    last_name = (props.get("lastname") or "").strip() or "-"
    email = (props.get("email") or "").strip() or None
    phone = (props.get("phone") or props.get("mobilephone") or "").strip() or None

    # Gender
    gender_raw = (props.get("gender") or "").strip().upper()
    gender = None
    if gender_raw in ("MALE", "FEMALE", "DIVERSE", "M", "F", "D"):
        gender = {"M": "MALE", "F": "FEMALE", "D": "DIVERSE"}.get(gender_raw, gender_raw)

    # Language
    lang = (props.get("hs_language") or "").strip().lower()
    preferred_language = lang[:2] if lang else None

    # Member since
    created_str = props.get("createdate")
    member_since = None
    if created_str:
        try:
            member_since = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    # Additional info
    additional: dict[str, Any] = {}
    for key in ("company", "jobtitle", "lifecyclestage", "hs_lead_status"):
        val = (props.get(key) or "").strip()
        if val:
            additional[key] = val
    for key in ("city", "state", "country", "zip"):
        val = (props.get(key) or "").strip()
        if val:
            additional.setdefault("address", {})[key] = val

    # Date of birth
    dob_str = (props.get("date_of_birth") or "").strip()
    date_of_birth = None
    if dob_str:
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                date_of_birth = datetime.strptime(dob_str, fmt).date()
                break
            except ValueError:
                continue

    return {
        "source_id": str(raw["id"]),
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone_number": phone,
        "gender": gender,
        "preferred_language": preferred_language,
        "member_since": member_since,
        "date_of_birth": date_of_birth,
        "additional_info": additional,
    }


def sync_members_from_hubspot(tenant_id: int) -> dict[str, int]:
    """Full sync: fetch all HubSpot contacts and upsert into StudioMember."""
    client = _get_hubspot_client(tenant_id)
    logger.info("hubspot.sync.start", tenant_id=tenant_id)

    raw_contacts = client.list_all_contacts()
    logger.info("hubspot.sync.fetched", tenant_id=tenant_id, count=len(raw_contacts))

    db = SessionLocal()
    import_log = MemberImportLog(
        tenant_id=tenant_id,
        source="hubspot",
        status="running",
        total_rows=len(raw_contacts),
    )
    db.add(import_log)
    db.commit()

    existing_map: dict[str, StudioMember] = {}
    existing_rows = (
        db.query(StudioMember)
        .filter(StudioMember.tenant_id == tenant_id, StudioMember.source == "hubspot")
        .all()
    )
    for row in existing_rows:
        if row.source_id:
            existing_map[row.source_id] = row

    from sqlalchemy import func
    max_cid = (
        db.query(func.max(StudioMember.customer_id))
        .filter(StudioMember.tenant_id == tenant_id)
        .scalar()
    ) or 0
    next_cid = max_cid + 1

    created = 0
    updated = 0
    errors = 0
    error_details: list[dict] = []

    try:
        for raw in raw_contacts:
            try:
                normalized = _normalize_contact(raw)
                source_id = normalized["source_id"]
                existing = existing_map.get(source_id)
                additional_json = json.dumps(normalized["additional_info"], ensure_ascii=False) if normalized["additional_info"] else None

                if existing:
                    existing.first_name = normalized["first_name"]
                    existing.last_name = normalized["last_name"]
                    existing.email = normalized["email"]
                    existing.phone_number = normalized["phone_number"]
                    existing.gender = normalized["gender"]
                    existing.preferred_language = normalized["preferred_language"]
                    existing.additional_info = additional_json
                    if normalized["date_of_birth"]:
                        existing.date_of_birth = normalized["date_of_birth"]
                    if normalized["member_since"]:
                        existing.member_since = normalized["member_since"]
                    updated += 1
                else:
                    member = StudioMember(
                        tenant_id=tenant_id,
                        customer_id=next_cid,
                        source="hubspot",
                        source_id=source_id,
                        first_name=normalized["first_name"],
                        last_name=normalized["last_name"],
                        email=normalized["email"],
                        phone_number=normalized["phone_number"],
                        gender=normalized["gender"],
                        preferred_language=normalized["preferred_language"],
                        member_since=normalized["member_since"],
                        date_of_birth=normalized["date_of_birth"],
                        additional_info=additional_json,
                    )
                    db.add(member)
                    next_cid += 1
                    created += 1
            except Exception as e:
                errors += 1
                error_details.append({"hubspot_id": raw.get("id"), "error": str(e)})

        db.commit()
        import_log.status = "completed"
        import_log.imported = created
        import_log.updated = updated
        import_log.errors = errors
        import_log.error_log = json.dumps(error_details, ensure_ascii=False) if error_details else None
        import_log.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("hubspot.sync.completed", tenant_id=tenant_id, created=created, updated=updated, errors=errors)
        return {"total": len(raw_contacts), "created": created, "updated": updated, "skipped": 0, "errors": errors}
    except Exception as e:
        db.rollback()
        import_log.status = "failed"
        import_log.error_log = json.dumps([{"error": str(e)}])
        import_log.completed_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


def test_hubspot_connection(tenant_id: int) -> dict[str, Any]:
    """Test the HubSpot connection for a tenant."""
    try:
        client = _get_hubspot_client(tenant_id)
        return client.test_connection()
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
