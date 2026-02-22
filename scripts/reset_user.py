import asyncio
import os
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

from app.gateway.persistence import persistence
from app.gateway.redis_bus import RedisBus

USER_ID = "7473721797"

async def reset_user():
    print(f"🔄 Resetting User: {USER_ID}")
    
    # 1. Reset DB (History, Verification, Contact)
    # persistence.reset_chat handles session expiration and deletion
    result = persistence.reset_chat(
        USER_ID, 
        clear_verification=True, 
        clear_contact=True, 
        clear_history=True
    )
    print(f"✅ DB Reset: {result}")

    # 2. Reset Redis (Tokens, Active Session State)
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0") # Default to docker service name
    bus = RedisBus(redis_url=redis_url)
    await bus.connect()
    
    # Delete specific keys
    keys_to_delete = [
        f"user_token:{USER_ID}",
        f"session:{USER_ID}",
        f"session:{USER_ID}:human_mode"
    ]
    
    # Find active tokens (reverse lookup is hard, so we just scan)
    # In a real prod environment, do not use KEYS, but here it's fine for a script
    all_tokens = await bus.client.keys("token:*")
    for k in all_tokens:
        val = await bus.client.get(k)
        if val and USER_ID.encode() in val:
            keys_to_delete.append(k.decode("utf-8"))
            print(f"found token key to delete: {k}")

    if keys_to_delete:
        await bus.client.delete(*keys_to_delete)
        print(f"✅ Redis Keys Deleted: {keys_to_delete}")
    else:
        print("ℹ️ No Redis keys found to delete.")

    await bus.disconnect()
    print("🚀 Reset Complete. User is now 'New'.")

if __name__ == "__main__":
    asyncio.run(reset_user())
