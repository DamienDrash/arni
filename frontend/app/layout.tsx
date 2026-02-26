import type { Metadata } from "next";
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

export const metadata: Metadata = {
  metadataBase: new URL("https://www.ariia.ai"),
  title: {
    default: "ARIIA | AI Living System Agent",
    template: "%s | ARIIA"
  },
  description: "Enterprise AI Agent Platform for Studio Operations",
  alternates: {
    canonical: "/",
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
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="inntegrate-hybrid">
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
