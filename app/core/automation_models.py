"""ARIIA v2.1 – Automation Workflow Models.

Defines the data models for the automation engine:
- AutomationWorkflow: Workflow definition with trigger config and graph
- AutomationRun: Individual contact run through a workflow
- AutomationRunLog: Audit trail for each executed node
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index,
)
from sqlalchemy.orm import relationship
from app.core.db import Base


# ─── Automation Workflow ─────────────────────────────────────────────────────

class AutomationWorkflow(Base):
    """Definition of an automation workflow.

    The workflow_graph_json stores the complete React Flow graph definition
    including nodes (trigger, actions, conditions, waits) and edges.

    Trigger types:
        - segment_entry: Contact enters a segment
        - segment_exit: Contact leaves a segment
        - contact_created: New contact is created
        - tag_added: A tag is added to a contact
        - tag_removed: A tag is removed from a contact
        - lifecycle_change: Contact lifecycle stage changes
        - manual: Manually triggered by a user

    Re-entry policies:
        - skip: Contact already in workflow is not re-entered
        - restart: Existing run is cancelled, new one starts
        - parallel: Multiple runs allowed for same contact
    """
    __tablename__ = "automation_workflows"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)

    # ── Trigger Configuration ─────────────────────────────────────────────
    trigger_type = Column(String(50), nullable=False)
    trigger_config_json = Column(Text, nullable=True)
    # Examples:
    #   segment_entry:    {"segment_id": 123}
    #   tag_added:        {"tag_name": "vip"}
    #   lifecycle_change: {"lifecycle_from": "active", "lifecycle_to": "churn_risk"}

    # ── Workflow Graph ────────────────────────────────────────────────────
    workflow_graph_json = Column(Text, nullable=False, default="{\"nodes\":[],\"edges\":[]}")
    # React Flow format: {"nodes": [...], "edges": [...]}

    # ── Execution Limits ──────────────────────────────────────────────────
    max_concurrent_runs = Column(Integer, nullable=False, default=1000)
    re_entry_policy = Column(String(30), nullable=False, default="skip")

    # ── Metadata ──────────────────────────────────────────────────────────
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────
    runs = relationship("AutomationRun", back_populates="workflow", cascade="all, delete-orphan")


# ─── Automation Run ──────────────────────────────────────────────────────────

class AutomationRun(Base):
    """A single contact's journey through an automation workflow.

    Each run tracks the current position in the workflow graph,
    the next scheduled execution time, and the overall status.

    Statuses:
        - active: Currently executing or ready for next node
        - waiting: Paused at a wait node until next_execution_at
        - completed: Successfully finished all nodes
        - cancelled: Manually cancelled or superseded by re-entry
        - error: Failed during execution
    """
    __tablename__ = "automation_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("automation_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    status = Column(String(30), nullable=False, default="active")
    current_node_id = Column(String(100), nullable=True)
    next_execution_at = Column(DateTime, nullable=True, index=True)

    # Runtime data (e.g., which campaigns were sent, condition results)
    run_data_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    workflow = relationship("AutomationWorkflow", back_populates="runs")
    logs = relationship("AutomationRunLog", back_populates="run", cascade="all, delete-orphan",
                        order_by="AutomationRunLog.executed_at")

    __table_args__ = (
        Index("ix_ar_workflow_status", "workflow_id", "status"),
        Index("ix_ar_tenant_status", "tenant_id", "status"),
        Index("ix_ar_next_exec", "status", "next_execution_at"),
        Index("ix_ar_contact_workflow", "contact_id", "workflow_id"),
    )


# ─── Automation Run Log ──────────────────────────────────────────────────────

class AutomationRunLog(Base):
    """Audit trail entry for a single node execution within a run.

    Records what happened at each step, enabling debugging,
    monitoring, and compliance reporting.

    Node types:
        - trigger: The initial trigger node
        - send_campaign: Send a campaign to the contact
        - send_email: Send a direct email
        - send_whatsapp: Send a WhatsApp message
        - send_sms: Send an SMS message
        - wait: Pause execution for a duration
        - condition: Evaluate a condition and branch
        - add_tag: Add a tag to the contact
        - remove_tag: Remove a tag from the contact
        - set_field: Set a custom field value
        - update_lifecycle: Change the contact's lifecycle stage
        - end: Terminal node marking workflow completion
    """
    __tablename__ = "automation_run_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("automation_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    node_id = Column(String(100), nullable=False)
    node_type = Column(String(50), nullable=False)
    result_json = Column(Text, nullable=True)  # JSON: execution result details
    error_message = Column(Text, nullable=True)

    executed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────
    run = relationship("AutomationRun", back_populates="logs")

    __table_args__ = (
        Index("ix_arl_run_executed", "run_id", "executed_at"),
    )
