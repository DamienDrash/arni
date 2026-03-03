"""ARIIA v2.0 – Google Cloud TTS Adapter (Sprint 6).

Wraps the Google Cloud Text-to-Speech API v1 for speech synthesis.
Supports SSML input and multiple voice types (Standard, WaveNet, Neural2).

Capabilities:
  - voice.tts.generate  → Generate speech audio from text
  - voice.tts.ssml      → Generate speech from SSML markup
  - voice.voices.list   → List available Google TTS voices
"""

from __future__ import annotations

import base64
from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()

DEFAULT_BASE_URL = "https://texttospeech.googleapis.com/v1"
DEFAULT_LANGUAGE = "de-DE"
DEFAULT_VOICE = "de-DE-Neural2-B"


class GoogleTtsAdapter(BaseAdapter):
    """Adapter for Google Cloud Text-to-Speech API."""

    def __init__(self) -> None:
        self._clients: dict[int, dict[str, Any]] = {}
        self.version = "1.0.0"

    @property
    def integration_id(self) -> str:
        return "google_tts"

    @property
    def supported_capabilities(self) -> set[str]:
        return {"voice.tts.generate", "voice.tts.ssml", "voice.voices.list"}

    def configure_tenant(self, tenant_id: int, api_key: str, **kwargs: Any) -> None:
        self._clients[tenant_id] = {
            "api_key": api_key,
            "base_url": kwargs.get("base_url", DEFAULT_BASE_URL),
            "default_language": kwargs.get("language", DEFAULT_LANGUAGE),
            "default_voice": kwargs.get("voice", DEFAULT_VOICE),
            "service_account_json": kwargs.get("service_account_json"),
        }
        logger.info("google_tts.tenant_configured", tenant_id=tenant_id)

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "Google TTS"

    @property
    def category(self) -> str:
        return "voice"

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "credentials_json",
                    "label": "Service Account JSON",
                    "type": "password",
                    "required": True,
                    "help_text": "Google Cloud Service Account JSON Key.",
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
            metadata={"note": "Google TTS does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="Google TTS-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs: Any) -> AdapterResult:
        config = self._clients.get(tenant_id)
        if not config:
            return AdapterResult(success=False, error="Google TTS ist nicht konfiguriert.", error_code="NOT_CONFIGURED")

        handler = {
            "voice.tts.generate": self._tts_generate,
            "voice.tts.ssml": self._tts_ssml,
            "voice.voices.list": self._voices_list,
        }.get(capability_id)

        if handler:
            return await handler(config, **kwargs)
        return AdapterResult(success=False, error=f"Unbekannte Capability: {capability_id}", error_code="UNSUPPORTED_CAPABILITY")

    async def _tts_generate(self, config: dict, **kwargs: Any) -> AdapterResult:
        text = kwargs.get("text")
        if not text:
            return AdapterResult(success=False, error="Parameter 'text' ist erforderlich.", error_code="MISSING_PARAM")

        language = kwargs.get("language", config["default_language"])
        voice_name = kwargs.get("voice", config["default_voice"])
        encoding = kwargs.get("encoding", "MP3")
        speaking_rate = kwargs.get("speaking_rate", 1.0)
        pitch = kwargs.get("pitch", 0.0)

        payload = {
            "input": {"text": text},
            "voice": {"languageCode": language, "name": voice_name},
            "audioConfig": {"audioEncoding": encoding, "speakingRate": speaking_rate, "pitch": pitch},
        }

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{config['base_url']}/text:synthesize?key={config['api_key']}",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code == 200:
                    audio_content = resp.json().get("audioContent", "")
                    audio_bytes = base64.b64decode(audio_content) if audio_content else b""
                    return AdapterResult(
                        success=True,
                        data={"audio_bytes": len(audio_bytes), "voice": voice_name, "language": language, "encoding": encoding},
                        metadata={"raw_audio": audio_bytes},
                    )
                return AdapterResult(success=False, error=f"Google TTS API Fehler: {resp.status_code} – {resp.text[:200]}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _tts_ssml(self, config: dict, **kwargs: Any) -> AdapterResult:
        ssml = kwargs.get("ssml")
        if not ssml:
            return AdapterResult(success=False, error="Parameter 'ssml' ist erforderlich.", error_code="MISSING_PARAM")

        language = kwargs.get("language", config["default_language"])
        voice_name = kwargs.get("voice", config["default_voice"])
        encoding = kwargs.get("encoding", "MP3")

        payload = {
            "input": {"ssml": ssml},
            "voice": {"languageCode": language, "name": voice_name},
            "audioConfig": {"audioEncoding": encoding},
        }

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{config['base_url']}/text:synthesize?key={config['api_key']}",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code == 200:
                    audio_content = resp.json().get("audioContent", "")
                    audio_bytes = base64.b64decode(audio_content) if audio_content else b""
                    return AdapterResult(
                        success=True,
                        data={"audio_bytes": len(audio_bytes), "voice": voice_name, "language": language, "format": "ssml"},
                        metadata={"raw_audio": audio_bytes},
                    )
                return AdapterResult(success=False, error=f"API Fehler: {resp.status_code}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _voices_list(self, config: dict, **kwargs: Any) -> AdapterResult:
        language = kwargs.get("language", config["default_language"])
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{config['base_url']}/voices?languageCode={language}&key={config['api_key']}",
                )
                if resp.status_code == 200:
                    voices = resp.json().get("voices", [])
                    return AdapterResult(
                        success=True,
                        data=[{"name": v["name"], "language_codes": v.get("languageCodes", []), "gender": v.get("ssmlGender", "NEUTRAL")} for v in voices],
                        metadata={"total": len(voices), "language_filter": language},
                    )
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
                resp = await client.get(f"{config['base_url']}/voices?key={config['api_key']}")
                if resp.status_code == 200:
                    return AdapterResult(success=True, data={"status": "healthy", "adapter": "google_tts"})
                return AdapterResult(success=False, error=f"Health-Check fehlgeschlagen: {resp.status_code}", error_code="HEALTH_CHECK_FAILED")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
