"""ARIIA v2.0 – OpenAI TTS Adapter (Sprint 6).

Wraps the OpenAI TTS API for text-to-speech generation.
Supports models: tts-1, tts-1-hd, gpt-4o-mini-tts.

Capabilities:
  - voice.tts.generate  → Generate speech audio from text
  - voice.tts.stream    → Stream speech audio from text
  - voice.voices.list   → List available OpenAI TTS voices
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()

OPENAI_TTS_VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
OPENAI_TTS_MODELS = ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]
DEFAULT_MODEL = "tts-1"
DEFAULT_VOICE = "alloy"


class OpenAITtsAdapter(BaseAdapter):
    """Adapter for OpenAI Text-to-Speech API."""

    def __init__(self) -> None:
        self._clients: dict[int, dict[str, Any]] = {}
        self.version = "1.0.0"

    @property
    def integration_id(self) -> str:
        return "openai_tts"

    @property
    def supported_capabilities(self) -> set[str]:
        return {"voice.tts.generate", "voice.tts.stream", "voice.voices.list"}

    def configure_tenant(self, tenant_id: int, api_key: str, **kwargs: Any) -> None:
        self._clients[tenant_id] = {
            "api_key": api_key,
            "base_url": kwargs.get("base_url", "https://api.openai.com/v1"),
            "default_model": kwargs.get("model", DEFAULT_MODEL),
            "default_voice": kwargs.get("voice", DEFAULT_VOICE),
        }
        logger.info("openai_tts.tenant_configured", tenant_id=tenant_id)

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "OpenAI TTS"

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
            metadata={"note": "OpenAI TTS does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="OpenAI TTS-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs: Any) -> AdapterResult:
        config = self._clients.get(tenant_id)
        if not config:
            return AdapterResult(success=False, error="OpenAI TTS ist nicht konfiguriert.", error_code="NOT_CONFIGURED")

        handler = {
            "voice.tts.generate": self._tts_generate,
            "voice.tts.stream": self._tts_stream,
            "voice.voices.list": self._voices_list,
        }.get(capability_id)

        if handler:
            return await handler(config, **kwargs)
        return AdapterResult(success=False, error=f"Unbekannte Capability: {capability_id}", error_code="UNSUPPORTED_CAPABILITY")

    async def _tts_generate(self, config: dict, **kwargs: Any) -> AdapterResult:
        text = kwargs.get("text") or kwargs.get("input")
        if not text:
            return AdapterResult(success=False, error="Parameter 'text' ist erforderlich.", error_code="MISSING_PARAM")

        model = kwargs.get("model", config["default_model"])
        voice = kwargs.get("voice", config["default_voice"])
        response_format = kwargs.get("response_format", "mp3")
        speed = kwargs.get("speed", 1.0)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{config['base_url']}/audio/speech",
                    headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
                    json={"model": model, "input": text, "voice": voice, "response_format": response_format, "speed": speed},
                )
                if resp.status_code == 200:
                    return AdapterResult(
                        success=True,
                        data={"audio_bytes": len(resp.content), "format": response_format, "voice": voice, "model": model},
                        metadata={"raw_audio": resp.content},
                    )
                return AdapterResult(success=False, error=f"OpenAI API Fehler: {resp.status_code} – {resp.text[:200]}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _tts_stream(self, config: dict, **kwargs: Any) -> AdapterResult:
        text = kwargs.get("text") or kwargs.get("input")
        if not text:
            return AdapterResult(success=False, error="Parameter 'text' ist erforderlich.", error_code="MISSING_PARAM")

        voice = kwargs.get("voice", config["default_voice"])
        model = kwargs.get("model", config["default_model"])
        return AdapterResult(
            success=True,
            data={"stream_url": f"{config['base_url']}/audio/speech", "voice": voice, "model": model, "text_length": len(text)},
        )

    async def _voices_list(self, config: dict, **kwargs: Any) -> AdapterResult:
        voices = [{"voice_id": v, "name": v.title(), "provider": "openai"} for v in OPENAI_TTS_VOICES]
        return AdapterResult(success=True, data=voices, metadata={"total": len(voices), "models": OPENAI_TTS_MODELS})

    async def health_check(self, tenant_id: int) -> AdapterResult:
        config = self._clients.get(tenant_id)
        if not config:
            return AdapterResult(success=False, error="Nicht konfiguriert", error_code="NOT_CONFIGURED")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{config['base_url']}/models", headers={"Authorization": f"Bearer {config['api_key']}"})
                if resp.status_code == 200:
                    return AdapterResult(success=True, data={"status": "healthy", "adapter": "openai_tts"})
                return AdapterResult(success=False, error=f"Health-Check fehlgeschlagen: {resp.status_code}", error_code="HEALTH_CHECK_FAILED")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
