# Integration Hub Bug Analysis

## Bug 1: Schnellfilter funktionieren nicht korrekt
- Die Kategorie-Tabs (Schnellfilter) filtern korrekt nach `activeCategory`
- ABER: Es fehlt ein "Quick Filter" für Plan-Status (z.B. "Verfügbar", "Gesperrt", "Verbunden")
- Die Kategorie-Labels sind nur auf Englisch, nicht i18n

## Bug 2: Professional Plan Integrationen sind deaktiviert
- **ROOT CAUSE GEFUNDEN**: Professional Plan hat slug `"pro"` in der DB (Zeile 419 in feature_gates.py)
- Frontend `isPlanSufficient()` vergleicht `plan.slug` mit `PLAN_ORDER` Map
- `PLAN_ORDER` hat Keys: `starter`, `professional`, `business`, `enterprise`
- DB hat slug `"pro"` für Professional Plan
- `"pro"` ist NICHT in `PLAN_ORDER` → `currentOrder = -1` → IMMER false!
- **FIX**: Entweder slug in DB auf "professional" ändern ODER PLAN_ORDER um "pro" erweitern

## Bug 3: Feature "platform_integrations" existiert nicht
- Integrationen wie Stripe, Calendly etc. haben `featureKey: "platform_integrations"`
- `feature("platform_integrations")` prüft `data.plan.features["platform_integrations"]`
- `_build_features_dict()` hat KEINEN Key "platform_integrations"
- Daher ist `feature("platform_integrations")` IMMER false
- `isIntegrationAccessible()` prüft: `planOk && (featureOk || addonOk)`
- Wenn featureKey gesetzt ist und feature() false zurückgibt → Integration ist gesperrt
- **FIX**: Entweder "platform_integrations" als Feature hinzufügen ODER featureKey entfernen/ändern

## Bug 4: Connector max_connectors nicht geprüft
- Professional Plan hat `max_connectors: 1`
- Aber es gibt keine Prüfung ob das Limit erreicht ist

## Zusammenfassung der Fixes:
1. PLAN_ORDER um "pro" erweitern (Frontend)
2. "platform_integrations" Feature hinzufügen ODER featureKey-Logik anpassen
3. Schnellfilter für Plan-Status hinzufügen
4. Kategorie-Labels i18n-fähig machen
