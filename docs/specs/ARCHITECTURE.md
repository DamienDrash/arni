# ARNI v1.4 System Architecture

## 1. High-Level Philosophy
Arni is an autonomous, local-first system agent for "GetImpulse Berlin".
Unlike traditional chatbots, Arni is a "Living System" that:
1.  **Observes** (Vision/Sensors)
2.  **Reasons** (Swarm Intelligence)
3.  **Acts** (API/IoT/Voice)
4.  **Improves** (Self-Refactoring via ACP)

## 2. Core Components

### A. Hybrid Gateway (The Kernel)
- **Technology:** FastAPI + Redis Pub/Sub + WebSockets.
- **Function:** Handles all ingress/egress.
- **Protocols:**
    - HTTP (`POST /webhook/*`) for Async events (Meta API, Sentry).
    - WebSocket (`/ws/control`) for Real-time Admin Dashboard & "Ghost Mode".
- **Pattern:** Single Source of Truth. All messages (WhatsApp, Telegram, Voice) pass through the Redis Bus.

### B. The Swarm (The Brain)
- **Router:** A lightweight LLM (GPT-4o-mini) classifies intents.
- **Agents:** Specialized sub-modules (Sales, Ops, Medic, Vision).
- **Fallback:** If Cloud is down, switch to Local LLM (Ollama/Llama-3) on VPS.

### C. Physical Integration Layer
- **Vision:** Local YOLOv8 inference on RTSP streams (Crowd Counting).
- **Voice:** Local Whisper (STT) and ElevenLabs (TTS).
- **IoT:** MQTT for Door/Light control (Shelly/Nuki).

### D. Self-Improvement Loop
- **ACP (Agent Client Protocol):** Arni connects to IDEs to refactor his own code.
- **Soul Evolution:** Weekly analysis of chat logs to update `SOUL.md` via Git PR.

## 3. System Diagram (Mermaid)

```mermaid
graph TD
    User[Member] -->|Voice/Text/Image| Gateway
    Admin[Trainer] -->|WebSocket| Gateway
    Camera[CCTV] -->|RTSP| Vision_Engine

    subgraph "Local Infrastructure (VPS)"
        Gateway[Hybrid Gateway]
        Redis[Message Bus]
        Vision_Engine[YOLOv8]
        Local_LLM[Ollama/Llama-3]
        Whisper[Local STT]
    end

    subgraph "Swarm Intelligence"
        Router[Manager Agent]
        Router --> Agent_Sales
        Router --> Agent_Ops
        Router --> Agent_Medic
        Router --> Agent_Vision
    end

    Gateway <--> Redis
    Redis <--> Router