import type { Metadata } from "next";
import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import NavShell from "../components/NavShell";

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
  title: "ARNI Control Deck",
  description: "Enterprise Admin Interface for Arni AI",
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
        <NavShell>{children}</NavShell>
      </body>
    </html>
  );
}
