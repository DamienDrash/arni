from app.gateway.persistence import persistence
from app.core.models import ChatSession
import sys

# Add project root to sys.path
sys.path.append("/root/.openclaw/workspace/ariia")

def list_users():
    print("🔍 Scanning DB for Telegram Users...")
    try:
        sessions = persistence.db.query(ChatSession).filter(ChatSession.platform == "telegram").all()
        if not sessions:
            print("❌ No Telegram users found in DB.")
        else:
            for s in sessions:
                print(f"✅ Found User: {s.user_id} (Active: {s.is_active})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_users()
