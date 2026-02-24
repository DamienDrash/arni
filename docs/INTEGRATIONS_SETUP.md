# ARIIA – Integrationen: Einrichtungsanleitung

Dieses Dokument beschreibt die Einrichtung aller verfügbaren Integrationen in ARIIA. Jede Integration kann direkt im ARIIA-Dashboard unter **Einstellungen → Integrationen** konfiguriert werden. Die dort integrierte Schritt-für-Schritt-Anleitung (Sidebar) führt durch den gesamten Prozess.

---

## Inhaltsverzeichnis

1. [Architektur-Übersicht](#architektur-übersicht)
2. [Messaging-Kanäle](#messaging-kanäle)
   - [Telegram](#telegram)
   - [WhatsApp (QR-Modus)](#whatsapp-qr-modus)
   - [WhatsApp (Meta Business API)](#whatsapp-meta-business-api)
   - [Instagram DM](#instagram-dm-beta)
   - [Facebook Messenger](#facebook-messenger-beta)
   - [Google Business Messages](#google-business-messages-beta)
3. [E-Mail](#e-mail)
   - [SMTP / E-Mail-Versand](#smtp--e-mail-versand)
   - [Postmark (E-Mail-Kanal)](#postmark-e-mail-kanal)
4. [Telefonie & Voice](#telefonie--voice)
   - [SMS (Twilio)](#sms-twilio)
   - [Voice (Twilio)](#voice-twilio)
5. [Mitglieder-Quellen](#mitglieder-quellen)
   - [Magicline](#magicline)
   - [Shopify](#shopify)
   - [WooCommerce](#woocommerce)
6. [CRM-Systeme](#crm-systeme)
   - [HubSpot](#hubspot)
7. [Connector Hub API](#connector-hub-api)
8. [Fehlerbehebung](#fehlerbehebung)

---

## Architektur-Übersicht

ARIIA verwendet ein **einheitliches Connector-System** (Connector Hub), das alle Integrationen zentral verwaltet:

| Komponente | Beschreibung |
|:---|:---|
| **Connector Registry** | Zentrale Definition aller Integrationen mit Feldern, Kategorien und Setup-Docs (`app/integrations/connector_registry.py`) |
| **Connector Hub Router** | Einheitliche API für Katalog, Konfiguration, Tests und Docs (`app/gateway/routers/connector_hub.py`) |
| **Frontend Integrations-Seite** | Einheitliche UI mit Karten-Übersicht, Detail-Konfiguration und Docs-Sidebar (`frontend/app/settings/integrations/page.tsx`) |
| **Webhook-Router** | Empfängt eingehende Nachrichten von allen Plattformen (`app/gateway/routers/webhooks.py`) |
| **Normalizer** | Normalisiert Nachrichten aller Plattformen in ein einheitliches Format (`app/integrations/normalizer.py`) |
| **Dispatcher** | Sendet Antworten über den richtigen Kanal zurück (`app/integrations/dispatcher.py`) |

### Konfigurationsfluss

```
Dashboard → Connector Hub API → persistence (DB Settings) → Integration Client
```

Alle Konfigurationswerte werden als Tenant-spezifische Settings in der Datenbank gespeichert. Sensitive Werte (Tokens, Secrets) werden in API-Responses maskiert.

---

## Messaging-Kanäle

### Telegram

**Kategorie:** Messaging | **Schwierigkeit:** Einfach | **Dauer:** 5 Minuten

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| **Bot Token** | Authentifizierungstoken für den Bot | BotFather in Telegram |
| Admin Chat ID | Chat-ID für Admin-Benachrichtigungen (optional) | Telegram API |
| Webhook Secret | Absicherung des Webhooks (optional) | Frei wählbar |

#### Schritt-für-Schritt

1. **BotFather öffnen:** Suche in Telegram nach `@BotFather` und starte einen Chat.
2. **Bot erstellen:** Sende `/newbot`. Wähle einen Namen und einen Benutzernamen (muss auf `bot` enden, z.B. `MeinStudioBot`).
3. **Token kopieren:** Du erhältst ein Token im Format `1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`. Kopiere es.
4. **In ARIIA eintragen:** Dashboard → Einstellungen → Integrationen → Telegram → Bot Token einfügen → Speichern.
5. **Admin Chat ID (optional):** Sende eine Nachricht an deinen Bot, dann öffne `https://api.telegram.org/bot<TOKEN>/getUpdates` im Browser. Die `chat.id` ist deine Chat-ID.
6. **Testen:** Klicke auf "Verbindung testen". Bei Erfolg wird der Bot-Benutzername angezeigt.

> **Webhook:** ARIIA richtet den Webhook automatisch ein. Die URL lautet: `https://{deine-domain}/webhook/telegram/{tenant_slug}`

---

### WhatsApp (QR-Modus)

**Kategorie:** Messaging | **Schwierigkeit:** Sehr einfach | **Dauer:** 2 Minuten

Der QR-Modus funktioniert wie WhatsApp Web — keine API-Registrierung nötig.

#### Schritt-für-Schritt

1. **Integration öffnen:** Dashboard → Einstellungen → Integrationen → WhatsApp.
2. **Modus wählen:** Stelle sicher, dass "QR-Code / WhatsApp Web (Bridge)" ausgewählt ist.
3. **QR-Code anzeigen:** Klicke auf "QR-Code anzeigen & verbinden".
4. **Smartphone:** Öffne WhatsApp → Menü (⋮) → Verknüpfte Geräte → Gerät hinzufügen.
5. **Scannen:** Scanne den QR-Code mit deinem Smartphone.

> **Wichtig:** Das Smartphone muss dauerhaft mit dem Internet verbunden bleiben, damit die Bridge funktioniert.

---

### WhatsApp (Meta Business API)

**Kategorie:** Messaging | **Schwierigkeit:** Mittel | **Dauer:** 30–60 Minuten

Die offizielle Meta Cloud API bietet höhere Zuverlässigkeit und Durchsatz als der QR-Modus.

#### Voraussetzungen

- Meta Business Account (verifiziert)
- Facebook-Seite für dein Unternehmen

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| **Phone Number ID** | ID der WhatsApp-Telefonnummer | Meta Developer Dashboard |
| **Access Token** | Permanenter System User Token | Meta Business Manager |
| **Verify Token** | Frei wählbar, für Webhook-Verifizierung | Selbst festlegen |
| App Secret | Für Webhook-Signaturprüfung (optional) | Meta Developer Dashboard |

#### Schritt-für-Schritt

1. **Meta Developer Account:** Registriere dich auf [developers.facebook.com](https://developers.facebook.com/).
2. **App erstellen:** Meine Apps → App erstellen → Typ "Business" → Use Case "WhatsApp".
3. **Telefonnummer:** Im WhatsApp-Setup: Nummer hinzufügen oder Test-Nummer verwenden. **Phone Number ID** notieren.
4. **System User Token:** [Business Settings → System Users](https://business.facebook.com/settings/system-users) → System User erstellen (Admin) → Token generieren mit Berechtigungen:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
5. **Webhook:** Developer Dashboard → WhatsApp → Configuration → Webhook URL:
   ```
   https://{deine-domain}/webhook/whatsapp/{tenant_slug}
   ```
   Verify Token: Derselbe wie in ARIIA konfiguriert. Felder abonnieren: `messages`.
6. **App Secret:** Dashboard → App Settings → Basic → App Secret kopieren.
7. **In ARIIA:** Alle Werte eintragen → Speichern → Testen.

> **Warnung:** Teile den Access Token niemals öffentlich. Jeder mit dem Token kann Nachrichten im Namen deines Unternehmens senden.

---

### Instagram DM (Beta)

**Kategorie:** Messaging | **Schwierigkeit:** Mittel | **Dauer:** 30–45 Minuten

#### Voraussetzungen

- Instagram Professional Account (Business oder Creator)
- Facebook-Seite, verknüpft mit dem Instagram-Account
- Meta Developer Account

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| **Instagram Page ID** | Instagram Business Account ID | Meta Developer Dashboard |
| **Page Access Token** | Langlebiger Token mit `instagram_manage_messages` | Graph API Explorer |
| App Secret | Für Webhook-Signaturprüfung (optional) | Meta Developer Dashboard |

#### Schritt-für-Schritt

1. **Professional Account:** Instagram-App → Einstellungen → Konto → Zu professionellem Konto wechseln.
2. **Facebook verknüpfen:** Instagram → Einstellungen → Konto → Verknüpfte Konten → Facebook-Seite auswählen.
3. **Meta App:** [developers.facebook.com/apps](https://developers.facebook.com/apps/) → App erstellen oder bestehende verwenden → Produkt "Instagram" hinzufügen.
4. **Berechtigungen:** App benötigt `instagram_manage_messages` und `pages_manage_metadata`.
5. **Token:** [Graph API Explorer](https://developers.facebook.com/tools/explorer/) → App wählen → "Page Access Token" → Seite wählen → Token generieren → In langlebigen Token umwandeln.
6. **Webhook:** Developer Dashboard → Instagram → Webhooks → Callback URL:
   ```
   https://{deine-domain}/webhook/instagram/{tenant_slug}
   ```
   Feld abonnieren: `messages`.

> **Hinweis:** Im Entwicklungsmodus funktioniert die API nur mit Testnutzern. Für den Produktivbetrieb ist ein **App Review** durch Meta erforderlich.

---

### Facebook Messenger (Beta)

**Kategorie:** Messaging | **Schwierigkeit:** Mittel | **Dauer:** 20–40 Minuten

#### Voraussetzungen

- Meta Business Account
- Facebook-Seite

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| **Facebook Page ID** | ID der Facebook-Seite | Seiteneinstellungen → Allgemein |
| **Page Access Token** | Langlebiger Token mit `pages_messaging` | Meta Developer Dashboard |
| Verify Token | Frei wählbar (optional) | Selbst festlegen |
| App Secret | Für Signaturprüfung (optional) | Meta Developer Dashboard |

#### Schritt-für-Schritt

1. **Facebook-Seite:** Falls nötig: [facebook.com/pages/create](https://www.facebook.com/pages/create).
2. **Meta App:** [developers.facebook.com/apps](https://developers.facebook.com/apps/) → App erstellen → Typ "Business" → Produkt "Messenger" hinzufügen.
3. **Seite verknüpfen:** Messenger-Setup → "Seiten hinzufügen oder entfernen" → Seite auswählen → Page Access Token generieren.
4. **Berechtigungen:** `pages_messaging`, `pages_manage_metadata` — App Review für Live-Modus erforderlich.
5. **Webhook:** Messenger → Settings → Webhooks → Callback URL:
   ```
   https://{deine-domain}/webhook/facebook/{tenant_slug}
   ```
   Abonnieren: `messages`, `messaging_postbacks`.
6. **Permanenter Token:** [Business Manager → System Users](https://business.facebook.com/settings/system-users) → System User erstellen → Permanenten Token generieren.

> **Hinweis:** Der Standard-Token läuft nach 60 Tagen ab. Verwende einen System User Token für permanenten Zugang.

---

### Google Business Messages (Beta)

**Kategorie:** Messaging | **Schwierigkeit:** Fortgeschritten | **Dauer:** 45–90 Minuten

#### Voraussetzungen

- Verifiziertes Google Business Profile
- Google Cloud Projekt

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| **Agent ID** | Agent-Identifikator | Business Communications Console |
| **Service Account JSON** | Google Cloud Service Account Key | Google Cloud Console |

#### Schritt-für-Schritt

1. **Business Profile:** [business.google.com](https://business.google.com/) → Standort verifizieren.
2. **Business Communications:** [business-communications.cloud.google.com](https://business-communications.cloud.google.com/console/) → Als Partner registrieren → Agent erstellen.
3. **Google Cloud:** [console.cloud.google.com](https://console.cloud.google.com/) → Projekt erstellen → "Business Messages API" aktivieren → Service Account erstellen → JSON-Key herunterladen.
4. **Webhook:** Business Communications Console → Agent → Integration → Webhook URL:
   ```
   https://{deine-domain}/webhook/google-business/{tenant_slug}
   ```
5. **Testen:** Business Messages Test-App verwenden → Nach erfolgreichem Test: Launch beantragen.

> **Warnung:** Der Launch-Prozess kann mehrere Tage dauern und erfordert eine Prüfung durch Google.

---

## E-Mail

### SMTP / E-Mail-Versand

**Kategorie:** E-Mail | **Schwierigkeit:** Einfach | **Dauer:** 5 Minuten

Wird für Verifizierungscodes, Benachrichtigungen und Systemmail verwendet.

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Beispiel |
|:---|:---|:---|
| **SMTP Host** | Server-Adresse | `smtp.gmail.com` |
| **SMTP Port** | Port (meist 587 für TLS) | `587` |
| **Benutzername** | Login-Name | `noreply@mein-studio.de` |
| **Passwort** | SMTP-Passwort oder App-Passwort | |
| **Absender-E-Mail** | Von-Adresse | `noreply@mein-studio.de` |

#### Gängige SMTP-Provider

| Provider | Host | Port | Hinweis |
|:---|:---|:---|:---|
| Gmail | `smtp.gmail.com` | 587 | App-Passwort erforderlich |
| Outlook/Microsoft 365 | `smtp.office365.com` | 587 | |
| IONOS | `smtp.ionos.de` | 587 | |
| Strato | `smtp.strato.de` | 465 | SSL statt TLS |
| All-Inkl | `smtp.all-inkl.com` | 587 | |

> **Gmail:** Unter [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) ein App-Passwort erstellen (2FA muss aktiviert sein).

---

### Postmark (E-Mail-Kanal)

**Kategorie:** E-Mail | **Schwierigkeit:** Einfach | **Dauer:** 10 Minuten

Postmark wird als dedizierter E-Mail-Kanal für eingehende und ausgehende Kundenkommunikation verwendet.

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| Kanal aktiviert | Ein/Aus | Dashboard |
| **Postmark Server Token** | API-Token des Servers | Postmark Dashboard |
| **Absender-E-Mail** | Verifizierte Absender-Adresse | Postmark Sender Signatures |

#### Schritt-für-Schritt

1. **Konto erstellen:** [postmarkapp.com](https://postmarkapp.com/) → Registrieren.
2. **Server erstellen:** Dashboard → Servers → Add Server.
3. **Token kopieren:** Server → API Tokens → Server API Token kopieren.
4. **Absender verifizieren:** Sender Signatures → Add Sender Signature → E-Mail-Adresse bestätigen.
5. **In ARIIA:** Token und Absender-E-Mail eintragen → Aktivieren → Testen.

---

## Telefonie & Voice

### SMS (Twilio)

**Kategorie:** Telefonie | **Schwierigkeit:** Einfach | **Dauer:** 15 Minuten

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| Kanal aktiviert | Ein/Aus | Dashboard |
| **Twilio Account SID** | Account-Identifikator | Twilio Console |
| **Twilio Auth Token** | Authentifizierungstoken | Twilio Console |
| **Twilio SMS-Nummer** | Telefonnummer für SMS | Twilio Phone Numbers |

#### Schritt-für-Schritt

1. **Konto erstellen:** [twilio.com](https://www.twilio.com/try-twilio) → Registrieren.
2. **Credentials:** Console Dashboard → Account SID und Auth Token kopieren.
3. **Nummer kaufen:** Phone Numbers → Buy a Number → Land wählen → SMS-fähige Nummer kaufen.
4. **In ARIIA:** SID, Token und Nummer eintragen → Aktivieren → Testen.

---

### Voice (Twilio)

**Kategorie:** Telefonie | **Schwierigkeit:** Einfach | **Dauer:** 15 Minuten

Verwendet dieselben Twilio-Credentials wie SMS, aber mit einer Voice-fähigen Nummer.

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| Kanal aktiviert | Ein/Aus | Dashboard |
| **Twilio Voice-Nummer** | Telefonnummer für Anrufe | Twilio Phone Numbers |
| **Stream-URL** | WebSocket-URL für Voice-Streaming | ARIIA-Konfiguration |

#### Schritt-für-Schritt

1. **Twilio-Konto:** Wie bei SMS (kann dasselbe Konto sein).
2. **Voice-Nummer:** Phone Numbers → Buy a Number → Voice-fähige Nummer wählen.
3. **Webhook:** Phone Numbers → Konfiguration → Voice → "A call comes in" → Webhook URL:
   ```
   https://{deine-domain}/voice/incoming/{tenant_slug}
   ```
4. **Stream-URL:** Die WebSocket-URL für das Voice-Streaming:
   ```
   wss://{deine-domain}/voice/stream
   ```

---

## Mitglieder-Quellen

### Magicline

**Kategorie:** Mitglieder | **Schwierigkeit:** Einfach | **Dauer:** 10 Minuten

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| **API Base URL** | Magicline API-Endpunkt | Magicline Support |
| **API Key** | Authentifizierungsschlüssel | Magicline Dashboard |
| Studio ID | Standort-ID (optional) | Magicline Dashboard |

#### Schritt-für-Schritt

1. **API-Zugang beantragen:** Kontaktiere den Magicline-Support und beantrage API-Zugang für dein Studio.
2. **Credentials erhalten:** Du erhältst eine Base URL und einen API Key.
3. **In ARIIA:** Base URL und API Key eintragen → Testen → Sync starten.

---

### Shopify

**Kategorie:** Mitglieder | **Schwierigkeit:** Einfach | **Dauer:** 10 Minuten

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| **Shop Domain** | Shopify-Shop-Domain | Shopify Admin |
| **Admin API Access Token** | API-Zugriffstoken | Shopify Admin → Apps |

#### Schritt-für-Schritt

1. **Shopify Admin:** Melde dich in deinem [Shopify Admin](https://admin.shopify.com/) an.
2. **Custom App erstellen:** Settings → Apps and sales channels → Develop apps → Create an app → Name: "ARIIA Sync".
3. **API Scopes:** Configure Admin API scopes → Aktiviere:
   - `read_customers`
   - `read_orders` (optional, für Bestelldaten)
4. **App installieren:** Install app → Admin API access token kopieren.
5. **Shop Domain:** Deine Domain ist `mein-shop.myshopify.com` (ohne `https://`).
6. **In ARIIA:** Domain und Token eintragen → Testen → Sync starten.

> **Hinweis:** Der Access Token wird nur einmal angezeigt. Speichere ihn sofort.

---

### WooCommerce

**Kategorie:** Mitglieder | **Schwierigkeit:** Einfach | **Dauer:** 10 Minuten

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| **Store URL** | WordPress/WooCommerce-URL | Browser-Adressleiste |
| **Consumer Key** | API-Schlüssel | WooCommerce REST API |
| **Consumer Secret** | API-Geheimnis | WooCommerce REST API |

#### Schritt-für-Schritt

1. **WordPress Admin:** Melde dich in deinem WordPress-Admin an.
2. **REST API:** WooCommerce → Settings → Advanced → REST API → Add key.
3. **Key erstellen:** Beschreibung: "ARIIA Sync" → Benutzer: Admin → Berechtigungen: "Read" → Generate API key.
4. **Keys kopieren:** Consumer Key (`ck_...`) und Consumer Secret (`cs_...`) sofort kopieren.
5. **In ARIIA:** Store URL, Consumer Key und Secret eintragen → Testen → Sync starten.

> **Warnung:** Die Keys werden nur einmal angezeigt und können nicht erneut abgerufen werden. WooCommerce erfordert HTTPS.

---

## CRM-Systeme

### HubSpot

**Kategorie:** CRM | **Schwierigkeit:** Einfach | **Dauer:** 10 Minuten

#### Benötigte Zugangsdaten

| Feld | Beschreibung | Wo zu finden |
|:---|:---|:---|
| **Private App Access Token** | API-Token einer Private App | HubSpot Settings |

#### Schritt-für-Schritt

1. **HubSpot Settings:** Melde dich an → Zahnrad (Settings) → Integrations → Private Apps.
2. **App erstellen:** Create a private app → Name: "ARIIA Sync".
3. **Scopes:** Tab "Scopes" → CRM → `crm.objects.contacts.read` aktivieren. Optional: `crm.objects.companies.read`.
4. **Erstellen:** Create app → Bestätigen → Access Token kopieren (beginnt mit `pat-`).
5. **In ARIIA:** Token eintragen → Testen → Sync starten.

---

## Connector Hub API

Alle Integrationen können auch programmatisch über die Connector Hub API verwaltet werden:

| Endpoint | Methode | Beschreibung |
|:---|:---|:---|
| `/admin/connector-hub/catalog` | GET | Alle Connectors mit Status |
| `/admin/connector-hub/{id}/config` | GET | Aktuelle Konfiguration (maskiert) |
| `/admin/connector-hub/{id}/config` | PUT | Konfiguration aktualisieren |
| `/admin/connector-hub/{id}/config` | DELETE | Konfiguration löschen |
| `/admin/connector-hub/{id}/setup-docs` | GET | Setup-Dokumentation |
| `/admin/connector-hub/{id}/test` | POST | Verbindung testen |

### Beispiel: Telegram konfigurieren via API

```bash
curl -X PUT https://{domain}/arni/admin/connector-hub/telegram/config \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"bot_token": "1234567890:ABC..."}'
```

---

## Fehlerbehebung

### Häufige Probleme

| Problem | Ursache | Lösung |
|:---|:---|:---|
| "Token ungültig" | Abgelaufener oder falscher Token | Neuen Token generieren |
| "Webhook nicht erreichbar" | Server nicht öffentlich erreichbar | Domain/SSL prüfen, Firewall-Regeln |
| "Verbindung fehlgeschlagen" | Netzwerkproblem oder falscher Hostname | URL und Erreichbarkeit prüfen |
| "Berechtigung fehlt" | Token hat nicht die nötigen Scopes | Token mit korrekten Berechtigungen neu erstellen |
| "Rate Limit" | Zu viele API-Aufrufe | Sync-Intervall erhöhen |

### Logs prüfen

```bash
docker compose logs ariia-core | grep "connector_hub"
docker compose logs ariia-core | grep "webhook"
```

### Konfiguration zurücksetzen

Im Dashboard: Connector öffnen → "Zurücksetzen" klicken. Oder via API:

```bash
curl -X DELETE https://{domain}/arni/admin/connector-hub/{connector_id}/config \
  -H "Authorization: Bearer {token}"
```
