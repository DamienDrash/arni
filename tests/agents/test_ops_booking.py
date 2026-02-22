"""Unit tests for Ops Agent Booking Flow."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.gateway.schemas import InboundMessage
from app.swarm.agents.ops import AgentOps
from app.swarm.llm import LLMClient

@pytest.fixture
def agent():
    llm = MagicMock(spec=LLMClient)
    llm.chat = AsyncMock()
    agent = AgentOps()
    agent._llm = llm
    return agent

@pytest.mark.asyncio
async def test_ops_booking_confirmation(agent):
    """Test that agent asks for confirmation before booking."""
    # User says "Book Yoga"
    # LLM should find class first, then ask confirmation
    # Here we mock LLM asking "Which one?" or similar.
    # But let's test the tool execution path.
    
    agent._llm.chat.return_value = "TOOL: get_class_schedule(2026-02-15)"
    
    with patch("app.swarm.tools.magicline.get_class_schedule") as mock_schedule:
        mock_schedule.return_value = "ID 101: Yoga (18:00)"
        
        msg = InboundMessage(
            message_id="book-1",
            platform="whatsapp",
            user_id="user-1",
            content="Buche Yoga morgen",
            content_type="text"
        )
        
        # We need to simulate the SECOND LLM call which sees the schedule and asks confirmation
        # AgentOps.handle does: Chat -> Tool -> Chat.
        # So we need side_effect for chat:
        # 1. "TOOL: get_class_schedule..."
        # 2. "Yoga ist um 18h (ID 101). Soll ich buchen?"
        agent._llm.chat.side_effect = [
            "TOOL: get_class_schedule(2026-02-15)",
            "Yoga ist um 18h (ID 101). Soll ich buchen?"
        ]
        
        response = await agent.handle(msg)
        
        assert "Soll ich buchen?" in response.content
        mock_schedule.assert_called_once()

@pytest.mark.asyncio
async def test_ops_booking_execution(agent):
    """Test actual booking execution when user says YES."""
    # User says "Yes, book ID 101"
    
    agent._llm.chat.side_effect = [
        "TOOL: class_book(101)",
        "Buchung bestätigt! Viel Spaß."
    ]
    
    with patch("app.swarm.tools.magicline.class_book") as mock_book:
        mock_book.return_value = "Buchung erfolgreich! (ID: 555)"
        
        msg = InboundMessage(
            message_id="book-2",
            platform="whatsapp",
            user_id="user-1",
            content="Ja, buche ID 101",
            content_type="text"
        )
        
        response = await agent.handle(msg)
        
        assert "Buchung bestätigt" in response.content
        mock_book.assert_called_once_with(101, user_identifier="user-1", tenant_id=None)
