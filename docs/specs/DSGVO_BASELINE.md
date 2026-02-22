# DSGVO-Baseline – Datenschutz & Privacy Policy für ARNI v1.4

> **Status:** Verbindlich ab Sprint 1 | **Verantwortlich:** @SEC
> **Rechtsgrundlage:** DSGVO/GDPR (EU 2016/679), insb. Art. 5, 6, 17, 25, 32

---

## 1. PII-Masking-Regeln (Personally Identifiable Information)

### Definition: Was ist PII im ARNI-Kontext?

| Kategorie | Beispiele | Risiko |
|-----------|----------|--------|
| **Direkte Identifikatoren** | Name, Telefonnummer, E-Mail, Mitglieds-ID | Hoch |
| **Finanz-Daten** | Kreditkartennummern, IBAN, Vertragsnummern | Kritisch |
| **Gesundheitsdaten** | Verletzungen, Diagnosen, Medikamente | Kritisch (Art. 9) |
| **Biometrische Daten** | Kamerabilder, Stimm-Aufnahmen | Kritisch (Art. 9) |
| **Standortdaten** | IP-Adressen, Geolocation | Mittel |

### Masking-Regeln für das Backend

```python
# PFLICHT: Alle PII-Felder müssen vor dem Logging maskiert werden.

# Regel 1: Kreditkarten → Nur letzte 4 Stellen
# Input:  "4111 1111 1111 1234"
# Output: "**** **** **** 1234"

# Regel 2: Telefonnummern → Teilmaskierung
# Input:  "+49 170 1234567"
# Output: "+49 170 ****567"

# Regel 3: E-Mail → Domain sichtbar
# Input:  "max.muster@gmail.com"
# Output: "m*********@gmail.com"

# Regel 4: Namen → Initialen in Logs
# Input:  "Max Mustermann"
# Output: "M.M."

# Regel 5: Gesundheitsdaten → NIEMALS loggen
# Input:  "Knieproblem seit 3 Wochen"
# Output: "[HEALTH_DATA_REDACTED]"

# Regel 6: Passwörter → Komplett maskiert
# Input:  "mein_passwort_123"
# Output: "****"
```

### Implementierungsanweisung für @BACKEND

```python
# Jeder Logger MUSS den PII-Filter nutzen:
# import structlog
# from app.tools.pii_filter import mask_pii
#
# logger = structlog.get_logger().bind(pii_filter=mask_pii)
#
# NIEMALS:
# logger.info(f"User {user.name} hat gebucht")  # ❌ PII im Log
#
# IMMER:
# logger.info("Booking created", user_id=user.id, class_id=cls.id)  # ✅ Nur IDs
```

---

## 2. 0s-Retention-Protokoll für Kameradaten (Vision Pipeline)

### Prinzip: Process-and-Discard

```
RTSP Stream → RAM-Snapshot → YOLOv8 Inference → Integer Count → Discard Image
                                                       ↓
                                               {count: 12, density: "medium"}
                                                       ↓
                                               Dieses JSON darf gespeichert werden.
                                               Das Bild: NIEMALS.
```

### Verbindliche Regeln

| # | Regel | Durchsetzung |
|---|-------|-------------|
| R1 | Kamerabilder werden **ausschließlich in RAM** verarbeitet | Kein `cv2.imwrite()`, kein `save()`, kein Disk-Buffer |
| R2 | Retention-Zeit: **0 Sekunden** | Bild-Variable wird nach Inference auf `None` gesetzt + `gc.collect()` |
| R3 | Kein Caching von Bildern | Kein Redis-Cache, kein Temp-File, kein Thumbnail |
| R4 | Kein Feature-Vector-Speichern | Nur `{count, density}` als Output – keine Embeddings |
| R5 | Logging: **Nur Zahlen** | Log: `"Vision: count=12, density=medium"` – kein Bild-Pfad, kein Base64 |
| R6 | Error-Handling: Bild trotzdem löschen | `try/finally` Block: Image-Cleanup auch bei Exception |

### Code-Template für @BACKEND

```python
import gc
from typing import Final

async def process_frame(frame: bytes) -> dict:
    """Process camera frame with 0s retention policy.

    DSGVO-BASELINE R1-R6: Image MUST NOT persist beyond this function.
    """
    result: Final[dict] = {"count": 0, "density": "low"}
    image = None
    try:
        image = decode_frame(frame)          # RAM only
        detections = model.predict(image)     # Inference
        result = {
            "count": len(detections),
            "density": classify_density(len(detections)),
        }
    finally:
        # R2+R6: Unconditional cleanup
        del image
        del frame
        gc.collect()

    return result  # Only integers leave this function
```

---

## 3. Consent Management

### Schema-Validierung (aus MEMORY.md)

```sql
-- sessions.consent_status MUSS vor jeder Datenverarbeitung geprüft werden
-- Gültige Werte: 'granted', 'revoked'
-- Bei 'revoked': Sofortige Löschung aller personenbezogenen Session-Daten
```

### Regeln

| Situation | Aktion |
|-----------|--------|
| Neuer User, kein Consent | Consent einholen BEVOR Daten verarbeitet werden |
| `consent_status = 'granted'` | Datenverarbeitung erlaubt |
| `consent_status = 'revoked'` | **Sofortige Löschung** aller PB-Daten (Art. 17) |
| User fordert Datenlöschung | Alle Daten in `sessions`, `messages`, `knowledge/members/{id}.md` löschen |
| Consent-Widerruf | Kein Override möglich – revoked ist revoked |

---

## 4. Notfall-Ausnahmen (Art. 6.1.d DSGVO)

Bei **lebenswichtigen Interessen** (Notfall) gelten reduzierte Datenschutz-Anforderungen:

- Keywords: `Herzinfarkt`, `Bewusstlos`, `Notarzt`, `Unfall`, `heart attack`, `unconscious`
- **Aktion:** Sofortiger Staff-Alert (Telegram) + Notruf-Nummer (112) anzeigen
- **DSGVO-Basis:** Art. 6.1.d – Verarbeitung zum Schutz lebenswichtiger Interessen
- **Logging:** Notfall-Events DÜRFEN mit Kontext geloggt werden (Haftungsschutz)

---

## 5. Audit-Checkliste (für @SEC bei jedem Sprint Review)

- [ ] Keine PII in Anwendungslogs (`grep -rn` auf Log-Output)
- [ ] Vision-Pipeline: Kein File-Write im Vision-Modul
- [ ] Consent-Status wird vor Datenverarbeitung geprüft
- [ ] Keine Credentials in Code, Env-Vars oder Docker Images
- [ ] Drittanbieter-APIs: Datenverarbeitungsvertrag (DPV) vorhanden?
- [ ] `data/knowledge/members/` Dateien: Nur faktenbasiert, keine Raw-PII
