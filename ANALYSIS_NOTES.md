# ARIIA Live-System Analyse

## Identifizierte Probleme

### 1. Doppelter Professional Plan
- Es gibt zwei Professional Plans: slug "pro" (ohne Stripe-Link) und slug "professional" (mit Stripe-Link prod_U2dL2e2W88oNMs)
- Der "pro" Plan hat PRODUCT: Not Linked, PRICE: Not Linked
- Der "professional" Plan hat PRODUCT: prod_U2dL2e2W88oNMs, PRICE: price_1T4Y4UEmo0m7USTcDUlOQUhC
- Problem: seed_plans() erstellt slug="pro", aber Stripe-Sync hat slug="professional" erstellt
- Lösung: billing_sync muss bestehende Pläne matchen statt neue zu erstellen

### 2. Stripe-Sync Probleme
- Der Sync scheint Duplikate zu erzeugen statt bestehende Pläne zu aktualisieren
- Enterprise hat PRICE: Not Linked
- Pro hat weder PRODUCT noch PRICE verlinkt

### 3. Fehlende Features
- Keine Analytics-Seite für System Admin (Umsatz, Token-Kosten)
- Keine LLM-Provider-Verwaltung für Tenants (nur für System Admin)
- Kein Token-Management/Usage-Tracking für Tenants
- Keine Progressbar für Token-Verbrauch bei Tenants
- Keine Option "mehr Token kaufen"
- Keine Blockierung bei aufgebrauchten Tokens

### 4. Sidebar Navigation
- System Admin hat keinen Analytics-Link
- Kein dedizierter "Revenue Analytics" Bereich

## Plan der Änderungen

### Backend
1. billing_sync.py - Duplikat-Problem fixen (slug-matching)
2. Neuer Router: revenue_analytics.py - Umsatz-Analytics für System Admin
3. Neuer Router: tenant_llm.py - LLM-Provider-Verwaltung für Tenants
4. Token-Tracking in feature_gates.py erweitern
5. Migration für LLM-Provider-Tabellen und Token-Tracking

### Frontend
1. Plans-Seite: Duplikate fixen, besseres UI
2. Neue Analytics-Seite für System Admin (Revenue, Token-Kosten)
3. LLM-Provider-Seite für Tenants
4. Token-Usage-Dashboard für Tenants
5. Sidebar-Navigation erweitern
