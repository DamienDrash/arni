# Multi-Source Mitgliederverwaltung — Architektur & Setup

## Ziel

Die Mitgliederverwaltung wurde von einer reinen Magicline-Anbindung zu einem
**flexiblen Multi-Source-System** erweitert. Tenants können Mitglieder aus
verschiedenen Quellen beziehen:

1. **Manuell** — Editierbare Tabelle im Frontend mit dynamischen Custom Columns
2. **CSV/Excel Import** — Bulk-Upload via Datei
3. **API** — Programmatischer CRUD-Zugriff für externe Systeme
4. **Magicline** — Bestehende Integration (unverändert)
5. **Shopify** — Kunden-Sync über Shopify Admin API
6. **WooCommerce** — Kunden-Sync über WooCommerce REST API
7. **HubSpot** — Kontakte-Sync über HubSpot CRM API

---

## Datenmodell-Erweiterungen

### StudioMember — Neue Spalten

| Spalte | Typ | Default | Beschreibung |
|:---|:---|:---|:---|
| `source` | VARCHAR(50) | `'manual'` | Herkunft: `manual`, `magicline`, `shopify`, `woocommerce`, `hubspot`, `csv`, `api` |
| `source_id` | VARCHAR(255) | NULL | Externe ID im Quellsystem (z.B. Shopify Customer ID) |
| `tags` | TEXT | NULL | JSON-Array: `["vip", "new", ...]` |
| `custom_fields` | TEXT | NULL | JSON-Object: `{"Schuhgröße": "42", "Lieblingskurs": "Yoga"}` |
| `notes` | TEXT | NULL | Freitext-Notizen |

### MemberCustomColumn — Neue Tabelle

Definiert pro Tenant die verfügbaren dynamischen Spalten:

| Spalte | Typ | Beschreibung |
|:---|:---|:---|
| `id` | INT PK | Auto-Increment |
| `tenant_id` | INT FK | Tenant-Zuordnung |
| `name` | VARCHAR(100) | Anzeigename (z.B. "Schuhgröße") |
| `slug` | VARCHAR(100) | Maschinenname (z.B. "schuhgroesse") |
| `field_type` | VARCHAR(20) | `text`, `number`, `date`, `boolean` |
| `options` | TEXT | JSON-Array für Dropdown-Optionen (optional) |
| `position` | INT | Sortierung |
| `is_visible` | BOOLEAN | In Tabelle anzeigen? |

### MemberImportLog — Neue Tabelle

Protokolliert jeden Import-Vorgang (CSV, Sync):

| Spalte | Typ | Beschreibung |
|:---|:---|:---|
| `id` | INT PK | Auto-Increment |
| `tenant_id` | INT FK | Tenant-Zuordnung |
| `source` | VARCHAR(50) | Import-Quelle |
| `status` | VARCHAR(20) | `running`, `completed`, `failed` |
| `total_rows` | INT | Gesamtanzahl |
| `imported` / `updated` / `skipped` / `errors` | INT | Zähler |
| `error_log` | TEXT | JSON-Array mit Fehlerdetails |

### Alembic-Migration

Datei: `alembic/versions/2026_02_24_member_multi_source.py`

---

## API-Referenz

### Manuelle CRUD-Endpoints

| Methode | Pfad | Beschreibung |
|:---|:---|:---|
| `POST` | `/admin/members` | Neues Mitglied anlegen |
| `PUT` | `/admin/members/{id}` | Mitglied aktualisieren (inkl. Custom Fields) |
| `DELETE` | `/admin/members/{id}` | Mitglied löschen |
| `POST` | `/admin/members/bulk` | Mehrere Mitglieder auf einmal anlegen |
| `DELETE` | `/admin/members/bulk` | Mehrere Mitglieder löschen |

### CSV Import/Export

| Methode | Pfad | Beschreibung |
|:---|:---|:---|
| `POST` | `/admin/members/import/csv` | CSV-Datei hochladen und importieren |
| `GET` | `/admin/members/export/csv` | Alle Mitglieder als CSV exportieren |

### Custom Columns

| Methode | Pfad | Beschreibung |
|:---|:---|:---|
| `GET` | `/admin/members/columns` | Alle Custom Columns auflisten |
| `POST` | `/admin/members/columns` | Neue Custom Column erstellen |
| `PUT` | `/admin/members/columns/{id}` | Custom Column aktualisieren |
| `DELETE` | `/admin/members/columns/{id}` | Custom Column löschen |

### Integrations-Sync

