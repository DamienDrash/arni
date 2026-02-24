"""Shopify customer → StudioMember sync.

Fetches all customers from Shopify and upserts them into the local database.
Matching is done by source='shopify' + source_id=shopify_customer_id.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from app.core.db import SessionLocal
from app.core.models import MemberImportLog, StudioMember
from app.gateway.persistence import get_setting

from .client import ShopifyClient

logger = structlog.get_logger()


def _get_shopify_client(tenant_id: int) -> ShopifyClient:
    """Build a ShopifyClient from tenant settings."""
    shop_domain = get_setting("shopify_shop_domain", tenant_id=tenant_id)
    access_token = get_setting("shopify_access_token", tenant_id=tenant_id)
    if not shop_domain or not access_token:
        raise ValueError(
            "Shopify ist nicht konfiguriert. Bitte Shop-Domain und Access Token "
            "unter Settings → Integrations eintragen."
        )
    return ShopifyClient(shop_domain=shop_domain, access_token=access_token)


def _normalize_customer(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Shopify customer object to StudioMember fields."""
    # Parse name
    first_name = (raw.get("first_name") or "").strip() or "-"
    last_name = (raw.get("last_name") or "").strip() or "-"

    # Phone: Shopify stores with country code
    phone = (raw.get("phone") or "").strip() or None

    # Email
    email = (raw.get("email") or "").strip() or None

    # Tags: Shopify stores as comma-separated string
    tags_str = (raw.get("tags") or "").strip()
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    # Gender: not a standard Shopify field, check metafields/note
    gender = None

    # Member since
    created_at_str = raw.get("created_at")
    member_since = None
    if created_at_str:
        try:
            member_since = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    # Additional info from Shopify-specific fields
    additional: dict[str, Any] = {}
    if raw.get("note"):
        additional["shopify_note"] = raw["note"]
    if raw.get("orders_count"):
        additional["orders_count"] = raw["orders_count"]
    if raw.get("total_spent"):
        additional["total_spent"] = raw["total_spent"]
    if raw.get("currency"):
        additional["currency"] = raw["currency"]
    if raw.get("verified_email") is not None:
        additional["email_verified"] = raw["verified_email"]

    # Address
    default_address = raw.get("default_address") or {}
    if default_address:
        additional["address"] = {
            "city": default_address.get("city"),
            "province": default_address.get("province"),
            "country": default_address.get("country"),
            "zip": default_address.get("zip"),
        }

    # Language
    locale = (raw.get("locale") or "").strip().lower()
    preferred_language = locale[:2] if locale else None

    return {
        "source_id": str(raw["id"]),
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone_number": phone,
        "gender": gender,
        "preferred_language": preferred_language,
        "member_since": member_since,
        "tags": tags,
        "additional_info": additional,
    }


def sync_members_from_shopify(tenant_id: int) -> dict[str, int]:
    """Full sync: fetch all Shopify customers and upsert into StudioMember.

    Returns:
        Dict with counts: total, created, updated, skipped, errors
    """
    client = _get_shopify_client(tenant_id)
    logger.info("shopify.sync.start", tenant_id=tenant_id)

    raw_customers = client.list_all_customers()
    logger.info("shopify.sync.fetched", tenant_id=tenant_id, count=len(raw_customers))

    db = SessionLocal()
    import_log = MemberImportLog(
        tenant_id=tenant_id,
        source="shopify",
        status="running",
        total_rows=len(raw_customers),
    )
    db.add(import_log)
    db.commit()

    # Load existing Shopify members for this tenant
    existing_map: dict[str, StudioMember] = {}
    existing_rows = (
        db.query(StudioMember)
        .filter(StudioMember.tenant_id == tenant_id, StudioMember.source == "shopify")
        .all()
    )
    for row in existing_rows:
        if row.source_id:
            existing_map[row.source_id] = row

    # Get next customer_id
    from sqlalchemy import func
    max_cid = (
        db.query(func.max(StudioMember.customer_id))
        .filter(StudioMember.tenant_id == tenant_id)
        .scalar()
    ) or 0
    next_cid = max_cid + 1

    created = 0
    updated = 0
    skipped = 0
    errors = 0
    error_details: list[dict] = []

    try:
        for raw in raw_customers:
            try:
                normalized = _normalize_customer(raw)
                source_id = normalized["source_id"]
                existing = existing_map.get(source_id)

                tags_json = json.dumps(normalized["tags"], ensure_ascii=False) if normalized["tags"] else None
                additional_json = json.dumps(normalized["additional_info"], ensure_ascii=False) if normalized["additional_info"] else None

                if existing:
                    # Update
                    existing.first_name = normalized["first_name"]
                    existing.last_name = normalized["last_name"]
                    existing.email = normalized["email"]
                    existing.phone_number = normalized["phone_number"]
                    existing.preferred_language = normalized["preferred_language"]
                    existing.tags = tags_json
                    existing.additional_info = additional_json
                    if normalized["member_since"]:
                        existing.member_since = normalized["member_since"]
                    updated += 1
                else:
                    # Create
                    member = StudioMember(
                        tenant_id=tenant_id,
                        customer_id=next_cid,
                        source="shopify",
                        source_id=source_id,
                        first_name=normalized["first_name"],
                        last_name=normalized["last_name"],
                        email=normalized["email"],
                        phone_number=normalized["phone_number"],
                        gender=normalized["gender"],
                        preferred_language=normalized["preferred_language"],
                        member_since=normalized["member_since"],
                        tags=tags_json,
                        additional_info=additional_json,
                    )
                    db.add(member)
                    next_cid += 1
                    created += 1

            except Exception as e:
                errors += 1
                error_details.append({"shopify_id": raw.get("id"), "error": str(e)})

        db.commit()

        import_log.status = "completed"
        import_log.imported = created
        import_log.updated = updated
        import_log.skipped = skipped
        import_log.errors = errors
        import_log.error_log = json.dumps(error_details, ensure_ascii=False) if error_details else None
        import_log.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "shopify.sync.completed",
            tenant_id=tenant_id,
            total=len(raw_customers),
            created=created,
            updated=updated,
            errors=errors,
        )

        return {
            "total": len(raw_customers),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as e:
        db.rollback()
        import_log.status = "failed"
        import_log.error_log = json.dumps([{"error": str(e)}])
        import_log.completed_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            pass
        logger.error("shopify.sync.failed", tenant_id=tenant_id, error=str(e))
        raise
    finally:
        db.close()


def test_shopify_connection(tenant_id: int) -> dict[str, Any]:
    """Test the Shopify connection for a tenant."""
    try:
        client = _get_shopify_client(tenant_id)
        return client.test_connection()
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
