"""Unit tests for Sales Agent Magicline Integration."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.gateway.schemas import InboundMessage
from app.swarm.agents.sales import AgentSales
from app.swarm.llm import LLMClient

@pytest.fixture
def agent():
    llm = MagicMock(spec=LLMClient)
    llm.chat = AsyncMock()
    # BaseAgent does not accept args. Inject LLM via instance attribute.
    agent = AgentSales()
    agent._llm = llm
    return agent

@pytest.mark.asyncio
async def test_sales_agent_tool_loop(agent):
    # Mock LLM to return TOOL command first, then final answer
    agent._llm.chat.side_effect = [
        "TOOL: get_member_status(user-1)",
        "Du bist Premium Mitglied!"
    ]
    
    # Mock Magicline tool execution
    with patch("app.swarm.agents.sales.magicline.get_member_status") as mock_tool:
        mock_tool.return_value = "Mitglied Test: Aktiv (Premium)"
        
        msg = InboundMessage(
            message_id="test-sales-1",
            platform="whatsapp",
            user_id="user-1",
            content="Bin ich Premium?",
            content_type="text"
        )
        
        response = await agent.handle(msg)
        
        # Verify
        assert response.content == "Du bist Premium Mitglied!"
        mock_tool.assert_called_once_with("user-1")
        
        # Verify LLM calls
        assert agent._llm.chat.call_count == 2

@pytest.mark.asyncio
async def test_sales_agent_no_tool(agent):
    agent._llm.chat.return_value = "Gerne helfe ich dir weiter."
    
    msg = InboundMessage(
        message_id="test-sales-2",
        platform="whatsapp",
        user_id="user-1",
        content="Hilfe",
        content_type="text"
    )
    
    response = await agent.handle(msg)
    assert response.content == "Gerne helfe ich dir weiter."
    assert agent._llm.chat.call_count == 1
