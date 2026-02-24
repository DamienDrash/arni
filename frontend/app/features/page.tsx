import { Metadata } from "next";
import FeaturesClient from "./FeaturesClient";

export const metadata: Metadata = {
  title: "Features | ARIIA - Intelligente KI-Agenten & Swarm Intelligence",
  description: "Entdecken Sie die technischen Highlights von ARIIA: Project Titan Orchestration, 3-Tier Memory, Vision AI und Multi-Channel Support für Ihr Studio.",
  keywords: ["KI Agenten Swarm", "Project Titan AI", "Fitness Studio Automatisierung Features", "Vision AI Gym", "3-Tier Memory AI"],
  openGraph: {
    title: "ARIIA Features | Die Zukunft der Fitness-KI",
    description: "Von Voice Pipeline bis Vision Agent - ARIIA bietet die umfassendste KI-Lösung für Studios.",
    url: "https://services.frigew.ski/arni/features",
    type: "website",
  },
};

export default function Page() {
  return <FeaturesClient />;
}
