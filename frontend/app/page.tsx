import { Metadata } from "next";
import HomeClient from "./HomeClient";

export const metadata: Metadata = {
  title: "ARIIA | Der intelligente KI-Assistent für Fitnessstudios",
  description: "ARIIA automatisiert die Kundenkommunikation für Fitnessstudios über WhatsApp, Telegram und Voice. Steigern Sie Ihre Effizienz mit Arnold Prime Orchestration.",
  keywords: ["KI Fitnessstudio", "Fitness Marketing Automatisierung", "KI Chatbot WhatsApp", "Magicline Integration KI", "ARIIA AI"],
  openGraph: {
    title: "ARIIA | AI Living System Agent",
    description: "Die Evolution der Studio-Operationen. Agentic Multi-Tenant SaaS Platform.",
    url: "https://services.frigew.ski/arni/",
    siteName: "ARIIA",
    images: [
      {
        url: "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/uFpxKFIPPBOjWMhN.png",
        width: 1200,
        height: 630,
        alt: "ARIIA Studio Deck Dashboard",
      },
    ],
    locale: "de_DE",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "ARIIA | AI Living System Agent",
    description: "KI-gestützte Kundenkommunikation für moderne Fitnessstudios.",
    images: ["https://files.manuscdn.com/user_upload_by_module/session_file/107911917/uFpxKFIPPBOjWMhN.png"],
  },
};

export default function Page() {
  return <HomeClient />;
}
