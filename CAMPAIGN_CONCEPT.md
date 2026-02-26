# ARIIA Campaign & Schedule System – Konzeption

## 1. Datenbank-Modelle

### Campaign (Kampagne)
- id, tenant_id, name, description
- type: "broadcast" | "scheduled" | "follow_up" | "drip"
- status: "draft" | "ai_generating" | "pending_review" | "approved" | "scheduled" | "sending" | "sent" | "failed" | "cancelled"
- channel: "email" | "whatsapp" | "telegram" | "sms" | "multi"
- target_type: "all_members" | "segment" | "selected" | "tags"
- target_filter_json: JSON (Segment-Filter, Tag-Filter, Member-IDs)
- template_id: FK → CampaignTemplate (optional)
- content_subject, content_body, content_html
- ai_prompt: Text (was der Tenant dem KI-Agent vorgibt)
- ai_generated_content: Text (was der KI-Agent generiert hat)
- preview_token: String (UUID für temporäre Preview-Seite)
- preview_expires_at: DateTime
- scheduled_at: DateTime (wann soll gesendet werden)
- sent_at: DateTime
- created_by: FK → User
- stats_sent, stats_delivered, stats_opened, stats_clicked, stats_failed: Integer
- created_at, updated_at

### CampaignTemplate (Vorlage)
- id, tenant_id, name, description
- type: "email" | "whatsapp" | "sms"
- header_html, footer_html, body_template
- variables_json: JSON (verfügbare Platzhalter)
- thumbnail_url
- is_default, is_active
- created_at, updated_at

### ScheduledFollowUp (Chat-basiertes Scheduling)
- id, tenant_id, member_id
- conversation_id (Referenz zum Chat)
- reason: Text (z.B. "Pause - Rückkehr nach 2 Wochen")
- follow_up_at: DateTime
- message_template: Text
- channel: "whatsapp" | "telegram" | "email" | "sms"
- status: "pending" | "sent" | "cancelled" | "failed"
- ai_context_json: JSON (Kontext aus dem Chat für den Follow-up)
- created_at, sent_at

### CampaignRecipient (Empfänger-Tracking)
- id, campaign_id, member_id
- status: "pending" | "sent" | "delivered" | "opened" | "clicked" | "failed" | "bounced"
- sent_at, delivered_at, opened_at, clicked_at
- error_message

## 2. Enterprise-Features (zusätzlich)

### A/B Testing
- Campaigns können Varianten haben (A/B)
- CampaignVariant: campaign_id, variant_name ("A", "B"), content_subject, content_body, percentage (50/50)
- Automatische Auswertung nach X Stunden → Gewinner an Rest senden

### Segmentierung
- MemberSegment: id, tenant_id, name, description, filter_json, is_dynamic
- Dynamische Segmente: Filter werden bei Kampagnen-Versand neu evaluiert
- Statische Segmente: Feste Member-Listen

### Drip Campaigns (Automatisierte Sequenzen)
- DripSequence: id, tenant_id, name, trigger_event
- DripStep: sequence_id, step_order, delay_hours, content_subject, content_body, channel

### Campaign Analytics
- Öffnungsraten, Klickraten, Bounce-Raten
- Heatmap für beste Versandzeiten
- Vergleich zwischen Kampagnen

## 3. KI-Agent Integration

### Campaign Agent (Neuer Worker im Swarm)
- Wird vom Lead Agent delegiert
- Kann auf Chat-Historie und Wissensspeicher zugreifen
- Generiert personalisierte Inhalte basierend auf:
  - Tenant-Vorgabe (Prompt)
  - Member-Daten (Name, Interessen, letzte Interaktion)
  - Wissensspeicher (FAQ, Produkte, Angebote)
  - Chat-Historie (Kontext der letzten Gespräche)

### Workflow:
1. Tenant gibt Kampagnen-Ziel vor (z.B. "Reaktivierung inaktiver Mitglieder")
2. KI-Agent generiert Content
3. Preview wird auf temporärer Seite bereitgestellt (UUID-Link)
4. Tenant prüft, gibt Feedback oder genehmigt
5. Bei Genehmigung → Kampagne wird geplant/gesendet

## 4. Plan-Zuordnung

| Feature | Starter | Professional | Business | Enterprise |
|---------|---------|-------------|----------|------------|
| Broadcasts | 1/Monat | 10/Monat | Unlimited | Unlimited |
| Templates | 2 | 10 | Unlimited | Unlimited |
| AI Content | - | Basic | Advanced | Advanced+Context |
| Segmente | - | 3 | 10 | Unlimited |
| A/B Testing | - | - | ✓ | ✓ |
| Drip Campaigns | - | - | - | ✓ |
| Follow-ups | 5/Monat | 50/Monat | Unlimited | Unlimited |
| Analytics | Basic | Standard | Advanced | Enterprise |
