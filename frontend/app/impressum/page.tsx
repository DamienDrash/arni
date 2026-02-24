"use client";

/*
 * ARIIA Impressum – Studio Deck Design
 */
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { motion } from "framer-motion";

const sectionStyle = { color: "oklch(0.65 0.015 270)" };
const headingStyle = { color: "oklch(0.97 0.005 270)" };

export default function ImpressumPage() {
  return (
    <div className="min-h-screen" style={{ background: "oklch(0.08 0.02 270)" }}>
      <Navbar />
      <main className="pt-28 pb-20 lg:pt-36 lg:pb-28">
        <div className="container mx-auto px-4 max-w-3xl">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <h1 className="text-3xl lg:text-4xl font-bold tracking-tight mb-8" style={headingStyle}>
              Impressum
            </h1>

            <div className="space-y-8 text-sm leading-relaxed" style={sectionStyle}>
              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>Angaben gemäß § 5 TMG</h2>
                <p>
                  ARIIA GmbH (i.G.)<br />
                  Musterstraße 1<br />
                  10115 Berlin<br />
                  Deutschland
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>Vertreten durch</h2>
                <p>Geschäftsführer: Damien Frigewski</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>Kontakt</h2>
                <p>
                  Telefon: +49 (0) 30 123 456 78<br />
                  E-Mail: hello@ariia.ai<br />
                  Webseite: www.ariia.ai
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>Registereintrag</h2>
                <p>
                  Eintragung im Handelsregister.<br />
                  Registergericht: Amtsgericht Berlin-Charlottenburg<br />
                  Registernummer: HRB XXXXX (in Gründung)
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>Umsatzsteuer-ID</h2>
                <p>
                  Umsatzsteuer-Identifikationsnummer gemäß § 27a Umsatzsteuergesetz:<br />
                  DE XXXXXXXXX (wird nach Gründung vergeben)
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>Verantwortlich für den Inhalt nach § 55 Abs. 2 RStV</h2>
                <p>
                  Damien Frigewski<br />
                  Musterstraße 1<br />
                  10115 Berlin
                </p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>Streitschlichtung</h2>
                <p>Die Europäische Kommission stellt eine Plattform zur Online-Streitbeilegung (OS) bereit: https://ec.europa.eu/consumers/odr/. Unsere E-Mail-Adresse finden Sie oben im Impressum. Wir sind nicht bereit oder verpflichtet, an Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>Haftung für Inhalte</h2>
                <p>Als Diensteanbieter sind wir gemäß § 7 Abs.1 TMG für eigene Inhalte auf diesen Seiten nach den allgemeinen Gesetzen verantwortlich. Nach §§ 8 bis 10 TMG sind wir als Diensteanbieter jedoch nicht verpflichtet, übermittelte oder gespeicherte fremde Informationen zu überwachen oder nach Umständen zu forschen, die auf eine rechtswidrige Tätigkeit hinweisen.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>Haftung für Links</h2>
                <p>Unser Angebot enthält Links zu externen Webseiten Dritter, auf deren Inhalte wir keinen Einfluss haben. Deshalb können wir für diese fremden Inhalte auch keine Gewähr übernehmen. Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter oder Betreiber der Seiten verantwortlich.</p>
              </section>
            </div>
          </motion.div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
