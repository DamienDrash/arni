from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.core.db import SessionLocal
from app.domains.billing.models import Plan, Subscription, UsageRecord
from app.domains.identity.models import Tenant
from app.media.service import MediaService


def _seed_media_quota_fixture(tenant_id: int) -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.query(UsageRecord).filter(UsageRecord.tenant_id == tenant_id).delete()
        db.query(Subscription).filter(Subscription.tenant_id == tenant_id).delete()
        db.query(Plan).filter(Plan.id == tenant_id).delete()
        db.query(Tenant).filter(Tenant.id == tenant_id).delete()

        db.add(
            Tenant(
                id=tenant_id,
                slug=f"media-{tenant_id}",
                name=f"Media {tenant_id}",
            )
        )
        db.add(
            Plan(
                id=tenant_id,
                name="Media Plan",
                slug=f"media-plan-{tenant_id}",
                price_monthly_cents=0,
                trial_days=0,
                ai_image_generations_per_month=2,
                media_storage_mb=1,
            )
        )
        db.add(
            Subscription(
                tenant_id=tenant_id,
                plan_id=tenant_id,
                status="active",
                current_period_start=now,
            )
        )
        db.add(
            UsageRecord(
                tenant_id=tenant_id,
                period_year=now.year,
                period_month=now.month,
                ai_image_generations_used=1,
                media_storage_bytes_used=512 * 1024,
            )
        )
        db.commit()
    finally:
        db.close()


def test_media_service_enforces_storage_and_image_quotas_from_billing_queries() -> None:
    tenant_id = 970001
    _seed_media_quota_fixture(tenant_id)

    db = SessionLocal()
    try:
        service = MediaService(db=db, tenant_id=tenant_id, tenant_slug=f"media-{tenant_id}")

        service.check_storage_quota(bytes_to_add=256 * 1024)
        service.check_image_gen_quota()

        with pytest.raises(HTTPException) as storage_error:
            service.check_storage_quota(bytes_to_add=600 * 1024)
        assert storage_error.value.status_code == 402

        service.increment_image_gen_usage()
        with pytest.raises(HTTPException) as image_error:
            service.check_image_gen_quota()
        assert image_error.value.status_code == 429
    finally:
        db.close()


def test_media_service_creates_usage_record_when_current_period_is_missing() -> None:
    tenant_id = 970002
    _seed_media_quota_fixture(tenant_id)

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.query(UsageRecord).filter(
            UsageRecord.tenant_id == tenant_id,
            UsageRecord.period_year == now.year,
            UsageRecord.period_month == now.month,
        ).delete()
        db.commit()

        service = MediaService(db=db, tenant_id=tenant_id, tenant_slug=f"media-{tenant_id}")
        service.increment_storage_usage(2048)

        record = (
            db.query(UsageRecord)
            .filter(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.period_year == now.year,
                UsageRecord.period_month == now.month,
            )
            .first()
        )
        assert record is not None
        assert record.media_storage_bytes_used == 2048
        assert record.ai_image_generations_used == 0
    finally:
        db.close()
