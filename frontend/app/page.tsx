import { Metadata } from "next";
import HomeClient from "./HomeClient";

const SITE_URL = "https://www.ariia.ai";
const OG_IMAGE = `${SITE_URL}/og-image.png`;

export const metadata: Metadata = {
  title: "ARIIA | Enterprise AI Agent Platform – Intelligente Kundenkommunikation automatisieren",
  description:
    "ARIIA automatisiert die Kundenkommunikation für Unternehmen jeder Branche über WhatsApp, Telegram und Voice. Multi-Agent Orchestration mit Swarm Intelligence steigert Effizienz, Kundenbindung und Umsatz. DSGVO-konform. Made in Germany. 14 Tage kostenlos testen.",
  keywords: [
    "Enterprise AI Agent Platform",
    "AI Chatbot Unternehmen",
    "WhatsApp Automatisierung Business",
    "KI Kundenkommunikation",
    "Multi-Agent Orchestration",
    "ARIIA AI",
    "Chatbot für Unternehmen",
    "Kundenkommunikation automatisieren",
    "Enterprise SaaS Deutschland",
    "KI Kundenverwaltung",
    "Voice AI Business",
    "Omnichannel Automatisierung",
    "Swarm Intelligence SaaS",
    "Multi-Tenant AI Platform",
    "CRM Integration KI",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "ARIIA | Enterprise AI Agent Platform – Intelligente Kundenkommunikation",
    description:
      "Die führende Enterprise AI Agent Platform. Automatisieren Sie Kundenkommunikation über WhatsApp, Telegram und Voice mit Multi-Agent Orchestration. DSGVO-konform.",
    url: SITE_URL,
    siteName: "ARIIA",
    images: [
      {
        url: OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "ARIIA – Enterprise AI Agent Platform Dashboard",
      },
    ],
    locale: "de_DE",
    alternateLocale: ["en_US"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "ARIIA | Enterprise AI Agent Platform",
    description:
      "Automatisieren Sie Kundenkommunikation über WhatsApp, Telegram und Voice mit Multi-Agent Orchestration. DSGVO-konform. 14 Tage kostenlos testen.",
    images: [OG_IMAGE],
    creator: "@ariia_ai",
  },
};

export default function Page() {
  return <HomeClient />;
}
