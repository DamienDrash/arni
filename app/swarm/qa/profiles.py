"""ARIIA Swarm v3 — QA Profiles and Criteria.

Defines the quality criteria that the QAJudge evaluates against,
and profiles that bundle criteria sets per agent type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QACriterion(str, Enum):
    """Individual quality criteria checked by the QAJudge."""

    DISCLAIMER_PRESENT = "disclaimer_present"
    NO_INTERNAL_TOOL_LEAK = "no_internal_tool_leak"
    CONFIRMATION_FOR_DESTRUCTIVE = "confirmation_for_destructive"
    LANGUAGE_MATCH = "language_match"
    RESPONSE_NOT_EMPTY = "response_not_empty"
    APPROPRIATE_LENGTH = "appropriate_length"
    NO_HALLUCINATED_PRICES = "no_hallucinated_prices"


@dataclass(frozen=True)
class QAProfile:
    """A bundle of QA criteria and settings for an agent type."""

    name: str
    criteria: frozenset[QACriterion]
    max_revision_attempts: int = 2
    escalate_on_fail: bool = False
    run_llm_check: bool = False


# ── Standard Profiles ─────────────────────────────────────────────────────────

QA_PROFILES: dict[str, QAProfile] = {
    "strict": QAProfile(
        name="strict",
        criteria=frozenset(QACriterion),
        max_revision_attempts=2,
        escalate_on_fail=True,
        run_llm_check=True,
    ),
    "standard": QAProfile(
        name="standard",
        criteria=frozenset({
            QACriterion.RESPONSE_NOT_EMPTY,
            QACriterion.NO_INTERNAL_TOOL_LEAK,
            QACriterion.LANGUAGE_MATCH,
            QACriterion.APPROPRIATE_LENGTH,
        }),
        max_revision_attempts=1,
        escalate_on_fail=False,
        run_llm_check=False,
    ),
    "off": QAProfile(
        name="off",
        criteria=frozenset(),
        max_revision_attempts=0,
        escalate_on_fail=False,
        run_llm_check=False,
    ),
}

# ── Agent → QA Profile Mapping ───────────────────────────────────────────────

AGENT_QA_PROFILES: dict[str, str] = {
    "ops": "standard",
    "sales": "standard",
    "medic": "strict",       # Health advice needs disclaimers
    "vision": "standard",
    "persona": "standard",
    "knowledge": "off",
    "campaign": "standard",
    "media": "standard",
}
