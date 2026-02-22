# Sprint 12: 1st & 2nd Level Support (RAG & Handoff)

**Goal:** Strengthen the core competence of Arni as a support assistant. No gimmicks (Vision), just solid answers and escalation paths.

---

## 🏗️ Architecture

### 1. Knowledge Base (RAG) - 1st Level Support
-   **Problem:** Arni hallucinates prices or rules if not in prompt.
-   **Solution:** Retrieval Augmented Generation (RAG).
-   **Stack:**
    -   `chromadb` (Local Vector Store).
    -   `LangChain` or simple embedding loop.
    -   `data/knowledge/*.md` (Source of Truth).
-   **Flow:** User Query -> Embed -> Search V-DB -> Context + Prompt -> Answer.

### 2. Human Handoff - 2nd Level Support
-   **Problem:** AI gets stuck or user is angry.
-   **Solution:** Explicit escalation protocol.
-   **Logic:**
    -   If Intent = `escalation` OR Sentiment = `negative`:
    -   Set User State = `human_mode`.
    -   Swarm Router **bypasses** AI and forwards messages to Staff Channel.
    -   Staff Reply -> Forward to User.

---

## 📝 User Stories

### US-12.1: Knowledge Base Integration (@AI)
**As** Studio Owner
**I want** to upload my Terms & Conditions and Price List,
**so that** Arni answers legal/pricing questions correctly (Hallucination Free).

**Constraint:**
-   Source of Truth must be easily updateable (files in repo).

### US-12.2: Human Escalation Protocol (@BACKEND)
**As** Member
**I want** to talk to a real human if the bot fails,
**so that** my complex issue gets resolved.

**Triggers:**
-   "Ich will einen Menschen sprechen."
-   "Support!"
-   "Das ist falsch!" (Negative Sentiment Loop).

**System Action:**
-   Send Alert to Admin Chat: "🚨 User 123 requests Human Handoff."
-   Pause AI responses for this user.
