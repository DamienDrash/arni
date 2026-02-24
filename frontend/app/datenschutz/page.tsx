"use client";

/*
 * ARIIA Datenschutzerklärung – Studio Deck Design
 */
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { motion } from "framer-motion";

const sectionStyle = { color: "oklch(0.65 0.015 270)" };
const headingStyle = { color: "oklch(0.97 0.005 270)" };

export default function DatenschutzPage() {
  return (
    <div className="min-h-screen" style={{ background: "oklch(0.08 0.02 270)" }}>
      <Navbar />
      <main className="pt-28 pb-20 lg:pt-36 lg:pb-28">
        <div className="container mx-auto px-4 max-w-3xl">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <h1 className="text-3xl lg:text-4xl font-bold tracking-tight mb-8" style={headingStyle}>
              Datenschutzerklärung
            </h1>

            <div className="space-y-8 text-sm leading-relaxed" style={sectionStyle}>
              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>1. Verantwortlicher</h2>
                <p>Verantwortlich für die Datenverarbeitung auf dieser Webseite ist:</p>
                <p className="mt-2">ARIIA GmbH (i.G.)<br />Musterstraße 1<br />10115 Berlin<br />E-Mail: datenschutz@ariia.ai</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>2. Erhebung und Speicherung personenbezogener Daten</h2>
                <p>Beim Besuch unserer Webseite werden automatisch Informationen an den Server unserer Webseite gesendet. Diese Informationen werden temporär in einem sogenannten Logfile gespeichert. Folgende Informationen werden dabei ohne Ihr Zutun erfasst und bis zur automatisierten Löschung gespeichert: IP-Adresse des anfragenden Rechners, Datum und Uhrzeit des Zugriffs, Name und URL der abgerufenen Datei, Webseite, von der aus der Zugriff erfolgt (Referrer-URL), verwendeter Browser und ggf. das Betriebssystem Ihres Rechners sowie der Name Ihres Access-Providers.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>3. Weitergabe von Daten</h2>
                <p>Eine Übermittlung Ihrer persönlichen Daten an Dritte zu anderen als den im Folgenden aufgeführten Zwecken findet nicht statt. Wir geben Ihre persönlichen Daten nur an Dritte weiter, wenn Sie Ihre nach Art. 6 Abs. 1 S. 1 lit. a DSGVO ausdrückliche Einwilligung dazu erteilt haben, die Weitergabe nach Art. 6 Abs. 1 S. 1 lit. f DSGVO zur Geltendmachung, Ausübung oder Verteidigung von Rechtsansprüchen erforderlich ist und kein Grund zur Annahme besteht, dass Sie ein überwiegendes schutzwürdiges Interesse an der Nichtweitergabe Ihrer Daten haben.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>4. Cookies</h2>
                <p>Wir setzen auf unserer Seite Cookies ein. Hierbei handelt es sich um kleine Dateien, die Ihr Browser automatisch erstellt und die auf Ihrem Endgerät gespeichert werden, wenn Sie unsere Seite besuchen. Cookies richten auf Ihrem Endgerät keinen Schaden an, enthalten keine Viren, Trojaner oder sonstige Schadsoftware. In dem Cookie werden Informationen abgelegt, die sich jeweils im Zusammenhang mit dem spezifisch eingesetzten Endgerät ergeben.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>5. Analyse-Tools</h2>
                <p>Wir nutzen Umami Analytics, eine datenschutzfreundliche, DSGVO-konforme Webanalyse-Lösung. Umami speichert keine persönlichen Daten, verwendet keine Cookies und respektiert die „Do Not Track"-Einstellung Ihres Browsers. Alle Daten werden anonymisiert erhoben und auf unseren eigenen Servern in der EU verarbeitet.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>6. Betroffenenrechte</h2>
                <p>Sie haben das Recht: gemäß Art. 15 DSGVO Auskunft über Ihre von uns verarbeiteten personenbezogenen Daten zu verlangen, gemäß Art. 16 DSGVO unverzüglich die Berichtigung unrichtiger oder Vervollständigung Ihrer bei uns gespeicherten personenbezogenen Daten zu verlangen, gemäß Art. 17 DSGVO die Löschung Ihrer bei uns gespeicherten personenbezogenen Daten zu verlangen, gemäß Art. 20 DSGVO Ihre personenbezogenen Daten in einem strukturierten, gängigen und maschinenlesbaren Format zu erhalten oder die Übermittlung an einen anderen Verantwortlichen zu verlangen.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>7. Datensicherheit</h2>
                <p>Wir verwenden innerhalb des Webseiten-Besuchs das verbreitete SSL-Verfahren (Secure Socket Layer) in Verbindung mit der jeweils höchsten Verschlüsselungsstufe, die von Ihrem Browser unterstützt wird. Ob eine einzelne Seite unseres Internetauftrittes verschlüsselt übertragen wird, erkennen Sie an der geschlossenen Darstellung des Schlüssel- beziehungsweise Schloss-Symbols in der unteren Statusleiste Ihres Browsers.</p>
              </section>

              <section>
                <h2 className="text-lg font-semibold mb-3" style={headingStyle}>8. Aktualität und Änderung dieser Datenschutzerklärung</h2>
                <p>Diese Datenschutzerklärung ist aktuell gültig und hat den Stand Februar 2026. Durch die Weiterentwicklung unserer Webseite und Angebote darüber oder aufgrund geänderter gesetzlicher beziehungsweise behördlicher Vorgaben kann es notwendig werden, diese Datenschutzerklärung zu ändern.</p>
              </section>
            </div>
          </motion.div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
