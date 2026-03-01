# Calendly – Scheduling Integration

## Überblick
Der CalendlyAdapter ermöglicht die Verwaltung von Terminbuchungen, Event-Typen, Verfügbarkeiten und Einladungen über die Calendly API v2.

## Integration ID
`calendly`

## Authentifizierung
- **Personal Access Token** (empfohlen) oder OAuth 2.0
- Token wird in den Tenant-Integrationseinstellungen hinterlegt

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `scheduling.event_types.list` | Event-Typen auflisten | – |
| `scheduling.events.list` | Geplante Events auflisten | – |
| `scheduling.events.get` | Event-Details abrufen | `event_uuid` |
| `scheduling.events.cancel` | Event absagen | `event_uuid` |
| `scheduling.availability.get` | Verfügbarkeit abrufen | – |
| `scheduling.invitee.list` | Eingeladene eines Events auflisten | `event_uuid` |
| `scheduling.webhook.subscribe` | Webhook abonnieren | `url`, `events` |
| `scheduling.webhook.list` | Aktive Webhooks auflisten | – |

## Anwendungsbeispiele

### Events auflisten
```python
result = await adapter.execute_capability(
    "scheduling.events.list",
    tenant_id=1,
    min_start_time="2026-03-01T00:00:00Z",
    status="active"
)
```

### Event absagen
```python
result = await adapter.execute_capability(
    "scheduling.events.cancel",
    tenant_id=1,
    event_uuid="abc-123-def",
    reason="Kunde hat abgesagt"
)
```

### Webhook abonnieren
```python
result = await adapter.execute_capability(
    "scheduling.webhook.subscribe",
    tenant_id=1,
    url="https://api.example.com/webhooks/calendly",
    events=["invitee.created", "invitee.canceled"]
)
```

## Webhook-Events
- `invitee.created` – Neuer Teilnehmer hat gebucht
- `invitee.canceled` – Teilnehmer hat storniert
- `routing_form_submission.created` – Routing-Formular ausgefüllt

## Rate Limits
- 350 Requests pro Minute (Personal Access Token)
- 10.000 Requests pro Tag (OAuth)

## Fehlerbehandlung
- `CALENDLY_NOT_CONFIGURED`: Token nicht hinterlegt
- `CALENDLY_HTTP_401`: Ungültiger Token
- `CALENDLY_HTTP_429`: Rate Limit erreicht
- `CALENDLY_REQUEST_FAILED`: Netzwerkfehler
