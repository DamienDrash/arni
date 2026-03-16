"""ARIIA Swarm v3 — Unit Tests for LeadAgent + IntentClassifier.

Tests intent classification routing, emergency bypass, fallbacks,
LeadAgent delegation, QA revision loop, and confirmation gate flow.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.swarm.contracts import (
    AgentResult,
    AgentTask,
    IntentResult,
    TenantContext,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_context(
    tenant_id: int = 1,
    plan_slug: str = "pro",
    integrations: frozenset[str] | None = None,
    settings: dict | None = None,
) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        tenant_slug="test-studio",
        plan_slug=plan_slug,
        active_integrations=integrations if integrations is not None else frozenset({"magicline"}),
        settings=settings or {},
        member_id="member-001",
        session_id="session-001",
    )


def _make_inbound(content: str = "Hallo", tenant_id: int = 1):
    """Create a minimal InboundMessage-like object."""
    from app.gateway.schemas import InboundMessage, Platform

    return InboundMessage(
        message_id="msg-001",
        platform=Platform.WHATSAPP,
        user_id="user-001",
        content=content,
        tenant_id=tenant_id,
    )


def _mock_llm_response(agent_id: str, confidence: float = 0.9, extracted: dict | None = None):
    """Create a mock LLM that returns a JSON classification response."""
    llm = AsyncMock()
    response = json.dumps({
        "agent_id": agent_id,
        "confidence": confidence,
        "extracted": extracted or {},
    })
    llm.chat = AsyncMock(return_value=response)
    return llm


# ═══════════════════════════════════════════════════════════════════════════
# IntentClassifier Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestIntentClassifierRouting:
    """Test that the classifier routes to the correct agent."""

    @pytest.mark.asyncio
    async def test_routes_to_ops(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("ops", 0.95, {"date": "2026-03-20"})
        ctx = _make_context(integrations=frozenset({"magicline"}))
        result = await classify("Ich möchte einen Termin buchen", ctx, llm=llm)

        assert result.agent_id == "ops"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_routes_to_sales(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("sales", 0.88)
        ctx = _make_context(integrations=frozenset({"magicline"}))
        result = await classify("Mein Vertrag läuft bald aus", ctx, llm=llm)

        assert result.agent_id == "sales"
        assert result.confidence == 0.88

    @pytest.mark.asyncio
    async def test_routes_to_medic(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("medic", 0.92)
        ctx = _make_context()
        result = await classify("Mein Knie tut weh beim Training", ctx, llm=llm)

        assert result.agent_id == "medic"
        assert result.confidence == 0.92

    @pytest.mark.asyncio
    async def test_routes_to_vision(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("vision", 0.85)
        ctx = _make_context()
        result = await classify("Kannst du meine Übungsform prüfen?", ctx, llm=llm)

        assert result.agent_id == "vision"

    @pytest.mark.asyncio
    async def test_routes_to_persona(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("persona", 0.7)
        ctx = _make_context()
        result = await classify("Wie geht es dir?", ctx, llm=llm)

        assert result.agent_id == "persona"

    @pytest.mark.asyncio
    async def test_routes_to_knowledge(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("knowledge", 0.91)
        ctx = _make_context()
        result = await classify("Was sind eure Öffnungszeiten?", ctx, llm=llm)

        assert result.agent_id == "knowledge"

    @pytest.mark.asyncio
    async def test_routes_to_campaign(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("campaign", 0.82)
        ctx = _make_context()
        result = await classify("Erstelle eine Marketingkampagne", ctx, llm=llm)

        assert result.agent_id == "campaign"

    @pytest.mark.asyncio
    async def test_routes_to_media(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("media", 0.79)
        ctx = _make_context()
        result = await classify("Erstelle einen Instagram Post", ctx, llm=llm)

        assert result.agent_id == "media"


class TestIntentClassifierEmergency:
    """Test emergency keyword bypass."""

    @pytest.mark.asyncio
    async def test_emergency_notfall(self):
        from app.swarm.lead.intent_classifier import classify

        ctx = _make_context()
        # Note: _check_emergency splits on whitespace, so keyword must be a clean word
        result = await classify("Hilfe notfall bitte", ctx)

        assert result.agent_id == "medic"
        assert result.confidence == 1.0
        assert result.extracted.get("emergency") is True

    @pytest.mark.asyncio
    async def test_emergency_112(self):
        from app.swarm.lead.intent_classifier import classify

        ctx = _make_context()
        result = await classify("Ruf 112 an bitte", ctx)

        assert result.agent_id == "medic"
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_emergency_unfall(self):
        from app.swarm.lead.intent_classifier import classify

        ctx = _make_context()
        result = await classify("Es gab einen Unfall im Studio", ctx)

        assert result.agent_id == "medic"
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_emergency_english(self):
        from app.swarm.lead.intent_classifier import classify

        ctx = _make_context()
        result = await classify("There has been an emergency", ctx)

        assert result.agent_id == "medic"
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_emergency_bypasses_llm(self):
        """Emergency keywords should NOT call the LLM at all."""
        from app.swarm.lead.intent_classifier import classify

        llm = AsyncMock()
        ctx = _make_context()
        result = await classify("Notfall hier!", ctx, llm=llm)

        assert result.agent_id == "medic"
        llm.chat.assert_not_called()


class TestIntentClassifierFallback:
    """Test fallback behavior on low confidence or errors."""

    @pytest.mark.asyncio
    async def test_low_confidence_falls_back_to_persona(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("ops", 0.3)
        ctx = _make_context(integrations=frozenset({"magicline"}))
        result = await classify("hmm", ctx, llm=llm)

        assert result.agent_id == "persona"

    @pytest.mark.asyncio
    async def test_no_llm_falls_back_to_persona(self):
        from app.swarm.lead.intent_classifier import classify

        ctx = _make_context()
        result = await classify("Buche einen Termin", ctx, llm=None)

        assert result.agent_id == "persona"
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_invalid_json_falls_back_to_persona(self):
        from app.swarm.lead.intent_classifier import classify

        llm = AsyncMock()
        llm.chat = AsyncMock(return_value="This is not JSON at all")
        ctx = _make_context()
        result = await classify("test", ctx, llm=llm)

        assert result.agent_id == "persona"
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back_to_persona(self):
        from app.swarm.lead.intent_classifier import classify

        llm = AsyncMock()
        llm.chat = AsyncMock(side_effect=RuntimeError("API down"))
        ctx = _make_context()
        result = await classify("test", ctx, llm=llm)

        assert result.agent_id == "persona"
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_invalid_agent_id_falls_back_to_persona(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("nonexistent_agent", 0.9)
        ctx = _make_context()
        result = await classify("test", ctx, llm=llm)

        assert result.agent_id == "persona"

    @pytest.mark.asyncio
    async def test_empty_response_falls_back_to_persona(self):
        from app.swarm.lead.intent_classifier import classify

        llm = AsyncMock()
        llm.chat = AsyncMock(return_value="")
        ctx = _make_context()
        result = await classify("test", ctx, llm=llm)

        assert result.agent_id == "persona"


class TestIntentClassifierIntegrationFilter:
    """Test that agents are filtered by active integrations."""

    @pytest.mark.asyncio
    async def test_ops_excluded_without_magicline(self):
        from app.swarm.lead.intent_classifier import classify

        # LLM returns "ops" but tenant lacks magicline integration
        # Even if LLM says "ops", the classifier should reject it since
        # ops is not in the available agents list
        llm = AsyncMock()
        llm.chat = AsyncMock(return_value='{"agent_id": "ops", "confidence": 0.9, "extracted": {}}')
        ctx = _make_context(integrations=frozenset())
        result = await classify("Buche einen Termin", ctx, llm=llm)

        # ops requires magicline — should fall back to persona
        assert result.agent_id == "persona"
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_sales_excluded_without_magicline(self):
        from app.swarm.lead.intent_classifier import _filter_by_integrations

        available = _filter_by_integrations(frozenset())
        assert "sales" not in available
        assert "ops" not in available
        assert "persona" in available
        assert "medic" in available

    @pytest.mark.asyncio
    async def test_all_agents_available_with_magicline(self):
        from app.swarm.lead.intent_classifier import _filter_by_integrations

        available = _filter_by_integrations(frozenset({"magicline"}))
        assert "ops" in available
        assert "sales" in available
        assert "persona" in available


class TestIntentClassifierHistory:
    """Test that conversation history is passed to the LLM."""

    @pytest.mark.asyncio
    async def test_history_included_in_messages(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("persona", 0.8)
        ctx = _make_context()
        history = (
            {"role": "user", "content": "Hallo"},
            {"role": "assistant", "content": "Hi! Wie kann ich helfen?"},
        )
        await classify("Was kostet das?", ctx, history=history, llm=llm)

        # Verify the LLM was called with messages including history
        call_args = llm.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages", [])
        # System + 2 history + 1 user = 4 messages
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "Hallo"
        assert messages[2]["content"] == "Hi! Wie kann ich helfen?"
        assert messages[3]["content"] == "Was kostet das?"

    @pytest.mark.asyncio
    async def test_history_truncated_to_5(self):
        from app.swarm.lead.intent_classifier import classify

        llm = _mock_llm_response("persona", 0.8)
        ctx = _make_context()
        history = tuple(
            {"role": "user", "content": f"message {i}"}
            for i in range(10)
        )
        await classify("latest", ctx, history=history, llm=llm)

        call_args = llm.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages", [])
        # System + 5 history (truncated) + 1 user = 7
        assert len(messages) == 7


# ═══════════════════════════════════════════════════════════════════════════
# LeadAgent Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestLeadAgentDelegation:
    """Test that LeadAgent delegates to the correct expert agent."""

    @pytest.mark.asyncio
    @patch("app.swarm.lead.lead_agent.LeadAgent._build_history", return_value=())
    @patch("app.swarm.lead.intent_classifier.classify")
    @patch("app.swarm.registry.dynamic_loader.get_agent_loader")
    @patch("app.swarm.qa.profiles.QA_PROFILES", {
        "standard": MagicMock(criteria=frozenset(), max_revision_attempts=0),
    })
    @patch("app.swarm.qa.profiles.AGENT_QA_PROFILES", {"ops": "standard"})
    async def test_delegates_to_expert(self, mock_loader_fn, mock_classify, mock_history):
        from app.swarm.lead.lead_agent import LeadAgent

        # Setup: classifier returns ops
        mock_classify.return_value = IntentResult(
            agent_id="ops", confidence=0.9, extracted={"date": "2026-03-20"}
        )

        # Setup: loader returns a mock agent
        mock_agent = AsyncMock()
        mock_agent.execute = AsyncMock(return_value=AgentResult(
            agent_id="ops",
            content="Termin gebucht für 20. März.",
            confidence=0.95,
        ))
        mock_loader = MagicMock()
        mock_loader.get_agent = MagicMock(return_value=mock_agent)
        mock_loader_fn.return_value = mock_loader

        lead = LeadAgent(llm=AsyncMock())
        msg = _make_inbound("Buche einen Termin für morgen")
        ctx = _make_context()

        result = await lead.handle(msg, ctx)

        assert result.agent_id == "ops"
        assert "Termin" in result.content
        mock_agent.execute.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.swarm.lead.lead_agent.LeadAgent._build_history", return_value=())
    @patch("app.swarm.lead.intent_classifier.classify")
    @patch("app.swarm.registry.dynamic_loader.get_agent_loader")
    async def test_fallback_when_agent_not_found(self, mock_loader_fn, mock_classify, mock_history):
        from app.swarm.lead.lead_agent import LeadAgent

        mock_classify.return_value = IntentResult(agent_id="ops", confidence=0.9)

        # Loader returns None for ops, also None for persona fallback
        mock_loader = MagicMock()
        mock_loader.get_agent = MagicMock(return_value=None)
        mock_loader_fn.return_value = mock_loader

        lead = LeadAgent(llm=AsyncMock())
        msg = _make_inbound("test")
        ctx = _make_context()

        result = await lead.handle(msg, ctx)

        assert result.agent_id == "lead"
        assert result.confidence < 0.5
        assert "später" in result.content or "leid" in result.content


class TestLeadAgentConfirmationGate:
    """Test confirmation gate interception in LeadAgent."""

    @pytest.mark.asyncio
    @patch("app.swarm.lead.lead_agent.LeadAgent._build_history", return_value=())
    async def test_confirmation_gate_intercept(self, mock_history):
        from app.swarm.lead.lead_agent import LeadAgent
        from app.swarm.lead.confirmation_gate import PendingConfirmation

        # Setup: Redis client returns pending confirmation
        mock_redis = AsyncMock()
        pending = PendingConfirmation(
            token="tok-123",
            agent_id="ops",
            confirmation_prompt="Termin stornieren?",
            confirmation_action={"action": "cancel", "booking_id": 42},
            tenant_id=1,
            member_id="member-001",
        )

        with patch("app.swarm.lead.confirmation_gate.ConfirmationGate") as MockGate:
            gate_instance = AsyncMock()
            gate_instance.check = AsyncMock(return_value=pending)
            gate_instance.resolve = AsyncMock(return_value=AgentResult(
                agent_id="ops",
                content="Termin wurde storniert.",
                confidence=1.0,
            ))
            MockGate.return_value = gate_instance
            MockGate.is_affirmative = MagicMock(return_value=True)

            lead = LeadAgent(llm=AsyncMock(), redis_client=mock_redis)
            msg = _make_inbound("Ja bitte")
            ctx = _make_context()

            result = await lead.handle(msg, ctx)

            assert result.content == "Termin wurde storniert."
            gate_instance.check.assert_called_once()
            gate_instance.resolve.assert_called_once()


class TestLeadAgentQA:
    """Test QA revision loop in LeadAgent."""

    @pytest.mark.asyncio
    async def test_qa_pass_returns_directly(self):
        from app.swarm.lead.lead_agent import LeadAgent
        from app.swarm.qa.profiles import QAProfile, QACriterion
        from app.swarm.qa.judge import QAJudge, QAVerdict, QAStatus

        lead = LeadAgent()

        mock_agent = AsyncMock()
        mock_agent.execute = AsyncMock(return_value=AgentResult(
            agent_id="persona",
            content="Hallo! Ich bin dein Fitness-Assistent. Wie kann ich dir helfen?",
        ))

        task = AgentTask(
            task_id="t-001",
            agent_id="persona",
            original_message="Hallo",
            intent_payload={},
            tenant_context=_make_context(),
        )

        profile = QAProfile(
            name="standard",
            criteria=frozenset({QACriterion.RESPONSE_NOT_EMPTY}),
            max_revision_attempts=1,
        )

        result = await lead._execute_with_qa(mock_agent, task, profile)

        assert result.agent_id == "persona"
        assert "Hallo" in result.content
        # Agent should have been called exactly once (QA passed first time)
        assert mock_agent.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_qa_revise_retries(self):
        from app.swarm.lead.lead_agent import LeadAgent
        from app.swarm.qa.profiles import QAProfile, QACriterion

        lead = LeadAgent()

        # First call: empty response (fails QA), second call: valid response
        mock_agent = AsyncMock()
        mock_agent.execute = AsyncMock(side_effect=[
            AgentResult(agent_id="ops", content="", confidence=0.9),
            AgentResult(agent_id="ops", content="Hier ist dein Termin am Montag um 10 Uhr.", confidence=0.9),
        ])

        task = AgentTask(
            task_id="t-002",
            agent_id="ops",
            original_message="Hallo, ich möchte einen Termin",
            intent_payload={},
            tenant_context=_make_context(),
        )

        profile = QAProfile(
            name="standard",
            criteria=frozenset({QACriterion.RESPONSE_NOT_EMPTY}),
            max_revision_attempts=1,
        )

        result = await lead._execute_with_qa(mock_agent, task, profile)

        assert result.content != ""
        assert mock_agent.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_qa_escalate_returns_handoff(self):
        from app.swarm.lead.lead_agent import LeadAgent
        from app.swarm.qa.profiles import QAProfile, QACriterion

        lead = LeadAgent()

        # Agent returns empty content — strict profile escalates on fail
        mock_agent = AsyncMock()
        mock_agent.execute = AsyncMock(return_value=AgentResult(
            agent_id="medic", content="", confidence=0.9,
        ))

        task = AgentTask(
            task_id="t-003",
            agent_id="medic",
            original_message="Ich habe Schmerzen",
            intent_payload={},
            tenant_context=_make_context(),
        )

        profile = QAProfile(
            name="strict",
            criteria=frozenset({QACriterion.RESPONSE_NOT_EMPTY}),
            max_revision_attempts=2,
            escalate_on_fail=True,
        )

        result = await lead._execute_with_qa(mock_agent, task, profile)

        assert "Mitarbeiter" in result.content or "weiter" in result.content
        assert result.metadata.get("needs_handoff") is True
        # Agent called only once — escalate immediately, no revision
        assert mock_agent.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_qa_no_criteria_skips_qa(self):
        from app.swarm.lead.lead_agent import LeadAgent
        from app.swarm.qa.profiles import QAProfile

        lead = LeadAgent()

        mock_agent = AsyncMock()
        mock_agent.execute = AsyncMock(return_value=AgentResult(
            agent_id="knowledge", content="Wir haben Mo-Fr 8-22 Uhr geöffnet.",
        ))

        task = AgentTask(
            task_id="t-004",
            agent_id="knowledge",
            original_message="Öffnungszeiten?",
            intent_payload={},
            tenant_context=_make_context(),
        )

        profile = QAProfile(name="off", criteria=frozenset(), max_revision_attempts=0)

        result = await lead._execute_with_qa(mock_agent, task, profile)

        assert result.content == "Wir haben Mo-Fr 8-22 Uhr geöffnet."
        assert mock_agent.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_qa_revise_injects_feedback(self):
        """On REVISE, the retry task should contain qa_feedback in intent_payload."""
        from app.swarm.lead.lead_agent import LeadAgent
        from app.swarm.qa.profiles import QAProfile, QACriterion

        lead = LeadAgent()

        call_payloads = []

        async def capture_execute(task):
            call_payloads.append(dict(task.intent_payload))
            if len(call_payloads) == 1:
                return AgentResult(agent_id="ops", content="", confidence=0.9)
            return AgentResult(agent_id="ops", content="Hier ist dein Termin am Montag.", confidence=0.9)

        mock_agent = AsyncMock()
        mock_agent.execute = AsyncMock(side_effect=capture_execute)

        task = AgentTask(
            task_id="t-005",
            agent_id="ops",
            original_message="Ich brauche einen Termin",
            intent_payload={},
            tenant_context=_make_context(),
        )

        profile = QAProfile(
            name="standard",
            criteria=frozenset({QACriterion.RESPONSE_NOT_EMPTY}),
            max_revision_attempts=1,
        )

        await lead._execute_with_qa(mock_agent, task, profile)

        assert len(call_payloads) == 2
        assert "qa_feedback" in call_payloads[1]
        assert call_payloads[1]["qa_attempt"] == 1


class TestLeadAgentNoGodClass:
    """Verify LeadAgent contains no domain logic."""

    def test_no_booking_logic(self):
        import inspect
        from app.swarm.lead.lead_agent import LeadAgent

        source = inspect.getsource(LeadAgent)
        # LeadAgent should NOT contain booking/sales/medic-specific logic
        assert "magicline" not in source.lower()
        assert "get_class_schedule" not in source
        assert "book_appointment" not in source
        assert "cancel_member_booking" not in source

    def test_no_sales_logic(self):
        import inspect
        from app.swarm.lead.lead_agent import LeadAgent

        source = inspect.getsource(LeadAgent)
        assert "churn" not in source.lower()
        assert "retention" not in source.lower()
        assert "upsell" not in source.lower()

    def test_no_health_logic(self):
        import inspect
        from app.swarm.lead.lead_agent import LeadAgent

        source = inspect.getsource(LeadAgent)
        assert "disclaimer" not in source.lower()
        assert "112" not in source
        assert "notfall" not in source.lower()
