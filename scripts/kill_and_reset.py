"""Kill old polling workers and reset webhook."""
import os
import signal
import subprocess
import asyncio
from dotenv import load_dotenv
from app.integrations.telegram import TelegramBot

load_dotenv()

def kill_old_workers():
    try:
        # Find pids
        pids = subprocess.check_output(["pgrep", "-f", "telegram_polling_worker.py"]).decode().split()
        my_pid = str(os.getpid())
        
        for pid in pids:
            if pid != my_pid:
                print(f"🔪 Killing old worker PID: {pid}")
                os.kill(int(pid), signal.SIGTERM)
    except subprocess.CalledProcessError:
        print("No old workers found.")

async def reset_webhook():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    bot = TelegramBot(bot_token=token)
    print("🧹 Deleting webhook...")
    try:
        await bot.delete_webhook()
        print("✅ Webhook deleted.")
    except Exception as e:
        print(f"❌ Delete failed: {e}")

if __name__ == "__main__":
    kill_old_workers()
    asyncio.run(reset_webhook())
