# Shopify Integration Skill

## Beschreibung
E-Commerce-Integration für Shopify-Shops. Ermöglicht dem Agenten, Kunden zu suchen, Bestellungen abzurufen, Produkte zu listen und Inventar zu prüfen.

## Capabilities
- `crm.customer.search` – Shopify-Kunden suchen (Email, Name, Telefon)
- `crm.customer.sync` – Vollständiger Kundensync in lokale DB
- `ecommerce.order.list` – Bestellungen auflisten
- `ecommerce.order.detail` – Bestellungsdetails abrufen
- `ecommerce.product.list` – Produkte auflisten
- `ecommerce.product.detail` – Produktdetails abrufen
- `ecommerce.inventory.check` – Inventar prüfen

## Konfiguration
- `domain` – Shopify-Shop-Domain (z.B. `mein-shop.myshopify.com`)
- `access_token` – Shopify Admin API Access Token

## Beispiel-Prompts
- "Suche den Kunden mit Email max@beispiel.de"
- "Zeige mir die letzten 10 Bestellungen"
- "Ist das Produkt XY noch auf Lager?"
- "Wie viele Bestellungen hat der Kunde?"
