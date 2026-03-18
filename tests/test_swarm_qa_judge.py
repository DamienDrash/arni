"""ARIIA Swarm v3 — Unit Tests for QAJudge.

Tests all deterministic QA criteria, profile handling,
escalation behavior, and edge cases.
"""

import pytest

from app.swarm.contracts import AgentResult, AgentTask, TenantContext
from app.swarm.qa.judge import QAJudge, QAStatus, QAVerdict
from app.swarm.qa.profiles import QACriterion, QAProfile, QA_PROFILES


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_context(tenant_id: int = 1, settings: dict = None) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        tenant_slug="test-studio",
        plan_slug="pro",
        active_integrations=frozenset(),
        settings=settings or {},
        member_id="member-001",
    )


def _make_task(
    message: str = "Hallo, ich habe eine Frage",
    agent_id: str = "ops",
    tenant_id: int = 1,
    settings: dict = None,
) -> AgentTask:
    return AgentTask(
        task_id="task-001",
        agent_id=agent_id,
        original_message=message,
        intent_payload={},
        tenant_context=_make_context(tenant_id=tenant_id, settings=settings),
    )


def _make_result(
    agent_id: str = "ops",
    content: str = "Hier ist deine Antwort zu deiner Frage.",
    requires_confirmation: bool = False,
    confirmation_prompt: str | None = None,
    confirmation_action: str | None = None,
) -> AgentResult:
    return AgentResult(
        agent_id=agent_id,
        content=content,
        confidence=0.9,
        requires_confirmation=requires_confirmation,
        confirmation_prompt=confirmation_prompt,
        confirmation_action=confirmation_action,
    )


# ── Disclaimer Tests (Medic) ────────────────────────────────────────────────


class TestDisclaimerPresent:
    def test_medic_without_disclaimer_revise(self) -> None:
        """Medic response without health disclaimer -> REVISE."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.DISCLAIMER_PRESENT}),
        )
        result = _make_result(agent_id="medic", content="Mach einfach Dehnübungen für dein Knie, das wird schon.")
        task = _make_task(message="Mein Knie tut weh", agent_id="medic")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE
        assert QACriterion.DISCLAIMER_PRESENT in verdict.failed_criteria

    def test_medic_with_disclaimer_pass(self) -> None:
        """Medic response with health disclaimer -> PASS."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.DISCLAIMER_PRESENT}),
        )
        result = _make_result(
            agent_id="medic",
            content="Dehnübungen können helfen. Ich bin kein Arzt — bitte konsultiere einen Arzt. Im Notfall ruf 112 an.",
        )
        task = _make_task(message="Mein Knie tut weh", agent_id="medic")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS

    def test_disclaimer_not_required_for_non_medic(self) -> None:
        """Non-medic agents always pass the disclaimer check."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.DISCLAIMER_PRESENT}),
        )
        result = _make_result(agent_id="ops", content="Dein Kurs ist um 10:00 Uhr.")
        task = _make_task(agent_id="ops")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS


# ── Internal Tool Leak Tests ────────────────────────────────────────────────


class TestNoInternalToolLeak:
    def test_tool_leak_revise(self) -> None:
        """Response containing 'TOOL: get_schedule()' -> REVISE."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.NO_INTERNAL_TOOL_LEAK}),
        )
        result = _make_result(content="TOOL: get_schedule() returned empty")
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE
        assert QACriterion.NO_INTERNAL_TOOL_LEAK in verdict.failed_criteria

    def test_tool_call_id_leak(self) -> None:
        """Response containing 'tool_call_id' -> REVISE."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.NO_INTERNAL_TOOL_LEAK}),
        )
        result = _make_result(content='Result from tool_call_id abc123: data')
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE

    def test_clean_response_passes(self) -> None:
        """Normal user-facing response -> PASS."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.NO_INTERNAL_TOOL_LEAK}),
        )
        result = _make_result(content="Dein nächster Kurs ist morgen um 10 Uhr.")
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS


# ── Confirmation for Destructive Actions Tests ──────────────────────────────


