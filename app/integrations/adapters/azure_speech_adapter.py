"""ARIIA v2.0 – Azure Speech Adapter (Sprint 6).

Wraps the Azure Cognitive Services Speech API for TTS, STT,
real-time transcription, and speech translation.

Capabilities:
  - voice.tts.generate          → Generate speech audio from text/SSML
  - voice.stt.transcribe        → Transcribe audio to text
  - voice.stt.realtime          → Real-time streaming STT
  - voice.translation.speech    → Translate speech to another language
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()

DEFAULT_LANGUAGE = "de-DE"
DEFAULT_VOICE = "de-DE-ConradNeural"


class AzureSpeechAdapter(BaseAdapter):
    """Adapter for Azure Cognitive Services Speech."""

    def __init__(self) -> None:
        self._clients: dict[int, dict[str, Any]] = {}
        self.version = "1.0.0"

    @property
    def integration_id(self) -> str:
        return "azure_speech"

    @property
    def supported_capabilities(self) -> set[str]:
        return {"voice.tts.generate", "voice.stt.transcribe", "voice.stt.realtime", "voice.translation.speech"}

    def configure_tenant(self, tenant_id: int, api_key: str, region: str, **kwargs: Any) -> None:
        self._clients[tenant_id] = {
            "api_key": api_key,
            "region": region,
            "tts_endpoint": f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
            "stt_endpoint": f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1",
            "token_endpoint": f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken",
            "default_language": kwargs.get("language", DEFAULT_LANGUAGE),
            "default_voice": kwargs.get("voice", DEFAULT_VOICE),
        }
        logger.info("azure_speech.tenant_configured", tenant_id=tenant_id, region=region)

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "Azure Speech"

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
                    "help_text": "Azure Cognitive Services Speech API Key.",
                },
                {
                    "key": "region",
                    "label": "Region",
                    "type": "text",
                    "required": True,
                    "help_text": "Azure Region (z.B. westeurope).",
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
            metadata={"note": "Azure Speech does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="Azure Speech-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs: Any) -> AdapterResult:
        config = self._clients.get(tenant_id)
        if not config:
            return AdapterResult(success=False, error="Azure Speech ist nicht konfiguriert.", error_code="NOT_CONFIGURED")

        handler = {
            "voice.tts.generate": self._tts_generate,
            "voice.stt.transcribe": self._stt_transcribe,
            "voice.stt.realtime": self._stt_realtime,
            "voice.translation.speech": self._translation_speech,
        }.get(capability_id)

        if handler:
            return await handler(config, **kwargs)
        return AdapterResult(success=False, error=f"Unbekannte Capability: {capability_id}", error_code="UNSUPPORTED_CAPABILITY")

    async def _tts_generate(self, config: dict, **kwargs: Any) -> AdapterResult:
        text = kwargs.get("text")
        ssml = kwargs.get("ssml")
        if not text and not ssml:
            return AdapterResult(success=False, error="Parameter 'text' oder 'ssml' ist erforderlich.", error_code="MISSING_PARAM")

        voice = kwargs.get("voice", config["default_voice"])
        language = kwargs.get("language", config["default_language"])
        output_format = kwargs.get("output_format", "audio-16khz-128kbitrate-mono-mp3")

        if not ssml:
            ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{language}'>
    <voice name='{voice}'>{text}</voice>
</speak>"""

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    config["tts_endpoint"],
                    headers={
                        "Ocp-Apim-Subscription-Key": config["api_key"],
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": output_format,
                    },
                    content=ssml.encode("utf-8"),
                )
                if resp.status_code == 200:
                    return AdapterResult(
                        success=True,
                        data={"audio_bytes": len(resp.content), "voice": voice, "language": language, "format": output_format},
                        metadata={"raw_audio": resp.content},
                    )
                return AdapterResult(success=False, error=f"Azure TTS Fehler: {resp.status_code} – {resp.text[:200]}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _stt_transcribe(self, config: dict, **kwargs: Any) -> AdapterResult:
        audio_data = kwargs.get("audio_data")
        file_path = kwargs.get("file_path")
        if not audio_data and not file_path:
            return AdapterResult(success=False, error="Parameter 'audio_data' oder 'file_path' ist erforderlich.", error_code="MISSING_PARAM")

        language = kwargs.get("language", config["default_language"])

        try:
            import httpx

            if file_path:
                import os
                if not os.path.exists(file_path):
                    return AdapterResult(success=False, error=f"Datei nicht gefunden: {file_path}", error_code="FILE_NOT_FOUND")
                with open(file_path, "rb") as f:
                    audio_data = f.read()

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{config['stt_endpoint']}?language={language}&format=detailed",
                    headers={
                        "Ocp-Apim-Subscription-Key": config["api_key"],
                        "Content-Type": "audio/wav",
                    },
                    content=audio_data,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    display_text = result.get("DisplayText", result.get("NBest", [{}])[0].get("Display", ""))
                    confidence = result.get("NBest", [{}])[0].get("Confidence", 0.0) if result.get("NBest") else 0.0
                    return AdapterResult(
                        success=True,
                        data={"text": display_text, "language": language, "confidence": confidence},
                        metadata={"recognition_status": result.get("RecognitionStatus", "Unknown")},
                    )
                return AdapterResult(success=False, error=f"Azure STT Fehler: {resp.status_code}", error_code="API_ERROR")
        except ImportError:
            return AdapterResult(success=False, error="httpx ist nicht installiert.", error_code="DEPENDENCY_MISSING")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="API_ERROR")

    async def _stt_realtime(self, config: dict, **kwargs: Any) -> AdapterResult:
        language = kwargs.get("language", config["default_language"])
        return AdapterResult(
            success=True,
            data={
                "websocket_url": f"wss://{config['region']}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language={language}",
                "auth_header": f"Ocp-Apim-Subscription-Key: {config['api_key']}",
                "language": language,
                "note": "WebSocket-Verbindung bereit. Sende Audio-Chunks für Echtzeit-Transkription.",
            },
        )

    async def _translation_speech(self, config: dict, **kwargs: Any) -> AdapterResult:
        audio_data = kwargs.get("audio_data")
        file_path = kwargs.get("file_path")
        if not audio_data and not file_path:
            return AdapterResult(success=False, error="Parameter 'audio_data' oder 'file_path' ist erforderlich.", error_code="MISSING_PARAM")

        source_language = kwargs.get("source_language", config["default_language"])
        target_language = kwargs.get("target_language", "en")

        try:
            import httpx

            if file_path:
                import os
                if not os.path.exists(file_path):
                    return AdapterResult(success=False, error=f"Datei nicht gefunden: {file_path}", error_code="FILE_NOT_FOUND")
                with open(file_path, "rb") as f:
                    audio_data = f.read()

            translation_url = f"https://{config['region']}.s2s.speech.microsoft.com/speech/translation/cognitiveservices/v1?from={source_language}&to={target_language}"
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    translation_url,
                    headers={
                        "Ocp-Apim-Subscription-Key": config["api_key"],
                        "Content-Type": "audio/wav",
                    },
                    content=audio_data,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    return AdapterResult(
                        success=True,
                        data={
                            "translated_text": result.get("Translation", {}).get("Translation", ""),
                            "source_text": result.get("Recognition", ""),
                            "source_language": source_language,
                            "target_language": target_language,
                        },
                    )
                return AdapterResult(success=False, error=f"Azure Translation Fehler: {resp.status_code}", error_code="API_ERROR")
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
                resp = await client.post(config["token_endpoint"], headers={"Ocp-Apim-Subscription-Key": config["api_key"]}, content=b"")
                if resp.status_code == 200:
                    return AdapterResult(success=True, data={"status": "healthy", "adapter": "azure_speech", "region": config["region"]})
                return AdapterResult(success=False, error=f"Health-Check fehlgeschlagen: {resp.status_code}", error_code="HEALTH_CHECK_FAILED")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
