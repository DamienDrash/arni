# Sprint 11 – Voice & Scale (P2)

> **Fokus:** Voice-First Experience & Deep CRM Integration.
> **Zeitraum:** Woche 26+

---

## 🎯 Ziele
1.  **Voice Interaction:** WhatsApp Sprachnachrichten verstehen & beantworten (Whisper + ElevenLabs).
2.  **Retention AI:** Sales Agent erkennt kündigungsgefährdete Mitglieder via CRM-Metriken.
3.  **Scaling:** Redis Queue Optimierung für 50+ parallele User.

---

## 📋 Backlog

### US-11.1: Voice Ingress (STT) @ARCH
**Als** Mitglied
**möchte ich** eine Sprachnachricht senden (via Telegram),
**damit** ich nicht tippen muss.

**Tasks:**
- [ ] `faster-whisper` Service in `app/voice/stt.py`
- [ ] Telegram Voice Download (`.ogg` -> `.wav` Konvertierung)
- [ ] Integration in Swarm Router (Audio -> Text -> Agent)

### US-11.2: Voice Egress (TTS) @ARCH
**Als** ARIIA
**möchte ich** mit meiner Stimme antworten,
**damit** die Interaktion persönlicher wirkt.

**Tasks:**
- [ ] TTS: Kokoro-82M (Local Inference, `espeak-ng` required)
- [ ] Caching für häufige Sätze (Begrüßung, Standard-Antworten)
- [ ] Versand als Telegram Voice Note (File Upload)

### US-11.3: CRM Retention Engine @BACKEND
**Als** Sales Agent
**möchte ich** wissen, wie oft das Mitglied trainiert,
**damit** ich bei Kündigung passende Gegenangebote machen kann (z.B. Pause statt Kündigung bei inaktiven Nutzern).

**Tasks:**
- [ ] `get_checkin_stats(90_days)` Metrik
- [ ] Logic: "If 0 visits in 30 days -> Offer Pause"
- [ ] Logic: "If active > 2x/week -> Offer Premium Upgrade"

### US-11.4: Scaling & Performance @DEVOPS
**Als** System
**möchte ich** 50 parallele Requests verarbeiten,
**damit** der Launch sicher ist.

**Tasks:**
- [ ] Redis Queue für Voice-Processing (Async Worker)
- [ ] Load Test mit 50 Users (Locust)

---

## 👥 Team Assignments

- **@ARCH:** Voice Pipeline Design (STT/TTS Latency < 3s)
- **@BACKEND:** CRM Logic & Redis Queue
- **@DEVOPS:** Load Testing & Docker Setup for Whisper (GPU support?)
