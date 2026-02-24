import asyncio
import sys
import os
from datetime import datetime

# Path setup
sys.path.append(os.getcwd())

from app.swarm.router.router import SwarmRouter
from app.gateway.schemas import InboundMessage
from app.swarm.llm import LLMClient
from config.settings import get_settings

async def run_audit():
    settings = get_settings()
    llm = LLMClient(settings.openai_api_key)
    router = SwarmRouter(llm)
    
    test_user = "dfrigewski@gmail.com"
    tenant_id = 2 # GetImpulse
    
    print("--- ARIIA GOLD-STANDARD AUDIT START ---")
    
    # PHASE 1: Info & Empathy
    print("
[PHASE 1: Beschwerde & Info]")
    q1 = "Ich bin echt sauer, die Duschen waren wieder eiskalt! Und was kostet eigentlich Premium?"
    print("USER: " + q1)
    res1 = await router.route(InboundMessage(message_id="a1", user_id=test_user, content=q1, platform="telegram", tenant_id=tenant_id))
    print("BOT: " + res1.content)
    
    # PHASE 2: Operations
    print("
[PHASE 2: Operations]")
    q2 = "Storniere mein Krafttraining heute um 14:30 Uhr."
    print("USER: " + q2)
    res2 = await router.route(InboundMessage(message_id="a2", user_id=test_user, content=q2, platform="telegram", tenant_id=tenant_id))
    print("BOT: " + res2.content)
    
    # PHASE 3: Memory & Motivation
    print("
[PHASE 3: Memory]")
    q3 = "Arnold, ich verliere die Motivation. Weißt du noch, warum ich mir den Marathon vorgenommen habe?"
    print("USER: " + q3)
    res3 = await router.route(InboundMessage(message_id="a3", user_id=test_user, content=q3, platform="telegram", tenant_id=tenant_id))
    print("BOT: " + res3.content)

if __name__ == "__main__":
    asyncio.run(run_audit())
