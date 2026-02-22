"""Text-to-Speech Service using Kokoro-82M (English) and Piper (German).

Generates audio files from text using local inference.
- English: Kokoro-82M (ONNX)
- German: Piper (Thorsten-High ONNX)

Also exposes TextToSpeech (stub-mode) and SpeechResult for tests and
environments without model files.
"""
import os
import hashlib
import struct
import time
import wave
from dataclasses import dataclass

import structlog
# Kokoro
from kokoro_onnx import Kokoro
from app.voice.models import MODEL_PATH, VOICES_PATH
# Piper
from piper import PiperVoice
from app.voice.text_cleaner import clean_text_for_tts

logger = structlog.get_logger()


# ── Public test-friendly / stub-mode API ──────────────────────────────────────

@dataclass
class SpeechResult:
    """Structured result from text-to-speech synthesis."""
    audio_data: bytes
    text_length: int
    duration_ms: int
    voice_id: str
    source: str


def _minimal_wav() -> bytes:
    """Return a minimal valid 44-byte WAV header with no audio data."""
    return (
        b"RIFF"
        + struct.pack("<I", 36)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, 8000, 16000, 2, 16)
        + b"data"
        + struct.pack("<I", 0)
    )


class TextToSpeech:
    """Stub-mode TTS engine used by tests and no-model environments."""

    is_stub: bool = True

    async def synthesize(self, text: str, voice_id: str = "stub") -> SpeechResult:
        t0 = time.perf_counter()
        audio = _minimal_wav()
        return SpeechResult(
            audio_data=audio,
            text_length=len(text),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            voice_id=voice_id,
            source="stub",
        )


# ── Production API ────────────────────────────────────────────────────────────

# Constants
MODEL_DIR = "app/voice/models"
# Kokoro (English)
KOKORO_MODEL = os.path.join(MODEL_DIR, "kokoro-v0_19.onnx")
KOKORO_VOICES = os.path.join(MODEL_DIR, "voices.npz")
# Piper (German)
PIPER_MODEL = os.path.join(MODEL_DIR, "de_DE-thorsten-high.onnx")
PIPER_CONFIG = os.path.join(MODEL_DIR, "de_DE-thorsten-high.json")

CACHE_DIR = "/tmp/tts_cache"

class TTSService:
    def __init__(self):
        """Initialize TTS Engines (Lazy Loading)."""
        self._kokoro = None
        self._piper = None
        
        # Ensure cache dir
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)

    @property
    def kokoro(self) -> Kokoro:
        """Lazy load Kokoro model (English)."""
        if self._kokoro is None:
            if not os.path.exists(KOKORO_MODEL) or not os.path.exists(KOKORO_VOICES):
                raise FileNotFoundError(f"Kokoro model files not found in {MODEL_DIR}")
            
            logger.info("tts.loading.kokoro", path=KOKORO_MODEL)
            try:
                self._kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
                logger.info("tts.loaded.kokoro")
            except Exception as e:
                logger.error("tts.load.kokoro.failed", error=str(e))
                raise
        return self._kokoro

    @property
    def piper_german(self) -> PiperVoice:
        """Lazy load Piper model (German)."""
        if self._piper is None:
            if not os.path.exists(PIPER_MODEL) or not os.path.exists(PIPER_CONFIG):
                # Fallback to Kokoro if Piper missing? Or raise?
                # For now raise, as we expect it installed.
                logger.error("tts.piper.missing", model=PIPER_MODEL, config=PIPER_CONFIG)
                raise FileNotFoundError("Piper German model files missing")
            
            logger.info("tts.loading.piper", path=PIPER_MODEL)
            try:
                # Load Piper
                self._piper = PiperVoice.load(PIPER_MODEL, config_path=PIPER_CONFIG)
                logger.info("tts.loaded.piper")
            except Exception as e:
                logger.error("tts.load.piper.failed", error=str(e))
                raise
        return self._piper

    def generate_audio(self, text: str, voice: str = "af_sarah") -> str:
        """Generate audio from text.
        
        Args:
            text: Text to speak.
            voice: Voice ID.
                   - If 'de_thorsten' or starts with 'de_' -> Use Piper (German).
                   - Else -> Use Kokoro (English/Default).
            
        Returns:
            Path to generated .wav file.
        """
        if not text:
            return ""

        # Language Detection / Routing
        is_german = voice.startswith("de_") or "thorsten" in voice
        engine_name = "piper" if is_german else "kokoro"
        lang_code = "de" if is_german else "en"

        # US-11.5: Text Cleaning (Emoji removal, Time normalization)
        text = clean_text_for_tts(text, lang=lang_code)
        
        if not text.strip():
            logger.wariiang("tts.empty_after_clean", original_len=len(text))
            return ""

        # Cache content based on CLEANED text
        cache_key = hashlib.md5(f"{text}_{voice}_{engine_name}".encode()).hexdigest()
        output_path = os.path.join(CACHE_DIR, f"{cache_key}.wav")

        if os.path.exists(output_path):
            logger.info("tts.cache_hit", engine=engine_name, text_preview=text[:20])
            return output_path

        start_time = time.time()
        try:
            logger.info("tts.generating", engine=engine_name, text_len=len(text), voice=voice)
            
            if is_german:
                # PIPER GENERATION
                with wave.open(output_path, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(self.piper_german.config.sample_rate)
                    # Iterate over generator
                    for audio_chunk in self.piper_german.synthesize(text):
                        wav_file.writeframes(audio_chunk.audio_int16_bytes)
            else:
                # KOKORO GENERATION
                import soundfile as sf
                # Kokoro.create(text, voice, speed, lang)
                # Defaults: speed=1.0, lang='en-us'
                samples, sample_rate = self.kokoro.create(
                    text, 
                    voice=voice if voice in ["af_sarah", "bf_emma"] else "af_sarah", 
                    speed=1.0, 
                    lang="en-us"
                )
                sf.write(output_path, samples, sample_rate)
            
            duration = time.time() - start_time
            logger.info("tts.generated", duration=f"{duration:.2f}s", path=output_path)
            
            return output_path
            
        except Exception as e:
            logger.error("tts.generation_failed", error=str(e))
            return ""

# Singleton
_service = None

def get_tts() -> TTSService:
    global _service
    if _service is None:
        _service = TTSService()
    return _service

# Wrapper for main.py compatibility (Async to match interface expected by main.py)
import asyncio

async def generate_voice_reply(text: str, voice: str = "af_sarah") -> str:
    """Generate audio reply asynchronously."""
    tts = get_tts()
    loop = asyncio.get_event_loop()
    
    # Run in executor
    wav_path = await loop.run_in_executor(None, tts.generate_audio, text, voice)
    
    # Convert to OGG (Telegram requirement)
    if wav_path and os.path.exists(wav_path):
        ogg_path = wav_path.replace(".wav", ".ogg")
        if not os.path.exists(ogg_path):
             # Simple ffmpeg conversion
             import subprocess
             # -y overwrite, -i input, -c:a libopus (codec), -b:a 32k (bitrate)
             cmd = f"ffmpeg -y -v error -i {wav_path} -c:a libopus -b:a 24k {ogg_path}"
             subprocess.run(cmd, shell=True)
             
        return ogg_path
    return ""
