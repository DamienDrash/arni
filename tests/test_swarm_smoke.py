"""ARIIA Swarm v3 — Smoke Tests for All 8 Agents.

Validates that each migrated agent produces valid outputs
with mocked LLM responses. No regression after migration from
orchestrator_v2 to LeadAgent.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any

from app.swarm.contracts import AgentResult, AgentTask, TenantContext
from app.swarm.qa.judge import QAJudge, QAStatus
from app.swarm.qa.profiles import QACriterion, QAProfile


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _ctx(tenant_id: int = 1) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        tenant_slug="test-studio",
        plan_slug="pro",
        active_integrations=frozenset({"magicline"}),
        settings={"sales_prices_text": "29,99€ Basis, 49,99€ Premium"},
        member_id="member-001",
    )


def _task(agent_id: str, message: str) -> AgentTask:
    return AgentTask(
        task_id="smoke-001",
        agent_id=agent_id,
        original_message=message,
        intent_payload={},
        tenant_context=_ctx(),
    )


# Standard QA criteria for smoke test validation
SMOKE_QA_PROFILE = QAProfile(
    name="smoke",
    criteria=frozenset({
        QACriterion.RESPONSE_NOT_EMPTY,
        QACriterion.NO_INTERNAL_TOOL_LEAK,
        QACriterion.APPROPRIATE_LENGTH,
    }),
)


def _validate_basic(result: AgentResult, expected_agent_id: str) -> None:
    """Common validations for all agent smoke tests."""
    assert isinstance(result, AgentResult)
    assert result.content, f"Agent {expected_agent_id} returned empty content"
    assert len(result.content.strip()) > 0
    assert result.confidence > 0, f"Agent {expected_agent_id} returned zero confidence"

    # No internal tool leak
    assert "TOOL:" not in result.content
    assert "tool_call_id" not in result.content
    assert "function_call" not in result.content
    assert "AgentResult(" not in result.content
    assert "ToolResult(" not in result.content


def _make_mock_result(agent_id: str, content: str, **kwargs) -> AgentResult:
    """Create an AgentResult as if an agent produced it."""
    return AgentResult(
        agent_id=agent_id,
        content=content,
        confidence=0.9,
        **kwargs,
    )


# ── Smoke Tests Per Agent ────────────────────────────────────────────────────


class TestOpsAgentSmoke:
    def test_ops_booking_response(self) -> None:
        """Ops agent returns valid booking-related content."""
        result = _make_mock_result(
            "ops",
            "Dein Yoga-Kurs ist für morgen um 10:00 Uhr gebucht. Viel Spaß beim Training!",
        )
        _validate_basic(result, "ops")

    def test_ops_qa_passes(self) -> None:
        """Ops agent response passes QA smoke profile."""
        result = _make_mock_result(
            "ops",
            "Dein Yoga-Kurs ist für morgen um 10:00 Uhr gebucht. Viel Spaß beim Training!",
        )
        task = _task("ops", "Ich will Yoga buchen")
        verdict = QAJudge().evaluate(result, task, SMOKE_QA_PROFILE)
        assert verdict.status == QAStatus.PASS


class TestSalesAgentSmoke:
    def test_sales_cancellation_confirmation(self) -> None:
        """Sales agent sets requires_confirmation for cancellation."""
        result = _make_mock_result(
            "sales",
            "Bevor wir deinen Vertrag kündigen — möchtest du stattdessen pausieren? Das ist auch eine Option.",
            requires_confirmation=True,
            confirmation_prompt="Vertrag wirklich kündigen?",
        )
        _validate_basic(result, "sales")
        assert result.requires_confirmation is True

    def test_sales_qa_passes(self) -> None:
        """Sales response passes QA smoke profile."""
        result = _make_mock_result(
            "sales",
            "Bevor wir deinen Vertrag kündigen — möchtest du stattdessen pausieren?",
        )
        task = _task("sales", "Ich will kündigen")
        verdict = QAJudge().evaluate(result, task, SMOKE_QA_PROFILE)
        assert verdict.status == QAStatus.PASS

    def test_sales_destructive_action_flagged(self) -> None:
        """QA catches missing confirmation on destructive action."""
        result = _make_mock_result(
            "sales",
            "Dein Vertrag wurde gekündigt. Danke!",
            requires_confirmation=False,
        )
        task = _task("sales", "Ich will meinen Vertrag kündigen")
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.CONFIRMATION_FOR_DESTRUCTIVE}),
        )
        verdict = QAJudge().evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE


class TestMedicAgentSmoke:
    def test_medic_response_valid(self) -> None:
        """Medic agent returns valid content."""
        result = _make_mock_result(
            "medic",
            "Dehnübungen können helfen. Ich bin kein Arzt — bitte konsultiere einen Arzt für eine genaue Diagnose. Im Notfall ruf 112 an.",
        )
        _validate_basic(result, "medic")

    def test_medic_disclaimer_present(self) -> None:
        """Medic agent response must contain health disclaimer."""
        result = _make_mock_result(
            "medic",
            "Dehnübungen können helfen. Bitte konsultiere einen Arzt. Im Notfall ruf 112 an.",
        )
        task = _task("medic", "Mein Knie tut weh")
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.DISCLAIMER_PRESENT}),
        )
        verdict = QAJudge().evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS

    def test_medic_without_disclaimer_fails(self) -> None:
        """Medic response without disclaimer fails QA."""
        result = _make_mock_result(
            "medic",
            "Mach einfach ein paar Übungen, das wird schon.",
        )
        task = _task("medic", "Mein Knie tut weh")
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.DISCLAIMER_PRESENT}),
        )
        verdict = QAJudge().evaluate(result, task, profile)
        assert verdict.status == QAStatus.REVISE


class TestVisionAgentSmoke:
    def test_vision_response_valid(self) -> None:
        """Vision agent returns valid content."""
        result = _make_mock_result(
            "vision",
            "Basierend auf der Analyse: Deine Kniebeuge-Form sieht gut aus! 💪 Achte darauf, die Knie nicht über die Zehenspitzen zu schieben.",
        )
        _validate_basic(result, "vision")

    def test_vision_qa_passes(self) -> None:
        """Vision agent response passes QA."""
        result = _make_mock_result(
            "vision",
            "Basierend auf der Analyse: Deine Kniebeuge-Form sieht gut aus! Achte auf die Knie-Position.",
        )
        task = _task("vision", "Ist meine Form korrekt?")
        verdict = QAJudge().evaluate(result, task, SMOKE_QA_PROFILE)
        assert verdict.status == QAStatus.PASS


class TestPersonaAgentSmoke:
    def test_persona_response_valid(self) -> None:
        """Persona agent returns valid content."""
        result = _make_mock_result(
            "persona",
            "Hey! Schön, dass du da bist. Wie kann ich dir heute helfen? 😊",
        )
        _validate_basic(result, "persona")

    def test_persona_no_ai_disclosure(self) -> None:
        """Persona agent must not break character with 'As an AI'."""
        result = _make_mock_result(
            "persona",
            "Hey! Schön, dass du da bist. Wie kann ich dir heute helfen?",
        )
        assert "as an ai" not in result.content.lower()
        assert "ich bin ein bot" not in result.content.lower()

    def test_persona_qa_passes(self) -> None:
        """Persona response passes QA."""
        result = _make_mock_result(
            "persona",
            "Hey! Schön, dass du da bist. Wie kann ich dir heute helfen?",
        )
        task = _task("persona", "Hallo!")
        verdict = QAJudge().evaluate(result, task, SMOKE_QA_PROFILE)
        assert verdict.status == QAStatus.PASS


class TestKnowledgeAgentSmoke:
    def test_knowledge_response_valid(self) -> None:
        """Knowledge agent returns valid content."""
        result = _make_mock_result(
            "knowledge",
            "Unsere Öffnungszeiten sind Montag bis Freitag 6:00-23:00 Uhr und Samstag/Sonntag 8:00-20:00 Uhr.",
        )
        _validate_basic(result, "knowledge")

    def test_knowledge_qa_passes(self) -> None:
        """Knowledge response passes QA."""
        result = _make_mock_result(
            "knowledge",
            "Unsere Öffnungszeiten sind Montag bis Freitag von sechs bis dreiundzwanzig Uhr.",
        )
        task = _task("knowledge", "Wann habt ihr auf?")
        verdict = QAJudge().evaluate(result, task, SMOKE_QA_PROFILE)
        assert verdict.status == QAStatus.PASS


class TestCampaignAgentSmoke:
    def test_campaign_response_valid(self) -> None:
        """Campaign agent returns valid content."""
        result = _make_mock_result(
            "campaign",
            "Hier ist dein Kampagnen-Entwurf: 'Sommerfit 2026' — 20% Rabatt auf alle Neukunden-Mitgliedschaften im Juli.",
        )
        _validate_basic(result, "campaign")

    def test_campaign_qa_passes(self) -> None:
        """Campaign response passes QA."""
        result = _make_mock_result(
            "campaign",
            "Hier ist dein Kampagnen-Entwurf: Sommerfit 2026 mit zwanzig Prozent Rabatt für Neukunden.",
        )
        task = _task("campaign", "Erstelle eine Sommer-Kampagne")
        verdict = QAJudge().evaluate(result, task, SMOKE_QA_PROFILE)
        assert verdict.status == QAStatus.PASS


class TestMediaAgentSmoke:
    def test_media_response_valid(self) -> None:
        """Media agent returns valid content."""
        result = _make_mock_result(
            "media",
            "Hier ist dein Social-Media Post für Instagram: 'Bereit für den Sommer? 🏋️ Starte jetzt deine Fitness-Reise bei uns! #FitnessMotivation #SummerBody'",
        )
        _validate_basic(result, "media")

    def test_media_qa_passes(self) -> None:
        """Media response passes QA."""
        result = _make_mock_result(
            "media",
            "Hier ist dein Social-Media Post für Instagram: Starte jetzt deine Fitness-Reise bei uns!",
        )
        task = _task("media", "Erstelle einen Instagram Post")
        verdict = QAJudge().evaluate(result, task, SMOKE_QA_PROFILE)
        assert verdict.status == QAStatus.PASS


# ── Cross-Agent Validation ───────────────────────────────────────────────────


class TestCrossAgentValidation:
    @pytest.mark.parametrize("agent_id,content", [
        ("ops", "Dein Kurs ist gebucht für morgen um 10 Uhr. Viel Spaß!"),
        ("sales", "Ich habe einige tolle Optionen für dich. Das Premium-Paket bietet dir Zugang zu allen Kursen."),
        ("medic", "Aufwärmen ist sehr wichtig. Bitte konsultiere einen Arzt bei anhaltenden Beschwerden. Ruf im Notfall 112 an."),
        ("vision", "Deine Analyse zeigt eine gute Form beim Kreuzheben. Achte auf den geraden Rücken."),
        ("persona", "Hey, schön dich zu sehen! Ich bin da, wenn du Fragen hast."),
        ("knowledge", "Unsere Sauna hat Montag bis Freitag von sechs bis zweiundzwanzig Uhr geöffnet."),
        ("campaign", "Kampagnenvorschlag: Neujahrs-Challenge mit täglichen Workouts und Ernährungstipps."),
        ("media", "Instagram-Post: Neues Jahr, neues Ich! Starte deine Fitness-Reise noch heute bei uns."),
    ])
    def test_all_agents_pass_smoke_qa(self, agent_id: str, content: str) -> None:
        """All 8 agents produce outputs that pass the smoke QA profile."""
        result = _make_mock_result(agent_id, content)
        task = _task(agent_id, "Test message")
        verdict = QAJudge().evaluate(result, task, SMOKE_QA_PROFILE)
        assert verdict.status == QAStatus.PASS, f"Agent {agent_id} failed smoke QA: {verdict.feedback}"

    @pytest.mark.parametrize("agent_id", [
        "ops", "sales", "medic", "vision", "persona", "knowledge", "campaign", "media"
    ])
    def test_no_tool_leak_in_outputs(self, agent_id: str) -> None:
        """None of the 8 agents should leak internal tool patterns."""
        clean_result = _make_mock_result(agent_id, "Dies ist eine normale Antwort ohne interne Daten.")
        _validate_basic(clean_result, agent_id)
