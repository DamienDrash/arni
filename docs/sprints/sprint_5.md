# Sprint 5 – Physical Intelligence

> **Status:** 🟡 Aktiv | **Methodik:** BMAD | **Start:** 2026-02-14

---

## Sprint 5a – Vision (Woche 9–10)

| # | Task | Agent | Beschreibung | Status |
|---|------|-------|-------------|--------|
| 5a.1 | YOLOv8 Processor | @BACKEND | Person detection pipeline (`app/vision/processor.py`) | ⬜ |
| 5a.2 | RTSP Connector | @BACKEND | Snapshot grabber for CCTV (`app/vision/rtsp.py`) | ⬜ |
| 5a.3 | Privacy Engine | @SEC | RAM-only processing, 0s Retention (`app/vision/privacy.py`) | ⬜ |
| 5a.4 | Agent Vision Upgrade | @BACKEND | Wire Vision Agent → live processor | ⬜ |
| 5a.5 | Vision Tests | @QA | Pytest with mock frames | ⬜ |
| 5a.6 | Vision Privacy Audit | @SEC | 0s retention audit report | ⬜ |

## Sprint 5b – Voice (Woche 11–12)

| # | Task | Agent | Beschreibung | Status |
|---|------|-------|-------------|--------|
| 5b.1 | Whisper STT | @BACKEND | Speech-to-text pipeline (`app/voice/stt.py`) | ⬜ |
| 5b.2 | Audio Ingress | @BACKEND | Voice msg download + conversion (`app/voice/ingress.py`) | ⬜ |
| 5b.3 | ElevenLabs TTS | @BACKEND | Text-to-speech integration (`app/voice/tts.py`) | ⬜ |
| 5b.4 | Voice Pipeline | @BACKEND | E2E: Voice In → STT → Swarm → TTS → Voice Out (`app/voice/pipeline.py`) | ⬜ |
| 5b.5 | Voice Tests | @QA | Pytest with audio fixtures | ⬜ |
| 5b.6 | README + Docs | @DOCS | Physical Intelligence documentation | ⬜ |

## Definition of Done
- [ ] YOLOv8 processor returns `{count, density}` from frames
- [ ] RTSP connector can grab snapshots (stubbed for VPS)
- [ ] 0s retention enforced: no images on disk, logs, or DB
- [ ] STT transcribes audio → text
- [ ] TTS converts text → audio response
- [ ] End-to-end voice pipeline completes in <8s target
- [ ] Tests: ≥80% coverage on vision + voice
- [ ] Privacy audit report created
