# Deepgram – ARIIA Skill

## Integration ID
`deepgram`

## Beschreibung
Speech-to-Text (pre-recorded & real-time), Text-to-Speech und Audio Intelligence über die Deepgram API v1. Unterstützt WebSocket-basiertes Echtzeit-Streaming.

## Authentifizierung
- **Typ:** API Key
- **Env:** `DEEPGRAM_API_KEY`

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `voice.stt.transcribe` | Pre-recorded Audio transkribieren | `audio_url`, `audio_data` oder `file_path`, optional: `model`, `language`, `diarize` |
| `voice.stt.realtime` | Echtzeit-Streaming-Transkription | optional: `model`, `language` |
| `voice.tts.generate` | Sprachausgabe aus Text | `text`, optional: `model` |
| `voice.intelligence.analyze` | Audio-Analyse (Sentiment, Topics) | `audio_url`, optional: `features` |

## Modelle
- STT: nova-2 (Standard), nova-2-general, nova-2-meeting
- TTS: aura-asteria-en, aura-luna-en, aura-stella-en

## Beispiel
```python
result = await adapter.execute_capability("voice.stt.transcribe", tenant_id=1, audio_url="https://example.com/audio.mp3")
```
