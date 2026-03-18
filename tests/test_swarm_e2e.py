"""ARIIA Swarm v3 — End-to-End Integration Tests.

Tests the full message → response pipeline through LeadAgent,
with mocked LLM and external APIs.
"""

import json
import pytest
import fakeredis.aioredis
from unittest.mock import AsyncMock, MagicMock, patch

from app.gateway.schemas import InboundMessage, Platform
from app.swarm.contracts import AgentResult, AgentTask, TenantContext, IntentResult
from app.swarm.lead.lead_agent import LeadAgent
from app.swarm.lead.confirmation_gate import ConfirmationGate
from app.swarm.lead.intent_classifier import classify, _check_emergency, EMERGENCY_KEYWORDS
from app.swarm.qa.judge import QAJudge, QAStatus
from app.swarm.qa.profiles import QACriterion, QAProfile, QA_PROFILES


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _msg(content: str, user_id: str = "user-001") -> InboundMessage:
    return InboundMessage(
        message_id="test-msg-001",
        platform=Platform.WHATSAPP,
        user_id=user_id,
        content=content,
    )


def _ctx(tenant_id: int = 1, member_id: str = "member-001") -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        tenant_slug="test-studio",
        plan_slug="pro",
        active_integrations=frozenset({"magicline"}),
        settings={},
        member_id=member_id,
    )


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis()


# ── Emergency Bypass Tests ───────────────────────────────────────────────────


class TestEmergencyBypass:
    @pytest.mark.parametrize("keyword", list(EMERGENCY_KEYWORDS))
    def test_emergency_keyword_detected(self, keyword: str) -> None:
        """All emergency keywords are detected by the classifier."""
        assert _check_emergency(f"Hilfe {keyword} bitte") is True

    @pytest.mark.anyio
    async def test_emergency_bypasses_llm(self) -> None:
        """Emergency keyword routes directly to medic without LLM call."""
        mock_llm = AsyncMock()
        result = await classify(
            message="Jemand hat einen notfall hier!",
            context=_ctx(),
            llm=mock_llm,
        )
        assert result.agent_id == "medic"
        assert result.confidence == 1.0
        assert result.extracted.get("emergency") is True
        # LLM should NOT have been called
        mock_llm.chat.assert_not_called()

    def test_non_emergency_not_detected(self) -> None:
        """Normal messages are not flagged as emergency."""
        assert _check_emergency("Ich will einen Kurs buchen") is False
        assert _check_emergency("Was kostet die Mitgliedschaft?") is False


# ── Intent Classifier Tests ──────────────────────────────────────────────────


class TestIntentClassifier:
    @pytest.mark.anyio
    async def test_no_llm_fallback_to_persona(self) -> None:
        """Without LLM, classifier falls back to persona."""
        result = await classify(
            message="Hallo, wie geht es?",
            context=_ctx(),
            llm=None,
        )
        assert result.agent_id == "persona"

    @pytest.mark.anyio
    async def test_llm_classifies_booking_intent(self) -> None:
        """LLM response with ops agent_id is returned."""
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value='{"agent_id": "ops", "confidence": 0.95, "extracted": {"action": "book"}}')

        result = await classify(
            message="Ich will Yoga buchen",
            context=_ctx(),
            llm=mock_llm,
        )
        assert result.agent_id == "ops"
        assert result.confidence == 0.95

    @pytest.mark.anyio
    async def test_low_confidence_falls_to_persona(self) -> None:
        """Low confidence from LLM falls back to persona."""
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value='{"agent_id": "ops", "confidence": 0.2, "extracted": {}}')

        result = await classify(
            message="irgendwas unklares",
            context=_ctx(),
            llm=mock_llm,
        )
        assert result.agent_id == "persona"


# ── QA Disclaimer in Medic Flow ─────────────────────────────────────────────


class TestMedicDisclaimerFlow:
    def test_medic_response_without_disclaimer_fails_qa(self) -> None:
        """QAJudge catches missing disclaimer in medic response."""
        judge = QAJudge()
        strict_profile = QA_PROFILES["strict"]

        result = AgentResult(
            agent_id="medic",
            content="Mach einfach Dehnübungen, das hilft.",
            confidence=0.9,
        )
        task = AgentTask(
            task_id="t1",
            agent_id="medic",
            original_message="Mein Knie tut weh",
            intent_payload={},
            tenant_context=_ctx(),
        )

        verdict = judge.evaluate(result, task, strict_profile)
        assert verdict.status in {QAStatus.REVISE, QAStatus.ESCALATE}

    def test_medic_response_with_disclaimer_passes_qa(self) -> None:
        """Medic response with proper disclaimer passes QA."""
        judge = QAJudge()
        profile = QAProfile(
            name="test",
            criteria=frozenset({QACriterion.DISCLAIMER_PRESENT}),
        )

        result = AgentResult(
            agent_id="medic",
            content="Dehnübungen können helfen. Bitte konsultiere einen Arzt. Im Notfall ruf 112 an.",
            confidence=0.9,
        )
        task = AgentTask(
            task_id="t1",
            agent_id="medic",
            original_message="Mein Knie tut weh",
            intent_payload={},
            tenant_context=_ctx(),
        )

        verdict = judge.evaluate(result, task, profile)
        assert verdict.status == QAStatus.PASS


# ── Confirmation Gate Flow ───────────────────────────────────────────────────


