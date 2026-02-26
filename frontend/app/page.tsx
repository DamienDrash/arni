import { Metadata } from "next";
import HomeClient from "./HomeClient";

const SITE_URL = "https://www.ariia.ai";
const OG_IMAGE = "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/uFpxKFIPPBOjWMhN.png";

export const metadata: Metadata = {
  title: "ARIIA | KI-Plattform für Fitnessstudios – Automatisierte Kundenkommunikation",
  description:
    "ARIIA automatisiert die Kundenkommunikation für Fitnessstudios über WhatsApp, Telegram und Voice. Intelligente AI-Agenten steigern Effizienz, Mitgliederbindung und Umsatz. 14 Tage kostenlos testen.",
  keywords: [
    "KI Fitnessstudio",
    "AI Chatbot Fitness",
    "WhatsApp Automatisierung Fitnessstudio",
    "Fitness Marketing Automatisierung",
    "Magicline Integration KI",
    "ARIIA AI",
    "Chatbot für Fitnessstudios",
    "Kundenkommunikation automatisieren",
    "Fitness Studio Software",
    "KI Mitgliederverwaltung",
    "Voice AI Fitness",
    "Telegram Bot Fitnessstudio",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "ARIIA | KI-Plattform für Fitnessstudios – Automatisierte Kundenkommunikation",
    description:
      "Die führende KI-Plattform für Fitnessstudios. Automatisieren Sie Kundenkommunikation über WhatsApp, Telegram und Voice mit intelligenten AI-Agenten.",
    url: SITE_URL,
    siteName: "ARIIA",
    images: [
      {
        url: OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "ARIIA – KI-Plattform für Fitnessstudios Dashboard",
      },
    ],
    locale: "de_DE",
    alternateLocale: ["en_US"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "ARIIA | KI-Plattform für Fitnessstudios",
    description:
      "Automatisieren Sie Kundenkommunikation über WhatsApp, Telegram und Voice mit intelligenten AI-Agenten. 14 Tage kostenlos testen.",
    images: [OG_IMAGE],
    creator: "@ariia_ai",
  },
};

export default function Page() {
  return <HomeClient />;
}
