import asyncio
import os
import sys
import json

# Ensure app is in path
sys.path.append(os.getcwd())

from app.gateway.persistence import persistence
from app.gateway.redis_bus import RedisBus

async def probe():
    print("🔍 Starting Debug Probe...")

    # 1. Verify Code Content matches expectation
    print("\n--- Code Verification ---")
    try:
        with open("app/gateway/admin.py", "r") as f:
            content = f.read()
            if "admin.token_autogen" in content:
                print("✅ admin.py contains token_autogen logic")
            else:
                print("❌ admin.py MISSING token_autogen logic")
        
        with open("app/gateway/main.py", "r") as f:
            content = f.read()
            if "gateway.verification.attempting_match" in content:
                print("✅ main.py contains debug logging")
            else:
                print("❌ main.py MISSING debug logging")
    except Exception as e:
        print(f"❌ Failed to read files: {e}")

    # 2. Check DB Session
    print("\n--- DB Session Check ---")
    
    # Force DB sync
    persistence.db.commit()
    
    sessions = persistence.get_recent_sessions(10)
    target_session = None
    for s in sessions:
        print(f"  User: {s.user_id} | Member: {s.member_id} | Active: {s.is_active} | Last: {s.last_message_at}")
        if s.user_id == "7473721797":
            target_session = s

    if not target_session:
        print("⚠️ User 7473721797 not found in recent sessions (is_active=True). Checking all...")
        # Check by ID directly
        s = persistence.get_session_by_user_id("7473721797")
        if s:
             print(f"  [Direct] User: {s.user_id} | Member: {s.member_id} | Active: {s.is_active}")
        else:
             print("  ❌ User 7473721797 does not exist in DB.")

    # 3. Check Redis Token
    print("\n--- Redis Token Check ---")
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    bus = RedisBus(redis_url=redis_url)
    await bus.connect()
    
    token_val = await bus.client.get("user_token:7473721797")
    if token_val:
        print(f"✅ Redis has token for user: {token_val}")
    else:
        print("❌ Redis has NO token for user.")
        
    await bus.disconnect()
    print("\nProbe Complete.")

if __name__ == "__main__":
    asyncio.run(probe())
