from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.billing.models import (
    AddonDefinitionV2,
    Feature,
    FeatureEntitlement,
    PlanV2,
    SubscriptionV2,
    UsageRecordV2,
)


class BillingGatingRepository:
    """Focused read-model access for billing gating and plan comparison."""

    def get_subscription_by_tenant(self, db: Session, tenant_id: int) -> SubscriptionV2 | None:
        return db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()

    def get_plan_by_id(self, db: Session, plan_id: int | None) -> PlanV2 | None:
        if plan_id is None:
            return None
        return db.query(PlanV2).filter(PlanV2.id == plan_id).first()

    def list_active_public_plans(self, db: Session) -> list[PlanV2]:
        return (
            db.query(PlanV2)
            .filter(PlanV2.is_active.is_(True), PlanV2.is_public.is_(True))
            .order_by(PlanV2.display_order.asc())
            .all()
        )

    def get_feature_by_key(self, db: Session, feature_key: str) -> Feature | None:
        return db.query(Feature).filter(Feature.key == feature_key).first()

    def get_feature_entitlement(
        self,
        db: Session,
        *,
        feature_set_id: int,
        feature_id: int,
    ) -> FeatureEntitlement | None:
        return (
            db.query(FeatureEntitlement)
            .filter(
                FeatureEntitlement.feature_set_id == feature_set_id,
                FeatureEntitlement.feature_id == feature_id,
            )
            .first()
        )

    def list_entitlements_for_feature_set(
        self,
        db: Session,
        feature_set_id: int,
    ) -> list[tuple[FeatureEntitlement, Feature]]:
        return (
            db.query(FeatureEntitlement, Feature)
            .join(Feature, FeatureEntitlement.feature_id == Feature.id)
            .filter(FeatureEntitlement.feature_set_id == feature_set_id)
            .order_by(Feature.display_order.asc())
            .all()
        )

    def get_addon_definition_by_slug(
        self,
        db: Session,
        addon_slug: str,
    ) -> AddonDefinitionV2 | None:
        return db.query(AddonDefinitionV2).filter(AddonDefinitionV2.slug == addon_slug).first()

    def get_usage_record_for_period(
        self,
        db: Session,
        *,
        tenant_id: int,
        feature_key: str,
        period: datetime,
    ) -> UsageRecordV2 | None:
        return (
            db.query(UsageRecordV2)
            .filter(
                UsageRecordV2.tenant_id == tenant_id,
                UsageRecordV2.feature_key == feature_key,
                UsageRecordV2.period_year == period.year,
                UsageRecordV2.period_month == period.month,
            )
            .first()
        )


gating_repository = BillingGatingRepository()