| Methode | Pfad | Beschreibung |
|:---|:---|:---|
| `GET` | `/admin/integrations/connectors` | Alle Connectors und Status auflisten |
| `PUT` | `/admin/integrations/connectors/shopify` | Shopify-Credentials speichern |
| `POST` | `/admin/integrations/connectors/shopify/test` | Shopify-Verbindung testen |
| `POST` | `/admin/integrations/connectors/shopify/sync` | Shopify-Kunden synchronisieren |
| `PUT` | `/admin/integrations/connectors/woocommerce` | WooCommerce-Credentials speichern |
| `POST` | `/admin/integrations/connectors/woocommerce/test` | WooCommerce-Verbindung testen |
| `POST` | `/admin/integrations/connectors/woocommerce/sync` | WooCommerce-Kunden synchronisieren |
| `PUT` | `/admin/integrations/connectors/hubspot` | HubSpot-Credentials speichern |
| `POST` | `/admin/integrations/connectors/hubspot/test` | HubSpot-Verbindung testen |
| `POST` | `/admin/integrations/connectors/hubspot/sync` | HubSpot-Kontakte synchronisieren |

---

## Setup-Anleitung

### 1. Datenbank-Migration ausführen

```bash
docker compose exec ariia-core alembic upgrade head
```

### 2. Shopify einrichten

1. Im Shopify Admin → Settings → Apps and sales channels → Develop apps
2. Neue Custom App erstellen mit Scope `read_customers`
3. Admin API access token kopieren
4. In ARIIA: Settings → Integrations → Shopify → Domain und Token eintragen
5. "Testen" klicken → "Sync" klicken

### 3. WooCommerce einrichten

1. WordPress Admin → WooCommerce → Settings → Advanced → REST API
2. Neuen Key erstellen mit Read-Berechtigung
3. Consumer Key und Secret kopieren
4. In ARIIA: Settings → Integrations → WooCommerce → URL und Keys eintragen
5. "Testen" klicken → "Sync" klicken

### 4. HubSpot einrichten

1. HubSpot → Settings → Integrations → Private Apps
2. Neue Private App erstellen mit Scope `crm.objects.contacts.read`
3. Access Token kopieren
4. In ARIIA: Settings → Integrations → HubSpot → Token eintragen
5. "Testen" klicken → "Sync" klicken

### 5. Manuelle Mitgliederverwaltung

- Mitglieder → "Mitglied anlegen" Button
- Inline-Editing: Direkt in der Tabelle auf Werte klicken zum Bearbeiten
- Custom Columns: "Spalten" Button → Eigene Felder definieren
- CSV Import: "CSV Import" Button → Datei hochladen
- CSV Export: "Export" Button

---

## Dateistruktur

```
app/
├── core/
│   └── models.py                          # StudioMember, MemberCustomColumn, MemberImportLog
├── gateway/
│   ├── admin.py                           # Bestehende Admin-Endpoints (erweitert)
│   ├── routers/
│   │   ├── members_crud.py                # Manuelle CRUD, CSV Import/Export, Custom Columns
│   │   └── integrations_sync.py           # Shopify/WooCommerce/HubSpot Connector-Endpoints
│   └── main.py                            # Router-Registrierung
├── integrations/
│   ├── magicline/                         # Bestehend (unverändert)
│   ├── shopify/
│   │   ├── __init__.py
│   │   ├── client.py                      # Shopify Admin API Client
│   │   └── members_sync.py               # Shopify → StudioMember Sync
│   ├── woocommerce/
│   │   ├── __init__.py
│   │   ├── client.py                      # WooCommerce REST API Client
│   │   └── members_sync.py               # WooCommerce → StudioMember Sync
│   └── hubspot/
│       ├── __init__.py
│       ├── client.py                      # HubSpot CRM API Client
│       └── members_sync.py               # HubSpot → StudioMember Sync
alembic/
└── versions/
    └── 2026_02_24_member_multi_source.py  # DB-Migration
frontend/
├── app/
│   ├── members/page.tsx                   # Erweiterte Mitglieder-Tabelle
│   └── settings/integrations/page.tsx     # Integrations-Seite (erweitert)
docs/
└── MEMBER_SOURCES_ARCHITECTURE.md         # Diese Datei
```

---

## Sync-Logik

Alle Sync-Operationen folgen dem gleichen Muster:

1. **Fetch**: Alle Kunden/Kontakte von der externen API laden (mit Pagination)
2. **Normalize**: Externe Felder auf StudioMember-Schema mappen
3. **Upsert**: Matching über `source` + `source_id` — Update bei Existenz, Insert bei Neuheit
4. **Log**: Import-Ergebnis in `MemberImportLog` protokollieren
5. **Settings**: Letzten Sync-Zeitpunkt und Status in Tenant-Settings speichern

Jeder Sync ist **idempotent** und kann beliebig oft ausgeführt werden.
