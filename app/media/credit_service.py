"""Image credit balance management."""
from __future__ import annotations
from datetime import datetime, timezone
import structlog
from sqlalchemy.orm import Session

logger = structlog.get_logger()


def get_balance(db: Session, tenant_id: int) -> int:
    """Return current credit balance for tenant."""
    from app.core.models import ImageCreditBalance
    rec = db.query(ImageCreditBalance).filter(ImageCreditBalance.tenant_id == tenant_id).first()
    return rec.balance if rec else 0


def add_credits(db: Session, tenant_id: int, amount: int, reason: str, reference_id: str | None = None) -> int:
    """Add credits to tenant balance. Returns new balance."""
    from app.core.models import ImageCreditBalance, ImageCreditTransaction

    rec = db.query(ImageCreditBalance).filter(ImageCreditBalance.tenant_id == tenant_id).with_for_update().first()
    if not rec:
        rec = ImageCreditBalance(tenant_id=tenant_id, balance=0)
        db.add(rec)

    rec.balance += amount
    rec.updated_at = datetime.now(timezone.utc)

    tx = ImageCreditTransaction(
        tenant_id=tenant_id,
        delta=amount,
        reason=reason,
        reference_id=reference_id,
        balance_after=rec.balance,
    )
    db.add(tx)
    db.commit()
    db.refresh(rec)
    logger.info("image_credits.added", tenant_id=tenant_id, amount=amount, reason=reason, balance=rec.balance)
    return rec.balance


def deduct_credits(db: Session, tenant_id: int, amount: int, reason: str, reference_id: str | None = None) -> bool:
    """Deduct credits from tenant balance. Returns False if insufficient."""
    from app.core.models import ImageCreditBalance, ImageCreditTransaction

    rec = db.query(ImageCreditBalance).filter(ImageCreditBalance.tenant_id == tenant_id).with_for_update().first()
    if not rec or rec.balance < amount:
        return False

    rec.balance -= amount
    rec.updated_at = datetime.now(timezone.utc)

    tx = ImageCreditTransaction(
        tenant_id=tenant_id,
        delta=-amount,
        reason=reason,
        reference_id=reference_id,
        balance_after=rec.balance,
    )
    db.add(tx)
    db.commit()
    logger.info("image_credits.deducted", tenant_id=tenant_id, amount=amount, reason=reason, balance=rec.balance)
    return True


def maybe_grant_monthly_credits(db: Session, tenant_id: int) -> int:
    """Grant monthly plan credits if not already granted this month. Returns credits granted (0 if already done)."""
    from app.core.models import ImageCreditBalance, Subscription, Plan

    now = datetime.now(timezone.utc)
    year, month = now.year, now.month

    rec = db.query(ImageCreditBalance).filter(ImageCreditBalance.tenant_id == tenant_id).first()
    if rec and rec.last_grant_year == year and rec.last_grant_month == month:
        return 0  # Already granted this month

    # Find plan monthly credits
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id,
        Subscription.status.in_(["active", "trialing"]),
    ).first()
    if not sub:
        return 0

    plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
    if not plan:
        return 0

    grant = getattr(plan, "monthly_image_credits", 0) or 0
    if grant <= 0:
        return 0

    if not rec:
        rec = ImageCreditBalance(tenant_id=tenant_id, balance=0)
        db.add(rec)
        db.flush()

    rec.balance += grant
    rec.last_grant_year = year
    rec.last_grant_month = month
    rec.updated_at = datetime.now(timezone.utc)

    from app.core.models import ImageCreditTransaction
    tx = ImageCreditTransaction(
        tenant_id=tenant_id,
        delta=grant,
        reason="plan_grant",
        reference_id=f"{year}-{month:02d}",
        balance_after=rec.balance,
    )
    db.add(tx)
    db.commit()
    logger.info("image_credits.monthly_grant", tenant_id=tenant_id, grant=grant, plan=plan.slug)
    return grant
