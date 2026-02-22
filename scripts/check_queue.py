import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.gateway.redis_bus import RedisBus
from config.settings import get_settings

async def check_queue():
    settings = get_settings()
    redis_bus = RedisBus(redis_url=settings.redis_url)
    await redis_bus.connect()
    
    client = redis_bus.client
    length = await client.llen(RedisBus.CHANNEL_VOICE_QUEUE)
    print(f"📊 Queue Length: {length}")
    
    if length > 0:
        # Peak first item
        item = await client.lrange(RedisBus.CHANNEL_VOICE_QUEUE, 0, 0)
        print(f"📥 First Item: {item[0]}")

    await redis_bus.disconnect()

if __name__ == "__main__":
    asyncio.run(check_queue())
