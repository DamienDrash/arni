"""Voice Processing Pipeline.

Provides VoicePipeline (stub-mode, for tests) and the production
process_voice_message / generate_voice_reply functions.
"""
import os
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import structlog

from app.voice.ingress import AudioFormat
from app.voice.stt import SpeechToText, TranscriptResult
from app.voice.tts import TextToSpeech, SpeechResult

logger = structlog.get_logger()

_TARGET_MS = 3000  # 3 s end-to-end target for voice pipeline


# ── Public test-friendly / stub-mode API ──────────────────────────────────────

@dataclass
class VoicePipelineResult:
    """Structured result from the full voice pipeline."""
    transcript: TranscriptResult
    response_text: str
    speech: SpeechResult
    total_duration_ms: int
    within_target: bool
    stages: dict = field(default_factory=dict)


class VoicePipeline:
    """Stub-mode end-to-end voice pipeline used by tests."""

    is_stub: bool = True

    async def process(
        self,
        audio_data: bytes,
        fmt: AudioFormat = AudioFormat.OGG,
        process_fn: Callable[[str], Awaitable[str]] | None = None,
    ) -> VoicePipelineResult:
        t0 = time.perf_counter()
        stages: dict[str, int] = {}

        # 1. Convert (stub — no real conversion needed)
        t1 = time.perf_counter()
        stages["convert"] = int((t1 - t0) * 1000)

        # 2. STT
        stt = SpeechToText()
        transcript = stt.transcribe(audio_data)
        t2 = time.perf_counter()
        stages["stt"] = int((t2 - t1) * 1000)

        # 3. Process (LLM call or stub)
        if process_fn is not None:
            response_text = await process_fn(transcript.text)
        else:
            response_text = f"Stub-Antwort auf: {transcript.text}"
        t3 = time.perf_counter()
        stages["process"] = int((t3 - t2) * 1000)

        # 4. TTS
        tts = TextToSpeech()
        speech = await tts.synthesize(response_text)
        t4 = time.perf_counter()
        stages["tts"] = int((t4 - t3) * 1000)

        total_ms = int((t4 - t0) * 1000)
        return VoicePipelineResult(
            transcript=transcript,
            response_text=response_text,
            speech=speech,
            total_duration_ms=max(1, total_ms),
            within_target=total_ms < _TARGET_MS,
            stages=stages,
        )


# ── Production API ────────────────────────────────────────────────────────────

from app.voice.stt import get_stt  # noqa: E402
from app.voice.tts import get_tts  # noqa: E402


async def process_voice_message(file_id: str, bot) -> dict:
    """Download and transcribe a Telegram voice message.
    
    Returns:
        Dict with keys: 'text', 'language', 'duration' (optional)
    """
    try:
        # 1. Get file path from Telegram
        file_info = await bot.get_file(file_id)
        remote_path = file_info.get("file_path")
        if not remote_path:
            logger.error("voice.pipeline.path_not_found", file_id=file_id)
            return {"text": "", "language": "en"}
        
        # 2. Download file
        logger.info("voice.pipeline.downloading", remote_path=remote_path)
        content = await bot.download_file(remote_path)
        
        # 3. Save to temp file
        # Telegram usually sends OGG Opus
        ext = remote_path.split(".")[-1]
        local_path = f"/tmp/{file_id}.{ext}"
        
        with open(local_path, "wb") as f:
            f.write(content)
            
        logger.info("voice.pipeline.saved", path=local_path, size=len(content))
        
        # 4. Transcribe
        stt = get_stt()
        # faster-whisper handles OGG/Opus directly via ffmpeg
        text, language = stt.transcribe(local_path)
        
        # 5. Cleanup
        if os.path.exists(local_path):
            os.remove(local_path)
            
        return {"text": text, "language": language}

    except Exception as e:
        logger.error("voice.pipeline.failed", error=str(e))
        return {"text": "", "language": "en"}

async def generate_voice_reply(text: str, voice: str = "af_sarah") -> str:
    """Generate OGG voice note from text.
    
    Args:
        text: Text to speak.
        voice: Voice ID (default: af_sarah). 
               Use 'de_thorsten' for German Piper.
    """
    try:
        # 1. Generate WAV (cached in TTS service)
        tts = get_tts()
        # Ensure we don't generate overly long audio for now
        if len(text) > 400: 
            text = text[:400] + "..." # Truncate for safety/speed in V1
            
        wav_path = tts.generate_audio(text, voice=voice)
        if not wav_path:
            return ""
        
        # 2. Convert to OGG (Voice Note format)
        # We start with the wav path
        ogg_path = wav_path.replace(".wav", ".ogg")
        
        if os.path.exists(ogg_path):
            return ogg_path
            
        # Convert using ffmpeg
        import ffmpeg
        logger.info("voice.pipeline.converting", src=wav_path, dst=ogg_path)
        try:
             stream = ffmpeg.input(wav_path)
             # Opus codec is standard for Telegram Voice Notes
             stream = ffmpeg.output(stream, ogg_path, acodec='libopus', audio_bitrate='32k')
             ffmpeg.run(stream, overwrite_output=True, quiet=True)
             return ogg_path
        except ffmpeg.Error as e:
            logger.error("voice.pipeline.ffmpeg_failed", error=str(e))
            return ""
            
    except Exception as e:
        logger.error("voice.pipeline.generation_failed", error=str(e))
        return ""
