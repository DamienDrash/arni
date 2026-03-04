
# ARIIA-Kampagnen-System: Tiefenanalyse & Fehlerdiagnose

**Datum:** 2026-03-04
**Autor:** Manus AI

## 1. Zusammenfassung

Diese Analyse dokumentiert die Ergebnisse einer umfassenden Untersuchung des Kampagnen-Moduls der ARIIA-Plattform. Ziel war es, die Ursachen für die gemeldete Dysfunktionalität zu identifizieren und eine Grundlage für die anschließende Reparatur und Optimierung zu schaffen. Die Untersuchung umfasste das Backend (Python, FastAPI), das Frontend (Next.js, TypeScript), die Datenbank-Schemata (SQLAlchemy), die Worker-Infrastruktur (Docker, Redis) und die Server-Logs.

Die Analyse hat **mehrere kritische und schwerwiegende Fehler** aufgedeckt, die in ihrer Gesamtheit die Kampagnen-Funktionalität vollständig lahmlegen. Der schwerwiegendste Fehler ist eine **Endlosschleife im Campaign Scheduler**, die durch einen trivialen Attributfehler verursacht wird und den Versand geplanter Kampagnen verhindert. Weitere Fehler betreffen die Segment-Auflösung, die Integration von E-Mail-Providern, das Analytics-Tracking und die Datenkonsistenz zwischen Frontend und Backend.

Im Folgenden werden die identifizierten Probleme detailliert beschrieben, kategorisiert nach ihrem Schweregrad.

## 2. Kritische Fehler (Systemabsturz & Datenintegrität)

Diese Fehler führen zu Abstürzen von Kernkomponenten oder zu fundamentalen Fehlfunktionen, die das System unbrauchbar machen.

### 2.1. Campaign Scheduler Crash-Loop (Root Cause)

- **Problem:** Der `campaign_scheduler_worker` stürzt in einer Endlosschleife alle 30 Sekunden ab. Dies wurde durch die Analyse der Docker-Logs auf dem Staging-Server (`staging-ariia-campaign-scheduler-1`) bestätigt. Der geloggte Fehler lautet: `error="type object 'Contact' has no attribute 'is_active'"`.
- **Ursache:** Die Funktion `resolve_recipients` im `campaign_scheduler_worker.py` (Zeilen 139 und 158) filtert Kontakte mit der Bedingung `Contact.is_active.is_(True)`. Das `Contact`-Modell in `app/core/contact_models.py` besitzt dieses Attribut jedoch nicht. Es implementiert einen Soft-Delete-Mechanismus über das Feld `deleted_at`. Der korrekte Filter wäre `Contact.deleted_at.is_(None)`.
- **Auswirkung:** **Keine geplanten Kampagnen können versendet werden.** Der Scheduler ist die zentrale Komponente für den asynchronen Versand und Orchestrierung. Sein Ausfall legt die Kernfunktionalität still.

### 2.2. Falscher Aufruf der Segment-Auswertung

- **Problem:** Kampagnen, die auf Segmente abzielen, können keine Empfänger auflösen.
- **Ursache:** Der `campaign_scheduler_worker.py` ruft in Zeile 164 die Methode `repo.evaluate_segment_v2(segment_id, tenant_id)` auf. Die tatsächliche Signatur in `app/contacts/repository.py` lautet jedoch `evaluate_segment_v2(self, db: Session, tenant_id: int, filter_groups: List[Dict], ...)`. Die übergebenen Argumente sind falsch und unvollständig, was zu einem sofortigen Fehler führt.
- **Auswirkung:** **Segment-basiertes Targeting ist vollständig funktionsunfähig.**

### 2.3. Fehlerhafter Import und Aufruf der AdapterRegistry

- **Problem:** Die `dispatch_message`-Funktion im Scheduler, die für den Versand über verschiedene Kanäle (E-Mail, SMS etc.) zuständig ist, würde bei Erreichen abstürzen.
- **Ursache:**
    1.  **Falscher Import:** `AdapterRegistry` wird aus `app.integrations.adapters.base` importiert, befindet sich aber tatsächlich in `app.integrations.adapters.registry`.
    2.  **Falscher Methodenaufruf:** Die Funktion ruft `registry.get_adapter("email", tenant_id=tenant.id)` auf. Die Methode `get_adapter` in der Registry erwartet jedoch nur eine `integration_id` und keinen `tenant_id`.
- **Auswirkung:** Selbst wenn der Scheduler nicht abstürzen würde, **könnte keine einzige Nachricht versendet werden**, da der Code zur Anbindung der E-Mail-Provider (und anderer Kanäle) fehlerhaft ist.

## 3. Schwerwiegende Fehler (Funktionalität nicht gegeben)

Diese Fehler verhindern, dass Kernfunktionen wie vorgesehen funktionieren, auch wenn sie nicht direkt zu einem Systemabsturz führen.

### 3.1. Fehlendes Analytics-Tracking bei Sofortversand

