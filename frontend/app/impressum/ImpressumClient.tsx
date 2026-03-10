"use client";

/**
 * ARIIA – Impressum (§ 5 TMG)
 * Production-ready, SaaS-specific, bilingual DE/EN.
 * Company details marked with [PLACEHOLDER] must be filled in before go-live.
 */
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { motion } from "framer-motion";
import { useI18n } from "@/lib/i18n/LanguageContext";

/* ─── Styles ──────────────────────────────────────────────────────────────── */
const C = {
  bg:       "oklch(0.08 0.02 270)",
  text:     "oklch(0.65 0.015 270)",
  heading:  "oklch(0.97 0.005 270)",
  muted:    "oklch(0.45 0.015 270)",
  accent:   "oklch(0.55 0.18 270)",
  border:   "oklch(0.18 0.02 270)",
  badge:    "oklch(0.14 0.03 270)",
};

/* ─── Content ─────────────────────────────────────────────────────────────── */
interface Section { heading: string; body: string | string[]; }

const CONTENT: Record<"de" | "en", {
  title: string;
  lastUpdated: string;
  legalNote: string;
  sections: Section[];
}> = {
  de: {
    title: "Impressum",
    lastUpdated: "Stand: März 2026",
    legalNote:
      "Hinweis: Dieses Impressum in deutscher Sprache ist das rechtlich maßgebliche Dokument. Übersetzungen dienen nur der Information.",
    sections: [
      {
        heading: "Angaben gemäß § 5 TMG",
        body: [
          "[PLACEHOLDER: Unternehmensname] (nachfolgend \"ARIIA\")",
          "[PLACEHOLDER: Straße Hausnummer]\n[PLACEHOLDER: PLZ Ort]\nDeutschland",
        ],
      },
      {
        heading: "Vertreten durch",
        body: "Geschäftsführer: Damien Frigewski",
      },
      {
        heading: "Kontakt",
        body: [
          "Telefon: [PLACEHOLDER: +49 (0) XX XXXX XXXX]",
          "E-Mail: hello@ariia.ai",
          "Website: www.ariia.ai",
        ],
      },
      {
        heading: "Registereintrag",
        body: [
          "Eintragung im Handelsregister.",
          "Registergericht: Amtsgericht [PLACEHOLDER: Ort]",
          "Registernummer: HRB [PLACEHOLDER: Nummer] (wird nach Eintragung vergeben)",
        ],
      },
      {
        heading: "Umsatzsteuer-Identifikationsnummer",
        body: [
          "gemäß § 27 a Umsatzsteuergesetz:",
          "DE [PLACEHOLDER: Nummer] (wird nach Gründung erteilt)",
        ],
      },
      {
        heading: "Verantwortlich für den Inhalt nach § 55 Abs. 2 RStV",
        body: [
          "Damien Frigewski",
          "[PLACEHOLDER: Straße Hausnummer]\n[PLACEHOLDER: PLZ Ort]",
        ],
      },
      {
        heading: "Gegenstand des Unternehmens",
        body: [
          "ARIIA ist eine cloudbasierte Software-as-a-Service (SaaS)-Plattform für Fitnessstudios und Gesundheitsdienstleister. Die Plattform umfasst KI-gestützte Kommunikationsagenten für WhatsApp, Telegram, SMS, E-Mail und Voice sowie ein integriertes Kampagnen-, Kontakt- und Wissensmanagement.",
          "ARIIA wird als Mehrmieter-System (Multi-Tenant) betrieben. Jeder Mieter (Tenant) erhält eine vollständig isolierte Umgebung mit eigenem Datenbereich.",
        ],
      },
      {
        heading: "EU-Streitschlichtung",
        body: [
          "Die Europäische Kommission stellt eine Plattform zur Online-Streitbeilegung (OS) bereit: https://ec.europa.eu/consumers/odr/",
          "Unsere E-Mail-Adresse finden Sie oben im Impressum.",
          "Wir sind nicht bereit oder verpflichtet, an Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen, da ARIIA ausschließlich an Unternehmen (B2B) vermarktet wird.",
        ],
      },
      {
        heading: "Haftung für Inhalte",
        body: "Als Diensteanbieter sind wir gemäß § 7 Abs. 1 TMG für eigene Inhalte auf diesen Seiten nach den allgemeinen Gesetzen verantwortlich. Nach §§ 8 bis 10 TMG sind wir als Diensteanbieter jedoch nicht verpflichtet, übermittelte oder gespeicherte fremde Informationen zu überwachen oder nach Umständen zu forschen, die auf eine rechtswidrige Tätigkeit hinweisen. Verpflichtungen zur Entfernung oder Sperrung der Nutzung von Informationen nach den allgemeinen Gesetzen bleiben hiervon unberührt. Eine diesbezügliche Haftung ist jedoch erst ab dem Zeitpunkt der Kenntnis einer konkreten Rechtsverletzung möglich. Bei Bekanntwerden von entsprechenden Rechtsverletzungen werden wir diese Inhalte umgehend entfernen.",
      },
      {
        heading: "Haftung für Links",
        body: "Unser Angebot enthält Links zu externen Websites Dritter, auf deren Inhalte wir keinen Einfluss haben. Deshalb können wir für diese fremden Inhalte auch keine Gewähr übernehmen. Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter oder Betreiber der Seiten verantwortlich. Die verlinkten Seiten wurden zum Zeitpunkt der Verlinkung auf mögliche Rechtsverstöße überprüft. Rechtswidrige Inhalte waren zum Zeitpunkt der Verlinkung nicht erkennbar. Eine permanente inhaltliche Kontrolle der verlinkten Seiten ist jedoch ohne konkrete Anhaltspunkte einer Rechtsverletzung nicht zumutbar. Bei Bekanntwerden von Rechtsverletzungen werden wir derartige Links umgehend entfernen.",
      },
      {
        heading: "Urheberrecht",
        body: [
          "Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen dem deutschen Urheberrecht. Die Vervielfältigung, Bearbeitung, Verbreitung und jede Art der Verwertung außerhalb der Grenzen des Urheberrechtes bedürfen der schriftlichen Zustimmung des jeweiligen Autors bzw. Erstellers.",
          "Downloads und Kopien dieser Seite sind nur für den privaten, nicht kommerziellen Gebrauch gestattet. Soweit die Inhalte auf dieser Seite nicht vom Betreiber erstellt wurden, werden die Urheberrechte Dritter beachtet. Insbesondere werden Inhalte Dritter als solche gekennzeichnet. Sollten Sie trotzdem auf eine Urheberrechtsverletzung aufmerksam werden, bitten wir um einen entsprechenden Hinweis. Bei Bekanntwerden von Rechtsverletzungen werden wir derartige Inhalte umgehend entfernen.",
        ],
      },
    ],
  },

  en: {
    title: "Imprint",
    lastUpdated: "As of: March 2026",
    legalNote:
      "Note: The German-language version of this imprint is the legally binding document. Translations are provided for information purposes only.",
    sections: [
      {
        heading: "Information according to § 5 TMG (German Telemedia Act)",
        body: [
          "[PLACEHOLDER: Company Name] (hereinafter \"ARIIA\")",
          "[PLACEHOLDER: Street No.]\n[PLACEHOLDER: ZIP City]\nGermany",
        ],
      },
      {
        heading: "Represented by",
        body: "Managing Director: Damien Frigewski",
      },
      {
        heading: "Contact",
        body: [
          "Phone: [PLACEHOLDER: +49 (0) XX XXXX XXXX]",
          "Email: hello@ariia.ai",
          "Website: www.ariia.ai",
        ],
      },
      {
        heading: "Register Entry",
        body: [
          "Entered in the commercial register.",
          "Register Court: District Court [PLACEHOLDER: City]",
          "Register Number: HRB [PLACEHOLDER: Number] (to be assigned upon registration)",
        ],
      },
      {
        heading: "VAT Identification Number",
        body: [
          "According to § 27 a of the German VAT Act:",
          "DE [PLACEHOLDER: Number] (to be issued upon incorporation)",
        ],
      },
      {
        heading: "Responsible for content according to § 55 (2) RStV",
        body: [
          "Damien Frigewski",
          "[PLACEHOLDER: Street No.]\n[PLACEHOLDER: ZIP City]",
        ],
      },
      {
        heading: "Business Purpose",
        body: [
          "ARIIA is a cloud-based Software-as-a-Service (SaaS) platform for fitness studios and health service providers. The platform includes AI-powered communication agents for WhatsApp, Telegram, SMS, Email and Voice as well as integrated campaign, contact and knowledge management.",
          "ARIIA operates as a multi-tenant system. Each tenant receives a fully isolated environment with a dedicated data domain.",
        ],
      },
      {
        heading: "EU Dispute Resolution",
        body: [
          "The European Commission provides a platform for online dispute resolution (ODR): https://ec.europa.eu/consumers/odr/",
          "Our email address can be found in the imprint above.",
          "We are not willing or obliged to participate in dispute resolution proceedings before a consumer arbitration board, as ARIIA is marketed exclusively to businesses (B2B).",
        ],
      },
      {
        heading: "Liability for Content",
        body: "As a service provider, we are responsible for our own content on these pages in accordance with § 7 (1) TMG and general law. However, according to §§ 8 to 10 TMG, we are not obligated to monitor transmitted or stored third-party information or to investigate circumstances that indicate illegal activity. Obligations to remove or block the use of information under general law remain unaffected. However, liability in this regard is only possible from the time of knowledge of a specific infringement. Upon becoming aware of such infringements, we will remove this content immediately.",
      },
      {
        heading: "Liability for Links",
        body: "Our website contains links to external third-party websites over whose content we have no control. Therefore, we cannot assume any liability for these external contents. The respective provider or operator of the linked pages is always responsible for their content. The linked pages were checked for possible legal violations at the time of linking. No illegal content was apparent at the time of linking. Permanent monitoring of the linked pages is not reasonable without concrete evidence of a legal violation. Upon becoming aware of legal violations, we will remove such links immediately.",
      },
      {
        heading: "Copyright",
        body: [
          "The content and works on these pages created by the site operators are subject to German copyright law. Reproduction, editing, distribution and any kind of exploitation outside the limits of copyright law require the written consent of the respective author or creator.",
          "Downloads and copies of this site are only permitted for private, non-commercial use. Where content on this site was not created by the operator, the copyrights of third parties are respected. Should you become aware of a copyright infringement, please inform us accordingly. Upon becoming aware of infringements, we will remove such content immediately.",
        ],
      },
    ],
  },
};

