"use client";

/**
 * ARIIA – Allgemeine Geschäftsbedingungen / Terms of Service
 * Production-ready SaaS AGB, bilingual DE/EN.
 * Covers: subscription plans, usage quotas, AI disclaimers, data, termination.
 */
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { motion } from "framer-motion";
import { useI18n } from "@/lib/i18n/LanguageContext";

/* ─── Styles ──────────────────────────────────────────────────────────────── */
const C = {
  bg:      "oklch(0.08 0.02 270)",
  text:    "oklch(0.65 0.015 270)",
  heading: "oklch(0.97 0.005 270)",
  muted:   "oklch(0.45 0.015 270)",
  accent:  "oklch(0.55 0.18 270)",
  border:  "oklch(0.18 0.02 270)",
  badge:   "oklch(0.14 0.03 270)",
};

/* ─── Types ───────────────────────────────────────────────────────────────── */
type Block =
  | { type: "text";   text: string }
  | { type: "list";   items: string[] }
  | { type: "indent"; items: string[] };
interface Section { heading: string; blocks: Block[]; }
interface PageContent {
  title: string;
  subtitle: string;
  lastUpdated: string;
  legalNote: string;
  sections: Section[];
}

/* ─── Content ─────────────────────────────────────────────────────────────── */
const CONTENT: Record<"de" | "en", PageContent> = {
  de: {
    title: "Allgemeine Geschäftsbedingungen",
    subtitle: "ARIIA SaaS-Plattform – B2B-Nutzungsbedingungen",
    lastUpdated: "Stand: März 2026",
    legalNote:
      "Diese AGB gelten ausschließlich für Unternehmer (§ 14 BGB). ARIIA wird nicht an Verbraucher (§ 13 BGB) vermarktet.",
    sections: [
      {
        heading: "§ 1 Geltungsbereich und Vertragsparteien",
        blocks: [
          {
            type: "text",
            text: "1.1 Diese Allgemeinen Geschäftsbedingungen (nachfolgend \"AGB\") gelten für sämtliche Verträge über die Nutzung der cloudbasierten SaaS-Plattform ARIIA (nachfolgend \"Plattform\"), die zwischen [PLACEHOLDER: Unternehmensname] (nachfolgend \"ARIIA\") und dem jeweiligen Unternehmen (nachfolgend \"Tenant\" oder \"Kunde\") abgeschlossen werden.",
          },
          {
            type: "text",
            text: "1.2 ARIIA richtet sich ausschließlich an Unternehmer im Sinne des § 14 BGB. Die Leistungen von ARIIA sind nicht für Verbraucher (§ 13 BGB) bestimmt.",
          },
          {
            type: "text",
            text: "1.3 Abweichende, entgegenstehende oder ergänzende Allgemeine Geschäftsbedingungen des Kunden werden nicht Vertragsbestandteil, es sei denn, ARIIA stimmt ihrer Geltung ausdrücklich schriftlich zu.",
          },
        ],
      },
      {
        heading: "§ 2 Leistungsbeschreibung",
        blocks: [
          {
            type: "text",
            text: "2.1 ARIIA stellt dem Tenant im Wege des Software-as-a-Service (SaaS) Zugang zu folgenden Funktionen bereit:",
          },
          {
            type: "list",
            items: [
              "KI-gestützte Kommunikationsagenten für WhatsApp Business API, Telegram, SMS und E-Mail",
              "Sprachassistenten (Voice) in stub- und produktivem Modus",
              "Kampagnenmanagement inkl. KI-Inhaltserstellung, Segmentierung, Versandplanung und A/B-Tests",
              "Kontaktmanagement (CRM) mit Tags, Segmenten und Kontakthistorie",
              "Wissensspeicher (Knowledge Base) mit Dokumentenupload und KI-Retrieval (RAG)",
              "Omnichannel-Orchestrierung und Sequenz-Kampagnen",
              "Admin-Dashboard mit Nutzer-, Rollen- und Mandantenverwaltung",
              "API-Zugang für eigene Integrationen",
            ],
          },
          {
            type: "text",
            text: "2.2 Der Umfang der verfügbaren Funktionen richtet sich nach dem gebuchten Abonnement-Plan (Starter, Pro oder Enterprise). Die aktuellen Leistungsmerkmale je Plan sind auf www.ariia.ai/pricing veröffentlicht.",
          },
          {
            type: "text",
            text: "2.3 ARIIA erbringt seine Leistungen über eine Mehrmieter-Architektur (Multi-Tenant). Jeder Tenant erhält eine vollständig isolierte Umgebung. ARIIA gewährleistet die Mandantentrennung durch technische Maßnahmen (Datenbankisolation nach tenant_id).",
          },
          {
            type: "text",
            text: "2.4 ARIIA ist berechtigt, die Plattform kontinuierlich weiterzuentwickeln und Leistungsmerkmale zu ergänzen, anzupassen oder einzustellen, sofern der vertraglich vereinbarte Leistungsumfang nicht wesentlich eingeschränkt wird.",
          },
        ],
      },
      {
        heading: "§ 3 Vertragsschluss und Account-Erstellung",
        blocks: [
          {
            type: "text",
            text: "3.1 Der Vertrag kommt durch Registrierung des Tenants auf www.ariia.ai und Bestätigung der Registrierung durch ARIIA zustande.",
          },
          {
            type: "text",
            text: "3.2 Mit der Registrierung erhält der Tenant automatisch einen Starter-Plan-Zugang. Der Wechsel zu Pro oder Enterprise erfolgt durch gesonderte Buchung.",
          },
          {
            type: "text",
            text: "3.3 Der Tenant ist verpflichtet, bei der Registrierung vollständige und wahrheitsgemäße Angaben zu machen. Änderungen sind unverzüglich zu aktualisieren.",
          },
          {
            type: "text",
            text: "3.4 Zugangsdaten sind vom Tenant geheim zu halten. Für Handlungen, die unter seinem Account vorgenommen werden, ist der Tenant verantwortlich.",
          },
        ],
      },
      {
        heading: "§ 4 Abonnement-Pläne und Kontingente",
        blocks: [
          {
            type: "text",
            text: "4.1 ARIIA bietet folgende Abonnement-Pläne an:",
          },
          {
            type: "indent",
            items: [
              "Starter: Grundfunktionen, begrenzte Nachrichten- und KI-Kontingente, geeignet für Studios im Aufbau.",
              "Pro: Erweiterte Funktionen, höhere Kontingente, A/B-Testing, Omnichannel-Sequenzen.",
              "Enterprise: Voller Funktionsumfang, angepasste Kontingente, dedizierter Support, individuelle AVV-Vereinbarungen.",
            ],
          },
          {
            type: "text",
            text: "4.2 Die konkreten monatlichen Kontingente (Nachrichten, KI-Tokens, Speicher, Bildgenerierungen) je Plan sind in den Plandetails auf www.ariia.ai/pricing sowie im Admin-Dashboard einsehbar.",
          },
          {
            type: "text",
            text: "4.3 Bei Überschreitung von Kontingentgrenzen gibt die Plattform einen HTTP 429-Fehler zurück (Quota exhausted) und informiert den Tenant im Dashboard. Weitere Nutzung in der betroffenen Kategorie ist bis zur nächsten Abrechnungsperiode oder nach Upgrade eingeschränkt.",
          },
          {
            type: "text",
            text: "4.4 Nicht verbrauchte Kontingente verfallen am Ende der Abrechnungsperiode und werden nicht übertragen.",
          },
        ],
      },
      {
        heading: "§ 5 Preise, Zahlung und Rechnungsstellung",
        blocks: [
          {
            type: "text",
            text: "5.1 Die aktuell gültigen Preise sind auf www.ariia.ai/pricing veröffentlicht. Alle Preise verstehen sich netto zzgl. der gesetzlichen Umsatzsteuer.",
          },
          {
            type: "text",
            text: "5.2 Die Abrechnung erfolgt monatlich im Voraus. ARIIA stellt dem Tenant am Anfang jeder Abrechnungsperiode eine Rechnung aus.",
          },
          {
            type: "text",
            text: "5.3 Zahlungen sind innerhalb von 14 Tagen nach Rechnungsdatum fällig. Bei Zahlungsverzug ist ARIIA berechtigt, den Zugang zur Plattform nach schriftlicher Mahnung zu sperren.",
          },
          {
            type: "text",
            text: "5.4 ARIIA behält sich vor, Preise mit einer Ankündigungsfrist von 30 Tagen zu ändern. Der Tenant hat in diesem Fall ein Sonderkündigungsrecht zum Zeitpunkt des Preisänderungstermins.",
          },
        ],
      },
      {
        heading: "§ 6 Nutzungsrechte und -pflichten",
        blocks: [
          {
            type: "text",
            text: "6.1 ARIIA gewährt dem Tenant für die Laufzeit des Vertrages ein nicht-exklusives, nicht übertragbares Recht zur Nutzung der Plattform im Rahmen des gebuchten Plans.",
          },
          {
            type: "text",
            text: "6.2 Der Tenant ist verpflichtet, die Plattform ausschließlich für rechtmäßige Zwecke zu nutzen. Untersagt ist insbesondere:",
          },
          {
            type: "list",
            items: [
              "Versand von Spam, unerwünschter Werbung oder Nachrichten ohne wirksame Einwilligung der Empfänger.",
              "Verstöße gegen die WhatsApp Business Policy, Telegram API-Nutzungsbedingungen oder sonstige Plattformrichtlinien.",
              "Nutzung der KI-Agenten für rechtswidrige, diskriminierende oder täuschende Zwecke.",
              "Verarbeitung besonderer Kategorien personenbezogener Daten (Art. 9 DSGVO) ohne ausdrückliche Einwilligung der Betroffenen.",
              "Reverse Engineering, Dekompilierung oder anderweitige Versuche, den Quellcode der Plattform zu extrahieren.",
              "Weiterveräußerung oder Sublizenzierung der Plattform ohne ausdrückliche Genehmigung von ARIIA.",
            ],
          },
          {
            type: "text",
            text: "6.3 Der Tenant ist als Verantwortlicher im Sinne der DSGVO allein verantwortlich für die Rechtmäßigkeit der Datenverarbeitung seiner Endkunden über die Plattform.",
          },
        ],
      },
      {
        heading: "§ 7 KI-generierte Inhalte und Haftungsausschluss",
        blocks: [
          {
            type: "text",
            text: "7.1 ARIIA nutzt Sprachmodelle von OpenAI (GPT-4o-mini, DALL-E 3) und optional weiterer KI-Anbieter zur Generierung von Texten, HTML-Inhalten und Bildern (nachfolgend \"KI-Outputs\").",
          },
          {
            type: "text",
            text: "7.2 KI-Outputs sind automatisch generiert und können inhaltliche Fehler, Ungenauigkeiten oder veraltete Informationen enthalten. ARIIA übernimmt keine Garantie für die Richtigkeit, Vollständigkeit oder Eignung von KI-Outputs für einen bestimmten Zweck.",
          },
          {
            type: "text",
            text: "7.3 Der Tenant ist verpflichtet, KI-generierte Inhalte vor dem Versand oder der Veröffentlichung auf ihre Richtigkeit und Rechtmäßigkeit zu prüfen. ARIIA empfiehlt die Nutzung des integrierten QA-Agenten als Hilfsmittel, ersetzt aber nicht die eigene Prüfpflicht des Tenants.",
          },
          {
            type: "text",
            text: "7.4 Gesundheitsbezogene Inhalte: Der Medic-Agent von ARIIA ist kein Medizinprodukt und ersetzt keine ärztliche Beratung. Alle gesundheitsbezogenen Ausgaben des KI-Agenten enthalten einen Haftungsausschluss und verweisen bei Notfällen auf den Notruf 112. ARIIA haftet nicht für Schäden, die aus der Verwendung medizinbezogener KI-Ausgaben entstehen.",
          },
          {
            type: "text",
            text: "7.5 Urheberrecht KI-Outputs: Für die urheberrechtliche Einordnung KI-generierter Inhalte ist der Tenant selbst verantwortlich. ARIIA gibt keine Garantie, dass KI-generierte Texte und Bilder frei von Rechten Dritter sind.",
          },
        ],
      },
      {
        heading: "§ 8 Verfügbarkeit und Support",
        blocks: [
          {
            type: "text",
            text: "8.1 ARIIA strebt eine Plattformverfügbarkeit von 99,0 % pro Kalendermonat an (gemessen als monatliche Gesamtverfügbarkeit). Geplante Wartungsfenster werden dem Tenant mindestens 24 Stunden im Voraus angekündigt und sind nicht auf die Verfügbarkeit angerechnet.",
          },
          {
            type: "text",
            text: "8.2 Die Verfügbarkeit von ARIIA hängt teilweise von Drittanbietern ab (WhatsApp Business API, Telegram, Twilio, OpenAI). Ausfälle dieser Dienste liegen außerhalb des Einflussbereichs von ARIIA und begründen keinen Anspruch auf Gutschriften oder Schadensersatz.",
          },
          {
            type: "text",
            text: "8.3 Support wird je nach Plan über das Ticketsystem auf www.ariia.ai oder per E-Mail erbracht. Enterprise-Kunden erhalten einen dedizierten Ansprechpartner.",
          },
        ],
      },
      {
        heading: "§ 9 Datenschutz und Auftragsverarbeitung",
        blocks: [
          {
            type: "text",
            text: "9.1 Soweit der Tenant über ARIIA personenbezogene Daten seiner Endkunden verarbeitet, handelt ARIIA als Auftragsverarbeiter im Sinne des Art. 28 DSGVO. Die Parteien schließen einen Auftragsverarbeitungsvertrag (AVV) ab.",
          },
          {
            type: "text",
            text: "9.2 Der AVV ist Bestandteil des Vertragsverhältnisses und kann unter datenschutz@ariia.ai angefordert werden.",
          },
          {
            type: "text",
            text: "9.3 Näheres zur Datenverarbeitung durch ARIIA findet sich in der Datenschutzerklärung unter www.ariia.ai/datenschutz.",
          },
        ],
      },
      {
        heading: "§ 10 Haftung",
        blocks: [
          {
            type: "text",
            text: "10.1 ARIIA haftet unbeschränkt für Schäden aus der Verletzung des Lebens, des Körpers oder der Gesundheit sowie für vorsätzlich oder grob fahrlässig verursachte Schäden.",
          },
          {
            type: "text",
            text: "10.2 Bei leicht fahrlässigen Pflichtverletzungen haftet ARIIA nur bei Verletzung einer wesentlichen Vertragspflicht (Kardinalpflicht). Die Haftung ist in diesem Fall der Höhe nach begrenzt auf den vorhersehbaren, typischerweise eintretenden Schaden, maximal jedoch auf die vom Tenant in den letzten 12 Monaten vor dem Schadensfall an ARIIA gezahlten Entgelte.",
          },
          {
            type: "text",
            text: "10.3 ARIIA haftet nicht für Schäden, die durch die Nutzung von KI-generierten Inhalten, durch Ausfälle von Drittdiensten (insb. WhatsApp, Telegram, Twilio, OpenAI) oder durch unzulässige Nutzung der Plattform durch den Tenant entstehen.",
          },
        ],
      },
      {
        heading: "§ 11 Laufzeit und Kündigung",
        blocks: [
          {
            type: "text",
            text: "11.1 Der Vertrag wird auf unbestimmte Zeit geschlossen und ist monatlich mit einer Frist von 30 Tagen zum Ende der jeweiligen Abrechnungsperiode kündbar.",
          },
          {
            type: "text",
            text: "11.2 Das Recht zur außerordentlichen Kündigung aus wichtigem Grund bleibt unberührt. ARIIA ist insbesondere berechtigt, den Vertrag fristlos zu kündigen, wenn der Tenant wiederholt oder schwerwiegend gegen diese AGB verstößt.",
          },
          {
            type: "text",
            text: "11.3 Nach Kündigung werden alle Daten des Tenants (Account-Daten, Kontakte, Kampagnen, Wissensdateien) nach einer Übergangsfrist von 30 Tagen unwiderruflich gelöscht. Der Tenant ist für den rechtzeitigen Export seiner Daten selbst verantwortlich.",
          },
        ],
      },
      {
        heading: "§ 12 Änderungen der AGB",
        blocks: [
          {
            type: "text",
            text: "12.1 ARIIA behält sich vor, diese AGB mit einer Ankündigungsfrist von 30 Tagen per E-Mail zu ändern. Widerspricht der Tenant den Änderungen nicht innerhalb dieser Frist, gelten die neuen AGB als akzeptiert.",
          },
          {
            type: "text",
            text: "12.2 Im Falle eines Widerspruchs ist ARIIA berechtigt, den Vertrag zum Zeitpunkt des Inkrafttretens der Änderungen zu kündigen.",
          },
        ],
      },
      {
        heading: "§ 13 Schlussbestimmungen",
        blocks: [
          {
            type: "text",
            text: "13.1 Es gilt das Recht der Bundesrepublik Deutschland unter Ausschluss des UN-Kaufrechts (CISG).",
          },
          {
            type: "text",
            text: "13.2 Ausschließlicher Gerichtsstand für alle Streitigkeiten aus und im Zusammenhang mit diesem Vertrag ist Berlin, sofern der Tenant Kaufmann ist.",
          },
          {
            type: "text",
            text: "13.3 Sollten einzelne Bestimmungen dieser AGB unwirksam oder undurchführbar sein oder werden, berührt dies die Wirksamkeit der übrigen Bestimmungen nicht.",
          },
          {
            type: "text",
            text: "13.4 Änderungen und Ergänzungen bedürfen der Schriftform. Dies gilt auch für die Aufhebung des Schriftformerfordernisses.",
          },
        ],
      },
    ],
  },

  en: {
    title: "Terms of Service",
    subtitle: "ARIIA SaaS Platform – B2B Terms of Use",
    lastUpdated: "As of: March 2026",
    legalNote:
      "These Terms of Service apply exclusively to businesses (not consumers). ARIIA is a B2B SaaS product. The German-language version is the legally binding document.",
    sections: [
      {
        heading: "§ 1 Scope and Parties",
        blocks: [
          {
            type: "text",
            text: "1.1 These Terms of Service (\"ToS\") govern all contracts for the use of the cloud-based SaaS platform ARIIA (\"Platform\") concluded between [PLACEHOLDER: Company Name] (\"ARIIA\") and the respective business customer (\"Tenant\" or \"Customer\").",
          },
          {
            type: "text",
            text: "1.2 ARIIA is exclusively directed at businesses. The Platform is not intended for consumers.",
          },
          {
            type: "text",
            text: "1.3 Conflicting general terms and conditions of the Customer shall not become part of the contract unless ARIIA expressly agrees in writing.",
          },
        ],
      },
      {
        heading: "§ 2 Service Description",
        blocks: [
          {
            type: "text",
            text: "2.1 ARIIA provides the Tenant with access, on a Software-as-a-Service basis, to the following functions:",
          },
          {
            type: "list",
            items: [
              "AI-powered communication agents for WhatsApp Business API, Telegram, SMS and Email",
              "Voice assistants (stub and production mode)",
              "Campaign management including AI content generation, segmentation, send scheduling and A/B testing",
              "Contact management (CRM) with tags, segments and contact history",
              "Knowledge base with document upload and AI retrieval (RAG)",
              "Omnichannel orchestration and sequence campaigns",
              "Admin dashboard with user, role and tenant management",
              "API access for custom integrations",
            ],
          },
          {
            type: "text",
            text: "2.2 Available features depend on the subscribed plan (Starter, Pro or Enterprise). Current plan details are published at www.ariia.ai/pricing.",
          },
          {
            type: "text",
            text: "2.3 ARIIA operates a multi-tenant architecture. Each Tenant receives a fully isolated environment. ARIIA ensures tenant isolation through technical measures (database isolation by tenant_id).",
          },
        ],
      },
      {
        heading: "§ 3 Contract Formation and Account Creation",
        blocks: [
          {
            type: "text",
            text: "3.1 The contract is formed upon registration of the Tenant at www.ariia.ai and confirmation of registration by ARIIA.",
          },
          {
            type: "text",
            text: "3.2 Upon registration, the Tenant automatically receives access to the Starter plan. Upgrading to Pro or Enterprise requires a separate booking.",
          },
          {
            type: "text",
            text: "3.3 The Tenant must provide complete and accurate information during registration and keep it up to date.",
          },
          {
            type: "text",
            text: "3.4 Access credentials must be kept confidential. The Tenant is responsible for all actions taken under their account.",
          },
        ],
      },
      {
        heading: "§ 4 Subscription Plans and Quotas",
        blocks: [
          {
            type: "text",
            text: "4.1 ARIIA offers the following subscription plans:",
          },
          {
            type: "indent",
            items: [
              "Starter: Core features, limited message and AI quotas, suitable for studios getting started.",
              "Pro: Extended features, higher quotas, A/B testing, omnichannel sequences.",
              "Enterprise: Full feature set, customisable quotas, dedicated support, individual DPA arrangements.",
            ],
          },
          {
            type: "text",
            text: "4.2 Specific monthly quotas (messages, AI tokens, storage, image generations) per plan are detailed at www.ariia.ai/pricing and in the admin dashboard.",
          },
          {
            type: "text",
            text: "4.3 When quota limits are exceeded, the platform returns an HTTP 429 error (Quota exhausted) and notifies the Tenant in the dashboard. Further usage in the affected category is restricted until the next billing period or after an upgrade.",
          },
          {
            type: "text",
            text: "4.4 Unused quotas expire at the end of the billing period and are not carried over.",
          },
        ],
      },
      {
        heading: "§ 5 Prices, Payment and Invoicing",
        blocks: [
          {
            type: "text",
            text: "5.1 Current prices are published at www.ariia.ai/pricing. All prices are net plus applicable VAT.",
          },
          {
            type: "text",
            text: "5.2 Billing is monthly in advance. ARIIA issues an invoice to the Tenant at the beginning of each billing period.",
          },
          {
            type: "text",
            text: "5.3 Payments are due within 14 days of the invoice date. In the event of late payment, ARIIA may suspend access to the Platform after written notice.",
          },
          {
            type: "text",
            text: "5.4 ARIIA may change prices with 30 days' prior notice. In this case, the Tenant has a special right of termination as of the effective date of the price change.",
          },
        ],
      },
      {
        heading: "§ 6 Usage Rights and Obligations",
        blocks: [
          {
            type: "text",
            text: "6.1 ARIIA grants the Tenant a non-exclusive, non-transferable right to use the Platform for the term of the contract within the scope of the subscribed plan.",
          },
          {
            type: "text",
            text: "6.2 The Tenant must use the Platform for lawful purposes only. Prohibited in particular:",
          },
          {
            type: "list",
            items: [
              "Sending spam, unsolicited advertising or messages without valid consent of recipients.",
              "Violations of WhatsApp Business Policy, Telegram API Terms or other platform policies.",
              "Use of AI agents for unlawful, discriminatory or deceptive purposes.",
              "Processing special categories of personal data (Art. 9 GDPR) without explicit consent.",
              "Reverse engineering, decompilation or other attempts to extract the Platform's source code.",
              "Resale or sublicensing of the Platform without ARIIA's express consent.",
            ],
          },
          {
            type: "text",
            text: "6.3 The Tenant, as data controller under GDPR, is solely responsible for the lawfulness of processing their end customers' data via the Platform.",
          },
        ],
      },
      {
        heading: "§ 7 AI-Generated Content and Disclaimer",
        blocks: [
          {
            type: "text",
            text: "7.1 ARIIA uses language models from OpenAI (GPT-4o-mini, DALL-E 3) and optionally other AI providers to generate texts, HTML content and images (\"AI Outputs\").",
          },
          {
            type: "text",
            text: "7.2 AI Outputs are automatically generated and may contain errors, inaccuracies or outdated information. ARIIA makes no warranty as to the accuracy, completeness or fitness for purpose of AI Outputs.",
          },
          {
            type: "text",
            text: "7.3 The Tenant is obliged to review AI-generated content for accuracy and compliance before sending or publishing. ARIIA recommends using the built-in QA agent as an aid, but this does not replace the Tenant's own review obligation.",
          },
          {
            type: "text",
            text: "7.4 Health-related content: The ARIIA Medic Agent is not a medical device and does not replace medical advice. All health-related AI outputs include a liability disclaimer and refer to emergency services (112) in emergencies. ARIIA is not liable for damages arising from the use of health-related AI outputs.",
          },
          {
            type: "text",
            text: "7.5 Copyright of AI Outputs: The Tenant is solely responsible for the copyright classification of AI-generated content. ARIIA makes no warranty that AI-generated texts and images are free from third-party rights.",
          },
        ],
      },
      {
        heading: "§ 8 Availability and Support",
        blocks: [
          {
            type: "text",
            text: "8.1 ARIIA targets a Platform availability of 99.0% per calendar month. Planned maintenance windows are announced at least 24 hours in advance and are not counted against availability.",
          },
          {
            type: "text",
            text: "8.2 ARIIA's availability partly depends on third-party providers (WhatsApp Business API, Telegram, Twilio, OpenAI). Outages of these services are beyond ARIIA's control and do not give rise to claims for credits or damages.",
          },
          {
            type: "text",
            text: "8.3 Support is provided per plan via the ticket system at www.ariia.ai or by email. Enterprise customers receive a dedicated account manager.",
          },
        ],
      },
      {
        heading: "§ 9 Data Protection and Data Processing",
        blocks: [
          {
            type: "text",
            text: "9.1 Where the Tenant processes personal data of its end customers via ARIIA, ARIIA acts as data processor within the meaning of Art. 28 GDPR. The parties shall conclude a Data Processing Agreement (DPA).",
          },
          {
            type: "text",
            text: "9.2 The DPA is part of the contractual relationship and can be requested at datenschutz@ariia.ai.",
          },
          {
            type: "text",
            text: "9.3 Further information on data processing by ARIIA can be found in the Privacy Policy at www.ariia.ai/datenschutz.",
          },
        ],
      },
      {
        heading: "§ 10 Liability",
        blocks: [
          {
            type: "text",
            text: "10.1 ARIIA's liability is unlimited for damages arising from injury to life, body or health, and for intentionally or grossly negligent damages.",
          },
          {
            type: "text",
            text: "10.2 For slightly negligent breaches of material contractual obligations (cardinal duties), ARIIA's liability is limited to foreseeable, typically occurring damages, but not exceeding the fees paid by the Tenant in the 12 months preceding the damaging event.",
          },
          {
            type: "text",
            text: "10.3 ARIIA is not liable for damages caused by AI-generated content, outages of third-party services (in particular WhatsApp, Telegram, Twilio, OpenAI) or unlawful use of the Platform by the Tenant.",
          },
        ],
      },
      {
        heading: "§ 11 Term and Termination",
        blocks: [
          {
            type: "text",
            text: "11.1 The contract is concluded for an indefinite period and may be terminated by either party with 30 days' notice to the end of the respective billing period.",
          },
          {
            type: "text",
            text: "11.2 The right to terminate for cause remains unaffected. ARIIA is entitled to terminate the contract with immediate effect in particular if the Tenant repeatedly or seriously breaches these ToS.",
          },
          {
            type: "text",
            text: "11.3 After termination, all Tenant data (account data, contacts, campaigns, knowledge files) will be irrevocably deleted after a transition period of 30 days. The Tenant is responsible for exporting their data in time.",
          },
        ],
      },
      {
        heading: "§ 12 Changes to the ToS",
        blocks: [
          {
            type: "text",
            text: "12.1 ARIIA may amend these ToS with 30 days' prior notice by email. If the Tenant does not object within this period, the new ToS shall be deemed accepted.",
          },
          {
            type: "text",
            text: "12.2 In the event of an objection, ARIIA may terminate the contract as of the date the amendments take effect.",
          },
        ],
      },
      {
        heading: "§ 13 Final Provisions",
        blocks: [
          {
            type: "text",
            text: "13.1 The law of the Federal Republic of Germany applies, excluding the UN Convention on Contracts for the International Sale of Goods (CISG).",
          },
          {
            type: "text",
            text: "13.2 Exclusive jurisdiction for all disputes arising from and in connection with this contract is Berlin, provided the Tenant is a merchant.",
          },
          {
            type: "text",
            text: "13.3 Should individual provisions of these ToS be or become invalid or unenforceable, this shall not affect the validity of the remaining provisions.",
          },
        ],
      },
    ],
  },
};

