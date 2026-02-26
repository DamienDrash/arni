# Implementation Notes - Members Page Overhaul

## Design System
- T tokens: bg=#0A0B0F, surface=#12131A, surfaceAlt=#1A1B24, border=#252630, text=#E8E9ED, textMuted=#8B8D9A, textDim=#5A5C6B, accent=#6C5CE7, accentLight=#A29BFE, accentDim=rgba(108,92,231,0.15)
- Card: background T.surface, borderRadius 16, border 1px solid T.border
- SectionHeader: title fontSize 18 fontWeight 700, subtitle fontSize 12 textMuted
- Badge: variants default/success/warning/danger/info/accent
- Modal: backdrop blur, surface bg, borderLight border, 16px borderRadius
- ProgressBar: T.surfaceAlt track, T.accent fill
- Button (CVA): default=#6C5DD3, outline=border-slate-700, ghost=hover:bg-slate-800
- framer-motion available, lucide-react for icons, @tanstack/react-query

## API Endpoints Available
- GET /admin/members - list members
- POST /admin/members - create member
- PUT /admin/members/{id} - update member
- DELETE /admin/members/bulk - bulk delete
- GET /admin/members/columns - custom columns
- POST /admin/members/columns - create custom column
- POST /admin/members/import/csv - CSV import
- GET /admin/members/export/csv - CSV export
- GET /admin/connector-hub/catalog - list all connectors with status
- GET /admin/connector-hub/{id}/config - get connector config
- PUT /admin/connector-hub/{id}/config - update connector config
- POST /admin/connector-hub/{id}/test - test connection
- GET /admin/connector-hub/{id}/setup-docs - get setup docs

## Connector Registry (members category)
- magicline: Magicline (fields: base_url, api_key, studio_id)
- shopify: Shopify (fields: domain, access_token)
- hubspot: HubSpot (fields: access_token) - category crm but relevant

## i18n
- useI18n() -> { t, language, setLanguage }
- t("key") with {{variable}} interpolation
- Locales: en.json, de.json + 10 others
- Members keys at "members.*"

## Architecture
- New page: app/members/page.tsx (overwrite existing)
- Uses inline styles with T tokens (project pattern)
- Uses Card, Badge, Modal, SectionHeader, ProgressBar from @/components/ui
- Uses apiFetch from @/lib/api
- Uses useI18n from @/lib/i18n/LanguageContext
