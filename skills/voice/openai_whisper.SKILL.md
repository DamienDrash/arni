# OpenAI Whisper – ARIIA Skill

## Integration ID
`openai_whisper`

## Beschreibung
Speech-to-Text über die OpenAI Whisper API. Unterstützt Transkription, Übersetzung ins Englische und wortgenaue Timestamps. Max. 25 MB Dateigröße.

## Authentifizierung
- **Typ:** Bearer Token
- **Env:** `OPENAI_API_KEY`

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `voice.stt.transcribe` | Audio in Text transkribieren | `file_path` oder `audio_data`, optional: `language`, `prompt` |
| `voice.stt.translate` | Audio ins Englische übersetzen | `file_path` oder `audio_data` |
| `voice.stt.timestamps` | Transkription mit Timestamps | `file_path` oder `audio_data`, optional: `granularity` (word/segment) |

## Unterstützte Formate
mp3, mp4, mpeg, mpga, m4a, wav, webm

## Beispiel
```python
result = await adapter.execute_capability("voice.stt.transcribe", tenant_id=1, file_path="/tmp/audio.mp3", language="de")
```
