"""app/swarm/base_team.py — Abstract base for Agent Teams.

Provides:
- AgentContext: resolved per-request context (tenant_id, user_id, slug)
- PipelineStep: single step result with timing + error
- TeamResult: full run result with structured steps
- BaseAgentTeam: abstract interface all teams implement
- DBDelegatingTeam: loads pipeline from DB and runs steps
- load_db_teams(): loads all active teams into the team registry
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()

# ─── Registry ─────────────────────────────────────────────────────────────────

_TEAM_REGISTRY: dict[str, type["BaseAgentTeam"]] = {}


def register_team(slug: str):
    """Decorator to register a team class by slug."""
    def decorator(cls: type[BaseAgentTeam]):
        _TEAM_REGISTRY[slug] = cls
        return cls
    return decorator


def get_team(slug: str) -> type["BaseAgentTeam"] | None:
    return _TEAM_REGISTRY.get(slug)


def list_teams() -> list[str]:
    return list(_TEAM_REGISTRY.keys())


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class AgentContext:
    """Resolved per-request context, set once by the framework."""
    tenant_id: int
    tenant_slug: str
    user_id: int | None = None


@dataclass
class PipelineStep:
    name: str
    status: str = "pending"        # "pending" | "running" | "completed" | "failed" | "skipped"
    duration_ms: int = 0
    output: Any = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class TeamResult:
    success: bool = False
    output: Any = None
    steps: list[PipelineStep] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0
    run_id: int | None = None   # Set by run_and_save() — callers use this for run reference

    def steps_as_json(self) -> str:
        return json.dumps([s.to_dict() for s in self.steps])


# ─── Base Class ───────────────────────────────────────────────────────────────

class BaseAgentTeam(ABC):
    """Abstract base for all agent teams."""

    slug: str = ""
    name: str = ""
    description: str = ""

    @abstractmethod
    async def run(self, payload: dict, context: AgentContext, db=None) -> TeamResult:
        """Execute the team with the given payload. Override in subclasses."""
        raise NotImplementedError

    async def run_and_save(
        self,
        payload: dict,
        context: AgentContext,
        db,
        *,
        triggered_by_user_id: int | None = None,
        trigger_source: str = "api",
        timeout_seconds: float = 300.0,
    ) -> TeamResult:
        """Execute the team and persist a run record to the DB.

        Design guarantees:
        - The AgentTeamRun row is committed BEFORE execution, so it survives any rollback.
        - If execution raises or times out, db is rolled back, then the run record is
          updated in a fresh flush (so run history is always complete).
        - run_id is attached to the returned TeamResult.
        """
        from app.swarm.run_models import AgentTeamRun

        run = AgentTeamRun(
            tenant_id=context.tenant_id,
            team_slug=self.slug,
            triggered_by_user_id=triggered_by_user_id,
            trigger_source=trigger_source,
            payload_json=json.dumps(payload),
            success=False,
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()          # Commit immediately — run record survives any downstream rollback
        db.refresh(run)
        run_id = run.id

        t0 = time.monotonic()
        result: TeamResult
        try:
            result = await asyncio.wait_for(
                self.run(payload, context, db),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                "base_team.run_timeout",
                slug=self.slug,
                timeout_seconds=timeout_seconds,
            )
            try:
                db.rollback()
            except Exception:
                pass
            result = TeamResult(
                success=False,
                error=f"Execution timed out after {timeout_seconds:.0f}s",
            )
        except Exception as exc:
            logger.error("base_team.run_error", slug=self.slug, error=str(exc))
            try:
                db.rollback()
            except Exception:
                pass
            result = TeamResult(success=False, error=str(exc))

        result.duration_ms = result.duration_ms or int((time.monotonic() - t0) * 1000)
        result.run_id = run_id

        # Update the persisted run record. After a potential rollback the run object
        # may be detached — re-fetch by PK to get a clean, session-bound instance.
        try:
            run_record = db.get(AgentTeamRun, run_id)
            if run_record is None:
                # Session was reset; use merge to re-attach and update
                run.success = result.success
                run.error_message = result.error
                run.duration_ms = result.duration_ms
                run.steps_json = result.steps_as_json()
                run.output_json = json.dumps(result.output) if result.output is not None else None
                run.completed_at = datetime.now(timezone.utc)
                db.merge(run)
            else:
                run_record.success = result.success
                run_record.error_message = result.error
                run_record.duration_ms = result.duration_ms
                run_record.steps_json = result.steps_as_json()
                run_record.output_json = (
                    json.dumps(result.output) if result.output is not None else None
                )
                run_record.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            logger.error(
                "base_team.run_update_failed",
                slug=self.slug,
                run_id=run_id,
                error=str(exc),
            )

        return result

    def _step(self, name: str) -> "_StepContext":
        """Context manager helper for timing + error isolation."""
        return _StepContext(name)


class _StepContext:
    """Context manager that times a step and captures errors.

    Only suppresses Exception subclasses — BaseException (KeyboardInterrupt,
    SystemExit, GeneratorExit) is always re-raised so the process can shut down.
    """

    def __init__(self, name: str):
        self.step = PipelineStep(name=name)
        self._start = 0.0

    def __enter__(self) -> PipelineStep:
        self.step.status = "running"
        self._start = time.monotonic()
        return self.step

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.monotonic() - self._start
        self.step.duration_ms = int(elapsed * 1000)
        if exc_type is None:
            self.step.status = "completed"
            return False
        # Propagate BaseException (KeyboardInterrupt, SystemExit, GeneratorExit)
        if not issubclass(exc_type, Exception):
            self.step.status = "failed"
            self.step.error = str(exc_val)
            return False  # re-raise
        # Suppress regular Exception — step is optional by convention here
        self.step.status = "failed"
        self.step.error = str(exc_val)
        logger.warning("team_step.failed", step=self.step.name, error=str(exc_val))
        return True


# ─── DB-Delegating Team ────────────────────────────────────────────────────────

class DBDelegatingTeam(BaseAgentTeam):
    """Generic team that reads its pipeline from DB and executes steps sequentially.

    For execution_mode=orchestrator, it delegates to the registered Python orchestrator.
    For execution_mode=pipeline, it runs agents sequentially passing output as context.
    """

    def __init__(self, team_config, steps: list):
        self._config = team_config
        self._steps = sorted(steps, key=lambda s: s.step_order)
        self.slug = team_config.slug
        self.name = team_config.name

    async def run(self, payload: dict, context: AgentContext, db=None) -> TeamResult:
        start = time.monotonic()
        result = TeamResult()

        if self._config.execution_mode == "orchestrator":
            result = await self._run_orchestrator(payload, context, db)
        else:
            result = await self._run_pipeline(payload, context, db)

        result.duration_ms = int((time.monotonic() - start) * 1000)
        return result

    async def _run_orchestrator(self, payload: dict, context: AgentContext, db) -> TeamResult:
        """Delegate to registered Python orchestrators for campaign/media teams."""
        result = TeamResult()
        slug = self._config.slug

        try:
            if slug == "campaign-generation":
                from app.swarm.agents.campaign.orchestrator import (
                    CampaignOrchestrator, CampaignGenerationRequest,
                )
                from app.swarm.llm import LLMClient
                llm = LLMClient()
                orch = CampaignOrchestrator(llm)
                req = CampaignGenerationRequest(
                    campaign_name=payload.get("campaign_name", "Campaign"),
                    channel=payload.get("channel", "email"),
                    tone=payload.get("tone", "professional"),
                    prompt=payload.get("prompt", ""),
                    tenant_id=context.tenant_id,
                    template_id=payload.get("template_id"),
                    use_knowledge=payload.get("use_knowledge", True),
                    use_chat_history=payload.get("use_chat_history", False),
                )
                gen_result = await orch.run(req, db)
                step = PipelineStep(name="campaign-generation", status="completed")
                step.output = {
                    "subject": gen_result.subject,
                    "body": gen_result.body,
                    "html": gen_result.html,
                    "qa_passed": gen_result.qa_passed,
                }
                result.steps = [step]
                result.output = step.output
                result.success = gen_result.error is None
                if gen_result.error:
                    result.error = gen_result.error

            elif slug == "media-generation":
                from app.swarm.agents.media.orchestrator import MediaOrchestrator
                from app.swarm.llm import LLMClient
                llm = LLMClient()
                orch = MediaOrchestrator(llm)
                gen_result = await orch.run(payload, context.tenant_id, db)
                step = PipelineStep(name="media-generation", status="completed")
                step.output = gen_result if isinstance(gen_result, dict) else {"result": str(gen_result)}
                result.steps = [step]
                result.output = step.output
                result.success = True

            else:
                result.error = f"No orchestrator registered for slug '{slug}'"
                result.success = False

        except Exception as exc:
            logger.error("db_delegating_team.orchestrator_error", slug=slug, error=str(exc))
            result.error = str(exc)
            result.success = False

        return result

    async def _run_pipeline(self, payload: dict, context: AgentContext, db) -> TeamResult:
        """Sequential pipeline: output of step N is passed as context to step N+1.

        The running context is built as a new dict on each step to avoid mutating
        the original payload or exposing internal state across step boundaries.
        """
        result = TeamResult()
        current_context: dict = dict(payload)  # shallow copy of input

        for step_cfg in self._steps:
            step = PipelineStep(name=step_cfg.display_name or step_cfg.agent_slug)
            result.steps.append(step)
            step.status = "running"
            t0 = time.monotonic()

            try:
                agent_output = await _invoke_agent_step(step_cfg, current_context, context, db)
                step.output = agent_output
                step.status = "completed"
                # Merge agent output into running context for next step (new dict each iteration)
                if isinstance(agent_output, dict):
                    current_context = {**current_context, **agent_output}
                else:
                    current_context = {**current_context, "last_output": str(agent_output)}
            except Exception as exc:
                step.status = "failed"
                step.error = str(exc)
                logger.warning(
                    "pipeline_step.failed",
                    team=self.slug,
                    step=step_cfg.agent_slug,
                    error=str(exc),
                )
                step.duration_ms = int((time.monotonic() - t0) * 1000)
                if not step_cfg.is_optional:
                    result.error = f"Step '{step.name}' failed: {exc}"
                    result.success = False
                    return result
                continue

            step.duration_ms = int((time.monotonic() - t0) * 1000)

        result.success = True
        result.output = current_context
        return result


def _build_slug_agent_map() -> dict:
    """Build a slug → agent class map. Logs a warning if any import fails."""
    agents: dict = {}
    _imports = [
        ("ops", "app.swarm.agents.ops", "AgentOps"),
        ("sales", "app.swarm.agents.sales", "AgentSales"),
        ("medic", "app.swarm.agents.medic", "AgentMedic"),
        ("vision", "app.swarm.agents.vision", "AgentVision"),
        ("persona", "app.swarm.agents.persona", "AgentPersona"),
    ]
    for slug, module_path, class_name in _imports:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            agents[slug] = getattr(mod, class_name)
        except Exception as exc:
            logger.warning(
                "base_team.agent_import_failed",
                slug=slug,
                module=module_path,
                error=str(exc),
            )
    return agents


# Lazily initialised on first use — avoids import-time failures blocking startup.
_SLUG_AGENT_MAP: dict | None = None


def _get_slug_agent_map() -> dict:
    global _SLUG_AGENT_MAP
    if _SLUG_AGENT_MAP is None:
        _SLUG_AGENT_MAP = _build_slug_agent_map()
    return _SLUG_AGENT_MAP


async def _invoke_agent_step(step_cfg, payload: dict, context: AgentContext, db) -> Any:
    """Look up the agent by slug and invoke it with the payload as a message."""
    agent_slug = step_cfg.agent_slug
    slug_map = _get_slug_agent_map()

    agent_cls = slug_map.get(agent_slug)
    if agent_cls is None:
        raise ValueError(
            f"Unknown agent slug '{agent_slug}'. "
            f"Available: {sorted(slug_map.keys())}"
        )

    agent = agent_cls()
    message = payload.get("message") or json.dumps(payload)
    response = await agent.handle(message)
    return {"response": response.content if hasattr(response, "content") else str(response)}


# ─── Registry Loader ──────────────────────────────────────────────────────────

def load_db_teams(db) -> dict[str, DBDelegatingTeam]:
    """Load all active teams from DB and return a slug→team map.

    Called at startup to pre-warm the registry.
    """
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep

    teams: dict[str, DBDelegatingTeam] = {}
    try:
        configs = db.query(AgentTeamConfig).filter(AgentTeamConfig.is_active == True).all()
        for cfg in configs:
            steps = db.query(AgentTeamStep).filter(
                AgentTeamStep.team_id == cfg.id
            ).order_by(AgentTeamStep.step_order).all()
            teams[cfg.slug] = DBDelegatingTeam(cfg, steps)
    except Exception as exc:
        logger.warning("load_db_teams.failed", error=str(exc))
    return teams
