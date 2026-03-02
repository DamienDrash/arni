"""ARIIA Memory Platform – Modular, event-driven knowledge & memory management.

This package implements the new Enterprise Memory Platform architecture,
replacing the legacy monolithic memory/knowledge modules with a set of
decoupled, event-driven microservices.

Architecture Overview:
    ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
    │  Ingestion   │──▶│  Event Bus   │──▶│  Extraction  │
    │  Service     │   │  (Internal)  │   │  Service     │
    └─────────────┘   └──────────────┘   └──────────────┘
                             │                    │
                             ▼                    ▼
                      ┌──────────────┐   ┌──────────────┐
                      │  Enrichment  │──▶│  Memory      │
                      │  Service     │   │  Writer      │
                      └──────────────┘   └──────────────┘
                                                │
                             ┌──────────┬───────┴───────┐
                             ▼          ▼               ▼
                      ┌──────────┐ ┌──────────┐  ┌──────────┐
                      │  Neo4j   │ │  Qdrant  │  │  Redis   │
                      │  Graph   │ │  Vector  │  │  Cache   │
                      └──────────┘ └──────────┘  └──────────┘

Modules:
    event_bus   – Internal async event bus for service communication
    ingestion   – Multi-format document ingestion with parser registry
    extraction  – LLM-powered entity and fact extraction
    enrichment  – Data enrichment from internal/external sources
    writer      – Transactional writes to graph + vector stores
    retrieval   – Unified hybrid search API (graph + vector + keyword)
    connectors  – External source connectors (Notion, etc.)
    consent     – GDPR-compliant consent management
    prefetcher  – Proactive context pre-fetching service
    models      – Shared data models and schemas
    config      – Platform configuration
"""

__version__ = "2.0.0"
