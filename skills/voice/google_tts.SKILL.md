# Google Cloud TTS – ARIIA Skill

## Integration ID
`google_tts`

## Beschreibung
Text-to-Speech über die Google Cloud Text-to-Speech API v1. Unterstützt Standard-, WaveNet- und Neural2-Stimmen sowie SSML-Markup.

## Authentifizierung
- **Typ:** API Key oder Service Account JSON
- **Env:** `GOOGLE_TTS_API_KEY`

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `voice.tts.generate` | Sprachausgabe aus Text generieren | `text`, optional: `voice`, `language`, `encoding`, `speaking_rate`, `pitch` |
| `voice.tts.ssml` | Sprachausgabe aus SSML-Markup | `ssml`, optional: `voice`, `language`, `encoding` |
| `voice.voices.list` | Verfügbare Stimmen auflisten | optional: `language` |

## Stimm-Typen
- Standard (kostenlos), WaveNet (natürlicher), Neural2 (höchste Qualität)

## Beispiel
```python
result = await adapter.execute_capability("voice.tts.generate", tenant_id=1, text="Hallo Welt", voice="de-DE-Neural2-B")
```
