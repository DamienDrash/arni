# ARIIA – Multi-Tenant AI Agent Platform for Fitness Studios

**ARIIA** (formerly ARNI) is a sophisticated, multi-tenant SaaS platform designed to automate and enhance member interactions for fitness studios. It acts as a digital front-desk assistant, leveraging a powerful AI agent swarm to manage communications, bookings, and member support across multiple channels like WhatsApp, Telegram, and Voice.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Open%20Studio%20Deck-brightgreen?style=for-the-badge&logo=live)](https://services.frigew.ski/arni)

---

## ✨ Core Features

ARIIA has evolved far beyond a simple chatbot into a comprehensive studio management and automation platform. The current version is a production-ready, multi-tenant SaaS application.

| Feature | Description |
| :--- | :--- |
| **Multi-Tenant SaaS** | Securely manage multiple independent fitness studios (tenants) with isolated data, configurations, and billing. |
| **AI Agent Swarm** | A "Project Titan" Orchestrator-Worker architecture delegates tasks to specialized agents (Ops, Sales, Medic, Vision) for superior problem-solving. |
| **Studio Deck** | A comprehensive web frontend (Next.js) for tenant admins to monitor conversations, manage members, view analytics, and configure the system. |
| **Multi-Channel Comms** | Seamlessly integrates with **WhatsApp**, **Telegram**, and **Voice** (STT/TTS), normalizing messages into a unified pipeline. |
| **Advanced CRM** | Rich member profiles with activity tracking, booking history, preference analysis, and automated data enrichment via **Magicline** integration. |
| **Churn Prediction** | Proactively identifies at-risk members using activity data and configurable churn-scoring rules. |
| **3-Tier Memory System** | Combines short-term (Redis), long-term (PostgreSQL), and knowledge-base (Markdown files) memory for deep, contextual conversations. |
| **Billing & Subscriptions** | A robust feature-gating system manages different SaaS plans (Starter, Pro, Enterprise) and enforces usage limits. |
| **Security & Governance** | Built with enterprise-grade security, including strict authentication, tenant data isolation (RLS), and encrypted API keys. |

## 🏛️ Architecture

The system is designed as a decoupled, service-oriented architecture, orchestrated via a central Redis message bus. This ensures scalability, resilience, and maintainability.

=======
# ARIIA v2.0 🤖 (Project Titan)

**ARIIA** is a sophisticated, multi-tenant AI Agentic SaaS platform designed to automate and enhance studio operations. It acts as a digital "Arnold Prime" orchestrator, leveraging a powerful AI worker swarm to manage communications, bookings, member memory, and physical intelligence across multiple channels like WhatsApp, Telegram, and Voice.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Open%20Studio%20Deck-6C5CE7?style=for-the-badge&logo=live)](https://services.frigew.ski/arni)

---

## ✨ Core Vision v2.0
ARIIA has evolved from a simple intent-router into a full-scale **Orchestrator-Worker Architecture**. At its heart lies **Arnold Prime**, a master orchestrator that plans, executes, and synthesizes complex multi-step tasks across a distributed swarm of specialized AI workers.

| Feature | Description |
| :--- | :--- |
| **Project Titan** | Master Orchestrator logic for sophisticated reasoning, parallel tool-calling, and response synthesis. |
| **Multi-Tenant SaaS** | Stricly isolated data, configurations, and communication channels per tenant with BYOK (Bring Your Own Key) support. |
| **3-Tier Deep Memory** | Episodic, Semantic (Vector DB), and RAM context memory for true long-term member relationships and analytical profiling. |
| **Omni-Channel Comms** | Unified pipeline for **WhatsApp**, **Telegram**, and **Voice** (Whisper STT + Kokoro/ElevenLabs TTS). |
| **Physical Intelligence** | YOLOv8-powered Vision Agent for real-time utilization analysis with a 0s-retention privacy engine. |
| **Studio Deck** | High-end Next.js admin interface for monitoring live sessions, analytics, and platform governance. |
| **Billing & Stripe** | Integrated subscription management, feature-gating, and automated usage tracking. |

## 🏛️ Architecture

The system is a decoupled, service-oriented architecture, orchestrated via Arnold Prime and a central Redis message bus.

>>>>>>> Stashed changes
```mermaid
graph TD
    subgraph "Channels"
        direction LR
        User_WA[Member via WhatsApp]
        User_TG[Member via Telegram]
<<<<<<< Updated upstream
        User_Voice[Member via Voice Call]
=======
        User_Voice[Member via Voice/Audio]
>>>>>>> Stashed changes
    end

    subgraph "ARIIA SaaS Platform (Docker)"
        direction TB
        Gateway[FastAPI Gateway]
<<<<<<< Updated upstream
        Redis[Redis Message Bus]
        Frontend[Next.js Studio Deck]
        Postgres[PostgreSQL Database]
        Worker[Background Worker]
        
        subgraph "AI Core"
            direction TB
            Orchestrator[Master Orchestrator]
            Agent_Ops[Ops Agent]
            Agent_Sales[Sales Agent]
            Agent_Medic[Medic Agent]
            Agent_Vision[Vision Agent]
            Orchestrator --> Agent_Ops & Agent_Sales & Agent_Medic & Agent_Vision
=======
        Redis[Redis Bus]
        Frontend[Next.js Studio Deck]
        Postgres[(PostgreSQL)]
        Qdrant[(Qdrant Vector DB)]
        
        subgraph "AI Core (Titan)"
            direction TB
            Orchestrator[Arnold Prime]
            Agent_Ops[Worker: Ops]
            Agent_Sales[Worker: Sales]
            Agent_Medic[Worker: Medic]
            Agent_Vision[Worker: Vision]
            Orchestrator -- Tool Call --> Agent_Ops & Agent_Sales & Agent_Medic & Agent_Vision
>>>>>>> Stashed changes
        end

        User_WA & User_TG & User_Voice --> Gateway
        Gateway <--> Redis
<<<<<<< Updated upstream
        Redis --> Orchestrator
        Orchestrator --> Redis
        Redis --> Gateway
        Gateway --> User_WA & User_TG & User_Voice
=======
        Redis <--> Orchestrator
>>>>>>> Stashed changes
        
        Admin[Studio Admin] --> Frontend
        Frontend <--> Gateway
        Gateway <--> Postgres
<<<<<<< Updated upstream
        Worker <--> Postgres
        Worker <--> Redis
=======
        Gateway <--> Qdrant
>>>>>>> Stashed changes
    end
```

## 🚀 Getting Started

<<<<<<< Updated upstream
The entire platform is containerized and can be launched with a single command using Docker Compose.

**Prerequisites:**
*   Docker & Docker Compose
*   An `.env` file configured with your API keys and secrets (see `.env.example`).

```bash
# 1. Clone the repository
git clone https://github.com/DamienDrash/arni.git
cd arni

# 2. Configure your environment
cp .env.example .env
# nano .env  <-- Add your OPENAI_API_KEY, AUTH_SECRET, etc.

# 3. Launch the platform
=======
The entire platform is containerized and can be launched with Docker Compose.

**Prerequisites:**
*   Docker & Docker Compose
*   An `.env` file (see `.env.example`)

```bash
# 1. Clone & Enter
git clone https://github.com/DamienDrash/arni.git
cd arni

# 2. Setup Environment
cp .env.example .env
# Edit .env with your keys (OpenAI, Meta, etc.)

# 3. Launch the Evolution
>>>>>>> Stashed changes
docker compose up --build
```

Your services will be available at:
<<<<<<< Updated upstream
*   **Studio Deck (Frontend):** `http://localhost:3000`
*   **ARIIA Gateway (Backend):** `http://localhost:8000/docs`
=======
*   **Studio Deck:** `https://services.frigew.ski/arni/`
*   **API Docs:** `http://localhost:8000/docs`
>>>>>>> Stashed changes

## 💻 Technology Stack

| Area | Technology |
| :--- | :--- |
| **Backend** | Python 3.12, FastAPI, PostgreSQL, Redis, SQLAlchemy, Pydantic |
<<<<<<< Updated upstream
| **Frontend** | Next.js 16, React 19, TypeScript, TailwindCSS, TanStack Query |
| **AI & ML** | OpenAI (GPT-4), YOLOv8, Whisper STT, ElevenLabs TTS |
| **DevOps** | Docker, Docker Compose, Alembic, Pytest, Playwright, GitHub Actions |

## 📁 Project Structure

The codebase is organized into a clean, modular structure that separates concerns and facilitates development.

```
/home/ubuntu/arni
├── app/                  # Core Backend Application
│   ├── core/             # Auth, DB Models, Feature Gates, Security
│   ├── gateway/          # FastAPI Routers (Admin, Webhooks, WebSockets)
│   ├── integrations/     # Connectors (WhatsApp, Telegram, Magicline)
│   ├── memory/           # 3-Tier Memory & Knowledge Base System
│   ├── swarm/            # AI Agent Swarm (Master Orchestrator & Workers)
│   └── ...               # Other modules (Voice, Vision, etc.)
├── frontend/             # Next.js Studio Deck Application
│   ├── app/              # Next.js App Router, Pages & API Routes
│   └── components/       # Reusable React Components
├── tests/                # Backend Pytest Integration & Unit Tests
├── alembic/              # Database Migration Scripts
├── docs/                 # Project Documentation & Architecture Specs
├── scripts/              # Utility and operational scripts
├── docker-compose.yml    # Defines all application services
└── pyproject.toml        # Python project definition and dependencies
```

## 🧪 Testing

The project maintains a high standard of quality with a comprehensive test suite.

```bash
# Run all backend tests inside the container
docker compose exec ariia-core pytest -v
```

*   **36+** detailed test files covering all critical modules.
*   Integration tests for authentication, multi-tenancy, and core agent logic.
*   End-to-end tests for the frontend using Playwright.

## 🗺️ Roadmap

This project is actively being developed into a high-end, enterprise-ready SaaS platform. The roadmap, detailed in `docs/sprints/SAAS_ROADMAP.md`, includes further enhancements to security, billing, and white-labeling capabilities.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
=======
| **Frontend** | Next.js 16 (App Router), TypeScript, TailwindCSS, Framer Motion |
| **AI & ML** | GPT-4o, YOLOv8, Whisper, ElevenLabs, Kokoro-82M, Qdrant |
| **Ops** | Docker, Alembic, Prometheus, LangFuse, Pytest |

## 📁 Project Structure

```
ariia/
├── app/
│   ├── swarm/             # Arnold Prime & Worker Swarm
│   ├── gateway/           # Multi-Tenant FastAPI Gateway
│   ├── core/              # Auth (RBAC), Billing, DB Models
│   ├── memory/            # 3-Tier Memory & Analysis
│   ├── integrations/      # Connectors (Magicline, WA, Stripe)
│   ├── tools/             # MCP-Compliant Tools
│   ├── vision/            # YOLOv8 Privacy Engine
│   └── voice/             # E2E Voice Pipeline
├── frontend/              # "Studio Deck" Admin Dashboard
├── tests/                 # QA Suite (Contract + Integration)
└── scripts/               # Deployment & Maintenance
```

## 🧪 Development Workflow: The BMAD Cycle
1.  **B - Benchmark:** Define success metrics and test cases first.
2.  **M - Modularize:** Build the worker or tool in isolation.
3.  **A - Architect:** Integrate into Arnold Prime's orchestration loop.
4.  **D - Deploy & Verify:** Run quality gates and verify against benchmarks.

---

> Built with ❤️ for the future of fitness | ARIIA v2.0.0
>>>>>>> Stashed changes
