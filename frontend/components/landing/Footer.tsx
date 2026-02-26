/*
 * ARIIA Footer – Studio Deck Design Language
 * Violet primary, Deep Navy base.
 */
import Link from "next/link";
import AriiaLogo from "./AriiaLogo";
import { useI18n } from "@/lib/i18n/LanguageContext";

export default function Footer() {
  const { t } = useI18n();
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
              {t("footer.brandDesc")}
            </p>
          </div>

          {/* Produkt */}
          <nav aria-label="Produkt-Navigation">
            <h4 className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.55 0.015 270)" }}>
              {t("footer.product")}
            </h4>
            <div className="space-y-2.5">
              <Link href="/features" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>{t("footer.links.features")}</Link>
              <Link href="/pricing" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>{t("footer.links.pricing")}</Link>
              <Link href="/register" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>{t("footer.links.test")}</Link>
            </div>
          </nav>

          {/* Unternehmen */}
          <nav aria-label="Rechtliche Navigation">
            <h4 className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.55 0.015 270)" }}>
              {t("footer.company")}
            </h4>
            <div className="space-y-2.5">
              <Link href="/impressum" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>{t("footer.links.impressum")}</Link>
              <Link href="/datenschutz" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>{t("footer.links.datenschutz")}</Link>
              <Link href="/agb" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>{t("footer.links.agb")}</Link>
            </div>
          </nav>

          {/* Kontakt */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.55 0.015 270)" }}>
              {t("footer.contact")}
            </h4>
            <div className="space-y-2.5">
              <a href="mailto:hello@ariia.ai" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>hello@ariia.ai</a>
              <a href="mailto:enterprise@ariia.ai" className="block text-sm no-underline transition-colors" style={{ color: "oklch(0.5 0.015 270)" }}>{t("footer.links.enterprise")}</a>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="pt-6 flex flex-col sm:flex-row items-center justify-between gap-4"
          style={{ borderTop: "1px solid oklch(0.16 0.04 270)" }}>
          <p className="text-xs" style={{ color: "oklch(0.4 0.015 270)" }}>
            &copy; {new Date().getFullYear()} ARIIA. {t("footer.rights")}
          </p>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-xs" style={{ color: "oklch(0.4 0.015 270)" }}>
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: "oklch(0.62 0.22 292)" }} />
              {t("common.allSystemsOnline")}
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
