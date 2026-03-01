# Skill: Member Memory

**Integration ID:** `member_memory`
**Adapter:** `MemberMemoryAdapter`
**Kategorie:** Agent Tools / Knowledge
**Priorität:** Kritisch – Agent-Kernfunktion

## Beschreibung

Das Member Memory System ist das Langzeitgedächtnis von ARIIA für einzelne Mitglieder. Es speichert extrahierte Fakten, Präferenzen, Trainingsziele, Sentiment-Muster und Motivations-Anker aus Chat-Konversationen. Diese Informationen ermöglichen hochpersonalisierte Interaktionen und proaktive Retention-Maßnahmen.

## Capabilities

### memory.member.search
Semantische Suche nach spezifischen Fakten über ein Mitglied.

**Parameter:**
| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|-------------|
| `user_identifier` | string | Ja | Member ID, Mitgliedsnummer oder E-Mail |
| `query` | string | Ja | Suchanfrage (z.B. "Trainingsziele", "Einschränkungen") |

**Beispiel:**
```json
{"user_identifier": "12345", "query": "körperliche Einschränkungen"}
```

### memory.member.summary
Analytische Zusammenfassung eines Mitglieds abrufen.

**Parameter:**
| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|-------------|
| `member_id` | string | Ja | Customer-ID oder Mitgliedsnummer |

**Rückgabe:** Die extrahierte analytische Zusammenfassung aus dem Mitgliederprofil, inklusive Motivations-Anker, Sentiment-Muster und Präferenzen.

### memory.member.history
Letzte Chat-Nachrichten eines Mitglieds abrufen.

**Parameter:**
| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|-------------|
| `member_id` | string | Ja | Customer-ID oder Mitgliedsnummer |
| `limit` | int | Nein | Anzahl Nachrichten (Standard: 20) |

### memory.member.index
Mitglieder-Profil in die Vektor-Datenbank indexieren.

**Parameter:**
| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|-------------|
| `member_id` | string | Ja | Customer-ID |
| `profile_summary` | string | Nein | Vorab-berechnete Zusammenfassung (überspringt LLM-Analyse) |

### memory.member.list
Alle Mitglieder mit Gedächtnis-Profilen auflisten.

**Parameter:** Keine zusätzlichen Parameter erforderlich.

## Architektur

```
Agent → DynamicToolResolver → MemberMemoryAdapter
                                  ├── search_member_memory() (Suche)
                                  ├── HybridRetriever (Vektor-Suche)
                                  ├── member_memory_analyzer (Indexierung)
                                  └── Markdown-Profildateien (Fallback)
```

## Datenquellen

Das System nutzt eine dreistufige Suchstrategie:

1. **ChromaDB Vektor-Suche** – Semantische Suche in der Member-Memory-Collection
2. **Datenbank-Lookup** – Multi-Faktor-Identifikation über Customer-ID, Mitgliedsnummer oder E-Mail
3. **Markdown-Fallback** – Direktes Lesen der physischen Profil-Dateien unter `data/knowledge/members/`

## Abhängigkeiten

- `app.swarm.tools.member_memory` – Bestehende Suchfunktion
- `app.memory.member_memory_analyzer` – Profilanalyse und Indexierung
- `app.core.knowledge.retriever.HybridRetriever` – Vektor-Suche
- `app.core.models.StudioMember` – Mitglieder-Datenmodell

## Konfiguration

Keine externen API-Keys erforderlich. Profildateien werden automatisch durch den Member Memory Analyzer aus Chat-Konversationen generiert und unter `data/knowledge/tenants/{slug}/members/` gespeichert.
