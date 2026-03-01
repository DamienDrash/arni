# OpenAI TTS – ARIIA Skill

## Integration ID
`openai_tts`

## Beschreibung
Text-to-Speech über die OpenAI Audio API. Unterstützt Modelle tts-1, tts-1-hd und gpt-4o-mini-tts mit 10 verschiedenen Stimmen.

## Authentifizierung
- **Typ:** Bearer Token
- **Env:** `OPENAI_API_KEY`

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `voice.tts.generate` | Sprachausgabe aus Text generieren | `text`, optional: `voice`, `model`, `response_format`, `speed` |
| `voice.tts.stream` | Sprachausgabe als Stream | `text`, optional: `voice`, `model` |
| `voice.voices.list` | Verfügbare Stimmen auflisten | – |

## Stimmen
alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer

## Beispiel
```python
result = await adapter.execute_capability("voice.tts.generate", tenant_id=1, text="Hallo Welt", voice="nova")
```
