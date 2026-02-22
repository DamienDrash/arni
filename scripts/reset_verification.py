import sys
import os

# Add project root to path (adjusted)
project_root = "/root/.openclaw/workspace/arni"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.db import SessionLocal
from app.core.models import ChatSession

def reset_verification():
    db = SessionLocal()
    try:
        # Default test user ID from previous logs
        user_id = "7473721797" 
        
        session = db.query(ChatSession).filter(ChatSession.user_id == user_id).first()
        if session:
            print(f"Found session for {user_id}. Resetting...")
            session.member_id = None
            session.phone_number = None
            session.email = None
            # Keep user_name as is
            db.commit()
            print("✅ Verification data cleared.")
        else:
            print(f"❌ Session for {user_id} not found.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_verification()
