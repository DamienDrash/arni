# WooCommerce – E-Commerce Integration

## Überblick
Der WooCommerceAdapter verbindet ARIIA mit WooCommerce-Shops über die REST API v3. Er ermöglicht die Verwaltung von Kunden, Bestellungen und Produkten sowie die Einrichtung von Webhooks für Echtzeit-Synchronisation.

## Integration ID
`woocommerce`

## Authentifizierung
- **OAuth 1.0a** mit Consumer Key und Consumer Secret
- Zugangsdaten über WooCommerce → Einstellungen → Erweitert → REST-API

## Capabilities

| Capability ID | Beschreibung | Pflichtparameter |
|---|---|---|
| `ecommerce.customer.search` | Kunden suchen | `email` oder `search` |
| `ecommerce.customer.create` | Neuen Kunden erstellen | `email` |
| `ecommerce.order.list` | Bestellungen auflisten | – |
| `ecommerce.order.status` | Bestellstatus abrufen | `order_id` |
| `ecommerce.product.list` | Produkte auflisten | – |
| `ecommerce.product.search` | Produkte suchen | `search` oder `sku` |
| `ecommerce.webhook.subscribe` | Webhook registrieren | `topic`, `delivery_url` |

## Anwendungsbeispiele

### Kunde suchen
```python
result = await adapter.execute_capability(
    "ecommerce.customer.search",
    tenant_id=1,
    email="max@example.com"
)
```

### Bestellstatus abrufen
```python
result = await adapter.execute_capability(
    "ecommerce.order.status",
    tenant_id=1,
    order_id=12345
)
```

## Fehlerbehandlung
- `NOT_CONFIGURED`: Store-URL oder API-Keys nicht hinterlegt
- `WOOCOMMERCE_HTTP_401`: Ungültige API-Zugangsdaten
- `WOOCOMMERCE_HTTP_404`: Ressource nicht gefunden
- `MISSING_PARAM`: Pflichtparameter fehlt
