"""ARIIA v2.1 – Contact Change Listener.

Polls the contact_activities table for relevant changes and triggers
matching automation workflows. This is the bridge between contact events
(segment entry, tag changes, lifecycle transitions) and the automation engine.

Architecture Decision:
    Uses polling on contact_activities instead of Redis Pub/Sub because:
    1. contact_activities already serves as the central event log
    2. No additional infrastructure required
    3. Guaranteed delivery (DB-backed vs. in-memory)
    4. Natural deduplication via timestamp tracking
"""
from __future__ import annotations

import json
import structlog
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.contact_models import ContactActivity
from app.core.automation_models import AutomationWorkflow, AutomationRun

logger = structlog.get_logger()

# Activity types that can trigger automations
RELEVANT_ACTIVITY_TYPES = [
    "lifecycle_change",
    "tag_added",
    "tag_removed",
    "segment_entered",
    "segment_exited",
    "contact_created",
    "import_completed",
]

# Mapping from activity_type to trigger_type
_ACTIVITY_TO_TRIGGER = {
    "lifecycle_change": "lifecycle_change",
    "tag_added": "tag_added",
    "tag_removed": "tag_removed",
    "segment_entered": "segment_entry",
    "segment_exited": "segment_exit",
    "contact_created": "contact_created",
}

POLL_BATCH_SIZE = 500


