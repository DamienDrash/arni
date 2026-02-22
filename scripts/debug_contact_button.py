import asyncio
import os
import sys

# Add project root to path
sys.path.append("/root/.openclaw/workspace/arni")

from app.integrations.telegram import TelegramBot
from config.settings import get_settings
from dotenv import load_dotenv

load_dotenv("/root/.openclaw/workspace/arni/.env")

async def main():
    settings = get_settings()
    bot = TelegramBot(settings.telegram_bot_token)
    
    # Damien's ID from previous logs
    chat_id = "7473721797" 
    
    print(f"Token Loaded: {settings.telegram_bot_token[:5]}****")
    print(f"Base URL: {bot._base_url}")
    
    print(f"Sending Contact Request to {chat_id}...")
    
    try:
        # Manually constructing the payload to match what `send_contact_request` does
        # to ensure it works in isolation.
        res = await bot.send_contact_request(
            chat_id, 
            "⚠️ DEBUG TEST: Bitte unten auf den Button 'Nummer teilen' klicken."
        )
        print("Success!", res)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
