"use client";

/*
 * ARIIA AGB – Studio Deck Design
 */
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { motion } from "framer-motion";

const sectionStyle = { color: "oklch(0.65 0.015 270)" };
const headingStyle = { color: "oklch(0.97 0.005 270)" };

export default function AGBPage() {
  return (
    <div className="min-h-screen" style={{ background: "oklch(0.08 0.02 270)" }}>
      <Navbar />
      <main className="pt-28 pb-20 lg:pt-36 lg:pb-28">
        <div className="container mx-auto px-4 max-w-3xl">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <h1 className="text-3xl lg:text-4xl font-bold tracking-tight mb-8" style={headingStyle}>
              Allgemeine Geschäftsbedingungen
            </h1>

            <div className="space-y-8 text-sm leading-relaxed" style={sectionStyle}>
              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>§ 1 Geltungsbereich</h2>
                <p>Diese Allgemeinen Geschäftsbedingungen (AGB) gelten für alle Verträge zwischen der ARIIA GmbH (i.G.), Musterstraße 1, 10115 Berlin (nachfolgend „Anbieter") und dem Kunden (nachfolgend „Kunde") über die Nutzung der ARIIA-Plattform als Software-as-a-Service (SaaS). Abweichende Bedingungen des Kunden werden nicht anerkannt, es sei denn, der Anbieter stimmt ihrer Geltung ausdrücklich schriftlich zu.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>§ 2 Vertragsgegenstand</h2>
                <p>Der Anbieter stellt dem Kunden die ARIIA-Plattform zur Verfügung, eine KI-gestützte Lösung für automatisierte Kundenkommunikation über verschiedene Kanäle (WhatsApp, Telegram, Voice, SMS, E-Mail). Der genaue Leistungsumfang ergibt sich aus dem vom Kunden gewählten Tarif (Starter, Pro oder Enterprise) sowie etwaigen Add-ons.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>§ 3 Vertragsschluss und Testphase</h2>
                <p>Der Vertrag kommt durch die Registrierung des Kunden auf der Webseite und die Bestätigung durch den Anbieter zustande. Jeder neue Kunde erhält eine kostenlose Testphase von 14 Tagen. Während der Testphase kann der Kunde den vollen Funktionsumfang des gewählten Tarifs nutzen. Nach Ablauf der Testphase wird der Vertrag automatisch in ein kostenpflichtiges Abonnement überführt, sofern der Kunde nicht vorher kündigt.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>§ 4 Preise und Zahlungsbedingungen</h2>
                <p>Die aktuellen Preise ergeben sich aus der Preisliste auf der Webseite des Anbieters. Alle Preise verstehen sich zuzüglich der gesetzlichen Mehrwertsteuer. Die Abrechnung erfolgt monatlich oder jährlich im Voraus, je nach gewähltem Abrechnungszeitraum. Bei jährlicher Abrechnung gewährt der Anbieter einen Rabatt von 20% auf den monatlichen Preis. Die Zahlung erfolgt per Kreditkarte, SEPA-Lastschrift oder Überweisung.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>§ 5 Laufzeit und Kündigung</h2>
                <p>Bei monatlicher Abrechnung beträgt die Mindestlaufzeit einen Monat. Der Vertrag verlängert sich automatisch um jeweils einen weiteren Monat, sofern er nicht mit einer Frist von 14 Tagen zum Ende des jeweiligen Abrechnungszeitraums gekündigt wird. Bei jährlicher Abrechnung beträgt die Mindestlaufzeit ein Jahr. Die Kündigung kann schriftlich oder über das Kundenkonto erfolgen.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>§ 6 Verfügbarkeit und SLA</h2>
                <p>Der Anbieter bemüht sich um eine Verfügbarkeit der Plattform von 99,9% im Jahresmittel. Geplante Wartungsarbeiten werden dem Kunden mindestens 48 Stunden im Voraus angekündigt und finden nach Möglichkeit außerhalb der Geschäftszeiten statt. Im Enterprise-Tarif gelten individuelle SLA-Vereinbarungen.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>§ 7 Datenschutz</h2>
                <p>Der Anbieter verarbeitet personenbezogene Daten des Kunden und seiner Endkunden ausschließlich im Rahmen der geltenden Datenschutzgesetze, insbesondere der DSGVO. Einzelheiten zur Datenverarbeitung sind in der Datenschutzerklärung und im Auftragsverarbeitungsvertrag (AVV) geregelt, der auf Anfrage bereitgestellt wird.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>§ 8 Haftung</h2>
                <p>Der Anbieter haftet unbeschränkt für Vorsatz und grobe Fahrlässigkeit. Bei leichter Fahrlässigkeit haftet der Anbieter nur bei Verletzung wesentlicher Vertragspflichten (Kardinalpflichten) und begrenzt auf den vorhersehbaren, vertragstypischen Schaden. Die Haftung für mittelbare Schäden, Folgeschäden und entgangenen Gewinn ist bei leichter Fahrlässigkeit ausgeschlossen.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>§ 9 Schlussbestimmungen</h2>
                <p>Es gilt das Recht der Bundesrepublik Deutschland unter Ausschluss des UN-Kaufrechts. Gerichtsstand für alle Streitigkeiten aus oder im Zusammenhang mit diesem Vertrag ist Berlin, sofern der Kunde Kaufmann, juristische Person des öffentlichen Rechts oder öffentlich-rechtliches Sondervermögen ist. Sollten einzelne Bestimmungen dieser AGB unwirksam sein oder werden, bleibt die Wirksamkeit der übrigen Bestimmungen unberührt.</p>
              </section>

              <p className="pt-4" style={{ color: "oklch(0.45 0.02 280)" }}>Stand: Februar 2026</p>
            </div>
          </motion.div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
