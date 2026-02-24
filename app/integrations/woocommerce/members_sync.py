"""WooCommerce customer → StudioMember sync.

Fetches all customers from WooCommerce and upserts them into the local database.
Matching is done by source='woocommerce' + source_id=wc_customer_id.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from app.core.db import SessionLocal
from app.core.models import MemberImportLog, StudioMember
from app.gateway.persistence import get_setting

from .client import WooCommerceClient

logger = structlog.get_logger()


def _get_wc_client(tenant_id: int) -> WooCommerceClient:
    """Build a WooCommerceClient from tenant settings."""
    store_url = get_setting("woocommerce_store_url", tenant_id=tenant_id)
    consumer_key = get_setting("woocommerce_consumer_key", tenant_id=tenant_id)
    consumer_secret = get_setting("woocommerce_consumer_secret", tenant_id=tenant_id)
    if not store_url or not consumer_key or not consumer_secret:
        raise ValueError(
            "WooCommerce ist nicht konfiguriert. Bitte Store-URL, Consumer Key und "
            "Consumer Secret unter Settings → Integrations eintragen."
        )
    return WooCommerceClient(store_url=store_url, consumer_key=consumer_key, consumer_secret=consumer_secret)


def _normalize_customer(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a WooCommerce customer to StudioMember fields."""
    first_name = (raw.get("first_name") or "").strip() or "-"
    last_name = (raw.get("last_name") or "").strip() or "-"
    email = (raw.get("email") or "").strip() or None

    # Phone from billing address
    billing = raw.get("billing") or {}
    phone = (billing.get("phone") or "").strip() or None

    # Member since
    created_str = raw.get("date_created")
    member_since = None
    if created_str:
        try:
            member_since = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    # Additional info
    additional: dict[str, Any] = {}
    if raw.get("is_paying_customer"):
        additional["is_paying_customer"] = True
    if raw.get("avatar_url"):
        additional["avatar_url"] = raw["avatar_url"]

    # Address info
    for addr_type in ("billing", "shipping"):
        addr = raw.get(addr_type) or {}
        if addr.get("city") or addr.get("country"):
            additional[f"{addr_type}_address"] = {
                k: v for k, v in addr.items()
                if k in ("city", "state", "postcode", "country", "company") and v
            }

    return {
        "source_id": str(raw["id"]),
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone_number": phone,
        "member_since": member_since,
        "additional_info": additional,
    }


def sync_members_from_woocommerce(tenant_id: int) -> dict[str, int]:
    """Full sync: fetch all WooCommerce customers and upsert into StudioMember."""
    client = _get_wc_client(tenant_id)
    logger.info("woocommerce.sync.start", tenant_id=tenant_id)

    raw_customers = client.list_all_customers()
    logger.info("woocommerce.sync.fetched", tenant_id=tenant_id, count=len(raw_customers))

    db = SessionLocal()
    import_log = MemberImportLog(
        tenant_id=tenant_id,
        source="woocommerce",
        status="running",
        total_rows=len(raw_customers),
    )
    db.add(import_log)
    db.commit()

    existing_map: dict[str, StudioMember] = {}
    existing_rows = (
        db.query(StudioMember)
        .filter(StudioMember.tenant_id == tenant_id, StudioMember.source == "woocommerce")
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
        for raw in raw_customers:
            try:
                normalized = _normalize_customer(raw)
                source_id = normalized["source_id"]
                existing = existing_map.get(source_id)
                additional_json = json.dumps(normalized["additional_info"], ensure_ascii=False) if normalized["additional_info"] else None

                if existing:
                    existing.first_name = normalized["first_name"]
                    existing.last_name = normalized["last_name"]
                    existing.email = normalized["email"]
                    existing.phone_number = normalized["phone_number"]
                    existing.additional_info = additional_json
                    if normalized["member_since"]:
                        existing.member_since = normalized["member_since"]
                    updated += 1
                else:
                    member = StudioMember(
                        tenant_id=tenant_id,
                        customer_id=next_cid,
                        source="woocommerce",
                        source_id=source_id,
                        first_name=normalized["first_name"],
                        last_name=normalized["last_name"],
                        email=normalized["email"],
                        phone_number=normalized["phone_number"],
                        member_since=normalized["member_since"],
                        additional_info=additional_json,
                    )
                    db.add(member)
                    next_cid += 1
                    created += 1
            except Exception as e:
                errors += 1
                error_details.append({"wc_id": raw.get("id"), "error": str(e)})

        db.commit()
        import_log.status = "completed"
        import_log.imported = created
        import_log.updated = updated
        import_log.errors = errors
        import_log.error_log = json.dumps(error_details, ensure_ascii=False) if error_details else None
        import_log.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("woocommerce.sync.completed", tenant_id=tenant_id, created=created, updated=updated, errors=errors)
        return {"total": len(raw_customers), "created": created, "updated": updated, "skipped": 0, "errors": errors}
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


def test_woocommerce_connection(tenant_id: int) -> dict[str, Any]:
    """Test the WooCommerce connection for a tenant."""
    try:
        client = _get_wc_client(tenant_id)
        return client.test_connection()
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
