# Frontend Tiefenanalyse (High-End Premium SaaS)

**Datum:** 2026-02-20  
**Scope:** `frontend/` inkl. App-Routen, Komponenten, UI-Primitives, API-Proxy-Schicht, Auth-Handling, UX/Accessibility/Performance/Security.  
**Zielbild:** High-End Premium SaaS (Enterprise-tauglich, skalierbar, konsistent, sicher, barrierearm).

## 1. Executive Summary

- **Reifegrad aktuell:** ca. **6/10**
- **Stärken:**
  - Gute Grundstruktur mit Sidebar-IA und klarer Domänenabgrenzung.
  - Viele zentrale Verwaltungsbereiche bereits vorhanden (`/users`, `/tenants`, `/plans`, `/settings/*`, `/audit`, `/members`, `/live`).
  - Einheitliche Farbtoken-Basis in `frontend/lib/tokens.ts`.
- **Hauptdefizite:**
  - Teilweise Mock-/Pseudo-Daten in produktionskritischen Views.
  - Session-Sicherheit nicht auf Gold-Standard (Token in `localStorage`).
  - Accessibility- und Keyboard-Semantik lückenhaft.
  - Hohe Inline-Style-Last (Wartbarkeit/Konsistenz).
  - Responsive-Verhalten in mehreren Kernscreens nicht robust genug.

---

## 2. Kritische Findings (P0)

## 2.1 Mock-Daten in Kern-Dashboards
**Impact:** Hoch (Vertrauensverlust, KPI-Integrität)  
**Belege:**
- `frontend/lib/mock-data.ts`
- `frontend/components/pages/DashboardPage.tsx`
- `frontend/components/pages/AnalyticsPage.tsx`

**Problembild:**
- Produktive KPI-Ansichten greifen teilweise auf Mockdaten zurück, inkl. `Math.random()`-basierter Werte.
- Für Enterprise SaaS ist dies fachlich und reputationsseitig nicht tragbar.

**Maßnahme:**
- Komplett auf reale Endpunkte umstellen.
- Mock-Layer ausschließlich in Storybook/Dev-Sandbox halten.
- KPI-Metadaten anzeigen (Zeitfenster, Last update, Quelle).

## 2.2 Session/Auth nicht Gold-Standard
**Impact:** Hoch (Security/Compliance)  
**Belege:**
- `frontend/lib/auth.ts`
- `frontend/lib/api.ts`

**Problembild:**
- Access Token im `localStorage` (XSS-anfällig).
- 401-Handling mit Hard-Redirect nicht basePath-safe.

**Maßnahme:**
- Umstellung auf HttpOnly/Secure/SameSite-Cookies.
- CSRF-Schutz für mutierende Requests.
- Redirects basePath-sicher (`withBasePath("/login")`).

## 2.3 Realtime-Architektur im Live Monitor inkonsistent
**Impact:** Hoch (Betriebsstabilität/Kosten/UX)  
**Belege:**
- `frontend/app/live/page.tsx`

**Problembild:**
- Gemisch aus Polling (2s/3s) + optionalem WS.
- Hohe Last, potenzielle Inkonsistenzen bei schneller Laständerung.

**Maßnahme:**
- WS/SSE-first Architektur mit Heartbeat + Backoff-Reconnect.
- Polling nur als expliziter Fallback.

---

## 3. Wichtige Findings (P1)

## 3.1 Accessibility-Lücken (WCAG)
**Impact:** Mittel-Hoch (Enterprise-Anforderungen, Compliance)  
**Belege (Auszug):**
- `frontend/app/live/page.tsx`
- `frontend/components/TiptapEditor.tsx`
- `frontend/app/settings/general/page.tsx`

**Problembild:**
- Interaktive Elemente ohne konsistente ARIA-/Keyboard-Semantik.
- Toggle-Komponenten ohne klare Accessibility-Attribute.
- Klickbare Container teilweise ohne semantische Button/Link-Rolle.

**Maßnahme:**
- Einheitliche a11y-fähige UI-Primitives (`Button`, `Toggle`, `Dialog`, `Menu`).
- Focus-Management in Overlays.
- WCAG AA als Standard.

## 3.2 Responsiveness an mehreren Stellen fragil
**Impact:** Mittel-Hoch (Desktop small, Tablet, mobile landscape)  
**Belege (Auszug):**
- `frontend/app/knowledge/page.tsx`
- `frontend/app/users/page.tsx`
- `frontend/app/live/page.tsx`

**Problembild:**
- Feste Grid-Spalten und Höhen führen in engen Viewports zu suboptimalem Verhalten.

**Maßnahme:**
- Breakpoint-Strategie zentralisieren.
- Tabellen mit Mobile-Card-Fallback.
- Chat-Layouts mit robustem Height/Scroll-Konzept.

## 3.3 Hoher Inline-Style-Anteil
**Impact:** Mittel (Wartbarkeit, Konsistenz, Skalierung)  
**Befund:**
- Sehr hoher Anteil inline definierter Styles in App/Components.

**Problembild:**
- Design-Änderungen erfordern viele manuelle Eingriffe.
- Inkonsistenzrisiko steigt mit jeder neuen Seite.

