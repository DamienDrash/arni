"""Fix Telegram Webhook Configuration."""
import asyncio
import os
from dotenv import load_dotenv
from app.integrations.telegram import TelegramBot

load_dotenv()

async def fix_webhook():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    public_url = os.getenv("GATEWAY_PUBLIC_URL")
    
    if not token or not public_url:
        print("❌ Error: Missing TELEGRAM_BOT_TOKEN or GATEWAY_PUBLIC_URL in .env")
        return

    bot = TelegramBot(bot_token=token)
    webhook_url = f"{public_url}/webhook/telegram"
    
    print(f"🔄 Setting webhook to: {webhook_url}")
    
    try:
        # 1. Delete old
        await bot.delete_webhook()
        # 2. Set new
        res = await bot.set_webhook(webhook_url)
        print(f"✅ Webhook Result: {res}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(fix_webhook())
