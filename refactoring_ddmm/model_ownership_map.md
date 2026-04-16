# Epic 7 — Model Ownership Map

## Ziel
`app/core/models.py` ist aktuell ein Sammelmodul fuer fachlich unterschiedliche Aggregate. Vor dem physischen Aufteilen der Modelle wird hier die kuenftige Ownership eindeutig festgezogen, damit `7.2` und `7.3` entlang stabiler Domain-Grenzen erfolgen.

## Zielstruktur

### Tenant / Identity
- `Tenant`
- `UserAccount`
- `PendingInvitation`
- `RefreshToken`
- `UserSession`
- `AuditLog`

Zielmodul:
- `app/domains/identity/models.py`

Begruendung:
- Tenant-, User-, Session- und Einladungskern gehoeren fachlich zusammen.
- `AuditLog` bleibt hier, weil Actor-/Tenant-/Admin-Governance daran haengt und nicht primär Billing oder Campaigns owned.

### Support / CRM / Contacts
- `StudioMember`
- `MemberCustomColumn`
- `MemberImportLog`
- `MemberSegment`
- `ScheduledFollowUp`
- `MemberFeedback`
- `ContactConsent`
- `ChatSession`
- `ChatMessage`

Zielmodule:
- `app/domains/support/models.py`
- optional spaeter: `app/domains/support/chat_models.py`

Begruendung:
- Diese Modelle bilden zusammen den operativen Support-/CRM-Kern.
- Chat, Member, Feedback, Segmente und Follow-ups sind fachlich enger an Support gebunden als an Campaigns oder Knowledge.

### Billing / Entitlements / AI-Costs
- `Plan`
- `AddonDefinition`
- `TenantAddon`
- `Subscription`
- `UsageRecord`
- `TokenPurchase`
- `ImageCreditPack`
- `ImageCreditBalance`
- `ImageCreditTransaction`
- `ImageCreditPurchase`
- `LLMModelCost`
- `LLMUsageLog`

Zielmodule:
- `app/domains/billing/models.py`
- optional spaeter: `app/domains/billing/ai_billing_models.py`

Begruendung:
- Plan-, Add-on-, Subscription- und Usage-Ownership ist bereits in Epic 6 stark in den Billing-Slice verlagert.
- AI-Cost- und Credit-Modelle sind fachlich eher monetarisierte Entitlements als generische AI-Konfiguration.

### Campaigns
- `Campaign`
- `CampaignTemplate`
- `CampaignVariant`
- `CampaignRecipient`
- `CampaignOffer`

Zielmodul:
- `app/domains/campaigns/models.py`

Begruendung:
- Opt-in-, Offer-, Template- und Recipient-Flows bilden einen zusammenhaengenden Kampagnenkern.

### Knowledge / Ingestion
- `IngestionJob`
- `IngestionJobStatus`

Zielmodul:
- `app/domains/knowledge/models.py`

Begruendung:
- Das ist der explizite Wissensbasis-/Ingestion-Kern mit bereits eigenem Runtime-Slice.

### AI / Swarm Configuration
- `ToolDefinition`
- `AgentDefinition`
- `TenantAgentConfig`
- `TenantToolConfig`
- `TenantLLMConfig`

Zielmodul:
- `app/domains/ai/models.py`

Begruendung:
- Diese Modelle bilden den Agent-/Tool-/Tenant-AI-Konfigurationskern.
- Sie sind nicht Support-owned, obwohl Support diese Agenten nutzt.

### Platform / Settings
- `Setting`
- `TenantConfig`

Zielmodul:
- `app/domains/platform/models.py`

Begruendung:
- Beide Modelle sind technische Plattform-/Konfigurationscontainer und keine Fachaggregate einer einzelnen Produktdomäne.

## Phasenreihenfolge fuer 7.2
1. Tenant / Identity
2. Billing
3. Campaigns
4. Support / CRM / Contacts
5. Knowledge
6. AI / Swarm Configuration
7. Platform / Settings

## Guardrails fuer 7.2 und 7.3
- Keine Schemaaenderungen, nur Code-Verschiebung und Import-Neuzuordnung.
- `app/core/models.py` wird zuerst zu einem re-export Shim reduziert, nicht sofort geloescht.
- Cross-Domain-Reads werden nicht ueber Fremdmodellimporte legitimiert, sondern schrittweise ueber Query-/Repository-Services gezogen.
- Jede Domain-Verschiebung braucht einen fokussierten Import-/Migrationstest oder einen bestehenden Regression-Gate.

## Erste Cross-Domain-Hotspots fuer 7.3
- Support -> Billing:
  `Subscription`, `Plan`, `UsageRecord`
- Campaigns -> Support:
  `StudioMember`, `MemberSegment`
- AI / Swarm -> Identity:
  `Tenant`, `UserAccount`
- Admin / Platform -> nahezu alle Domains:
  bleibt vorerst ueber Services/Repositories zentralisiert, nicht ueber neue Direktimporte