class TestConfirmationForDestructive:
    def test_destructive_without_confirmation_revise(self) -> None:
        """Destructive action (kündigen) without requires_confirmation -> REVISE."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.CONFIRMATION_FOR_DESTRUCTIVE}),
        )
        result = _make_result(content="Dein Vertrag wird gekündigt.", requires_confirmation=False)
        task = _make_task(message="Ich will meinen Vertrag kündigen")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE
        assert QACriterion.CONFIRMATION_FOR_DESTRUCTIVE in verdict.failed_criteria

    def test_destructive_with_confirmation_pass(self) -> None:
        """Destructive action with requires_confirmation=True -> PASS."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.CONFIRMATION_FOR_DESTRUCTIVE}),
        )
        result = _make_result(
            content="Möchtest du wirklich kündigen?",
            requires_confirmation=True,
        )
        task = _make_task(message="Ich will meinen Vertrag kündigen")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS

    def test_non_destructive_without_confirmation_pass(self) -> None:
        """Non-destructive action without confirmation -> PASS."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.CONFIRMATION_FOR_DESTRUCTIVE}),
        )
        result = _make_result(content="Dein Kurs ist um 10 Uhr.", requires_confirmation=False)
        task = _make_task(message="Wann ist mein nächster Kurs?")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS

    @pytest.mark.parametrize("keyword", [
        "löschen", "stornieren", "kündigen", "absagen", "entfernen",
        "delete", "cancel", "remove",
    ])
    def test_all_destructive_keywords_detected(self, keyword: str) -> None:
        """All destructive keywords trigger the confirmation check."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.CONFIRMATION_FOR_DESTRUCTIVE}),
        )
        result = _make_result(requires_confirmation=False)
        task = _make_task(message=f"Bitte {keyword} meinen Termin")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE


# ── Profile "off" Tests ──────────────────────────────────────────────────────


class TestProfileOff:
    def test_qa_profile_off_always_passes(self) -> None:
        """Profile 'off' (no criteria) -> always PASS."""
        judge = QAJudge()
        off_profile = QA_PROFILES["off"]
        # Even with a terrible result, should pass
        result = _make_result(agent_id="medic", content="")
        task = _make_task(agent_id="medic")
        verdict = judge.evaluate(result, task, off_profile)
        assert verdict.status == QAStatus.PASS

    def test_empty_criteria_set_passes(self) -> None:
        """Empty criteria set -> PASS."""
        judge = QAJudge()
        profile = QAProfile(name="empty", criteria=frozenset())
        result = _make_result(content="anything")
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS


# ── Strict Escalation Tests ─────────────────────────────────────────────────


class TestStrictEscalation:
    def test_strict_escalate_on_fail(self) -> None:
        """Strict profile with escalate_on_fail=True -> ESCALATE on failure."""
        judge = QAJudge()
        profile = QAProfile(
            name="strict",
            criteria=frozenset({QACriterion.DISCLAIMER_PRESENT}),
            escalate_on_fail=True,
        )
        result = _make_result(agent_id="medic", content="Mach einfach Dehnübungen, das hilft bestimmt.")
        task = _make_task(agent_id="medic")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.ESCALATE
        assert QACriterion.DISCLAIMER_PRESENT in verdict.failed_criteria

    def test_strict_pass_when_criteria_met(self) -> None:
        """Strict profile passes when all criteria are met."""
        judge = QAJudge()
        profile = QAProfile(
            name="strict",
            criteria=frozenset({QACriterion.DISCLAIMER_PRESENT}),
            escalate_on_fail=True,
        )
        result = _make_result(
            agent_id="medic",
            content="Konsultiere bitte einen Arzt für medizinische Beratung.",
        )
        task = _make_task(agent_id="medic")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS

    def test_non_strict_revise_instead_of_escalate(self) -> None:
        """Non-strict profile -> REVISE instead of ESCALATE."""
        judge = QAJudge()
        profile = QAProfile(
            name="standard",
            criteria=frozenset({QACriterion.DISCLAIMER_PRESENT}),
            escalate_on_fail=False,
        )
        result = _make_result(agent_id="medic", content="Mach einfach Dehnübungen, das hilft bestimmt.")
        task = _make_task(agent_id="medic")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE


# ── Max Revision Attempts Tests ──────────────────────────────────────────────


