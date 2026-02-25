import { Metadata } from "next";
import PricingClient from "./PricingClient";

export const metadata: Metadata = {
  title: "Pricing | ARIIA - Flexible Pläne für jedes Studio",
  description: "Wählen Sie den passenden ARIIA-Tarif für Ihr Business. Von Starter bis Enterprise - faire Preise und 14 Tage kostenlos testen.",
  keywords: ["ARIIA Preise", "Fitness KI Kosten", "KI SaaS Preisgestaltung", "Studio Automatisierung Tarife"],
  openGraph: {
    title: "ARIIA Pricing | Transparent & Skalierbar",
    description: "Starten Sie noch heute mit der digitalen Transformation Ihres Studios.",
    url: "https://services.frigew.ski/ariia/pricing",
    type: "website",
  },
};

export default function Page() {
  return <PricingClient />;
}
