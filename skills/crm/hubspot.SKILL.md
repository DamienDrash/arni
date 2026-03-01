# HubSpot – CRM Integration

## Überblick
Der HubSpotAdapter verbindet ARIIA mit HubSpot CRM über die API v3. Er ermöglicht die Verwaltung von Kontakten, Deals, Unternehmen und Tickets.

## Integration ID
`hubspot`

## Authentifizierung
- **OAuth 2.0** oder Private App Token
- Token über HubSpot → Settings → Integrations → Private Apps

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `crm.contact.search` | Kontakte suchen | `email` oder `query` |
| `crm.contact.create` | Neuen Kontakt erstellen | `email` |
| `crm.contact.update` | Kontakt aktualisieren | `contact_id` |
| `crm.deal.list` | Deals auflisten | – |
| `crm.deal.create` | Neuen Deal erstellen | `deal_name` |
| `crm.company.search` | Unternehmen suchen | `query` oder `domain` |
| `crm.ticket.create` | Support-Ticket erstellen | `subject` |

## Anwendungsbeispiele

### Kontakt suchen
```python
result = await adapter.execute_capability(
    "crm.contact.search",
    tenant_id=1,
    email="max@example.com"
)
```

### Deal erstellen
```python
result = await adapter.execute_capability(
    "crm.deal.create",
    tenant_id=1,
    deal_name="Enterprise Vertrag",
    amount=50000,
    stage="appointmentscheduled"
)
```

## Fehlerbehandlung
- `NOT_CONFIGURED`: Access Token nicht hinterlegt
- `HUBSPOT_HTTP_401`: Ungültiger oder abgelaufener Token
- `HUBSPOT_HTTP_429`: Rate Limit überschritten
- `MISSING_PARAM`: Pflichtparameter fehlt
