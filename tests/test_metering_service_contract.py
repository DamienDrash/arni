from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from app.billing.metering_service import metering_service
from app.billing.models import (
    Feature,
    FeatureEntitlement,
    FeatureSet,
    FeatureType,
    PlanV2,
    SubscriptionStatus,
    SubscriptionV2,
    UsageRecordV2,
)
from app.core.db import SessionLocal
from app.core.models import Tenant


def _create_metered_tenant_setup(*, hard_limit: int = 10) -> tuple[int, str]:
    unique = int(time.time() * 1000)
    db = SessionLocal()
    try:
        tenant = Tenant(slug=f"metering-{unique}", name=f"Metering {unique}")
        feature = Feature(
            key=f"metered-{unique}",
            name=f"Metered Feature {unique}",
            feature_type=FeatureType.METERED,
        )
        feature_set = FeatureSet(name=f"Metered Set {unique}", slug=f"metered-set-{unique}")
        db.add_all([tenant, feature, feature_set])
        db.flush()

        db.add(
            FeatureEntitlement(
                feature_set_id=feature_set.id,
                feature_id=feature.id,
                value_limit=5,
                hard_limit=hard_limit,
            )
        )

        plan = PlanV2(
            slug=f"metered-plan-{unique}",
            name=f"Metered Plan {unique}",
            price_monthly_cents=0,
            feature_set_id=feature_set.id,
            is_active=True,
            is_public=False,
        )
        db.add(plan)
        db.flush()

        db.add(
            SubscriptionV2(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status=SubscriptionStatus.ACTIVE,
            )
        )
        db.commit()
        return tenant.id, feature.key
    finally:
        db.close()


def test_metering_service_record_usage_enforces_hard_limit() -> None:
    tenant_id, feature_key = _create_metered_tenant_setup(hard_limit=10)
    db = SessionLocal()
    try:
        first = asyncio.run(
            metering_service.record_usage(db, tenant_id=tenant_id, feature_key=feature_key, quantity=8)
        )
        second = asyncio.run(
            metering_service.record_usage(db, tenant_id=tenant_id, feature_key=feature_key, quantity=3)
        )
    finally:
        db.close()

    assert first.recorded is True
    assert first.current_count == 8
    assert second.recorded is False
    assert second.blocked is True
    assert second.current_count == 8


def test_metering_service_get_all_usage_hydrates_feature_names() -> None:
    tenant_id, feature_key = _create_metered_tenant_setup(hard_limit=12)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        db.add(
            UsageRecordV2(
                tenant_id=tenant_id,
                feature_key=feature_key,
                period_year=now.year,
                period_month=now.month,
                usage_count=7,
                overage_count=2,
                soft_limit_snapshot=5,
                hard_limit_snapshot=12,
            )
        )
        db.commit()

        summaries = asyncio.run(
            metering_service.get_all_usage(
                db,
                tenant_id=tenant_id,
                period_year=now.year,
                period_month=now.month,
            )
        )
    finally:
        db.close()

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.feature_key == feature_key
    assert summary.feature_name.startswith("Metered Feature")
    assert summary.usage_count == 7
    assert summary.in_overage is True
    assert summary.remaining == 0
