"""MediaService: quota checks and DB record management for media assets."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import structlog
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.media_models import MediaAsset

logger = structlog.get_logger()


class MediaService:
    def __init__(self, db: Session, tenant_id: int, tenant_slug: str):
        self._db = db
        self._tenant_id = tenant_id
        self._tenant_slug = tenant_slug

    def _get_plan_limits(self) -> dict:
        from app.core.models import Plan, Subscription
        sub = self._db.query(Subscription).filter(
            Subscription.tenant_id == self._tenant_id,
            Subscription.status == "active",
        ).first()
        if not sub:
            return {}
        plan = self._db.query(Plan).filter(Plan.id == sub.plan_id).first()
        if not plan:
            return {}
        limits = {}
        if hasattr(plan, "ai_image_generations_per_month"):
            limits["ai_image_generations_per_month"] = plan.ai_image_generations_per_month
        if hasattr(plan, "media_storage_mb"):
            limits["media_storage_mb"] = plan.media_storage_mb
        return limits

    def _get_current_usage(self) -> dict:
        from app.core.models import UsageRecord
        now = datetime.now(timezone.utc)
        rec = self._db.query(UsageRecord).filter(
            UsageRecord.tenant_id == self._tenant_id,
            UsageRecord.period_year == now.year,
            UsageRecord.period_month == now.month,
        ).first()
        if not rec:
            return {"ai_image_generations_used": 0, "media_storage_bytes_used": 0}
        return {
            "ai_image_generations_used": getattr(rec, "ai_image_generations_used", 0) or 0,
            "media_storage_bytes_used": getattr(rec, "media_storage_bytes_used", 0) or 0,
        }

    def _get_or_create_usage_record(self):
        from app.core.models import UsageRecord
        now = datetime.now(timezone.utc)
        rec = self._db.query(UsageRecord).filter(
            UsageRecord.tenant_id == self._tenant_id,
            UsageRecord.period_year == now.year,
            UsageRecord.period_month == now.month,
        ).first()
        if not rec:
            rec = UsageRecord(
                tenant_id=self._tenant_id,
                period_year=now.year,
                period_month=now.month,
            )
            self._db.add(rec)
            self._db.flush()
        return rec

    def check_storage_quota(self, bytes_to_add: int = 0) -> None:
        limits = self._get_plan_limits()
        limit_mb = limits.get("media_storage_mb")
        if limit_mb is None or limit_mb == -1:
            return
        usage = self._get_current_usage()
        current_bytes = usage.get("media_storage_bytes_used", 0)
        if (current_bytes + bytes_to_add) > limit_mb * 1024 * 1024:
            raise HTTPException(
                status_code=402,
                detail=f"Media storage limit of {limit_mb}MB reached. Please upgrade your plan.",
            )

    def check_image_gen_quota(self) -> None:
        limits = self._get_plan_limits()
        limit = limits.get("ai_image_generations_per_month")
        if limit is None or limit == -1:
            return
        if limit == 0:
            raise HTTPException(
                status_code=402,
                detail="AI image generation is not available on your current plan. Please upgrade.",
            )
        usage = self._get_current_usage()
        if usage.get("ai_image_generations_used", 0) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly AI image generation limit of {limit} reached. Please upgrade your plan.",
            )

    def record_upload(self, filename: str, original_filename: str, file_size: int,
                      mime_type: str, width: Optional[int], height: Optional[int],
                      created_by: Optional[int]) -> MediaAsset:
        asset = MediaAsset(
            tenant_id=self._tenant_id,
            filename=filename,
            original_filename=original_filename,
            file_size=file_size,
            mime_type=mime_type,
            width=width,
            height=height,
            source="upload",
            created_by=created_by,
        )
        self._db.add(asset)
        self._db.commit()
        self._db.refresh(asset)
        return asset

    def record_ai_generated(self, filename: str, file_size: int, mime_type: str,
                             prompt: str, provider_slug: str,
                             created_by: Optional[int]) -> MediaAsset:
        asset = MediaAsset(
            tenant_id=self._tenant_id,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            source="ai_generated",
            generation_prompt=prompt,
            image_provider_slug=provider_slug,
            created_by=created_by,
        )
        self._db.add(asset)
        self._db.commit()
        self._db.refresh(asset)
        return asset

    def increment_image_gen_usage(self) -> None:
        rec = self._get_or_create_usage_record()
        current = getattr(rec, "ai_image_generations_used", 0) or 0
        if hasattr(rec, "ai_image_generations_used"):
            rec.ai_image_generations_used = current + 1
            self._db.commit()

    def increment_storage_usage(self, bytes_added: int) -> None:
        rec = self._get_or_create_usage_record()
        current = getattr(rec, "media_storage_bytes_used", 0) or 0
        if hasattr(rec, "media_storage_bytes_used"):
            rec.media_storage_bytes_used = current + bytes_added
            self._db.commit()

    def decrement_storage_usage(self, bytes_removed: int) -> None:
        rec = self._get_or_create_usage_record()
        current = getattr(rec, "media_storage_bytes_used", 0) or 0
        if hasattr(rec, "media_storage_bytes_used"):
            rec.media_storage_bytes_used = max(0, current - bytes_removed)
            self._db.commit()
