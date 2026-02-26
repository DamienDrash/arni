# Live Test Notes - 2026-02-26

## Pricing Page Status
Der doppelte Professional Plan (ID 7, slug "professional") wurde in der DB deaktiviert. Allerdings zeigt die Seite jetzt noch einen doppelten Enterprise-Eintrag. Der Markdown-Extrakt zeigt: nach den 4 Hauptplänen gibt es noch "Enterprise - Maßgeschneiderte Lösungen für große Studioketten...". Das kommt wahrscheinlich aus dem PricingClient.tsx, das ein separates Enterprise-CTA-Element rendert, das nicht aus der API kommt, sondern hardcoded ist.

## Nächste Schritte
Ich muss prüfen ob das Enterprise-Duplikat aus dem Frontend-Code stammt (hardcoded CTA) und es ggf. entfernen oder nur anzeigen wenn kein Enterprise-Plan aus der API kommt.
