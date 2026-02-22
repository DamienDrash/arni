# Privacy Impact Assessment – Memory Pipeline

> **@SEC** | Sprint 4 | Datum: 2026-02-14

---

## 1. Datenfluss-Diagramm

```
User Message → Gateway → Redis Bus
                           ↓
                    Consent Check (Art. 6)
                     ↓ granted    ↓ revoked
              RAM Context       → STOP + Löschung
                     ↓
              Swarm Router → Agent → Response
                     ↓
              [Context > 80%?]
                 ↓ ja          ↓ nein
           Silent Flush        → weiter
              ↓
     Fact Extraction → Knowledge File (data/knowledge/)
              ↓
     Graph Sync (NetworkX)
              ↓
     Context kompaktiert (Summary + 3 letzte Turns)
```

---

## 2. Risikobewertung je Tier

| Tier | Daten | Retention | Risiko | Maßnahmen |
|------|-------|-----------|--------|-----------|
| **RAM** | Letzte 20 Turns | 30 Min TTL | Niedrig | Auto-Expire, kein Disk-Write |
| **SQLite** | Sessions + Messages | 90 Tage | Mittel | Auto-Cleanup, CASCADE DELETE, PII-Filter |
| **Knowledge** | Extrahierte Fakten | Permanent | Mittel | Nur Fakten (kein Rohtext), Art. 17 Löschung |
| **Graph** | Beziehungs-Nodes | Runtime | Niedrig | In-Memory, kein Persist, User-Löschung |

---

## 3. DSGVO-Compliance Checklist

- [x] **Art. 6 (Rechtmäßigkeit):** Consent-Check vor jeder Datenverarbeitung
- [x] **Art. 17 (Recht auf Löschung):** Cascade Delete über alle 4 Tiers
- [x] **Art. 25 (Data Protection by Design):** TTL, auto-cleanup, minimale Speicherung
- [x] **Art. 32 (Sicherheit):** SQLite WAL-Mode, keine PII in Logs
- [x] **PII-Masking:** PIIFilter (Sprint 3) wird vor Knowledge-Speicherung angewandt
- [x] **Datensparsamkeit:** Nur extrahierte Fakten, nicht der gesamte Chat

---

## 4. Art. 17 – Löschungsverifikation

| Tier | Löschmechanismus | Verifizierung |
|------|-------------------|---------------|
| RAM | `context.clear(user_id)` | Dict-Entry entfernt |
| SQLite | `DELETE FROM sessions WHERE user_id = ?` (CASCADE) | Messages mit-gelöscht |
| Knowledge | `Path.unlink()` auf `{user_id}.md` | Datei gelöscht |
| Graph | `graph.remove_node()` + Orphan-Cleanup | Node + Edges entfernt |

---

## 5. Ergebnis

> **✅ FREIGEGEBEN** – Memory Pipeline ist DSGVO-konform.
> Alle Tiers unterstützen vollständige Löschung (Art. 17).
> Kein PII wird ohne Consent verarbeitet (Art. 6).
