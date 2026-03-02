"""ARIIA v2.0 – Contact Sync Health Check Service.

@ARCH: Contacts-Sync Refactoring, Phase 4
Provides health monitoring for all configured integrations.

Responsibilities:
  - Periodic health checks for each integration
  - Detect stale syncs (last sync too long ago)
  - Detect error patterns (consecutive failures)
  - Provide aggregated health status for monitoring dashboard
  - Generate alerts for critical issues
"""

from __future__ import annotations

import traceback
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

from app.core.db import SessionLocal
from app.core.integration_models import TenantIntegration, SyncLog

logger = structlog.get_logger()


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


class IntegrationHealth:
    """Health status for a single integration."""

    def __init__(
        self,
        tenant_id: int,
        integration_id: str,
        display_name: str,
    ):
        self.tenant_id = tenant_id
        self.integration_id = integration_id
        self.display_name = display_name
        self.status: HealthStatus = HealthStatus.UNKNOWN
        self.enabled: bool = True
        self.issues: List[str] = []
        self.metrics: Dict[str, Any] = {}
        self.last_check_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "integration_id": self.integration_id,
            "display_name": self.display_name,
            "status": self.status.value,
            "enabled": self.enabled,
            "issues": self.issues,
            "metrics": self.metrics,
            "last_check_at": self.last_check_at.isoformat() if self.last_check_at else None,
        }


