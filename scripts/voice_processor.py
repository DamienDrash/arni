import asyncio
import os
import sys
import structlog
from contextlib import suppress

# Add project root to path
sys.path.append(os.getcwd())

from app.gateway.redis_bus import RedisBus
from app.gateway.schemas import InboundMessage
from app.voice.pipeline import process_voice_message
from app.voice.tts import generate_voice_reply
from app.swarm.router.router import SwarmRouter
from app.swarm.llm import LLMClient
from app.integrations.telegram import TelegramBot
from config.settings import get_settings

logger = structlog.get_logger()

async def voice_processor():
    """Async Worker for processing Voice Messages from Redis Queue."""
    settings = get_settings()
    
    # 1. Setup Dependencies
    redis_bus = RedisBus(redis_url=settings.redis_url)
    llm_client = LLMClient(openai_api_key=settings.openai_api_key)
    swarm_router = SwarmRouter(llm=llm_client)
    telegram_bot = TelegramBot(
        bot_token=settings.telegram_bot_token,
        admin_chat_id=settings.telegram_admin_chat_id,
    )
    
    # 2. Connect
    await redis_bus.connect()
    logger.info("worker.voice.started", pid=os.getpid())

    try:
        while True:
            # 3. Blocking Pop from Queue
            # Timeout 1s to allow clean shutdown check
            item = await redis_bus.pop_from_queue(RedisBus.CHANNEL_VOICE_QUEUE, timeout=1)
            
            if not item:
                continue
                
            channel, data = item
            try:
                # 4. Parse Message
                message = InboundMessage.model_validate_json(data)
                logger.info("worker.job_received", message_id=message.message_id)

                # 5. STT (Speech-to-Text)
                # content is file_id here
                transcribed_data = await process_voice_message(message.content, telegram_bot)
                transcribed_text = transcribed_data.get("text", "")
                detected_lang = transcribed_data.get("language", "en")
                
                if not transcribed_text:
                    logger.wariiang("worker.stt_failed", message_id=message.message_id)
                    continue

                # Update Message
                message.content = transcribed_text
                message.metadata["original_type"] = "voice"
                message.metadata["user_language"] = detected_lang
                logger.info("worker.stt_success", text=transcribed_text, lang=detected_lang)

                # 6. AI Agent Routing
                result = await swarm_router.route(message)
                logger.info("worker.agent_reply", confidence=result.confidence)

                # 7. TTS (Text-to-Speech)
                if result.content:
                    voice_id = "de_thorsten" if detected_lang == "de" else "af_sarah"
                    logger.info("worker.tts_start", voice=voice_id)
                    
                    voice_path = await generate_voice_reply(result.content, voice=voice_id)
                    chat_id = message.metadata.get("chat_id", message.user_id)

                    if voice_path:
                        await telegram_bot.send_voice(chat_id, voice_path)
                        logger.info("worker.reply_sent_voice", to=chat_id)
                    else:
                        # Fallback to text
                        await telegram_bot.send_message(chat_id, result.content)
                        logger.wariiang("worker.reply_sent_text_fallback", to=chat_id)

            except Exception as e:
                logger.error("worker.job_failed", error=str(e))
                
    except asyncio.CancelledError:
        logger.info("worker.voice.stopping")
    finally:
        await redis_bus.disconnect()
        logger.info("worker.voice.stopped")

if __name__ == "__main__":
    try:
        asyncio.run(voice_processor())
    except KeyboardInterrupt:
        pass
