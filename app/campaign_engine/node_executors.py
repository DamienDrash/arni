"""ARIIA v2.1 – Automation Node Executors.

Each node type in a workflow graph is handled by a dedicated executor class.
This architecture ensures clean separation of concerns and easy extensibility.

Node types:
    - send_email: Send a direct email via EmailAdapter
    - send_whatsapp: Send a WhatsApp message via WhatsAppAdapter
    - send_sms: Send an SMS via SmsVoiceAdapter
    - send_campaign: Create and queue a campaign for the contact
    - wait: Pause execution for a specified duration
    - condition: Evaluate a condition and determine the next branch
    - add_tag: Add a tag to the contact
    - remove_tag: Remove a tag from the contact
    - set_field: Set a custom field on the contact
    - update_lifecycle: Change the contact's lifecycle stage
    - end: Mark the run as completed
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.automation_models import AutomationRun
from app.core.contact_models import Contact, ContactActivity
from app.domains.campaigns.models import Campaign, CampaignRecipient
from app.integrations.adapters.registry import get_adapter_registry

logger = logging.getLogger("ariia.automation.executors")


# ─── Base Executor ───────────────────────────────────────────────────────────

class BaseNodeExecutor(ABC):
    """Abstract base class for node executors."""

    @abstractmethod
    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        """Execute the node logic and return a result dict.

        Args:
            db: Database session
            run: The current automation run
            node: The node definition from the workflow graph

        Returns:
            A dict with execution results (logged to automation_run_logs)
        """
        ...


# ─── Messaging Executors ─────────────────────────────────────────────────────

class SendEmailExecutor(BaseNodeExecutor):
    """Send a direct email to the contact via the EmailAdapter."""

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        contact = db.query(Contact).filter(Contact.id == run.contact_id).first()
        if not contact:
            return {"status": "error", "error": "Contact not found"}
        if not contact.email:
            return {"status": "skipped", "reason": "No email address"}
        if not contact.consent_email:
            return {"status": "skipped", "reason": "No email consent"}

        registry = get_adapter_registry()
        adapter = registry.get_adapter("email")
        if not adapter:
            return {"status": "error", "error": "Email adapter not available"}

        subject = config.get("subject", "")
        body = config.get("body", "")

        # Personalize content
        subject = _personalize(subject, contact)
        body = _personalize(body, contact)

        result = await adapter.execute_capability(
            "messaging.send.html_email",
            run.tenant_id,
            to_email=contact.email,
            to_name=f"{contact.first_name} {contact.last_name}",
            subject=subject,
            html_body=body,
        )

        _log_activity(db, contact, run.tenant_id, "email_sent",
                      f"Automation Email: {subject}",
                      {"workflow_id": run.workflow_id, "run_id": run.id})

        return {
            "status": "sent" if result.success else "error",
            "channel": "email",
            "to": contact.email,
            "error": result.error if not result.success else None,
        }


class SendWhatsAppExecutor(BaseNodeExecutor):
    """Send a WhatsApp message to the contact."""

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        contact = db.query(Contact).filter(Contact.id == run.contact_id).first()
        if not contact:
            return {"status": "error", "error": "Contact not found"}
        if not contact.phone:
            return {"status": "skipped", "reason": "No phone number"}
        if not contact.consent_whatsapp:
            return {"status": "skipped", "reason": "No WhatsApp consent"}

        registry = get_adapter_registry()
        adapter = registry.get_adapter("whatsapp")
        if not adapter:
            return {"status": "error", "error": "WhatsApp adapter not available"}

        message = _personalize(config.get("message", ""), contact)

        result = await adapter.execute_capability(
            "messaging.send.text",
            run.tenant_id,
            to_phone=contact.phone,
            message=message,
        )

        _log_activity(db, contact, run.tenant_id, "whatsapp_sent",
                      f"Automation WhatsApp: {message[:80]}...",
                      {"workflow_id": run.workflow_id, "run_id": run.id})

        return {
            "status": "sent" if result.success else "error",
            "channel": "whatsapp",
            "to": contact.phone,
            "error": result.error if not result.success else None,
        }


class SendSmsExecutor(BaseNodeExecutor):
    """Send an SMS to the contact."""

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        contact = db.query(Contact).filter(Contact.id == run.contact_id).first()
        if not contact:
            return {"status": "error", "error": "Contact not found"}
        if not contact.phone:
            return {"status": "skipped", "reason": "No phone number"}
        if not contact.consent_phone:
            return {"status": "skipped", "reason": "No phone consent"}

        registry = get_adapter_registry()
        adapter = registry.get_adapter("sms_voice")
        if not adapter:
            return {"status": "error", "error": "SMS adapter not available"}

        message = _personalize(config.get("message", ""), contact)

        result = await adapter.execute_capability(
            "messaging.send.sms",
            run.tenant_id,
            to_phone=contact.phone,
            message=message,
        )

        _log_activity(db, contact, run.tenant_id, "sms_sent",
                      f"Automation SMS: {message[:80]}...",
                      {"workflow_id": run.workflow_id, "run_id": run.id})

        return {
            "status": "sent" if result.success else "error",
            "channel": "sms",
            "to": contact.phone,
            "error": result.error if not result.success else None,
        }


class SendCampaignExecutor(BaseNodeExecutor):
    """Create and queue a campaign for the contact via the existing CampaignSchedulerWorker."""

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        contact = db.query(Contact).filter(Contact.id == run.contact_id).first()
        if not contact:
            return {"status": "error", "error": "Contact not found"}

        campaign_name = config.get("campaign_name", f"Auto: {run.workflow_id}-{run.id}")
        channel = config.get("channel", "email")
        subject = _personalize(config.get("subject", ""), contact)
        body = _personalize(config.get("body", ""), contact)
        template_id = config.get("template_id")

        campaign = Campaign(
            tenant_id=run.tenant_id,
            name=campaign_name,
            type="automation",
            status="scheduled",
            channel=channel,
            target_type="manual",
            content_subject=subject,
            content_body=body,
            template_id=template_id,
            scheduled_at=datetime.now(timezone.utc),
        )
        db.add(campaign)
        db.flush()

        recipient = CampaignRecipient(
            campaign_id=campaign.id,
            tenant_id=run.tenant_id,
            contact_id=contact.id,
            channel=channel,
            status="pending",
        )
        db.add(recipient)
        db.commit()

        return {
            "status": "queued",
            "campaign_id": campaign.id,
            "channel": channel,
            "contact_id": contact.id,
        }


# ─── Flow Control Executors ──────────────────────────────────────────────────

class WaitExecutor(BaseNodeExecutor):
    """Pause execution for a specified duration.

    The run's next_execution_at is set to now() + duration,
    and the engine will pick it up again after the wait period.
    """

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        duration_value = config.get("duration", 1)
        duration_unit = config.get("unit", "days")  # minutes, hours, days

        delta_map = {
            "minutes": timedelta(minutes=duration_value),
            "hours": timedelta(hours=duration_value),
            "days": timedelta(days=duration_value),
        }
        delta = delta_map.get(duration_unit, timedelta(days=1))
        wait_until = datetime.now(timezone.utc) + delta

        run.next_execution_at = wait_until

        return {
            "status": "waiting",
            "wait_until": wait_until.isoformat(),
            "duration": f"{duration_value} {duration_unit}",
        }


class ConditionExecutor(BaseNodeExecutor):
    """Evaluate a condition and determine the branch (yes/no).

    Supported condition types:
        - has_tag: Check if contact has a specific tag
        - field_equals: Check if a contact field equals a value
        - email_opened: Check if a previous email was opened
        - lifecycle_is: Check if contact is in a specific lifecycle stage
        - segment_member: Check if contact is in a specific segment
    """

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        condition_type = config.get("condition_type", "has_tag")
        contact = db.query(Contact).filter(Contact.id == run.contact_id).first()
        if not contact:
            return {"branch": "no", "reason": "Contact not found"}

        result = False

        if condition_type == "has_tag":
            tag_name = config.get("tag_name", "")
            tags = json.loads(contact.tags_json or "[]") if hasattr(contact, "tags_json") and contact.tags_json else []
            result = tag_name in tags

        elif condition_type == "field_equals":
            field_name = config.get("field_name", "")
            expected_value = config.get("field_value", "")
            actual_value = getattr(contact, field_name, None)
            if actual_value is None and hasattr(contact, "custom_fields_json") and contact.custom_fields_json:
                custom = json.loads(contact.custom_fields_json)
                actual_value = custom.get(field_name)
            result = str(actual_value) == str(expected_value) if actual_value is not None else False

        elif condition_type == "lifecycle_is":
            expected_stage = config.get("lifecycle_stage", "")
            result = (contact.lifecycle_stage or "") == expected_stage

        elif condition_type == "segment_member":
            from app.contacts.repository import ContactRepository
            segment_id = config.get("segment_id")
            if segment_id:
                repo = ContactRepository()
                members = await repo.evaluate_segment_v2(db, segment_id, run.tenant_id, limit=1,
                                                         contact_id_filter=run.contact_id)
                result = len(members) > 0

        elif condition_type == "email_opened":
            # Check if any email in this run was opened
            run_data = json.loads(run.run_data_json or "{}")
            result = run_data.get("last_email_opened", False)

        return {
            "branch": "yes" if result else "no",
            "condition_type": condition_type,
            "evaluated": result,
        }


# ─── Contact Modification Executors ──────────────────────────────────────────

class AddTagExecutor(BaseNodeExecutor):
    """Add a tag to the contact."""

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        tag_name = config.get("tag_name", "")
        contact = db.query(Contact).filter(Contact.id == run.contact_id).first()
        if not contact:
            return {"status": "error", "error": "Contact not found"}

        tags = json.loads(contact.tags_json or "[]") if hasattr(contact, "tags_json") and contact.tags_json else []
        if tag_name not in tags:
            tags.append(tag_name)
            contact.tags_json = json.dumps(tags)
            _log_activity(db, contact, run.tenant_id, "tag_added",
                          f"Tag hinzugefügt: {tag_name}",
                          {"tag": tag_name, "source": "automation", "workflow_id": run.workflow_id})
            db.commit()

        return {"status": "added", "tag": tag_name}


class RemoveTagExecutor(BaseNodeExecutor):
    """Remove a tag from the contact."""

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        tag_name = config.get("tag_name", "")
        contact = db.query(Contact).filter(Contact.id == run.contact_id).first()
        if not contact:
            return {"status": "error", "error": "Contact not found"}

        tags = json.loads(contact.tags_json or "[]") if hasattr(contact, "tags_json") and contact.tags_json else []
        if tag_name in tags:
            tags.remove(tag_name)
            contact.tags_json = json.dumps(tags)
            _log_activity(db, contact, run.tenant_id, "tag_removed",
                          f"Tag entfernt: {tag_name}",
                          {"tag": tag_name, "source": "automation", "workflow_id": run.workflow_id})
            db.commit()

        return {"status": "removed", "tag": tag_name}


class SetFieldExecutor(BaseNodeExecutor):
    """Set a custom field value on the contact."""

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        field_name = config.get("field_name", "")
        field_value = config.get("field_value", "")
        contact = db.query(Contact).filter(Contact.id == run.contact_id).first()
        if not contact:
            return {"status": "error", "error": "Contact not found"}

        # Try direct attribute first, then custom fields
        if hasattr(contact, field_name) and field_name not in ("id", "tenant_id"):
            setattr(contact, field_name, field_value)
        elif hasattr(contact, "custom_fields_json"):
            custom = json.loads(contact.custom_fields_json or "{}")
            custom[field_name] = field_value
            contact.custom_fields_json = json.dumps(custom)

        _log_activity(db, contact, run.tenant_id, "field_updated",
                      f"Feld aktualisiert: {field_name} = {field_value}",
                      {"field": field_name, "value": field_value, "source": "automation"})
        db.commit()

        return {"status": "set", "field": field_name, "value": field_value}


class UpdateLifecycleExecutor(BaseNodeExecutor):
    """Change the contact's lifecycle stage."""

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        config = node.get("data", {})
        new_stage = config.get("lifecycle_stage", "")
        contact = db.query(Contact).filter(Contact.id == run.contact_id).first()
        if not contact:
            return {"status": "error", "error": "Contact not found"}

        old_stage = contact.lifecycle_stage or "unknown"
        contact.lifecycle_stage = new_stage

        _log_activity(db, contact, run.tenant_id, "lifecycle_change",
                      f"Lifecycle: {old_stage} → {new_stage}",
                      {"from": old_stage, "to": new_stage, "source": "automation"})
        db.commit()

        return {"status": "updated", "from": old_stage, "to": new_stage}


