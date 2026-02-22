"""Test Telegram Outbound Message."""
import asyncio
import os
from dotenv import load_dotenv
from app.integrations.telegram import TelegramBot

load_dotenv()

async def test_send():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ Error: Missing credentials in .env")
        return

    print(f"🚀 Sending test message to {chat_id}...")
    bot = TelegramBot(bot_token=token)
    
    try:
        await bot.send_message(chat_id, "👋 Hallo! Hier ist ARNI. Test-Nachricht erfolgreich.")
        print("✅ Message sent!")
    except Exception as e:
        print(f"❌ Failed to send: {e}")

if __name__ == "__main__":
    asyncio.run(test_send())
