# Sprint 14 – Enterprise Premium (Gold Standard)

> **Ziel:** Transformation von "Funktional" zu "Enterprise Grade" durch Observability, Evals und Hardened Security.
> **Zeitraum:** Woche 28–29
> **Status:** 🔴 Planned

---

## 🎯 Sprint Ziele
1. **Transparenz:** Jede Entscheidung des Bots ist trace-bar (Warum hat er das getan?).
2. **Qualität:** Änderungen am Prompt/Code werden automatisch gegen Golden Dataset getestet.
3. **Sicherheit:** Ein deterministischer Layer verhindert, dass der Bot "ausbricht".

---

## 📝 User Stories

### US-14.1: X-Ray Vision (Observability)
**Assignee:** @BACKEND, @DEVOPS  
**Als** Developer  
**möchte ich** jeden Thought-Process und Tool-Call in einem Dashboard sehen,  
**damit** ich halluzinationen und logische Fehler sofort debuggen kann.

**Tasks:**
- [ ] Integration von **LangFuse** (Self-Hosted oder Cloud) in `PromptEngine`.
- [ ] Tracing aller `OpsAgent` Schritte (System Prompt, Tool Call, Response).
- [ ] User-Feedback (Daumen hoch/runter) mit Trace verknüpfen.

**Acceptance Criteria:**
- [ ] Dashboard zeigt Latency, Token-Kosten und Trace-Tree für jede Request.
- [ ] Fehlerhafte Tool-Calls sind rot markiert.

---

### US-14.2: CI/CD für Intelligenz (Evaluation)
**Assignee:** @QA, @AI  
**Als** PO  
**möchte ich**, dass bei jedem Update automatisch geprüft wird, ob der Bot dümmer geworden ist,  
**damit** wir keine Regressionen bei den Business Rules (`SKILL.md`) haben.

**Tasks:**
- [ ] Setup **DeepEval** oder **Ragas**.
- [ ] Erstellung "Golden Dataset" aus 50 echten, anonymisierten Chats.
- [ ] GitHub Action: Führt Evals bei PR aus.

**Acceptance Criteria:**
- [ ] Pipeline failt, wenn "Answer Relevancy" < 0.8.
- [ ] Pipeline failt, wenn "Faithfulness" (keine Halluzination) < 0.9.

---

### US-14.3: The Iron Dome (Guardrails)
**Assignee:** @SEC, @AI  
**Als** CISO  
**möchte ich** eine deterministische Firewall vor und nach dem LLM,  
**damit** Jailbreaks, PII-Leaks und Competitor-Erwähnungen technisch unmöglich sind.

**Tasks:**
- [ ] Implementation **Nemo Guardrails** (NVIDIA) oder **Lakera**.
- [ ] Definition `risk.yml`: Blockiere "Ignore previous instructions", "Wie baue ich eine Bombe".
- [ ] Output-Filter: Maskiere Muster wie IBAN/Kreditkarte *nochmal* hart.

**Acceptance Criteria:**
- [ ] Test-Script mit 100 bekannten Jailbreaks wird zu 100% blockiert.
- [ ] Antwortzeit penalty < 200ms.

---

### US-14.4: Hybrid Search Engine
**Assignee:** @AI, @BACKEND  
**Als** User  
**möchte ich**, dass der Bot "Protein Riegel Schoko" exakt findet,  
**damit** ich nicht frustriert bin, wenn er "Schokoriegel" nicht kennt.

**Tasks:**
- [ ] Upgrade RAG: **ChromaDB** -> **Qdrant** oder **Weaviate** (Hybrid Support).
- [ ] Integration **BM25** (Keyword) + **Dense Vector** (Semantic).
- [ ] Reranking Step (z.B. Cohere Rerank) für Top-Resultate.

**Acceptance Criteria:**
- [ ] Suche nach exakten Produkt-SKUs liefert das korrekte Produkt auf Platz 1.
- [ ] Fuzzy-Suche ("Dings für Muskeln") funktioniert weiterhin.

---

## 📅 Timeline & Kapazität

| Rolle | Kapazität | Fokus |
|-------|-----------|-------|
| @BACKEND | 100% | LangFuse & Hybrid Search Backend |
| @AI | 100% | Evals & Reranking Logic |
| @DEVOPS | 50% | Self-Hosting LangFuse / Qdrant |
| @SEC | 50% | Guardrails Config & Red Teaming |
| @QA | 100% | Golden Dataset Creation |

---

## Premium Enterprise Check ✅

| Feature | Status | Notes |
| :--- | :--- | :--- |
| **Observability** | ✅ **Done** | LangFuse Integration + BaseAgent Tracing |
| **Evaluations** | ✅ **Done** | DeepEval Pipeline + Golden Dataset (50 items) |
| **Guardrails** | ✅ **Done** | The Iron Dome (P0 Prompt Injection Block) |
| **Search** | ✅ **Done** | Hybrid Search (RRF) for Product Precision |
| **High Availability** | 🚧 **Pending** | Load Balancing (Sprint 15) |

## Sprint Result
**Status:** ✅ SUCCEEDED
**Velocity:** HIGH (All P0/P1 items delivered)
**Next:** Sprint 15: Deployment & Scale (Kubernetes/Cloud Run)
| **RBAC / Audit Log** | Sprint 13 (Admin) | ✅ Done |
| **SLA / Uptime** | Sprint 7 (Load Test)| ✅ Done |

> **Conclusion:** With Sprint 14, ARNI achieves "Enterprise Grade Level 3" (Autonomous & Observable).
