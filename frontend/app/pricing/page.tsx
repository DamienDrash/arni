import { Metadata } from "next";
import PricingClient from "./PricingClient";

const SITE_URL = "https://www.ariia.ai";
const OG_IMAGE = `${SITE_URL}/og-pricing.png`;

export const metadata: Metadata = {
  title: "Preise & Pläne – Flexible Tarife für jede Unternehmensgröße",
  description:
    "Wählen Sie den passenden ARIIA-Tarif für Ihr Unternehmen. Von Starter (49€/Monat) bis Enterprise (499€/Monat) – faire Preise, transparente Leistungen und 14 Tage kostenlos testen. DSGVO-konform.",
  keywords: [
    "ARIIA Preise",
    "Enterprise AI Kosten",
    "KI SaaS Preisgestaltung",
    "Business Automatisierung Tarife",
    "AI Agent Platform Preise",
    "AI Chatbot Kosten",
    "WhatsApp Bot Preise",
    "Enterprise CRM KI Preise",
    "Multi-Agent Orchestration Kosten",
  ],
  alternates: {
    canonical: "/pricing",
  },
  openGraph: {
    title: "ARIIA Preise | Transparent & Skalierbar",
    description:
      "Starten Sie noch heute mit der intelligenten Automatisierung Ihrer Kundenkommunikation. Ab 49€/Monat oder 14 Tage kostenlos testen.",
    url: `${SITE_URL}/pricing`,
    type: "website",
    images: [
      {
        url: OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "ARIIA Pricing – Flexible Tarife für Unternehmen",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "ARIIA Preise | Ab 49€/Monat für Unternehmen",
    description:
      "Faire Preise, transparente Leistungen. Von Starter bis Enterprise – für jede Unternehmensgröße der passende Plan.",
    images: [OG_IMAGE],
  },
};

export default function Page() {
  return <PricingClient />;
}
