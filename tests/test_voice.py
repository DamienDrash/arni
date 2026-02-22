"""ARNI v1.4 – Voice Module Tests.

@QA: Sprint 5b, Task 5b.5
Tests: STT, Ingress, TTS, Pipeline.
"""

import pytest

from app.voice.stt import SpeechToText, TranscriptResult
from app.voice.ingress import AudioIngress, AudioFormat
from app.voice.tts import TextToSpeech, SpeechResult
from app.voice.pipeline import VoicePipeline, VoicePipelineResult


# ──────────────────────────────────────────
# Speech-to-Text Tests
# ──────────────────────────────────────────


class TestSpeechToText:
    """Tests for Whisper STT engine."""

    def test_stt_starts_in_stub_mode(self) -> None:
        stt = SpeechToText()
        assert stt.is_stub is True

    def test_stub_transcribe(self) -> None:
        stt = SpeechToText()
        result = stt.transcribe(b"fake-audio")
        assert isinstance(result, TranscriptResult)
        assert result.source == "stub"
        assert result.language == "de"
        assert result.confidence > 0

    def test_stub_transcribe_has_text(self) -> None:
        stt = SpeechToText()
        result = stt.transcribe(b"audio-data")
        assert len(result.text) > 0
        assert "Stub" in result.text

    def test_stub_transcribe_duration(self) -> None:
        stt = SpeechToText()
        result = stt.transcribe(b"data")
        assert result.duration_ms >= 0


# ──────────────────────────────────────────
# Audio Ingress Tests
# ──────────────────────────────────────────


class TestAudioIngress:
    """Tests for audio format conversion."""

    def test_wav_passthrough(self) -> None:
        ingress = AudioIngress()
        data = b"RIFF" + b"\x00" * 40  # fake WAV
        result = ingress.convert_to_wav(data, AudioFormat.WAV)
        assert result == data  # No conversion needed

    def test_detect_format_ogg(self) -> None:
        ingress = AudioIngress()
        assert ingress.detect_format("voice.ogg") == AudioFormat.OGG

    def test_detect_format_mp3(self) -> None:
        ingress = AudioIngress()
        assert ingress.detect_format("message.mp3") == AudioFormat.MP3

    def test_detect_format_wav(self) -> None:
        ingress = AudioIngress()
        assert ingress.detect_format("audio.wav") == AudioFormat.WAV

    def test_detect_format_webm(self) -> None:
        ingress = AudioIngress()
        assert ingress.detect_format("recording.webm") == AudioFormat.WEBM

    def test_detect_format_m4a(self) -> None:
        ingress = AudioIngress()
        assert ingress.detect_format("voice.m4a") == AudioFormat.M4A

    def test_detect_format_opus(self) -> None:
        ingress = AudioIngress()
        assert ingress.detect_format("voice.opus") == AudioFormat.OGG

    def test_detect_format_unknown(self) -> None:
        ingress = AudioIngress()
        assert ingress.detect_format("file.xyz") == AudioFormat.OGG  # default

    def test_has_ffmpeg_property(self) -> None:
        ingress = AudioIngress()
        assert isinstance(ingress.has_ffmpeg, bool)


# ──────────────────────────────────────────
# Text-to-Speech Tests
# ──────────────────────────────────────────


class TestTextToSpeech:
    """Tests for TTS engine."""

    def test_tts_starts_in_stub_mode(self) -> None:
        tts = TextToSpeech()
        assert tts.is_stub is True

    @pytest.mark.anyio
    async def test_stub_synthesize(self) -> None:
        tts = TextToSpeech()
        result = await tts.synthesize("Hallo, wie geht es dir?")
        assert isinstance(result, SpeechResult)
        assert result.source == "stub"
        assert len(result.audio_data) > 0

    @pytest.mark.anyio
    async def test_stub_generates_valid_wav(self) -> None:
        tts = TextToSpeech()
        result = await tts.synthesize("Test")
        # WAV starts with RIFF header
        assert result.audio_data[:4] == b"RIFF"

    @pytest.mark.anyio
    async def test_stub_records_text_length(self) -> None:
        tts = TextToSpeech()
        text = "Hallo Welt"
        result = await tts.synthesize(text)
        assert result.text_length == len(text)

    @pytest.mark.anyio
    async def test_stub_duration(self) -> None:
        tts = TextToSpeech()
        result = await tts.synthesize("Test")
        assert result.duration_ms >= 0

    @pytest.mark.anyio
    async def test_custom_voice_id(self) -> None:
        tts = TextToSpeech()
        result = await tts.synthesize("Hi", voice_id="custom-voice-123")
        assert result.voice_id == "custom-voice-123"


# ──────────────────────────────────────────
# Voice Pipeline Tests
# ──────────────────────────────────────────


class TestVoicePipeline:
    """Tests for end-to-end voice pipeline."""

    def test_pipeline_starts_in_stub_mode(self) -> None:
        pipeline = VoicePipeline()
        assert pipeline.is_stub is True

    @pytest.mark.anyio
    async def test_e2e_pipeline_stub(self) -> None:
        pipeline = VoicePipeline()
        result = await pipeline.process(b"fake-audio", AudioFormat.OGG)
        assert isinstance(result, VoicePipelineResult)
        assert result.transcript.text
        assert result.response_text
        assert len(result.speech.audio_data) > 0

    @pytest.mark.anyio
    async def test_pipeline_within_target(self) -> None:
        pipeline = VoicePipeline()
        result = await pipeline.process(b"audio")
        # Stub mode should be very fast
        assert result.within_target is True

    @pytest.mark.anyio
    async def test_pipeline_has_stages(self) -> None:
        pipeline = VoicePipeline()
        result = await pipeline.process(b"audio")
        assert "convert" in result.stages
        assert "stt" in result.stages
        assert "process" in result.stages
        assert "tts" in result.stages

    @pytest.mark.anyio
    async def test_pipeline_custom_process_fn(self) -> None:
        pipeline = VoicePipeline()

        async def custom_fn(text: str) -> str:
            return f"Antwort auf: {text}"

        result = await pipeline.process(b"audio", process_fn=custom_fn)
        assert "Antwort auf:" in result.response_text

    @pytest.mark.anyio
    async def test_pipeline_total_duration(self) -> None:
        pipeline = VoicePipeline()
        result = await pipeline.process(b"audio")
        assert result.total_duration_ms > 0
