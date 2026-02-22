# ARIIA P1 Task Tracker: Premium UX & Frontend Accessibility

Dieser Plan zielt darauf ab, die im Frontend Audit definierten P1-Ziele zu erreichen, um "Enterprise Grade" zu festigen.

- [ ] **1. Accessibility (A11y) Baseline herstellen (Sprint B)**
  - [ ] Einheitliche a11y-fähige UI-Primitives (`Button`, `Toggle`, `Dialog`, `Menu`).
  - [ ] Interaktive Elemente ohne konsistente ARIA-/Keyboard-Semantik beheben (u.a. `/live`, `TiptapEditor`, `/settings/general`).
  - [ ] Focus-Management in Overlays (Modals/Dialogs) sicherstellen.
  - [ ] Klickbare Container mit semantischer Button/Link-Rolle versehen.

- [ ] **2. Responsive Hardening (Sprint B)**
  - [ ] Breakpoint-Strategie zentralisieren und in `/knowledge`, `/users`, `/live` härten.
  - [ ] Tabellen mit Mobile-Card-Fallback ausstatten (z.B. in User/Tenant-Liste).
  - [ ] Chat-Layouts mit robustem Height/Scroll-Konzept versehen.

- [ ] **3. Premium Interaktionsmuster etablieren (Sprint B)**
  - [ ] Native Browser-Dialoge (`prompt()`, `confirm()`, `alert()`) im Produktivcode finden (u.a. `/live`, `/escalations`).
  - [ ] Ersetzen dieser durch gebrandete, in React-Komponenten gegossene Dialog- und Confirm-Modals.

- [ ] **4. Design-System & Inline-Style Reduktion (Sprint C)**
  - [ ] Identifizieren und Auslagern von stark genutzten Inline-Styles in zentrale Utility-Klassen / Komponenten-Varianten.
  - [ ] Konsolidierung von wiederverwendbaren Form-/Table-/Modal-Bausteinen.

- [ ] **5. Audit Log & Settings UX (Sprint C - Governance)**
  - [ ] Erweiterung des Audit Logs (`/audit`) zu einer echten Governance-Konsole (Filter, Diff-Ansicht, Drilldown).
  - [ ] Mischen von DE/EN in UI-Labels beheben.
