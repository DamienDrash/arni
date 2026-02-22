"""ARNI v1.4 – Swarm Router & Agent Tests.

@QA: Sprint 2, Tasks 2.11–2.13
Tests: Intent classification, agent dispatch, keyword fallback, Medic disclaimer.
"""

import pytest

from app.gateway.schemas import InboundMessage, Platform
from app.swarm.agents.medic import AgentMedic
from app.swarm.agents.ops import AgentOps
from app.swarm.agents.persona import AgentPersona
from app.swarm.agents.sales import AgentSales
from app.swarm.agents.vision import AgentVision
from app.swarm.base import AgentResponse
from app.swarm.llm import LLMClient
from app.swarm.router.intents import Intent, ROUTING_TABLE
from app.swarm.router.router import SwarmRouter


# ── Helpers ──


def make_message(content: str, msg_id: str = "test-001") -> InboundMessage:
    """Create a test InboundMessage."""
    return InboundMessage(
        message_id=msg_id,
        platform=Platform.WHATSAPP,
        user_id="test-user",
        content=content,
    )


# ── Intent & Routing Table Tests ──


class TestIntentEnum:
    def test_all_intents_defined(self) -> None:
        assert len(Intent) == 6  # booking, sales, health, crowd, smalltalk, unknown

    def test_routing_table_covers_all_except_unknown(self) -> None:
        for intent in Intent:
            if intent != Intent.UNKNOWN:
                assert intent in ROUTING_TABLE

    def test_routing_table_agent_names(self) -> None:
        assert ROUTING_TABLE[Intent.BOOKING] == "ops"
        assert ROUTING_TABLE[Intent.SALES] == "sales"
        assert ROUTING_TABLE[Intent.HEALTH] == "medic"
        assert ROUTING_TABLE[Intent.CROWD] == "vision"
        assert ROUTING_TABLE[Intent.SMALLTALK] == "persona"


# ── Keyword Classification Tests ──


class TestKeywordClassification:
    def test_booking_keywords(self) -> None:
        assert SwarmRouter._keyword_classify("Ich will einen Kurs buchen") == Intent.BOOKING

    def test_sales_keywords(self) -> None:
        assert SwarmRouter._keyword_classify("Was kostet die Mitgliedschaft?") == Intent.SALES

    def test_health_keywords(self) -> None:
        assert SwarmRouter._keyword_classify("Ich habe Schmerzen im Knie") == Intent.HEALTH

    def test_crowd_keywords(self) -> None:
        assert SwarmRouter._keyword_classify("Ist es gerade voll?") == Intent.CROWD

    def test_smalltalk_keywords(self) -> None:
        assert SwarmRouter._keyword_classify("Hey, hallo!") == Intent.SMALLTALK

    def test_unknown_returns_unknown(self) -> None:
        assert SwarmRouter._keyword_classify("xyz quantum physics") == Intent.UNKNOWN


# ── Agent Tests ──


class TestAgentOps:
    @pytest.mark.anyio
    async def test_booking_response(self) -> None:
        agent = AgentOps()
        msg = make_message("Ich will einen Kurs buchen")
        result = await agent.handle(msg)
        assert isinstance(result, AgentResponse)
        assert "verfügbar" in result.content.lower() or "buchen" in result.content.lower()

    @pytest.mark.anyio
    async def test_cancellation_requires_confirmation(self) -> None:
        agent = AgentOps()
        msg = make_message("Ich will meinen Kurs stornieren")
        result = await agent.handle(msg)
        assert result.requires_confirmation is True

    @pytest.mark.anyio
    async def test_opening_hours(self) -> None:
        agent = AgentOps()
        msg = make_message("Habt ihr auf?")
        result = await agent.handle(msg)
        assert "öffnungszeit" in result.content.lower() or "23:00" in result.content

    @pytest.mark.anyio
    async def test_agent_name(self) -> None:
        assert AgentOps().name == "ops"


class TestAgentSales:
    @pytest.mark.anyio
    async def test_cancellation_offers_alternatives(self) -> None:
        agent = AgentSales()
        msg = make_message("Ich möchte kündigen")
        result = await agent.handle(msg)
        assert result.requires_confirmation is True
        assert "pausieren" in result.content.lower() or "option" in result.content.lower() or "alternativ" in result.content.lower()

    @pytest.mark.anyio
    async def test_pricing_response(self) -> None:
        agent = AgentSales()
        msg = make_message("Was kostet das?")
        result = await agent.handle(msg)
        assert "€" in result.content or "preis" in result.content.lower()

    @pytest.mark.anyio
    async def test_agent_name(self) -> None:
        assert AgentSales().name == "sales"


