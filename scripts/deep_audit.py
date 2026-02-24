import asyncio
import sys
import os
from datetime import datetime

sys.path.append(os.getcwd())

from app.swarm.router.router import SwarmRouter
from app.gateway.schemas import InboundMessage
from app.swarm.llm import LLMClient
from config.settings import get_settings

async def run():
    llm = LLMClient(get_settings().openai_api_key)
    router = SwarmRouter(llm)
    user = "dfrigewski@gmail.com"
    tid = 2
    
    conv = [
        "Arnold, ich habe heute beim Aufwachen starke Rückenschmerzen gespürt. Was steht eigentlich heute in meinem Trainingsplan?",
        "Das klingt nicht gut. Storniere bitte mein Krafttraining für heute und buche mir stattdessen Yoga für morgen um 10 Uhr.",
        "Danke. Sag mal, weißt du eigentlich noch, warum ich mir das alles antue? Ich verliere gerade echt die Motivation bei dem ganzen Stress hier (Spinde kaputt, Duschen kalt...)."
    ]
    
    print("--- DEEP AUDIT ---")
    for i, text in enumerate(conv):
        print("\nTURN " + str(i+1) + ": " + text)
        msg = InboundMessage(message_id="a"+str(i), user_id=user, content=text, platform="telegram", tenant_id=tid)
        res = await router.route(msg)
        print("BOT: " + res.content)

if __name__ == "__main__":
    asyncio.run(run())
