from __future__ import annotations

from sqlalchemy.orm import Session

from app.billing.models import Feature, UsageRecordV2


class BillingMeteringRepository:
    """Focused usage-record access for billing metering."""

    def get_usage_record(
        self,
        db: Session,
        *,
        tenant_id: int,
        feature_key: str,
        period_year: int,
        period_month: int,
    ) -> UsageRecordV2 | None:
        return (
            db.query(UsageRecordV2)
            .filter(
                UsageRecordV2.tenant_id == tenant_id,
                UsageRecordV2.feature_key == feature_key,
                UsageRecordV2.period_year == period_year,
                UsageRecordV2.period_month == period_month,
            )
            .first()
        )

    def create_usage_record(
        self,
        db: Session,
        *,
        tenant_id: int,
        feature_key: str,
        period_year: int,
        period_month: int,
        soft_limit: int | None,
        hard_limit: int | None,
    ) -> UsageRecordV2:
        usage = UsageRecordV2(
            tenant_id=tenant_id,
            feature_key=feature_key,
            period_year=period_year,
            period_month=period_month,
            usage_count=0,
            overage_count=0,
            soft_limit_snapshot=soft_limit,
            hard_limit_snapshot=hard_limit,
        )
        db.add(usage)
        db.flush()
        return usage

    def list_usage_records(
        self,
        db: Session,
        *,
        tenant_id: int,
        period_year: int,
        period_month: int,
    ) -> list[UsageRecordV2]:
        return (
            db.query(UsageRecordV2)
            .filter(
                UsageRecordV2.tenant_id == tenant_id,
                UsageRecordV2.period_year == period_year,
                UsageRecordV2.period_month == period_month,
            )
            .all()
        )

    def list_features_by_keys(
        self,
        db: Session,
        feature_keys: list[str],
    ) -> list[Feature]:
        if not feature_keys:
            return []
        return db.query(Feature).filter(Feature.key.in_(feature_keys)).all()


metering_repository = BillingMeteringRepository()
