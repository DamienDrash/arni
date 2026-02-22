from app.gateway.persistence import persistence
from app.core.models import ChatSession
import sys

sys.path.append("/root/.openclaw/workspace/arni")

def check_sessions():
    print("🔍 Checking Chat Sessions...")
    sessions = persistence.db.query(ChatSession).all()
    for s in sessions:
        print(f"User: {s.user_id} | Name: '{s.user_name}' | Phone: '{s.phone_number}' | Platform: '{s.platform}'")

if __name__ == "__main__":
    check_sessions()
