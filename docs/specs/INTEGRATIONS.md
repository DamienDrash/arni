# API & Protocol Specifications

## 1. Communication Layer
### WhatsApp
- **Production:** Meta Cloud API (Webhooks).
- **Dev/Prototyping:** Baileys (Node.js Sidecar via Redis).
- **Features:** Text, Image, Voice, Native Flows (Forms).

### Telegram
- **Use Case:** Admin Alerts, Logging, "Ghost Mode" Control.
- **Bot API:** Standard polling/webhook.

## 2. Business Logic Layer
### Magicline API
- **Auth:** Bearer Token.
- **Endpoints:**
  - `GET /v1/classes` (Schedule)
  - `POST /v1/booking` (Action)
  - `GET /v1/customers/{id}` (Context)

### Facility (IoT)
- **Protocol:** MQTT / HTTP.
- **Devices:**
  - Shelly Relays (Lights).
  - Nuki Smart Lock (Emergency Entry).

## 3. Physical Intelligence Layer
### Vision (Cameras)
- **Source:** RTSP Stream (`rtsp://user:pass@192.168.1.X:554/stream`).
- **Processing:** Local Python `ultralytics` lib.
- **Privacy:** Images are processed in RAM and dropped immediately.

### Voice (Audio)
- **STT:** `faster-whisper` (Local). Model: `medium`.
- **TTS:** ElevenLabs API (Turbo v2.5). Fallback: Coqui TTS (Local).

## 4. Dev Tools (Self-Improvement)
### ACP (Agent Client Protocol)
- **Transport:** WebSocket / TCP Tunnel.
- **Integration:** VS Code / Zed.
- **Permissions:** Read/Write access to `workspace/skills/` and `config/`.