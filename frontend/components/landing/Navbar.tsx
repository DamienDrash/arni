import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n/LanguageContext";
import AriiaLogo from "./AriiaLogo";
import LanguageSwitcher from "@/components/i18n/LanguageSwitcher";

export default function Navbar() {
  const pathname = usePathname();
  const { t } = useI18n();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  const navLinks = [
    { href: "/", label: "Home" },
    { href: "/features", label: t("common.features") },
    { href: "/pricing", label: t("common.pricing") },
  ];

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="fixed top-0 left-0 right-0 z-50">
      <motion.div
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="mx-auto transition-all duration-300"
        style={{
          backdropFilter: "blur(24px)",
          background: scrolled ? "oklch(0.09 0.04 270 / 0.92)" : "oklch(0.09 0.04 270 / 0.7)",
          borderBottom: scrolled ? "1px solid oklch(0.62 0.22 292 / 0.15)" : "1px solid transparent",
        }}
      >
        <div className="container mx-auto px-4 flex items-center justify-between h-16 lg:h-[72px]">
          {/* Logo */}
          <Link href="/" className="flex items-center no-underline group">
            <AriiaLogo variant="full" height={44} className="transition-transform duration-300 group-hover:scale-105" />
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-1" aria-label="Hauptnavigation">
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className="relative text-sm font-medium px-4 py-2 rounded-lg transition-all duration-200 no-underline"
                  style={{
                    color: isActive ? "oklch(0.72 0.2 292)" : "oklch(0.65 0.015 270)",
                    background: isActive ? "oklch(0.62 0.22 292 / 0.1)" : "transparent",
                  }}
                >
                  {link.label}
                  {isActive && (
                    <motion.div
                      layoutId="nav-indicator"
                      className="absolute bottom-0 left-3 right-3 h-[2px] rounded-full"
                      style={{ background: "oklch(0.62 0.22 292)" }}
                      transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    />
                  )}
                </Link>
              );
            })}
          </nav>

          {/* Desktop CTA */}
          <div className="hidden md:flex items-center gap-3">
            <LanguageSwitcher />
            <Link href="/login">
              <Button variant="ghost" className="text-sm font-medium hover:bg-white/5 active:bg-white/10"
                style={{ color: "oklch(0.75 0.01 270)" }}>
                {t("navbar.login")}
              </Button>
            </Link>
            <Link href="/register">
              <Button className="text-sm px-5 py-2 rounded-lg font-bold shadow-lg shadow-indigo-500/20 active:scale-95" 
                style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>
                {t("navbar.register")}
              </Button>
            </Link>
          </div>

          {/* Mobile Toggle */}
          <div className="md:hidden flex items-center gap-2">
            <LanguageSwitcher />
            <button
              className="p-2 rounded-lg transition-colors"
              onClick={() => setMobileOpen(!mobileOpen)}
              style={{ color: "oklch(0.88 0.01 270)" }}
              aria-label={mobileOpen ? "Menü schließen" : "Menü öffnen"}
              aria-expanded={mobileOpen}
            >
              {mobileOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
        </div>
      </motion.div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="md:hidden overflow-hidden"
            style={{
              background: "oklch(0.10 0.04 270 / 0.98)",
              backdropFilter: "blur(24px)",
              borderBottom: "1px solid oklch(0.62 0.22 292 / 0.12)",
            }}
          >
            <div className="container mx-auto px-4 py-4 flex flex-col gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="text-base font-medium py-3 px-3 rounded-lg no-underline transition-colors"
                  style={{
                    color: pathname === link.href ? "oklch(0.72 0.2 292)" : "oklch(0.7 0.015 270)",
                    background: pathname === link.href ? "oklch(0.62 0.22 292 / 0.1)" : "transparent",
                  }}
                  onClick={() => setMobileOpen(false)}
                >
                  {link.label}
                </Link>
              ))}
              <div className="flex flex-col gap-2 pt-4 mt-2 border-t" style={{ borderColor: "oklch(0.22 0.04 270)" }}>
                <Link href="/login" onClick={() => setMobileOpen(false)}>
                  <Button variant="ghost" className="w-full justify-start" style={{ color: "oklch(0.75 0.01 270)" }}>
                    {t("navbar.login")}
                  </Button>
                </Link>
                <Link href="/register" onClick={() => setMobileOpen(false)}>
                  <Button className="w-full rounded-lg" style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>
                    {t("navbar.register")}
                  </Button>
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
