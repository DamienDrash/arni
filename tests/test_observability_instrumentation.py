
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

# Mock libraries not present in env
sys.modules["langfuse"] = MagicMock()
sys.modules["langfuse.decorators"] = MagicMock()
sys.modules["structlog"] = MagicMock()

from app.swarm.base import BaseAgent, AgentResponse
from app.core.observability import ObservabilityService

class MockAgent(BaseAgent):
    @property
    def name(self): return "mock_agent"
    @property
    def description(self): return "Mocks stuff"
    async def handle(self, message): return AgentResponse("ok")

async def test_tracing_logic():
    print("Testing Observability Instrumentation...")
    
    # 1. Setup Mock LLM
    mock_llm = MagicMock()
    # Async mock for chat
    f = asyncio.Future()
    f.set_result("Mock LLM Response")
    mock_llm.chat.return_value = f
    
    MockAgent.set_llm(mock_llm)
    agent = MockAgent()

    # 2. Patch ObservabilityService to verify calls
    with patch.object(ObservabilityService, 'trace') as mock_trace:
        # Mock the span object returned by trace
        mock_span = MagicMock()
        mock_trace.return_value = mock_span
        
        # 3. Simulate Chat
        response = await agent._chat("System Prompt", "User Message", "user_123")
        
        # 4. Assertions
        assert response == "Mock LLM Response"
        print("✅ LLM Response received")
        
        # Verify Trace was created
        mock_trace.assert_called_once()
        print("✅ Trace created")
        
        # Verify Span was started
        mock_span.span.assert_called_once()
        print("✅ Span 'llm-generation' started")
        
        # Verify Span was ended
        mock_span.span.return_value.end.assert_called_once()
        print("✅ Span ended")

if __name__ == "__main__":
    asyncio.run(test_tracing_logic())
