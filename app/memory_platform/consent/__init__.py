"""Consent Management Service – GDPR-compliant consent tracking.

Manages user consent for memory storage, profiling, and marketing.
Integrates with the Memory Writer to enforce consent checks before
writing personal data, and with the Retrieval Service to filter
results based on consent status.

Implements the "Right to be Forgotten" by coordinating data deletion
across all stores (graph, vector, cache).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from app.memory_platform.models import ConsentRecord, ConsentStatus

logger = structlog.get_logger()


class ConsentService:
    """GDPR-compliant consent management for the Memory Platform."""

    def __init__(self) -> None:
        self._records: dict[str, ConsentRecord] = {}  # consent_id -> record
        self._member_index: dict[str, list[str]] = {}  # member_id -> [consent_ids]

    # ── Consent Operations ───────────────────────────────────────────

    async def grant_consent(
        self,
        tenant_id: int,
        member_id: str,
        consent_type: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ConsentRecord:
        """Record that a member has granted consent."""
        record = ConsentRecord(
            tenant_id=tenant_id,
            member_id=member_id,
            consent_type=consent_type,
            status=ConsentStatus.GRANTED,
            granted_at=datetime.now(timezone.utc),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Check for existing consent of same type
        existing = await self.get_consent(tenant_id, member_id, consent_type)
        if existing:
            existing.status = ConsentStatus.GRANTED
            existing.granted_at = datetime.now(timezone.utc)
            existing.withdrawn_at = None
            existing.ip_address = ip_address
            existing.user_agent = user_agent
            logger.info(
                "consent.updated",
                member_id=member_id,
                consent_type=consent_type,
                status="granted",
            )
            return existing

        self._records[record.consent_id] = record
        self._member_index.setdefault(member_id, []).append(record.consent_id)

        logger.info(
            "consent.granted",
            member_id=member_id,
            consent_type=consent_type,
        )
        return record

    async def withdraw_consent(
        self,
        tenant_id: int,
        member_id: str,
        consent_type: str,
    ) -> ConsentRecord | None:
        """Record that a member has withdrawn consent."""
        record = await self.get_consent(tenant_id, member_id, consent_type)
        if not record:
            logger.warning(
                "consent.withdraw_not_found",
                member_id=member_id,
                consent_type=consent_type,
            )
            return None

        record.status = ConsentStatus.WITHDRAWN
        record.withdrawn_at = datetime.now(timezone.utc)

        logger.info(
            "consent.withdrawn",
            member_id=member_id,
            consent_type=consent_type,
        )

        # If memory_storage consent is withdrawn, trigger data deletion
        if consent_type == "memory_storage":
            await self._handle_right_to_be_forgotten(tenant_id, member_id)

        return record

    async def get_consent(
        self,
        tenant_id: int,
        member_id: str,
        consent_type: str,
    ) -> ConsentRecord | None:
        """Get the current consent status for a specific type."""
        consent_ids = self._member_index.get(member_id, [])
        for cid in consent_ids:
            record = self._records.get(cid)
            if (
                record
                and record.tenant_id == tenant_id
                and record.consent_type == consent_type
            ):
                return record
        return None

    async def check_consent(
        self,
        tenant_id: int,
        member_id: str,
        consent_type: str,
    ) -> bool:
        """Check if a member has active consent for a given type."""
        record = await self.get_consent(tenant_id, member_id, consent_type)
        return record is not None and record.status == ConsentStatus.GRANTED

    async def get_all_consents(
        self,
        tenant_id: int,
        member_id: str,
    ) -> list[ConsentRecord]:
        """Get all consent records for a member."""
        consent_ids = self._member_index.get(member_id, [])
        results = []
        for cid in consent_ids:
            record = self._records.get(cid)
            if record and record.tenant_id == tenant_id:
                results.append(record)
        return results

    # ── Right to be Forgotten ────────────────────────────────────────

    async def _handle_right_to_be_forgotten(
        self,
        tenant_id: int,
        member_id: str,
    ) -> None:
        """Delete all personal data for a member across all stores."""
        logger.info(
            "consent.right_to_be_forgotten",
            tenant_id=tenant_id,
            member_id=member_id,
        )

        try:
            from app.memory_platform.writer import get_writer_service
            writer = get_writer_service()
            deleted = await writer.delete_member_data(tenant_id, member_id)
            logger.info(
                "consent.data_deleted",
                member_id=member_id,
                items_deleted=deleted,
            )
        except Exception as exc:
            logger.error(
                "consent.deletion_error",
                member_id=member_id,
                error=str(exc),
            )

    # ── Audit ────────────────────────────────────────────────────────

    async def get_audit_log(
        self,
        tenant_id: int,
        member_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get consent audit log entries."""
        entries = []
        for record in self._records.values():
            if record.tenant_id != tenant_id:
                continue
            if member_id and record.member_id != member_id:
                continue
            entries.append({
                "consent_id": record.consent_id,
                "member_id": record.member_id,
                "consent_type": record.consent_type,
                "status": record.status.value,
                "granted_at": record.granted_at.isoformat() if record.granted_at else None,
                "withdrawn_at": record.withdrawn_at.isoformat() if record.withdrawn_at else None,
            })
        return sorted(entries, key=lambda e: e.get("granted_at") or "", reverse=True)[:limit]


# ── Singleton ────────────────────────────────────────────────────────

_service: ConsentService | None = None


def get_consent_service() -> ConsentService:
    """Return the singleton consent service."""
    global _service
    if _service is None:
        _service = ConsentService()
    return _service
