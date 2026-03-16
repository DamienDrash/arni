"""ARIIA Swarm v3 — QAJudge.

Evaluates AgentResult quality against a QAProfile's criteria.
Two-phase evaluation:
  Phase 1: Deterministic rule checks (no LLM)
  Phase 2: Optional LLM-based quality check (only if profile.run_llm_check)
"""

from __future__ import annotations

import re
import structlog
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.swarm.contracts import AgentResult, AgentTask
from app.swarm.qa.profiles import QACriterion, QAProfile

logger = structlog.get_logger()


class QAStatus(str, Enum):
    """Verdict status from the QAJudge."""
    PASS = "pass"
    REVISE = "revise"
    ESCALATE = "escalate"


@dataclass
class CheckResult:
    """Result of a single criterion check."""
    criterion: QACriterion
    passed: bool
    reason: str = ""


@dataclass
class QAVerdict:
    """Final verdict from the QAJudge."""
    status: QAStatus
    feedback: str = ""
    reason: str = ""
    failed_criteria: list[QACriterion] | None = None


# ── Internal tool/system patterns that should never leak to users ─────────

_INTERNAL_LEAK_PATTERNS = [
    r"TOOL\s*:",
    r"tool_call_id",
    r"function_call",
    r"\{\"role\":\s*\"tool\"",
    r"OBSERVATION:",
    r"AgentResult\(",
    r"ToolResult\(",
    r"```json\s*\{.*\"tool_calls\"",
]

# ── Destructive action keywords ──────────────────────────────────────────────

_DESTRUCTIVE_KEYWORDS = [
    "löschen", "loeschen", "stornieren", "storno", "kündigen", "kuendigen",
    "absagen", "entfernen", "delete", "cancel", "remove",
]

# ── Health disclaimer patterns ───────────────────────────────────────────────

_DISCLAIMER_PATTERNS = [
    r"112",
    r"arzt",
    r"ärzt",
    r"aerzt",
    r"notarzt",
    r"medizinisch",
    r"haftung",
    r"keine\s+(medizinische|ärztliche)",
    r"ersetzt\s+keine",
    r"disclaimer",
]


