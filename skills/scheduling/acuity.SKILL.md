# Acuity Scheduling – Scheduling Integration

## Überblick
Der AcuityAdapter ermöglicht die Verwaltung von Terminen, Kalendern und Verfügbarkeiten über die Acuity Scheduling API. Acuity bietet erweiterte Features wie integrierte Zahlungsabwicklung und benutzerdefinierte Formulare.

## Integration ID
`acuity`

## Authentifizierung
- **HTTP Basic Auth** mit User ID und API Key
- Zugangsdaten über Acuity Dashboard → Integrations → API

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `scheduling.appointments.list` | Termine auflisten | – |
| `scheduling.appointments.create` | Neuen Termin erstellen | `appointment_type_id`, `datetime`, `first_name`, `last_name`, `email` |
| `scheduling.appointments.cancel` | Termin absagen | `appointment_id` |
| `scheduling.appointments.reschedule` | Termin verschieben | `appointment_id`, `new_datetime` |
| `scheduling.availability.get` | Verfügbare Zeitfenster abrufen | `appointment_type_id`, `month` |
| `scheduling.calendars.list` | Kalender auflisten | – |
| `scheduling.appointment_types.list` | Terminarten auflisten | – |

## Anwendungsbeispiele

### Termin erstellen
```python
result = await adapter.execute_capability(
    "scheduling.appointments.create",
    tenant_id=1,
    appointment_type_id=12345,
    datetime="2026-03-15T10:00:00+0100",
    first_name="Max",
    last_name="Mustermann",
    email="max@example.com",
    phone="+491234567890"
)
```

### Verfügbarkeit prüfen
```python
result = await adapter.execute_capability(
    "scheduling.availability.get",
    tenant_id=1,
    appointment_type_id=12345,
    month="2026-03",
    timezone="Europe/Berlin"
)
```

### Termin verschieben
```python
result = await adapter.execute_capability(
    "scheduling.appointments.reschedule",
    tenant_id=1,
    appointment_id=67890,
    new_datetime="2026-03-16T14:00:00+0100"
)
```

## Fehlerbehandlung
- `ACUITY_NOT_CONFIGURED`: User ID oder API Key nicht hinterlegt
- `ACUITY_HTTP_401`: Ungültige Zugangsdaten
- `ACUITY_HTTP_404`: Termin/Ressource nicht gefunden
- `ACUITY_HTTP_422`: Ungültige Parameter (z.B. Zeitfenster nicht verfügbar)
- `ACUITY_REQUEST_FAILED`: Netzwerkfehler
