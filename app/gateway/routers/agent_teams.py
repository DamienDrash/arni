"""app/gateway/routers/agent_teams.py — Agent Team Management API.

Endpoints under /v2/admin/agent-teams/ and /v2/admin/agent-tools/.

Multi-tenant: every query is scoped to auth.tenant_id.
System-admin can manage system teams and builtin tools.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, get_current_user
from app.core.db import get_db, SessionLocal
from app.core.models import AuditLog
from app.core.feature_gates import FeatureGate

logger = structlog.get_logger()

router = APIRouter(tags=["agent-teams"])

# ─── Slug validation pattern ──────────────────────────────────────────────────
_SLUG_RE = re.compile(r'^[a-z0-9]([a-z0-9\-]{0,62}[a-z0-9])?$')


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _require_team_access(auth: AuthContext) -> None:
    """tenant_admin or system_admin only — tenant_user has no access."""
    if auth.role not in {"system_admin", "tenant_admin"}:
        raise HTTPException(403, "Agent Teams require tenant_admin or system_admin role")


def _require_feature(auth: AuthContext) -> None:
    """Enforce agent_teams_enabled plan gate. system_admin bypasses."""
    if auth.role == "system_admin":
        return
    FeatureGate(auth.tenant_id).require_feature("agent_teams")


def _safe_yaml_export(team, steps: list) -> None:
    """Background-safe YAML export — failures are logged, never raise."""
    try:
        from app.swarm.team_yaml import export_team_yaml
        export_team_yaml(team, steps)
    except Exception as exc:
        logger.warning("agent_teams.yaml_export_failed", slug=getattr(team, "slug", "?"), error=str(exc))


def _audit(
    auth: AuthContext,
    action: str,
    target_type: str,
    target_id: str,
    details: dict,
) -> None:
    """Write an audit log entry. Non-blocking — failures are logged only."""
    try:
        _db = SessionLocal()
        try:
            actor_user_id = auth.user_id
            actor_email = auth.email
            actor_tenant_id = auth.tenant_id
            if getattr(auth, "is_impersonating", False):
                actor_user_id = getattr(auth, "impersonator_user_id", actor_user_id)
                actor_email = getattr(auth, "impersonator_email", actor_email)
                actor_tenant_id = getattr(auth, "impersonator_tenant_id", actor_tenant_id)
            _db.add(AuditLog(
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                tenant_id=actor_tenant_id,
                action=action,
                category="agent_teams",
                target_type=target_type,
                target_id=str(target_id),
                details_json=json.dumps(details, ensure_ascii=False),
            ))
            _db.commit()
        finally:
            _db.close()
    except Exception as exc:
        logger.error("agent_teams.audit_write_failed", action=action, error=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class StepIn(BaseModel):
    step_order: int
    agent_slug: str
    display_name: Optional[str] = None
    tools_json: Optional[str] = None       # JSON array string: '["knowledge_base"]'
    prompt_override: Optional[str] = None
    model_override: Optional[str] = None
    is_optional: bool = False

    @field_validator("tools_json")
    @classmethod
    def validate_tools_json(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(f"tools_json must be valid JSON: {exc}") from exc
        if not isinstance(parsed, list):
            raise ValueError("tools_json must be a JSON array")
        if not all(isinstance(t, str) for t in parsed):
            raise ValueError("tools_json must be a JSON array of strings")
        return v

    @field_validator("agent_slug")
    @classmethod
    def validate_agent_slug(cls, v: str) -> str:
        if not v or len(v) > 64:
            raise ValueError("agent_slug must be 1–64 characters")
        return v


class TeamCreate(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    lead_agent_slug: Optional[str] = None
    execution_mode: Literal["pipeline", "orchestrator"] = "pipeline"
    input_schema_json: Optional[str] = None
    steps: list[StepIn] = []

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "slug must be lowercase alphanumeric with hyphens, "
                "start and end with alphanumeric, max 64 chars"
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 128:
            raise ValueError("name must be at most 128 characters")
        return v

    @field_validator("input_schema_json")
    @classmethod
    def validate_input_schema_json(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(f"input_schema_json must be valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("input_schema_json must be a JSON object")
        return v

    @model_validator(mode="after")
    def validate_step_orders_unique(self) -> "TeamCreate":
        orders = [s.step_order for s in self.steps]
        if len(orders) != len(set(orders)):
            raise ValueError("step_order values must be unique within a team")
        return self


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    lead_agent_slug: Optional[str] = None
    execution_mode: Optional[Literal["pipeline", "orchestrator"]] = None
    input_schema_json: Optional[str] = None
    is_active: Optional[bool] = None
    steps: Optional[list[StepIn]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("name must not be empty")
            if len(v) > 128:
                raise ValueError("name must be at most 128 characters")
        return v

    @field_validator("input_schema_json")
    @classmethod
    def validate_input_schema_json(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(f"input_schema_json must be valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("input_schema_json must be a JSON object")
        return v

    @model_validator(mode="after")
    def validate_step_orders_unique(self) -> "TeamUpdate":
        if self.steps:
            orders = [s.step_order for s in self.steps]
            if len(orders) != len(set(orders)):
                raise ValueError("step_order values must be unique within a team")
        return self


class TeamRunRequest(BaseModel):
    payload: dict = {}


class ToolCreate(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    tool_class: Optional[str] = None
    config_schema_json: Optional[str] = None
    is_builtin: bool = False

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "slug must be lowercase alphanumeric with hyphens, "
                "start and end with alphanumeric, max 64 chars"
            )
        return v

    @field_validator("config_schema_json")
    @classmethod
    def validate_config_schema_json(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(f"config_schema_json must be valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("config_schema_json must be a JSON object")
        return v


class ToolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tool_class: Optional[str] = None
    config_schema_json: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("config_schema_json")
    @classmethod
    def validate_config_schema_json(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(f"config_schema_json must be valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("config_schema_json must be a JSON object")
        return v


class TeamCloneRequest(BaseModel):
    new_slug: str
    new_name: str

    @field_validator("new_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "new_slug must be lowercase alphanumeric with hyphens, "
                "start and end with alphanumeric, max 64 chars"
            )
        return v

    @field_validator("new_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("new_name must not be empty")
        if len(v) > 128:
            raise ValueError("new_name must be at most 128 characters")
        return v


# ═══════════════════════════════════════════════════════════════════════════════
# SERIALISERS
# ═══════════════════════════════════════════════════════════════════════════════

def _team_to_dict(team) -> dict:
    return {
        "id": team.id,
        "slug": team.slug,
        "name": team.name,
        "description": team.description,
        "lead_agent_slug": team.lead_agent_slug,
        "execution_mode": team.execution_mode,
        "input_schema_json": team.input_schema_json,
        "yaml_version": team.yaml_version,
        "is_active": team.is_active,
        "is_system": team.is_system,
        "created_at": team.created_at.isoformat() if team.created_at else None,
        "updated_at": team.updated_at.isoformat() if team.updated_at else None,
    }


def _step_to_dict(step) -> dict:
    return {
        "id": step.id,
        "team_id": step.team_id,
        "step_order": step.step_order,
        "agent_slug": step.agent_slug,
        "display_name": step.display_name,
        "tools_json": step.tools_json,
        "prompt_override": step.prompt_override,
        "model_override": step.model_override,
        "is_optional": step.is_optional,
    }


def _tool_to_dict(tool) -> dict:
    return {
        "id": tool.id,
        "slug": tool.slug,
        "name": tool.name,
        "description": tool.description,
        "tool_class": tool.tool_class,
        "config_schema_json": tool.config_schema_json,
        "is_builtin": tool.is_builtin,
        "is_active": tool.is_active,
        "tenant_id": tool.tenant_id,
        "created_at": tool.created_at.isoformat() if tool.created_at else None,
    }


def _run_to_dict(run, include_steps: bool = False) -> dict:
    d = {
        "id": run.id,
        "team_slug": run.team_slug,
        "trigger_source": run.trigger_source,
        "success": run.success,
        "duration_ms": run.duration_ms,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
    if include_steps:
        d["payload"] = json.loads(run.payload_json) if run.payload_json else {}
        d["output"] = json.loads(run.output_json) if run.output_json else {}
        d["steps"] = json.loads(run.steps_json) if run.steps_json else []
    return d


# ═══════════════════════════════════════════════════════════════════════════════
# TEAMS — LIST & CREATE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/agent-teams/")
def list_teams(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep

    q = db.query(AgentTeamConfig).filter(AgentTeamConfig.tenant_id == auth.tenant_id)
    if active_only:
        q = q.filter(AgentTeamConfig.is_active == True)
    teams = q.order_by(AgentTeamConfig.name).all()

    if not teams:
        return []

    # Single aggregate query — no N+1
    team_ids = [t.id for t in teams]
    step_counts_rows = (
        db.query(AgentTeamStep.team_id, func.count(AgentTeamStep.id).label("cnt"))
        .filter(AgentTeamStep.team_id.in_(team_ids))
        .group_by(AgentTeamStep.team_id)
        .all()
    )
    count_map = {row.team_id: row.cnt for row in step_counts_rows}

    result = []
    for team in teams:
        d = _team_to_dict(team)
        d["step_count"] = count_map.get(team.id, 0)
        result.append(d)
    return result


@router.post("/admin/agent-teams/", status_code=201)
def create_team(
    body: TeamCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep

    # Slug uniqueness per tenant
    existing = db.query(AgentTeamConfig).filter(
        AgentTeamConfig.tenant_id == auth.tenant_id,
        AgentTeamConfig.slug == body.slug,
    ).first()
    if existing:
        raise HTTPException(409, f"Team slug '{body.slug}' already exists for this tenant")

    team = AgentTeamConfig(
        tenant_id=auth.tenant_id,
        slug=body.slug,
        name=body.name,
        description=body.description,
        lead_agent_slug=body.lead_agent_slug,
        execution_mode=body.execution_mode,
        input_schema_json=body.input_schema_json,
        yaml_version=1,
        is_active=True,
        is_system=False,
    )
    db.add(team)
    db.flush()

    steps = []
    for s in body.steps:
        step = AgentTeamStep(
            team_id=team.id,
            step_order=s.step_order,
            agent_slug=s.agent_slug,
            display_name=s.display_name,
            tools_json=s.tools_json,
            prompt_override=s.prompt_override,
            model_override=s.model_override,
            is_optional=s.is_optional,
        )
        db.add(step)
        steps.append(step)

    db.flush()
    db.commit()
    db.refresh(team)
    # Non-blocking: YAML export runs after response is sent
    background_tasks.add_task(_safe_yaml_export, team, list(steps))
    _audit(auth, "create", "agent_team", team.slug, {"name": team.name, "execution_mode": team.execution_mode})
    return _team_to_dict(team)


# ═══════════════════════════════════════════════════════════════════════════════
# TEAMS — DETAIL, UPDATE, DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/agent-teams/{slug}/detail")
def get_team_detail(
    slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep

    team = db.query(AgentTeamConfig).filter(
        AgentTeamConfig.tenant_id == auth.tenant_id,
        AgentTeamConfig.slug == slug,
    ).first()
    if not team:
        raise HTTPException(404, "Team not found")

    steps = db.query(AgentTeamStep).filter(
        AgentTeamStep.team_id == team.id
    ).order_by(AgentTeamStep.step_order).all()

    result = _team_to_dict(team)
    result["steps"] = [_step_to_dict(s) for s in steps]
    return result


@router.put("/admin/agent-teams/{slug}")
def update_team(
    slug: str,
    body: TeamUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep

    team = db.query(AgentTeamConfig).filter(
        AgentTeamConfig.tenant_id == auth.tenant_id,
        AgentTeamConfig.slug == slug,
    ).first()
    if not team:
        raise HTTPException(404, "Team not found")

    if body.name is not None:
        team.name = body.name
    if body.description is not None:
        team.description = body.description
    if body.lead_agent_slug is not None:
        team.lead_agent_slug = body.lead_agent_slug
    if body.execution_mode is not None:
        team.execution_mode = body.execution_mode
    if body.input_schema_json is not None:
        team.input_schema_json = body.input_schema_json
    if body.is_active is not None:
        team.is_active = body.is_active

    if body.steps is not None:
        # Replace all steps atomically
        db.query(AgentTeamStep).filter(AgentTeamStep.team_id == team.id).delete()
        db.flush()
        new_steps = []
        for s in body.steps:
            step = AgentTeamStep(
                team_id=team.id,
                step_order=s.step_order,
                agent_slug=s.agent_slug,
                display_name=s.display_name,
                tools_json=s.tools_json,
                prompt_override=s.prompt_override,
                model_override=s.model_override,
                is_optional=s.is_optional,
            )
            db.add(step)
            new_steps.append(step)
        db.flush()
        team.yaml_version = (team.yaml_version or 1) + 1
        background_tasks.add_task(_safe_yaml_export, team, list(new_steps))

    team.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(team)
    _audit(auth, "update", "agent_team", team.slug, {"name": team.name, "yaml_version": team.yaml_version})
    return _team_to_dict(team)


@router.delete("/admin/agent-teams/{slug}", status_code=204)
def delete_team(
    slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    from app.swarm.team_models import AgentTeamConfig

    team = db.query(AgentTeamConfig).filter(
        AgentTeamConfig.tenant_id == auth.tenant_id,
        AgentTeamConfig.slug == slug,
    ).first()
    if not team:
        raise HTTPException(404, "Team not found")

    # System teams: only system_admin can delete
    if team.is_system and auth.role != "system_admin":
        raise HTTPException(403, "Only system_admin can delete system teams")

    # Soft-delete
    team.is_active = False
    team.updated_at = datetime.now(timezone.utc)
    db.commit()
    _audit(auth, "delete", "agent_team", team.slug, {"name": team.name, "is_system": team.is_system})


# ═══════════════════════════════════════════════════════════════════════════════
# CLONE
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/admin/agent-teams/{slug}/clone", status_code=201)
def clone_team(
    slug: str,
    body: TeamCloneRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep

    source = db.query(AgentTeamConfig).filter(
        AgentTeamConfig.tenant_id == auth.tenant_id,
        AgentTeamConfig.slug == slug,
    ).first()
    if not source:
        raise HTTPException(404, "Team not found")

    # Ensure new slug is unique for this tenant
    conflict = db.query(AgentTeamConfig).filter(
        AgentTeamConfig.tenant_id == auth.tenant_id,
        AgentTeamConfig.slug == body.new_slug,
    ).first()
    if conflict:
        raise HTTPException(409, f"Team slug '{body.new_slug}' already exists for this tenant")

    clone = AgentTeamConfig(
        tenant_id=auth.tenant_id,
        slug=body.new_slug,
        name=body.new_name,
        description=source.description,
        lead_agent_slug=source.lead_agent_slug,
        execution_mode=source.execution_mode,
        input_schema_json=source.input_schema_json,
        yaml_version=1,
        is_active=True,
        is_system=False,  # clones are never system teams
    )
    db.add(clone)
    db.flush()  # populate clone.id

    source_steps = db.query(AgentTeamStep).filter(
        AgentTeamStep.team_id == source.id
    ).order_by(AgentTeamStep.step_order).all()

    cloned_steps = []
    for s in source_steps:
        step = AgentTeamStep(
            team_id=clone.id,
            step_order=s.step_order,
            agent_slug=s.agent_slug,
            display_name=s.display_name,
            tools_json=s.tools_json,
            prompt_override=s.prompt_override,
            model_override=s.model_override,
            is_optional=s.is_optional,
        )
        db.add(step)
        cloned_steps.append(step)

    db.flush()
    db.commit()
    db.refresh(clone)
    background_tasks.add_task(_safe_yaml_export, clone, list(cloned_steps))
    _audit(auth, "clone", "agent_team", clone.slug, {"source_slug": slug, "name": clone.name})
    return _team_to_dict(clone)


# ═══════════════════════════════════════════════════════════════════════════════
# RUNS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/admin/agent-teams/{slug}/run", status_code=201)
async def run_team(
    slug: str,
    body: TeamRunRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep
    from app.swarm.base_team import AgentContext, DBDelegatingTeam

    team = db.query(AgentTeamConfig).filter(
        AgentTeamConfig.tenant_id == auth.tenant_id,
        AgentTeamConfig.slug == slug,
        AgentTeamConfig.is_active == True,
    ).first()
    if not team:
        raise HTTPException(404, "Team not found or inactive")

    steps = db.query(AgentTeamStep).filter(
        AgentTeamStep.team_id == team.id
    ).order_by(AgentTeamStep.step_order).all()

    context = AgentContext(
        tenant_id=auth.tenant_id,
        tenant_slug=auth.tenant_slug,
        user_id=auth.user_id,
    )

    delegating_team = DBDelegatingTeam(team, steps)
    result = await delegating_team.run_and_save(
        body.payload,
        context,
        db,
        triggered_by_user_id=auth.user_id,
        trigger_source="api",
    )

    # run_id is set directly by run_and_save() — no race condition
    return {
        "run_id": result.run_id,
        "success": result.success,
        "error": result.error,
        "duration_ms": result.duration_ms,
        "output": result.output,
        "steps": [s.to_dict() for s in result.steps],
    }


# NOTE: Runs use /admin/agent-runs/ prefix (NOT /agent-teams/runs/) to avoid
# FastAPI route shadowing where "runs" would match the {slug} path parameter.

@router.get("/admin/agent-runs/")
def list_all_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    team_slug: Optional[str] = Query(None, description="Filter by team slug"),
    success: Optional[bool] = Query(None, description="Filter by success/failure"),
    started_after: Optional[datetime] = Query(None, description="Filter runs started after this ISO datetime"),
    started_before: Optional[datetime] = Query(None, description="Filter runs started before this ISO datetime"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.run_models import AgentTeamRun

    q = db.query(AgentTeamRun).filter(AgentTeamRun.tenant_id == auth.tenant_id)

    if team_slug:
        q = q.filter(AgentTeamRun.team_slug == team_slug)
    if success is not None:
        q = q.filter(AgentTeamRun.success == success)
    if started_after:
        q = q.filter(AgentTeamRun.started_at >= started_after)
    if started_before:
        q = q.filter(AgentTeamRun.started_at <= started_before)

    total = q.count()
    runs = q.order_by(AgentTeamRun.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_run_to_dict(r) for r in runs],
    }


@router.get("/admin/agent-runs/{run_id}")
def get_run_detail(
    run_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.run_models import AgentTeamRun

    run = db.query(AgentTeamRun).filter(
        AgentTeamRun.id == run_id,
        AgentTeamRun.tenant_id == auth.tenant_id,
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")
    return _run_to_dict(run, include_steps=True)


@router.get("/admin/agent-teams/{slug}/runs")
def list_team_runs(
    slug: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.run_models import AgentTeamRun

    q = db.query(AgentTeamRun).filter(
        AgentTeamRun.tenant_id == auth.tenant_id,
        AgentTeamRun.team_slug == slug,
    )
    total = q.count()
    runs = q.order_by(AgentTeamRun.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_run_to_dict(r) for r in runs],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/agent-tools/")
def list_tools(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentToolDefinition
    from sqlalchemy import or_

    # Return global builtins (tenant_id IS NULL) plus tenant-scoped custom tools
    q = db.query(AgentToolDefinition).filter(
        or_(
            AgentToolDefinition.tenant_id == None,
            AgentToolDefinition.tenant_id == auth.tenant_id,
        )
    )
    if active_only:
        q = q.filter(AgentToolDefinition.is_active == True)
    tools = q.order_by(AgentToolDefinition.name).all()
    return [_tool_to_dict(t) for t in tools]


@router.post("/admin/agent-tools/", status_code=201)
def create_tool(
    body: ToolCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentToolDefinition
    from sqlalchemy import or_

    # Builtin tools can only be created by system_admin
    if body.is_builtin and auth.role != "system_admin":
        raise HTTPException(403, "Only system_admin can create builtin tools")

    # Slug uniqueness: check global builtins + this tenant's custom tools
    existing = db.query(AgentToolDefinition).filter(
        AgentToolDefinition.slug == body.slug,
        or_(
            AgentToolDefinition.tenant_id == None,
            AgentToolDefinition.tenant_id == auth.tenant_id,
        ),
    ).first()
    if existing:
        raise HTTPException(409, f"Tool slug '{body.slug}' already exists")

    tool = AgentToolDefinition(
        tenant_id=None if body.is_builtin else auth.tenant_id,
        slug=body.slug,
        name=body.name,
        description=body.description,
        tool_class=body.tool_class,
        config_schema_json=body.config_schema_json,
        is_builtin=body.is_builtin,
        is_active=True,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    _audit(auth, "create", "agent_tool", tool.slug, {"name": tool.name, "is_builtin": tool.is_builtin})
    return _tool_to_dict(tool)


@router.put("/admin/agent-tools/{slug}")
def update_tool(
    slug: str,
    body: ToolUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentToolDefinition
    from sqlalchemy import or_

    tool = db.query(AgentToolDefinition).filter(
        AgentToolDefinition.slug == slug,
        or_(
            AgentToolDefinition.tenant_id == None,
            AgentToolDefinition.tenant_id == auth.tenant_id,
        ),
    ).first()
    if not tool:
        raise HTTPException(404, "Tool not found")

    # Builtin tools: only system_admin can modify
    if tool.is_builtin and auth.role != "system_admin":
        raise HTTPException(403, "Only system_admin can modify builtin tools")

    if body.name is not None:
        tool.name = body.name
    if body.description is not None:
        tool.description = body.description
    if body.tool_class is not None:
        tool.tool_class = body.tool_class
    if body.config_schema_json is not None:
        tool.config_schema_json = body.config_schema_json
    if body.is_active is not None:
        tool.is_active = body.is_active

    tool.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tool)
    _audit(auth, "update", "agent_tool", tool.slug, {"name": tool.name})
    return _tool_to_dict(tool)


@router.delete("/admin/agent-tools/{slug}", status_code=204)
def delete_tool(
    slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentToolDefinition
    from sqlalchemy import or_

    tool = db.query(AgentToolDefinition).filter(
        AgentToolDefinition.slug == slug,
        or_(
            AgentToolDefinition.tenant_id == None,
            AgentToolDefinition.tenant_id == auth.tenant_id,
        ),
    ).first()
    if not tool:
        raise HTTPException(404, "Tool not found")

    # Builtin tools: only system_admin can delete
    if tool.is_builtin and auth.role != "system_admin":
        raise HTTPException(403, "Only system_admin can delete builtin tools")

    _audit(auth, "delete", "agent_tool", tool.slug, {"name": tool.name, "is_builtin": tool.is_builtin})
    db.delete(tool)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL USAGE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/agent-tools/usage-summary")
def get_tools_usage_summary(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    """Return {tool_slug: team_count} for all tools referenced by this tenant's active steps."""
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep

    rows = (
        db.query(AgentTeamStep.tools_json)
        .join(AgentTeamConfig, AgentTeamStep.team_id == AgentTeamConfig.id)
        .filter(AgentTeamConfig.tenant_id == auth.tenant_id)
        .all()
    )
    counts: dict = {}
    for (tools_json,) in rows:
        if tools_json:
            try:
                slugs = json.loads(tools_json)
                for s in slugs:
                    if isinstance(s, str):
                        counts[s] = counts.get(s, 0) + 1
            except Exception:
                pass
    return counts


