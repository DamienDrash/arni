from app.gateway.persistence import persistence
from app.core.models import ChatMessage
import sys
from sqlalchemy import desc

sys.path.append("/root/.openclaw/workspace/ariia")

def check_history():
    print("🔍 Checking Chat History for Telegram User 999888777...")
    try:
        # ChatMessage uses session_id to store user_id
        messages = persistence.db.query(ChatMessage).filter(
            ChatMessage.session_id == "999888777"
        ).order_by(desc(ChatMessage.timestamp)).all()
        
        if not messages:
            print("❌ No messages found for this user.")
        else:
            print(f"✅ Found {len(messages)} messages:")
            for m in messages:
                # We don't have platform on ChatMessage, but we can check role
                print(f"   [{m.timestamp}] {m.role}: {m.content}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_history()
