# ARIIA – RBAC & Feature-Gating System

> Enterprise-Grade Berechtigungs- und Feature-Gating-System für rollenbasierte Zugriffskontrolle und plan-basierte Feature-Verfügbarkeit.

## 1. Architektur-Übersicht

Das System besteht aus drei Schichten:

| Schicht | Komponente | Funktion |
|:---|:---|:---|
| **Backend** | `feature_gates.py` | Plan-Daten laden, Feature/Channel-Checks, Usage-Tracking, Permission-Builder |
| **Backend** | `GET /admin/permissions` | Liefert die vollständige Permission-Map an das Frontend |
| **Frontend** | `usePermissions()` Hook | Cached Permissions, bietet `feature()`, `canPage()`, `isRole()` etc. |
| **Frontend** | `<FeatureGate>`, `<RoleGate>`, `<PageGuard>` | Deklarative Komponenten für Feature/Rollen-Gating |
| **Frontend** | `NavShell.tsx` | Zentrale Seiten-Guard-Logik mit Feature-Blocking |
| **Frontend** | `Sidebar.tsx` | Rollenbasierte Navigation mit Plan-Badges und Upgrade-CTAs |
| **Frontend** | `SettingsSubnav.tsx` | Feature-gated Settings-Tabs |

## 2. Rollen

| Rolle | Beschreibung | Scope |
|:---|:---|:---|
| **system_admin** | Plattform-Betreiber (ARIIA-Team) | Alle Tenants, System-Konfiguration, keine Tenant-Features |
| **tenant_admin** | Studio-Inhaber / Manager | Eigener Tenant, alle Features im gebuchten Plan |
| **tenant_user** | Mitarbeiter / Agent | Eigener Tenant, nur operative Features (Live, Escalations, Analytics) |

## 3. Plan-Feature-Matrix

| Feature | Starter (Free) | Pro (99€/mo) | Enterprise |
|:---|:---|:---|:---|
| **Kanäle** | | | |
| WhatsApp | ✓ | ✓ | ✓ |
| Telegram | ✗ | ✓ | ✓ |
| SMS | ✗ | ✓ | ✓ |
| E-Mail-Kanal | ✗ | ✓ | ✓ |
| Instagram DM | ✗ | ✓ | ✓ |
| Facebook Messenger | ✗ | ✓ | ✓ |
| Voice / Telefonie | ✗ | ✗ | ✓ |
| Google Business Messages | ✗ | ✗ | ✓ |
| **Features** | | | |
| Member Memory Analyzer | ✗ | ✓ | ✓ |
| Custom Prompts | ✗ | ✓ | ✓ |
| Advanced Analytics | ✗ | ✓ | ✓ |
| Custom Branding | ✗ | ✓ | ✓ |
| Audit Log | ✗ | ✓ | ✓ |
| API-Zugang | ✗ | ✓ | ✓ |
| Multi-Source Members | ✗ | ✓ | ✓ |
| Automation | ✗ | ✗ | ✓ |
| **Limits** | | | |
| Mitglieder | 500 | Unbegrenzt | Unbegrenzt |
| Nachrichten/Monat | 1.000 | Unbegrenzt | Unbegrenzt |
| Kanäle (max.) | 1 | 4 | 10 |

## 4. Seiten-Zugriffs-Matrix

### System Admin

| Seite | Zugriff | Feature-Gate |
|:---|:---|:---|
| /dashboard | ✓ | – |
| /tenants | ✓ | – |
| /plans | ✓ | – |
| /system-prompt | ✓ | – |
| /users | ✓ | – |
| /audit | ✓ | – |
| /settings/general | ✓ | – |
| /settings/ai | ✓ | – |
| /settings/account | ✓ | – |

### Tenant Admin

| Seite | Zugriff | Feature-Gate |
|:---|:---|:---|
| /dashboard | ✓ | – |
| /live | ✓ | – |
| /escalations | ✓ | – |
| /analytics | ✓ | – |
| /members | ✓ | – |
| /member-memory | ✓ | `memory_analyzer` |
| /knowledge | ✓ | – |
| /magicline | ✓ | – |
| /users | ✓ | – |
| /audit | ✓ | `audit_log` |
| /settings/integrations | ✓ | – |
| /settings/prompts | ✓ | `custom_prompts` |
| /settings/billing | ✓ | – |
| /settings/branding | ✓ | `branding` |
| /settings/automation | ✓ | `automation` |
| /settings/account | ✓ | – |

### Tenant User (Agent)

| Seite | Zugriff | Feature-Gate |
|:---|:---|:---|
| /dashboard | ✓ | – |
| /live | ✓ | – |
| /escalations | ✓ | – |
| /analytics | ✓ | – |
| /settings/account | ✓ | – |
| Alle anderen Seiten | ✗ | – |

## 5. Backend-Implementierung

### Permission-Endpoint

```
GET /admin/permissions
```

