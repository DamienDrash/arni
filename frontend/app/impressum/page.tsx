import { Metadata } from "next";
import ImpressumClient from "./ImpressumClient";

export const metadata: Metadata = {
  title: "Impressum – Anbieterkennzeichnung",
  description:
    "Impressum und Anbieterkennzeichnung der ARIIA KI-Plattform gemäß § 5 TMG.",
  robots: {
    index: true,
    follow: true,
  },
  alternates: {
    canonical: "/impressum",
  },
};

export default function Page() {
  return <ImpressumClient />;
}
