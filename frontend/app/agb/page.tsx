"use client";

/*
 * ARIIA AGB – Studio Deck Design
 */
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { motion } from "framer-motion";
import { useI18n } from "@/lib/i18n/LanguageContext";

const sectionStyle = { color: "oklch(0.65 0.015 270)" };
const headingStyle = { color: "oklch(0.97 0.005 270)" };

export default function AGBPage() {
  const { t } = useI18n();
  return (
    <div className="min-h-screen" style={{ background: "oklch(0.08 0.02 270)" }}>
      <Navbar />
      <main className="pt-28 pb-20 lg:pt-36 lg:pb-28">
        <div className="container mx-auto px-4 max-w-3xl">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <h1 className="text-3xl lg:text-4xl font-bold tracking-tight mb-8" style={headingStyle}>
              {t("legal.agb.title")}
            </h1>

                        <div className="space-y-8 text-sm leading-relaxed" style={sectionStyle}>
                          <section>
                            <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.agb.s1_title")}</h2>
                            <p>{t("legal.agb.s1_text")}</p>
                          </section>
            
                          <section>
                            <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.agb.s2_title")}</h2>
                            <p>{t("legal.agb.s2_text")}</p>
                          </section>
            
                          <section>
                            <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.agb.s3_title")}</h2>
                            <p>{t("legal.agb.s3_text")}</p>
                          </section>
            
                          <section>
                            <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.agb.s4_title")}</h2>
                            <p>{t("legal.agb.s4_text")}</p>
                          </section>
            
                          <section>
                            <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.agb.s5_title")}</h2>
                            <p>{t("legal.agb.s5_text")}</p>
                          </section>
            
                          <section>
                            <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.agb.s6_title")}</h2>
                            <p>{t("legal.agb.s6_text")}</p>
                          </section>
            
                          <section>
                            <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.agb.s7_title")}</h2>
                            <p>{t("legal.agb.s7_text")}</p>
                          </section>
            
                          <section>
                            <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.agb.s8_title")}</h2>
                            <p>{t("legal.agb.s8_text")}</p>
                          </section>
            
                          <section>
                            <h2 className="text-lg font-semibold mb-3" style={headingStyle}>{t("legal.agb.s9_title")}</h2>
                            <p>{t("legal.agb.s9_text")}</p>
                          </section>
            
                          <p className="pt-4" style={{ color: "oklch(0.45 0.02 280)" }}>{t("legal.agb.status")}</p>
                        </div>
          </motion.div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