- **Problem:** Bei Kampagnen, die über den "Sofort Senden"-Button im Frontend gestartet werden, findet kein Open- oder Click-Tracking statt.
- **Ursache:** Der API-Endpunkt `POST /campaigns/{campaign_id}/send` in `app/gateway/routers/campaigns.py` verwendet eine veraltete, lokale Rendering-Funktion `_render_campaign_email`. Diese Funktion injiziert weder das Tracking-Pixel noch schreibt sie die Links für das Klick-Tracking um. Die korrekte Logik ist im `MessageRenderer` (`app/campaign_engine/renderer.py`) gekapselt, wird aber von diesem Endpunkt nicht verwendet.
- **Auswirkung:** **Keine Erfolgsmessung (Öffnungen, Klicks) für manuell versendete Kampagnen möglich.** Dies untergräbt den gesamten Zweck von E-Mail-Marketing-Analytics.

### 3.2. Inkonsistente API-Endpunkte für Analytics

- **Problem:** Das Frontend (`frontend/app/campaign-analytics/page.tsx`) versucht, Analytics-Daten von Endpunkten wie `/v2/admin/analytics/overview` und `/v2/admin/analytics/campaigns` abzurufen.
- **Ursache:** Diese Endpunkte existieren nicht unter dem angegebenen Pfad. Die Analyse des Backends hat gezeigt, dass die korrekten Routen in `app/gateway/routers/analytics_api.py` definiert sind, aber möglicherweise unter einem anderen Präfix oder einer anderen Version laufen. Die Routen in `app/gateway/admin.py` deuten auf alte, unversionierte Endpunkte hin.
- **Auswirkung:** **Die gesamte Analytics-Seite im Frontend ist funktionslos**, da sie keine Daten vom Backend empfangen kann.

### 3.3. Fehlender Healthcheck für den E-Mail-Worker

- **Problem:** Der `staging-ariia-email-worker-1` wird auf dem Server als `unhealthy` angezeigt.
- **Ursache:** In der `docker-compose.yml` fehlt für den `ariia-email-worker`-Service jegliche `healthcheck`-Definition. Docker markiert Container ohne Healthcheck, die nicht sofort beenden, oft standardmäßig als `unhealthy`.
- **Auswirkung:** Obwohl der Worker möglicherweise läuft, ist sein Zustand für die Orchestrierung und das Monitoring unklar. Dies erschwert die Fehlerdiagnose und kann zu Problemen im Betrieb führen.

### 3.4. Veraltetes E-Mail-Rendering ohne Templates

- **Problem:** Der `send_campaign`-Endpunkt verwendet eine hartcodierte, veraltete HTML-Struktur zum Generieren von E-Mails und ignoriert das moderne Template-System.
- **Ursache:** Die Funktion `_render_campaign_email` in `campaigns.py` baut das HTML manuell zusammen und nutzt nicht den `MessageRenderer`, der die Logik zur Anwendung von Tenant-spezifischen Templates, Farben und Logos enthält.
- **Auswirkung:** Alle sofort versendeten E-Mails haben ein inkonsistentes und veraltetes Design. Das Branding der Kunden wird nicht korrekt dargestellt.

## 4. Mittelschwere und kleinere Fehler

- **Inkonsistente Kontakt-Filterung:** An mehreren Stellen im Code (`campaigns.py`, `campaign_scheduler_worker.py`) wird versucht, Kontakte basierend auf `is_active` zu filtern, obwohl das Modell dies nicht unterstützt. Dies deutet auf weit verbreitete Inkonsistenzen nach der Migration von `StudioMember` zu `Contact` hin.
- **Fehlende Fehlerbehandlung:** Der `send_campaign`-Endpunkt aktualisiert den Kampagnenstatus auf `sending` und committet dies, bevor der Versandprozess beginnt. Wenn der Prozess fehlschlägt (z.B. wegen fehlender SMTP-Konfiguration), bleibt die Kampagne im Status `sending` hängen und wird nie als `failed` markiert.
- **Legacy-Code:** Es gibt zahlreiche Referenzen auf veraltete Konzepte wie `StudioMember` oder `getimpulse`, die entfernt werden sollten, um die Codebasis zu bereinigen.
- **Fehlende A/B-Test-Implementierung:** Das Frontend bietet eine detaillierte UI zur Konfiguration von A/B-Tests (`ABTestConfig.tsx`), aber die zugehörige Backend-Logik im `campaign_scheduler_worker` und `analytics_processor` scheint unvollständig oder nicht korrekt implementiert zu sein.

## 5. Fazit & Nächste Schritte

Die Kampagnen-Funktionalität ist aufgrund einer Kaskade von Fehlern, die von kritischen Abstürzen bis hin zu Design- und Dateninkonsistenzen reichen, vollständig außer Betrieb. Die Probleme sind tief in der Codebasis verwurzelt und deuten auf eine unvollständige oder fehlerhafte Migration und Refaktorierung in der Vergangenheit hin.

Die Behebung erfordert einen strukturierten Ansatz, der bei den kritischsten Fehlern beginnt, um das System wieder lauffähig zu machen, und sich dann den schwerwiegenden Funktionsfehlern widmet. Die nächste Phase des Projekts wird sich auf die Erstellung einer detaillierten Roadmap zur Behebung dieser Probleme konzentrieren.
