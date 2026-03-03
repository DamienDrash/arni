# ARIIA SaaS – Pricing & Plan Strategie

Basierend auf den im System verankerten Funktionen (Abo-Typen, Feature-Gates für WhatsApp/Telegram/Voice, Message-Limits und Analyzer) habe ich folgendes **modulare Pricing-Modell** für ARIIA entworfen. Dieses Modell richtet sich an Fitnessstudios (B2B) und skaliert mit deren Größe und Anforderungen.

Alle Pläne werden **monatlich** oder **jährlich (mit 20 % Rabatt)** angeboten.

---

## 1. Die Kern-Pläne (Tiered Model)

### 🥉 Starter (Der Einstieg für Mikro-Studios & Boutiquen)
*Fokus: Automatisierung der grundlegenden Kundenanfragen auf einem Kanal.*
- **Preis (Monatlich):** 49,00 € / Monat
- **Preis (Jährlich):** 470,00 € / Jahr (~39,00 € / Monat)
- **Inklusive Limits:**
  - Max. 1 Kanal (z.B. Telegram oder Web-Chat)
  - Bis zu 500 aktive Mitglieder synchronisiert
  - Bis zu 1.000 KI-Nachrichten pro Monat
- **Kern-Features:**
  - Standard-KI-Agent ("ARIIA Core")
  - Basis Magicline-Integration (Kunden-Sync)
- **Nicht enthalten:** WhatsApp, Voice, Custom Prompts, Memory Analyzer.

### 🥈 Pro (Der Standard für etablierte Studios)
*Fokus: Omnichannel-Erlebnis und proaktive Kundenbindung.*
- **Preis (Monatlich):** 149,00 € / Monat
- **Preis (Jährlich):** 1.430,00 € / Jahr (~119,00 € / Monat)
- **Inklusive Limits:**
  - Max. 2 Kanäle (inklusive **WhatsApp**)
  - Bis zu 2.500 aktive Mitglieder synchronisiert
  - Bis zu 5.000 KI-Nachrichten pro Monat
- **Kern-Features:** Alle *Starter*-Features +
  - Erweiterte Magicline-Integration (Check-in Stats, Buchungen)
  - Memory Analyzer (Erkenntnisse aus vergangenen Chats für personalisierte Ansprache)
  - Custom Prompts (Anpassbare Tonalität & Studio-Regeln)

### 🥇 Enterprise / Scale (Für Studioketten & Premium-Clubs)
*Fokus: Volle Power, alle Kanäle, höchste Automatisierung.*
- **Preis (Monatlich):** 399,00 € / Monat
- **Preis (Jährlich):** 3.830,00 € / Jahr (~319,00 € / Monat)
- **Inklusive Limits:**
  - Unlimitierte Kanäle (WhatsApp, Telegram, SMS, Email, Plattform-Chat)
  - Bis zu 10.000 aktive Mitglieder (darüber hinaus Custom Pricing)
  - Bis zu 25.000 KI-Nachrichten pro Monat
- **Kern-Features:** Alle *Pro*-Features +
  - **Voice enabled** (Sprachnachrichten-Verarbeitung)
  - Dedizierter Support & Onboarding
  - Audit Logs & Governance Console (Sicherheits-Feature)

---

## 2. Das Modulare Add-on System
Um flexibel auf spezielle Kundenwünsche einzugehen, können Nutzer der kleineren Pläne gezielt Features hinzubuchen (Modulares Upselling).

| Add-on Modul | Beschreibung | Preis (Monatlich) |
| :--- | :--- | :--- |
| **WhatsApp Business API** | Freischaltung von WhatsApp als Kommunikationskanal (im Starter-Plan regulär nicht drin). | + 30,00 € / Monat |
| **Voice / Speech-to-Text** | ARIIA kann Sprachnachrichten verarbeiten und beantworten. | + 50,00 € / Monat |
| **Volume Boost: Messages** | Paket für weitere 5.000 KI-Nachrichten, falls das Limit erreicht wird. | + 29,00 € / Paket |
| **Volume Boost: Members** | Paket für die Synchronisierung von 1.000 weiteren aktiven Mitgliedern. | + 19,00 € / Paket |
| **AI Memory & Analytics** | Freischaltung des `memory_analyzer` Moduls (Standard nur ab Pro). | + 49,00 € / Monat |

---

## 3. Empfehlungen für die Markteinführung

1. **Testphasen (Trialing):** 
   Setze in Stripe eine automatische **14-tägige kostenlose Testphase** für den "Pro" Plan an. In dieser Zeit dürfen Studios den vollen Umfang (inklusive WhatsApp) testen. Da die Datenbank das Feld `trial_ends_at` unterstützt, lässt sich das nahtlos integrieren.
2. **Fair Use Policy bei Metriken:**
   Die Tabelle `UsageRecord` zählt brav die `llm_tokens_used` und `messages_inbound/outbound`. Berechne ggf. Overage-Fees (z.B. 0,02 € pro zusätzlicher Nachricht) automatisch über Stripe Usage-Based Billing "Metered Billing", statt den Service direkt hart abzuschalten. Das liefert unaufdringlich mehr Umsatz (Expansion Revenue).
3. **Onboarding-Fee (Einmalig):**
   Für den Start mit der Magicline-Verknüpfung und WhatsApp-Nummer-Registrierung kann man eine Setup-Gebühr von **199 € - 149 €** erheben, um die anfänglichen Support-Kosten zu decken. (Beim Jahresabo oft als "inklusive" verkauft).
