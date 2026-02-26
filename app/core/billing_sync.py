"""ARIIA – Billing Sync Engine (S4.3).

Bidirectional synchronization between local Plan/Addon definitions and Stripe.

Directions
----------
- **push_plan_to_stripe(plan)**: Local DB → Stripe (Product + Price).
  Called when a system admin creates or edits a plan in the Admin UI.
- **push_addon_to_stripe(addon)**: Local DB → Stripe (Product + Price).
  Called when a system admin creates or edits an addon in the Admin UI.
- **sync_plans_from_stripe()**: Stripe → Local DB.
  Called periodically (every 15 min) and on manual trigger.
  Updates prices, active-status and stripe IDs.  Does NOT overwrite
  feature-flags or limits (those are admin-only).
- **sync_addons_from_stripe()**: Stripe → Local DB.
  Mirrors addon products/prices from Stripe into AddonDefinition rows.
- **full_bidirectional_sync()**: Convenience wrapper that runs both directions.

Stripe Product Naming Convention
---------------------------------
Plans:   ``ARIIA Plan: <name>``        → metadata.ariia_type = "plan", metadata.ariia_slug = "<slug>"
Addons:  ``ARIIA Add-on: <name>``      → metadata.ariia_type = "addon", metadata.ariia_slug = "<slug>"

All Stripe interactions use the secret key stored in the Settings table
(key ``billing_stripe_secret_key``, encrypted at rest).
"""

from __future__ import annotations

import json
import structlog
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.models import Plan, AddonDefinition
from app.gateway.persistence import persistence

logger = structlog.get_logger()


# ── Stripe Client ────────────────────────────────────────────────────────────

def get_stripe_client():
    """Return configured stripe module or None if not available.

    Reads the secret key from the encrypted Settings store.
    """
    sk = persistence.get_setting("billing_stripe_secret_key", "", tenant_id=1)
    if not sk:
        return None
    try:
        import stripe
        stripe.api_key = sk
        return stripe
    except ImportError:
        logger.error("billing.stripe_not_installed")
        return None


def is_stripe_configured() -> bool:
    """Check whether Stripe is enabled and a secret key is present.

    Stripe credentials are system-wide (tenant_id=1).
    """
    enabled = (persistence.get_setting("billing_stripe_enabled", "false", tenant_id=1) or "").lower() == "true"
    sk = (persistence.get_setting("billing_stripe_secret_key", "", tenant_id=1) or "").strip()
    return enabled and bool(sk)


# ── Push to Stripe (Local → Stripe) ─────────────────────────────────────────

async def push_plan_to_stripe(db: Session, plan: Plan) -> bool:
    """Create or update a Stripe Product + Price for a local Plan.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session (will be committed on success).
    plan : Plan
        The local plan object to sync.

    Returns
    -------
    bool
        True if sync succeeded.
    """
    s = get_stripe_client()
    if not s:
        return False

    try:
        product_name = f"ARIIA Plan: {plan.name}"
        metadata = {
            "ariia_type": "plan",
            "ariia_slug": plan.slug,
            "ariia_plan_id": str(plan.id),
        }

        # 1. Find or create Product
        if plan.stripe_product_id:
            try:
                prod = s.Product.retrieve(plan.stripe_product_id)
                s.Product.modify(
                    plan.stripe_product_id,
                    name=product_name,
                    active=plan.is_active,
                    description=plan.description or "",
                    metadata=metadata,
                )
            except Exception:
                plan.stripe_product_id = None

        if not plan.stripe_product_id:
            # Search by metadata first
            existing = s.Product.search(query=f"metadata['ariia_slug']:'{plan.slug}'")
            if existing.data:
                prod = existing.data[0]
                plan.stripe_product_id = prod.id
                s.Product.modify(
                    prod.id,
                    name=product_name,
                    active=plan.is_active,
                    description=plan.description or "",
                    metadata=metadata,
                )
            else:
                prod = s.Product.create(
                    name=product_name,
                    active=plan.is_active,
                    description=plan.description or "",
                    metadata=metadata,
                )
                plan.stripe_product_id = prod.id

        # 2. Handle Monthly Price
        plan.stripe_price_id = await _sync_price(
            s, plan.stripe_product_id, plan.stripe_price_id,
            plan.price_monthly_cents, "month",
        )

        # 3. Handle Yearly Price (if configured)
        if plan.price_yearly_cents is not None and plan.price_yearly_cents > 0:
            plan.stripe_price_yearly_id = await _sync_price(
                s, plan.stripe_product_id, plan.stripe_price_yearly_id,
                plan.price_yearly_cents, "year",
            )

        db.commit()
        logger.info("billing.push_plan_ok", slug=plan.slug, product_id=plan.stripe_product_id)
        return True

    except Exception as e:
        logger.error("billing.push_plan_failed", slug=plan.slug, error=str(e))
        return False


