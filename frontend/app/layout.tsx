import type { Metadata, Viewport } from "next";
import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import NavShell from "../components/NavShell";
import { Providers } from "./providers";

const headingFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-heading",
  display: "swap",
});

const monoFont = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
  weight: ["400", "500", "600"],
});

const SITE_URL = "https://www.ariia.ai";
const OG_IMAGE = "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/uFpxKFIPPBOjWMhN.png";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0a0b1a" },
    { media: "(prefers-color-scheme: light)", color: "#7c5cfc" },
  ],
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),

  title: {
    default: "ARIIA | KI-Plattform für Fitnessstudios – Automatisierte Kundenkommunikation",
    template: "%s | ARIIA",
  },
  description:
    "ARIIA ist die führende KI-Plattform für Fitnessstudios. Automatisieren Sie Kundenkommunikation über WhatsApp, Telegram und Voice mit intelligenten AI-Agenten. 14 Tage kostenlos testen.",

  applicationName: "ARIIA",
  authors: [{ name: "ARIIA", url: SITE_URL }],
  generator: "Next.js",
  keywords: [
    "KI Fitnessstudio",
    "AI Chatbot Fitnessstudio",
    "WhatsApp Automatisierung Fitness",
    "Fitness Studio Software",
    "KI Kundenkommunikation",
    "Magicline Integration",
    "AI Agent Platform",
    "Fitness Marketing Automatisierung",
    "ARIIA",
    "Chatbot für Studios",
    "Mitgliederverwaltung KI",
    "Voice AI Fitnessstudio",
    "Multi-Channel Kommunikation Fitness",
    "SaaS Fitnessstudio",
    "Fitness CRM KI",
  ],
  referrer: "origin-when-cross-origin",
  creator: "ARIIA",
  publisher: "ARIIA",

  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },

  alternates: {
    canonical: "/",
    languages: {
      "de-DE": "/",
      "en-US": "/",
    },
  },

  openGraph: {
    type: "website",
    locale: "de_DE",
    alternateLocale: ["en_US"],
    url: SITE_URL,
    siteName: "ARIIA",
    title: "ARIIA | KI-Plattform für Fitnessstudios – Automatisierte Kundenkommunikation",
    description:
      "Die führende KI-Plattform für Fitnessstudios. Automatisieren Sie Kundenkommunikation über WhatsApp, Telegram und Voice mit intelligenten AI-Agenten.",
    images: [
      {
        url: OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "ARIIA – KI-Plattform für Fitnessstudios Dashboard",
        type: "image/png",
      },
    ],
  },

  twitter: {
    card: "summary_large_image",
    title: "ARIIA | KI-Plattform für Fitnessstudios",
    description:
      "Automatisieren Sie Kundenkommunikation über WhatsApp, Telegram und Voice mit intelligenten AI-Agenten. 14 Tage kostenlos testen.",
    images: [OG_IMAGE],
    creator: "@ariia_ai",
    site: "@ariia_ai",
  },

  robots: {
    index: true,
    follow: true,
    nocache: false,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },

  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-96x96.png", sizes: "96x96", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
    shortcut: "/favicon.ico",
  },

  manifest: "/site.webmanifest",

  category: "technology",

  other: {
    "msapplication-TileColor": "#7c5cfc",
    "apple-mobile-web-app-capable": "yes",
    "apple-mobile-web-app-status-bar-style": "black-translucent",
    "apple-mobile-web-app-title": "ARIIA",
  },
};

/* ── JSON-LD Structured Data (Global) ── */
const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "ARIIA",
  url: SITE_URL,
  logo: `${SITE_URL}/logo-full-dark-large.png`,
  description:
    "ARIIA ist die führende KI-Plattform für Fitnessstudios. Automatisierte Kundenkommunikation über WhatsApp, Telegram und Voice.",
  foundingDate: "2024",
  sameAs: [],
  contactPoint: {
    "@type": "ContactPoint",
    email: "hello@ariia.ai",
    contactType: "customer service",
    availableLanguage: ["German", "English"],
  },
  address: {
    "@type": "PostalAddress",
    addressCountry: "DE",
  },
};

const websiteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "ARIIA",
  alternateName: ["ARIIA AI", "ARIIA KI-Plattform"],
  url: SITE_URL,
  description:
    "KI-Plattform für Fitnessstudios – Automatisierte Kundenkommunikation über WhatsApp, Telegram und Voice.",
  publisher: {
    "@type": "Organization",
    name: "ARIIA",
    url: SITE_URL,
  },
  potentialAction: {
    "@type": "SearchAction",
    target: {
      "@type": "EntryPoint",
      urlTemplate: `${SITE_URL}/features`,
    },
    "query-input": "required name=search_term_string",
  },
  inLanguage: ["de-DE", "en-US"],
};

const softwareJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "ARIIA",
  applicationCategory: "BusinessApplication",
  applicationSubCategory: "Customer Communication Platform",
  operatingSystem: "Web",
  url: SITE_URL,
  description:
    "Enterprise AI Agent Platform für Fitnessstudios. Automatisierte Kundenkommunikation über WhatsApp, Telegram, Voice und mehr.",
  offers: {
    "@type": "AggregateOffer",
    priceCurrency: "EUR",
    lowPrice: "0",
    highPrice: "499",
    offerCount: "4",
    offers: [
      {
        "@type": "Offer",
        name: "Trial",
        price: "0",
        priceCurrency: "EUR",
        description: "14 Tage kostenlos testen – Alle Starter-Features inklusive",
        url: `${SITE_URL}/register`,
      },
      {
        "@type": "Offer",
        name: "Starter",
        price: "49",
        priceCurrency: "EUR",
        description: "Für kleine Studios – bis 200 Mitglieder",
        url: `${SITE_URL}/pricing`,
      },
      {
        "@type": "Offer",
        name: "Professional",
        price: "149",
        priceCurrency: "EUR",
        description: "Für wachsende Studios – bis 2.000 Mitglieder",
        url: `${SITE_URL}/pricing`,
      },
      {
        "@type": "Offer",
        name: "Enterprise",
        price: "499",
        priceCurrency: "EUR",
        description: "Für Studio-Ketten – unbegrenzte Mitglieder",
        url: `${SITE_URL}/pricing`,
      },
    ],
  },
  featureList: [
    "WhatsApp Business Integration",
    "Telegram Bot Integration",
    "Voice AI Pipeline",
    "Magicline CRM Integration",
    "Multi-Channel Kommunikation",
    "AI-gestützte Mitgliederverwaltung",
    "Automatische Eskalation",
    "Knowledge Base Management",
    "Member Memory System",
    "Kampagnen-Management",
    "Echtzeit Analytics Dashboard",
    "Multi-Tenant Architektur",
  ],
  screenshot: OG_IMAGE,
  aggregateRating: {
    "@type": "AggregateRating",
    ratingValue: "4.8",
    ratingCount: "47",
    bestRating: "5",
    worstRating: "1",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="de" dir="ltr" data-theme="inntegrate-hybrid">
      <head>
        {/* Preconnect for performance */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />

        {/* DNS Prefetch for external resources */}
        <link rel="dns-prefetch" href="https://fonts.googleapis.com" />

        {/* JSON-LD Structured Data */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
        />
      </head>
      <body
        suppressHydrationWarning={true}
        className={`${headingFont.variable} ${monoFont.variable} font-sans antialiased`}
      >
        <Providers>
          <NavShell>{children}</NavShell>
        </Providers>
      </body>
    </html>
  );
}
