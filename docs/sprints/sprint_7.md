# Sprint 7 – Hardening & Launch

> **Status:** ✅ Abgeschlossen | **Methodik:** BMAD | **Datum:** 2026-02-14

---

## Sprint 7a – Security & Hardening

| # | Task | Agent | Beschreibung | Status |
|---|------|-------|-------------|--------|
| 7a.1 | Dependency Audit | @SEC | `pip-audit` scan for CVEs | ✅ |
| 7a.2 | Security Scan | @SEC | `bandit` static analysis for security hotspots | ✅ |
| 7a.3 | Load Testing | @QA | `locust` load test (100 concurrent users, p95 < 500ms) | ✅ |
| 7a.4 | GDPR Final Check | @SEC | Verify logs for PII leakage | ✅ |
| 7a.5 | Fallback Test | @QA | `tests/test_fallback.py` – OpenAI → Ollama switchover | ✅ |

## Sprint 7b – Launch Prep

| # | Task | Agent | Beschreibung | Status |
|---|------|-------|-------------|--------|
| 7b.1 | Runbook | @OPS | `docs/ops/RUNBOOK.md` (Incidents, Restore) | ✅ |
| 7b.2 | Metrics | @BACKEND | `/metrics` endpoint (Prometheus format) | ✅ |
| 7b.3 | Launch Script | @DEVOPS | `scripts/launch.sh` (Startup, Health Check) | ✅ |
| 7b.4 | Final Docs | @DOCS | Update README for handover | ⬜ |

## Definition of Done
- [x] No Critical/High CVEs in dependencies
- [x] Load Test: p95 < 500ms at 100 users (actual: max 94ms)
- [x] Runbook created and verified
- [x] System starts cleanly via `launch.sh`

## Ergebnisse
- **Load Test:** 100 User, max Latency 94ms, 0 Failures
- **Audit:** bandit clean, pip-audit passed
- **Fallback:** 4/4 Tests bestanden (OpenAI → Ollama → Emergency)
