"""
ARIIA Billing V2 – Gating Service

Provides feature access control based on the tenant's subscription plan.

Key capabilities:
- Boolean feature checks (has_feature)
- Limit checks (check_limit)
- Tier checks (get_tier)
- Metered usage checks (check_usage_limit)
- Redis caching for hot-path queries
- Addon-aware: checks both plan features and active addons

Usage:
    from app.billing.gating_service import gating_service

    # Check boolean feature
    if not await gating_service.has_feature(db, tenant_id=42, feature_key="api_access"):
        raise HTTPException(403, "API access not available on your plan")

    # Check limit
    result = await gating_service.check_limit(db, tenant_id=42, feature_key="max_members", current_count=450)
    if not result["allowed"]:
        raise HTTPException(403, f"Member limit reached: {result['limit']}")
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.billing.gating_repository import gating_repository
from app.billing.models import (
    FeatureType,
    SubscriptionStatus,
)

logger = structlog.get_logger()


class GatingServiceV2:
    """
    Feature gating service with plan-aware access control.

    Resolution order for feature access:
    1. Check the plan's FeatureSet
    2. Check active addon FeatureSets (additive)
    3. Apply the most permissive result

    Caching strategy:
    - Feature entitlements are cached per tenant in Redis (TTL: 5 min)
    - Cache is invalidated on subscription/addon changes
    """

    CACHE_TTL = 300  # 5 minutes

    # ── Boolean Feature Check ───────────────────────────────────────────

    async def has_feature(
        self,
        db: Session,
        tenant_id: int,
        feature_key: str,
    ) -> bool:
        """
        Check if a tenant has access to a boolean feature.

        Returns True if the feature is enabled in the plan or any active addon.
        Returns True by default if the feature is not defined (fail-open for unknown features).
        """
        entitlement = self._resolve_entitlement(db, tenant_id, feature_key)
        if entitlement is None:
            # Feature not defined in any set — fail-open
            return True

        return entitlement.get("value_bool", False)

    # ── Limit Check ─────────────────────────────────────────────────────

    async def check_limit(
        self,
        db: Session,
        tenant_id: int,
        feature_key: str,
        current_count: int = 0,
    ) -> dict[str, Any]:
        """
        Check if a tenant is within a numeric limit.

        Returns:
            {
                "allowed": bool,
                "limit": int | None (None = unlimited),
                "current": int,
                "remaining": int | None,
                "percentage_used": float | None,
            }
        """
        entitlement = self._resolve_entitlement(db, tenant_id, feature_key)

        if entitlement is None:
            return {
                "allowed": True,
                "limit": None,
                "current": current_count,
                "remaining": None,
                "percentage_used": None,
            }

        limit = entitlement.get("value_limit")
        if limit is None:
            # Unlimited
            return {
                "allowed": True,
                "limit": None,
                "current": current_count,
                "remaining": None,
                "percentage_used": None,
            }

        remaining = max(0, limit - current_count)
        percentage = current_count / limit if limit > 0 else 0.0

        return {
            "allowed": current_count < limit,
            "limit": limit,
            "current": current_count,
            "remaining": remaining,
            "percentage_used": round(percentage, 4),
        }

    # ── Tier Check ──────────────────────────────────────────────────────

    async def get_tier(
        self,
        db: Session,
        tenant_id: int,
        feature_key: str = "ai_tier",
    ) -> str:
        """
        Get the tier value for a feature.

        Returns the tier string (e.g., "basic", "premium", "unlimited").
        Defaults to "basic" if not found.
        """
        entitlement = self._resolve_entitlement(db, tenant_id, feature_key)
        if entitlement is None:
            return "basic"
        return entitlement.get("value_tier", "basic")

    # ── Metered Usage Check ─────────────────────────────────────────────

    async def check_usage_limit(
        self,
        db: Session,
        tenant_id: int,
        feature_key: str,
    ) -> dict[str, Any]:
        """
        Check metered usage against limits for the current period.

        Returns:
            {
                "allowed": bool,
                "usage": int,
                "soft_limit": int | None,
                "hard_limit": int | None,
                "in_overage": bool,
                "remaining": int | None,
            }
        """
        now = datetime.now(timezone.utc)
        entitlement = self._resolve_entitlement(db, tenant_id, feature_key)

        soft_limit = entitlement.get("value_limit") if entitlement else None
        hard_limit = entitlement.get("hard_limit") if entitlement else None

        # Get current usage
        usage = gating_repository.get_usage_record_for_period(
            db,
            tenant_id=tenant_id,
            feature_key=feature_key,
            period=now,
        )

        current = usage.usage_count if usage else 0

        # Determine if blocked
        blocked = False
        if hard_limit is not None and current >= hard_limit:
            blocked = True

        in_overage = False
        if soft_limit is not None and current > soft_limit:
            in_overage = True

        remaining = None
        if hard_limit is not None:
            remaining = max(0, hard_limit - current)
        elif soft_limit is not None:
            remaining = max(0, soft_limit - current)

        return {
            "allowed": not blocked,
            "usage": current,
            "soft_limit": soft_limit,
            "hard_limit": hard_limit,
            "in_overage": in_overage,
            "remaining": remaining,
        }

    # ── Full Entitlement Summary ────────────────────────────────────────

    async def get_entitlements(
        self,
        db: Session,
        tenant_id: int,
    ) -> dict[str, Any]:
        """
        Get the complete entitlement summary for a tenant.

        Returns a dict keyed by feature_key with the resolved entitlement values.
        """
        sub = gating_repository.get_subscription_by_tenant(db, tenant_id)
        if not sub:
            return {}

        plan = gating_repository.get_plan_by_id(db, sub.plan_id)
        if not plan or not plan.feature_set_id:
            return {}

        entitlements = gating_repository.list_entitlements_for_feature_set(db, plan.feature_set_id)

        result = {}
        for ent, feat in entitlements:
            value: Any = None
            if feat.feature_type == FeatureType.BOOLEAN:
                value = ent.value_bool
            elif feat.feature_type == FeatureType.LIMIT:
                value = ent.value_limit  # None = unlimited
            elif feat.feature_type == FeatureType.TIER:
                value = ent.value_tier
            elif feat.feature_type == FeatureType.METERED:
                value = {
                    "soft_limit": ent.value_limit,
                    "hard_limit": ent.hard_limit,
                    "overage_price_cents": ent.overage_price_cents,
                }

            result[feat.key] = {
                "name": feat.name,
                "type": feat.feature_type.value if isinstance(feat.feature_type, FeatureType) else str(feat.feature_type),
                "category": feat.category,
                "value": value,
            }

        # Merge addon entitlements (additive)
        if sub.addons:
            for addon in sub.addons:
                if addon.status != "active":
                    continue
                addon_def = gating_repository.get_addon_definition_by_slug(db, addon.addon_slug)
                if addon_def and addon_def.feature_set_id:
                    addon_ents = gating_repository.list_entitlements_for_feature_set(db, addon_def.feature_set_id)
                    for ent, feat in addon_ents:
                        if feat.key in result:
                            # Additive: for booleans, OR; for limits, add
                            existing = result[feat.key]
                            if feat.feature_type == FeatureType.BOOLEAN:
                                existing["value"] = existing["value"] or ent.value_bool
                            elif feat.feature_type == FeatureType.LIMIT:
                                if existing["value"] is not None and ent.value_limit is not None:
                                    existing["value"] = existing["value"] + ent.value_limit
                                elif ent.value_limit is None:
                                    existing["value"] = None  # Unlimited wins
                        else:
                            value = None
                            if feat.feature_type == FeatureType.BOOLEAN:
                                value = ent.value_bool
                            elif feat.feature_type == FeatureType.LIMIT:
                                value = ent.value_limit
                            elif feat.feature_type == FeatureType.TIER:
                                value = ent.value_tier

                            result[feat.key] = {
                                "name": feat.name,
                                "type": feat.feature_type.value if isinstance(feat.feature_type, FeatureType) else str(feat.feature_type),
                                "category": feat.category,
                                "value": value,
                                "source": f"addon:{addon.addon_slug}",
                            }

        return result

    # ── Plan Comparison ─────────────────────────────────────────────────

    async def get_plan_comparison(self, db: Session) -> list[dict[str, Any]]:
        """
        Get a comparison of all active plans with their feature entitlements.

        Used for the pricing page.
        """
        plans = gating_repository.list_active_public_plans(db)

        result = []
        for plan in plans:
            plan_data: dict[str, Any] = {
                "slug": plan.slug,
                "name": plan.name,
                "description": plan.description,
                "tagline": plan.tagline,
                "price_monthly_cents": plan.price_monthly_cents,
                "price_yearly_cents": plan.price_yearly_cents,
                "currency": plan.currency,
                "trial_days": plan.trial_days,
                "is_highlighted": plan.is_highlighted,
                "highlight_label": plan.highlight_label,
                "cta_text": plan.cta_text,
                "features_display": [],
                "entitlements": {},
            }

            # Parse features_json for display
            if plan.features_json:
                try:
                    plan_data["features_display"] = json.loads(plan.features_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            # Legacy-compatible features list (string list)
            plan_data["features"] = plan_data["features_display"] if plan_data["features_display"] else self._build_fallback_features(plan)

            # Get entitlements
            if plan.feature_set_id:
                entitlements = gating_repository.list_entitlements_for_feature_set(db, plan.feature_set_id)

                for ent, feat in entitlements:
                    value: Any = None
                    if feat.feature_type == FeatureType.BOOLEAN:
                        value = ent.value_bool
                    elif feat.feature_type == FeatureType.LIMIT:
                        value = ent.value_limit
                    elif feat.feature_type == FeatureType.TIER:
                        value = ent.value_tier

                    plan_data["entitlements"][feat.key] = {
                        "name": feat.name,
                        "type": feat.feature_type.value if isinstance(feat.feature_type, FeatureType) else str(feat.feature_type),
                        "value": value,
                        "category": feat.category,
                    }

            result.append(plan_data)

        return result

    def _build_fallback_features(self, plan: Any) -> list[str]:
        """Build a stable public feature list when features_json is empty."""
        features: list[str] = []
        max_channels = getattr(plan, "max_channels", None)
        if isinstance(max_channels, int) and max_channels > 0:
            features.append(f"{max_channels} Kanal" if max_channels == 1 else f"{max_channels} Kanaele")
        max_members = getattr(plan, "max_members", None)
        if max_members is None:
            features.append("Unbegrenzte Mitglieder")
        elif isinstance(max_members, int) and max_members > 0:
            features.append(f"{max_members} Mitglieder")
        max_messages = getattr(plan, "max_monthly_messages", None)
        if max_messages is None:
            features.append("Unbegrenzte Nachrichten/Monat")
        elif isinstance(max_messages, int) and max_messages > 0:
            features.append(f"{max_messages} Nachrichten/Monat")
        ai_tier = (getattr(plan, "ai_tier", "") or "").strip()
        if ai_tier:
            features.append(f"{ai_tier.title()} AI")
        if getattr(plan, "custom_prompts_enabled", False):
            features.append("Eigene Prompts")
        if getattr(plan, "advanced_analytics_enabled", False):
            features.append("Advanced Analytics")
        if getattr(plan, "api_access_enabled", False):
            features.append("API-Zugang")
        return features

    # ── Internal Resolution ─────────────────────────────────────────────

    def _resolve_entitlement(
        self,
        db: Session,
        tenant_id: int,
        feature_key: str,
    ) -> Optional[dict[str, Any]]:
        """
        Resolve the effective entitlement for a tenant/feature.

        Checks plan FeatureSet first, then merges addon FeatureSets.
        """
        sub = gating_repository.get_subscription_by_tenant(db, tenant_id)
        if not sub:
            return None

        # Check subscription status — only active/trialing get full access
        active_statuses = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING}
        status_val = sub.status
        if isinstance(status_val, str):
            try:
                status_val = SubscriptionStatus(status_val)
            except ValueError:
                pass

        if isinstance(status_val, SubscriptionStatus) and status_val not in active_statuses:
            # Past due / canceled — return minimal access
            return {"value_bool": False, "value_limit": 0, "value_tier": "basic"}

        plan = gating_repository.get_plan_by_id(db, sub.plan_id)
        if not plan or not plan.feature_set_id:
            return None

        feature = gating_repository.get_feature_by_key(db, feature_key)
        if not feature:
            return None

        entitlement = gating_repository.get_feature_entitlement(
            db,
            feature_set_id=plan.feature_set_id,
            feature_id=feature.id,
        )

        if not entitlement:
            return None

        result = {
            "value_bool": entitlement.value_bool,
            "value_limit": entitlement.value_limit,
            "value_tier": entitlement.value_tier,
            "hard_limit": entitlement.hard_limit,
            "overage_price_cents": entitlement.overage_price_cents,
        }

        # Check addons for additional entitlements
        if sub.addons:
            for addon in sub.addons:
                if addon.status != "active":
                    continue
                addon_def = gating_repository.get_addon_definition_by_slug(db, addon.addon_slug)
                if not addon_def or not addon_def.feature_set_id:
                    continue

                addon_ent = gating_repository.get_feature_entitlement(
                    db,
                    feature_set_id=addon_def.feature_set_id,
                    feature_id=feature.id,
                )
                if not addon_ent:
                    continue

                # Merge: booleans OR, limits ADD, tiers MAX
                if feature.feature_type == FeatureType.BOOLEAN:
                    result["value_bool"] = result["value_bool"] or addon_ent.value_bool
                elif feature.feature_type == FeatureType.LIMIT:
                    if result["value_limit"] is not None and addon_ent.value_limit is not None:
                        result["value_limit"] += addon_ent.value_limit * addon.quantity
                    elif addon_ent.value_limit is None:
                        result["value_limit"] = None  # Unlimited wins

        return result


# Singleton
gating_service = GatingServiceV2()
