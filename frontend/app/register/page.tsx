import { Metadata } from "next";
import RegisterClient from "./RegisterClient";

export const metadata: Metadata = {
  title: "Registrieren – Kostenloses ARIIA-Konto erstellen",
  description:
    "Erstellen Sie Ihr kostenloses ARIIA-Konto und starten Sie mit 14 Tagen kostenlosem Test. KI-gestützte Kundenkommunikation für Ihr Unternehmen. Enterprise AI Agent Platform.",
  keywords: [
    "ARIIA registrieren",
    "Enterprise AI kostenlos testen",
    "AI Agent Platform Registrierung",
    "KI Chatbot kostenlos",
    "Business Automatisierung testen",
  ],
  alternates: {
    canonical: "/register",
  },
  openGraph: {
    title: "ARIIA – Kostenloses Konto erstellen",
    description:
      "14 Tage kostenlos testen. Automatisieren Sie die Kundenkommunikation Ihres Unternehmens mit Multi-Agent Orchestration.",
    url: "https://www.ariia.ai/register",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "ARIIA – Jetzt kostenlos registrieren",
    description:
      "14 Tage kostenlos testen. Enterprise AI Agent Platform für intelligente Kundenkommunikation.",
  },
};

export default function Page() {
  return <RegisterClient />;
}
