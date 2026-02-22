import asyncio
import os
import sys
import json
from uuid import uuid4

# Add project root to path
sys.path.append(os.getcwd())

from app.gateway.redis_bus import RedisBus
from app.gateway.schemas import InboundMessage, Platform
from config.settings import get_settings

async def test_voice_queue():
    settings = get_settings()
    redis_bus = RedisBus(redis_url=settings.redis_url)
    await redis_bus.connect()
    
    # 1. Clear Queue
    print("🧹 Clearing ariia:voice_queue...")
    while await redis_bus.pop_from_queue(RedisBus.CHANNEL_VOICE_QUEUE, timeout=1):
        pass

    # 2. Push Mock Voice Message
    msg = InboundMessage(
        message_id=str(uuid4()),
        platform=Platform.TELEGRAM,
        user_id="test_user",
        content="mock_file_id_123", # content is file_id for voice
        content_type="voice",
        metadata={"original_type": "voice", "chat_id": "7473721797"}
    )
    
    print(f"📤 Pushing message {msg.message_id} to queue...")
    await redis_bus.push_to_queue(RedisBus.CHANNEL_VOICE_QUEUE, msg.model_dump_json())
    
    # 3. Check if it's there
    # We can't easily peak without popping in simple redis, but length check works
    # client = redis_bus.client
    # length = await client.llen(RedisBus.CHANNEL_VOICE_QUEUE)
    # print(f"✅ Queue length: {length}")

    await redis_bus.disconnect()
    print("🚀 Done. Now run 'python3 scripts/voice_processor.py' to see if it processes!")

if __name__ == "__main__":
    asyncio.run(test_voice_queue())
