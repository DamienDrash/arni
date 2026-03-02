"""ARIIA v2.0 – Contact Sync Conflict Resolver.

@ARCH: Contacts-Sync Refactoring, Phase 3
Handles conflict resolution for bidirectional (two-way) sync scenarios.

Strategies:
  - LAST_WRITE_WINS: Most recent update wins (default)
  - SOURCE_WINS: External source always wins
  - ARIIA_WINS: ARIIA data always wins
  - MANUAL: Flag for manual review
  - FIELD_LEVEL: Per-field strategy based on configuration

Design:
  - Compares field-by-field between local and remote records
  - Tracks change timestamps per field when available
  - Generates conflict reports for manual review queue
  - Supports custom merge rules per integration
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger()


class ConflictStrategy(str, Enum):
    LAST_WRITE_WINS = "last_write_wins"
    SOURCE_WINS = "source_wins"
    ARIIA_WINS = "ariia_wins"
    MANUAL = "manual"
    FIELD_LEVEL = "field_level"


class ConflictAction(str, Enum):
    USE_LOCAL = "use_local"
    USE_REMOTE = "use_remote"
    MERGE = "merge"
    SKIP = "skip"
    FLAG_REVIEW = "flag_review"


class FieldConflict:
    """Represents a conflict on a single field."""

    def __init__(
        self,
        field_name: str,
        local_value: Any,
        remote_value: Any,
        local_updated_at: Optional[datetime] = None,
        remote_updated_at: Optional[datetime] = None,
    ):
        self.field_name = field_name
        self.local_value = local_value
        self.remote_value = remote_value
        self.local_updated_at = local_updated_at
        self.remote_updated_at = remote_updated_at
        self.resolution: Optional[ConflictAction] = None
        self.resolved_value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field_name,
            "local_value": str(self.local_value),
            "remote_value": str(self.remote_value),
            "local_updated_at": self.local_updated_at.isoformat() if self.local_updated_at else None,
            "remote_updated_at": self.remote_updated_at.isoformat() if self.remote_updated_at else None,
            "resolution": self.resolution.value if self.resolution else None,
            "resolved_value": str(self.resolved_value) if self.resolved_value is not None else None,
        }


class ConflictReport:
    """Aggregated conflict report for a single contact."""

    def __init__(
        self,
        contact_id: int,
        integration_id: str,
        external_id: str,
    ):
        self.contact_id = contact_id
        self.integration_id = integration_id
        self.external_id = external_id
        self.conflicts: List[FieldConflict] = []
        self.strategy_used: Optional[ConflictStrategy] = None
        self.auto_resolved: bool = False
        self.created_at: datetime = datetime.now(timezone.utc)

    @property
    def has_unresolved(self) -> bool:
        return any(c.resolution is None for c in self.conflicts)

    @property
    def needs_review(self) -> bool:
        return any(c.resolution == ConflictAction.FLAG_REVIEW for c in self.conflicts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "integration_id": self.integration_id,
            "external_id": self.external_id,
            "strategy_used": self.strategy_used.value if self.strategy_used else None,
            "auto_resolved": self.auto_resolved,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "has_unresolved": self.has_unresolved,
            "needs_review": self.needs_review,
            "created_at": self.created_at.isoformat(),
        }


class ConflictResolver:
    """Resolves conflicts between local and remote contact data."""

    # Fields that are safe to auto-merge (non-critical)
    SAFE_MERGE_FIELDS = {
        "phone_secondary", "company", "position", "notes",
        "tags", "custom_fields",
    }

    # Fields that require careful handling
    CRITICAL_FIELDS = {
        "email", "phone", "first_name", "last_name",
    }

    # Fields where longer/more complete value wins
    COMPLETENESS_FIELDS = {
        "address_street", "address_city", "address_zip",
        "address_country", "company", "position",
    }

    def __init__(
        self,
        default_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        field_strategies: Optional[Dict[str, ConflictStrategy]] = None,
    ):
        self.default_strategy = default_strategy
        self.field_strategies = field_strategies or {}

    def detect_conflicts(
        self,
        local_data: Dict[str, Any],
        remote_data: Dict[str, Any],
        local_updated_at: Optional[datetime] = None,
        remote_updated_at: Optional[datetime] = None,
    ) -> List[FieldConflict]:
        """Detect field-level conflicts between local and remote data."""
        conflicts = []

        # Compare all fields present in either record
        all_fields = set(local_data.keys()) | set(remote_data.keys())

        for field in all_fields:
            local_val = local_data.get(field)
            remote_val = remote_data.get(field)

            # Skip if both are None/empty
            if not local_val and not remote_val:
                continue

            # Skip if identical
            if self._values_equal(local_val, remote_val):
                continue

            # Skip if one is None and the other has data (not a conflict, it's enrichment)
            if local_val is None or remote_val is None:
                continue

            conflicts.append(FieldConflict(
                field_name=field,
                local_value=local_val,
                remote_value=remote_val,
                local_updated_at=local_updated_at,
                remote_updated_at=remote_updated_at,
            ))

        return conflicts

    def resolve(
        self,
        contact_id: int,
        integration_id: str,
        external_id: str,
        local_data: Dict[str, Any],
        remote_data: Dict[str, Any],
        local_updated_at: Optional[datetime] = None,
        remote_updated_at: Optional[datetime] = None,
    ) -> Tuple[Dict[str, Any], ConflictReport]:
        """
        Resolve conflicts and return merged data + conflict report.
        
        Returns:
            Tuple of (merged_data, conflict_report)
        """
        report = ConflictReport(
            contact_id=contact_id,
            integration_id=integration_id,
            external_id=external_id,
        )

        conflicts = self.detect_conflicts(
            local_data, remote_data,
            local_updated_at, remote_updated_at,
        )

        if not conflicts:
            # No conflicts – merge by taking non-None values
            merged = {**local_data}
            for k, v in remote_data.items():
                if v is not None and merged.get(k) is None:
                    merged[k] = v
            report.auto_resolved = True
            report.strategy_used = self.default_strategy
            return merged, report

        report.conflicts = conflicts
        report.strategy_used = self.default_strategy

        # Start with local data as base
        merged = {**local_data}

        for conflict in conflicts:
            field = conflict.field_name
            strategy = self.field_strategies.get(field, self.default_strategy)

            if strategy == ConflictStrategy.LAST_WRITE_WINS:
                self._resolve_last_write_wins(conflict, merged)
            elif strategy == ConflictStrategy.SOURCE_WINS:
                self._resolve_source_wins(conflict, merged)
            elif strategy == ConflictStrategy.ARIIA_WINS:
                self._resolve_ariia_wins(conflict, merged)
            elif strategy == ConflictStrategy.MANUAL:
                self._resolve_manual(conflict, merged)
            elif strategy == ConflictStrategy.FIELD_LEVEL:
                self._resolve_field_level(conflict, merged)

        report.auto_resolved = not report.needs_review

        logger.info(
            "conflict_resolver.resolved",
            contact_id=contact_id,
            total_conflicts=len(conflicts),
            auto_resolved=report.auto_resolved,
            needs_review=report.needs_review,
        )

        return merged, report

    def _resolve_last_write_wins(self, conflict: FieldConflict, merged: Dict) -> None:
        """Most recent timestamp wins."""
        if conflict.remote_updated_at and conflict.local_updated_at:
            if conflict.remote_updated_at > conflict.local_updated_at:
                merged[conflict.field_name] = conflict.remote_value
                conflict.resolution = ConflictAction.USE_REMOTE
                conflict.resolved_value = conflict.remote_value
            else:
                conflict.resolution = ConflictAction.USE_LOCAL
                conflict.resolved_value = conflict.local_value
        else:
            # No timestamps – prefer remote (source of truth for inbound)
            merged[conflict.field_name] = conflict.remote_value
            conflict.resolution = ConflictAction.USE_REMOTE
            conflict.resolved_value = conflict.remote_value

    def _resolve_source_wins(self, conflict: FieldConflict, merged: Dict) -> None:
        """External source always wins."""
        merged[conflict.field_name] = conflict.remote_value
        conflict.resolution = ConflictAction.USE_REMOTE
        conflict.resolved_value = conflict.remote_value

    def _resolve_ariia_wins(self, conflict: FieldConflict, merged: Dict) -> None:
        """ARIIA data always wins."""
        conflict.resolution = ConflictAction.USE_LOCAL
        conflict.resolved_value = conflict.local_value

    def _resolve_manual(self, conflict: FieldConflict, merged: Dict) -> None:
        """Flag for manual review – keep local value for now."""
        conflict.resolution = ConflictAction.FLAG_REVIEW
        conflict.resolved_value = conflict.local_value

    def _resolve_field_level(self, conflict: FieldConflict, merged: Dict) -> None:
        """Smart per-field resolution."""
        field = conflict.field_name

        if field in self.CRITICAL_FIELDS:
            # Critical fields: flag for review if both have values
            conflict.resolution = ConflictAction.FLAG_REVIEW
            conflict.resolved_value = conflict.local_value

        elif field in self.COMPLETENESS_FIELDS:
            # Prefer the more complete value
            local_len = len(str(conflict.local_value)) if conflict.local_value else 0
            remote_len = len(str(conflict.remote_value)) if conflict.remote_value else 0
            if remote_len > local_len:
                merged[conflict.field_name] = conflict.remote_value
                conflict.resolution = ConflictAction.USE_REMOTE
                conflict.resolved_value = conflict.remote_value
            else:
                conflict.resolution = ConflictAction.USE_LOCAL
                conflict.resolved_value = conflict.local_value

        elif field in self.SAFE_MERGE_FIELDS:
            # Safe fields: source wins
            merged[conflict.field_name] = conflict.remote_value
            conflict.resolution = ConflictAction.USE_REMOTE
            conflict.resolved_value = conflict.remote_value

        else:
            # Default: last write wins
            self._resolve_last_write_wins(conflict, merged)

    @staticmethod
    def _values_equal(a: Any, b: Any) -> bool:
        """Compare two values, handling type differences."""
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        # Normalize strings
        if isinstance(a, str) and isinstance(b, str):
            return a.strip().lower() == b.strip().lower()
        # Compare as strings as fallback
        return str(a) == str(b)


# Default resolver instance
default_resolver = ConflictResolver(
    default_strategy=ConflictStrategy.LAST_WRITE_WINS,
)
