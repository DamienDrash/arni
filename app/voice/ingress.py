"""ARIIA v1.4 – Audio Ingress.

@BACKEND: Sprint 5b, Task 5b.2
Download + convert voice messages from WhatsApp/Telegram.
"""

from __future__ import annotations

import shutil
import subprocess
from enum import Enum
from pathlib import Path

import structlog

logger = structlog.get_logger()

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


class AudioFormat(str, Enum):
    """Supported audio formats."""
    OGG = "ogg"
    MP3 = "mp3"
    WAV = "wav"
    WEBM = "webm"
    M4A = "m4a"


class AudioIngress:
    """Voice message download and conversion pipeline.

    Converts various audio formats (OGG, MP3, WEBM, M4A)
    to WAV for Whisper STT processing.
    Auto-detects ffmpeg availability → passthrough for WAV.
    """

    def __init__(self) -> None:
        self._ffmpeg_available = FFMPEG_AVAILABLE
        if not self._ffmpeg_available:
            logger.wariiang("voice.ffmpeg_unavailable", msg="ffmpeg not found, conversion disabled")

    @property
    def has_ffmpeg(self) -> bool:
        return self._ffmpeg_available

    def convert_to_wav(self, audio_data: bytes, source_format: AudioFormat) -> bytes:
        """Convert audio data to WAV format.

        Args:
            audio_data: Raw audio bytes.
            source_format: Original audio format.

        Returns:
            WAV-encoded audio bytes.
        """
        if source_format == AudioFormat.WAV:
            return audio_data

        if not self._ffmpeg_available:
            logger.wariiang("voice.conversion_skipped", reason="no ffmpeg")
            return audio_data

        return self._ffmpeg_convert(audio_data, source_format)

    def _ffmpeg_convert(self, audio_data: bytes, source_format: AudioFormat) -> bytes:
        """Convert audio via ffmpeg subprocess."""
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-i", "pipe:0",
                    "-f", "wav",
                    "-ar", "16000",  # 16kHz sample rate (Whisper optimal)
                    "-ac", "1",  # Mono
                    "-acodec", "pcm_s16le",
                    "pipe:1",
                ],
                input=audio_data,
                capture_output=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error("voice.ffmpeg_error", stderr=result.stderr[:200].decode(errors="replace"))
                return audio_data

            logger.debug(
                "voice.converted",
                from_format=source_format.value,
                input_size=len(audio_data),
                output_size=len(result.stdout),
            )
            return result.stdout

        except subprocess.TimeoutExpired:
            logger.error("voice.ffmpeg_timeout")
            return audio_data
        except Exception as e:
            logger.error("voice.conversion_failed", error=str(e))
            return audio_data

    def detect_format(self, filename: str) -> AudioFormat:
        """Detect audio format from filename.

        Args:
            filename: Original filename or URL.

        Returns:
            Detected AudioFormat.
        """
        ext = Path(filename).suffix.lower().lstrip(".")
        format_map = {
            "ogg": AudioFormat.OGG,
            "oga": AudioFormat.OGG,
            "opus": AudioFormat.OGG,
            "mp3": AudioFormat.MP3,
            "wav": AudioFormat.WAV,
            "webm": AudioFormat.WEBM,
            "m4a": AudioFormat.M4A,
        }
        return format_map.get(ext, AudioFormat.OGG)
