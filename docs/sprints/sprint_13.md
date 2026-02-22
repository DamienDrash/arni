# Sprint 13: Admin Dashboard 🎛️

**Goal:** Centralized Control Panel for Ariia.

## 🏗️ Tech Stack
-   **Framework:** Next.js 14 (App Router)
-   **Style:** Tailwind CSS + DaisyUI (Dark Mode default)
-   **Deployment:** Static Export or Node Server (mapped to `/ariia`)

## 🎨 Layout
-   **Sidebar:**
    -   📊 **Dashboard:** Metrics (Total chats today).
    -   👻 **Live Ghost:** Real-time WebSocket feed.
    -   📚 **Knowledge:** Edit RAG docs.
    -   🚨 **Handoffs:** Active human escalations.
    -   ⚙️ **Settings:** Toggle System Status / Edit SOUL.md.

## 🔌 API Integration
The Frontend talks to the Python Gateway (`main.py`) via:
1.  **WebSocket:** `/ws/control` (Live Stream).
2.  **REST:** `/admin/*` endpoints (File interactions, Redis control).
    -   *Security:* Basic Auth handling (or simple Token header from Env).

## 📝 User Stories
(See task.md for breakdown)

## 🛡️ Security
-   Admin Panel must be password protected.
-   We will implement a simple "Hardcoded Token" auth for MVP (Sprint 13).
-   Env: `ADMIN_PASSWORD` in `.env`.
