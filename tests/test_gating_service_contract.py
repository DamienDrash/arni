from __future__ import annotations

import time
from datetime import datetime, timezone

from app.billing.gating_service import gating_service
from app.billing.models import (
    AddonDefinitionV2,
    Feature,
    FeatureEntitlement,
    FeatureSet,
    FeatureType,
    PlanV2,
    SubscriptionStatus,
    SubscriptionV2,
    TenantAddonV2,
    UsageRecordV2,
)
from app.core.db import SessionLocal
from app.core.models import Tenant


def test_gating_service_plan_comparison_returns_public_plans_with_entitlements() -> None:
    db = SessionLocal()
    try:
        plans = __import__("asyncio").run(gating_service.get_plan_comparison(db))
    finally:
        db.close()

    assert plans
    starter = next(plan for plan in plans if plan["slug"] == "starter")
    assert starter["features_display"]
    assert "max_members" in starter["entitlements"]
    assert starter["entitlements"]["max_members"]["value"] == 500


def test_gating_service_merges_addon_limit_entitlements_additively() -> None:
    unique = int(time.time() * 1000)
    db = SessionLocal()
    try:
        tenant = Tenant(slug=f"gating-addon-{unique}", name=f"Gating Addon {unique}")
        db.add(tenant)
        db.flush()

        base_plan = db.query(PlanV2).filter(PlanV2.slug == "starter").first()
        assert base_plan is not None

        feature = db.query(Feature).filter(Feature.key == "max_channels").first()
        assert feature is not None

        addon_feature_set = FeatureSet(name=f"Addon Channels {unique}", slug=f"addon-channels-{unique}")
        db.add(addon_feature_set)
        db.flush()

        db.add(
            FeatureEntitlement(
                feature_set_id=addon_feature_set.id,
                feature_id=feature.id,
                value_limit=2,
            )
        )
        db.add(
            AddonDefinitionV2(
                slug=f"extra-channel-test-{unique}",
                name="Extra Channel Test",
                feature_set_id=addon_feature_set.id,
                is_active=True,
            )
        )
        db.flush()

        sub = SubscriptionV2(
            tenant_id=tenant.id,
            plan_id=base_plan.id,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(sub)
        db.flush()

        db.add(
            TenantAddonV2(
                subscription_id=sub.id,
                addon_slug=f"extra-channel-test-{unique}",
                quantity=2,
                status="active",
            )
        )
        db.commit()

        result = __import__("asyncio").run(
            gating_service.check_limit(db, tenant.id, "max_channels", current_count=3)
        )
    finally:
        db.close()

    assert result["limit"] == 5
    assert result["allowed"] is True
    assert result["remaining"] == 2


def test_gating_service_usage_limit_reads_current_period_usage() -> None:
    unique = int(time.time() * 1000)
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        tenant = Tenant(slug=f"gating-usage-{unique}", name=f"Gating Usage {unique}")
        db.add(tenant)
        db.flush()

        feature = Feature(
            key=f"metered-feature-{unique}",
            name="Metered Feature Test",
            feature_type=FeatureType.METERED,
        )
        feature_set = FeatureSet(name=f"Metered Set {unique}", slug=f"metered-set-{unique}")
        db.add_all([feature, feature_set])
        db.flush()

        db.add(
            FeatureEntitlement(
                feature_set_id=feature_set.id,
                feature_id=feature.id,
                value_limit=100,
                hard_limit=120,
            )
        )

        plan = PlanV2(
            slug=f"metered-plan-{unique}",
            name="Metered Plan Test",
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
        db.add(
            UsageRecordV2(
                tenant_id=tenant.id,
                feature_key=feature.key,
                period_year=now.year,
                period_month=now.month,
                usage_count=110,
                overage_count=10,
            )
        )
        db.commit()

        result = __import__("asyncio").run(
            gating_service.check_usage_limit(db, tenant.id, feature.key)
        )
    finally:
        db.close()

    assert result["allowed"] is True
    assert result["usage"] == 110
    assert result["soft_limit"] == 100
    assert result["hard_limit"] == 120
    assert result["in_overage"] is True
    assert result["remaining"] == 10
