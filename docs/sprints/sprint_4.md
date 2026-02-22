# Sprint 4 – Memory & Knowledge (Woche 7–8)

> **Status:** 🟡 Aktiv | **Methodik:** BMAD | **Start:** 2026-02-14

---

## Tasks

| # | Task | Agent | Beschreibung | Benchmark | Status |
|---|------|-------|-------------|-----------|--------|
| 4.1 | Short-Term Memory | @BACKEND | RAM Context Manager (20 Turns, TTL) | Kontext über 20 Nachrichten erhalten | ⬜ |
| 4.2 | SQLite Session DB | @BACKEND | `sessions.db` mit sessions + messages Tabellen | CRUD + 90-Tage Retention | ⬜ |
| 4.3 | Session Repository | @BACKEND | Async Repository Pattern für Session/Message CRUD | create/get/update/delete funktional | ⬜ |
| 4.4 | Silent Flush | @BACKEND | Context Compaction → Fact Extraction bei >80% | Facts extrahiert, RAM gepruned | ⬜ |
| 4.5 | Long-Term Knowledge | @BACKEND | `data/knowledge/members/{id}.md` – Fakten-Dateien | Markdown-File pro Member | ⬜ |
| 4.6 | GraphRAG Stub | @BACKEND | NetworkX In-Memory Graph mit Fact→Node Sync | Graph-Query gibt Fakten zurück | ⬜ |
| 4.7 | Consent Manager | @SEC | Art. 6 Consent-Prüfung + Art. 17 Right to Erasure | `revoked` → sofortige Löschung | ⬜ |
| 4.8 | Privacy Impact Assessment | @SEC | PIA-Dokument für Memory Pipeline | Compliance-Report fertig | ⬜ |
| 4.9 | Memory Integration | @BACKEND | Swarm Router + Agents ← Memory Context Injection | Agents erhalten Kontext | ⬜ |
| 4.10 | Unit Tests Memory | @QA | Context, Session, Flush, Knowledge, Consent Tests | ≥80% Coverage | ⬜ |
| 4.11 | README + Docs Update | @DOCS | Memory Architecture in README dokumentiert | Docs aktuell | ⬜ |

## Definition of Done
- [ ] Short-Term Memory hält 20 Turns pro User
- [ ] SQLite Sessions DB erstellt und CRUD funktional
- [ ] Silent Flush extrahiert Fakten bei >80% Context-Limit
- [ ] Long-Term Knowledge Files werden geschrieben
- [ ] Consent Manager: `revoked` → Daten gelöscht (Art. 17)
- [ ] Tests: ≥80% Coverage auf `app/memory/`
- [ ] PIA Report erstellt und signiert
