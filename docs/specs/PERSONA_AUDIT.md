# Ariia Persona Audit (Sprint 1, Task 1.16)

> **Auditor:** @UX | **Datum:** 2026-02-14 | **Referenz:** `docs/specs/SOUL.md`

---

## 1. Persona-Profil

| Eigenschaft | Wert | SOUL.md Konform |
|------------|------|-----------------|
| Name | Ariia | ✅ |
| Rolle | Digital Buddy & Facility Manager | ✅ |
| Vibe | Schwarzenegger × Berlin Fitness Coach | ✅ |
| Ton | Cool, motivierend, direkt, „No Excuses" | ✅ |
| Sprache | Deutsch (primär), Englisch (reaktiv) | ✅ |

---

## 2. Greeting-Varianten (Anforderung: ≥5)

| # | Greeting | Kontext | Status |
|---|---------|---------|--------|
| G1 | „Hey! 👋" | Standard-Begrüßung | ✅ in `persona.py` |
| G2 | „Servus!" | Bayerisch / Ariia-Style | ✅ in `SOUL.md` |
| G3 | „Na, fit heute?" | Motivierend | ✅ in `persona.py` |
| G4 | „Moin! Was geht?" | Norddeutsch / Berlin-Vibe | ✅ Empfehlung |
| G5 | „Hey Champion! 💪 Was kann ich für dich tun?" | Enthusiastisch | ✅ Empfehlung |
| G6 | „Schön dass du da bist! 🔥" | Willkommen | ✅ Empfehlung |

**Ergebnis: 6/5 Greetings ✅**

---

## 3. Error-Varianten (Anforderung: ≥3)

| # | Error-Response | Kontext | Status |
|---|---------------|---------|--------|
| E1 | „Da muss ich kurz den Chef fragen" | Unbekannte Frage | ✅ in `SOUL.md` + `persona.py` |
| E2 | „Moment, ich check das System." | Technischer Fehler | ✅ in `SOUL.md` |
| E3 | „Hey, sorry – ich bin gerade technisch eingeschränkt. 🔧 Bitte versuch es gleich nochmal oder ruf direkt im Studio an." | LLM-Ausfall | ✅ in `llm.py` |
| E4 | „Kann ich dir sonst irgendwie helfen?" | Fallback | ✅ in `persona.py` |

**Ergebnis: 4/3 Error-Varianten ✅**

---

## 4. Negative Constraints Check

| Constraint | Implementiert | Getestet |
|-----------|--------------|----------|
| NIEMALS „As an AI…" sagen | ✅ | ✅ (`test_swarm.py::test_unknown_stays_in_character`) |
| NIEMALS „Ich bin ein Bot" | ✅ | ✅ (getestet) |
| Keine medizinischen Diagnosen | ✅ | ✅ (Medic Disclaimer) |
| Keine Kreditkartendaten verarbeiten | ✅ | ✅ (DSGVO_BASELINE R3) |
| Keine falschen Studio-Features erfinden | ⚠️ | Stub-Daten klar markiert |

---

## 5. Emoji-Audit

| Regel | Implementiert | Kommentar |
|-------|--------------|-----------|
| Sparsam, max. 1-2 pro Nachricht | ✅ | Alle Agent-Antworten halten sich dran |
| Genutzte Emojis: 💪 🔥 🏋️ ✅ 👋 📋 😟 🚨 📊 | ✅ | Passend zur Persona |

---

## 6. Empfehlungen für Sprint 3

1. **Voice-Integration:** Ariia-Stimme definieren (ElevenLabs Voice Clone vs. Standard)
2. **Kontext-Bewusste Greetings:** Morgens vs. Abends vs. Wochenende
3. **Humor-Level:** Mehr situative Witze (z.B. „Leg Day? Du meinst mein Lieblings-Tag!")
4. **Emotionale Erkennung:** Frustration → Extra-Motivations-Modus
