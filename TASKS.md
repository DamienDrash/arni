# Tasks: Sanierung des ARIIA-Kampagnen-Moduls

Dieses Dokument listet die konkreten, priorisierten Aufgaben zur Behebung der Fehler und zur Implementierung der neuen Architektur auf. Jede Aufgabe sollte in einem separaten Git-Commit umgesetzt werden.

---

## Prio 1: Kritische Fehler (Systemstabilisierung)

**Ziel:** Den Totalausfall des Systems beheben.

-   **[x] TASK-001: Fix `Contact.is_active` im Campaign Scheduler**
    -   **Beschreibung:** Ersetze alle Vorkommen von `Contact.is_active.is_(True)` im `scripts/campaign_scheduler_worker.py` durch `Contact.deleted_at.is_(None)`.
    -   **Akzeptanzkriterien:** Der `campaign_scheduler_worker` stürzt nicht mehr mit dem Fehler `AttributeError: 'Contact' object has no attribute 'is_active'` ab. Die Server-Logs zeigen keine wiederholten Abstürze mehr.

-   **[x] TASK-002: Fix `evaluate_segment_v2` Aufruf im Scheduler**
    -   **Beschreibung:** Korrigiere den Aufruf von `evaluate_segment_v2` in `scripts/campaign_scheduler_worker.py`, um die korrekten Argumente (`db`, `tenant_id`, `filter_groups`) zu übergeben. Die `segment_id` muss zuerst aus der DB geladen werden, um an die `filter_groups` zu gelangen.
    -   **Akzeptanzkriterien:** Kampagnen, die auf Segmente abzielen, können ihre Empfängerliste korrekt auflösen.

-   **[x] TASK-003: Fix `AdapterRegistry` Import und Aufruf**
    -   **Beschreibung:** Ändere den Import in `scripts/campaign_scheduler_worker.py` von `app.integrations.adapters.base` auf `app.integrations.adapters.registry`. Passe den Aufruf von `get_adapter` an, sodass er ohne `tenant_id` erfolgt.
    -   **Akzeptanzkriterien:** Die `dispatch_message`-Funktion kann einen E-Mail-Adapter erfolgreich laden und prinzipiell für den Versand verwenden.

-   **[x] TASK-004: Refactor `send_campaign` Endpoint zur Nutzung des `MessageRenderer`**
    -   **Beschreibung:** Baue den `POST /campaigns/{campaign_id}/send` Endpunkt in `app/gateway/routers/campaigns.py` um. Entferne die lokale `_render_campaign_email`-Funktion und verwende stattdessen den zentralen `MessageRenderer` (`app/campaign_engine/renderer.py`), um den E-Mail-Body zu erstellen. Stelle sicher, dass `inject_tracking_pixel` und `rewrite_links` aufgerufen werden.
    -   **Akzeptanzkriterien:** Manuell versendete E-Mails enthalten einen Tracking-Pixel und umgeschriebene Links. Das E-Mail-Design entspricht den im Tenant konfigurierten Templates.

---

## Prio 2: Hohe Priorität (Kernfunktionalität wiederherstellen)

**Ziel:** Die für den Benutzer sichtbaren Kernfunktionen wieder nutzbar machen.

-   **[x] TASK-005: Fix Analytics API Endpoints & Frontend-Anbindung** *(bereits korrekt implementiert, Router registriert)*
    -   **Beschreibung:** Stelle sicher, dass die vom Frontend (`CampaignAnalyticsPage`) aufgerufenen Endpunkte (`/v2/admin/analytics/...`) im Backend korrekt implementiert sind und die erwarteten Daten liefern. Passe bei Bedarf die Pfade im Frontend oder Backend an.
    -   **Akzeptanzkriterien:** Die Kampagnen-Analytics-Seite im Frontend lädt und zeigt Daten (auch wenn diese anfangs noch unvollständig sind).

-   **[x] TASK-006: Implementiere einen robusten `AnalyticsProcessor`** *(bereits korrekt implementiert)*
    -   **Beschreibung:** Überarbeite den `analytics_processing_worker.py`. Stelle sicher, dass er alle Event-Typen (`sent`, `opened`, `clicked`, `bounced`, `unsubscribed`) aus der Redis-Queue korrekt verarbeitet. Implementiere die Logik zur Aggregation der `stats_*`-Zähler in der `Campaign`-Tabelle.
    -   **Akzeptanzkriterien:** Eingehende Tracking-Events führen zu korrekten Updates in den `CampaignRecipient`- und `Campaign`-Tabellen. Die Analytics-Seite zeigt korrekte Zahlen für alle Metriken.

-   **[x] TASK-007: Vollständige Implementierung der A/B-Test-Logik**
    -   **Beschreibung:** Implementiere die Backend-Logik für A/B-Tests. Der `CampaignScheduler` muss die Varianten an eine Teilgruppe der Empfänger senden. Ein neuer Worker oder ein geplanter Job muss nach Ablauf der Testdauer die Ergebnisse auswerten (`open_rate` oder `click_rate`) und die Gewinner-Variante an die restlichen Empfänger senden.
    -   **Akzeptanzkriterien:** Ein konfigurierter A/B-Test wird korrekt ausgeführt, der Gewinner wird ermittelt und der Rest der Kampagne wird wie erwartet versendet.

-   **[x] TASK-008: Füge Healthcheck zum `email-worker` hinzu**
    -   **Beschreibung:** Füge eine `healthcheck`-Definition zum `ariia-email-worker`-Service in der `docker-compose.yml` hinzu. Der Healthcheck sollte prüfen, ob der Worker-Prozess läuft und eine Verbindung zu Redis herstellen kann.
    -   **Akzeptanzkriterien:** Der `staging-ariia-email-worker-1` wird auf dem Server als `healthy` angezeigt.

---

## Prio 3: Mittlere Priorität (Architektur-Upgrade)

**Ziel:** Die technische Grundlage für zukünftige Entwicklungen schaffen.

-   **[ ] TASK-009: Architektur-Refactoring: `SendingWorker` einführen**
    -   **Beschreibung:** Erstelle einen neuen `SendingWorker`, der Sende-Jobs aus einer `campaign:send_queue` liest. Modifiziere den `CampaignScheduler` und den `send_campaign`-Endpunkt, sodass sie nur noch Jobs in diese Queue einreihen, anstatt direkt zu senden.
    -   **Akzeptanzkriterien:** Der E-Mail-Versand erfolgt asynchron über den neuen Worker. Das System ist resilienter gegenüber Fehlern beim Versand.

-   **[ ] TASK-010: Ersetze manuelles Scheduling durch `APScheduler`**
    -   **Beschreibung:** Integriere `APScheduler` in den `CampaignScheduler`, um den manuellen Polling-Loop zu ersetzen. Konfiguriere einen `SQLAlchemyJobStore` für Persistenz.
    -   **Akzeptanzkriterien:** Geplante Kampagnen werden zuverlässig zur exakten, geplanten Zeit ausgelöst. Der Scheduler-Code ist einfacher und robuster.

-   **[ ] TASK-011: Code-Bereinigung: Legacy-Referenzen entfernen**
    -   **Beschreibung:** Durchsuche die gesamte Codebasis nach veralteten Referenzen wie `StudioMember`, `getimpulse`, `member_id` (wo `contact_id` verwendet werden sollte) und entferne bzw. ersetze sie.
    -   **Akzeptanzkriterien:** Die Codebasis ist sauber und frei von Altlasten.