async def push_addon_to_stripe(db: Session, addon: AddonDefinition) -> bool:
    """Create or update a Stripe Product + Price for a local AddonDefinition."""
    s = get_stripe_client()
    if not s:
        return False

    try:
        product_name = f"ARIIA Add-on: {addon.name}"
        metadata = {
            "ariia_type": "addon",
            "ariia_slug": addon.slug,
            "ariia_addon_id": str(addon.id),
        }

        # Find or create Product
        if addon.stripe_product_id:
            try:
                s.Product.modify(
                    addon.stripe_product_id,
                    name=product_name,
                    active=addon.is_active,
                    description=addon.description or "",
                    metadata=metadata,
                )
            except Exception:
                addon.stripe_product_id = None

        if not addon.stripe_product_id:
            existing = s.Product.search(query=f"metadata['ariia_slug']:'{addon.slug}'")
            if existing.data:
                addon.stripe_product_id = existing.data[0].id
                s.Product.modify(
                    addon.stripe_product_id,
                    name=product_name,
                    active=addon.is_active,
                    description=addon.description or "",
                    metadata=metadata,
                )
            else:
                prod = s.Product.create(
                    name=product_name,
                    active=addon.is_active,
                    description=addon.description or "",
                    metadata=metadata,
                )
                addon.stripe_product_id = prod.id

        # Price
        addon.stripe_price_id = await _sync_price(
            s, addon.stripe_product_id, addon.stripe_price_id,
            addon.price_monthly_cents, "month",
        )

        db.commit()
        logger.info("billing.push_addon_ok", slug=addon.slug, product_id=addon.stripe_product_id)
        return True

    except Exception as e:
        logger.error("billing.push_addon_failed", slug=addon.slug, error=str(e))
        return False


async def _sync_price(
    stripe_mod, product_id: str, current_price_id: Optional[str],
    amount_cents: int, interval: str,
) -> Optional[str]:
    """Ensure a Stripe Price exists with the correct amount. Returns the price ID.

    If the current price has a different amount, archives it and creates a new one.
    """
    if current_price_id:
        try:
            existing_price = stripe_mod.Price.retrieve(current_price_id)
            if existing_price.unit_amount == amount_cents and existing_price.active:
                return current_price_id
            # Price changed → archive old, create new
            stripe_mod.Price.modify(current_price_id, active=False)
        except Exception:
            pass

    if amount_cents < 0:
        return current_price_id

    new_price = stripe_mod.Price.create(
        product=product_id,
        unit_amount=amount_cents,
        currency="eur",
        recurring={"interval": interval},
    )
    return new_price.id


# ── Sync from Stripe (Stripe → Local) ───────────────────────────────────────