class QAJudge:
    """Evaluates AgentResult quality against a QAProfile."""

    def evaluate(
        self,
        result: AgentResult,
        task: AgentTask,
        profile: QAProfile,
    ) -> QAVerdict:
        """Evaluate the result against the profile's criteria.

        Phase 1: Deterministic checks (always runs).
        Phase 2: LLM check (only if profile.run_llm_check and Phase 1 passed).

        Args:
            result: The AgentResult to evaluate.
            task: The original task for context.
            profile: The QAProfile with criteria to check.

        Returns:
            QAVerdict with pass/revise/escalate status.
        """
        if not profile.criteria:
            return QAVerdict(status=QAStatus.PASS)

        # Phase 1: Deterministic checks
        failed: list[CheckResult] = []
        for criterion in profile.criteria:
            check = self._run_deterministic_check(criterion, result, task)
            if not check.passed:
                failed.append(check)

        if failed:
            failed_criteria = [f.criterion for f in failed]
            feedback = "; ".join(
                f"{f.criterion.value}: {f.reason}" for f in failed
            )

            if profile.escalate_on_fail:
                return QAVerdict(
                    status=QAStatus.ESCALATE,
                    feedback=feedback,
                    reason="Deterministic QA check failed with escalation flag",
                    failed_criteria=failed_criteria,
                )

            return QAVerdict(
                status=QAStatus.REVISE,
                feedback=feedback,
                reason="Deterministic QA check failed",
                failed_criteria=failed_criteria,
            )

        # Phase 2: Optional LLM check
        if profile.run_llm_check:
            llm_verdict = self._run_llm_check(result, task, profile)
            if llm_verdict is not None:
                return llm_verdict

        return QAVerdict(status=QAStatus.PASS)

    def _run_deterministic_check(
        self,
        criterion: QACriterion,
        result: AgentResult,
        task: AgentTask,
    ) -> CheckResult:
        """Run a single deterministic criterion check.

        Returns:
            CheckResult with passed=True/False.
        """
        content = result.content or ""
        content_lower = content.lower()

        if criterion == QACriterion.RESPONSE_NOT_EMPTY:
            passed = len(content.strip()) > 0
            return CheckResult(
                criterion=criterion,
                passed=passed,
                reason="" if passed else "Response is empty",
            )

        if criterion == QACriterion.APPROPRIATE_LENGTH:
            # Too short (< 10 chars) or too long (> 3000 chars)
            length = len(content.strip())
            passed = 10 <= length <= 3000
            reason = ""
            if length < 10:
                reason = f"Response too short ({length} chars)"
            elif length > 3000:
                reason = f"Response too long ({length} chars)"
            return CheckResult(criterion=criterion, passed=passed, reason=reason)

        if criterion == QACriterion.NO_INTERNAL_TOOL_LEAK:
            for pattern in _INTERNAL_LEAK_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    return CheckResult(
                        criterion=criterion,
                        passed=False,
                        reason=f"Internal tool pattern leaked: {pattern}",
                    )
            return CheckResult(criterion=criterion, passed=True)

        if criterion == QACriterion.DISCLAIMER_PRESENT:
            # Only required for medic agent
            if result.agent_id != "medic":
                return CheckResult(criterion=criterion, passed=True)
            has_disclaimer = any(
                re.search(p, content_lower) for p in _DISCLAIMER_PATTERNS
            )
            return CheckResult(
                criterion=criterion,
                passed=has_disclaimer,
                reason="" if has_disclaimer else "Health disclaimer missing (must reference doctor/112)",
            )

        if criterion == QACriterion.CONFIRMATION_FOR_DESTRUCTIVE:
            # If the original message contains destructive keywords,
            # the result should have requires_confirmation=True
            msg_lower = task.original_message.lower()
            is_destructive = any(kw in msg_lower for kw in _DESTRUCTIVE_KEYWORDS)
            if is_destructive and not result.requires_confirmation:
                return CheckResult(
                    criterion=criterion,
                    passed=False,
                    reason="Destructive action detected but no confirmation requested",
                )
            return CheckResult(criterion=criterion, passed=True)

        if criterion == QACriterion.LANGUAGE_MATCH:
            # Basic heuristic: if the user wrote in German, response should be German
            # Check for common German articles/words
            msg = task.original_message.lower()
            is_german = any(w in msg.split() for w in ["ich", "ein", "der", "die", "das", "und", "ist", "hallo", "bitte"])
            if is_german:
                has_german = any(w in content_lower.split() for w in ["ich", "ein", "der", "die", "das", "und", "ist", "du", "dein"])
                return CheckResult(
                    criterion=criterion,
                    passed=has_german,
                    reason="" if has_german else "Response language does not match user language (expected German)",
                )
            return CheckResult(criterion=criterion, passed=True)

        if criterion == QACriterion.NO_HALLUCINATED_PRICES:
            # Check if response contains price-like patterns that aren't
            # from the tenant's official price list
            price_patterns = re.findall(r"\d+[.,]\d{2}\s*€|€\s*\d+[.,]\d{2}|\d+\s*Euro", content)
            if price_patterns:
                # If there are prices, check if the tenant has a price list
                prices_text = task.tenant_context.settings.get("sales_prices_text", "")
                if not prices_text:
                    return CheckResult(
                        criterion=criterion,
                        passed=False,
                        reason="Prices mentioned but no official price list configured",
                    )
            return CheckResult(criterion=criterion, passed=True)

        # Unknown criterion: pass by default
        logger.warning("qa_judge.unknown_criterion", criterion=criterion.value)
        return CheckResult(criterion=criterion, passed=True)

    def _run_llm_check(
        self,
        result: AgentResult,
        task: AgentTask,
        profile: QAProfile,
    ) -> QAVerdict | None:
        """Optional LLM-based quality check.

        Returns QAVerdict if LLM finds issues, None if no issues or LLM unavailable.
        Currently a stub — will be wired to LLM in a later task.
        """
        # TODO: Implement LLM-based quality check in a follow-up task.
        # This would send the result + task to an LLM with a QA prompt
        # and parse the response for PASS/REVISE/ESCALATE.
        return None
