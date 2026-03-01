# Skill: Knowledge Base

**Integration ID:** `knowledge`
**Adapter:** `KnowledgeAdapter`
**Kategorie:** Agent Tools / Knowledge
**Priorität:** Kritisch – Agent-Kernfunktion

## Beschreibung

Die Knowledge Base ist das zentrale Wissensmanagement-System von ARIIA. Sie basiert auf ChromaDB (Vektor-Datenbank) und ermöglicht semantische Suche über Tenant-spezifische Wissensdokumente wie Preislisten, Öffnungszeiten, Regeln und Policies.

## Capabilities

### knowledge.search
Semantische Suche in der Wissensbasis des Tenants.

**Parameter:**
| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|-------------|
| `query` | string | Ja | Suchbegriff oder Frage (z.B. "Was kostet Premium?") |
| `collection_name` | string | Nein | ChromaDB-Collection überschreiben |
| `top_n` | int | Nein | Anzahl Ergebnisse (Standard: 3) |

**Beispiel:**
```json
{"query": "Öffnungszeiten am Wochenende", "top_n": 5}
```

### knowledge.ingest
Wissensdateien (Markdown) des Tenants in ChromaDB einlesen/aktualisieren.

**Parameter:**
| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|-------------|
| `tenant_slug` | string | Nein | Tenant-Slug überschreiben |

### knowledge.list_collections
Alle verfügbaren ChromaDB-Collections mit Dokumentanzahl auflisten.

**Parameter:** Keine zusätzlichen Parameter erforderlich.

### knowledge.document.add
Ein einzelnes Dokument zur Wissensbasis hinzufügen.

**Parameter:**
| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|-------------|
| `content` | string | Ja | Textinhalt des Dokuments |
| `doc_id` | string | Nein | Eigene Dokument-ID (sonst auto-generiert) |
| `source` | string | Nein | Quellenbezeichnung (Standard: "manual") |
| `collection_name` | string | Nein | Collection überschreiben |
| `metadata` | dict | Nein | Zusätzliche Metadaten |

### knowledge.document.delete
Dokumente aus der Wissensbasis löschen.

**Parameter:**
| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|-------------|
| `doc_ids` | list[str] | Nein* | Liste von Dokument-IDs |
| `where_filter` | dict | Nein* | Metadaten-Filter für Bulk-Löschung |
| `collection_name` | string | Nein | Collection überschreiben |

*Mindestens einer der Parameter `doc_ids` oder `where_filter` ist erforderlich.

### knowledge.stats
Statistiken einer Knowledge-Base-Collection abrufen.

**Parameter:**
| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|-------------|
| `collection_name` | string | Nein | Collection überschreiben |

## Architektur

```
Agent → DynamicToolResolver → KnowledgeAdapter
                                  ├── HybridRetriever (Suche)
                                  ├── KnowledgeStore (CRUD)
                                  └── ingest_tenant_knowledge() (Batch-Import)
```

## Abhängigkeiten

- `chromadb` – Vektor-Datenbank
- `app.core.knowledge.retriever.HybridRetriever` – Semantische Suche
- `app.knowledge.store.KnowledgeStore` – Dokument-CRUD
- `app.knowledge.ingest` – Batch-Ingest aus Markdown-Dateien

## Konfiguration

Die Knowledge Base benötigt keine externen API-Keys. Die ChromaDB-Datenbank wird lokal unter `data/chroma_db/` gespeichert. Collections werden automatisch pro Tenant erstellt.
