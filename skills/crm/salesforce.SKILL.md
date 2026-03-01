# Salesforce – Enterprise CRM Integration

## Überblick
Der SalesforceAdapter verbindet ARIIA mit Salesforce CRM über die REST API v66.0. Er ermöglicht die Verwaltung von Kontakten, Leads, Opportunities und Cases sowie die Ausführung beliebiger SOQL-Abfragen.

## Integration ID
`salesforce`

## Authentifizierung
- **OAuth 2.0** mit Instance URL und Access Token
- Connected App über Salesforce Setup → App Manager

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `crm.contact.search` | Kontakte suchen | `email` oder `name` |
| `crm.contact.create` | Neuen Kontakt erstellen | `last_name` |
| `crm.contact.update` | Kontakt aktualisieren | `contact_id` |
| `crm.lead.create` | Neuen Lead erstellen | `last_name`, `company` |
| `crm.opportunity.list` | Opportunities auflisten | – |
| `crm.case.create` | Support-Case erstellen | `subject` |
| `crm.soql.query` | SOQL-Abfrage ausführen | `query` |

## Anwendungsbeispiele

### Kontakt suchen
```python
result = await adapter.execute_capability(
    "crm.contact.search",
    tenant_id=1,
    email="max@example.com"
)
```

### SOQL-Abfrage
```python
result = await adapter.execute_capability(
    "crm.soql.query",
    tenant_id=1,
    query="SELECT Id, Name FROM Account WHERE Industry = 'Technology' LIMIT 10"
)
```

## Fehlerbehandlung
- `NOT_CONFIGURED`: Instance URL oder Access Token nicht hinterlegt
- `SALESFORCE_HTTP_401`: Ungültiger oder abgelaufener Token
- `SALESFORCE_HTTP_403`: Fehlende Berechtigungen
- `MISSING_PARAM`: Pflichtparameter fehlt
