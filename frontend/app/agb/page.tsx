import { Metadata } from "next";
import AgbClient from "./AgbClient";

export const metadata: Metadata = {
  title: "AGB – Allgemeine Geschäftsbedingungen",
  description:
    "Allgemeine Geschäftsbedingungen der ARIIA KI-Plattform. Nutzungsbedingungen für die SaaS-Plattform.",
  robots: {
    index: true,
    follow: true,
  },
  alternates: {
    canonical: "/agb",
  },
};

export default function Page() {
  return <AgbClient />;
}