class TestMaxRevisionAttempts:
    def test_max_revision_attempts_on_profiles(self) -> None:
        """Standard profiles have expected max_revision_attempts."""
        assert QA_PROFILES["strict"].max_revision_attempts == 2
        assert QA_PROFILES["standard"].max_revision_attempts == 1
        assert QA_PROFILES["off"].max_revision_attempts == 0

    def test_verdict_provides_feedback_for_revision(self) -> None:
        """REVISE verdict includes feedback describing what failed."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.RESPONSE_NOT_EMPTY}),
        )
        result = _make_result(content="")
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE
        assert verdict.feedback  # Non-empty feedback
        assert "empty" in verdict.feedback.lower() or "response_not_empty" in verdict.feedback.lower()


# ── Deterministic-only Tests ─────────────────────────────────────────────────


class TestDeterministicChecks:
    def test_all_criteria_deterministic_no_llm(self) -> None:
        """Deterministic checks produce verdict without LLM calls."""
        judge = QAJudge()
        profile = QAProfile(
            name="all_deterministic",
            criteria=frozenset(QACriterion),
        )
        result = _make_result(
            agent_id="ops",
            content="Hier ist die Antwort zu deiner Buchung. Der Kurs ist morgen um 10 Uhr verfügbar.",
            requires_confirmation=False,
        )
        task = _make_task(message="Wann ist mein nächster Kurs?")
        # This should work without any LLM call
        verdict = judge.evaluate(result, task, profile)
        assert isinstance(verdict, QAVerdict)
        assert verdict.status in {QAStatus.PASS, QAStatus.REVISE}

    def test_response_not_empty_pass(self) -> None:
        """Non-empty response passes RESPONSE_NOT_EMPTY."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.RESPONSE_NOT_EMPTY}),
        )
        result = _make_result(content="Some content")
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS

    def test_response_empty_revise(self) -> None:
        """Empty response fails RESPONSE_NOT_EMPTY."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.RESPONSE_NOT_EMPTY}),
        )
        result = _make_result(content="")
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE

    def test_appropriate_length_pass(self) -> None:
        """Response of appropriate length passes."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.APPROPRIATE_LENGTH}),
        )
        result = _make_result(content="Dies ist eine Antwort mittlerer Länge die völlig in Ordnung ist.")
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS

    def test_too_short_response_revise(self) -> None:
        """Response < 10 chars fails APPROPRIATE_LENGTH."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.APPROPRIATE_LENGTH}),
        )
        result = _make_result(content="Hi")
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE

    def test_too_long_response_revise(self) -> None:
        """Response > 3000 chars fails APPROPRIATE_LENGTH."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.APPROPRIATE_LENGTH}),
        )
        result = _make_result(content="x" * 3001)
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE

    def test_language_match_german_pass(self) -> None:
        """German question + German answer passes LANGUAGE_MATCH."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.LANGUAGE_MATCH}),
        )
        result = _make_result(content="Dein nächster Kurs ist morgen um 10 Uhr.")
        task = _make_task(message="Ich habe eine Frage")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS

    def test_no_hallucinated_prices_without_config(self) -> None:
        """Price in response without sales_prices_text -> REVISE."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.NO_HALLUCINATED_PRICES}),
        )
        result = _make_result(content="Die Mitgliedschaft kostet 29,99 €.")
        task = _make_task(settings={})
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE

    def test_no_hallucinated_prices_with_config(self) -> None:
        """Price in response with sales_prices_text configured -> PASS."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.NO_HALLUCINATED_PRICES}),
        )
        result = _make_result(content="Die Mitgliedschaft kostet 29,99 €.")
        task = _make_task(settings={"sales_prices_text": "29,99€ Basis"})
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS


# ── Multiple Criteria Tests ──────────────────────────────────────────────────


class TestMultipleCriteria:
    def test_multiple_failures_reported(self) -> None:
        """Multiple failing criteria are all reported."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({
                QACriterion.DISCLAIMER_PRESENT,
                QACriterion.NO_INTERNAL_TOOL_LEAK,
            }),
        )
        result = _make_result(
            agent_id="medic",
            content="TOOL: get_health_data() zeigt keine Probleme bei dir.",
        )
        task = _make_task(agent_id="medic")
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE
        assert QACriterion.DISCLAIMER_PRESENT in verdict.failed_criteria
        assert QACriterion.NO_INTERNAL_TOOL_LEAK in verdict.failed_criteria

    def test_all_pass_when_clean(self) -> None:
        """All criteria pass with a well-formed response."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({
                QACriterion.RESPONSE_NOT_EMPTY,
                QACriterion.APPROPRIATE_LENGTH,
                QACriterion.NO_INTERNAL_TOOL_LEAK,
            }),
        )
        result = _make_result(content="Dein Kurs ist morgen um 10 Uhr im Hauptstudio.")
        task = _make_task()
        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS


# ── Standard Profiles Validation ─────────────────────────────────────────────


class TestStandardProfiles:
    def test_strict_profile_exists(self) -> None:
        assert "strict" in QA_PROFILES
        assert QA_PROFILES["strict"].escalate_on_fail is True
        assert QA_PROFILES["strict"].escalate_on_fail is True

    def test_standard_profile_exists(self) -> None:
        assert "standard" in QA_PROFILES
        assert QA_PROFILES["standard"].escalate_on_fail is False

    def test_off_profile_exists(self) -> None:
        assert "off" in QA_PROFILES
        assert len(QA_PROFILES["off"].criteria) == 0
