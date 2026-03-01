"""ARIIA v2.0 – Deepgram Adapter (Sprint 6).

Wraps the Deepgram API v1 for speech-to-text (pre-recorded & real-time),
text-to-speech, and audio intelligence capabilities.

Capabilities:
  - voice.stt.transcribe        → Transcribe pre-recorded audio
  - voice.stt.realtime          → Real-time streaming STT via WebSocket
  - voice.tts.generate          → Generate speech audio from text
  - voice.intelligence.analyze  → Audio intelligence (sentiment, topics, etc.)
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()

DEFAULT_BASE_URL = "https://api.deepgram.com/v1"
DEFAULT_MODEL = "nova-2"
DEFAULT_LANGUAGE = "de"


class DeepgramAdapter(BaseAdapter):
    """Adapter for Deepgram Speech AI platform."""

    def __init__(self) -> None:
        self._clients: dict[int, dict[str, Any]] = {}
        self.version = "1.0.0"
        self.display_name = "Deepgram"

    @property
    def integration_id(self) -> str:
        return "deepgram"

    @property
    def supported_capabilities(self) -> set[str]:
        return {"voice.stt.transcribe", "voice.stt.realtime", "voice.tts.generate", "voice.intelligence.analyze"}

    def configure_tenant(self, tenant_id: int, api_key: str, **kwargs: Any) -> None:
        self._clients[tenant_id] = {
            "api_key": api_key,
            "base_url": kwargs.get("base_url", DEFAULT_BASE_URL),
            "default_model": kwargs.get("model", DEFAULT_MODEL),
            "default_language": kwargs.get("language", DEFAULT_LANGUAGE),
        }
        logger.info("deepgram.tenant_configured", tenant_id=tenant_id)

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs: Any) -> AdapterResult:
        config = self._clients.get(tenant_id)
        if not config:
            return AdapterResult(success=False, error="Deepgram ist nicht konfiguriert.", error_code="NOT_CONFIGURED")

        handler = {
            "voice.stt.transcribe": self._stt_transcribe,
            "voice.stt.realtime": self._stt_realtime,
            "voice.tts.generate": self._tts_generate,
            "voice.intelligence.analyze": self._intelligence_analyze,
        }.get(capability_id)

        if handler:
            return await handler(config, **kwargs)
        return AdapterResult(success=False, error=f"Unbekannte Capability: {capability_id}", error_code="UNSUPPORTED_CAPABILITY")

    async def _stt_transcribe(self, config: dict, **kwargs: Any) -> AdapterResult:
        audio_url = kwargs.get("audio_url")
        audio_data = kwargs.get("audio_data")
        file_path = kwargs.get("file_path")
        if not audio_url and not audio_data and not file_path:
            return AdapterResult(success=False, error="Parameter 'audio_url', 'audio_data' oder 'file_path' ist erforderlich.", error_code="MISSING_PARAM")

        model = kwargs.get("model", config["default_model"])
        language = kwargs.get("language", config["default_language"])
        smart_format = kwargs.get("smart_format", True)
        punctuate = kwargs.get("punctuate", True)
        diarize = kwargs.get("diarize", False)

        params = f"model={model}&language={language}&smart_format={str(smart_format).lower()}&punctuate={str(punctuate).lower()}&diarize={str(diarize).lower()}"

        try:
            import httpx
            headers = {"Authorization": f"Token {config['api_key']}"}

            async with httpx.AsyncClient(timeout=120.0) as client:
                if audio_url:
                    headers["Content-Type"] = "application/json"
                    resp = await client.post(f"{config['base_url']}/listen?{params}", headers=headers, json={"url": audio_url})
                elif file_path:
                    import os
                    if not os.path.exists(file_path):
                        return AdapterResult(success=False, error=f"Datei nicht gefunden: {file_path}", error_code="FILE_NOT_FOUND")
                    with open(file_path, "rb") as f:
                        headers["Content-Type"] = "audio/mpeg"
                        resp = await client.post(f"{config['base_url']}/listen?{params}", headers=headers, content=f.read())
                else:
                    headers["Content-Type"] = "audio/mpeg"
                    resp = await client.post(f"{config['base_url']}/listen?{params}", headers=headers, content=audio_data)

                if resp.status_code == 200:
                    result = resp.json()
                    channels = result.get("results", {}).get("channels", [])
                    transcript = ""
                    if channels:
                        alternatives = channels[0].get("alternatives", [])
                        if alternatives:
                            transcript = alternatives[0].get("transcript", "")
                    return AdapterResult(
                        success=True,
                        data={"text": transcript, "model": model, "language": language},
                        metadata={"raw_response": result.get("metadata", {})},
                    )
                return AdapterResult(success=False, error=f"Deepgram API Fehler: {resp.status_code} – {resp.text[:200]}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _stt_realtime(self, config: dict, **kwargs: Any) -> AdapterResult:
        model = kwargs.get("model", config["default_model"])
        language = kwargs.get("language", config["default_language"])
        return AdapterResult(
            success=True,
            data={
                "websocket_url": f"wss://api.deepgram.com/v1/listen?model={model}&language={language}",
                "auth_header": f"Token {config['api_key']}",
                "model": model,
                "language": language,
                "note": "WebSocket-Verbindung bereit. Sende Audio-Chunks für Echtzeit-Transkription.",
            },
        )

    async def _tts_generate(self, config: dict, **kwargs: Any) -> AdapterResult:
        text = kwargs.get("text")
        if not text:
            return AdapterResult(success=False, error="Parameter 'text' ist erforderlich.", error_code="MISSING_PARAM")

        model = kwargs.get("model", "aura-asteria-en")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{config['base_url']}/speak?model={model}",
                    headers={"Authorization": f"Token {config['api_key']}", "Content-Type": "application/json"},
                    json={"text": text},
                )
                if resp.status_code == 200:
                    return AdapterResult(
                        success=True,
                        data={"audio_bytes": len(resp.content), "model": model, "format": "mp3"},
                        metadata={"raw_audio": resp.content},
                    )
                return AdapterResult(success=False, error=f"API Fehler: {resp.status_code}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _intelligence_analyze(self, config: dict, **kwargs: Any) -> AdapterResult:
        audio_url = kwargs.get("audio_url")
        if not audio_url:
            return AdapterResult(success=False, error="Parameter 'audio_url' ist erforderlich.", error_code="MISSING_PARAM")

        features = kwargs.get("features", ["summarize", "topics", "sentiment"])
        params = "&".join([f"{f}=true" for f in features])

        try:
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{config['base_url']}/listen?{params}&model={config['default_model']}&language={config['default_language']}",
                    headers={"Authorization": f"Token {config['api_key']}", "Content-Type": "application/json"},
                    json={"url": audio_url},
                )
                if resp.status_code == 200:
                    result = resp.json()
                    return AdapterResult(success=True, data={"analysis": result.get("results", {}), "features": features})
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
                resp = await client.get(f"{config['base_url']}/projects", headers={"Authorization": f"Token {config['api_key']}"})
                if resp.status_code == 200:
                    return AdapterResult(success=True, data={"status": "healthy", "adapter": "deepgram"})
                return AdapterResult(success=False, error=f"Health-Check fehlgeschlagen: {resp.status_code}", error_code="HEALTH_CHECK_FAILED")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
