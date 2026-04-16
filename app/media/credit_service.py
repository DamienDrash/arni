"""Image credit balance management."""
from __future__ import annotations
from datetime import datetime, timezone
import structlog
from sqlalchemy.orm import Session
from app.domains.billing.models import ImageCreditBalance, ImageCreditTransaction
from app.domains.billing.queries import billing_queries

logger = structlog.get_logger()


def get_balance(db: Session, tenant_id: int) -> int:
    """Return current credit balance for tenant."""
    rec = billing_queries.get_image_credit_balance(db, tenant_id)
    return rec.balance if rec else 0


def add_credits(db: Session, tenant_id: int, amount: int, reason: str, reference_id: str | None = None) -> int:
    """Add credits to tenant balance. Returns new balance."""

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

    now = datetime.now(timezone.utc)
    year, month = now.year, now.month

    rec = billing_queries.get_image_credit_balance(db, tenant_id)
    if rec and rec.last_grant_year == year and rec.last_grant_month == month:
        return 0  # Already granted this month

    grant, plan_slug = billing_queries.get_monthly_image_credit_grant_for_tenant(
        db,
        tenant_id,
        subscription_statuses=("active", "trialing"),
    )
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

    tx = ImageCreditTransaction(
        tenant_id=tenant_id,
        delta=grant,
        reason="plan_grant",
        reference_id=f"{year}-{month:02d}",
        balance_after=rec.balance,
    )
    db.add(tx)
    db.commit()
    logger.info("image_credits.monthly_grant", tenant_id=tenant_id, grant=grant, plan=plan_slug)
    return grant
