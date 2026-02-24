/*
 * ARIIA Footer – Studio Deck Design Language
 * Violet primary, Deep Navy base.
 */
import Link from "next/link";
import AriiaLogo from "./AriiaLogo";

export default function Footer() {
  return (
    <footer className="relative" style={{ background: "oklch(0.07 0.04 270)", borderTop: "1px solid oklch(0.16 0.04 270)" }}>
      <div className="container mx-auto px-4 py-14 lg:py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10 lg:gap-16 mb-12">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <div className="mb-4">
              <AriiaLogo variant="full" height={34} />
            </div>
            <p className="text-sm leading-relaxed max-w-xs" style={{ color: "oklch(0.45 0.015 270)" }}>
              KI-gestützte Kundenkommunikation für Fitness Studios, Personal Trainer und KMUs. Made in Germany.
            </p>
          </div>

          {/* Produkt */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.55 0.015 270)" }}>
              Produkt
            </h4>
            <div className="space-y-2.5">
              <Link href="/features" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>Features</Link>
              <Link href="/pricing" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>Pricing</Link>
              <Link href="/register" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>Kostenlos testen</Link>
            </div>
          </div>

          {/* Unternehmen */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.55 0.015 270)" }}>
              Unternehmen
            </h4>
            <div className="space-y-2.5">
              <Link href="/impressum" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>Impressum</Link>
              <Link href="/datenschutz" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>Datenschutz</Link>
              <Link href="/agb" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>AGB</Link>
            </div>
          </div>

          {/* Kontakt */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.55 0.015 270)" }}>
              Kontakt
            </h4>
            <div className="space-y-2.5">
              <a href="mailto:hello@ariia.ai" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>hello@ariia.ai</a>
              <a href="mailto:enterprise@ariia.ai" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>Enterprise Anfragen</a>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="pt-6 flex flex-col sm:flex-row items-center justify-between gap-4"
          style={{ borderTop: "1px solid oklch(0.16 0.04 270)" }}>
          <p className="text-xs" style={{ color: "oklch(0.4 0.015 270)" }}>
            &copy; {new Date().getFullYear()} ARIIA. Alle Rechte vorbehalten.
          </p>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-xs" style={{ color: "oklch(0.4 0.015 270)" }}>
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: "oklch(0.62 0.22 292)" }} />
              Alle Systeme online
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
