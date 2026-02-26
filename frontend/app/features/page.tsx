import { Metadata } from "next";
import FeaturesClient from "./FeaturesClient";

const OG_IMAGE = "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/uFpxKFIPPBOjWMhN.png";

export const metadata: Metadata = {
  title: "Features – Intelligente KI-Agenten & Swarm Intelligence für Fitnessstudios",
  description:
    "Entdecken Sie die technischen Highlights von ARIIA: Multi-Agent Orchestration, 3-Tier Memory, Vision AI, Voice Pipeline und Multi-Channel Support. Die umfassendste KI-Lösung für moderne Fitnessstudios.",
  keywords: [
    "KI Agenten Swarm Intelligence",
    "Multi-Agent Orchestration",
    "Fitness Studio Automatisierung Features",
    "Vision AI Fitnessstudio",
    "3-Tier Memory AI",
    "Voice Pipeline KI",
    "WhatsApp Bot Features",
    "Telegram Integration Fitness",
    "Magicline API Integration",
    "AI Knowledge Base",
    "Member Memory System",
    "Echtzeit Analytics",
  ],
  alternates: {
    canonical: "/features",
  },
  openGraph: {
    title: "ARIIA Features | Die Zukunft der Fitness-KI",
    description:
      "Von Voice Pipeline bis Vision Agent – ARIIA bietet die umfassendste KI-Lösung für Studios. Multi-Channel, Multi-Agent, Multi-Tenant.",
    url: "https://www.ariia.ai/features",
    type: "website",
    images: [
      {
        url: OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "ARIIA Features – KI-Agenten für Fitnessstudios",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "ARIIA Features | Intelligente KI-Agenten für Fitnessstudios",
    description:
      "Multi-Agent Orchestration, Voice AI, Vision AI und mehr. Entdecken Sie die Zukunft der Fitness-Kommunikation.",
    images: [OG_IMAGE],
  },
};

export default function Page() {
  return <FeaturesClient />;
}
