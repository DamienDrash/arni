"""Seed image credit packs into DB and sync plan monthly credits."""
from __future__ import annotations
import structlog
from sqlalchemy.orm import Session

from app.domains.billing.models import ImageCreditPack, Plan

logger = structlog.get_logger()

_CREDIT_PACKS = [
    {
        "slug": "credits_s",
        "name": "Credit Pack S",
        "description": "100 Credits für Bildgenerierung",
        "credits": 100,
        "price_once_cents": 500,
        "price_monthly_cents": 450,
        "price_yearly_cents": 4800,
        "display_order": 1,
    },
    {
        "slug": "credits_m",
        "name": "Credit Pack M",
        "description": "500 Credits für Bildgenerierung",
        "credits": 500,
        "price_once_cents": 2000,
        "price_monthly_cents": 1800,
        "price_yearly_cents": 19200,
        "display_order": 2,
    },
    {
        "slug": "credits_l",
        "name": "Credit Pack L",
        "description": "2.000 Credits für Bildgenerierung",
        "credits": 2000,
        "price_once_cents": 7000,
        "price_monthly_cents": 6000,
        "price_yearly_cents": 60000,
        "display_order": 3,
    },
]

_PLAN_MONTHLY_CREDITS = {
    "trial":      5,
    "starter":    10,
    "pro":        50,
    "business":   150,
    "enterprise": 500,
}


def seed_credit_packs(db: Session) -> None:
    """Idempotently seed credit packs."""
    for data in _CREDIT_PACKS:
        existing = db.query(ImageCreditPack).filter(ImageCreditPack.slug == data["slug"]).first()
        if existing:
            # Update name/description/prices if changed
            for k, v in data.items():
                if getattr(existing, k, None) != v:
                    setattr(existing, k, v)
            db.commit()
            continue
        pack = ImageCreditPack(**data)
        db.add(pack)
        logger.info("credit_seed.pack_created", slug=data["slug"])
    db.commit()


def seed_plan_credits(db: Session) -> None:
    """Backfill monthly_image_credits on all plans."""
    for slug, credits in _PLAN_MONTHLY_CREDITS.items():
        plan = db.query(Plan).filter(Plan.slug == slug).first()
        if plan and getattr(plan, "monthly_image_credits", None) != credits:
            plan.monthly_image_credits = credits
            db.commit()
            logger.info("credit_seed.plan_updated", slug=slug, credits=credits)
    logger.info("credit_seed.plan_credits_done")
