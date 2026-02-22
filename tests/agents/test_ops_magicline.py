"""Unit tests for Ops Agent Magicline Integration."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.gateway.schemas import InboundMessage
from app.swarm.agents.ops import AgentOps
from app.swarm.llm import LLMClient

@pytest.fixture
def agent():
    llm = MagicMock(spec=LLMClient)
    llm.chat = AsyncMock()
    # BaseAgent does not accept args. Inject LLM via instance attribute.
    agent = AgentOps()
    agent._llm = llm
    return agent

@pytest.mark.asyncio
async def test_ops_agent_tool_loop(agent):
    # Mock LLM to return TOOL command first, then final answer
    agent._llm.chat.side_effect = [
        "TOOL: get_class_schedule(2026-02-15)",
        "Hier ist der Kursplan..."
    ]
    
    # Mock Magicline tool execution
    with patch("app.swarm.agents.ops.magicline.get_class_schedule") as mock_tool:
        mock_tool.return_value = "Kursplan: Yoga 18:00"
        
        msg = InboundMessage(
            message_id="test-1",
            platform="whatsapp",
            user_id="user-1",
            content="Wann ist Yoga?",
            content_type="text"
        )
        
        response = await agent.handle(msg)
        
        # Verify
        assert response.content == "Hier ist der Kursplan..."
        mock_tool.assert_called_once_with("2026-02-15")
        
        # Verify LLM calls
        assert agent._llm.chat.call_count == 2
        # First call: Initial prompt
        # Second call: Prompt with tool output

@pytest.mark.asyncio
async def test_ops_agent_appointment_tool(agent):
    agent._llm.chat.side_effect = [
        "TOOL: get_appointment_slots(massage, 3)",
        "Termine gefunden..."
    ]

    with patch("app.swarm.agents.ops.magicline.get_appointment_slots") as mock_tool:
        mock_tool.return_value = "Termin 1..."
        
        msg = InboundMessage(
            message_id="test-2",
            platform="whatsapp",
            user_id="user-1",
            content="Massage Termin?",
            content_type="text"
        )
        
        await agent.handle(msg)
        mock_tool.assert_called_once_with("massage", 3)

@pytest.mark.asyncio
async def test_ops_agent_no_tool(agent):
    agent._llm.chat.return_value = "Hallo, wie kann ich helfen?"
    
    msg = InboundMessage(
        message_id="test-3",
        platform="whatsapp",
        user_id="user-1",
        content="Hallo",
        content_type="text"
    )
    
    response = await agent.handle(msg)
    assert response.content == "Hallo, wie kann ich helfen?"
    assert agent._llm.chat.call_count == 1