/* ─── Component ────────────────────────────────────────────────────────────── */

export default function ImpressumClient() {
  const { language } = useI18n();
  const lang = (language === "de" ? "de" : "en") as "de" | "en";
  const content = CONTENT[lang];

  return (
    <div className="min-h-screen" style={{ background: C.bg }}>
      <Navbar />
      <main className="pt-28 pb-20 lg:pt-36 lg:pb-28">
        <div className="container mx-auto px-4 max-w-3xl">
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
                Legal
              </div>
              <h1
                className="text-3xl lg:text-4xl font-bold tracking-tight mb-3"
                style={{ color: C.heading }}
              >
                {content.title}
              </h1>
              <p className="text-xs" style={{ color: C.muted }}>
                {content.lastUpdated}
              </p>
            </div>

            {/* Legal note (DE binding) */}
            <div
              className="mb-8 p-4 rounded-xl text-xs leading-relaxed border"
              style={{ background: C.badge, borderColor: C.border, color: C.muted }}
            >
              {content.legalNote}
            </div>

            {/* Sections */}
            <div className="space-y-8 text-sm leading-relaxed" style={{ color: C.text }}>
              {content.sections.map((section, i) => (
                <section key={i}>
                  <h2
                    className="text-base font-semibold mb-3"
                    style={{ color: C.heading }}
                  >
                    {section.heading}
                  </h2>
                  {Array.isArray(section.body) ? (
                    <div className="space-y-2">
                      {section.body.map((para, j) => (
                        <p key={j} style={{ whiteSpace: "pre-line" }}>
                          {para}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p style={{ whiteSpace: "pre-line" }}>{section.body}</p>
                  )}
                </section>
              ))}
            </div>

            {/* Divider */}
            <div
              className="mt-12 pt-6 border-t text-xs"
              style={{ borderColor: C.border, color: C.muted }}
            >
              ARIIA · hello@ariia.ai · www.ariia.ai
            </div>
          </motion.div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
