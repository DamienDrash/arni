"use client";

/**
 * AuthLayout – Wraps Login & Register pages with the Landing Page Navbar + Footer
 * so they feel like a natural part of the marketing site instead of standalone pages.
 */
import Navbar from "./Navbar";
import Footer from "./Footer";

interface AuthLayoutProps {
  children: React.ReactNode;
}

export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="flex flex-col min-h-screen" style={{ background: "oklch(0.08 0.04 270)" }}>
      <Navbar />
      <main className="flex-1 flex items-center justify-center pt-20 pb-16 px-4">
        {children}
      </main>
      <Footer />
    </div>
  );
}
