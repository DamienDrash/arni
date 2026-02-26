import { Metadata } from "next";
import RegisterClient from "./RegisterClient";

export const metadata: Metadata = {
  title: "Registrieren – Kostenloses ARIIA-Konto erstellen",
  description:
    "Erstellen Sie Ihr kostenloses ARIIA-Konto und starten Sie mit 14 Tagen kostenlosem Test. KI-gestützte Kundenkommunikation für Ihr Fitnessstudio.",
  keywords: [
    "ARIIA registrieren",
    "Fitness KI kostenlos testen",
    "Studio Software Registrierung",
    "KI Chatbot kostenlos",
  ],
  alternates: {
    canonical: "/register",
  },
  openGraph: {
    title: "ARIIA – Kostenloses Konto erstellen",
    description:
      "14 Tage kostenlos testen. Automatisieren Sie die Kundenkommunikation Ihres Fitnessstudios mit KI.",
    url: "https://www.ariia.ai/register",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "ARIIA – Jetzt kostenlos registrieren",
    description:
      "14 Tage kostenlos testen. KI-gestützte Kundenkommunikation für Fitnessstudios.",
  },
};

export default function Page() {
  return <RegisterClient />;
}
