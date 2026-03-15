"""app/swarm/team_yaml.py — YAML versioning for Agent Team configs.

On every save, the team config is exported to data/teams/{slug}.yaml.
This makes team definitions git-trackable and rollback-capable.

Security: slugs are validated against a strict regex before use in file paths.
Concurrency: a threading.Lock prevents races when background tasks write simultaneously.
"""

from __future__ import annotations

import json
import os
import re
import threading
from typing import TYPE_CHECKING

import structlog
import yaml

if TYPE_CHECKING:
    from app.swarm.team_models import AgentTeamConfig

logger = structlog.get_logger()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEAMS_DIR = os.path.join(BASE_DIR, "data", "teams")

# Only lowercase alphanumeric + hyphens; must start/end with alphanumeric; max 64 chars.
_SLUG_RE = re.compile(r'^[a-z0-9]([a-z0-9\-]{0,62}[a-z0-9])?$')

# Serialise concurrent YAML writes so two background tasks can't clobber each other.
_WRITE_LOCK = threading.Lock()


def _ensure_teams_dir() -> None:
    os.makedirs(TEAMS_DIR, exist_ok=True)


def _safe_path(slug: str) -> str:
    """Return the absolute file path for a team YAML, validating against path traversal.

    Raises ValueError for invalid or path-traversing slugs.
    """
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid team slug {slug!r}: must be lowercase alphanumeric with hyphens (max 64 chars)"
        )
    path = os.path.realpath(os.path.join(TEAMS_DIR, f"{slug}.yaml"))
    teams_dir_real = os.path.realpath(TEAMS_DIR)
    # Ensure resolved path stays within TEAMS_DIR
    if not (path == teams_dir_real or path.startswith(teams_dir_real + os.sep)):
        raise ValueError(f"Path traversal detected for slug {slug!r}")
    return path


def export_team_yaml(team: "AgentTeamConfig", steps: list) -> str:
    """Export a team config + its steps to a YAML file.

    Returns the path of the written file.
    Raises ValueError if the slug is invalid.
    """
    _ensure_teams_dir()
    path = _safe_path(team.slug)

    steps_data = []
    for step in sorted(steps, key=lambda s: s.step_order):
        step_dict: dict = {
            "step_order": step.step_order,
            "agent_slug": step.agent_slug,
        }
        if step.display_name:
            step_dict["display_name"] = step.display_name
        if step.tools_json:
            try:
                step_dict["tools"] = json.loads(step.tools_json)
            except Exception:
                step_dict["tools"] = []
        if step.prompt_override:
            step_dict["prompt_override"] = step.prompt_override
        if step.model_override:
            step_dict["model_override"] = step.model_override
        if step.is_optional:
            step_dict["is_optional"] = True
        steps_data.append(step_dict)

    input_schema = None
    if team.input_schema_json:
        try:
            input_schema = json.loads(team.input_schema_json)
        except Exception:
            input_schema = None

    doc: dict = {
        "version": team.yaml_version,
        "slug": team.slug,
        "name": team.name,
        "execution_mode": team.execution_mode,
        "steps": steps_data,
    }
    if team.description:
        doc["description"] = team.description
    if team.lead_agent_slug:
        doc["lead_agent_slug"] = team.lead_agent_slug
    if input_schema:
        doc["input_schema"] = input_schema

    # Atomic write: write to a temp file then os.replace() — prevents partial reads
    # if the process is killed mid-write (e.g. during a rolling update).
    tmp_path = path + ".tmp"
    with _WRITE_LOCK:
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                yaml.dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            os.replace(tmp_path, path)  # atomic on POSIX; best-effort on Windows
        finally:
            # Clean up temp file if os.replace() failed
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

    logger.info("team_yaml.exported", slug=team.slug, version=team.yaml_version, path=path)
    return path


def load_team_yaml(slug: str) -> dict | None:
    """Load a team YAML file by slug. Returns None if not found."""
    try:
        path = _safe_path(slug)
    except ValueError:
        logger.warning("team_yaml.load_invalid_slug", slug=slug)
        return None
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
