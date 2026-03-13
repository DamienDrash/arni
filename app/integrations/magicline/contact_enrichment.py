"""Contact Enrichment – enriches the contacts table with Magicline data.

Fetches check-in stats, booking history, and churn prediction for every
Magicline contact and writes the results back to the contacts table:

  - Contact.score          → engagement score (0-100, inverted from churn risk)
  - Contact.lifecycle_stage → updated to "churned" when churn risk is high
  - ContactActivity        → enrichment snapshot stored in the timeline

Design:
  - `enrich_contacts_for_tenant(tenant_id)` is the main entry point
  - Throttled batch: 1 API call per contact, 50ms delay between calls
  - Idempotent: safe to run multiple times (skips contacts enriched < TTL hours ago)
  - TTL: 6 hours per contact (same as member_enrichment.py)
  - Hooked into SyncCore.run_sync() so it runs after every successful Magicline sync
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog

from app.core.contact_models import ActivityType, Contact, ContactActivity, LifecycleStage
from app.core.db import SessionLocal
from app.integrations.magicline import get_client
from app.integrations.magicline.member_enrichment import (
    CHECKIN_SLICE_SIZE,
    ENRICHMENT_TTL_HOURS,
    _compute_booking_stats,
    _compute_checkin_stats,
    _compute_churn_prediction,
    _derive_training_preferences,
    _extract_items,
    _fetch_recent_bookings,
)

logger = structlog.get_logger()

# ContactActivity type identifier for enrichment events
_ENRICHMENT_ACTIVITY_TYPE = "enrichment"

# Metadata key used to record when a contact was last enriched
_ENRICHED_AT_KEY = "enriched_at"


def _get_last_enriched_at(contact: Contact) -> datetime | None:
    """Read the last enrichment timestamp from the most recent enrichment activity."""
    # We piggyback on ContactActivity.metadata_json rather than adding a column
    # This avoids a schema migration while still supporting TTL-based caching
    # (queries are filtered in Python after loading the latest enrichment activity)
    return None  # Resolved via DB query in enrich_contacts_for_tenant


def _churn_score_to_engagement(churn_score: int) -> int:
    """Convert churn risk score (high = bad) to engagement score (high = good)."""
    return max(0, 100 - churn_score)


def _churn_risk_to_lifecycle(churn_risk: str, current_stage: str) -> str:
    """Suggest updated lifecycle_stage based on churn risk.

    Only upgrades to 'churned' or preserves 'customer' / current stage.
    Never downgrades an already 'churned' contact to a lower-risk stage
    automatically – that should be a manual action.
    """
    if current_stage == LifecycleStage.CHURNED:
        return current_stage  # Don't auto-reactivate
    if churn_risk == "high":
        return LifecycleStage.CHURNED
    return current_stage


async def enrich_single_contact(
    contact: Contact,
    tenant_id: int,
    force: bool = False,
) -> dict[str, Any]:
    """Enrich one contact with Magicline activity data.

    Args:
        contact: The Contact ORM object (not yet in session, fetched externally).
        tenant_id: Tenant the contact belongs to.
        force: Skip TTL cache and always re-fetch.

    Returns:
        Dict with enrichment results or {"skipped": True} / {"error": ...}.
    """
    # Extract Magicline customer_id from external_ids JSON
    if not contact.external_ids:
        return {"skipped": True, "reason": "no_external_ids"}

    try:
        ext = json.loads(contact.external_ids)
    except (json.JSONDecodeError, TypeError):
        return {"skipped": True, "reason": "invalid_external_ids"}

    customer_id_raw = ext.get("magicline")
    if not customer_id_raw:
        return {"skipped": True, "reason": "no_magicline_id"}

    try:
        customer_id = int(customer_id_raw)
    except (ValueError, TypeError):
        return {"skipped": True, "reason": "invalid_magicline_id"}

    client = get_client(tenant_id=tenant_id)
    if not client:
        return {"error": "Magicline not configured"}

    today = date.today()

    # Read checkin_enabled setting
    try:
        from app.gateway.persistence import persistence as _persistence
        checkin_enabled = _persistence.get_setting("checkin_enabled", "true", tenant_id=tenant_id) == "true"
    except Exception:
        checkin_enabled = True

    # Fetch check-ins (90 + 30 day window)
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
            logger.warning("contact_enrichment.checkins_failed", customer_id=customer_id, error=str(e))

    checkin_stats = _compute_checkin_stats(checkins_90, checkins_30)
    checkin_stats["checkin_enabled"] = checkin_enabled

    # Fetch bookings
    bookings: dict[str, list] = {}
    try:
        bookings = _fetch_recent_bookings(client, customer_id)
    except Exception as e:
        logger.warning("contact_enrichment.bookings_failed", customer_id=customer_id, error=str(e))
        bookings = {"upcoming": [], "past": []}

    # Booking-based stats fallback
    if checkin_stats["total_90d"] == 0 and bookings.get("past"):
        checkin_stats = _compute_booking_stats(bookings["past"])
        checkin_stats["checkin_enabled"] = checkin_enabled

    # Training preferences
    training_prefs = _derive_training_preferences(bookings)
    checkin_stats.update(training_prefs)

    # Churn prediction
    churn = _compute_churn_prediction(
        checkin_stats,
        bookings,
        is_paused=None,  # Not available directly – contacts table doesn't cache pause state
    )
    checkin_stats["churn_prediction"] = churn

    return {
        "customer_id": customer_id,
        "checkin_stats": checkin_stats,
        "bookings": bookings,
        "churn": churn,
    }


async def enrich_contacts_for_tenant(tenant_id: int, force: bool = False) -> dict[str, Any]:
    """Enrich all Magicline contacts for a tenant.

    Iterates all contacts with source='magicline', fetches enrichment data
    from Magicline, and updates Contact.score + Contact.lifecycle_stage.
    Full enrichment data is stored in ContactActivity for the timeline.

    Args:
        tenant_id: Tenant to enrich.
        force: Re-enrich even if TTL has not expired.

    Returns:
        Summary dict: {enriched, skipped, errors, tenant_id}
    """
    db = SessionLocal()
    try:
        contacts = (
            db.query(Contact)
            .filter(
                Contact.tenant_id == tenant_id,
                Contact.source == "magicline",
                Contact.deleted_at.is_(None),
            )
            .all()
        )
    except Exception as e:
        db.close()
        logger.error("contact_enrichment.query_failed", tenant_id=tenant_id, error=str(e))
        return {"enriched": 0, "skipped": 0, "errors": 1, "tenant_id": tenant_id}

    # Build TTL lookup from the last enrichment activity per contact
    if not force:
        ttl_cutoff = datetime.now(timezone.utc) - timedelta(hours=ENRICHMENT_TTL_HOURS)
        try:
            from sqlalchemy import and_
            recent_enrichments = (
                db.query(ContactActivity.contact_id, ContactActivity.created_at)
                .filter(
                    ContactActivity.tenant_id == tenant_id,
                    ContactActivity.activity_type == _ENRICHMENT_ACTIVITY_TYPE,
                    ContactActivity.created_at >= ttl_cutoff,
                )
                .all()
            )
            recently_enriched_ids = {row.contact_id for row in recent_enrichments}
        except Exception:
            recently_enriched_ids = set()
    else:
        recently_enriched_ids = set()

    db.close()

    enriched = 0
    skipped = 0
    errors = 0

    logger.info(
        "contact_enrichment.started",
        tenant_id=tenant_id,
        total_contacts=len(contacts),
        force=force,
    )

    for contact in contacts:
        # Skip if recently enriched (TTL cache)
        if not force and contact.id in recently_enriched_ids:
            skipped += 1
            continue

        try:
            result = await enrich_single_contact(contact, tenant_id=tenant_id, force=force)
        except Exception as e:
            logger.error(
                "contact_enrichment.single_failed",
                contact_id=contact.id,
                tenant_id=tenant_id,
                error=str(e),
            )
            errors += 1
            continue

        if result.get("skipped"):
            skipped += 1
            continue

        if result.get("error"):
            errors += 1
            continue

        # Persist enrichment results
        db2 = SessionLocal()
        try:
            contact_db = db2.query(Contact).filter(Contact.id == contact.id).first()
            if not contact_db:
                skipped += 1
                db2.close()
                continue

            churn = result["churn"]
            checkin_stats = result["checkin_stats"]

            # Update score (engagement = inverted churn risk)
            contact_db.score = _churn_score_to_engagement(churn["score"])

            # Update lifecycle_stage if warranted
            new_stage = _churn_risk_to_lifecycle(churn["risk"], contact_db.lifecycle_stage)
            if new_stage != contact_db.lifecycle_stage:
                contact_db.lifecycle_stage = new_stage

            contact_db.updated_at = datetime.now(timezone.utc)

            # Store enrichment snapshot in activity timeline
            db2.add(ContactActivity(
                contact_id=contact.id,
                tenant_id=tenant_id,
                activity_type=_ENRICHMENT_ACTIVITY_TYPE,
                title="Training-Analyse aktualisiert",
                description=(
                    f"Churn-Risiko: {churn['risk']} ({churn['score']}/100) | "
                    f"Besuche (30T): {checkin_stats.get('total_30d', 0)} | "
                    f"Besuche (90T): {checkin_stats.get('total_90d', 0)} | "
                    f"Letzter Besuch: {checkin_stats.get('last_visit') or '–'}"
                ),
                metadata_json=json.dumps(
                    {
                        _ENRICHED_AT_KEY: datetime.now(timezone.utc).isoformat(),
                        "churn_prediction": churn,
                        "checkin_stats": {
                            k: v for k, v in checkin_stats.items()
                            if k not in ("churn_prediction",)
                        },
                        "upcoming_bookings": len(result["bookings"].get("upcoming", [])),
                        "past_bookings_stored": len(result["bookings"].get("past", [])),
                    },
                    ensure_ascii=False,
                ),
                performed_by_name="Magicline Enrichment",
            ))

            db2.commit()
            enriched += 1

            logger.debug(
                "contact_enrichment.contact_enriched",
                contact_id=contact.id,
                customer_id=result["customer_id"],
                churn_risk=churn["risk"],
                score=contact_db.score,
            )
        except Exception as e:
            db2.rollback()
            logger.error(
                "contact_enrichment.persist_failed",
                contact_id=contact.id,
                tenant_id=tenant_id,
                error=str(e),
            )
            errors += 1
        finally:
            db2.close()

        # Throttle: brief sleep to avoid hammering the Magicline API
        await asyncio.sleep(0.05)

    logger.info(
        "contact_enrichment.completed",
        tenant_id=tenant_id,
        enriched=enriched,
        skipped=skipped,
        errors=errors,
    )

    return {"enriched": enriched, "skipped": skipped, "errors": errors, "tenant_id": tenant_id}
