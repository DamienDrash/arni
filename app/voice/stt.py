"""Speech-to-Text Service using faster-whisper.

Handles transcription of audio files (wav, ogg, mp3) to text.
Exposes SpeechToText (stub-mode, used by tests / no-model environments)
and STTService (production, requires faster-whisper model files).
"""
import os
import time
from dataclasses import dataclass

import structlog
from faster_whisper import WhisperModel

logger = structlog.get_logger()


# ── Public test-friendly / stub-mode API ──────────────────────────────────────

@dataclass
class TranscriptResult:
    """Structured result from speech-to-text transcription."""
    text: str
    language: str
    confidence: float
    source: str
    duration_ms: int = 0


class SpeechToText:
    """Stub-mode STT engine used by tests and no-model environments.

    Always starts in stub mode (is_stub=True). A future production subclass
    can override is_stub and load a real model.
    """

    is_stub: bool = True

    def transcribe(self, audio_data: bytes) -> TranscriptResult:
        t0 = time.perf_counter()
        # Stub: return a deterministic placeholder transcript
        result = TranscriptResult(
            text=f"Stub-Transkription: {len(audio_data)} Bytes Audio empfangen.",
            language="de",
            confidence=0.99,
            source="stub",
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        return result


# ── Production API ────────────────────────────────────────────────────────────

class STTService:
    def __init__(self, model_size="medium", device="cpu", compute_type="int8"):
        """Initialize Whisper model.
        
        Args:
            model_size: 'tiny', 'base', 'small', 'medium', 'large-v2'
            device: 'cpu' or 'cuda' (use 'cpu' for dev container)
            compute_type: 'int8', 'float16', 'float32'
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        
        logger.info("stt.loading_model", model=model_size, device=device)
        try:
            # Download and load model
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("stt.model_loaded")
        except Exception as e:
            logger.error("stt.load_failed", error=str(e))
            raise

    def transcribe(self, file_path: str) -> tuple[str, str]:
        """Transcribe audio file to text.
        
        Returns:
            Tuple of (transcribed_text, detected_language_code).
        """
        if not os.path.exists(file_path):
            logger.error("stt.file_not_found", path=file_path)
            return "", "en"

        try:
            logger.info("stt.transcribing", path=file_path)
            # Tune parameters for short voice commands
            segments, info = self.model.transcribe(
                file_path, 
                beam_size=5,
                condition_on_previous_text=False,  # Prevent hallucinations
                initial_prompt="Hallo, hier ist eine Nachricht.",  # German bias
                no_speech_threshold=0.6
            )
            
            # Segments is a generator, so consume it
            text_segments = []
            for segment in segments:
                text_segments.append(segment.text)
                
            full_text = " ".join(text_segments).strip()
            
            logger.info("stt.success", 
                        path=file_path, 
                        language=info.language, 
                        prob=info.language_probability,
                        text_len=len(full_text))
            return full_text, info.language
            
        except Exception as e:
            logger.error("stt.transcription_failed", error=str(e))
            return "", "en"

# Singleton management
_service = None

def get_stt() -> STTService:
    global _service
    if _service is None:
        # Defaults for dev environment (int8 cpu is fast enough for testing)
        # Use 'small' or 'medium' depending on RAM availability. 
        # 'medium' is better for German but heavy (1.5GB VRAM/RAM).
        # 'small' is ~500MB. Let's start with 'small' for safety in dev container.
        _service = STTService(model_size="small")
    return _service
