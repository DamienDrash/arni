# Cal.com – Scheduling Integration

## Überblick
Der CalComAdapter ermöglicht die Verwaltung von Terminbuchungen über Cal.com – eine Open-Source-Scheduling-Plattform, die auch selbst gehostet werden kann.

## Integration ID
`calcom`

## Authentifizierung
- **API Key** (über Cal.com Dashboard → Settings → Developer → API Keys)
- Optional: Self-Hosted Base URL konfigurierbar

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `scheduling.event_types.list` | Event-Typen auflisten | – |
| `scheduling.bookings.list` | Buchungen auflisten | – |
| `scheduling.bookings.create` | Neue Buchung erstellen | `event_type_id`, `start`, `name`, `email` |
| `scheduling.bookings.cancel` | Buchung stornieren | `booking_id` |
| `scheduling.bookings.reschedule` | Buchung verschieben | `booking_id`, `new_start` |
| `scheduling.availability.get` | Verfügbarkeit abrufen | – |
| `scheduling.slots.list` | Freie Zeitfenster auflisten | `event_type_id`, `start_time`, `end_time` |

## Anwendungsbeispiele

### Buchung erstellen
```python
result = await adapter.execute_capability(
    "scheduling.bookings.create",
    tenant_id=1,
    event_type_id=42,
    start="2026-03-15T10:00:00Z",
    name="Max Mustermann",
    email="max@example.com",
    timezone="Europe/Berlin"
)
```

### Freie Slots abfragen
```python
result = await adapter.execute_capability(
    "scheduling.slots.list",
    tenant_id=1,
    event_type_id=42,
    start_time="2026-03-15T00:00:00Z",
    end_time="2026-03-16T00:00:00Z"
)
```

## Self-Hosting
Cal.com kann selbst gehostet werden. In diesem Fall die `base_url` in den Integrationseinstellungen auf die eigene Instanz setzen (z.B. `https://cal.meinefirma.de/api/v1`).

## Fehlerbehandlung
- `CALCOM_NOT_CONFIGURED`: API Key nicht hinterlegt
- `CALCOM_HTTP_401`: Ungültiger API Key
- `CALCOM_HTTP_404`: Ressource nicht gefunden
- `CALCOM_REQUEST_FAILED`: Netzwerkfehler
