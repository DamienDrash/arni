# Roadmap: Sanierung des ARIIA-Kampagnen-Moduls

**Q1 2026**

Diese Roadmap skizziert die strategische Abfolge zur vollständigen Wiederherstellung und Optimierung der Kampagnen-Funktionalität. Das Projekt ist in drei Hauptmeilensteine unterteilt, die auf den Ergebnissen der Tiefenanalyse aufbauen.

---

### Meilenstein 1: Stabilisierung & Kritische Bugfixes (1-2 Wochen)

**Ziel:** Das System aus dem aktuellen, nicht funktionsfähigen Zustand in einen stabilen, minimal lauffähigen Zustand zu versetzen. Der Fokus liegt auf der Behebung der kritischen Fehler, die zu Abstürzen und dem vollständigen Stillstand des Kampagnenversands führen.

*   **Woche 1: Scheduler & Core Logic Repair**
    *   Behebung des `Contact.is_active`-Bugs im `campaign_scheduler_worker`.
    *   Korrektur des fehlerhaften `evaluate_segment_v2`-Aufrufs.
    *   Reparatur der `AdapterRegistry`-Importe und -Aufrufe.
    *   **Ergebnis:** Der Campaign Scheduler läuft stabil und kann prinzipiell wieder Kampagnen verarbeiten und versenden.

*   **Woche 2: Wiederherstellung des manuellen Versands & Trackings**
    *   Refactoring des `send_campaign`-Endpunkts zur Nutzung des zentralen `MessageRenderer`.
    *   Sicherstellung, dass Open- und Click-Tracking für alle E-Mails (manuell und geplant) korrekt injiziert werden.
    *   **Ergebnis:** Manuell gestartete Kampagnen sind wieder voll funktionsfähig, inklusive Analytics-Tracking.

---

### Meilenstein 2: Wiederherstellung der Kernfunktionalität (2-3 Wochen)

**Ziel:** Alle wesentlichen, vom Benutzer erwarteten Funktionen des Kampagnen-Moduls wiederherstellen und auf einen Gold-Standard bringen. Dies umfasst Analytics, Segmentierung und A/B-Testing.

*   **Woche 3: Analytics & Frontend-Integration**
    *   Reparatur und Validierung aller Analytics-API-Endpunkte (`/v2/admin/analytics/...`).
    *   Anpassung des Frontends (`CampaignAnalyticsPage`) zur korrekten Anbindung an die reparierten Endpunkte.
    *   Implementierung eines robusten `AnalyticsProcessor`, der alle Event-Typen (sent, delivered, opened, clicked, bounced, etc.) korrekt verarbeitet.
    *   **Ergebnis:** Die Analytics-Seite ist voll funktionsfähig und zeigt korrekte, zeitnahe Daten an.

*   **Woche 4: Robuste Segmentierung & A/B-Tests**
    *   Finalisierung der `evaluate_segment_v2`-Logik, um komplexe, mehrstufige Segment-Filter zu unterstützen.
    *   Vollständige Implementierung der A/B-Test-Logik im Backend, inklusive statistischer Auswertung und automatischem Versand der Gewinner-Variante.
    *   **Ergebnis:** Segmentierung und A/B-Tests sind zuverlässige Werkzeuge für den Marketer.

---

### Meilenstein 3: Architektur-Upgrade & Zukunftssicherheit (Laufend nach M2)

**Ziel:** Die Architektur des Kampagnen-Systems modernisieren, um zukünftige Skalierbarkeit, Zuverlässigkeit und Erweiterbarkeit zu gewährleisten. Dies basiert auf den Erkenntnissen der Gold-Standard-Recherche.

*   **Refactoring zu einer Event-Driven Architecture:**
    *   **Schritt 1: Entkopplung des Sendevorgangs:** Einführung eines dedizierten `SendingWorker`, der E-Mails aus einer Redis-Queue konsumiert. Der `campaign_scheduler_worker` ist nur noch für die Planung und das Einreihen der Sende-Jobs in die Queue zuständig.
    *   **Schritt 2: Optimierung der Ingestion:** Schaffung eines separaten `IngestionService` für eingehende Events (z.B. Webhooks von E-Mail-Providern), der die Roh-Events validiert und in eine Verarbeitungs-Queue stellt.

*   **Einführung von APScheduler:**
    *   Ersetzen des selbstgebauten Polling-Mechanismus im `campaign_scheduler_worker` durch die etablierte Bibliothek `APScheduler`. Dies erhöht die Zuverlässigkeit und ermöglicht komplexere Planungsstrategien.

*   **Code-Bereinigung:**
    *   Entfernung von sämtlichem Legacy-Code, der sich auf `StudioMember` oder `getimpulse` bezieht.
    *   Vereinheitlichung der Konfiguration und der Logging-Praktiken im gesamten Modul.

**Ergebnis:** Ein modernes, robustes und skalierbares Kampagnen-System, das als solide Grundlage für zukünftige Features dient.
