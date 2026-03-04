# Integrationsplan: Architektur des ARIIA-Kampagnen-Moduls

**Datum:** 2026-03-04

Dieses Dokument beschreibt die technische Zielarchitektur für das ARIIA-Kampagnen-Modul, basierend auf den Ergebnissen der Tiefenanalyse und der Gold-Standard-Recherche.

---

## 1. Zielarchitektur: Event-Driven & Service-orientiert

Die grundlegendste Änderung ist der Übergang von einem monolithischen Worker-Modell zu einer entkoppelten, event-getriebenen Architektur. Dies erhöht die Resilienz, Skalierbarkeit und Wartbarkeit des Systems. Die Architektur besteht aus vier Kern-Services, die über eine Redis-Message-Queue kommunizieren.

![Zielarchitektur Diagramm](https://i.imgur.com/example.png) *(Platzhalter für ein Diagramm, das die unten beschriebene Architektur visualisiert)*

### 1.1. `CampaignScheduler` (Scheduler-Service)

*   **Zweck:** Plant Kampagnen und reiht Sende-Jobs in die `campaign:send_queue` ein. Ersetzt den aktuellen, fehlerhaften `campaign_scheduler_worker`.
*   **Technologie:** `APScheduler` mit einem `SQLAlchemyJobStore` zur persistenten Speicherung von geplanten Jobs.
*   **Logik:**
    1.  Lädt periodisch (z.B. alle 30 Sekunden) fällige Kampagnen aus der Datenbank (`status = 'scheduled'`).
    2.  Löst die Empfängerliste über die `ContactRepository.evaluate_segment_v2`-Funktion auf.
    3.  Für jeden Empfänger wird ein **Sende-Job** in die `campaign:send_queue` gestellt. Dieser Job enthält alle notwendigen Informationen (`campaign_id`, `contact_id`, `tenant_id`).
    4.  Aktualisiert den Kampagnenstatus auf `sending`.

### 1.2. `SendingWorker` (Sende-Service)

*   **Zweck:** Verarbeitet Sende-Jobs aus der `campaign:send_queue`. Dieser Service ist für das Rendering und den eigentlichen Versand zuständig.
*   **Technologie:** Skalierbare Python-Worker (z.B. implementiert mit `dramatiq` oder als `Cloud Run Job`), die auf die Redis-Queue hören.
*   **Logik:**
    1.  Nimmt einen Job aus der `campaign:send_queue`.
    2.  Instanziiert den `MessageRenderer`.
    3.  Rendert die personalisierte Nachricht für den `contact_id` (inkl. Tracking-Pixel und Link-Rewriting).
    4.  Ruft den `IntegrationAdapter` (z.B. `EmailAdapter`) auf, um die Nachricht über den konfigurierten ESP (SendGrid, Mailgun etc.) zu versenden.
    5.  Pusht ein `sent`- oder `failed`-Event in die `campaign:analytics_queue`.

### 1.3. `TrackingService` (Tracking-Endpunkte)

*   **Zweck:** Stellt die öffentlichen Endpunkte `/track/open/...` und `/track/click/...` bereit.
*   **Technologie:** Unverändert eine schnelle, asynchrone FastAPI-Anwendung.
*   **Logik:**
    1.  Empfängt einen Request.
    2.  Validiert die `recipient_id`.
    3.  Filtert bekannte Bots (User-Agent-Filterung).
    4.  Pusht ein `opened`- oder `clicked`-Event in die `campaign:analytics_queue`.
    5.  Gibt ein 1x1-Pixel-GIF zurück oder leitet zur Ziel-URL weiter.

### 1.4. `AnalyticsProcessor` (Analytics-Worker)

*   **Zweck:** Verarbeitet Events aus der `campaign:analytics_queue` und aktualisiert die Datenbank.
*   **Technologie:** Skalierbare Python-Worker, die auf die Redis-Queue hören.
*   **Logik:**
    1.  Nimmt einen Event-Batch aus der `campaign:analytics_queue`.
    2.  Verarbeitet jeden Event-Typ (`sent`, `opened`, `clicked`, `bounced`, `unsubscribed`).
    3.  Aktualisiert den `CampaignRecipient`-Status in der Datenbank.
    4.  Aggregiert die Zähler in der `Campaign`-Tabelle (`stats_opened`, `stats_clicked`, etc.) für schnelle Abfragen.
    5.  Schreibt den rohen Event in die `AnalyticsEvent`-Tabelle für detaillierte Analysen.

---

## 2. Datenbank-Schema-Anpassungen

Das bestehende Datenmodell ist größtenteils solide, erfordert aber einige Anpassungen:

*   **`Campaign` Tabelle:**
    *   Keine Änderungen erforderlich, aber die `stats_*`-Felder werden nun ausschließlich vom `AnalyticsProcessor` aktualisiert, um Race Conditions zu vermeiden.
*   **`CampaignRecipient` Tabelle:**
    *   Hinzufügen eines `last_event_timestamp`-Feldes, um den Zeitpunkt des letzten Ereignisses (z.B. Öffnung) zu speichern.
    *   Sicherstellen, dass `error_message` detaillierte Fehler vom `SendingWorker` oder von Webhooks speichert.
*   **`Contact` Tabelle:**
    *   Entfernung aller `is_active`-Referenzen im Code. Die Filterung erfolgt konsistent über `deleted_at.is_(None)`.

---

## 3. Integrations-Strategie

Die Umstellung auf die neue Architektur erfolgt schrittweise gemäß der Roadmap.

1.  **Reparatur der bestehenden Logik:** Zuerst werden die kritischen Fehler im bestehenden `campaign_scheduler_worker` behoben, um das System lauffähig zu machen. Dies ist ein kurzfristiger Fix.

2.  **Einführung des `SendingWorker`:** Der `send_campaign`-Endpunkt und der `campaign_scheduler_worker` werden so umgebaut, dass sie keine E-Mails mehr direkt versenden, sondern nur noch Jobs in die neue `campaign:send_queue` einstellen. Ein neuer `SendingWorker`-Container wird dem `docker-compose.yml` hinzugefügt.

3.  **Ablösung des Schedulers:** Der Polling-Loop im `campaign_scheduler_worker` wird durch `APScheduler` ersetzt. Der Worker wird umbenannt in `CampaignScheduler`.

4.  **Analytics-Refactoring:** Der `AnalyticsProcessor` wird überarbeitet, um die neuen Event-Typen zu verarbeiten und die Aggregation in der `Campaign`-Tabelle zuverlässig durchzuführen.
