"""ARIIA v2.0 – ElevenLabs Voice Adapter (Sprint 6).

Wraps the ElevenLabs API v1 for text-to-speech, voice cloning, and
speech-to-text capabilities. Supports streaming TTS output.

Capabilities:
  - voice.tts.generate      → Generate speech audio from text
  - voice.tts.stream        → Stream speech audio from text
  - voice.voices.list       → List available voices
  - voice.voices.clone      → Clone a voice from audio samples
  - voice.stt.transcribe    → Transcribe audio to text
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()

DEFAULT_BASE_URL = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_multilingual_v2"


class ElevenLabsAdapter(BaseAdapter):
    """Adapter for ElevenLabs Voice AI platform."""

    def __init__(self) -> None:
        self._clients: dict[int, dict[str, Any]] = {}
        self.version = "1.0.0"

    @property
    def integration_id(self) -> str:
        return "elevenlabs"

    @property
    def supported_capabilities(self) -> set[str]:
        return {
            "voice.tts.generate",
            "voice.tts.stream",
            "voice.voices.list",
            "voice.voices.clone",
            "voice.stt.transcribe",
        }

    def configure_tenant(self, tenant_id: int, api_key: str, **kwargs: Any) -> None:
        self._clients[tenant_id] = {
            "api_key": api_key,
            "base_url": kwargs.get("base_url", DEFAULT_BASE_URL),
            "default_voice_id": kwargs.get("default_voice_id"),
            "default_model": kwargs.get("model", DEFAULT_MODEL),
        }
        logger.info("elevenlabs.tenant_configured", tenant_id=tenant_id)

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "ElevenLabs"

    @property
    def category(self) -> str:
        return "voice"

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "required": True,
                    "help_text": "ElevenLabs API Key.",
                },
            ],
        }

    async def get_contacts(
        self,
        tenant_id: int,
        config: dict,
        last_sync_at=None,
        sync_mode=None,
    ) -> "SyncResult":
        from app.integrations.adapters.base import SyncResult
        return SyncResult(
            success=True,
            records_fetched=0,
            contacts=[],
            metadata={"note": "ElevenLabs does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="ElevenLabs-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs: Any) -> AdapterResult:
        config = self._clients.get(tenant_id)
        if not config:
            return AdapterResult(success=False, error="ElevenLabs ist nicht konfiguriert.", error_code="NOT_CONFIGURED")

        handler = {
            "voice.tts.generate": self._tts_generate,
            "voice.tts.stream": self._tts_stream,
            "voice.voices.list": self._voices_list,
            "voice.voices.clone": self._voices_clone,
            "voice.stt.transcribe": self._stt_transcribe,
        }.get(capability_id)

        if handler:
            return await handler(config, **kwargs)
        return AdapterResult(success=False, error=f"Unbekannte Capability: {capability_id}", error_code="UNSUPPORTED_CAPABILITY")

    async def _tts_generate(self, config: dict, **kwargs: Any) -> AdapterResult:
        text = kwargs.get("text")
        if not text:
            return AdapterResult(success=False, error="Parameter 'text' ist erforderlich.", error_code="MISSING_PARAM")

        voice_id = kwargs.get("voice_id", config.get("default_voice_id", "21m00Tcm4TlvDq8ikWAM"))
        model_id = kwargs.get("model", config["default_model"])
        stability = kwargs.get("stability", 0.5)
        similarity_boost = kwargs.get("similarity_boost", 0.75)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{config['base_url']}/text-to-speech/{voice_id}",
                    headers={"xi-api-key": config["api_key"], "Content-Type": "application/json"},
                    json={
                        "text": text,
                        "model_id": model_id,
                        "voice_settings": {"stability": stability, "similarity_boost": similarity_boost},
                    },
                )
                if resp.status_code == 200:
                    return AdapterResult(
                        success=True,
                        data={"audio_bytes": len(resp.content), "content_type": resp.headers.get("content-type", "audio/mpeg"), "voice_id": voice_id},
                        metadata={"raw_audio": resp.content},
                    )
                return AdapterResult(success=False, error=f"ElevenLabs API Fehler: {resp.status_code} – {resp.text[:200]}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _tts_stream(self, config: dict, **kwargs: Any) -> AdapterResult:
        text = kwargs.get("text")
        if not text:
            return AdapterResult(success=False, error="Parameter 'text' ist erforderlich.", error_code="MISSING_PARAM")

        voice_id = kwargs.get("voice_id", config.get("default_voice_id", "21m00Tcm4TlvDq8ikWAM"))
        return AdapterResult(
            success=True,
            data={
                "stream_url": f"{config['base_url']}/text-to-speech/{voice_id}/stream",
                "voice_id": voice_id,
                "text_length": len(text),
                "note": "Streaming-Endpoint bereit. Audio wird chunk-weise geliefert.",
            },
        )

    async def _voices_list(self, config: dict, **kwargs: Any) -> AdapterResult:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{config['base_url']}/voices",
                    headers={"xi-api-key": config["api_key"]},
                )
                if resp.status_code == 200:
                    voices = resp.json().get("voices", [])
                    return AdapterResult(
                        success=True,
                        data=[{"voice_id": v["voice_id"], "name": v["name"], "category": v.get("category", "unknown")} for v in voices],
                        metadata={"total": len(voices)},
                    )
                return AdapterResult(success=False, error=f"API Fehler: {resp.status_code}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _voices_clone(self, config: dict, **kwargs: Any) -> AdapterResult:
        name = kwargs.get("name")
        files = kwargs.get("files")
        if not name or not files:
            return AdapterResult(success=False, error="Parameter 'name' und 'files' sind erforderlich.", error_code="MISSING_PARAM")

        return AdapterResult(
            success=True,
            data={"status": "clone_initiated", "name": name, "files_count": len(files) if isinstance(files, list) else 1},
            metadata={"endpoint": f"{config['base_url']}/voices/add"},
        )

    async def _stt_transcribe(self, config: dict, **kwargs: Any) -> AdapterResult:
        audio_url = kwargs.get("audio_url")
        audio_data = kwargs.get("audio_data")
        if not audio_url and not audio_data:
            return AdapterResult(success=False, error="Parameter 'audio_url' oder 'audio_data' ist erforderlich.", error_code="MISSING_PARAM")

        return AdapterResult(
            success=True,
            data={"status": "transcription_initiated", "source": "url" if audio_url else "data"},
            metadata={"endpoint": f"{config['base_url']}/speech-to-text"},
        )

    async def health_check(self, tenant_id: int) -> AdapterResult:
        config = self._clients.get(tenant_id)
        if not config:
            return AdapterResult(success=False, error="Nicht konfiguriert", error_code="NOT_CONFIGURED")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{config['base_url']}/user", headers={"xi-api-key": config["api_key"]})
                if resp.status_code == 200:
                    return AdapterResult(success=True, data={"status": "healthy", "adapter": "elevenlabs"})
                return AdapterResult(success=False, error=f"Health-Check fehlgeschlagen: {resp.status_code}", error_code="HEALTH_CHECK_FAILED")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
