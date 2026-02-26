import { Metadata } from "next";
import LoginClient from "./LoginClient";

export const metadata: Metadata = {
  title: "Login – Anmelden bei ARIIA",
  description: "Melden Sie sich bei Ihrem ARIIA-Konto an und verwalten Sie Ihre Enterprise AI Agent Platform.",
  robots: {
    index: false,
    follow: false,
  },
  alternates: {
    canonical: "/login",
  },
};

export default function Page() {
  return <LoginClient />;
}
