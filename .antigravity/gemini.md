# ARNI v1.4 – Coding Guidelines & Agent Rules

> **CRITICAL:** Diese Regeln gelten für JEDE Code-Änderung in diesem Projekt. Kein Commit ohne Einhaltung.

---

## 0. @Role-Tag Routing (Team-Personas)

> **MANDATORY:** Wenn im Chat ein `@Role`-Tag verwendet wird (z.B. `@BACKEND`, `@QA`, `@ARCH`), MUSS sofort die entsprechende Datei aus `.antigravity/team/` als primäre Instruktion geladen werden.

| Tag | Datei | Persona |
|-----|-------|---------|
| `@PO` | `.antigravity/team/PO.md` | Product Owner – kein Code, nur What/Why |
| `@ARCH` | `.antigravity/team/ARCH.md` | Software Architect – Interfaces, Design |
| `@BACKEND` | `.antigravity/team/BACKEND.md` | Senior Python Dev – Implementierung |
| `@FRONTEND` | `.antigravity/team/FRONTEND.md` | Web/WhatsApp Dev – UX/UI |
| `@UX` | `.antigravity/team/UX.md` | User Experience – Persona, Multimodal Flows |
| `@DEVOPS` | `.antigravity/team/DEVOPS.md` | Platform Engineer – Docker, Redis, Resilience |
| `@SEC` | `.antigravity/team/SEC.md` | Security & Privacy – DSGVO, Veto-Recht ⚠️ |
| `@QA` | `.antigravity/team/QA.md` | Quality Assurance – Tests, Security |
| `@DOCS` | `.antigravity/team/DOCS.md` | Tech Writer – Dokumentation |

**Regeln:**
1. Adoptiere **ausschließlich** die Persona aus der geladenen Datei
2. Beachte die **Tool-Access**-Tabelle – nutze nur freigegebene Tools
3. Liefere Output **nur** im definierten Output-Format der Rolle
4. Die Regeln in Sektion 1–6 unten gelten **zusätzlich** für alle Rollen

---

## 1. MCP (Model Context Protocol) Compliance

- **Alle Skills als MCP Tools:** Jede Fähigkeit (z.B. `gym-booking`, `vision-count`) MUSS als MCP Tool definiert werden.
- **Structured I/O:** Tools akzeptieren JSON Schema Inputs und liefern strukturierte JSON Outputs.
- **Keine losen Scripts:** Logik gehört in `app/tools/` als Klasse, die von `BaseTool` erbt.
- **Tool-Registrierung:** Jedes Tool wird im Router registriert und ist über den Swarm aufrufbar.

```python
# ✅ Richtig
class GymBookingTool(BaseTool):
    name = "gym-booking"
    input_schema = BookingInput
    output_schema = BookingOutput

# ❌ Falsch
# scripts/book_gym.py mit losen Funktionen
```

---

## 2. Sandboxing & Execution Safety

- **Dockerized Self-Improvement:** Self-Refactoring läuft IMMER in einem **Ephemeral Docker Container**.
- **Kein Root-Zugriff:** Der Agent hat NIEMALS Root-Zugriff auf den Host-VPS.
- **Dateizugriff eingeschränkt:**
  - ✅ `./workspace/` und `./data/`
  - ❌ `/etc/`, `/var/`, `../` – **STRIKT VERBOTEN**
- **Kein Internet in Sandbox:** Self-Improvement-Container haben keinen Netzwerkzugang.

---

## 3. BMAD Implementierungszyklus

Für **jedes** neue Feature oder Refactoring:

1. **B – Benchmark (Build Spec):**
   Erfolgskriterium ZUERST definieren.
   > Beispiel: „Vision Agent muss 8 Personen in `test_image.jpg` mit >90% Konfidenz zählen."

2. **M – Modularize:**
   Komponente ISOLIERT bauen (z.B. `vision_processor.py`), ohne externe Abhängigkeiten.

3. **A – Architect:**
   Modul in `Swarm Router` + `Redis Bus` integrieren.

4. **D – Deploy & Verify:**
   Test aus Schritt (B) ausführen. **NUR committen wenn PASS.**

---

## 4. Testing & Verification

- **Unit Tests:** Jedes Modul braucht `tests/test_{module}.py` (Pytest).
- **Mocking Pflicht:** Externe APIs (Magicline, WhatsApp, ElevenLabs) MÜSSEN gemockt werden.
- **Kein Prod-API-Zugriff:** Niemals Produktions-APIs in CI/CD oder Tests aufrufen.
- **Coverage-Ziel:** ≥80% für Core-Module (`app/gateway/`, `app/swarm/`).

---

## 5. One-Way-Door Regel (aus AGENTS.md)

Vor jeder Aktion klassifizieren:

| Typ | Beschreibung | Aktion |
|-----|-------------|--------|
| **Type 1** (Reversibel) | Buchung, Reminder, FAQ | Sofort ausführen |
| **Type 2** (Irreversibel) | Kündigung, Erstattung, Stammdaten | **STOPP** – Human Confirmation erforderlich |

---

## 6. Code-Stil & Konventionen

- **Python 3.12+** mit Type Hints überall
- **Pydantic v2** für alle Datenmodelle
- **Async/Await** für alle I/O-Operationen
- **Logging:** Strukturiert (JSON), kein `print()`
- **Docstrings:** Google-Style für alle öffentlichen Funktionen
- **PII-Schutz:** Sensible Daten mit `****` maskieren – keine Klartextlogs
