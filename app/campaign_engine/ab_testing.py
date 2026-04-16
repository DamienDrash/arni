"""ARIIA v2.4 – A/B Testing Engine.

Provides statistical analysis and winner determination for A/B test campaigns.
Implements a Z-test for proportions to determine statistical significance.

Workflow:
1. Split recipients into test group (ab_test_percentage) and holdout group
2. Distribute test group evenly across variants
3. After ab_test_duration_hours, evaluate performance
4. Determine winner using Z-test (95% confidence threshold)
5. If ab_test_auto_send, send winner variant to holdout group
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.domains.campaigns.models import Campaign, CampaignRecipient, CampaignVariant

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# STATISTICAL FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def z_test_proportions(p1: float, n1: int, p2: float, n2: int) -> tuple[float, float]:
    """Perform a two-proportion Z-test.

    Returns:
        (z_score, confidence_level) where confidence_level is between 0.0 and 1.0.
    """
    if n1 == 0 or n2 == 0:
        return 0.0, 0.0

    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    if p_pool == 0 or p_pool == 1:
        return 0.0, 0.0

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 0.0

    z = abs(p1 - p2) / se

    # Approximate confidence from Z-score using standard normal CDF approximation
    # Using the Abramowitz & Stegun approximation for the normal CDF
    confidence = _z_to_confidence(z)
    return z, confidence


def _z_to_confidence(z: float) -> float:
    """Convert Z-score to confidence level (two-tailed p-value → confidence)."""
    if z <= 0:
        return 0.0
    # Approximation of the standard normal CDF using the error function
    # P(Z > z) ≈ 0.5 * erfc(z / sqrt(2))
    p_value = 2 * (1 - _normal_cdf(z))
    return max(0.0, min(1.0, 1.0 - p_value))


def _normal_cdf(x: float) -> float:
    """Approximate the standard normal CDF using a polynomial approximation."""
    # Horner form of the Abramowitz & Stegun approximation (formula 26.2.17)
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)


# ═══════════════════════════════════════════════════════════════════════════
# A/B TEST MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

class ABTestingEngine:
    """Manages the A/B testing lifecycle for campaigns."""

    CONFIDENCE_THRESHOLD = 0.95

    def __init__(self, db: Session):
        self.db = db

    def split_recipients(
        self,
        campaign: Campaign,
        all_recipient_ids: list[int],
    ) -> dict[str, list[int]]:
        """Split recipients into test and holdout groups, then distribute test group across variants.

        Returns:
            {
                "test_A": [recipient_ids...],
                "test_B": [recipient_ids...],
                "holdout": [recipient_ids...],
            }
        """
        variants = (
            self.db.query(CampaignVariant)
            .filter(CampaignVariant.campaign_id == campaign.id)
            .order_by(CampaignVariant.variant_name)
            .all()
        )
        if not variants:
            return {"holdout": all_recipient_ids}

        # Shuffle for randomization
        shuffled = list(all_recipient_ids)
        random.shuffle(shuffled)

        test_size = max(1, int(len(shuffled) * campaign.ab_test_percentage / 100))
        test_group = shuffled[:test_size]
        holdout_group = shuffled[test_size:]

        # Distribute test group evenly across variants
        result: dict[str, list[int]] = {"holdout": holdout_group}
        chunk_size = max(1, len(test_group) // len(variants))

        for i, variant in enumerate(variants):
            start = i * chunk_size
            end = start + chunk_size if i < len(variants) - 1 else len(test_group)
            result[f"test_{variant.variant_name}"] = test_group[start:end]

            # Update variant percentage based on actual split
            variant.percentage = int(len(test_group[start:end]) / max(1, len(test_group)) * 100)

        self.db.commit()
        logger.info(
            "ab_test_split",
            campaign_id=campaign.id,
            total=len(all_recipient_ids),
            test_size=test_size,
            holdout_size=len(holdout_group),
            variants=len(variants),
        )
        return result

    def evaluate_test(self, campaign: Campaign) -> Optional[CampaignVariant]:
        """Evaluate A/B test results and determine the winner.

        Returns:
            The winning CampaignVariant, or None if no winner can be determined.
        """
        variants = (
            self.db.query(CampaignVariant)
            .filter(CampaignVariant.campaign_id == campaign.id)
            .order_by(CampaignVariant.variant_name)
            .all()
        )
        if len(variants) < 2:
            logger.warning("ab_test_evaluate_skip", campaign_id=campaign.id, reason="less_than_2_variants")
            return None

        metric = campaign.ab_test_metric or "open_rate"

        # Calculate rates for each variant
        variant_stats = []
        for v in variants:
            sent = v.stats_sent or 0
            if metric == "open_rate":
                successes = v.stats_opened or 0
            elif metric == "click_rate":
                successes = v.stats_clicked or 0
            else:
                successes = v.stats_opened or 0

            rate = successes / sent if sent > 0 else 0.0
            variant_stats.append({
                "variant": v,
                "sent": sent,
                "successes": successes,
                "rate": rate,
            })

        # Sort by rate descending
        variant_stats.sort(key=lambda x: x["rate"], reverse=True)
        best = variant_stats[0]
        second = variant_stats[1]

        # Calculate statistical significance between top 2
        z_score, confidence = z_test_proportions(
            best["rate"], best["sent"],
            second["rate"], second["sent"],
        )

        logger.info(
            "ab_test_evaluate",
            campaign_id=campaign.id,
            metric=metric,
            best_variant=best["variant"].variant_name,
            best_rate=round(best["rate"], 4),
            second_variant=second["variant"].variant_name,
            second_rate=round(second["rate"], 4),
            z_score=round(z_score, 3),
            confidence=round(confidence, 4),
        )

        # Mark winner
        winner = best["variant"]
        now = datetime.now(timezone.utc)

        for v in variants:
            if v.id == winner.id:
                v.is_winner = True
                v.winner_selected_at = now
                v.winner_metric = metric
                v.confidence_level = round(confidence, 4)
            else:
                v.is_winner = False
                v.confidence_level = round(confidence, 4)

        campaign.ab_winner_variant = winner.variant_name

        if confidence < self.CONFIDENCE_THRESHOLD:
            logger.warning(
                "ab_test_low_confidence",
                campaign_id=campaign.id,
                confidence=round(confidence, 4),
                threshold=self.CONFIDENCE_THRESHOLD,
                note="Winner selected by absolute rate, but confidence is below threshold.",
            )

        self.db.commit()
        return winner

    def get_winner_content(self, campaign: Campaign) -> Optional[dict]:
        """Get the content of the winning variant for sending to the holdout group.

        Returns:
            {"subject": ..., "body": ..., "html": ...} or None
        """
        winner = (
            self.db.query(CampaignVariant)
            .filter(
                CampaignVariant.campaign_id == campaign.id,
                CampaignVariant.is_winner == True,
            )
            .first()
        )
        if not winner:
            return None

        return {
            "subject": winner.content_subject or campaign.content_subject,
            "body": winner.content_body or campaign.content_body,
            "html": winner.content_html or campaign.content_html,
            "variant_name": winner.variant_name,
        }

    def get_test_results_summary(self, campaign: Campaign) -> dict:
        """Get a summary of A/B test results for display in the UI."""
        variants = (
            self.db.query(CampaignVariant)
            .filter(CampaignVariant.campaign_id == campaign.id)
            .order_by(CampaignVariant.variant_name)
            .all()
        )

        metric = campaign.ab_test_metric or "open_rate"
        results = []
        for v in variants:
            sent = v.stats_sent or 0
            opened = v.stats_opened or 0
            clicked = v.stats_clicked or 0
            open_rate = opened / sent if sent > 0 else 0.0
            click_rate = clicked / sent if sent > 0 else 0.0

            results.append({
                "variant_name": v.variant_name,
                "subject": v.content_subject,
                "sent": sent,
                "opened": opened,
                "clicked": clicked,
                "open_rate": round(open_rate, 4),
                "click_rate": round(click_rate, 4),
                "is_winner": v.is_winner,
                "confidence_level": v.confidence_level,
            })

        return {
            "campaign_id": campaign.id,
            "metric": metric,
            "test_percentage": campaign.ab_test_percentage,
            "duration_hours": campaign.ab_test_duration_hours,
            "auto_send": campaign.ab_test_auto_send,
            "winner_variant": campaign.ab_winner_variant,
            "variants": results,
        }