async def sync_plans_from_stripe(db: Session) -> dict:
    """Pull plan data from Stripe and update local Plan rows.

    Only updates: stripe IDs, price, active status, name.
    Does NOT overwrite feature-flags or limits (admin-controlled).

    Returns
    -------
    dict
        Summary with counts of created, updated, deactivated plans.
    """
    s = get_stripe_client()
    if not s:
        return {"error": "stripe_not_configured"}

    result = {"created": 0, "updated": 0, "deactivated": 0}

    try:
        products = s.Product.list(active=True, limit=100)
        seen_slugs = set()

        for prod in products.data:
            meta = prod.get("metadata", {})
            ariia_type = meta.get("ariia_type", "")
            ariia_slug = meta.get("ariia_slug", "")

            # Legacy detection: products named "ARIIA <name>" without metadata
            if not ariia_type and prod.name.startswith("ARIIA ") and "Add-on" not in prod.name:
                ariia_type = "plan"
                ariia_slug = prod.name.replace("ARIIA Plan: ", "").replace("ARIIA ", "").lower().strip().replace(" ", "-")

            if ariia_type != "plan" or not ariia_slug:
                continue

            # ── Slug normalization: map common Stripe names to local slugs ──
            SLUG_ALIASES = {
                "professional": "pro",
                "prof": "pro",
                "starter-plan": "starter",
                "business-plan": "business",
                "enterprise-plan": "enterprise",
            }
            ariia_slug = SLUG_ALIASES.get(ariia_slug, ariia_slug)

            # Skip if we already processed this slug (prevents duplicates)
            if ariia_slug in seen_slugs:
                continue
            seen_slugs.add(ariia_slug)

            # Fetch active prices
            prices = s.Price.list(product=prod.id, active=True, limit=10)
            monthly_price = None
            yearly_price = None
            for p in prices.data:
                interval = (p.get("recurring") or {}).get("interval", "month")
                if interval == "month" and not monthly_price:
                    monthly_price = p
                elif interval == "year" and not yearly_price:
                    yearly_price = p

            # Also try to find by stripe_product_id first (most reliable)
            plan = db.query(Plan).filter(Plan.stripe_product_id == prod.id).first()
            if not plan:
                plan = db.query(Plan).filter(Plan.slug == ariia_slug).first()

            if plan:
                # Update existing
                plan.stripe_product_id = prod.id
                if monthly_price:
                    plan.stripe_price_id = monthly_price.id
                    plan.price_monthly_cents = monthly_price.unit_amount or 0
                if yearly_price:
                    plan.stripe_price_yearly_id = yearly_price.id
                    plan.price_yearly_cents = yearly_price.unit_amount or 0
                plan.is_active = prod.active
                # Do NOT overwrite name if plan already has a good name from seed
                # Only update name for plans that were created from Stripe (no seed)
                if not plan.features_json:
                    clean_name = prod.name.replace("ARIIA Plan: ", "").replace("ARIIA ", "").strip()
                    if clean_name:
                        plan.name = clean_name
                if prod.description and not plan.description:
                    plan.description = prod.description
                result["updated"] += 1
            else:
                # Create new plan from Stripe — only if slug is not already taken
                existing_by_slug = db.query(Plan).filter(Plan.slug == ariia_slug).first()
                if existing_by_slug:
                    # Update the existing one instead of creating a duplicate
                    existing_by_slug.stripe_product_id = prod.id
                    if monthly_price:
                        existing_by_slug.stripe_price_id = monthly_price.id
                        existing_by_slug.price_monthly_cents = monthly_price.unit_amount or 0
                    result["updated"] += 1
                else:
                    new_plan = Plan(
                        name=prod.name.replace("ARIIA Plan: ", "").replace("ARIIA ", "").strip(),
                        slug=ariia_slug,
                        description=prod.description or "",
                        stripe_product_id=prod.id,
                        stripe_price_id=monthly_price.id if monthly_price else None,
                        stripe_price_yearly_id=yearly_price.id if yearly_price else None,
                        price_monthly_cents=monthly_price.unit_amount if monthly_price else 0,
                        price_yearly_cents=yearly_price.unit_amount if yearly_price else None,
                        is_active=True,
                    )
                    db.add(new_plan)
                    result["created"] += 1

        db.commit()
        logger.info("billing.sync_plans_from_stripe_ok", **result)
        return result

    except Exception as e:
        db.rollback()
        logger.error("billing.sync_plans_from_stripe_failed", error=str(e))
        return {"error": str(e)}


