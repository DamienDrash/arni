"""ARIIA v2.1 – Automation Engine.

Core engine that processes active automation runs by executing their current node
and advancing them through the workflow graph.

The engine is designed to be run as a polling worker that periodically checks
for due runs and processes them in batches.
"""
from __future__ import annotations

import json
import structlog
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.automation_models import AutomationWorkflow, AutomationRun, AutomationRunLog
from app.core.advisory_locks import advisory_lock_or_skip
from app.campaign_engine.node_executors import get_executor

logger = structlog.get_logger()

BATCH_SIZE = 100


class AutomationEngine:
    """Processes due automation runs by executing their current node."""

    async def process_due_runs(self, db: Session) -> int:
        """Find and process all runs that are due for execution.

        Returns the number of runs processed.
        """
        now = datetime.now(timezone.utc)
        due_runs = (
            db.query(AutomationRun)
            .filter(
                AutomationRun.status.in_(["active", "waiting"]),
                AutomationRun.next_execution_at <= now,
            )
            .order_by(AutomationRun.next_execution_at.asc())
            .limit(BATCH_SIZE)
            .all()
        )

        processed = 0
        for run in due_runs:
            with advisory_lock_or_skip(db, f"automation_run:{run.id}") as acquired:
                if not acquired:
                    logger.debug(
                        "automation.run_skipped_lock",
                        run_id=run.id,
                        tenant_id=run.tenant_id,
                    )
                    continue
                try:
                    await self._execute_node(db, run)
                    processed += 1
                except Exception as e:
                    logger.error(
                        "automation.run_execution_failed",
                        run_id=run.id,
                        workflow_id=run.workflow_id,
                        tenant_id=run.tenant_id,
                        error=str(e),
                    )
                    run.status = "error"
                    run.error_message = str(e)
                    db.commit()

        return processed

    async def _execute_node(self, db: Session, run: AutomationRun) -> None:
        """Execute the current node of a run and advance to the next."""
        workflow = db.query(AutomationWorkflow).filter(
            AutomationWorkflow.id == run.workflow_id
        ).first()

        if not workflow:
            run.status = "error"
            run.error_message = f"Workflow {run.workflow_id} not found"
            db.commit()
            return

        graph = _parse_graph(workflow.workflow_graph_json)
        node = _find_node(graph, run.current_node_id)

        if not node:
            run.status = "error"
            run.error_message = f"Node '{run.current_node_id}' not found in graph"
            db.commit()
            return

        node_type = node.get("type", node.get("data", {}).get("nodeType", "end"))

        # 1. Get executor for this node type
        executor = get_executor(node_type)

        # 2. Execute the node
        try:
            result = await executor.execute(db, run, node)
        except Exception as e:
            result = {"status": "error", "error": str(e)}
            logger.error(
                "automation.node_execution_failed",
                run_id=run.id,
                node_id=run.current_node_id,
                node_type=node_type,
                tenant_id=run.tenant_id,
                error=str(e),
            )

        # 3. Log the execution
        log_entry = AutomationRunLog(
            run_id=run.id,
            node_id=run.current_node_id,
            node_type=node_type,
            result_json=json.dumps(result),
            error_message=result.get("error") if isinstance(result, dict) else None,
        )
        db.add(log_entry)

        # 4. Determine next node
        if isinstance(result, dict) and result.get("status") == "error" and node_type not in ("condition",):
            run.status = "error"
            run.error_message = result.get("error", "Unknown error")
            db.commit()
            return

        if node_type == "end":
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        if node_type == "wait":
            next_node_id = _resolve_next_node(graph, node, result)
            if next_node_id:
                run.current_node_id = next_node_id
                run.status = "waiting"
            else:
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # For all other nodes, advance immediately
        next_node_id = _resolve_next_node(graph, node, result)

        if next_node_id is None:
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
        else:
            run.current_node_id = next_node_id
            run.status = "active"
            run.next_execution_at = datetime.now(timezone.utc)

        db.commit()


# ─── Graph Helpers ───────────────────────────────────────────────────────────

def _parse_graph(graph_json: str) -> dict:
    """Parse the workflow graph JSON safely."""
    try:
        graph = json.loads(graph_json)
        if not isinstance(graph, dict):
            return {"nodes": [], "edges": []}
        return graph
    except (json.JSONDecodeError, TypeError):
        return {"nodes": [], "edges": []}


def _find_node(graph: dict, node_id: str) -> Optional[dict]:
    """Find a node in the graph by its ID."""
    if not node_id:
        return None
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def _resolve_next_node(graph: dict, current_node: dict, result: dict) -> Optional[str]:
    """Determine the next node based on edges and execution result.

    For condition nodes, the result contains a 'branch' key ('yes' or 'no')
    which is matched against edge labels/sourceHandles.
    """
    current_id = current_node.get("id")
    edges = graph.get("edges", [])
    node_type = current_node.get("type", current_node.get("data", {}).get("nodeType", ""))

    if node_type == "condition":
        branch = result.get("branch", "no") if isinstance(result, dict) else "no"
        for edge in edges:
            if edge.get("source") == current_id:
                source_handle = edge.get("sourceHandle", "")
                if source_handle == branch or source_handle == f"{branch}-handle":
                    return edge.get("target")
        for edge in edges:
            if edge.get("source") == current_id:
                label = (edge.get("label", "") or "").lower()
                if branch in label:
                    return edge.get("target")

    # For non-condition nodes, follow the first outgoing edge
    for edge in edges:
        if edge.get("source") == current_id:
            return edge.get("target")

    return None