class EndExecutor(BaseNodeExecutor):
    """Terminal node – marks the run as completed."""

    async def execute(self, db: Session, run: AutomationRun, node: dict) -> dict:
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        return {"status": "completed"}


# ─── Executor Registry ───────────────────────────────────────────────────────

_EXECUTOR_MAP: dict[str, BaseNodeExecutor] = {
    "send_email": SendEmailExecutor(),
    "send_whatsapp": SendWhatsAppExecutor(),
    "send_sms": SendSmsExecutor(),
    "send_campaign": SendCampaignExecutor(),
    "wait": WaitExecutor(),
    "condition": ConditionExecutor(),
    "add_tag": AddTagExecutor(),
    "remove_tag": RemoveTagExecutor(),
    "set_field": SetFieldExecutor(),
    "update_lifecycle": UpdateLifecycleExecutor(),
    "end": EndExecutor(),
}


def get_executor(node_type: str) -> BaseNodeExecutor:
    """Get the executor for a given node type.

    Returns EndExecutor as fallback for unknown types.
    """
    executor = _EXECUTOR_MAP.get(node_type)
    if executor is None:
        logger.warning("automation.unknown_node_type", node_type=node_type)
        return EndExecutor()
    return executor


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _personalize(text: str, contact: Contact) -> str:
    """Replace {{ contact.* }} placeholders with actual contact values."""
    if not text:
        return text
    replacements = {
        "{{ contact.first_name }}": contact.first_name or "",
        "{{ contact.last_name }}": contact.last_name or "",
        "{{ contact.email }}": contact.email or "",
        "{{ contact.phone }}": contact.phone or "",
        "{{ contact.company }}": getattr(contact, "company", "") or "",
        "{{ contact.lifecycle_stage }}": contact.lifecycle_stage or "",
        "{{contact.first_name}}": contact.first_name or "",
        "{{contact.last_name}}": contact.last_name or "",
        "{{contact.email}}": contact.email or "",
        "{{contact.phone}}": contact.phone or "",
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def _log_activity(db: Session, contact: Contact, tenant_id: int,
                  activity_type: str, title: str, metadata: dict | None = None) -> None:
    """Create a ContactActivity entry for audit trail."""
    try:
        activity = ContactActivity(
            contact_id=contact.id,
            tenant_id=tenant_id,
            activity_type=activity_type,
            title=title,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(activity)
    except Exception as e:
        logger.error("automation.activity_log_failed", error=str(e))
