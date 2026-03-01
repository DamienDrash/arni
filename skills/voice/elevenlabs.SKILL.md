# ElevenLabs Voice AI – ARIIA Skill

## Integration ID
`elevenlabs`

## Beschreibung
Text-to-Speech, Voice Cloning und Speech-to-Text über die ElevenLabs API v1. Unterstützt Streaming-Ausgabe und mehrsprachige Stimmen.

## Authentifizierung
- **Typ:** API Key
- **Env:** `ELEVENLABS_API_KEY`

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `voice.tts.generate` | Sprachausgabe aus Text generieren | `text`, optional: `voice_id`, `model`, `stability`, `similarity_boost` |
| `voice.tts.stream` | Sprachausgabe als Stream | `text`, optional: `voice_id` |
| `voice.voices.list` | Verfügbare Stimmen auflisten | – |
| `voice.voices.clone` | Stimme aus Audio-Samples klonen | `name`, `files` |
| `voice.stt.transcribe` | Audio in Text transkribieren | `audio_url` oder `audio_data` |

## Beispiel
```python
result = await adapter.execute_capability("voice.tts.generate", tenant_id=1, text="Hallo Welt", voice_id="21m00Tcm4TlvDq8ikWAM")
```
