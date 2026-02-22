from app.gateway.persistence import persistence
from app.core.models import ChatSession
import sys

sys.path.append("/root/.openclaw/workspace/arni")

def fix_platforms():
    print("🛠 Fixing ChatSession platforms...")
    sessions = persistence.db.query(ChatSession).all()
    count = 0
    for s in sessions:
        if s.platform == "Platform.TELEGRAM":
            print(f"   -> Fixing {s.user_id}: 'Platform.TELEGRAM' -> 'telegram'")
            s.platform = "telegram"
            count += 1
        elif s.platform == "Platform.WHATSAPP":
            print(f"   -> Fixing {s.user_id}: 'Platform.WHATSAPP' -> 'whatsapp'")
            s.platform = "whatsapp"
            count += 1
            
    if count > 0:
        persistence.db.commit()
        print(f"✅ Fixed {count} sessions.")
    else:
        print("✅ No fixes needed.")

if __name__ == "__main__":
    fix_platforms()
