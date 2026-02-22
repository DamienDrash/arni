import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.gateway.schemas import InboundMessage
from app.swarm.agents.persona import AgentPersona
from app.swarm.llm import LLMClient
from app.knowledge.store import KnowledgeStore
from config.settings import get_settings

async def test_rag():
    print("🧠 Testing Knowledge Base (RAG)...")
    
    # 1. Check Store
    store = KnowledgeStore()
    count = store.count()
    print(f"📊 Documents in Store: {count}")
    if count == 0:
        print("❌ Store empty! Run 'python app/knowledge/ingest.py' first.")
        return

    # 2. Setup Agent
    settings = get_settings()
    llm = LLMClient(openai_api_key=settings.openai_api_key)
    AgentPersona.set_llm(llm)
    agent = AgentPersona()

    # 3. Test Scenarios
    scenarios = [
        ("Was kostet der Premium Tarif?", "39,90"),
        ("Habe ich eine Getränkeflatrate im Standard?", "inklusive"),
        ("Darf ich mein eigenes Handtuch vergessen?", "Pflicht"),
        ("Wie lange habt ihr am Sonntag auf?", "22:00")
    ]

    for question, expected_keyword in scenarios:
        print(f"\n❓ User: '{question}'")
        msg = InboundMessage(
            message_id="test-rag",
            platform="telegram",
            user_id="tester",
            content=question,
            metadata={} # Fixed pydantic validation
        )
        
        response = await agent.handle(msg)
        print(f"🤖 Arni: {response.content}")
        
        # Verify
        if expected_keyword.lower() in response.content.lower():
            print(f"✅ PASS: Found '{expected_keyword}'")
        else:
            print(f"⚠️ WARN: Keyword '{expected_keyword}' not found. Check output.")

if __name__ == "__main__":
    asyncio.run(test_rag())
