import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.gateway.schemas import InboundMessage
from app.swarm.llm import LLMClient
from app.swarm.router.router import SwarmRouter
from app.swarm.router.intents import Intent
from config.settings import get_settings

async def test_handoff_routing():
    print("🛡️ Testing Human Handoff Routing...")
    
    settings = get_settings()
    llm = LLMClient(openai_api_key=settings.openai_api_key)
    router = SwarmRouter(llm=llm)

    test_phrases = [
        "Ich will einen Menschen sprechen",
        "Gib mir einen Mitarbeiter",
        "Support bitte!",
        "Ich will den Admin",
        "Das ist mir zu blöd, gib mir jemanden echten"
    ]

    for phrase in test_phrases:
        print(f"\n🗣️ User: '{phrase}'")
        msg = InboundMessage(
            message_id="test-handoff",
            platform="telegram",
            user_id="tester",
            content=phrase,
            metadata={}
        )
        
        # Test Classification (Accessing private method for debug/test)
        intent, conf = await router._classify(phrase)
        print(f"🎯 Intent: {intent.value} ({conf})")
        
        if intent == Intent.HUMAN_HANDOFF:
             print("✅ Classification PASS")
        else:
             print("❌ Classification FAIL")

        # Test Routing Response
        response = await router.route(msg)
        if response.metadata and response.metadata.get("handoff"):
             print("✅ Metadata PASS: handoff=True")
             print(f"🤖 Response: {response.content}")
        else:
             print("❌ Metadata FAIL: No handoff flag")

if __name__ == "__main__":
    asyncio.run(test_handoff_routing())
