# DNS-Analyse ariia.ai – Stand 03.03.2026

## Aktuelle Records

| Typ | Record | Wert |
|-----|--------|------|
| A | ariia.ai | 185.209.228.251 |
| MX | ariia.ai | 5 smtpin.rzone.de. (Strato) |
| NS | ariia.ai | shades14.rzone.de., docks11.rzone.de. (Strato) |
| DMARC | _dmarc.ariia.ai | v=DMARC1;p=reject; |
| SPF | ariia.ai | **FEHLT** |
| DKIM | *._domainkey.ariia.ai | **FEHLT** |

## Probleme

1. **Kein SPF-Record**: Ohne SPF können Empfänger nicht verifizieren, dass der Strato-Server berechtigt ist, E-Mails für ariia.ai zu senden.
2. **Kein DKIM-Record**: Ohne DKIM gibt es keine kryptographische Signatur der E-Mails.
3. **DMARC auf p=reject**: DMARC ist auf "reject" gesetzt, aber OHNE SPF und DKIM. Das bedeutet: Empfänger sollen E-Mails ablehnen, die SPF/DKIM nicht bestehen – aber da beides fehlt, werden ALLE E-Mails abgelehnt!

## Lösung

### 1. SPF-Record hinzufügen
```
ariia.ai. IN TXT "v=spf1 include:_spf.strato.de a mx ~all"
```
- `include:_spf.strato.de` – erlaubt Strato-Mailserver
- `a` – erlaubt den Server unter ariia.ai (185.209.228.251)
- `mx` – erlaubt die MX-Server
- `~all` – Softfail für alle anderen (besser als -all während der Einrichtung)

### 2. DKIM bei Strato aktivieren
- Im Strato-Kundenbereich unter "E-Mail" → "DKIM" aktivieren
- Strato generiert den DKIM-Key und setzt den DNS-Record automatisch

### 3. DMARC anpassen (nach SPF+DKIM)
```
_dmarc.ariia.ai. IN TXT "v=DMARC1; p=quarantine; rua=mailto:dmarc@ariia.ai; ruf=mailto:dmarc@ariia.ai; pct=100"
```
- Erst auf `quarantine` setzen, nach Verifizierung auf `reject` zurücksetzen
- rua/ruf für Reporting-Mails