async def sync_addons_from_stripe(db: Session) -> dict:
    """Pull addon data from Stripe and update local AddonDefinition rows."""
    s = get_stripe_client()
    if not s:
        return {"error": "stripe_not_configured"}

    result = {"created": 0, "updated": 0}

    try:
        products = s.Product.list(active=True, limit=100)

        for prod in products.data:
            meta = prod.get("metadata", {})
            ariia_type = meta.get("ariia_type", "")
            ariia_slug = meta.get("ariia_slug", "")

            # Legacy detection
            if not ariia_type and ("Add-on" in prod.name or "Addon" in prod.name):
                ariia_type = "addon"
                ariia_slug = prod.name.split(":")[-1].strip().lower().replace(" ", "_") if ":" in prod.name else prod.name.lower().replace(" ", "_")

            if ariia_type != "addon" or not ariia_slug:
                continue

            prices = s.Price.list(product=prod.id, active=True, limit=1)
            price = prices.data[0] if prices.data else None

            addon = db.query(AddonDefinition).filter(AddonDefinition.slug == ariia_slug).first()
            if addon:
                addon.stripe_product_id = prod.id
                if price:
                    addon.stripe_price_id = price.id
                    addon.price_monthly_cents = price.unit_amount or 0
                addon.is_active = prod.active
                clean_name = prod.name.replace("ARIIA Add-on: ", "").replace("ARIIA Addon: ", "").strip()
                if clean_name:
                    addon.name = clean_name
                if prod.description:
                    addon.description = prod.description
                result["updated"] += 1
            else:
                new_addon = AddonDefinition(
                    slug=ariia_slug,
                    name=prod.name.replace("ARIIA Add-on: ", "").replace("ARIIA Addon: ", "").strip(),
                    description=prod.description or "",
                    stripe_product_id=prod.id,
                    stripe_price_id=price.id if price else None,
                    price_monthly_cents=price.unit_amount if price else 0,
                    is_active=True,
                )
                db.add(new_addon)
                result["created"] += 1

        db.commit()
        logger.info("billing.sync_addons_from_stripe_ok", **result)
        return result

    except Exception as e:
        db.rollback()
        logger.error("billing.sync_addons_from_stripe_failed", error=str(e))
        return {"error": str(e)}


async def full_bidirectional_sync(db: Session) -> dict:
    """Run a full bidirectional sync.

    1. Push all local plans/addons that have no stripe_product_id to Stripe.
    2. Pull all Stripe products back to update IDs and prices.
    """
    push_results = {"plans_pushed": 0, "addons_pushed": 0}

    # Push plans without Stripe IDs
    plans_without_stripe = db.query(Plan).filter(
        Plan.stripe_product_id.is_(None),
        Plan.is_active.is_(True),
    ).all()
    for plan in plans_without_stripe:
        ok = await push_plan_to_stripe(db, plan)
        if ok:
            push_results["plans_pushed"] += 1

    # Push addons without Stripe IDs
    addons_without_stripe = db.query(AddonDefinition).filter(
        AddonDefinition.stripe_product_id.is_(None),
        AddonDefinition.is_active.is_(True),
    ).all()
    for addon in addons_without_stripe:
        ok = await push_addon_to_stripe(db, addon)
        if ok:
            push_results["addons_pushed"] += 1

    # Pull from Stripe
    plan_sync = await sync_plans_from_stripe(db)
    addon_sync = await sync_addons_from_stripe(db)

    return {
        "push": push_results,
        "pull_plans": plan_sync,
        "pull_addons": addon_sync,
    }


# ── Legacy Compatibility ────────────────────────────────────────────────────

# Keep old function names for backward compatibility
async def sync_from_stripe(db: Session):
    """Legacy wrapper — calls sync_plans_from_stripe."""
    return await sync_plans_from_stripe(db)


async def push_to_stripe(db: Session, plan: Plan):
    """Legacy wrapper — calls push_plan_to_stripe."""
    return await push_plan_to_stripe(db, plan)
