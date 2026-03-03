# Strato DNS TXT Records – ariia.ai

## Aktuelle Einstellungen

### STRATO DMARC
- Option 1: "STRATO Standard DMARC-Regel" (Radio Button, index 30)
- Option 2: "Keine STRATO DMARC-Regel" (Radio Button, index 32)
- Aktuell: Standard DMARC-Regel scheint ausgewählt

### STRATO SPF-Regel
- Optionen: Keine / Standard STRATO Mailserver / FAIL / SOFTFAIL
- Muss noch gesehen werden (weiter unten)

### Eigene TXT/CNAME Records
- Typ: TXT oder CNAME
- Präfix: .ariia.ai
- Wert: (leer)
- "Weiteren Record erstellen" Button

## Nötige Änderungen
1. SPF: "Standard STRATO Mailserver" oder "SOFTFAIL" auswählen
2. DMARC: Standard DMARC-Regel beibehalten (oder eigene setzen)
3. Optional: Eigenen SPF TXT Record für erweiterte Konfiguration
