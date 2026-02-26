import { Metadata } from "next";
import FeaturesClient from "./FeaturesClient";

const SITE_URL = "https://www.ariia.ai";
const OG_IMAGE = `${SITE_URL}/og-features.png`;

export const metadata: Metadata = {
  title: "Features – Multi-Agent Orchestration, Swarm Intelligence & Enterprise AI",
  description:
    "Entdecken Sie die technischen Highlights von ARIIA: Multi-Agent Orchestration, 3-Tier Memory, Vision AI, Voice Pipeline und Omnichannel Support. Die umfassendste Enterprise AI Agent Platform für intelligente Kundenkommunikation.",
  keywords: [
    "KI Agenten Swarm Intelligence",
    "Multi-Agent Orchestration",
    "Enterprise AI Features",
    "Vision AI Business",
    "3-Tier Memory AI",
    "Voice Pipeline KI",
    "WhatsApp Bot Features",
    "Telegram Integration Business",
    "CRM API Integration",
    "AI Knowledge Base",
    "Contact Memory System",
    "Echtzeit Analytics",
    "Omnichannel Automatisierung",
    "Enterprise SaaS Features",
  ],
  alternates: {
    canonical: "/features",
  },
  openGraph: {
    title: "ARIIA Features | Enterprise AI Agent Platform",
    description:
      "Von Voice Pipeline bis Vision Agent – ARIIA bietet die umfassendste Enterprise AI Agent Platform. Multi-Channel, Multi-Agent, Multi-Tenant.",
    url: `${SITE_URL}/features`,
    type: "website",
    images: [
      {
        url: OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "ARIIA Features – Enterprise AI Agent Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "ARIIA Features | Enterprise AI Agent Platform",
    description:
      "Multi-Agent Orchestration, Voice AI, Vision AI und mehr. Entdecken Sie die Zukunft der intelligenten Kundenkommunikation.",
    images: [OG_IMAGE],
  },
};

export default function Page() {
  return <FeaturesClient />;
}