class SyncHealthService:
    """Monitors health of all contact sync integrations."""

    # Thresholds
    STALE_SYNC_WARNING_FACTOR = 3.0   # 3x the sync interval
    STALE_SYNC_CRITICAL_FACTOR = 10.0  # 10x the sync interval
    CONSECUTIVE_ERROR_WARNING = 3
    CONSECUTIVE_ERROR_CRITICAL = 5
    HIGH_FAILURE_RATE_WARNING = 0.2   # 20% failure rate
    HIGH_FAILURE_RATE_CRITICAL = 0.5  # 50% failure rate
    SLOW_SYNC_WARNING_MS = 60_000     # 60 seconds
    SLOW_SYNC_CRITICAL_MS = 300_000   # 5 minutes

    def check_integration_health(
        self,
        tenant_id: int,
        integration_id: str,
    ) -> IntegrationHealth:
        """Run health checks for a single integration."""
        db = SessionLocal()
        try:
            ti = (
                db.query(TenantIntegration)
                .filter(
                    TenantIntegration.tenant_id == tenant_id,
                    TenantIntegration.integration_id == integration_id,
                )
                .first()
            )

            if not ti:
                health = IntegrationHealth(tenant_id, integration_id, integration_id)
                health.status = HealthStatus.UNKNOWN
                health.issues.append("Integration nicht gefunden")
                return health

            health = IntegrationHealth(
                tenant_id=tenant_id,
                integration_id=integration_id,
                display_name=ti.display_name or integration_id,
            )
            health.enabled = ti.enabled
            health.last_check_at = datetime.now(timezone.utc)

            if not ti.enabled:
                health.status = HealthStatus.DISABLED
                return health

            # Get recent sync logs
            from sqlalchemy import desc
            recent_logs = (
                db.query(SyncLog)
                .filter(
                    SyncLog.tenant_id == tenant_id,
                    SyncLog.integration_id == integration_id,
                )
                .order_by(desc(SyncLog.started_at))
                .limit(20)
                .all()
            )

            # Run individual checks
            issues_warning = []
            issues_critical = []

            self._check_stale_sync(ti, health, issues_warning, issues_critical)
            self._check_consecutive_errors(recent_logs, health, issues_warning, issues_critical)
            self._check_failure_rate(recent_logs, health, issues_warning, issues_critical)
            self._check_sync_duration(recent_logs, health, issues_warning, issues_critical)
            self._compute_metrics(ti, recent_logs, health)

            # Determine overall status
            if issues_critical:
                health.status = HealthStatus.CRITICAL
                health.issues = issues_critical + issues_warning
            elif issues_warning:
                health.status = HealthStatus.WARNING
                health.issues = issues_warning
            else:
                health.status = HealthStatus.HEALTHY

            return health

        except Exception as e:
            logger.error("sync_health.check_error", error=str(e), traceback=traceback.format_exc())
            health = IntegrationHealth(tenant_id, integration_id, integration_id)
            health.status = HealthStatus.UNKNOWN
            health.issues.append(f"Health-Check fehlgeschlagen: {str(e)}")
            return health
        finally:
            db.close()

    def check_all_integrations(self, tenant_id: int) -> List[IntegrationHealth]:
        """Run health checks for all integrations of a tenant."""
        db = SessionLocal()
        try:
            integrations = (
                db.query(TenantIntegration)
                .filter(TenantIntegration.tenant_id == tenant_id)
                .all()
            )

            results = []
            for ti in integrations:
                health = self.check_integration_health(tenant_id, ti.integration_id)
                results.append(health)

            return results
        except Exception as e:
            logger.error("sync_health.check_all_error", error=str(e))
            return []
        finally:
            db.close()

    def get_system_health_summary(self, tenant_id: int) -> Dict[str, Any]:
        """Get aggregated health summary for monitoring dashboard."""
        checks = self.check_all_integrations(tenant_id)

        total = len(checks)
        healthy = sum(1 for c in checks if c.status == HealthStatus.HEALTHY)
        warning = sum(1 for c in checks if c.status == HealthStatus.WARNING)
        critical = sum(1 for c in checks if c.status == HealthStatus.CRITICAL)
        disabled = sum(1 for c in checks if c.status == HealthStatus.DISABLED)
        unknown = sum(1 for c in checks if c.status == HealthStatus.UNKNOWN)

        # Overall system status
        if critical > 0:
            overall = HealthStatus.CRITICAL
        elif warning > 0:
            overall = HealthStatus.WARNING
        elif healthy > 0:
            overall = HealthStatus.HEALTHY
        else:
            overall = HealthStatus.UNKNOWN

        # Aggregate metrics
        total_synced = 0
        total_errors = 0
        avg_duration_ms = 0
        duration_count = 0

        for check in checks:
            m = check.metrics
            total_synced += m.get("total_records_synced_24h", 0)
            total_errors += m.get("errors_24h", 0)
            if m.get("avg_duration_ms"):
                avg_duration_ms += m["avg_duration_ms"]
                duration_count += 1

        return {
            "overall_status": overall.value,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total": total,
                "healthy": healthy,
                "warning": warning,
                "critical": critical,
                "disabled": disabled,
                "unknown": unknown,
            },
            "aggregated_metrics": {
                "total_records_synced_24h": total_synced,
                "total_errors_24h": total_errors,
                "avg_sync_duration_ms": round(avg_duration_ms / duration_count) if duration_count > 0 else 0,
            },
            "integrations": [c.to_dict() for c in checks],
        }

    # ── Individual Health Checks ──────────────────────────────────────────────

    def _check_stale_sync(
        self,
        ti: TenantIntegration,
        health: IntegrationHealth,
        warnings: List[str],
        criticals: List[str],
    ) -> None:
        """Check if the last sync is too old."""
        if not ti.last_sync_at:
            warnings.append("Noch nie synchronisiert")
            return

        now = datetime.now(timezone.utc)
        last_sync = ti.last_sync_at
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)

        interval = timedelta(minutes=ti.sync_interval_minutes or 60)
        age = now - last_sync

        warning_threshold = interval * self.STALE_SYNC_WARNING_FACTOR
        critical_threshold = interval * self.STALE_SYNC_CRITICAL_FACTOR

        if age > critical_threshold:
            hours = age.total_seconds() / 3600
            criticals.append(f"Letzter Sync vor {hours:.1f} Stunden (kritisch veraltet)")
        elif age > warning_threshold:
            hours = age.total_seconds() / 3600
            warnings.append(f"Letzter Sync vor {hours:.1f} Stunden (veraltet)")

    def _check_consecutive_errors(
        self,
        logs: List[SyncLog],
        health: IntegrationHealth,
        warnings: List[str],
        criticals: List[str],
    ) -> None:
        """Check for consecutive sync errors."""
        consecutive = 0
        for log in logs:
            if log.status == "error":
                consecutive += 1
            else:
                break

        if consecutive >= self.CONSECUTIVE_ERROR_CRITICAL:
            criticals.append(f"{consecutive} aufeinanderfolgende Sync-Fehler")
        elif consecutive >= self.CONSECUTIVE_ERROR_WARNING:
            warnings.append(f"{consecutive} aufeinanderfolgende Sync-Fehler")

        health.metrics["consecutive_errors"] = consecutive

    def _check_failure_rate(
        self,
        logs: List[SyncLog],
        health: IntegrationHealth,
        warnings: List[str],
        criticals: List[str],
    ) -> None:
        """Check the failure rate over recent syncs."""
        if len(logs) < 5:
            return  # Not enough data

        errors = sum(1 for l in logs if l.status == "error")
        rate = errors / len(logs)

        if rate >= self.HIGH_FAILURE_RATE_CRITICAL:
            criticals.append(f"Fehlerrate {rate:.0%} in den letzten {len(logs)} Syncs")
        elif rate >= self.HIGH_FAILURE_RATE_WARNING:
            warnings.append(f"Fehlerrate {rate:.0%} in den letzten {len(logs)} Syncs")

        health.metrics["failure_rate"] = round(rate, 3)

    def _check_sync_duration(
        self,
        logs: List[SyncLog],
        health: IntegrationHealth,
        warnings: List[str],
        criticals: List[str],
    ) -> None:
        """Check if syncs are taking too long."""
        successful_logs = [l for l in logs if l.status == "success" and l.duration_ms]
        if not successful_logs:
            return

        avg_duration = sum(l.duration_ms for l in successful_logs) / len(successful_logs)
        max_duration = max(l.duration_ms for l in successful_logs)

        if avg_duration >= self.SLOW_SYNC_CRITICAL_MS:
            criticals.append(f"Durchschnittliche Sync-Dauer {avg_duration / 1000:.1f}s (kritisch langsam)")
        elif avg_duration >= self.SLOW_SYNC_WARNING_MS:
            warnings.append(f"Durchschnittliche Sync-Dauer {avg_duration / 1000:.1f}s (langsam)")

        health.metrics["avg_duration_ms"] = round(avg_duration)
        health.metrics["max_duration_ms"] = max_duration

    def _compute_metrics(
        self,
        ti: TenantIntegration,
        logs: List[SyncLog],
        health: IntegrationHealth,
    ) -> None:
        """Compute additional metrics for the dashboard."""
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        logs_24h = [l for l in logs if l.started_at and l.started_at.replace(tzinfo=timezone.utc) >= last_24h]
        logs_7d = [l for l in logs if l.started_at and l.started_at.replace(tzinfo=timezone.utc) >= last_7d]

        # Records synced in last 24h
        records_24h = sum(
            (l.records_created or 0) + (l.records_updated or 0)
            for l in logs_24h
        )

        # Errors in last 24h
        errors_24h = sum(1 for l in logs_24h if l.status == "error")

        # Success rate 7d
        success_7d = sum(1 for l in logs_7d if l.status == "success")
        total_7d = len(logs_7d)

        health.metrics.update({
            "total_records_synced_24h": records_24h,
            "errors_24h": errors_24h,
            "syncs_24h": len(logs_24h),
            "syncs_7d": total_7d,
            "success_rate_7d": round(success_7d / total_7d, 3) if total_7d > 0 else None,
            "last_sync_at": ti.last_sync_at.isoformat() if ti.last_sync_at else None,
            "last_sync_status": ti.last_sync_status,
            "sync_interval_minutes": ti.sync_interval_minutes,
        })


# Singleton
sync_health_service = SyncHealthService()