/* ─── Sub-components ──────────────────────────────────────────────────────── */

function RenderBlocks({ blocks }: { blocks: Block[] }) {
  return (
    <div className="space-y-3">
      {blocks.map((block, i) => {
        if (block.type === "text") {
          return (
            <p key={i} style={{ color: C.text, lineHeight: 1.75, whiteSpace: "pre-line" }}>
              {block.text}
            </p>
          );
        }
        if (block.type === "list") {
          return (
            <ul key={i} style={{ paddingLeft: 20, margin: 0 }}>
              {block.items.map((item, j) => (
                <li key={j} style={{ color: C.text, lineHeight: 1.75, marginBottom: 4 }}>
                  {item}
                </li>
              ))}
            </ul>
          );
        }
        if (block.type === "indent") {
          return (
            <div key={i} style={{ paddingLeft: 16, borderLeft: `2px solid ${C.border}` }}>
              {block.items.map((item, j) => (
                <p key={j} style={{ color: C.text, lineHeight: 1.75, marginBottom: 4 }}>
                  {item}
                </p>
              ))}
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}

/* ─── Component ────────────────────────────────────────────────────────────── */

export default function AgbClient() {
  const { language } = useI18n();
  const lang = (language === "de" ? "de" : "en") as "de" | "en";
  const content = CONTENT[lang];

  return (
    <div className="min-h-screen" style={{ background: C.bg }}>
      <Navbar />
      <main className="pt-28 pb-20 lg:pt-36 lg:pb-28">
        <div className="container mx-auto px-4 max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* Header */}
            <div className="mb-10">
              <div
                className="inline-block text-xs font-bold uppercase tracking-widest px-3 py-1 rounded-full mb-4"
                style={{ background: C.badge, color: C.accent }}
              >
                Legal · ToS
              </div>
              <h1
                className="text-3xl lg:text-4xl font-bold tracking-tight mb-2"
                style={{ color: C.heading }}
              >
                {content.title}
              </h1>
              <p className="text-sm mb-2" style={{ color: C.muted }}>
                {content.subtitle}
              </p>
              <p className="text-xs" style={{ color: C.muted }}>
                {content.lastUpdated}
              </p>
            </div>

            {/* Legal note */}
            <div
              className="mb-8 p-4 rounded-xl text-xs leading-relaxed border"
              style={{ background: C.badge, borderColor: C.border, color: C.muted }}
            >
              {content.legalNote}
            </div>

            {/* Table of Contents */}
            <div
              className="mb-10 p-5 rounded-xl border text-xs"
              style={{ background: C.badge, borderColor: C.border }}
            >
              <p
                className="font-bold uppercase tracking-wider mb-3"
                style={{ color: C.muted }}
              >
                {lang === "de" ? "Inhaltsverzeichnis" : "Table of Contents"}
              </p>
              <ol style={{ paddingLeft: 16, margin: 0 }}>
                {content.sections.map((s, i) => (
                  <li key={i} style={{ color: C.accent, marginBottom: 2 }}>
                    <a
                      href={`#section-${i}`}
                      style={{ color: C.accent, textDecoration: "none" }}
                    >
                      {s.heading}
                    </a>
                  </li>
                ))}
              </ol>
            </div>

            {/* Sections */}
            <div className="space-y-10 text-sm">
              {content.sections.map((section, i) => (
                <section key={i} id={`section-${i}`}>
                  <h2
                    className="text-base font-semibold mb-4"
                    style={{ color: C.heading }}
                  >
                    {section.heading}
                  </h2>
                  <RenderBlocks blocks={section.blocks} />
                </section>
              ))}
            </div>

            {/* Footer */}
            <div
              className="mt-12 pt-6 border-t text-xs"
              style={{ borderColor: C.border, color: C.muted }}
            >
              ARIIA · hello@ariia.ai · www.ariia.ai
              <span className="ml-4">
                <a href="/impressum" style={{ color: C.accent, textDecoration: "none", marginRight: 12 }}>
                  Impressum
                </a>
                <a href="/datenschutz" style={{ color: C.accent, textDecoration: "none" }}>
                  {lang === "de" ? "Datenschutz" : "Privacy"}
                </a>
              </span>
            </div>
          </motion.div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
