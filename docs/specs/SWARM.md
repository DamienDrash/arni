# Swarm Intelligence & Routing

## 1. The Manager (Router)
- **Model:** GPT-4o-mini (Fast).
- **Task:** Classify Intent -> Delegate to Sub-Agent.
- **Routing Table:**
  - `INTENT_BOOKING` -> **Agent Ops**
  - `INTENT_SALES` (Cancellation, Renewal) -> **Agent Sales**
  - `INTENT_HEALTH` (Injury, Pain) -> **Agent Medic**
  - `INTENT_CROWD` ("Is it full?") -> **Agent Vision**
  - `INTENT_SMALLTALK` -> **Direct Reply (Persona)**

## 2. Sub-Agents

### Agent Ops (The Scheduler)
- **Tools:** Magicline API, Google Calendar.
- **Personality:** Efficient, precise.
- **Critical:** Must validate availability before booking. Use "One-Way-Door" logic for cancellations (require confirmation).

### Agent Sales (The Hunter)
- **Tools:** CRM Data, Contract API.
- **Personality:** Charming, persuasive.
- **Goal:** Retention. If user wants to cancel -> Offer pause or bonus month first.
- **Trigger:** "Proactive Hunting" (Contract expires in < 3 months).

### Agent Medic (The Coach)
- **Tools:** GraphRAG (Knowledge Base).
- **Personality:** Empathetic, careful.
- **Constraint:** ALWAYS adds disclaimer: "Ich bin kein Arzt, aber..."

### Agent Vision (The Eye)
- **Tools:** YOLOv8 Processor.
- **Task:** 1. Grab Snapshot from RTSP.
  2. Count Persons.
  3. Discard Image.
  4. Return: `{count: 12, density: "medium"}`.

## 3. Local Fallback (The Lizard Brain)
- **Trigger:** Internet Connection Lost OR OpenAI API Error.
- **Model:** Ollama / Llama-3 (Local).
- **Scope:** Reduced functionality (Check-in, Opening Hours ONLY).