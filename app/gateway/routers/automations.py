"""ARIIA v2.1 – Automation Workflows API Router.

Provides CRUD endpoints for automation workflows, run management,
and audit trail access.

Endpoints:
    GET    /v2/admin/automations                          List workflows
    POST   /v2/admin/automations                          Create workflow
    GET    /v2/admin/automations/{id}                     Get workflow
    PUT    /v2/admin/automations/{id}                     Update workflow
    DELETE /v2/admin/automations/{id}                     Delete workflow (soft)
    POST   /v2/admin/automations/{id}/activate            Activate workflow
    POST   /v2/admin/automations/{id}/deactivate          Deactivate workflow
    POST   /v2/admin/automations/{id}/trigger             Manually trigger for contacts
    GET    /v2/admin/automations/{id}/runs                List runs
    GET    /v2/admin/automations/{id}/runs/{run_id}/logs  Get run audit trail
    POST   /v2/admin/automations/{id}/runs/{run_id}/cancel Cancel a run
    GET    /v2/admin/automations/stats                    Automation statistics
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.auth import AuthContext, get_current_user
from app.core.db import get_db
from app.core.automation_models import AutomationWorkflow, AutomationRun, AutomationRunLog

logger = logging.getLogger("ariia.api.automations")

router = APIRouter(
    prefix="/v2/admin/automations",
    tags=["automations"],
)


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: str = Field(..., pattern=r"^(segment_entry|segment_exit|contact_created|tag_added|tag_removed|lifecycle_change|manual)$")
    trigger_config_json: Optional[str] = None
    workflow_graph_json: str = '{"nodes":[],"edges":[]}'
    max_concurrent_runs: int = Field(default=1000, ge=1, le=100000)
    re_entry_policy: str = Field(default="skip", pattern=r"^(skip|restart|parallel)$")


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config_json: Optional[str] = None
    workflow_graph_json: Optional[str] = None
    max_concurrent_runs: Optional[int] = Field(None, ge=1, le=100000)
    re_entry_policy: Optional[str] = None


class ManualTriggerRequest(BaseModel):
    contact_ids: list[int] = Field(..., min_length=1, max_length=1000)


# ─── Helper ──────────────────────────────────────────────────────────────────

def _get_workflow(db: Session, workflow_id: int, tenant_id: int) -> AutomationWorkflow:
    """Get a workflow by ID, scoped to tenant."""
    wf = db.query(AutomationWorkflow).filter(
        AutomationWorkflow.id == workflow_id,
        AutomationWorkflow.tenant_id == tenant_id,
    ).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow nicht gefunden")
    return wf


def _workflow_to_dict(wf: AutomationWorkflow, active_runs: int = 0) -> dict:
    """Serialize a workflow to a dict."""
    return {
        "id": wf.id,
        "tenant_id": wf.tenant_id,
        "name": wf.name,
        "description": wf.description,
        "is_active": wf.is_active,
        "trigger_type": wf.trigger_type,
        "trigger_config_json": wf.trigger_config_json,
        "workflow_graph_json": wf.workflow_graph_json,
        "max_concurrent_runs": wf.max_concurrent_runs,
        "re_entry_policy": wf.re_entry_policy,
        "active_runs": active_runs,
        "created_by": wf.created_by,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }


def _run_to_dict(run: AutomationRun) -> dict:
    """Serialize a run to a dict."""
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "contact_id": run.contact_id,
        "tenant_id": run.tenant_id,
        "status": run.status,
        "current_node_id": run.current_node_id,
        "next_execution_at": run.next_execution_at.isoformat() if run.next_execution_at else None,
        "run_data_json": run.run_data_json,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _log_to_dict(log: AutomationRunLog) -> dict:
    """Serialize a run log to a dict."""
    return {
        "id": log.id,
        "run_id": log.run_id,
        "node_id": log.node_id,
        "node_type": log.node_type,
        "result_json": log.result_json,
        "error_message": log.error_message,
        "executed_at": log.executed_at.isoformat() if log.executed_at else None,
    }


# ─── CRUD Endpoints ──────────────────────────────────────────────────────────

@router.get("")
async def list_workflows(
    is_active: Optional[bool] = None,
    trigger_type: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all automation workflows for the current tenant."""
    q = db.query(AutomationWorkflow).filter(
        AutomationWorkflow.tenant_id == user.tenant_id,
    )
    if is_active is not None:
        q = q.filter(AutomationWorkflow.is_active == is_active)
    if trigger_type:
        q = q.filter(AutomationWorkflow.trigger_type == trigger_type)
    if search:
        q = q.filter(AutomationWorkflow.name.ilike(f"%{search}%"))

    total = q.count()
    workflows = q.order_by(AutomationWorkflow.updated_at.desc()).offset(skip).limit(limit).all()

    # Get active run counts in one query
    run_counts = {}
    if workflows:
        wf_ids = [wf.id for wf in workflows]
        counts = (
            db.query(AutomationRun.workflow_id, func.count(AutomationRun.id))
            .filter(
                AutomationRun.workflow_id.in_(wf_ids),
                AutomationRun.status.in_(["active", "waiting"]),
            )
            .group_by(AutomationRun.workflow_id)
            .all()
        )
        run_counts = {wf_id: count for wf_id, count in counts}

    return {
        "items": [_workflow_to_dict(wf, run_counts.get(wf.id, 0)) for wf in workflows],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("", status_code=201)
async def create_workflow(
    data: WorkflowCreate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new automation workflow."""
    # Validate graph JSON
    try:
        if data.workflow_graph_json:
            json.loads(data.workflow_graph_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ungültiges workflow_graph_json")

    if data.trigger_config_json:
        try:
            json.loads(data.trigger_config_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Ungültiges trigger_config_json")

    workflow = AutomationWorkflow(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        trigger_type=data.trigger_type,
        trigger_config_json=data.trigger_config_json,
        workflow_graph_json=data.workflow_graph_json,
        max_concurrent_runs=data.max_concurrent_runs,
        re_entry_policy=data.re_entry_policy,
        created_by=user.user_id,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    logger.info("automation.workflow_created", workflow_id=workflow.id, tenant_id=user.tenant_id)
    return _workflow_to_dict(workflow)


@router.get("/stats")
async def get_automation_stats(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get automation statistics for the current tenant."""
    total_workflows = db.query(func.count(AutomationWorkflow.id)).filter(
        AutomationWorkflow.tenant_id == user.tenant_id
    ).scalar() or 0

    active_workflows = db.query(func.count(AutomationWorkflow.id)).filter(
        AutomationWorkflow.tenant_id == user.tenant_id,
        AutomationWorkflow.is_active.is_(True),
    ).scalar() or 0

    active_runs = db.query(func.count(AutomationRun.id)).filter(
        AutomationRun.tenant_id == user.tenant_id,
        AutomationRun.status.in_(["active", "waiting"]),
    ).scalar() or 0

    completed_runs = db.query(func.count(AutomationRun.id)).filter(
        AutomationRun.tenant_id == user.tenant_id,
        AutomationRun.status == "completed",
    ).scalar() or 0

    error_runs = db.query(func.count(AutomationRun.id)).filter(
        AutomationRun.tenant_id == user.tenant_id,
        AutomationRun.status == "error",
    ).scalar() or 0

    return {
        "total_workflows": total_workflows,
        "active_workflows": active_workflows,
        "active_runs": active_runs,
        "completed_runs": completed_runs,
        "error_runs": error_runs,
    }


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single workflow with its full graph definition."""
    wf = _get_workflow(db, workflow_id, user.tenant_id)
    active_runs = db.query(func.count(AutomationRun.id)).filter(
        AutomationRun.workflow_id == wf.id,
        AutomationRun.status.in_(["active", "waiting"]),
    ).scalar() or 0
    return _workflow_to_dict(wf, active_runs)


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: int,
    data: WorkflowUpdate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a workflow. Cannot update graph while workflow is active."""
    wf = _get_workflow(db, workflow_id, user.tenant_id)

    if wf.is_active and data.workflow_graph_json is not None:
        raise HTTPException(
            status_code=400,
            detail="Workflow-Graph kann nicht geändert werden, solange der Workflow aktiv ist. Bitte zuerst deaktivieren."
        )

    if data.workflow_graph_json:
        try:
            json.loads(data.workflow_graph_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Ungültiges workflow_graph_json")

    if data.trigger_config_json:
        try:
            json.loads(data.trigger_config_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Ungültiges trigger_config_json")

    update_fields = data.model_dump(exclude_unset=True)
    for key, value in update_fields.items():
        setattr(wf, key, value)

    wf.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(wf)

    logger.info("automation.workflow_updated", workflow_id=wf.id)
    return _workflow_to_dict(wf)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a workflow by deactivating it and cancelling all active runs."""
    wf = _get_workflow(db, workflow_id, user.tenant_id)

    # Cancel all active runs
    db.query(AutomationRun).filter(
        AutomationRun.workflow_id == wf.id,
        AutomationRun.status.in_(["active", "waiting"]),
    ).update(
        {"status": "cancelled", "completed_at": datetime.now(timezone.utc)},
        synchronize_session="fetch",
    )

    wf.is_active = False
    wf.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("automation.workflow_deleted", workflow_id=wf.id)
    return {"status": "deleted", "workflow_id": wf.id}


@router.post("/{workflow_id}/activate")
async def activate_workflow(
    workflow_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate a workflow so it starts processing triggers."""
    wf = _get_workflow(db, workflow_id, user.tenant_id)

    # Validate that the graph has at least a trigger and one action
    try:
        graph = json.loads(wf.workflow_graph_json)
        nodes = graph.get("nodes", [])
        if len(nodes) < 2:
            raise HTTPException(
                status_code=400,
                detail="Workflow muss mindestens einen Trigger und eine Aktion enthalten."
            )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ungültiger Workflow-Graph")

    wf.is_active = True
    wf.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("automation.workflow_activated", workflow_id=wf.id)
    return {"status": "activated", "workflow_id": wf.id}


@router.post("/{workflow_id}/deactivate")
async def deactivate_workflow(
    workflow_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate a workflow. Active runs continue but no new triggers are processed."""
    wf = _get_workflow(db, workflow_id, user.tenant_id)
    wf.is_active = False
    wf.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("automation.workflow_deactivated", workflow_id=wf.id)
    return {"status": "deactivated", "workflow_id": wf.id}


@router.post("/{workflow_id}/trigger")
async def manual_trigger(
    workflow_id: int,
    data: ManualTriggerRequest,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a workflow for specific contacts."""
    wf = _get_workflow(db, workflow_id, user.tenant_id)

    if not wf.is_active:
        raise HTTPException(status_code=400, detail="Workflow ist nicht aktiv")

    graph = json.loads(wf.workflow_graph_json or '{"nodes":[],"edges":[]}')
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Find first action node
    trigger_id = None
    for node in nodes:
        node_type = node.get("type", node.get("data", {}).get("nodeType", ""))
        if node_type == "trigger":
            trigger_id = node.get("id")
            break

    first_node_id = None
    if trigger_id:
        for edge in edges:
            if edge.get("source") == trigger_id:
                first_node_id = edge.get("target")
                break
    if not first_node_id and nodes:
        first_node_id = nodes[0].get("id")

    created = 0
    skipped = 0
    for contact_id in data.contact_ids:
        # Check re-entry policy
        existing = db.query(AutomationRun).filter(
            AutomationRun.workflow_id == wf.id,
            AutomationRun.contact_id == contact_id,
            AutomationRun.status.in_(["active", "waiting"]),
        ).first()

        if existing and wf.re_entry_policy == "skip":
            skipped += 1
            continue
        elif existing and wf.re_entry_policy == "restart":
            existing.status = "cancelled"
            existing.completed_at = datetime.now(timezone.utc)

        run = AutomationRun(
            workflow_id=wf.id,
            contact_id=contact_id,
            tenant_id=user.tenant_id,
            status="active",
            current_node_id=first_node_id,
            next_execution_at=datetime.now(timezone.utc),
        )
        db.add(run)
        created += 1

    db.commit()
    logger.info("automation.manual_trigger", workflow_id=wf.id, created=created, skipped=skipped)
    return {"status": "triggered", "created": created, "skipped": skipped}


# ─── Run Endpoints ───────────────────────────────────────────────────────────

@router.get("/{workflow_id}/runs")
async def list_runs(
    workflow_id: int,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all runs for a workflow."""
    wf = _get_workflow(db, workflow_id, user.tenant_id)

    q = db.query(AutomationRun).filter(AutomationRun.workflow_id == wf.id)
    if status:
        q = q.filter(AutomationRun.status == status)

    total = q.count()
    runs = q.order_by(AutomationRun.started_at.desc()).offset(skip).limit(limit).all()

    return {
        "items": [_run_to_dict(r) for r in runs],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{workflow_id}/runs/{run_id}/logs")
async def get_run_logs(
    workflow_id: int,
    run_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the audit trail (logs) for a specific run."""
    wf = _get_workflow(db, workflow_id, user.tenant_id)

    run = db.query(AutomationRun).filter(
        AutomationRun.id == run_id,
        AutomationRun.workflow_id == wf.id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run nicht gefunden")

    logs = (
        db.query(AutomationRunLog)
        .filter(AutomationRunLog.run_id == run.id)
        .order_by(AutomationRunLog.executed_at.asc())
        .all()
    )

    return {
        "run": _run_to_dict(run),
        "logs": [_log_to_dict(log) for log in logs],
    }


@router.post("/{workflow_id}/runs/{run_id}/cancel")
async def cancel_run(
    workflow_id: int,
    run_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel an active or waiting run."""
    wf = _get_workflow(db, workflow_id, user.tenant_id)

    run = db.query(AutomationRun).filter(
        AutomationRun.id == run_id,
        AutomationRun.workflow_id == wf.id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run nicht gefunden")

    if run.status not in ("active", "waiting"):
        raise HTTPException(status_code=400, detail=f"Run kann nicht abgebrochen werden (Status: {run.status})")

    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("automation.run_cancelled", run_id=run.id, workflow_id=wf.id)
    return {"status": "cancelled", "run_id": run.id}
