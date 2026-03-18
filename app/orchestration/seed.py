"""Seed default orchestrator definitions into the database (idempotent)."""
from __future__ import annotations
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.orchestration.models import OrchestratorDefinition

logger = structlog.get_logger()

DEFAULTS = [
    {
        "name": "swarm-orchestrator",
        "display_name": "Swarm Orchestrator",
        "category": "SWARM",
        "scope": "SYSTEM",
        "config_current": {
            "intent_classifier": {"model": "gpt-4o-mini", "temperature": 0.0, "fallback_agent": "persona", "low_confidence_threshold": 0.6},
            "qa_gate": {"enabled": True, "max_revision_rounds": 2, "escalation_handler": "human_handoff"},
            "confirmation_gate": {"ttl_seconds": 300, "warning_at_seconds": 240, "expiry_notification": True},
            "agent_loader_cache_ttl_seconds": 60,
            "tool_registry_cache_ttl_seconds": 60,
        },
        "guardrails": {"qa_gate.enabled": {"immutable": True, "value": True}, "intent_classifier.max_revision_rounds": {"max": 3}},
    },
    {
        "name": "quality-gate",
        "display_name": "Quality Gate",
        "category": "SWARM",
        "scope": "SYSTEM",
        "config_current": {"escalation_handler": "human_handoff", "max_revision_rounds": 2},
        "guardrails": {"enabled": {"immutable": True, "value": True}},
    },
    {
        "name": "confirmation-gate",
        "display_name": "Confirmation Gate",
        "category": "SWARM",
        "scope": "TENANT",
        "config_current": {"ttl_seconds": 300, "warning_at_seconds": 240, "expiry_notification": True},
        "guardrails": {},
    },
    {
        "name": "campaign-delivery-orchestrator",
        "display_name": "Campaign Delivery",
        "category": "CAMPAIGN",
        "scope": "TENANT",
        "config_current": {"batch_size": 50, "retry_max": 3, "retry_backoff_seconds": [60, 300, 900]},
        "guardrails": {"batch_size": {"max": 500}},
    },
    {
        "name": "automation-orchestrator",
        "display_name": "Automation Engine",
        "category": "AUTOMATION",
        "scope": "TENANT",
        "config_current": {"batch_size": 100, "max_concurrent_runs": 10},
        "guardrails": {},
    },
    {
        "name": "integration-sync-orchestrator",
        "display_name": "Integration Sync",
        "category": "SYNC",
        "scope": "TENANT",
        "config_current": {"max_concurrent_syncs": 3, "default_interval_minutes": 360},
        "guardrails": {"max_concurrent_syncs": {"max": 10}},
    },
]


def seed_default_orchestrators(db: Session) -> None:
    """Insert default orchestrator definitions if they don't exist yet."""
    now = datetime.now(timezone.utc)
    created = 0
    for defn in DEFAULTS:
        exists = db.query(OrchestratorDefinition).filter(OrchestratorDefinition.name == defn["name"]).first()
        if exists:
            continue
        orch = OrchestratorDefinition(
            name=defn["name"],
            display_name=defn["display_name"],
            category=defn["category"],
            scope=defn["scope"],
            config_current=defn.get("config_current"),
            guardrails=defn.get("guardrails"),
            created_at=now,
            updated_at=now,
        )
        db.add(orch)
        created += 1
    if created:
        db.commit()
        logger.info("orchestration.seed_completed", created=created)
    else:
        logger.debug("orchestration.seed_skipped", reason="all defaults already exist")