**Maßnahme:**
- Design-System konsolidieren (Tokens + Komponentenvarianten + Utility Patterns).
- Wiederverwendbare Form-/Table-/Modal-Bausteine.

## 3.4 Nicht-premium Interaktionsmuster
**Impact:** Mittel  
**Belege:**
- `frontend/app/live/page.tsx`
- `frontend/components/pages/EscalationsPage.tsx`

**Problembild:**
- Nutzung von `prompt()`, `confirm()`, `alert()` wirkt technisch/provisorisch.

**Maßnahme:**
- Produktive Dialog-/Confirm-/Toast-Komponenten mit konsistentem Branding.

## 3.5 Legacy-/Doppelstrukturen
**Impact:** Mittel (Komplexität/Fehlerfläche)  
**Belege:**
- `frontend/components/pages/SettingsOverviewPage.tsx` (alt/parallel)
- Mehrere Admin-Proxy-Routen:
  - `frontend/app/api/admin/[...path]/route.ts`
  - `frontend/app/proxy/admin/[...path]/route.ts`
  - `frontend/app/internal/admin/[...path]/route.ts`

**Maßnahme:**
- Zielarchitektur definieren, redundante Wege reduzieren.
- Alte/ungenutzte Seiten konsolidieren.

---

## 4. Weitere Findings (P2)

1. **Mischsprache DE/EN** in UI-Labels und Statusmeldungen reduziert Professionalität.
2. **Global Error Screen** nicht im Produkt-Designsystem:
   - `frontend/app/global-error.tsx`
3. **Settings UX** noch ohne vollständige Operator-Guidance:
   - Feldvalidierung, Testresultate pro Integration, Änderungsdiff, Audit-Kontext.
4. **Audit Log UX** roh und ohne Premium-Funktionen:
   - fehlende facettierte Filter, Diff-Ansicht, Export, Drilldown.

---

## 5. Empfohlene Zielarchitektur (High-End Premium)

## 5.1 UI/Design-System
- Einheitliche Primitive für:
  - Buttons, Inputs, Toggles, Badges, Tables, Modals, Toasts.
- Semantische Tokens:
  - `surfaceElevated`, `focusRing`, `dangerSurface`, `successText`, etc.
- Konsequent komponierbare Layout-Bausteine pro Seitentyp (Table, Form, Split, Chat).

## 5.2 Data Layer
- React Query/SWR für API-State:
  - Caching, retry policy, stale-time, optimistic updates.
- Einheitliches Error/Loading/Empty-State Pattern.
- Realtime-Stream abstrahieren (`useLiveSessions` Hook + fallback).

## 5.3 Security
- Session in HttpOnly-Cookies.
- CSRF-Strategie.
- Striktes handling von 401/403 ohne harte Pfadannahmen.
- Kein Secret-Handling im Browserzustand über das notwendige Maß hinaus.

## 5.4 Accessibility
- WCAG AA als Definition of Done.
- Keyboard-first Navigierbarkeit.
- ARIA Live Regions für dynamische Statusmeldungen (z. B. Live Monitor).

---

## 6. Priorisierte Umsetzung (Roadmap)

## Sprint A (P0) – Stabilität, Wahrheit, Sicherheit
1. Dashboard/Analytics auf reale APIs umstellen; Mockdaten aus Produktpfad entfernen.
2. Auth-Session von `localStorage` auf Cookie-basiert migrieren.
3. 401-Redirects basePath-sicher machen.
4. Live Monitor Realtime-Pfad konsolidieren (WS/SSE-first).

## Sprint B (P1) – Premium UX + A11y
1. `prompt/confirm/alert` durch gebrandete Dialoge ersetzen.
2. Accessibility-Baseline über alle interaktiven Kernelemente herstellen.
3. Responsive Hardening für `live`, `knowledge`, `users`, `tenants`, `plans`.

## Sprint C (P1/P2) – Skalierung und Governance
1. Inline-Style-Abbau in ein konsistentes Designsystem.
2. Audit Log zu Governance-Konsole ausbauen (Filter, Diff, Export).
3. Settings-Operator-Experience erweitern (Validierung, Testläufe, Änderungsjournal).
4. Legacy-Komponenten und redundante Proxy-Wege bereinigen.

---

## 7. Abnahmekriterien (Qualitäts-Gates)

1. **No Mock in Product KPI Views** (automatischer CI-Check auf `mock-data`-Imports in produktiven Seiten).
2. **Security Gate:** kein Access-Token in `localStorage`.
3. **A11y Gate:** Keyboard-Flow + Focus + ARIA auf Kernseiten bestanden.
4. **Performance Gate:** messbare Reduktion unnötiger Polling-Requests.
5. **UX Gate:** keine nativen `alert/prompt/confirm` in produktiven Flows.

---

## 8. Fazit

Das Frontend ist funktional stark gewachsen und deckt viele betriebliche Bereiche ab. Für eine **High-End Premium SaaS** fehlen jedoch noch zentrale Qualitätsmerkmale in den Bereichen **Datenvertrauen, Security, Accessibility, Konsistenz und Skalierbarkeit**. Mit der oben priorisierten Roadmap kann das Niveau in 2–3 fokussierten Sprints substanziell angehoben werden.
