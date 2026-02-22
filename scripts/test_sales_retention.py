import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from app.swarm.agents.sales import AgentSales
from app.gateway.schemas import InboundMessage, Platform
from app.swarm.tools import magicline
from app.swarm.llm import LLMClient
from config.settings import get_settings

# Mock Magicline Tools
original_get_checkin_stats = magicline.get_checkin_stats
original_get_member_status = magicline.get_member_status

async def test_sales_retention():
    # Setup LLM
    settings = get_settings()
    llm = LLMClient(openai_api_key=settings.openai_api_key)
    AgentSales.set_llm(llm)
    
    agent = AgentSales()
    print("📉 Testing Sales Agent CRM Retention Logic...\n")

    # --- Scenario 1: Inactive User (>30 days) ---
    print("--- [1] Scenario: Inactive User (Last visit 45 days ago) ---")
    
    # Mock return value for Inactive
    magicline.get_checkin_stats = MagicMock(return_value=(
        "Statistik für Daniel (letzte 90 Tage):\n"
        "- Besuche gesamt: 2\n"
        "- Ø Besuche/Woche: 0.2\n"
        "- Letzter Besuch: 2026-01-01 (vor 45 Tagen)\n"
        "- Status: INAKTIV ⚠️"
    ))
    magicline.get_member_status = MagicMock(return_value="Mitglied Daniel: Aktiv (Standard).")

    msg = InboundMessage(
        message_id="test-msg-1",
        platform=Platform.TELEGRAM,
        user_id="test_user",
        content="Wie oft war ich eigentlich in letzter Zeit da?"
    )
    
    response = await agent.handle(msg)
    print(f"🤖 Agent: {response.content}")
    
    if "trainer" in response.content.lower() or "check-up" in response.content.lower():
        print("✅ PASS: Agent suggested Trainer/Check-Up.")
    else:
        print("❌ FAIL: Agent did NOT suggest Trainer.")
        
    if "rabatt" in response.content.lower() or "ruhemonat" in response.content.lower():
         print("❌ FAIL: Agent offered forbidden discount/pause!")
    else:
         print("✅ PASS: No forbidden offers.")


    # --- Scenario 2: Active User (>2x week) ---
    print("\n--- [2] Scenario: Active User (3.5x week) ---")
    
    # Mock return value for Active
    magicline.get_checkin_stats = MagicMock(return_value=(
        "Statistik für Daniel (letzte 90 Tage):\n"
        "- Besuche gesamt: 45\n"
        "- Ø Besuche/Woche: 3.5\n"
        "- Letzter Besuch: 2026-02-14 (vor 1 Tag)\n"
        "- Status: AKTIV ✅"
    ))

    msg = InboundMessage(
        message_id="test-msg-2",
        platform=Platform.TELEGRAM,
        user_id="test_user",
        content="Lohnt sich mein Vertrag überhaupt noch?"
    )
    
    response = await agent.handle(msg)
    print(f"🤖 Agent: {response.content}")
    
    if "premium" in response.content.lower() or "upgrade" in response.content.lower():
        print("✅ PASS: Agent suggested Premium/Upgrade.")
    else:
        print("❌ FAIL: Agent did NOT suggest Upgrade.")

    # Cleanup
    magicline.get_checkin_stats = original_get_checkin_stats
    magicline.get_member_status = original_get_member_status

if __name__ == "__main__":
    asyncio.run(test_sales_retention())
