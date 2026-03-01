# ARIIA CRM Skill (Manual CRM)

## Beschreibung
Integriertes CRM für Tenants ohne externes CRM-System. Verwaltet Kontakte direkt in der ARIIA-Datenbank. Unterstützt CSV-Import, Tagging und vollständige CRUD-Operationen.

## Capabilities
- `crm.customer.search` – Mitglieder suchen (Name, Email, Telefon)
- `crm.customer.detail` – Mitgliederdetails abrufen
- `crm.customer.create` – Neues Mitglied anlegen
- `crm.customer.update` – Mitglied aktualisieren
- `crm.customer.list` – Mitglieder auflisten mit Filtern
- `crm.customer.stats` – Mitgliederstatistiken
- `crm.import.csv` – CSV-Import von Mitgliedern
- `crm.tag.manage` – Tags verwalten

## Konfiguration
Keine externe Konfiguration erforderlich – nutzt die lokale ARIIA-Datenbank.

## Beispiel-Prompts
- "Suche das Mitglied Max Mustermann"
- "Lege einen neuen Kontakt an: Maria Muster, maria@beispiel.de"
- "Zeige mir alle Mitglieder mit dem Tag 'VIP'"
- "Wie viele aktive Mitglieder haben wir?"