Liefert:
```json
{
  "role": "tenant_admin",
  "plan": {
    "slug": "pro",
    "name": "Pro",
    "price_monthly_cents": 9900,
    "features": {
      "whatsapp": true,
      "telegram": true,
      "sms": true,
      "email_channel": true,
      "voice": false,
      "instagram": true,
      "facebook": true,
      "google_business": false,
      "memory_analyzer": true,
      "custom_prompts": true,
      "advanced_analytics": true,
      "branding": true,
      "audit_log": true,
      "automation": false,
      "api_access": true,
      "multi_source_members": true
    },
    "limits": {
      "max_members": null,
      "max_monthly_messages": null,
      "max_channels": 4
    }
  },
  "subscription": {
    "has_subscription": true,
    "status": "active",
    "current_period_end": "2026-03-24T00:00:00",
    "trial_ends_at": null
  },
  "usage": {
    "messages_used": 4521,
    "messages_inbound": 2100,
    "messages_outbound": 2421,
    "members_count": 312,
    "llm_tokens_used": 1250000
  },
  "pages": {
    "/dashboard": true,
    "/live": true,
    "/member-memory": true,
    "/audit": true,
    "/settings/automation": false,
    ...
  }
}
```

### Feature Gate (Backend-Enforcement)

```python
from app.core.feature_gates import FeatureGate

gate = FeatureGate(tenant_id=7)
gate.require_channel("telegram")       # HTTP 402 wenn nicht im Plan
gate.require_feature("memory_analyzer") # HTTP 402 wenn nicht im Plan
gate.check_message_limit()             # HTTP 429 wenn Limit erreicht
gate.check_member_limit()              # HTTP 402 wenn Limit erreicht
```

## 6. Frontend-Implementierung

### usePermissions() Hook

```tsx
import { usePermissions } from "@/lib/permissions";

function MyComponent() {
  const {
    role,                    // "system_admin" | "tenant_admin" | "tenant_user"
    isSystemAdmin,           // boolean
    isTenantAdmin,           // boolean
    isTenantUser,            // boolean
    feature,                 // (key: string) => boolean
    canPage,                 // (path: string) => boolean
    plan,                    // { slug, name, features, limits }
    usage,                   // { messages_used, members_count, ... }
    subscription,            // { has_subscription, status, ... }
    isNearLimit,             // (resource) => boolean (>80%)
    isAtLimit,               // (resource) => boolean (>=100%)
    requiredPlanFor,         // (feature) => "Pro" | "Enterprise"
    loading,                 // boolean
    reload,                  // () => void
  } = usePermissions();

  if (feature("memory_analyzer")) {
    // Show memory analyzer features
  }
}
```

### FeatureGate Komponente

```tsx
import { FeatureGate } from "@/components/FeatureGate";

// Full page gate with upgrade prompt
<FeatureGate feature="memory_analyzer">
  <MemberMemoryContent />
</FeatureGate>

// Inline badge for locked features
<FeatureGate feature="voice" inline>
  <VoiceSettings />
</FeatureGate>
```

### RoleGate Komponente

```tsx
import { RoleGate } from "@/components/FeatureGate";

<RoleGate roles={["system_admin", "tenant_admin"]}>
  <AdminOnlyContent />
</RoleGate>
```

### UsageBanner Komponente

```tsx
import { UsageBanner } from "@/components/FeatureGate";

// Shows warning when near limit, error when at limit
<UsageBanner resource="messages" />
<UsageBanner resource="members" />
```

## 7. UI-Verhalten

### Sidebar
- **system_admin**: Sieht Platform Governance + System & Core Sektionen
- **tenant_admin**: Sieht Operations + Kunden & Team + Knowledge + Studio Sektionen
- **tenant_user**: Sieht nur Operations (Dashboard, Live, Escalations, Analytics) + Account
- Feature-gated Items (z.B. Member Memory, Automation) werden mit Crown-Badge angezeigt und leiten zum Billing weiter
- Plan-Indikator zeigt aktuellen Plan und Nachrichten-Verbrauch
- Upgrade-CTA für Starter-Plan-Nutzer

### Settings-Navigation
- Tabs werden rollenbasiert gefiltert
- Feature-gated Tabs (Prompts, Branding, Automation) zeigen Crown-Badge und leiten zum Billing weiter

### Feature-Blocked Seiten
- NavShell erkennt automatisch ob die aktuelle Seite ein Feature benötigt
- Zeigt statt des Inhalts einen Premium-Upgrade-Prompt mit:
  - Feature-Beschreibung und Vorteile
  - Benötigter Plan (Pro oder Enterprise)
  - Direkter Link zur Billing-Seite

## 8. Datenbank-Änderungen

### Neue Spalten in `plans`-Tabelle

| Spalte | Typ | Default |
|:---|:---|:---|
| `instagram_enabled` | Boolean | false |
| `facebook_enabled` | Boolean | false |
| `google_business_enabled` | Boolean | false |
| `advanced_analytics_enabled` | Boolean | false |
| `branding_enabled` | Boolean | false |
| `audit_log_enabled` | Boolean | false |
| `automation_enabled` | Boolean | false |
| `api_access_enabled` | Boolean | false |
| `multi_source_members_enabled` | Boolean | false |

### Migration

```bash
docker compose exec ariia-core alembic upgrade head
```

## 9. Caching

- Frontend cached Permissions für 5 Minuten in `sessionStorage`
- Cache wird automatisch geleert bei:
  - Login/Logout
  - Session-Update (Impersonation)
  - Manueller Reload via `usePermissions().reload()`
- Event `ariia:session-updated` triggert Cache-Refresh
