"use client";

/*
 * ARIIA Datenschutzerklärung – Studio Deck Design
 */
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { motion } from "framer-motion";
import { useI18n } from "@/lib/i18n/LanguageContext";

const sectionStyle = { color: "oklch(0.65 0.015 270)" };
const headingStyle = { color: "oklch(0.97 0.005 270)" };

export default function DatenschutzClient() {
  const { t } = useI18n();
  return (
    <div className="min-h-screen" style={{ background: "oklch(0.08 0.02 270)" }}>
      <Navbar />
      <main className="pt-28 pb-20 lg:pt-36 lg:pb-28">
        <div className="container mx-auto px-4 max-w-3xl">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <h1 className="text-3xl lg:text-4xl font-bold tracking-tight mb-8" style={headingStyle}>
              {t("legal.privacy.title")}
            </h1>

            <div className="space-y-8 text-sm leading-relaxed" style={sectionStyle}>
              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.privacy.s1_title")}</h2>
                <p>{t("legal.privacy.s1_text")}</p>
                <p className="mt-2">ARIIA GmbH (i.G.)<br />Musterstraße 1<br />10115 Berlin<br />E-Mail: datenschutz@ariia.ai</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.privacy.s2_title")}</h2>
                <p>{t("legal.privacy.s2_text")}</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.privacy.s3_title")}</h2>
                <p>{t("legal.privacy.s3_text")}</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.privacy.s4_title")}</h2>
                <p>{t("legal.privacy.s4_text")}</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.privacy.s5_title")}</h2>
                <p>{t("legal.privacy.s5_text")}</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.privacy.s6_title")}</h2>
                <p>{t("legal.privacy.s6_text")}</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.privacy.s7_title")}</h2>
                <p>{t("legal.privacy.s7_text")}</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.privacy.s8_title")}</h2>
                <p>{t("legal.privacy.s8_text")}</p>
              </section>
            </div>
          </motion.div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
