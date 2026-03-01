# Azure Speech – ARIIA Skill

## Integration ID
`azure_speech`

## Beschreibung
Text-to-Speech, Speech-to-Text, Echtzeit-Transkription und Sprach-Übersetzung über Azure Cognitive Services Speech API. Unterstützt SSML und Neural Voices.

## Authentifizierung
- **Typ:** API Key + Region
- **Env:** `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `voice.tts.generate` | Sprachausgabe aus Text/SSML | `text` oder `ssml`, optional: `voice`, `language`, `output_format` |
| `voice.stt.transcribe` | Audio in Text transkribieren | `audio_data` oder `file_path`, optional: `language` |
| `voice.stt.realtime` | Echtzeit-Streaming-Transkription | optional: `language` |
| `voice.translation.speech` | Sprach-Übersetzung | `audio_data` oder `file_path`, `target_language`, optional: `source_language` |

## Regionen
westeurope, germanywestcentral, eastus, westus2, etc.

## Beispiel
```python
result = await adapter.execute_capability("voice.tts.generate", tenant_id=1, text="Hallo Welt", voice="de-DE-ConradNeural")
```
