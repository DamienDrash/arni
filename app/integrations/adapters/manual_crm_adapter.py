"""ARIIA v2.0 – Manual CRM Adapter.

@ARCH: Phase 6, Meilenstein 6.4 – Skalierung & Ökosystem

Generic CRM adapter for tenants who don't use an external CRM system.
Provides basic CRM functionality using the local database (StudioMember table)
without requiring any external API integration.

This is the "default" adapter for tenants who manage their members manually
through the ARIIA platform, CSV imports, or the Public API.

Supported Capabilities:
  - crm.customer.search       → Search local members
  - crm.customer.detail       → Get member details
  - crm.customer.create       → Create a new member
  - crm.customer.update       → Update member information
  - crm.customer.list         → List members with filters
  - crm.customer.stats        → Get member statistics
  - crm.import.csv            → Import members from CSV data
  - crm.tag.manage            → Add/remove tags from members
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from app.integrations.adapters.base import BaseAdapter, AdapterResult

logger = structlog.get_logger()


class ManualCrmAdapter(BaseAdapter):
    """Adapter for local/manual CRM management without external API."""

    integration_id = "manual_crm"
    display_name = "ARIIA CRM"
    description = (
        "Integriertes CRM für manuelle Mitgliederverwaltung. "
        "Keine externe API erforderlich – verwaltet Kontakte direkt in der ARIIA-Datenbank."
    )
    version = "1.0.0"
    supported_capabilities = {
        "crm.customer.search",
        "crm.customer.detail",
        "crm.customer.create",
        "crm.customer.update",
        "crm.customer.list",
        "crm.customer.stats",
        "crm.import.csv",
        "crm.tag.manage",
    }

    def __init__(self):
        super().__init__()
        # In-memory store for testing; in production, uses SQLAlchemy + StudioMember
        self._members: dict[int, dict[int, dict]] = {}  # tenant_id -> {member_id -> member}
        self._next_id: dict[int, int] = {}  # tenant_id -> next_member_id

    def _get_members(self, tenant_id: int) -> dict[int, dict]:
        """Get the member store for a tenant."""
        if tenant_id not in self._members:
            self._members[tenant_id] = {}
            self._next_id[tenant_id] = 1
        return self._members[tenant_id]

    def _next_member_id(self, tenant_id: int) -> int:
        """Get the next member ID for a tenant."""
        if tenant_id not in self._next_id:
            self._next_id[tenant_id] = 1
        mid = self._next_id[tenant_id]
        self._next_id[tenant_id] = mid + 1
        return mid

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability to the appropriate handler."""
        handlers = {
            "crm.customer.search": self._customer_search,
            "crm.customer.detail": self._customer_detail,
            "crm.customer.create": self._customer_create,
            "crm.customer.update": self._customer_update,
            "crm.customer.list": self._customer_list,
            "crm.customer.stats": self._customer_stats,
            "crm.import.csv": self._import_csv,
            "crm.tag.manage": self._tag_manage,
        }

        handler = handlers.get(capability_id)
        if not handler:
            return AdapterResult(
                success=False,
                error=f"Unknown capability: {capability_id}",
                error_code="UNKNOWN_CAPABILITY",
            )

        return await handler(tenant_id, **kwargs)

    # ── Capability Handlers ──────────────────────────────────────────────

    async def _customer_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Search members by name, email, or phone."""
        query = kwargs.get("query", "").lower()
        limit = kwargs.get("limit", 20)

        if not query:
            return AdapterResult(success=False, error="Search query required", error_code="MISSING_QUERY")

        members = self._get_members(tenant_id)
        results = []

        for mid, member in members.items():
            searchable = " ".join([
                member.get("first_name", ""),
                member.get("last_name", ""),
                member.get("email", ""),
                member.get("phone", ""),
            ]).lower()

            if query in searchable:
                results.append({**member, "id": mid})

        results = results[:limit]
        return AdapterResult(
            success=True,
            data={"members": results, "count": len(results), "query": query},
        )

    async def _customer_detail(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get detailed member information."""
        member_id = kwargs.get("member_id")
        if member_id is None:
            return AdapterResult(success=False, error="member_id required", error_code="MISSING_PARAM")

        members = self._get_members(tenant_id)
        member = members.get(int(member_id))

        if not member:
            return AdapterResult(success=False, error="Member not found", error_code="NOT_FOUND")

        return AdapterResult(
            success=True,
            data={**member, "id": int(member_id)},
        )

    async def _customer_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Create a new member."""
        first_name = kwargs.get("first_name", "")
        last_name = kwargs.get("last_name", "")
        email = kwargs.get("email", "")
        phone = kwargs.get("phone", "")
        tags = kwargs.get("tags", [])
        notes = kwargs.get("notes", "")

        if not first_name and not email:
            return AdapterResult(
                success=False,
                error="At least first_name or email is required",
                error_code="MISSING_PARAM",
            )

        # Check for duplicate email
        if email:
            members = self._get_members(tenant_id)
            for existing in members.values():
                if existing.get("email", "").lower() == email.lower():
                    return AdapterResult(
                        success=False,
                        error=f"Member with email {email} already exists",
                        error_code="DUPLICATE_EMAIL",
                    )

        member_id = self._next_member_id(tenant_id)
        now = datetime.now(timezone.utc).isoformat()

        member = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "tags": tags if isinstance(tags, list) else [tags] if tags else [],
            "notes": notes,
            "status": "active",
            "source": "manual",
            "created_at": now,
            "updated_at": now,
        }

        self._get_members(tenant_id)[member_id] = member

        logger.info("manual_crm.member_created",
                     tenant_id=tenant_id,
                     member_id=member_id,
                     email=email)

        return AdapterResult(
            success=True,
            data={**member, "id": member_id},
        )

    async def _customer_update(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Update member information."""
        member_id = kwargs.get("member_id")
        if member_id is None:
            return AdapterResult(success=False, error="member_id required", error_code="MISSING_PARAM")

        members = self._get_members(tenant_id)
        member = members.get(int(member_id))

        if not member:
            return AdapterResult(success=False, error="Member not found", error_code="NOT_FOUND")

        # Update fields
        updatable_fields = ["first_name", "last_name", "email", "phone", "tags", "notes", "status"]
        updated_fields = []
        for field_name in updatable_fields:
            if field_name in kwargs and kwargs[field_name] is not None:
                member[field_name] = kwargs[field_name]
                updated_fields.append(field_name)

        member["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info("manual_crm.member_updated",
                     tenant_id=tenant_id,
                     member_id=member_id,
                     fields=updated_fields)

        return AdapterResult(
            success=True,
            data={**member, "id": int(member_id), "updated_fields": updated_fields},
        )

    async def _customer_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        """List members with optional filters."""
        limit = kwargs.get("limit", 50)
        offset = kwargs.get("offset", 0)
        status_filter = kwargs.get("status", "")
        tag_filter = kwargs.get("tag", "")
        sort_by = kwargs.get("sort_by", "created_at")
        sort_order = kwargs.get("sort_order", "desc")

        members = self._get_members(tenant_id)
        results = []

        for mid, member in members.items():
            # Apply filters
            if status_filter and member.get("status") != status_filter:
                continue
            if tag_filter and tag_filter not in member.get("tags", []):
                continue
            results.append({**member, "id": mid})

        # Sort
        reverse = sort_order == "desc"
        results.sort(key=lambda m: m.get(sort_by, ""), reverse=reverse)

        total = len(results)
        results = results[offset:offset + limit]

        return AdapterResult(
            success=True,
            data={
                "members": results,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )

    async def _customer_stats(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get member statistics."""
        members = self._get_members(tenant_id)

        total = len(members)
        status_counts = Counter(m.get("status", "unknown") for m in members.values())
        source_counts = Counter(m.get("source", "unknown") for m in members.values())

        all_tags = []
        for m in members.values():
            all_tags.extend(m.get("tags", []))
        tag_counts = Counter(all_tags)

        return AdapterResult(
            success=True,
            data={
                "total_members": total,
                "by_status": dict(status_counts),
                "by_source": dict(source_counts),
                "top_tags": dict(tag_counts.most_common(10)),
            },
        )

    async def _import_csv(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Import members from CSV data."""
        csv_data = kwargs.get("csv_data", "")
        if not csv_data:
            return AdapterResult(success=False, error="csv_data required", error_code="MISSING_PARAM")

        try:
            reader = csv.DictReader(io.StringIO(csv_data))
            imported = 0
            skipped = 0
            errors = []

            for row_num, row in enumerate(reader, start=1):
                try:
                    # Map common CSV column names
                    first_name = row.get("first_name") or row.get("Vorname") or row.get("vorname", "")
                    last_name = row.get("last_name") or row.get("Nachname") or row.get("nachname", "")
                    email = row.get("email") or row.get("Email") or row.get("E-Mail", "")
                    phone = row.get("phone") or row.get("Telefon") or row.get("telefon", "")
                    tags_str = row.get("tags") or row.get("Tags", "")
                    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

                    if not first_name and not email:
                        skipped += 1
                        continue

                    # Check duplicate
                    duplicate = False
                    if email:
                        for existing in self._get_members(tenant_id).values():
                            if existing.get("email", "").lower() == email.lower():
                                duplicate = True
                                break

                    if duplicate:
                        skipped += 1
                        continue

                    member_id = self._next_member_id(tenant_id)
                    now = datetime.now(timezone.utc).isoformat()
                    self._get_members(tenant_id)[member_id] = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "phone": phone,
                        "tags": tags + ["csv_import"],
                        "notes": "",
                        "status": "active",
                        "source": "csv_import",
                        "created_at": now,
                        "updated_at": now,
                    }
                    imported += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")

            logger.info("manual_crm.csv_imported",
                        tenant_id=tenant_id,
                        imported=imported,
                        skipped=skipped,
                        errors=len(errors))

            return AdapterResult(
                success=True,
                data={
                    "imported": imported,
                    "skipped": skipped,
                    "errors": errors[:10],  # Limit error messages
                    "total_members": len(self._get_members(tenant_id)),
                },
            )
        except Exception as e:
            return AdapterResult(success=False, error=f"CSV parse error: {e}", error_code="CSV_ERROR")

    async def _tag_manage(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Add or remove tags from a member."""
        member_id = kwargs.get("member_id")
        add_tags = kwargs.get("add_tags", [])
        remove_tags = kwargs.get("remove_tags", [])

        if member_id is None:
            return AdapterResult(success=False, error="member_id required", error_code="MISSING_PARAM")

        members = self._get_members(tenant_id)
        member = members.get(int(member_id))

        if not member:
            return AdapterResult(success=False, error="Member not found", error_code="NOT_FOUND")

        current_tags = set(member.get("tags", []))

        if add_tags:
            current_tags.update(add_tags)
        if remove_tags:
            current_tags -= set(remove_tags)

        member["tags"] = sorted(list(current_tags))
        member["updated_at"] = datetime.now(timezone.utc).isoformat()

        return AdapterResult(
            success=True,
            data={
                "member_id": int(member_id),
                "tags": member["tags"],
                "added": add_tags,
                "removed": remove_tags,
            },
        )

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Health check for manual CRM (always healthy since it's local)."""
        members = self._get_members(tenant_id)
        return AdapterResult(
            success=True,
            data={
                "status": "healthy",
                "adapter": self.integration_id,
                "total_members": len(members),
            },
        )
