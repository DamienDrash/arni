import { Metadata } from "next";
import DatenschutzClient from "./DatenschutzClient";

export const metadata: Metadata = {
  title: "Datenschutzerklärung – DSGVO-konforme Datenverarbeitung",
  description:
    "Datenschutzerklärung der ARIIA KI-Plattform. Informationen zur Verarbeitung personenbezogener Daten gemäß DSGVO.",
  robots: {
    index: true,
    follow: true,
  },
  alternates: {
    canonical: "/datenschutz",
  },
};

export default function Page() {
  return <DatenschutzClient />;
}