class ContactChangeListener:
    """Listens for contact changes and triggers matching automation workflows."""

    def __init__(self):
        self._last_processed_id: int = 0

    async def poll(self, db: Session) -> int:
        """Poll for new activities since last check.

        Returns the number of workflows triggered.
        """
        query = (
            db.query(ContactActivity)
            .filter(
                ContactActivity.id > self._last_processed_id,
                ContactActivity.activity_type.in_(RELEVANT_ACTIVITY_TYPES),
            )
            .order_by(ContactActivity.id.asc())
            .limit(POLL_BATCH_SIZE)
        )

        new_activities = query.all()
        triggered = 0

        for activity in new_activities:
            try:
                count = await self._process_activity(db, activity)
                triggered += count
            except Exception as e:
                logger.error(
                    "listener.activity_processing_failed",
                    activity_id=activity.id,
                    tenant_id=activity.tenant_id,
                    error=str(e),
                )
            finally:
                self._last_processed_id = activity.id

        return triggered

    async def _process_activity(self, db: Session, activity: ContactActivity) -> int:
        """Check if any active workflow should be triggered by this activity.

        Returns the number of workflows triggered.
        """
        trigger_type = _ACTIVITY_TO_TRIGGER.get(activity.activity_type)
        if not trigger_type:
            return 0

        # Find matching active workflows for this tenant
        workflows = (
            db.query(AutomationWorkflow)
            .filter(
                AutomationWorkflow.tenant_id == activity.tenant_id,
                AutomationWorkflow.is_active.is_(True),
                AutomationWorkflow.trigger_type == trigger_type,
            )
            .all()
        )

        triggered = 0
        for workflow in workflows:
            if self._matches_trigger_config(workflow, activity):
                started = await self._start_run(db, workflow, activity.contact_id)
                if started:
                    triggered += 1

        return triggered

    def _matches_trigger_config(self, workflow: AutomationWorkflow, activity: ContactActivity) -> bool:
        """Check if the activity matches the workflow's trigger configuration."""
        config = _parse_json(workflow.trigger_config_json)
        metadata = _parse_json(activity.metadata_json)

        if not config:
            return True

        trigger_type = workflow.trigger_type

        if trigger_type in ("segment_entry", "segment_exit"):
            target_segment_id = config.get("segment_id")
            if target_segment_id is not None:
                return str(target_segment_id) == str(metadata.get("segment_id"))
            target_segment_name = config.get("segment_name", "")
            if target_segment_name:
                return target_segment_name.lower() == metadata.get("segment_name", "").lower()

        elif trigger_type == "tag_added":
            target_tag = config.get("tag_name", "")
            activity_tag = metadata.get("tag", metadata.get("tag_name", ""))
            return target_tag.lower() == activity_tag.lower() if target_tag else True

        elif trigger_type == "tag_removed":
            target_tag = config.get("tag_name", "")
            activity_tag = metadata.get("tag", metadata.get("tag_name", ""))
            return target_tag.lower() == activity_tag.lower() if target_tag else True

        elif trigger_type == "lifecycle_change":
            target_from = config.get("lifecycle_from", "")
            target_to = config.get("lifecycle_to", "")
            actual_from = metadata.get("from", metadata.get("old_stage", ""))
            actual_to = metadata.get("to", metadata.get("new_stage", ""))
            from_match = (not target_from) or (target_from.lower() == actual_from.lower())
            to_match = (not target_to) or (target_to.lower() == actual_to.lower())
            return from_match and to_match

        elif trigger_type == "contact_created":
            return True

        return True

    async def _start_run(self, db: Session, workflow: AutomationWorkflow, contact_id: int) -> bool:
        """Create a new automation run for the contact.

        Returns True if a run was created, False if skipped.
        """
        # Check re-entry policy
        existing = (
            db.query(AutomationRun)
            .filter(
                AutomationRun.workflow_id == workflow.id,
                AutomationRun.contact_id == contact_id,
                AutomationRun.status.in_(["active", "waiting"]),
            )
            .first()
        )

        if existing:
            if workflow.re_entry_policy == "skip":
                logger.debug(
                    "listener.run_skipped_reentry",
                    workflow_id=workflow.id,
                    contact_id=contact_id,
                )
                return False
            elif workflow.re_entry_policy == "restart":
                existing.status = "cancelled"
                existing.completed_at = datetime.now(timezone.utc)
                logger.info(
                    "listener.run_cancelled_for_restart",
                    old_run_id=existing.id,
                    workflow_id=workflow.id,
                    contact_id=contact_id,
                )

        # Check max concurrent runs
        active_count = (
            db.query(AutomationRun)
            .filter(
                AutomationRun.workflow_id == workflow.id,
                AutomationRun.status.in_(["active", "waiting"]),
            )
            .count()
        )
        if active_count >= workflow.max_concurrent_runs:
            logger.warning(
                "listener.max_concurrent_runs_reached",
                workflow_id=workflow.id,
                tenant_id=workflow.tenant_id,
                active_count=active_count,
                max_allowed=workflow.max_concurrent_runs,
            )
            return False

        # Parse graph to find the first action node (after trigger)
        graph = _parse_json(workflow.workflow_graph_json)
        first_node_id = _find_first_action_node(graph)

        if not first_node_id:
            logger.warning("listener.no_action_node_found", workflow_id=workflow.id)
            return False

        run = AutomationRun(
            workflow_id=workflow.id,
            contact_id=contact_id,
            tenant_id=workflow.tenant_id,
            status="active",
            current_node_id=first_node_id,
            next_execution_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()

        logger.info(
            "listener.run_started",
            run_id=run.id,
            workflow_id=workflow.id,
            contact_id=contact_id,
            tenant_id=workflow.tenant_id,
            first_node=first_node_id,
        )
        return True


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_json(text: Optional[str]) -> dict:
    """Safely parse JSON text to dict."""
    if not text:
        return {}
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _find_first_action_node(graph: dict) -> Optional[str]:
    """Find the first non-trigger node in the workflow graph.

    Follows edges from the trigger node to find the first action node.
    """
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    trigger_id = None
    for node in nodes:
        node_type = node.get("type", node.get("data", {}).get("nodeType", ""))
        if node_type == "trigger":
            trigger_id = node.get("id")
            break

    if not trigger_id:
        return nodes[0].get("id") if nodes else None

    for edge in edges:
        if edge.get("source") == trigger_id:
            return edge.get("target")

    return None
