"""ARIIA Swarm v3 — Core Contracts.

Frozen dataclasses shared across all swarm components:
agents, tools, intent classifier, confirmation gate, QA judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context injected into every agent/tool execution."""

    tenant_id: int
    tenant_slug: str
    plan_slug: str
    active_integrations: frozenset[str]
    settings: dict[str, Any]
    member_id: str | None = None
    session_id: str | None = None
    user_name: str = ""
    phone_number: str = ""


@dataclass(frozen=True)
class AgentTask:
    """Immutable task passed from the LeadAgent to an expert agent."""

    task_id: str
    agent_id: str
    original_message: str
    intent_payload: dict[str, Any]
    tenant_context: TenantContext
    conversation_history: tuple[dict[str, str], ...] = ()
    requires_confirmation_token: str | None = None


@dataclass
class AgentResult:
    """Result returned by an expert agent to the LeadAgent."""

    agent_id: str
    content: str
    confidence: float = 1.0
    requires_confirmation: bool = False
    confirmation_prompt: str | None = None
    confirmation_action: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result returned by a SkillTool execution."""

    success: bool
    data: Any = None
    error_message: str | None = None


@dataclass(frozen=True)
class IntentResult:
    """Result from the IntentClassifier."""

    agent_id: str
    confidence: float
    extracted: dict[str, Any] = field(default_factory=dict)
