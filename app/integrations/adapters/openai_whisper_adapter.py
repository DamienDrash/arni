"""ARIIA v2.0 – OpenAI Whisper Adapter (Sprint 6).

Wraps the OpenAI Whisper API for speech-to-text transcription and translation.
Max file size: 25 MB. Supports formats: mp3, mp4, mpeg, mpga, m4a, wav, webm.

Capabilities:
  - voice.stt.transcribe   → Transcribe audio to text
  - voice.stt.translate     → Translate audio to English text
  - voice.stt.timestamps    → Transcribe with word-level timestamps
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()

SUPPORTED_FORMATS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"}
MAX_FILE_SIZE_MB = 25
WHISPER_MODEL = "whisper-1"


class OpenAIWhisperAdapter(BaseAdapter):
    """Adapter for OpenAI Whisper Speech-to-Text API."""

    def __init__(self) -> None:
        self._clients: dict[int, dict[str, Any]] = {}
        self.version = "1.0.0"

    @property
    def integration_id(self) -> str:
        return "openai_whisper"

    @property
    def supported_capabilities(self) -> set[str]:
        return {"voice.stt.transcribe", "voice.stt.translate", "voice.stt.timestamps"}

    def configure_tenant(self, tenant_id: int, api_key: str, **kwargs: Any) -> None:
        self._clients[tenant_id] = {
            "api_key": api_key,
            "base_url": kwargs.get("base_url", "https://api.openai.com/v1"),
            "default_language": kwargs.get("language", "de"),
        }
        logger.info("openai_whisper.tenant_configured", tenant_id=tenant_id)

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "OpenAI Whisper"

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
                    "help_text": "OpenAI API Key.",
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
            metadata={"note": "OpenAI Whisper does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="OpenAI Whisper-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs: Any) -> AdapterResult:
        config = self._clients.get(tenant_id)
        if not config:
            return AdapterResult(success=False, error="OpenAI Whisper ist nicht konfiguriert.", error_code="NOT_CONFIGURED")

        handler = {
            "voice.stt.transcribe": self._stt_transcribe,
            "voice.stt.translate": self._stt_translate,
            "voice.stt.timestamps": self._stt_timestamps,
        }.get(capability_id)

        if handler:
            return await handler(config, **kwargs)
        return AdapterResult(success=False, error=f"Unbekannte Capability: {capability_id}", error_code="UNSUPPORTED_CAPABILITY")

    async def _stt_transcribe(self, config: dict, **kwargs: Any) -> AdapterResult:
        file_path = kwargs.get("file_path")
        audio_data = kwargs.get("audio_data")
        if not file_path and not audio_data:
            return AdapterResult(success=False, error="Parameter 'file_path' oder 'audio_data' ist erforderlich.", error_code="MISSING_PARAM")

        language = kwargs.get("language", config["default_language"])
        prompt = kwargs.get("prompt", "")

        try:
            import httpx
            headers = {"Authorization": f"Bearer {config['api_key']}"}

            if file_path:
                import os
                if not os.path.exists(file_path):
                    return AdapterResult(success=False, error=f"Datei nicht gefunden: {file_path}", error_code="FILE_NOT_FOUND")
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > MAX_FILE_SIZE_MB:
                    return AdapterResult(success=False, error=f"Datei zu groß: {file_size_mb:.1f} MB (max {MAX_FILE_SIZE_MB} MB)", error_code="FILE_TOO_LARGE")

                async with httpx.AsyncClient(timeout=120.0) as client:
                    with open(file_path, "rb") as f:
                        resp = await client.post(
                            f"{config['base_url']}/audio/transcriptions",
                            headers=headers,
                            data={"model": WHISPER_MODEL, "language": language, "prompt": prompt},
                            files={"file": f},
                        )
            else:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(
                        f"{config['base_url']}/audio/transcriptions",
                        headers=headers,
                        data={"model": WHISPER_MODEL, "language": language, "prompt": prompt},
                        files={"file": ("audio.mp3", audio_data, "audio/mpeg")},
                    )

            if resp.status_code == 200:
                result = resp.json()
                return AdapterResult(success=True, data={"text": result.get("text", ""), "language": language})
            return AdapterResult(success=False, error=f"Whisper API Fehler: {resp.status_code} – {resp.text[:200]}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _stt_translate(self, config: dict, **kwargs: Any) -> AdapterResult:
        file_path = kwargs.get("file_path")
        audio_data = kwargs.get("audio_data")
        if not file_path and not audio_data:
            return AdapterResult(success=False, error="Parameter 'file_path' oder 'audio_data' ist erforderlich.", error_code="MISSING_PARAM")

        try:
            import httpx
            headers = {"Authorization": f"Bearer {config['api_key']}"}

            if file_path:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    with open(file_path, "rb") as f:
                        resp = await client.post(
                            f"{config['base_url']}/audio/translations",
                            headers=headers,
                            data={"model": WHISPER_MODEL},
                            files={"file": f},
                        )
            else:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(
                        f"{config['base_url']}/audio/translations",
                        headers=headers,
                        data={"model": WHISPER_MODEL},
                        files={"file": ("audio.mp3", audio_data, "audio/mpeg")},
                    )

            if resp.status_code == 200:
                result = resp.json()
                return AdapterResult(success=True, data={"text": result.get("text", ""), "target_language": "en"})
            return AdapterResult(success=False, error=f"API Fehler: {resp.status_code}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _stt_timestamps(self, config: dict, **kwargs: Any) -> AdapterResult:
        file_path = kwargs.get("file_path")
        audio_data = kwargs.get("audio_data")
        if not file_path and not audio_data:
            return AdapterResult(success=False, error="Parameter 'file_path' oder 'audio_data' ist erforderlich.", error_code="MISSING_PARAM")

        granularity = kwargs.get("granularity", "word")
        try:
            import httpx
            headers = {"Authorization": f"Bearer {config['api_key']}"}
            data = {"model": WHISPER_MODEL, "response_format": "verbose_json", "timestamp_granularities[]": granularity}

            if file_path:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    with open(file_path, "rb") as f:
                        resp = await client.post(f"{config['base_url']}/audio/transcriptions", headers=headers, data=data, files={"file": f})
            else:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(
                        f"{config['base_url']}/audio/transcriptions", headers=headers, data=data,
                        files={"file": ("audio.mp3", audio_data, "audio/mpeg")},
                    )

            if resp.status_code == 200:
                result = resp.json()
                return AdapterResult(success=True, data={"text": result.get("text", ""), "words": result.get("words", []), "segments": result.get("segments", [])})
            return AdapterResult(success=False, error=f"API Fehler: {resp.status_code}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def health_check(self, tenant_id: int) -> AdapterResult:
        config = self._clients.get(tenant_id)
        if not config:
            return AdapterResult(success=False, error="Nicht konfiguriert", error_code="NOT_CONFIGURED")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{config['base_url']}/models", headers={"Authorization": f"Bearer {config['api_key']}"})
                if resp.status_code == 200:
                    return AdapterResult(success=True, data={"status": "healthy", "adapter": "openai_whisper"})
                return AdapterResult(success=False, error=f"Health-Check fehlgeschlagen: {resp.status_code}", error_code="HEALTH_CHECK_FAILED")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
