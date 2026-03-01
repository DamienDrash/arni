"""app/integrations/connector_docs.py — n8n-Style Connector Documentation.

Structured documentation for every connector, served via the Connector Hub API.
Each entry follows the pattern:
  - overview: Short description for the docs listing
  - title: Full title for the docs page
  - difficulty: easy | medium | advanced
  - estimated_time: Setup time estimate
  - prerequisites: List of things needed before setup
  - use_cases: What this connector enables
  - steps: Step-by-step setup instructions
  - faq: Frequently asked questions
  - troubleshooting: Common issues and fixes
  - links: External documentation links
"""
from __future__ import annotations
from typing import Dict, Any

CONNECTOR_DOCS: Dict[str, Dict[str, Any]] = {

    # ══════════════════════════════════════════════════════════════════════════
    # MESSAGING
    # ══════════════════════════════════════════════════════════════════════════

    "whatsapp": {
        "title": "WhatsApp Business API",
        "overview": "Verbinde dein WhatsApp Business-Konto, um Nachrichten automatisch zu empfangen und zu beantworten. ARIIA wird zum intelligenten Assistenten hinter deiner WhatsApp-Nummer.",
        "difficulty": "medium",
        "estimated_time": "10–15 Min.",
        "prerequisites": [
            "Ein Meta Business-Konto (business.facebook.com)",
            "Eine verifizierte Telefonnummer für WhatsApp Business",
            "Zugang zum Meta Developer Portal (developers.facebook.com)",
        ],
        "use_cases": [
            "Automatische Beantwortung von Kundenanfragen rund um die Uhr",
            "Terminbuchungen und -erinnerungen per WhatsApp",
            "Versand von Angeboten, Rechnungen und Statusupdates",
            "Interaktive Buchungsflows mit WhatsApp Flows",
        ],
        "steps": [
            {
                "title": "Modus wählen",
                "description": "Wähle zwischen **QR-Code** (schnell, für kleine Teams) oder **API-Modus** (für die offizielle WhatsApp Business API mit Meta Cloud). Der QR-Modus verbindet dein bestehendes WhatsApp direkt. Der API-Modus erfordert ein Meta Developer-Konto.",
                "tip": "Für den Produktivbetrieb empfehlen wir den API-Modus – er bietet höhere Zuverlässigkeit und offizielle Meta-Unterstützung.",
            },
            {
                "title": "API-Zugangsdaten eingeben (nur API-Modus)",
                "description": "Gehe zu **developers.facebook.com** > Deine App > WhatsApp > API Setup. Kopiere die **Phone Number ID** und den **Permanent Access Token**. Füge sie hier in die entsprechenden Felder ein.",
                "tip": "Erstelle einen permanenten System User Token unter Business Settings > System Users, damit der Token nicht abläuft.",
            },
            {
                "title": "Webhook konfigurieren",
                "description": "ARIIA generiert automatisch eine Webhook-URL und einen Verify Token für dich. Kopiere beide Werte und trage sie in deiner Meta App unter **WhatsApp > Configuration > Webhook** ein. Abonniere die Felder: `messages` und `messaging_postbacks`.",
                "tip": "Die Webhook-URL findest du direkt im Onboarding-Wizard unter 'Webhook-Informationen'.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen', um zu prüfen, ob ARIIA Nachrichten empfangen und senden kann. Sende anschließend eine Testnachricht an deine WhatsApp-Nummer.",
            },
        ],
        "faq": [
            {
                "question": "Kann ich meine bestehende WhatsApp-Nummer verwenden?",
                "answer": "Ja, im QR-Modus kannst du deine bestehende Nummer direkt verbinden. Im API-Modus benötigst du eine bei Meta registrierte Business-Nummer.",
            },
            {
                "question": "Was passiert, wenn ARIIA nicht antworten kann?",
                "answer": "Wenn ARIIA unsicher ist, wird die Nachricht automatisch an einen menschlichen Mitarbeiter eskaliert (Handoff).",
            },
            {
                "question": "Wie viele Nachrichten kann ich senden?",
                "answer": "Das hängt von deinem Meta Business-Tier und deinem ARIIA-Plan ab. Im Starter-Plan sind 500 AI-Resolutions pro Monat enthalten.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Webhook-Verifizierung schlägt fehl",
                "solution": "Stelle sicher, dass der Verify Token exakt übereinstimmt (keine Leerzeichen). Prüfe, ob die Webhook-URL korrekt kopiert wurde.",
            },
            {
                "issue": "Nachrichten werden nicht empfangen",
                "solution": "Prüfe in der Meta App, ob das Webhook-Feld 'messages' abonniert ist. Stelle sicher, dass die App live geschaltet ist (nicht im Entwicklungsmodus).",
            },
        ],
        "links": [
            {"label": "Meta WhatsApp Business API Docs", "url": "https://developers.facebook.com/docs/whatsapp/cloud-api"},
            {"label": "WhatsApp Business Platform", "url": "https://business.whatsapp.com/"},
        ],
    },

    "telegram": {
        "title": "Telegram Bot",
        "overview": "Erstelle einen Telegram-Bot und verbinde ihn mit ARIIA, um Kundenanfragen über Telegram automatisch zu beantworten.",
        "difficulty": "easy",
        "estimated_time": "3–5 Min.",
        "prerequisites": [
            "Ein Telegram-Konto",
            "Zugang zu @BotFather auf Telegram",
        ],
        "use_cases": [
            "Automatische Beantwortung von Kundenanfragen über Telegram",
            "Support-Bot für technische Anfragen",
            "Benachrichtigungen und Statusupdates an Kunden",
        ],
        "steps": [
            {
                "title": "Bot bei @BotFather erstellen",
                "description": "Öffne Telegram und suche nach **@BotFather**. Sende `/newbot` und folge den Anweisungen. Du erhältst einen **Bot Token** – kopiere diesen.",
                "tip": "Wähle einen professionellen Bot-Namen, der zu deinem Unternehmen passt (z.B. 'MeineFirma_Support_Bot').",
            },
            {
                "title": "Bot Token eingeben",
                "description": "Füge den Bot Token hier ein. ARIIA konfiguriert den Webhook automatisch, sodass alle eingehenden Nachrichten verarbeitet werden.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen'. Sende anschließend eine Nachricht an deinen Bot auf Telegram, um zu prüfen, ob ARIIA antwortet.",
            },
        ],
        "faq": [
            {
                "question": "Kann ich einen bestehenden Bot verwenden?",
                "answer": "Ja, solange du den Bot Token hast. Beachte, dass der Webhook auf ARIIA umgestellt wird.",
            },
            {
                "question": "Kann ich den Bot anpassen?",
                "answer": "Ja, über @BotFather kannst du Name, Beschreibung und Profilbild deines Bots ändern.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Bot antwortet nicht",
                "solution": "Prüfe, ob der Bot Token korrekt ist. Stelle sicher, dass du den Bot gestartet hast (/start).",
            },
        ],
        "links": [
            {"label": "Telegram Bot API Docs", "url": "https://core.telegram.org/bots/api"},
            {"label": "BotFather", "url": "https://t.me/botfather"},
        ],
    },

    "sms": {
        "title": "SMS (Twilio)",
        "overview": "Sende und empfange SMS-Nachrichten über Twilio. Ideal für Terminerinnerungen, Bestätigungen und Zwei-Faktor-Authentifizierung.",
        "difficulty": "medium",
        "estimated_time": "5–10 Min.",
        "prerequisites": [
            "Ein Twilio-Konto (twilio.com)",
            "Eine Twilio-Telefonnummer mit SMS-Fähigkeit",
            "Account SID und Auth Token aus der Twilio Console",
        ],
        "use_cases": [
            "Automatische Terminerinnerungen per SMS",
            "Bestätigungsnachrichten nach Buchungen",
            "Zwei-Faktor-Authentifizierung (2FA)",
            "Marketing-Kampagnen per SMS",
        ],
        "steps": [
            {
                "title": "Twilio-Konto erstellen",
                "description": "Registriere dich auf **twilio.com** und verifiziere dein Konto. Du erhältst ein Startguthaben zum Testen.",
                "tip": "Im Trial-Modus kannst du nur an verifizierte Nummern senden. Für den Produktivbetrieb musst du dein Konto upgraden.",
            },
            {
                "title": "Zugangsdaten eingeben",
                "description": "Kopiere **Account SID** und **Auth Token** aus der Twilio Console (Dashboard). Gib außerdem deine Twilio-Telefonnummer ein.",
            },
            {
                "title": "Webhook konfigurieren",
                "description": "ARIIA generiert eine Webhook-URL. Trage diese in der Twilio Console unter **Phone Numbers > Active Numbers > deine Nummer > Messaging > Webhook** ein.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen' und sende eine Test-SMS an deine Twilio-Nummer.",
            },
        ],
        "faq": [
            {
                "question": "Was kostet eine SMS über Twilio?",
                "answer": "Die Kosten variieren je nach Land. In Deutschland ca. 0,07 € pro SMS. Aktuelle Preise findest du auf twilio.com/sms/pricing.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "SMS werden nicht empfangen",
                "solution": "Prüfe, ob die Webhook-URL in der Twilio Console korrekt eingetragen ist. Stelle sicher, dass die Nummer SMS-fähig ist.",
            },
        ],
        "links": [
            {"label": "Twilio SMS Docs", "url": "https://www.twilio.com/docs/sms"},
            {"label": "Twilio Console", "url": "https://console.twilio.com/"},
        ],
    },

    "twilio_voice": {
        "title": "Twilio Voice (Telefonie)",
        "overview": "Empfange und tätige Anrufe über Twilio. ARIIA kann als intelligenter Telefonassistent fungieren und Anrufe automatisch bearbeiten.",
        "difficulty": "advanced",
        "estimated_time": "10–15 Min.",
        "prerequisites": [
            "Ein Twilio-Konto mit Voice-Fähigkeit",
            "Eine Twilio-Telefonnummer mit Voice-Support",
            "Account SID und Auth Token",
        ],
        "use_cases": [
            "Automatische Anrufannahme und -weiterleitung",
            "IVR-Menüs (Interactive Voice Response)",
            "Outbound-Anrufe für Terminerinnerungen",
            "Voice-AI-Assistenten für Kundenservice",
        ],
        "steps": [
            {
                "title": "Twilio Voice einrichten",
                "description": "Stelle sicher, dass deine Twilio-Nummer Voice-fähig ist. Gehe in die Twilio Console und aktiviere Voice für deine Nummer.",
            },
            {
                "title": "Zugangsdaten eingeben",
                "description": "Gib Account SID, Auth Token und deine Voice-Telefonnummer ein. Optional: Erstelle eine TwiML App für erweiterte Steuerung.",
                "tip": "Eine TwiML App ermöglicht erweiterte Anruf-Steuerung wie Warteschlangen, Aufnahmen und Konferenzschaltungen.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen'. Rufe anschließend deine Twilio-Nummer an, um zu prüfen, ob ARIIA den Anruf annimmt.",
            },
        ],
        "faq": [
            {
                "question": "Kann ARIIA Anrufe aufzeichnen?",
                "answer": "Ja, mit aktivierter Aufnahme-Funktion. Beachte die lokalen Datenschutzgesetze (DSGVO) und informiere den Anrufer.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Anrufe werden nicht angenommen",
                "solution": "Prüfe die TwiML-Konfiguration und stelle sicher, dass der Voice-Webhook korrekt eingerichtet ist.",
            },
        ],
        "links": [
            {"label": "Twilio Voice Docs", "url": "https://www.twilio.com/docs/voice"},
        ],
    },

    "smtp_email": {
        "title": "E-Mail (SMTP & IMAP)",
        "overview": "Verbinde deinen eigenen Mailserver, um E-Mails über ARIIA zu senden und zu empfangen. Volle Kontrolle über deine E-Mail-Infrastruktur.",
        "difficulty": "medium",
        "estimated_time": "5–10 Min.",
        "prerequisites": [
            "SMTP-Serverdaten (Host, Port, Benutzername, Passwort)",
            "Optional: IMAP-Serverdaten für den E-Mail-Empfang",
        ],
        "use_cases": [
            "E-Mail-Versand über den eigenen Mailserver",
            "Automatische Antworten auf eingehende E-Mails",
            "Newsletter und Transaktions-E-Mails",
        ],
        "steps": [
            {
                "title": "SMTP-Daten eingeben",
                "description": "Gib den SMTP-Host, Port (meist 587 für TLS oder 465 für SSL), Benutzername und Passwort ein. Diese Daten findest du bei deinem E-Mail-Provider.",
                "tip": "Die meisten Provider nutzen Port 587 mit STARTTLS. Gmail, Outlook und andere große Provider unterstützen dies.",
            },
            {
                "title": "IMAP-Daten eingeben (optional)",
                "description": "Für den E-Mail-Empfang gib den IMAP-Host und Port (meist 993 für SSL) ein. ARIIA prüft dann regelmäßig dein Postfach.",
            },
            {
                "title": "Absender konfigurieren",
                "description": "Gib die Absender-E-Mail-Adresse und den Absendernamen ein. Diese werden in allen ausgehenden E-Mails angezeigt.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen'. ARIIA prüft sowohl die SMTP- als auch die IMAP-Verbindung.",
            },
        ],
        "faq": [
            {
                "question": "Kann ich Gmail verwenden?",
                "answer": "Ja, verwende smtp.gmail.com (Port 587) und imap.gmail.com (Port 993). Du benötigst ein App-Passwort (nicht dein normales Gmail-Passwort).",
            },
            {
                "question": "Was ist der Unterschied zu Postmark?",
                "answer": "SMTP/IMAP nutzt deinen eigenen Mailserver. Postmark ist ein spezialisierter Transaktions-E-Mail-Dienst mit höherer Zustellrate.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Authentifizierung fehlgeschlagen",
                "solution": "Prüfe Benutzername und Passwort. Bei Gmail: Erstelle ein App-Passwort unter myaccount.google.com > Sicherheit.",
            },
            {
                "issue": "Verbindung wird abgelehnt",
                "solution": "Prüfe Host und Port. Stelle sicher, dass dein Mailserver externe Verbindungen erlaubt.",
            },
        ],
        "links": [
            {"label": "Gmail SMTP-Einstellungen", "url": "https://support.google.com/mail/answer/7126229"},
        ],
    },

    "postmark": {
        "title": "Postmark (Transaktions-E-Mail)",
        "overview": "Nutze Postmark für zuverlässigen Transaktions-E-Mail-Versand mit branchenführender Zustellrate. Ideal für geschäftskritische E-Mails.",
        "difficulty": "easy",
        "estimated_time": "3–5 Min.",
        "prerequisites": [
            "Ein Postmark-Konto (postmarkapp.com)",
            "Ein Server API Token aus der Postmark Console",
        ],
        "use_cases": [
            "Transaktions-E-Mails (Bestätigungen, Rechnungen)",
            "Passwort-Reset und Verifizierungs-E-Mails",
            "Hohe Zustellrate für geschäftskritische Nachrichten",
        ],
        "steps": [
            {
                "title": "Postmark-Konto erstellen",
                "description": "Registriere dich auf **postmarkapp.com** und erstelle einen Server. Kopiere den **Server API Token**.",
            },
            {
                "title": "Token und Absender eingeben",
                "description": "Füge den Server API Token ein. Gib die Absender-E-Mail und den Namen ein. Die Absender-Adresse muss in Postmark verifiziert sein.",
                "tip": "Verifiziere deine Domain in Postmark für bessere Zustellraten (SPF, DKIM).",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen', um zu prüfen, ob der API Token gültig ist.",
            },
        ],
        "faq": [
            {
                "question": "Was kostet Postmark?",
                "answer": "Postmark bietet 100 kostenlose E-Mails pro Monat. Danach ab ca. $1.25 pro 1.000 E-Mails.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Token ungültig",
                "solution": "Stelle sicher, dass du den Server API Token verwendest (nicht den Account API Token).",
            },
        ],
        "links": [
            {"label": "Postmark Docs", "url": "https://postmarkapp.com/developer"},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # MEMBERS / CRM
    # ══════════════════════════════════════════════════════════════════════════

    "magicline": {
        "title": "Magicline (Fitness-CRM)",
        "overview": "Synchronisiere Mitglieder, Check-ins und Vertragsdaten aus Magicline. Ideal für Fitnessstudios und Gesundheitseinrichtungen.",
        "difficulty": "easy",
        "estimated_time": "3–5 Min.",
        "prerequisites": [
            "Ein Magicline-Konto mit API-Zugang",
            "API-Key aus der Magicline-Verwaltung",
        ],
        "use_cases": [
            "Automatische Mitglieder-Synchronisation",
            "Check-in-Daten für personalisierte Kommunikation",
            "Vertragsverlängerungen und Kündigungsprävention",
        ],
        "steps": [
            {
                "title": "API-Zugang aktivieren",
                "description": "Kontaktiere den Magicline-Support oder gehe in die Verwaltung, um den API-Zugang zu aktivieren. Du erhältst eine **API Base URL** und einen **API Key**.",
            },
            {
                "title": "Zugangsdaten eingeben",
                "description": "Gib die API Base URL und den API Key ein. Optional: Gib die Studio ID ein, wenn du mehrere Standorte hast.",
            },
            {
                "title": "Verbindung testen und synchronisieren",
                "description": "Klicke auf 'Verbindung testen'. Nach erfolgreicher Verbindung startet die erste Synchronisation automatisch.",
            },
        ],
        "faq": [
            {
                "question": "Wie oft werden Daten synchronisiert?",
                "answer": "Standardmäßig alle 15 Minuten. Du kannst die Frequenz in den erweiterten Einstellungen anpassen.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "API-Verbindung fehlgeschlagen",
                "solution": "Prüfe, ob die Base URL korrekt ist (inkl. https://). Stelle sicher, dass der API Key aktiv ist.",
            },
        ],
        "links": [
            {"label": "Magicline API Docs", "url": "https://www.magicline.com/"},
        ],
    },

    "shopify": {
        "title": "Shopify",
        "overview": "Synchronisiere Kunden und Bestelldaten aus deinem Shopify-Store. Ermöglicht personalisierte Kommunikation basierend auf Kaufverhalten.",
        "difficulty": "medium",
        "estimated_time": "5–10 Min.",
        "prerequisites": [
            "Ein Shopify-Store mit Admin-Zugang",
            "Ein Custom App mit Admin API Token",
        ],
        "use_cases": [
            "Kundendaten-Synchronisation aus Shopify",
            "Automatische Bestellbestätigungen und Versandbenachrichtigungen",
            "Personalisierte Produktempfehlungen",
        ],
        "steps": [
            {
                "title": "Custom App erstellen",
                "description": "Gehe in deinem Shopify-Admin zu **Settings > Apps and sales channels > Develop apps**. Erstelle eine neue App und konfiguriere die Admin API-Berechtigungen (mindestens: read_customers, read_orders).",
            },
            {
                "title": "API Token kopieren",
                "description": "Nach der Installation der App erhältst du einen **Admin API Access Token**. Kopiere diesen zusammen mit deiner Shop-Domain.",
            },
            {
                "title": "Verbindung testen",
                "description": "Gib Shop-Domain und Token ein, dann klicke auf 'Verbindung testen'.",
            },
        ],
        "faq": [
            {
                "question": "Welche Shopify-Pläne werden unterstützt?",
                "answer": "Alle Shopify-Pläne ab Basic. Custom Apps sind in allen Plänen verfügbar.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Zugriff verweigert",
                "solution": "Prüfe die API-Berechtigungen deiner Custom App. Stelle sicher, dass read_customers aktiviert ist.",
            },
        ],
        "links": [
            {"label": "Shopify Admin API Docs", "url": "https://shopify.dev/docs/api/admin-rest"},
        ],
    },

    "hubspot": {
        "title": "HubSpot CRM",
        "overview": "Synchronisiere Kontakte und Deals aus HubSpot CRM. Nutze CRM-Daten für intelligente, kontextbezogene Kommunikation.",
        "difficulty": "easy",
        "estimated_time": "3–5 Min.",
        "prerequisites": [
            "Ein HubSpot-Konto (kostenlos oder bezahlt)",
            "Ein Private App Token aus den HubSpot-Einstellungen",
        ],
        "use_cases": [
            "Kontakt-Synchronisation mit HubSpot CRM",
            "Deal-Tracking und automatische Follow-ups",
            "Lead-Scoring basierend auf Interaktionen",
        ],
        "steps": [
            {
                "title": "Private App erstellen",
                "description": "Gehe in HubSpot zu **Settings > Integrations > Private Apps**. Erstelle eine neue App und wähle die Berechtigungen: crm.objects.contacts.read, crm.objects.deals.read.",
            },
            {
                "title": "Token eingeben",
                "description": "Kopiere den **Private App Token** und füge ihn hier ein.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen', um die API-Verbindung zu prüfen.",
            },
        ],
        "faq": [
            {
                "question": "Funktioniert das mit dem kostenlosen HubSpot-Plan?",
                "answer": "Ja, Private Apps sind in allen HubSpot-Plänen verfügbar, auch im kostenlosen CRM.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Token ungültig",
                "solution": "Stelle sicher, dass du den Token der Private App verwendest (beginnt mit 'pat-').",
            },
        ],
        "links": [
            {"label": "HubSpot API Docs", "url": "https://developers.hubspot.com/docs/api/overview"},
        ],
    },

    "salesforce": {
        "title": "Salesforce CRM",
        "overview": "Verbinde Salesforce für Enterprise-CRM-Integration. Synchronisiere Kontakte, Leads und Opportunities für datengetriebene Kommunikation.",
        "difficulty": "advanced",
        "estimated_time": "15–20 Min.",
        "prerequisites": [
            "Ein Salesforce-Konto mit API-Zugang",
            "Eine Connected App in Salesforce Setup",
            "Client ID, Client Secret und Refresh Token",
        ],
        "use_cases": [
            "Enterprise-CRM-Synchronisation",
            "Lead-Management und automatische Qualifizierung",
            "Opportunity-Tracking mit KI-gestützten Insights",
        ],
        "steps": [
            {
                "title": "Connected App erstellen",
                "description": "Gehe in Salesforce zu **Setup > App Manager > New Connected App**. Aktiviere OAuth und wähle die Scopes: api, refresh_token, offline_access.",
            },
            {
                "title": "OAuth-Flow durchführen",
                "description": "Nutze die Client ID und das Client Secret, um einen Refresh Token zu erhalten. Gib alle drei Werte zusammen mit deiner Instance URL ein.",
                "tip": "Verwende den OAuth 2.0 Web Server Flow für den sichersten Zugang.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen'. ARIIA prüft die API-Verbindung und zeigt den verbundenen Salesforce-Org-Namen an.",
            },
        ],
        "faq": [
            {
                "question": "Welche Salesforce-Editionen werden unterstützt?",
                "answer": "Alle Editionen mit API-Zugang: Enterprise, Unlimited, Developer und Performance.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "INVALID_SESSION_ID Fehler",
                "solution": "Der Refresh Token ist abgelaufen. Erstelle einen neuen über den OAuth-Flow.",
            },
        ],
        "links": [
            {"label": "Salesforce REST API Docs", "url": "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/"},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # PAYMENTS
    # ══════════════════════════════════════════════════════════════════════════

    "stripe": {
        "title": "Stripe Payments",
        "overview": "Akzeptiere Online-Zahlungen und verwalte Abonnements mit Stripe. Die weltweit führende Zahlungsplattform für Unternehmen jeder Größe.",
        "difficulty": "medium",
        "estimated_time": "5–10 Min.",
        "prerequisites": [
            "Ein Stripe-Konto (stripe.com)",
            "Publishable Key und Secret Key aus dem Stripe Dashboard",
        ],
        "use_cases": [
            "Online-Zahlungen und Checkout",
            "Abonnement-Verwaltung (Recurring Payments)",
            "Rechnungsstellung und Gutschriften",
        ],
        "steps": [
            {
                "title": "API-Keys kopieren",
                "description": "Gehe im Stripe Dashboard zu **Developers > API Keys**. Kopiere den **Publishable Key** und den **Secret Key**.",
                "tip": "Verwende zunächst die Test-Keys (beginnen mit 'pk_test_' und 'sk_test_'), um die Integration zu testen.",
            },
            {
                "title": "Keys eingeben",
                "description": "Füge beide Keys in die entsprechenden Felder ein. Optional: Konfiguriere einen Webhook Signing Secret für Echtzeit-Events.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen'. ARIIA prüft die API-Verbindung und zeigt deinen Stripe-Account-Namen an.",
            },
        ],
        "faq": [
            {
                "question": "Kann ich im Testmodus starten?",
                "answer": "Ja, verwende die Test-API-Keys. Alle Transaktionen im Testmodus sind kostenlos und simuliert.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Secret Key ungültig",
                "solution": "Stelle sicher, dass du den richtigen Key-Typ verwendest (Test vs. Live). Der Secret Key beginnt mit 'sk_'.",
            },
        ],
        "links": [
            {"label": "Stripe API Docs", "url": "https://stripe.com/docs/api"},
            {"label": "Stripe Dashboard", "url": "https://dashboard.stripe.com/"},
        ],
    },

    "paypal": {
        "title": "PayPal",
        "overview": "Akzeptiere PayPal-Zahlungen weltweit. Unterstützt Einmalzahlungen, Abonnements und PayPal Checkout.",
        "difficulty": "medium",
        "estimated_time": "5–10 Min.",
        "prerequisites": [
            "Ein PayPal Business-Konto",
            "Client ID und Client Secret aus dem PayPal Developer Portal",
        ],
        "use_cases": [
            "PayPal-Zahlungen akzeptieren",
            "Abonnements über PayPal",
            "Internationale Zahlungen",
        ],
        "steps": [
            {
                "title": "App im Developer Portal erstellen",
                "description": "Gehe zu **developer.paypal.com** und erstelle eine REST API App. Du erhältst Client ID und Client Secret.",
            },
            {
                "title": "Zugangsdaten eingeben",
                "description": "Gib Client ID, Client Secret und den Modus (Sandbox oder Live) ein.",
                "tip": "Starte im Sandbox-Modus zum Testen. Wechsle erst zu Live, wenn alles funktioniert.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen', um die OAuth-Authentifizierung zu prüfen.",
            },
        ],
        "faq": [
            {
                "question": "Was ist der Unterschied zwischen Sandbox und Live?",
                "answer": "Sandbox ist die Testumgebung – keine echten Zahlungen. Live verarbeitet echte Transaktionen.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Authentifizierung fehlgeschlagen",
                "solution": "Prüfe, ob Client ID und Secret zum gewählten Modus (Sandbox/Live) passen.",
            },
        ],
        "links": [
            {"label": "PayPal Developer Docs", "url": "https://developer.paypal.com/docs/"},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # SCHEDULING
    # ══════════════════════════════════════════════════════════════════════════

    "calendly": {
        "title": "Calendly",
        "overview": "Ermögliche Terminbuchungen über Calendly. ARIIA kann Buchungslinks teilen und Termine automatisch verwalten.",
        "difficulty": "easy",
        "estimated_time": "3–5 Min.",
        "prerequisites": [
            "Ein Calendly-Konto (kostenlos oder bezahlt)",
            "Ein Personal Access Token aus den Calendly-Einstellungen",
        ],
        "use_cases": [
            "Automatische Terminbuchung über Chat",
            "Terminerinnerungen und Follow-ups",
            "Verfügbarkeitsabfragen in Echtzeit",
        ],
        "steps": [
            {
                "title": "Personal Access Token erstellen",
                "description": "Gehe in Calendly zu **Integrations > API & Webhooks > Personal Access Tokens**. Erstelle einen neuen Token.",
            },
            {
                "title": "Token eingeben",
                "description": "Füge den Token hier ein. ARIIA verbindet sich automatisch mit deinem Calendly-Konto.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen'. ARIIA zeigt deinen Calendly-Benutzernamen an.",
            },
        ],
        "faq": [
            {
                "question": "Funktioniert das mit dem kostenlosen Calendly-Plan?",
                "answer": "Ja, die API ist in allen Calendly-Plänen verfügbar.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Token ungültig",
                "solution": "Erstelle einen neuen Token in den Calendly-Einstellungen. Tokens können ablaufen.",
            },
        ],
        "links": [
            {"label": "Calendly API Docs", "url": "https://developer.calendly.com/"},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # AI & VOICE
    # ══════════════════════════════════════════════════════════════════════════

    "elevenlabs": {
        "title": "ElevenLabs (Voice AI)",
        "overview": "Nutze ultra-realistische KI-Stimmen von ElevenLabs für Voice-Assistenten, Anrufbearbeitung und Audio-Content.",
        "difficulty": "easy",
        "estimated_time": "3–5 Min.",
        "prerequisites": [
            "Ein ElevenLabs-Konto (elevenlabs.io)",
            "Ein API Key aus den ElevenLabs-Einstellungen",
        ],
        "use_cases": [
            "Voice-AI-Assistenten mit natürlichen Stimmen",
            "Automatische Anrufbearbeitung",
            "Audio-Content-Erstellung",
            "Mehrsprachige Voice-Bots",
        ],
        "steps": [
            {
                "title": "API Key erstellen",
                "description": "Gehe auf **elevenlabs.io** und navigiere zu **Profile > API Key**. Kopiere den Key.",
            },
            {
                "title": "Stimme und Modell wählen",
                "description": "Gib den API Key ein und wähle optional eine Standard-Voice-ID und das Modell (empfohlen: eleven_multilingual_v2 für mehrsprachige Unterstützung).",
                "tip": "Du kannst eigene Stimmen in ElevenLabs klonen und die Voice-ID hier verwenden.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen', um die API-Verbindung zu prüfen.",
            },
        ],
        "faq": [
            {
                "question": "Wie viele Zeichen kann ich pro Monat generieren?",
                "answer": "Das hängt von deinem ElevenLabs-Plan ab. Der kostenlose Plan bietet 10.000 Zeichen pro Monat.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "API Key ungültig",
                "solution": "Erstelle einen neuen API Key in deinem ElevenLabs-Profil.",
            },
        ],
        "links": [
            {"label": "ElevenLabs API Docs", "url": "https://docs.elevenlabs.io/api-reference"},
            {"label": "ElevenLabs Voice Library", "url": "https://elevenlabs.io/voice-library"},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ANALYTICS
    # ══════════════════════════════════════════════════════════════════════════

    "google_analytics": {
        "title": "Google Analytics",
        "overview": "Tracke Kundeninteraktionen und Conversion-Events mit Google Analytics. Messe den Erfolg deiner AI-Assistenten.",
        "difficulty": "medium",
        "estimated_time": "5–10 Min.",
        "prerequisites": [
            "Ein Google Analytics 4 Property",
            "Measurement ID und API Secret",
        ],
        "use_cases": [
            "Tracking von Chatbot-Interaktionen",
            "Conversion-Messung für AI-gestützte Buchungen",
            "Analyse der Kundenzufriedenheit",
        ],
        "steps": [
            {
                "title": "Measurement ID finden",
                "description": "Gehe in Google Analytics zu **Admin > Data Streams > Web**. Kopiere die **Measurement ID** (beginnt mit 'G-').",
            },
            {
                "title": "API Secret erstellen",
                "description": "In Google Analytics: **Admin > Data Streams > dein Stream > Measurement Protocol API Secrets**. Erstelle ein neues Secret.",
            },
            {
                "title": "Verbindung testen",
                "description": "Gib Measurement ID und API Secret ein, dann klicke auf 'Verbindung testen'.",
            },
        ],
        "faq": [
            {
                "question": "Welche Events werden getrackt?",
                "answer": "ARIIA sendet Custom Events wie 'ai_conversation_start', 'ai_resolution', 'ai_handoff' und 'ai_booking'.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Events erscheinen nicht in GA4",
                "solution": "Events können bis zu 24 Stunden verzögert sein. Prüfe im Realtime-Report, ob Events ankommen.",
            },
        ],
        "links": [
            {"label": "GA4 Measurement Protocol", "url": "https://developers.google.com/analytics/devguides/collection/protocol/ga4"},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # PAYMENT & BILLING
    # ══════════════════════════════════════════════════════════════════════════

    "stripe": {
        "title": "Stripe Payment & Billing",
        "overview": "Verbinde Stripe für automatische Zahlungsabwicklung, Abonnement-Verwaltung und verbrauchsbasierte Abrechnung. ARIIA verwaltet den kompletten Billing-Lifecycle deiner Kunden.",
        "difficulty": "medium",
        "estimated_time": "10–15 Min.",
        "prerequisites": [
            "Ein Stripe-Konto (stripe.com)",
            "Zugang zum Stripe Dashboard",
            "Secret Key und Publishable Key aus dem Dashboard",
        ],
        "use_cases": [
            "Automatische Abonnement-Verwaltung (Upgrade, Downgrade, Kündigung)",
            "Checkout-Sessions für neue Kunden erstellen",
            "Rechnungen und Zahlungshistorie abrufen",
            "Verbrauchsbasierte Abrechnung (Conversations, API-Calls, Tokens)",
            "Plan-Limits und Feature-Gates durchsetzen",
        ],
        "steps": [
            {
                "title": "Stripe-Konto vorbereiten",
                "description": "Melde dich bei **stripe.com** an und stelle sicher, dass dein Konto aktiviert ist. Für Tests kannst du den Testmodus verwenden.",
                "tip": "Im Testmodus kannst du mit Testkarten (z.B. 4242 4242 4242 4242) Zahlungen simulieren, ohne echtes Geld zu bewegen.",
            },
            {
                "title": "API-Keys kopieren",
                "description": "Gehe zu **Stripe Dashboard** > Developers > API Keys. Kopiere den **Secret Key** (beginnt mit sk_test_ oder sk_live_). Füge ihn hier in das Feld 'API Key' ein.",
                "tip": "Verwende für die Ersteinrichtung den Test-Key. Wechsle erst nach erfolgreichen Tests zum Live-Key.",
            },
            {
                "title": "Webhook einrichten",
                "description": "Gehe zu **Stripe Dashboard** > Developers > Webhooks > Add Endpoint. Trage die Webhook-URL ein, die dir ARIIA anzeigt. Wähle die Events: checkout.session.completed, customer.subscription.updated, customer.subscription.deleted, invoice.paid, invoice.payment_failed.",
                "tip": "Das Webhook-Signing-Secret (whsec_...) wird benötigt, um die Echtheit der Events zu verifizieren.",
            },
            {
                "title": "Produkte & Preise anlegen",
                "description": "Erstelle in Stripe unter Products deine Abo-Pläne (z.B. Starter, Professional, Business). Notiere die Price IDs (price_...) – diese werden für Checkout-Sessions benötigt.",
                "tip": "ARIIA synchronisiert die Pläne automatisch. Änderungen in Stripe werden beim nächsten Sync übernommen.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen'. ARIIA prüft den API-Key und zeigt den Kontostatus an.",
            },
        ],
        "faq": [
            {
                "question": "Was passiert bei einem Plan-Upgrade?",
                "answer": "Bei einem Upgrade wird automatisch eine anteilige Berechnung (Proration) erstellt. Der Kunde zahlt nur die Differenz für den Rest der Abrechnungsperiode.",
            },
            {
                "question": "Kann ich den Testmodus verwenden?",
                "answer": "Ja! Verwende den Test-Secret-Key (sk_test_...) und Stripe-Testkarten. Alle Funktionen arbeiten identisch zum Live-Modus.",
            },
            {
                "question": "Wie funktioniert die verbrauchsbasierte Abrechnung?",
                "answer": "ARIIA trackt automatisch Conversations, API-Calls und Token-Verbrauch. Am Ende jeder Abrechnungsperiode wird der Verbrauch an Stripe gemeldet.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "Webhook-Events kommen nicht an",
                "solution": "Prüfe im Stripe Dashboard unter Webhooks > Recent Events, ob Events gesendet werden. Stelle sicher, dass die Webhook-URL korrekt ist und das Signing Secret übereinstimmt.",
            },
            {
                "issue": "Checkout-Session zeigt Fehler",
                "solution": "Stelle sicher, dass die Price ID gültig ist und der Stripe-Account aktiviert ist. Im Testmodus müssen Test-Price-IDs verwendet werden.",
            },
        ],
        "links": [
            {"label": "Stripe API Dokumentation", "url": "https://stripe.com/docs/api"},
            {"label": "Stripe Checkout Guide", "url": "https://stripe.com/docs/payments/checkout"},
            {"label": "Stripe Webhooks", "url": "https://stripe.com/docs/webhooks"},
        ],
    },

    "paypal": {
        "title": "PayPal Payment",
        "overview": "Verbinde PayPal für Zahlungen, Abonnements und Auszahlungen. Ideal als zusätzliche Zahlungsoption neben Stripe – besonders beliebt bei Endkunden.",
        "difficulty": "medium",
        "estimated_time": "10–15 Min.",
        "prerequisites": [
            "Ein PayPal Business-Konto (paypal.com)",
            "Zugang zum PayPal Developer Portal (developer.paypal.com)",
            "Eine App mit Client ID und Secret im Developer Portal",
        ],
        "use_cases": [
            "Einmalzahlungen über PayPal Checkout",
            "Wiederkehrende Abonnements über PayPal Billing",
            "Auszahlungen an Partner und Affiliates",
            "PayPal als alternative Zahlungsmethode anbieten",
        ],
        "steps": [
            {
                "title": "PayPal Developer App erstellen",
                "description": "Gehe zu **developer.paypal.com** > My Apps & Credentials. Klicke auf 'Create App' und vergib einen Namen (z.B. 'ARIIA Integration'). Wähle 'Merchant' als App-Typ.",
                "tip": "Erstelle zuerst eine Sandbox-App zum Testen. Du kannst später zur Live-App wechseln.",
            },
            {
                "title": "Client ID und Secret kopieren",
                "description": "Nach dem Erstellen der App siehst du die **Client ID** und den **Secret**. Kopiere beide Werte und füge sie hier in die entsprechenden Felder ein.",
                "tip": "Der Secret wird nur einmal angezeigt. Speichere ihn sicher ab.",
            },
            {
                "title": "Sandbox/Live-Modus wählen",
                "description": "Wähle den **Sandbox-Modus** für Tests oder den **Live-Modus** für echte Zahlungen. Im Sandbox-Modus kannst du mit Test-Konten Zahlungen simulieren.",
                "tip": "PayPal stellt automatisch Sandbox-Käufer- und Verkäufer-Konten bereit, die du unter Sandbox > Accounts findest.",
            },
            {
                "title": "Webhooks einrichten (optional)",
                "description": "Gehe zu deiner App > Webhooks > Add Webhook. Trage die von ARIIA angezeigte URL ein und wähle relevante Events (PAYMENT.CAPTURE.COMPLETED, BILLING.SUBSCRIPTION.*).",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen'. ARIIA authentifiziert sich bei PayPal und zeigt den Status an.",
            },
        ],
        "faq": [
            {
                "question": "Kann ich PayPal und Stripe gleichzeitig nutzen?",
                "answer": "Ja! Viele Unternehmen bieten beide Optionen an. Kunden können bei der Zahlung wählen, welche Methode sie bevorzugen.",
            },
            {
                "question": "Wie funktionieren Auszahlungen?",
                "answer": "Über die Payout-Funktion kannst du Geld direkt an PayPal-Email-Adressen senden – ideal für Affiliate-Provisionen oder Partner-Vergütungen.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "OAuth-Token kann nicht bezogen werden",
                "solution": "Prüfe, ob Client ID und Secret korrekt sind und zum gewählten Modus (Sandbox/Live) passen. Sandbox-Credentials funktionieren nicht im Live-Modus und umgekehrt.",
            },
            {
                "issue": "Zahlung wird abgelehnt",
                "solution": "Im Sandbox-Modus: Verwende die Standard-Sandbox-Käufer-Credentials. Im Live-Modus: Stelle sicher, dass das PayPal-Konto verifiziert und nicht eingeschränkt ist.",
            },
        ],
        "links": [
            {"label": "PayPal REST API Dokumentation", "url": "https://developer.paypal.com/docs/api/overview/"},
            {"label": "PayPal Checkout Integration", "url": "https://developer.paypal.com/docs/checkout/"},
            {"label": "PayPal Webhooks Guide", "url": "https://developer.paypal.com/docs/api-basics/notifications/webhooks/"},
        ],
    },

    "mollie": {
        "title": "Mollie Payment",
        "overview": "Verbinde Mollie für europäische Zahlungsmethoden wie iDEAL, SEPA-Lastschrift, Bancontact und Sofort. Perfekt für den europäischen Markt mit einfacher Integration.",
        "difficulty": "easy",
        "estimated_time": "5–10 Min.",
        "prerequisites": [
            "Ein Mollie-Konto (mollie.com)",
            "API Key aus dem Mollie Dashboard",
        ],
        "use_cases": [
            "Europäische Zahlungsmethoden anbieten (iDEAL, SEPA, Bancontact, Sofort)",
            "Kreditkartenzahlungen über Mollie abwickeln",
            "Wiederkehrende Zahlungen und Abonnements",
            "Rückerstattungen direkt aus ARIIA verarbeiten",
        ],
        "steps": [
            {
                "title": "Mollie-Konto erstellen",
                "description": "Registriere dich bei **mollie.com** und vervollständige die Verifizierung deines Unternehmens. Mollie prüft dein Unternehmen und aktiviert die gewünschten Zahlungsmethoden.",
                "tip": "Die Verifizierung dauert in der Regel 1–2 Werktage. Du kannst aber sofort im Testmodus starten.",
            },
            {
                "title": "API Key kopieren",
                "description": "Gehe zu **Mollie Dashboard** > Developers > API Keys. Kopiere den **Test API Key** (beginnt mit test_) oder den **Live API Key** (beginnt mit live_). Füge ihn hier ein.",
                "tip": "Der Test-Key funktioniert mit simulierten Zahlungen. Wechsle zum Live-Key, sobald du bereit für echte Zahlungen bist.",
            },
            {
                "title": "Zahlungsmethoden aktivieren",
                "description": "Gehe im Mollie Dashboard zu **Settings** > Payment Methods und aktiviere die gewünschten Methoden (iDEAL, Kreditkarte, SEPA, etc.).",
                "tip": "Einige Methoden (z.B. Kreditkarte) erfordern eine zusätzliche Aktivierung durch Mollie.",
            },
            {
                "title": "Verbindung testen",
                "description": "Klicke auf 'Verbindung testen'. ARIIA prüft den API-Key und zeigt die verfügbaren Zahlungsmethoden an.",
            },
        ],
        "faq": [
            {
                "question": "Welche Zahlungsmethoden unterstützt Mollie?",
                "answer": "Mollie unterstützt über 20 Methoden: iDEAL, Kreditkarte, SEPA-Lastschrift, Bancontact, Sofort, Giropay, EPS, Przelewy24, Apple Pay, und mehr.",
            },
            {
                "question": "Was kostet Mollie?",
                "answer": "Mollie berechnet nur pro Transaktion – keine monatlichen Gebühren. Die Kosten variieren je nach Zahlungsmethode (z.B. iDEAL: €0,29, Kreditkarte: 1,8% + €0,25).",
            },
            {
                "question": "Kann ich Mollie und Stripe gleichzeitig nutzen?",
                "answer": "Ja! Mollie eignet sich besonders für europäische Methoden wie iDEAL und SEPA, während Stripe global stärker ist. Beide können parallel betrieben werden.",
            },
        ],
        "troubleshooting": [
            {
                "issue": "API Key wird nicht akzeptiert",
                "solution": "Stelle sicher, dass du den vollständigen Key kopiert hast (beginnt mit test_ oder live_). Prüfe, ob dein Mollie-Konto aktiv ist.",
            },
            {
                "issue": "Zahlungsmethode nicht verfügbar",
                "solution": "Prüfe im Mollie Dashboard, ob die Methode aktiviert ist. Einige Methoden sind nur für bestimmte Währungen oder Länder verfügbar.",
            },
        ],
        "links": [
            {"label": "Mollie API Dokumentation", "url": "https://docs.mollie.com/"},
            {"label": "Mollie Zahlungsmethoden", "url": "https://www.mollie.com/payments"},
            {"label": "Mollie Recurring Payments", "url": "https://docs.mollie.com/payments/recurring"},
        ],
    },
}