class TestConfirmationGateFlow:
    @pytest.mark.anyio
    async def test_sales_cancellation_requires_confirmation(self, redis_client) -> None:
        """Cancellation flow stores confirmation and resolves on user response."""
        gate = ConfirmationGate(redis_client)
        ctx = _ctx()

        # Step 1: Agent returns requires_confirmation
        agent_result = AgentResult(
            agent_id="sales",
            content="Möchtest du wirklich kündigen?",
            confidence=0.9,
            requires_confirmation=True,
            confirmation_prompt="Vertrag kündigen?",
            confirmation_action='{"action": "terminate_contract", "contract_id": 42}',
        )

        # Step 2: Store in gate
        token = await gate.store(agent_result, ctx)
        assert token

        # Step 3: Check pending
        pending = await gate.check(ctx)
        assert pending is not None
        assert pending.agent_id == "sales"

        # Step 4: User denies
        resolved = await gate.resolve(token, user_confirmed=False, context=ctx)
        assert "abgebrochen" in resolved.content.lower()

    @pytest.mark.anyio
    async def test_confirmation_gate_user_confirms(self, redis_client) -> None:
        """User confirming 'ja' triggers re-dispatch (mocked agent)."""
        gate = ConfirmationGate(redis_client)
        ctx = _ctx()

        agent_result = AgentResult(
            agent_id="ops",
            content="Kurs stornieren?",
            requires_confirmation=True,
            confirmation_prompt="Stornierung bestätigen?",
            confirmation_action='{"action": "cancel_booking", "booking_id": 123}',
        )

        token = await gate.store(agent_result, ctx)

        # Mock the agent loader to avoid loading real agents
        with patch("app.swarm.lead.agent_loader.get_agent_loader") as mock_loader:
            mock_agent = AsyncMock()
            mock_agent.execute_confirmed = AsyncMock(
                return_value=AgentResult(
                    agent_id="ops",
                    content="Dein Kurs wurde erfolgreich storniert.",
                    confidence=1.0,
                )
            )
            mock_loader.return_value.get_agent.return_value = mock_agent

            resolved = await gate.resolve(token, user_confirmed=True, context=ctx)
            assert "storniert" in resolved.content.lower()


# ── Unknown Intent Fallback ──────────────────────────────────────────────────


class TestUnknownIntentFallback:
    @pytest.mark.anyio
    async def test_unknown_intent_falls_to_persona(self) -> None:
        """Gibberish message without LLM falls back to persona."""
        result = await classify(
            message="bla bla xyz unbekannt random text",
            context=_ctx(),
            llm=None,
        )
        assert result.agent_id == "persona"
        assert result.confidence <= 0.5


# ── LeadAgent Pipeline Tests ────────────────────────────────────────────────


class TestLeadAgentPipeline:
    @pytest.mark.anyio
    async def test_lead_agent_emergency_routing(self, redis_client) -> None:
        """LeadAgent routes emergency directly to medic."""
        lead = LeadAgent(llm=None, redis_client=redis_client)

        mock_agent = AsyncMock()
        mock_agent.execute = AsyncMock(
            return_value=AgentResult(
                agent_id="medic",
                content="Ruf sofort 112 an! Ich bin kein Arzt.",
                confidence=1.0,
            )
        )

        with patch("app.swarm.lead.intent_classifier.classify") as mock_classify, \
             patch("app.swarm.registry.dynamic_loader.get_agent_loader") as mock_loader, \
             patch("app.gateway.persistence.persistence", create=True):

            mock_classify.return_value = IntentResult(
                agent_id="medic", confidence=1.0, extracted={"emergency": True}
            )
            mock_loader.return_value.get_agent.return_value = mock_agent

            msg = _msg("Notfall Jemand ist umgefallen")
            ctx = _ctx()
            result = await lead.handle(msg, ctx)

            assert isinstance(result, AgentResult)

    @pytest.mark.anyio
    async def test_lead_agent_handles_no_agent(self, redis_client) -> None:
        """LeadAgent returns fallback when no agent is found."""
        lead = LeadAgent(llm=None, redis_client=redis_client)

        with patch("app.swarm.lead.intent_classifier.classify") as mock_classify, \
             patch("app.swarm.registry.dynamic_loader.get_agent_loader") as mock_loader, \
             patch("app.gateway.persistence.persistence", create=True):

            mock_classify.return_value = IntentResult(
                agent_id="nonexistent", confidence=0.9
            )
            mock_loader.return_value.get_agent.return_value = None

            msg = _msg("Test message")
            ctx = _ctx()
            result = await lead.handle(msg, ctx)

            assert isinstance(result, AgentResult)
            # Should get a fallback response
            assert result.content  # Not empty


# ── Integration Filter Tests ────────────────────────────────────────────────


class TestIntegrationFiltering:
    @pytest.mark.anyio
    async def test_ops_unavailable_without_magicline(self) -> None:
        """Without magicline integration, ops agent not offered to LLM."""
        from app.swarm.lead.intent_classifier import _filter_by_integrations

        # No integrations
        available = _filter_by_integrations(frozenset())
        assert "ops" not in available
        assert "sales" not in available
        assert "persona" in available
        assert "medic" in available

    @pytest.mark.anyio
    async def test_ops_available_with_magicline(self) -> None:
        """With magicline integration, ops agent is available."""
        from app.swarm.lead.intent_classifier import _filter_by_integrations

        available = _filter_by_integrations(frozenset({"magicline"}))
        assert "ops" in available
        assert "sales" in available
