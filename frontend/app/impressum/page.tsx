"use client";

/*
 * ARIIA Impressum – Studio Deck Design
 */
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { motion } from "framer-motion";
import { useI18n } from "@/lib/i18n/LanguageContext";

const sectionStyle = { color: "oklch(0.65 0.015 270)" };
const headingStyle = { color: "oklch(0.97 0.005 270)" };

export default function ImpressumPage() {
  const { t } = useI18n();
  return (
    <div className="min-h-screen" style={{ background: "oklch(0.08 0.02 270)" }}>
      <Navbar />
      <main className="pt-28 pb-20 lg:pt-36 lg:pb-28">
        <div className="container mx-auto px-4 max-w-3xl">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <h1 className="text-3xl lg:text-4xl font-bold tracking-tight mb-8" style={headingStyle}>
              {t("legal.impressum.title")}
            </h1>

            <div className="space-y-8 text-sm leading-relaxed" style={sectionStyle}>
              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.impressum.tmg5")}</h2>
                <p>
                  ARIIA GmbH (i.G.)<br />
                  Musterstraße 1<br />
                  10115 Berlin<br />
                  Deutschland
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.impressum.representedBy")}</h2>
                <p>{t("legal.impressum.managingDirector")}: Damien Frigewski</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.impressum.contact")}</h2>
                <p>
                  {t("legal.impressum.phone")}: +49 (0) 30 123 456 78<br />
                  {t("legal.impressum.email")}: hello@ariia.ai<br />
                  {t("legal.impressum.website")}: www.ariia.ai
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.impressum.registerEntry")}</h2>
                <p>
                  Eintragung im Handelsregister.<br />
                  {t("legal.impressum.registerCourt")}: Amtsgericht Berlin-Charlottenburg<br />
                  {t("legal.impressum.registerNumber")}: HRB XXXXX (in Gründung)
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.impressum.vatId")}</h2>
                <p>
                  Umsatzsteuer-Identifikationsnummer gemäß § 27a Umsatzsteuergesetz:<br />
                  DE XXXXXXXXX (wird nach Gründung vergeben)
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.impressum.responsibleContent")}</h2>
                <p>
                  Damien Frigewski<br />
                  Musterstraße 1<br />
                  10115 Berlin
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.impressum.dispute")}</h2>
                <p>{t("impressum.disputeText")}</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.impressum.liabilityContent")}</h2>
                <p>{t("impressum.liabilityContentText")}</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.impressum.liabilityLinks")}</h2>
                <p>{t("impressum.liabilityLinksText")}</p>
              </section>
            </div>
          </motion.div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
