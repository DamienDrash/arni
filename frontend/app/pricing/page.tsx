import { Metadata } from "next";
import PricingClient from "./PricingClient";

const OG_IMAGE = "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/uFpxKFIPPBOjWMhN.png";

export const metadata: Metadata = {
  title: "Preise & Pläne – Flexible Tarife für jedes Fitnessstudio",
  description:
    "Wählen Sie den passenden ARIIA-Tarif für Ihr Fitnessstudio. Von Starter (49€/Monat) bis Enterprise (499€/Monat) – faire Preise, transparente Leistungen und 14 Tage kostenlos testen.",
  keywords: [
    "ARIIA Preise",
    "Fitness KI Kosten",
    "KI SaaS Preisgestaltung",
    "Studio Automatisierung Tarife",
    "Fitnessstudio Software Preise",
    "AI Chatbot Kosten",
    "WhatsApp Bot Preise",
    "Fitness CRM Preise",
  ],
  alternates: {
    canonical: "/pricing",
  },
  openGraph: {
    title: "ARIIA Preise | Transparent & Skalierbar",
    description:
      "Starten Sie noch heute mit der digitalen Transformation Ihres Studios. Ab 49€/Monat oder 14 Tage kostenlos testen.",
    url: "https://www.ariia.ai/pricing",
    type: "website",
    images: [
      {
        url: OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "ARIIA Pricing – Flexible Tarife für Fitnessstudios",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "ARIIA Preise | Ab 49€/Monat für Fitnessstudios",
    description:
      "Faire Preise, transparente Leistungen. Von Starter bis Enterprise – für jede Studiogröße der passende Plan.",
    images: [OG_IMAGE],
  },
};

export default function Page() {
  return <PricingClient />;
}
