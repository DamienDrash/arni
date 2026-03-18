"""OrchestratorManager — single source of truth for all orchestrator configs."""
from __future__ import annotations
import json, copy
from datetime import datetime, timezone
from typing import Any
import structlog
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.orchestration.models import OrchestratorDefinition, OrchestratorVersion, OrchestratorTenantOverride

logger = structlog.get_logger()

IMMUTABLE_GUARDRAILS = {
    "quality-gate": {"qa_gate.enabled": True},  # cannot be set to False
}

MAX_GUARDRAILS = {
    "swarm-orchestrator": {"intent_classifier.max_revision_rounds": 3},
}


class OrchestratorManager:
    def __init__(self, db: Session):
        self._db = db

    def get_config(self, name: str, tenant_id: int | None = None) -> dict:
        orch = self._get_or_404(name)
        config = copy.deepcopy(orch.config_current or {})
        if tenant_id:
            override = self._db.query(OrchestratorTenantOverride).filter(
                OrchestratorTenantOverride.orchestrator_id == orch.id,
                OrchestratorTenantOverride.tenant_id == tenant_id,
            ).first()
            if override and override.config_override:
                config.update(override.config_override)
        return config

    def update_config(self, name: str, patch: dict, updated_by: int, change_summary: str = "") -> OrchestratorVersion:
        orch = self._get_or_404(name)
        self._check_guardrails(name, patch)
        new_config = copy.deepcopy(orch.config_current or {})
        new_config.update(patch)
        now = datetime.now(timezone.utc)
        version = OrchestratorVersion(
            orchestrator_id=orch.id,
            version=orch.config_version,
            config_snapshot=copy.deepcopy(orch.config_current),
            changed_by=updated_by,
            changed_at=now,
            rollback_safe=True,
            change_summary=change_summary,
        )
        self._db.add(version)
        orch.config_current = new_config
        orch.config_version += 1
        orch.updated_at = now
        orch.updated_by = updated_by
        self._db.commit()
        self._db.refresh(version)
        self._invalidate_cache(name)
        logger.info("orchestrator.config_updated", name=name, version=orch.config_version, by=updated_by)
        return version

    def set_state(self, name: str, new_state: str, changed_by: int) -> None:
        valid_transitions = {
            "ACTIVE": {"PAUSED", "DRAINING", "DISABLED"},
            "PAUSED": {"ACTIVE", "DISABLED"},
            "DRAINING": {"ACTIVE", "DISABLED"},
            "DISABLED": set(),
        }
        orch = self._get_or_404(name)
        if new_state not in valid_transitions.get(orch.status, set()):
            raise HTTPException(422, f"Invalid transition {orch.status} \u2192 {new_state}")
        orch.status = new_state
        orch.updated_at = datetime.now(timezone.utc)
        orch.updated_by = changed_by
        self._db.commit()
        logger.info("orchestrator.state_changed", name=name, new_state=new_state)

    def rollback(self, name: str, target_version: int, changed_by: int) -> OrchestratorVersion:
        orch = self._get_or_404(name)
        target = self._db.query(OrchestratorVersion).filter(
            OrchestratorVersion.orchestrator_id == orch.id,
            OrchestratorVersion.version == target_version,
        ).first()
        if not target:
            raise HTTPException(404, f"Version {target_version} not found")
        if not target.rollback_safe:
            raise HTTPException(409, f"Version {target_version} is not rollback-safe")
        return self.update_config(name, target.config_snapshot or {}, changed_by, f"Rollback to v{target_version}")

    def list_versions(self, name: str) -> list:
        orch = self._get_or_404(name)
        return self._db.query(OrchestratorVersion).filter(
            OrchestratorVersion.orchestrator_id == orch.id
        ).order_by(OrchestratorVersion.version.desc()).all()

    def list_all(self) -> list[OrchestratorDefinition]:
        return self._db.query(OrchestratorDefinition).order_by(OrchestratorDefinition.name).all()

    def _get_or_404(self, name: str) -> OrchestratorDefinition:
        orch = self._db.query(OrchestratorDefinition).filter(OrchestratorDefinition.name == name).first()
        if not orch:
            raise HTTPException(404, f"Orchestrator '{name}' not found")
        return orch

    def _check_guardrails(self, name: str, patch: dict) -> None:
        for field, required_value in IMMUTABLE_GUARDRAILS.get(name, {}).items():
            keys = field.split(".")
            val = patch
            for k in keys:
                if not isinstance(val, dict):
                    break
                val = val.get(k)
            if val is not None and val != required_value:
                raise HTTPException(422, f"Guardrail violation: {field} cannot be changed from {required_value}")
        for field, max_val in MAX_GUARDRAILS.get(name, {}).items():
            keys = field.split(".")
            val = patch
            for k in keys:
                if not isinstance(val, dict):
                    break
                val = val.get(k)
            if val is not None and isinstance(val, (int, float)) and val > max_val:
                raise HTTPException(422, f"Guardrail violation: {field} cannot exceed {max_val}")

    def _invalidate_cache(self, name: str) -> None:
        try:
            import redis as redis_lib
            from config.settings import get_settings
            s = get_settings()
            r = redis_lib.from_url(s.redis_url or "redis://localhost:6379/1")
            r.publish("swarm:config:updated", json.dumps({"orchestrator_name": name, "tenant_id": None}))
            r.delete(f"orch:config:{name}:global")
        except Exception as e:
            logger.warning("orchestrator.cache_invalidation_failed", error=str(e))


def get_orchestrator_manager(db: Session) -> OrchestratorManager:
    return OrchestratorManager(db)
