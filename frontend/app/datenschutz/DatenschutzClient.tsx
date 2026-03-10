"use client";

/**
 * ARIIA – Datenschutzerklärung / Privacy Policy
 * GDPR-compliant, SaaS-specific, bilingual DE/EN.
 * Covers: account data, usage data, AI subprocessors, cookies, tenant DPA.
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
  tableHd: "oklch(0.12 0.02 270)",
};

/* ─── Types ───────────────────────────────────────────────────────────────── */
interface Paragraph { type: "text"; text: string; }
interface List      { type: "list"; items: string[]; }
interface Table     { type: "table"; headers: string[]; rows: string[][]; }
type Block = Paragraph | List | Table;
interface Section   { heading: string; blocks: Block[]; }
interface PageContent {
  title: string;
  subtitle: string;
  lastUpdated: string;
  sections: Section[];
}

/* ─── Content ─────────────────────────────────────────────────────────────── */
const CONTENT: Record<"de" | "en", PageContent> = {
  de: {
    title: "Datenschutzerklärung",
    subtitle: "Informationen gemäß Art. 13, 14 DSGVO",
    lastUpdated: "Stand: März 2026",
    sections: [
      {
        heading: "1. Verantwortlicher",
        blocks: [
          {
            type: "text",
            text: "Verantwortlicher im Sinne der Datenschutz-Grundverordnung (DSGVO) ist:",
          },
          {
            type: "text",
            text: "[PLACEHOLDER: Unternehmensname]\n[PLACEHOLDER: Straße Hausnummer]\n[PLACEHOLDER: PLZ Ort]\nDeutschland\nE-Mail: datenschutz@ariia.ai\nWeb: www.ariia.ai",
          },
          {
            type: "text",
            text: "Bei datenschutzrechtlichen Anfragen wenden Sie sich bitte an: datenschutz@ariia.ai",
          },
        ],
      },
      {
        heading: "2. Überblick – was ist ARIIA?",
        blocks: [
          {
            type: "text",
            text: "ARIIA ist eine cloudbasierte SaaS-Plattform, die Fitnessstudios und Gesundheitsdienstleistern (nachfolgend \"Tenants\") KI-gestützte Kommunikationsagenten für WhatsApp, Telegram, SMS, E-Mail und Voice sowie ein integriertes Kampagnen-, Kontakt- und Wissensmanagement bereitstellt.",
          },
          {
            type: "text",
            text: "ARIIA verarbeitet personenbezogene Daten in zwei Rollen:",
          },
          {
            type: "list",
            items: [
              "Verantwortlicher (Art. 4 Nr. 7 DSGVO): für die Verarbeitung im Rahmen des eigenen Betriebs der Plattform (z. B. Kundenkonten, Zahlungsabwicklung, Plattformsicherheit).",
              "Auftragsverarbeiter (Art. 4 Nr. 8 DSGVO): für Daten, die Tenants über ihre Endkunden in der Plattform verarbeiten (z. B. Mitgliedernamen, Chatnachrichten). Hierfür wird ein Auftragsverarbeitungsvertrag (AVV) gemäß Art. 28 DSGVO abgeschlossen.",
            ],
          },
          {
            type: "text",
            text: "Diese Datenschutzerklärung richtet sich an Tenants, Nutzer des Admin-Dashboards sowie an Besucher der Website www.ariia.ai.",
          },
        ],
      },
      {
        heading: "3. Erhobene Daten und Verarbeitungszwecke",
        blocks: [
          { type: "text", text: "Wir verarbeiten folgende Kategorien personenbezogener Daten:" },
          {
            type: "table",
            headers: ["Datenkategorie", "Betroffene Personen", "Zweck", "Rechtsgrundlage"],
            rows: [
              [
                "Account-Daten (Name, E-Mail, Passwort-Hash, Rolle, Tenant-Zuordnung)",
                "Admin-Nutzer der Tenants",
                "Authentifizierung, Zugriffsverwaltung, Vertragsdurchführung",
                "Art. 6 Abs. 1 lit. b DSGVO",
              ],
              [
                "Zahlungsdaten (Abo-Plan, Abrechnungsperiode, Zahlungsstatus)",
                "Tenants (Unternehmen)",
                "Abrechnung, Planverwaltung, Vertragsdurchführung",
                "Art. 6 Abs. 1 lit. b DSGVO",
              ],
              [
                "Nutzungsdaten (API-Calls, gesendete Nachrichten, KI-Tokens, Kampagnen-Statistiken)",
                "Admin-Nutzer, Tenants",
                "Kontingentüberwachung, Missbrauchserkennung, Service-Optimierung",
                "Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse)",
              ],
              [
                "Kontaktdaten der Endkunden (Name, Telefonnummer, E-Mail, Mitgliedschaftsdaten)",
                "Endkunden der Tenants",
                "Kommunikationsagenten, Kampagnen, CRM – im Auftrag des Tenants",
                "Art. 28 DSGVO (Auftragsverarbeitung)",
              ],
              [
                "Chat-Nachrichten (eingehend/ausgehend über WhatsApp, Telegram, SMS, E-Mail)",
                "Endkunden der Tenants",
                "KI-Agentenbetrieb, Kontextgedächtnis – im Auftrag des Tenants",
                "Art. 28 DSGVO (Auftragsverarbeitung)",
              ],
              [
                "Wissensdaten (Dokumente, PDFs, Trainingsdaten)",
                "Tenants (Daten des Studios)",
                "KI-Wissensmanagement, RAG-System",
                "Art. 6 Abs. 1 lit. b DSGVO",
              ],
              [
                "Log-Daten (IP-Adresse, Browser-UA, Zugriffszeit, Fehlerprotokolle)",
                "Alle Nutzer und Besucher",
                "Sicherheit, Debugging, Betriebsstabilität",
                "Art. 6 Abs. 1 lit. f DSGVO",
              ],
            ],
          },
        ],
      },
      {
        heading: "4. Speicherdauer",
        blocks: [
          {
            type: "text",
            text: "Wir speichern personenbezogene Daten nur so lange, wie es für den jeweiligen Zweck erforderlich ist:",
          },
          {
            type: "list",
            items: [
              "Account-Daten: bis zur Kündigung des Tenants + 30 Tage (Nachlauffrist) + gesetzliche Aufbewahrungspflicht (i. d. R. 10 Jahre für steuerrelevante Daten).",
              "Chat-Nachrichten (Langzeitspeicher): 90 Tage, danach automatische Löschung.",
              "Chat-Kontext im RAM-Speicher: max. 30 Minuten Inaktivität (flüchtig).",
              "Log-Daten: 30 Tage rollierende Aufbewahrung.",
              "Kameradaten (Vision-Modul): 0 Sekunden Retention – ausschließlich RAM-Verarbeitung, keine Persistierung.",
              "Zahlungsbelege: 10 Jahre gemäß §§ 147 AO, 257 HGB.",
            ],
          },
        ],
      },
      {
        heading: "5. Auftragsverarbeiter und Drittanbieter",
        blocks: [
          {
            type: "text",
            text: "Wir setzen folgende Auftragsverarbeiter und Dienstleister ein. Soweit Daten in Drittländer (außerhalb EU/EWR) übertragen werden, geschieht dies auf Basis von EU-Standardvertragsklauseln (SCC) gemäß Art. 46 DSGVO:",
          },
          {
            type: "table",
            headers: ["Anbieter", "Zweck", "Sitz", "Schutzmaßnahme"],
            rows: [
              ["OpenAI, Inc.", "KI-Sprachmodelle (GPT-4o-mini, DALL-E 3)", "USA", "EU-SCC, Datenschutznachtrag"],
              ["Meta Platforms (WhatsApp Business API)", "Nachrichtenversand über WhatsApp", "USA", "EU-SCC"],
              ["Telegram Messenger Inc.", "Nachrichtenversand über Telegram", "Dubai/USA", "EU-SCC, ToS Datenverarbeitung"],
              ["Twilio Inc.", "SMS-Versand (Twilio SMS API)", "USA", "EU-SCC, Datenschutznachtrag"],
              ["[PLACEHOLDER: Hosting-Anbieter]", "Cloud-Infrastruktur, Datenbanken", "Deutschland", "DSGVO-konform, AVV"],
              ["[PLACEHOLDER: Zahlungsanbieter]", "Zahlungsabwicklung", "EU/USA", "PCI-DSS, AVV / EU-SCC"],
            ],
          },
          {
            type: "text",
            text: "Alle Auftragsverarbeiter wurden sorgfältig ausgewählt und es wurden Auftragsverarbeitungsverträge gemäß Art. 28 DSGVO abgeschlossen.",
          },
        ],
      },
      {
        heading: "6. Datensicherheit",
        blocks: [
          {
            type: "text",
            text: "Wir treffen gemäß Art. 32 DSGVO angemessene technische und organisatorische Maßnahmen (TOMs) zum Schutz Ihrer Daten:",
          },
          {
            type: "list",
            items: [
              "Transportverschlüsselung: TLS 1.2/1.3 für alle Verbindungen.",
              "Passwortsicherheit: PBKDF2-HMAC-SHA256 mit 200.000 Iterationen.",
              "API-Authentifizierung: HMAC-SHA256-Token, 12h TTL.",
              "Webhook-Sicherheit: HMAC-SHA256-Signaturverifikation (WhatsApp), HMAC-SHA1 (Twilio).",
              "Mandantentrennung: Alle Datenbankabfragen werden strikt nach tenant_id isoliert – keine Daten-Leckage zwischen Tenants.",
              "PII-Masking: Personenbezogene Daten werden in Protokollen automatisch maskiert.",
              "Kameradaten: 0-Sekunden-Retention, ausschließlich RAM-Verarbeitung.",
              "API-Keys von Drittanbietern werden mit Fernet-Verschlüsselung (AES-128-CBC) gespeichert.",
              "Regelmäßige Sicherheitsaudits und Penetrationstests.",
            ],
          },
        ],
      },
      {
        heading: "7. Cookies und Session-Daten",
        blocks: [
          {
            type: "text",
            text: "Die ARIIA-Plattform verwendet die folgenden Cookies und Session-Mechanismen:",
          },
          {
            type: "table",
            headers: ["Cookie / Token", "Zweck", "Lebensdauer", "Typ"],
            rows: [
              [
                "ariia_access_token",
                "Authentifizierungs-Session für Admin-Nutzer (HMAC-SHA256-signiert)",
                "12 Stunden",
                "Session-Cookie (HttpOnly, SameSite=Strict)",
              ],
              [
                "ariia_lang",
                "Gespeicherte Sprachpräferenz des Nutzers",
                "Persistent (localStorage)",
                "Kein Cookie – localStorage",
              ],
            ],
          },
          {
            type: "text",
            text: "Die Website www.ariia.ai (Marketing-Seiten) verwendet keine Analyse- oder Tracking-Cookies von Drittanbietern. Auf den geschützten Admin-Seiten werden ausschließlich technisch notwendige Cookies eingesetzt, die keiner Einwilligung nach § 25 TTDSG bedürfen.",
          },
        ],
      },
      {
        heading: "8. Ihre Rechte als betroffene Person (Art. 15–22 DSGVO)",
        blocks: [
          {
            type: "text",
            text: "Sie haben folgende Rechte gegenüber dem Verantwortlichen bezüglich Ihrer personenbezogenen Daten:",
          },
          {
            type: "list",
            items: [
              "Auskunftsrecht (Art. 15 DSGVO): Sie können Auskunft über die von uns verarbeiteten Daten verlangen.",
              "Berichtigungsrecht (Art. 16 DSGVO): Sie können die Berichtigung unrichtiger oder unvollständiger Daten verlangen.",
              "Löschungsrecht (Art. 17 DSGVO): Sie können unter bestimmten Voraussetzungen die Löschung Ihrer Daten verlangen (\"Recht auf Vergessenwerden\").",
              "Einschränkung der Verarbeitung (Art. 18 DSGVO): Sie können die Einschränkung der Verarbeitung verlangen.",
              "Datenübertragbarkeit (Art. 20 DSGVO): Sie können Ihre Daten in einem strukturierten, maschinenlesbaren Format erhalten.",
              "Widerspruchsrecht (Art. 21 DSGVO): Sie können der Verarbeitung auf Basis berechtigter Interessen widersprechen.",
              "Widerruf der Einwilligung (Art. 7 Abs. 3 DSGVO): Sofern eine Einwilligung als Rechtsgrundlage dient, können Sie diese jederzeit widerrufen.",
            ],
          },
          {
            type: "text",
            text: "Zur Ausübung Ihrer Rechte wenden Sie sich an: datenschutz@ariia.ai\n\nSie haben zudem das Recht, sich bei der zuständigen Datenschutz-Aufsichtsbehörde zu beschweren. Für Deutschland ist dies der/die Bundesbeauftragte für den Datenschutz und die Informationsfreiheit (BfDI) oder die zuständige Landesbehörde.",
          },
        ],
      },
      {
        heading: "9. Auftragsverarbeitungsvertrag (AVV) für Tenants",
        blocks: [
          {
            type: "text",
            text: "Tenants (Unternehmenskunden), die ARIIA für die Verarbeitung personenbezogener Daten ihrer Endkunden nutzen, schließen mit uns einen Auftragsverarbeitungsvertrag (AVV) gemäß Art. 28 DSGVO ab. Der AVV regelt insbesondere:",
          },
          {
            type: "list",
            items: [
              "Gegenstand, Dauer und Art der Verarbeitung.",
              "Zweck und Kategorien der verarbeiteten Daten.",
              "Pflichten und Rechte des Verantwortlichen (Tenant).",
              "Technische und organisatorische Maßnahmen des Auftragsverarbeiters (ARIIA).",
              "Regelungen zu Unterauftragsverarbeitern (insb. OpenAI, Twilio, Meta).",
            ],
          },
          {
            type: "text",
            text: "Den AVV können Sie anfordern unter: datenschutz@ariia.ai",
          },
        ],
      },
      {
        heading: "10. Besondere Hinweise zur KI-Verarbeitung",
        blocks: [
          {
            type: "text",
            text: "ARIIA verwendet OpenAI-Sprachmodelle (GPT-4o-mini) für die KI-Agenten und die Kampagnenerstellung. Dabei gelten folgende Grundsätze:",
          },
          {
            type: "list",
            items: [
              "Datenweitergabe: Chatnachrichten und relevante Kontextdaten werden zur Verarbeitung an OpenAI übermittelt. Die Übertragung erfolgt ausschließlich für die Verarbeitung im Auftrag der jeweiligen Anfrage (keine Verwendung für OpenAI-Modelltraining gemäß API-Nutzungsbedingungen).",
              "KI-Ausgaben: KI-generierte Inhalte können fehlerhaft sein. ARIIA gibt keine Garantie für die Richtigkeit KI-generierter Texte, Empfehlungen oder Diagnosen.",
              "Gesundheitsbezogene Anfragen: Der Medic-Agent gibt stets den Haftungsausschluss aus und verweist bei Notfällen auf den Notruf 112. Keine Diagnosen.",
              "PII-Schutz: Vor der Weitergabe an das LLM werden erkannte personenbezogene Daten in Logs maskiert (PII-Filter).",
            ],
          },
        ],
      },
      {
        heading: "11. Änderungen dieser Datenschutzerklärung",
        blocks: [
          {
            type: "text",
            text: "Wir behalten uns vor, diese Datenschutzerklärung anzupassen, um sie an geänderte Rechtslage, Plattform-Funktionen oder Verarbeitungsvorgänge anzupassen. Die jeweils aktuelle Version ist auf www.ariia.ai/datenschutz abrufbar. Tenants werden über wesentliche Änderungen per E-Mail oder im Admin-Dashboard informiert.",
          },
        ],
      },
    ],
  },

  en: {
    title: "Privacy Policy",
    subtitle: "Information pursuant to Art. 13, 14 GDPR",
    lastUpdated: "As of: March 2026",
    sections: [
      {
        heading: "1. Data Controller",
        blocks: [
          {
            type: "text",
            text: "The data controller within the meaning of the General Data Protection Regulation (GDPR) is:",
          },
          {
            type: "text",
            text: "[PLACEHOLDER: Company Name]\n[PLACEHOLDER: Street No.]\n[PLACEHOLDER: ZIP City]\nGermany\nEmail: datenschutz@ariia.ai\nWeb: www.ariia.ai",
          },
          {
            type: "text",
            text: "For all data protection inquiries, please contact: datenschutz@ariia.ai",
          },
        ],
      },
      {
        heading: "2. About ARIIA",
        blocks: [
          {
            type: "text",
            text: "ARIIA is a cloud-based SaaS platform providing fitness studios and health service providers (\"Tenants\") with AI-powered communication agents for WhatsApp, Telegram, SMS, Email and Voice, as well as integrated campaign, contact and knowledge management.",
          },
          {
            type: "text",
            text: "ARIIA processes personal data in two capacities:",
          },
          {
            type: "list",
            items: [
              "Data Controller (Art. 4(7) GDPR): for processing related to the operation of the platform itself (e.g. customer accounts, payment processing, platform security).",
              "Data Processor (Art. 4(8) GDPR): for data that Tenants process about their end customers within the platform (e.g. member names, chat messages). A Data Processing Agreement (DPA) pursuant to Art. 28 GDPR is concluded for this purpose.",
            ],
          },
          {
            type: "text",
            text: "This Privacy Policy is addressed to Tenants, admin dashboard users, and visitors to www.ariia.ai.",
          },
        ],
      },
      {
        heading: "3. Data Collected and Processing Purposes",
        blocks: [
          { type: "text", text: "We process the following categories of personal data:" },
          {
            type: "table",
            headers: ["Data Category", "Data Subjects", "Purpose", "Legal Basis"],
            rows: [
              [
                "Account data (name, email, password hash, role, tenant assignment)",
                "Tenant admin users",
                "Authentication, access management, contract performance",
                "Art. 6(1)(b) GDPR",
              ],
              [
                "Payment data (subscription plan, billing period, payment status)",
                "Tenants (companies)",
                "Billing, plan management, contract performance",
                "Art. 6(1)(b) GDPR",
              ],
              [
                "Usage data (API calls, messages sent, AI tokens, campaign statistics)",
                "Admin users, Tenants",
                "Quota monitoring, abuse detection, service optimisation",
                "Art. 6(1)(f) GDPR (legitimate interest)",
              ],
              [
                "End customer contact data (name, phone, email, membership data)",
                "Tenants' end customers",
                "Communication agents, campaigns, CRM – on behalf of Tenant",
                "Art. 28 GDPR (data processing)",
              ],
              [
                "Chat messages (inbound/outbound via WhatsApp, Telegram, SMS, Email)",
                "Tenants' end customers",
                "AI agent operation, context memory – on behalf of Tenant",
                "Art. 28 GDPR (data processing)",
              ],
              [
                "Knowledge data (documents, PDFs, training data)",
                "Tenants (studio data)",
                "AI knowledge management, RAG system",
                "Art. 6(1)(b) GDPR",
              ],
              [
                "Log data (IP address, browser UA, access time, error logs)",
                "All users and visitors",
                "Security, debugging, operational stability",
                "Art. 6(1)(f) GDPR",
              ],
            ],
          },
        ],
      },
      {
        heading: "4. Retention Periods",
        blocks: [
          {
            type: "text",
            text: "We store personal data only for as long as necessary for the respective purpose:",
          },
          {
            type: "list",
            items: [
              "Account data: until termination of the Tenant account + 30 days (run-off period) + statutory retention obligations (generally 10 years for tax-relevant data).",
              "Chat messages (long-term storage): 90 days, then automatic deletion.",
              "Chat context in RAM: max. 30 minutes of inactivity (volatile).",
              "Log data: 30-day rolling retention.",
              "Camera data (Vision module): 0-second retention – RAM-only processing, no persistence.",
              "Payment records: 10 years pursuant to applicable commercial and tax law.",
            ],
          },
        ],
      },
      {
        heading: "5. Sub-processors and Third-Party Service Providers",
        blocks: [
          {
            type: "text",
            text: "We engage the following sub-processors and service providers. Where data is transferred to third countries (outside EU/EEA), this is done on the basis of EU Standard Contractual Clauses (SCC) pursuant to Art. 46 GDPR:",
          },
          {
            type: "table",
            headers: ["Provider", "Purpose", "Location", "Safeguard"],
            rows: [
              ["OpenAI, Inc.", "AI language models (GPT-4o-mini, DALL-E 3)", "USA", "EU SCC, Data Processing Addendum"],
              ["Meta Platforms (WhatsApp Business API)", "Message delivery via WhatsApp", "USA", "EU SCC"],
              ["Telegram Messenger Inc.", "Message delivery via Telegram", "Dubai/USA", "EU SCC, ToS data processing"],
              ["Twilio Inc.", "SMS delivery (Twilio SMS API)", "USA", "EU SCC, Data Processing Addendum"],
              ["[PLACEHOLDER: Hosting Provider]", "Cloud infrastructure, databases", "Germany", "GDPR-compliant, DPA"],
              ["[PLACEHOLDER: Payment Provider]", "Payment processing", "EU/USA", "PCI-DSS, DPA / EU SCC"],
            ],
          },
          {
            type: "text",
            text: "All sub-processors have been carefully selected and Data Processing Agreements pursuant to Art. 28 GDPR have been concluded.",
          },
        ],
      },
      {
        heading: "6. Data Security",
        blocks: [
          {
            type: "text",
            text: "We implement appropriate technical and organisational measures (TOMs) pursuant to Art. 32 GDPR to protect your data:",
          },
          {
            type: "list",
            items: [
              "Transport encryption: TLS 1.2/1.3 for all connections.",
              "Password security: PBKDF2-HMAC-SHA256 with 200,000 iterations.",
              "API authentication: HMAC-SHA256 tokens, 12h TTL.",
              "Webhook security: HMAC-SHA256 signature verification (WhatsApp), HMAC-SHA1 (Twilio).",
              "Tenant isolation: All database queries are strictly isolated by tenant_id – no data leakage between tenants.",
              "PII masking: Personal data is automatically masked in logs.",
              "Camera data: 0-second retention, RAM-only processing.",
              "Third-party API keys are stored with Fernet encryption (AES-128-CBC).",
              "Regular security audits and penetration tests.",
            ],
          },
        ],
      },
      {
        heading: "7. Cookies and Session Data",
        blocks: [
          {
            type: "text",
            text: "The ARIIA platform uses the following cookies and session mechanisms:",
          },
          {
            type: "table",
            headers: ["Cookie / Token", "Purpose", "Lifetime", "Type"],
            rows: [
              [
                "ariia_access_token",
                "Authentication session for admin users (HMAC-SHA256 signed)",
                "12 hours",
                "Session cookie (HttpOnly, SameSite=Strict)",
              ],
              [
                "ariia_lang",
                "Stored language preference of the user",
                "Persistent (localStorage)",
                "Not a cookie – localStorage",
              ],
            ],
          },
          {
            type: "text",
            text: "The website www.ariia.ai (marketing pages) does not use any analytics or tracking cookies from third parties. The protected admin pages use only technically necessary cookies that do not require consent.",
          },
        ],
      },
      {
        heading: "8. Your Rights as a Data Subject (Art. 15–22 GDPR)",
        blocks: [
          {
            type: "text",
            text: "You have the following rights vis-à-vis the data controller regarding your personal data:",
          },
          {
            type: "list",
            items: [
              "Right of access (Art. 15 GDPR): You may request information about the data we process.",
              "Right to rectification (Art. 16 GDPR): You may request correction of inaccurate or incomplete data.",
              "Right to erasure (Art. 17 GDPR): Under certain conditions, you may request deletion of your data ('right to be forgotten').",
              "Right to restriction of processing (Art. 18 GDPR): You may request restriction of processing.",
              "Right to data portability (Art. 20 GDPR): You may receive your data in a structured, machine-readable format.",
              "Right to object (Art. 21 GDPR): You may object to processing based on legitimate interests.",
              "Right to withdraw consent (Art. 7(3) GDPR): Where consent is the legal basis, you may withdraw it at any time.",
            ],
          },
          {
            type: "text",
            text: "To exercise your rights, please contact: datenschutz@ariia.ai\n\nYou also have the right to lodge a complaint with the competent data protection supervisory authority.",
          },
        ],
      },
      {
        heading: "9. Data Processing Agreement for Tenants",
        blocks: [
          {
            type: "text",
            text: "Tenants (business customers) who use ARIIA to process personal data of their end customers conclude a Data Processing Agreement (DPA) with us pursuant to Art. 28 GDPR. The DPA covers in particular:",
          },
          {
            type: "list",
            items: [
              "Subject matter, duration and nature of processing.",
              "Purpose and categories of processed data.",
              "Obligations and rights of the controller (Tenant).",
              "Technical and organisational measures of the processor (ARIIA).",
              "Provisions on sub-processors (in particular OpenAI, Twilio, Meta).",
            ],
          },
          {
            type: "text",
            text: "To request the DPA, please contact: datenschutz@ariia.ai",
          },
        ],
      },
      {
        heading: "10. Notes on AI Processing",
        blocks: [
          {
            type: "text",
            text: "ARIIA uses OpenAI language models (GPT-4o-mini) for AI agents and campaign generation. The following principles apply:",
          },
          {
            type: "list",
            items: [
              "Data transfer: Chat messages and relevant context data are transmitted to OpenAI for processing. Transfer is solely for processing the respective request (not used for OpenAI model training per API terms).",
              "AI outputs: AI-generated content may be inaccurate. ARIIA makes no warranty as to the accuracy of AI-generated texts, recommendations or assessments.",
              "Health-related queries: The Medic agent always includes a liability disclaimer and refers to emergency services (112/999) in emergencies. No diagnoses.",
              "PII protection: Recognised personal data is masked in logs before transmission to the LLM (PII filter).",
            ],
          },
        ],
      },
      {
        heading: "11. Changes to this Privacy Policy",
        blocks: [
          {
            type: "text",
            text: "We reserve the right to update this Privacy Policy to reflect changes in law, platform features or processing activities. The current version is available at www.ariia.ai/datenschutz. Tenants will be informed of material changes by email or via the admin dashboard.",
          },
        ],
      },
    ],
  },
};

/* ─── Sub-components ──────────────────────────────────────────────────────── */

function RenderTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div style={{ overflowX: "auto", borderRadius: 10, border: `1px solid ${C.border}` }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr style={{ background: C.tableHd }}>
            {headers.map((h, i) => (
              <th
                key={i}
                style={{
                  padding: "10px 14px",
                  textAlign: "left",
                  fontWeight: 700,
                  color: C.heading,
                  borderBottom: `1px solid ${C.border}`,
                  whiteSpace: "nowrap",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr
              key={ri}
              style={{ borderBottom: ri < rows.length - 1 ? `1px solid ${C.border}` : "none" }}
            >
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  style={{
                    padding: "10px 14px",
                    color: C.text,
                    verticalAlign: "top",
                    lineHeight: 1.6,
                  }}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
        if (block.type === "table") {
          return <RenderTable key={i} headers={block.headers} rows={block.rows} />;
        }
        return null;
      })}
    </div>
  );
}

/* ─── Component ────────────────────────────────────────────────────────────── */

export default function DatenschutzClient() {
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
                Legal · GDPR
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
              ARIIA · datenschutz@ariia.ai · www.ariia.ai
            </div>
          </motion.div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