@router.get("/admin/agent-tools/{slug}/usage")
def get_tool_usage(
    slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    """Return which teams (and step positions) reference this tool."""
    _require_team_access(auth)
    _require_feature(auth)
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep

    rows = (
        db.query(AgentTeamStep, AgentTeamConfig)
        .join(AgentTeamConfig, AgentTeamStep.team_id == AgentTeamConfig.id)
        .filter(AgentTeamConfig.tenant_id == auth.tenant_id)
        .all()
    )

    usages = []
    for step, team in rows:
        if step.tools_json:
            try:
                slugs = json.loads(step.tools_json)
            except Exception:
                slugs = []
            if slug in slugs:
                usages.append({
                    "team_slug": team.slug,
                    "team_name": team.name,
                    "step_order": step.step_order,
                    "step_display_name": step.display_name,
                })

    return {"tool_slug": slug, "usage_count": len(usages), "usages": usages}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT DEFINITIONS (read-only, for dropdowns)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/agent-definitions/")
def list_agent_definitions(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    _require_team_access(auth)
    _require_feature(auth)
    try:
        from app.ai_config.models import AgentDefinition
        agents = db.query(AgentDefinition).filter(
            AgentDefinition.is_active == True
        ).order_by(AgentDefinition.name).all()
        return [
            {
                "id": a.id,
                "slug": a.slug,
                "name": a.name,
                "description": a.description,
                "default_model": a.default_model,
                "default_tools_json": a.default_tools_json,
            }
            for a in agents
        ]
    except Exception as exc:
        logger.warning("agent_definitions.list_failed", error=str(exc))
        return []
