"""ARIIA v2.0 – Database Contact Adapter.

@ARCH: Contacts Refactoring, Phase 1 – Integration Adapter
Replaces the legacy ManualCrmAdapter with a proper database-backed
contact adapter that uses the new Contact model and service layer.

This adapter bridges the existing integration/capability system
(used by the AI agent runtime) with the new Contact service.

Supported Capabilities
----------------------
- crm.contact.search – Search contacts by name, email, phone
- crm.contact.get – Get a single contact by ID
- crm.contact.create – Create a new contact
- crm.contact.update – Update an existing contact
- crm.contact.list – List contacts with filters
- crm.contact.add_note – Add a note to a contact
- crm.contact.add_tag – Add a tag to a contact
- crm.contact.stats – Get contact statistics
"""

from __future__ import annotations

from typing import Any

import structlog

from app.contacts.schemas import ContactCreate, ContactUpdate, NoteCreate
from app.contacts.service import contact_service
from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class DatabaseContactAdapter(BaseAdapter):
    """Database-backed contact adapter using the new Contact model.

    Replaces ManualCrmAdapter for all CRM-related capabilities.
    Uses the ContactService for all operations, ensuring consistent
    business logic, validation, and activity logging.
    """

    @property
    def integration_id(self) -> str:
        return "database_crm"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "crm.contact.search",
            "crm.contact.get",
            "crm.contact.create",
            "crm.contact.update",
            "crm.contact.list",
            "crm.contact.add_note",
            "crm.contact.add_tag",
            "crm.contact.remove_tag",
            "crm.contact.stats",
        ]

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability calls to the appropriate service method."""
        try:
            if capability_id == "crm.contact.search":
                return await self._search_contacts(tenant_id, **kwargs)
            elif capability_id == "crm.contact.get":
                return await self._get_contact(tenant_id, **kwargs)
            elif capability_id == "crm.contact.create":
                return await self._create_contact(tenant_id, **kwargs)
            elif capability_id == "crm.contact.update":
                return await self._update_contact(tenant_id, **kwargs)
            elif capability_id == "crm.contact.list":
                return await self._list_contacts(tenant_id, **kwargs)
            elif capability_id == "crm.contact.add_note":
                return await self._add_note(tenant_id, **kwargs)
            elif capability_id == "crm.contact.add_tag":
                return await self._add_tag(tenant_id, **kwargs)
            elif capability_id == "crm.contact.remove_tag":
                return await self._remove_tag(tenant_id, **kwargs)
            elif capability_id == "crm.contact.stats":
                return await self._get_stats(tenant_id, **kwargs)
            else:
                return AdapterResult(
                    success=False,
                    error=f"Unknown capability: {capability_id}",
                    error_code="UNKNOWN_CAPABILITY",
                )
        except Exception as e:
            logger.error(
                "database_contact_adapter.error",
                capability=capability_id,
                tenant_id=tenant_id,
                error=str(e),
            )
            return AdapterResult(
                success=False,
                error=str(e),
                error_code="ADAPTER_ERROR",
            )

    async def _search_contacts(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Search contacts by name, email, or phone."""
        search = kwargs.get("query") or kwargs.get("search") or kwargs.get("email") or kwargs.get("name", "")
        result = contact_service.list_contacts(
            tenant_id,
            search=search,
            page=1,
            page_size=kwargs.get("limit", 20),
        )
        contacts = [
            {
                "id": c.id,
                "name": c.full_name,
                "email": c.email,
                "phone": c.phone,
                "company": c.company,
                "lifecycle_stage": c.lifecycle_stage,
                "source": c.source,
                "tags": [t.name for t in c.tags],
            }
            for c in result.items
        ]
        return AdapterResult(
            success=True,
            data=contacts,
            metadata={"total": result.total},
        )

    async def _get_contact(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get a single contact by ID."""
        contact_id = kwargs.get("contact_id") or kwargs.get("id")
        if not contact_id:
            return AdapterResult(success=False, error="contact_id ist erforderlich", error_code="MISSING_PARAM")

        contact = contact_service.get_contact(tenant_id, int(contact_id))
        if not contact:
            return AdapterResult(success=False, error=f"Kontakt {contact_id} nicht gefunden", error_code="NOT_FOUND")

        return AdapterResult(
            success=True,
            data={
                "id": contact.id,
                "name": contact.full_name,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "email": contact.email,
                "phone": contact.phone,
                "company": contact.company,
                "job_title": contact.job_title,
                "lifecycle_stage": contact.lifecycle_stage,
                "source": contact.source,
                "score": contact.score,
                "tags": [t.name for t in contact.tags],
                "custom_fields": contact.custom_fields,
                "created_at": contact.created_at.isoformat() if contact.created_at else None,
            },
        )

    async def _create_contact(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Create a new contact."""
        try:
            data = ContactCreate(
                first_name=kwargs.get("first_name", ""),
                last_name=kwargs.get("last_name", ""),
                email=kwargs.get("email"),
                phone=kwargs.get("phone") or kwargs.get("phone_number"),
                company=kwargs.get("company"),
                source=kwargs.get("source", "ai_agent"),
                notes=kwargs.get("notes"),
                tags=kwargs.get("tags", []),
            )
            contact = contact_service.create_contact(tenant_id, data)
            return AdapterResult(
                success=True,
                data={
                    "id": contact.id,
                    "name": contact.full_name,
                    "email": contact.email,
                    "message": f"Kontakt '{contact.full_name}' erfolgreich erstellt.",
                },
            )
        except ValueError as e:
            return AdapterResult(success=False, error=str(e), error_code="VALIDATION_ERROR")

    async def _update_contact(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Update an existing contact."""
        contact_id = kwargs.pop("contact_id", None) or kwargs.pop("id", None)
        if not contact_id:
            return AdapterResult(success=False, error="contact_id ist erforderlich", error_code="MISSING_PARAM")

        try:
            update_fields = {k: v for k, v in kwargs.items() if v is not None}
            if "phone_number" in update_fields:
                update_fields["phone"] = update_fields.pop("phone_number")

            data = ContactUpdate(**update_fields)
            contact = contact_service.update_contact(tenant_id, int(contact_id), data)
            if not contact:
                return AdapterResult(success=False, error=f"Kontakt {contact_id} nicht gefunden", error_code="NOT_FOUND")

            return AdapterResult(
                success=True,
                data={
                    "id": contact.id,
                    "name": contact.full_name,
                    "message": f"Kontakt '{contact.full_name}' erfolgreich aktualisiert.",
                },
            )
        except ValueError as e:
            return AdapterResult(success=False, error=str(e), error_code="VALIDATION_ERROR")

    async def _list_contacts(self, tenant_id: int, **kwargs) -> AdapterResult:
        """List contacts with optional filters."""
        result = contact_service.list_contacts(
            tenant_id,
            lifecycle_stage=kwargs.get("lifecycle_stage"),
            source=kwargs.get("source"),
            tags=kwargs.get("tags"),
            page=kwargs.get("page", 1),
            page_size=kwargs.get("limit", 20),
        )
        contacts = [
            {
                "id": c.id,
                "name": c.full_name,
                "email": c.email,
                "phone": c.phone,
                "lifecycle_stage": c.lifecycle_stage,
            }
            for c in result.items
        ]
        return AdapterResult(
            success=True,
            data=contacts,
            metadata={"total": result.total, "page": result.page, "total_pages": result.total_pages},
        )

    async def _add_note(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Add a note to a contact."""
        contact_id = kwargs.get("contact_id") or kwargs.get("id")
        content = kwargs.get("content") or kwargs.get("note")
        if not contact_id or not content:
            return AdapterResult(success=False, error="contact_id und content sind erforderlich", error_code="MISSING_PARAM")

        note_data = NoteCreate(content=content)
        note = contact_service.add_note(tenant_id, int(contact_id), note_data)
        if not note:
            return AdapterResult(success=False, error=f"Kontakt {contact_id} nicht gefunden", error_code="NOT_FOUND")

        return AdapterResult(
            success=True,
            data={"note_id": note.id, "message": "Notiz erfolgreich hinzugefügt."},
        )

    async def _add_tag(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Add a tag to a contact."""
        contact_id = kwargs.get("contact_id") or kwargs.get("id")
        tag_name = kwargs.get("tag") or kwargs.get("tag_name")
        if not contact_id or not tag_name:
            return AdapterResult(success=False, error="contact_id und tag sind erforderlich", error_code="MISSING_PARAM")

        result = contact_service.add_tag_to_contact(tenant_id, int(contact_id), tag_name)
        if not result:
            return AdapterResult(success=False, error=f"Kontakt {contact_id} nicht gefunden", error_code="NOT_FOUND")

        return AdapterResult(
            success=True,
            data={"message": f"Tag '{tag_name}' erfolgreich hinzugefügt."},
        )

    async def _remove_tag(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Remove a tag from a contact."""
        contact_id = kwargs.get("contact_id") or kwargs.get("id")
        tag_name = kwargs.get("tag") or kwargs.get("tag_name")
        if not contact_id or not tag_name:
            return AdapterResult(success=False, error="contact_id und tag sind erforderlich", error_code="MISSING_PARAM")

        result = contact_service.remove_tag_from_contact(tenant_id, int(contact_id), tag_name)
        return AdapterResult(
            success=True,
            data={"message": f"Tag '{tag_name}' {'entfernt' if result else 'nicht gefunden'}."},
        )

    async def _get_stats(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get contact statistics."""
        stats = contact_service.get_statistics(tenant_id)
        return AdapterResult(success=True, data=stats)
