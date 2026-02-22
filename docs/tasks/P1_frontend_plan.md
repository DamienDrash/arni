# ARIIA P1 Implementation Plan: UX, A11y & Skalierung

Dieser Plan adressiert die P1-Prioritäten aus dem Frontend Deep Audit (Sprint B / C) für das Premium Enterprise Zielbild. Das übergeordnete Ziel ist eine deutliche Steigerung der Zugänglichkeit, eine Beseitigung von Provisorien (z.B. system-native Dialogs) und eine Stabilisierung auf mobilen Endgeräten.

## User Review Required

> [!IMPORTANT]
> - Gibt es eine bevorzugte Komponenten-Bibliothek für A11y UI-Primitives (z.B. Radix UI, Headless UI, React Aria), die wir nutzen sollen, oder sollen wir die bestehenden Tailwind-Komponenten von Grund auf ARIA-konform ausbauen?
> - Sollen wir das globale Audit Log UI als Tabellen-Ansicht belassen und nur Filter/Diffs ergänzen oder zu einer Karten-zentrierten Timeline-View umbauen?

## Proposed Changes

---

### UI Primitives & Accessibility (Sprint B)

Alle grundlegenden interaktiven UI-Elemente erhalten eine Keyboard-/Focus-Governance.

### [NEW] `frontend/components/ui/Dialog.tsx`
Wir implementieren eine saubere, ARIA-konforme Modal-Lösung, die den Fokus einsperrt und via ESC zu schließen ist.

### [NEW] `frontend/components/ui/ConfirmModal.tsx`
Ein Hook/Component-Konstrukt zum Austausch aller nativen `window.confirm()` und `window.prompt()` Aufrufe.

### [MODIFY] `frontend/components/TiptapEditor.tsx`
Sicherstellung relevanter Tab-Indizes, ARIA-Label und High-Contrast Anpassungen für die Toolbar im Knowledge- / Prompt-Editor.

---

### Responsive Hardening & Layouts (Sprint B)

Bisher statisch / brüchig umgesetzte Layouts (Table Grids, Chat) werden robuster auf Flexbox / Mobile-First Container umgestellt.

### [MODIFY] `frontend/app/users/page.tsx` und `frontend/app/tenants/page.tsx`
Einbau von Mobile-Card Fallbacks, falls der Viewport zu klein für die Datentabellen wird.

### [MODIFY] `frontend/app/live/page.tsx`
- Die `LiveSessionChat` Container erhalten flex-basiertes Scroll-Verhalten (Height=100%, shrink).
- Austausch nativer Alerts bei Eskalationen durch den neuen `ConfirmModal`.

---

### Governance Konsole / Audit Log (Sprint C)

### [MODIFY] `frontend/app/audit/page.tsx`
Erweitern der simplen Listenansicht um:
- **Filter-Sidebar:** Filtern nach Actor, Target, Date Range, Action-Type.
- **Diff-View:** Wenn in den Metadaten Änderungen an Objekten vorhanden sind, werden diese als Before/After JSON-Diff oder visualisierter Change-Summary gerendert.

### [MODIFY] `frontend/app/settings/general/page.tsx`
- Beseitigung von Inline-Styles hin zu globalen `form-group` Utilities.
- Sprachliche Mischungen (DE/EN) bereinigen.

---

## Verification Plan

### Automated Tests
1. **Linting Check:** `npx eslint` über die gesamte Frontend Codebase, um Aushöhlung von `eslint-plugin-jsx-a11y` Regeln festzustellen.
2. **Type Check:** `npx tsc --noEmit` für alle neuen Types (Modal Props etc.).

### Manual Verification
1. Lade `live`, `settings`, `users` ohne Maus (nur mit Tabulator + Enter) bedienen. Es muss jederzeit klar ersichtlich sein, worauf der Fokus liegt.
2. Responsiver Test (Browser DevTools auf Mobile-Viewport) im `live` Monitor und der `users` Tabelle.
3. Klick auf potenziell destruktive Aktionen (Löschen, Eskalation übernehmen) triggert das neue Premium-Branded Modal, nicht den nativen Windows/Mac Standard.