class TestAgentMedic:
    @pytest.mark.anyio
    async def test_always_has_disclaimer(self) -> None:
        agent = AgentMedic()
        msg = make_message("Ich habe Knieschmerzen")
        result = await agent.handle(msg)
        assert "Ich bin kein Arzt" in result.content

    @pytest.mark.anyio
    async def test_disclaimer_on_generic(self) -> None:
        agent = AgentMedic()
        msg = make_message("Soll ich mit Rückenschmerzen trainieren?")
        result = await agent.handle(msg)
        assert "Ich bin kein Arzt" in result.content

    @pytest.mark.anyio
    async def test_emergency_detection(self) -> None:
        agent = AgentMedic()
        msg = make_message("Jemand hat einen Herzinfarkt!")
        result = await agent.handle(msg)
        assert "112" in result.content
        assert result.metadata is not None
        assert result.metadata.get("severity") == "critical"

    @pytest.mark.anyio
    async def test_agent_name(self) -> None:
        assert AgentMedic().name == "medic"


class TestAgentVision:
    @pytest.mark.anyio
    async def test_returns_crowd_data(self) -> None:
        agent = AgentVision()
        msg = make_message("Wie voll ist es?")
        result = await agent.handle(msg)
        assert result.metadata is not None
        assert "count" in result.metadata
        assert result.metadata["source"] == "stub"

    @pytest.mark.anyio
    async def test_agent_name(self) -> None:
        assert AgentVision().name == "vision"


class TestAgentPersona:
    @pytest.mark.anyio
    async def test_greeting(self) -> None:
        agent = AgentPersona()
        msg = make_message("Hey!")
        result = await agent.handle(msg)
        assert "hey" in result.content.lower() or "👋" in result.content

    @pytest.mark.anyio
    async def test_motivation(self) -> None:
        agent = AgentPersona()
        msg = make_message("Ich hab keine Lust heute")
        result = await agent.handle(msg)
        assert "💪" in result.content or "minuten" in result.content.lower()

    @pytest.mark.anyio
    async def test_unknown_stays_in_character(self) -> None:
        agent = AgentPersona()
        msg = make_message("blablabla xyz random input")
        result = await agent.handle(msg)
        # Must NOT say "As an AI" (SOUL.md constraint)
        assert "as an ai" not in result.content.lower()
        assert "ich bin ein bot" not in result.content.lower()

    @pytest.mark.anyio
    async def test_agent_name(self) -> None:
        assert AgentPersona().name == "persona"


# ── Router Integration Tests ──


class TestSwarmRouter:
    @pytest.fixture
    def router(self) -> SwarmRouter:
        """Router with no API key → will use keyword fallback."""
        llm = LLMClient(openai_api_key="")
        return SwarmRouter(llm=llm)

    @pytest.mark.anyio
    async def test_routes_booking(self, router: SwarmRouter) -> None:
        msg = make_message("Ich will einen Kurs buchen")
        result = await router.route(msg)
        assert isinstance(result, AgentResponse)

    @pytest.mark.anyio
    async def test_routes_health(self, router: SwarmRouter) -> None:
        msg = make_message("Mein Knie tut weh")
        result = await router.route(msg)
        assert "Ich bin kein Arzt" in result.content

    @pytest.mark.anyio
    async def test_routes_crowd(self, router: SwarmRouter) -> None:
        msg = make_message("Ist es gerade voll?")
        result = await router.route(msg)
        assert result.metadata is not None
        assert "count" in result.metadata

    @pytest.mark.anyio
    async def test_routes_cancellation_to_sales(self, router: SwarmRouter) -> None:
        msg = make_message("Ich will meinen Vertrag kündigen")
        result = await router.route(msg)
        assert result.requires_confirmation is True

    @pytest.mark.anyio
    async def test_unknown_falls_to_persona(self, router: SwarmRouter) -> None:
        msg = make_message("asdfjklö random gibberish")
        result = await router.route(msg)
        assert isinstance(result, AgentResponse)


# ── LLM Client Tests ──


class TestLLMClient:
    def test_fallback_initially_false(self) -> None:
        llm = LLMClient(openai_api_key="test-key")
        assert llm.is_fallback_active is False

    def test_emergency_response_content(self) -> None:
        llm = LLMClient()
        response = llm._emergency_response()
        assert "technisch eingeschränkt" in response

    @pytest.mark.anyio
    async def test_no_api_key_uses_fallback(self) -> None:
        llm = LLMClient(openai_api_key="")
        # Without any LLM available, should return emergency response
        result = await llm.chat([{"role": "user", "content": "test"}])
        assert isinstance(result, str)
        assert len(result) > 0
