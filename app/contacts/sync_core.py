"""ARIIA v2.0 – Contact Sync Core Orchestrator.

@ARCH: Contacts-Sync Refactoring – Phase 1
Central orchestrator that coordinates contact synchronisation between
external sources (via Adapters) and the ARIIA Contact model.

Responsibilities:
  - Resolve adapter for a given integration
  - Load tenant-specific config from DB + Vault
  - Execute sync (full / incremental) via adapter → SyncService pipeline
  - Log sync results to sync_logs table
  - Manage sync schedules
  - Handle webhook dispatch to correct adapter

This module replaces the scattered sync logic that was previously
distributed across magicline/contact_sync.py, shopify/contact_sync.py,
and the gateway integrations_sync router.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type

import structlog
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.contacts.sync_service import ContactSyncService, contact_sync_service
from app.core.db import SessionLocal
from app.core.integration_models import (
    IntegrationDefinition,
    SyncLog,
    SyncSchedule,
    TenantIntegration,
)
from app.core.security.vault import CredentialVault
from app.integrations.adapters.base import (
    BaseAdapter,
    ConnectionTestResult,
    NormalizedContact,
    SyncDirection,
    SyncMode,
    SyncResult,
)

logger = structlog.get_logger()


class AdapterRegistry:
    """Registry of all available contact-sync adapters.

    Adapters register themselves here. The SyncCore uses this registry
    to look up the correct adapter for a given integration_id.
    """

    _adapters: Dict[str, BaseAdapter] = {}

    @classmethod
    def register(cls, adapter: BaseAdapter) -> None:
        """Register an adapter instance."""
        cls._adapters[adapter.integration_id] = adapter
        logger.debug("adapter_registry.registered", adapter_id=adapter.integration_id)

    @classmethod
    def get(cls, integration_id: str) -> Optional[BaseAdapter]:
        """Get adapter by integration ID."""
        return cls._adapters.get(integration_id)

    @classmethod
    def get_all(cls) -> Dict[str, BaseAdapter]:
        """Get all registered adapters."""
        return dict(cls._adapters)

    @classmethod
    def get_sync_capable(cls) -> Dict[str, BaseAdapter]:
        """Get only adapters that support contact sync (have get_contacts)."""
        return {
            k: v for k, v in cls._adapters.items()
            if hasattr(v, "get_contacts") and callable(getattr(v, "get_contacts", None))
        }

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (for testing)."""
        cls._adapters.clear()


def _register_default_adapters() -> None:
    """Register all built-in adapters."""
    try:
        from app.integrations.adapters.magicline_adapter import MagiclineAdapter
        AdapterRegistry.register(MagiclineAdapter())
    except Exception as e:
        logger.warning("adapter_registry.magicline_failed", error=str(e))

    try:
        from app.integrations.adapters.shopify_adapter import ShopifyAdapter
        AdapterRegistry.register(ShopifyAdapter())
    except Exception as e:
        logger.warning("adapter_registry.shopify_failed", error=str(e))

    try:
        from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
        AdapterRegistry.register(WooCommerceAdapter())
    except Exception as e:
        logger.warning("adapter_registry.woocommerce_failed", error=str(e))

    try:
        from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
        AdapterRegistry.register(HubSpotAdapter())
    except Exception as e:
        logger.warning("adapter_registry.hubspot_failed", error=str(e))

    try:
        from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
        AdapterRegistry.register(SalesforceAdapter())
    except Exception as e:
        logger.warning("adapter_registry.salesforce_failed", error=str(e))


# Auto-register on module load
_register_default_adapters()


class SyncCore:
    """Central orchestrator for contact synchronisation.

    Usage:
        core = SyncCore()
        result = await core.run_sync(tenant_id=1, integration_id="magicline")
        result = await core.test_connection(tenant_id=1, integration_id="shopify", config={...})
    """

    def __init__(self):
        self.vault = CredentialVault()
        self.sync_service = contact_sync_service

    # ── Integration Management ───────────────────────────────────────────

    def get_available_integrations(self) -> List[Dict[str, Any]]:
        """List all available integrations with their config schemas."""
        result = []
        for adapter_id, adapter in AdapterRegistry.get_sync_capable().items():
            result.append({
                "integration_id": adapter.integration_id,
                "display_name": adapter.display_name,
                "category": adapter.category,
                "supported_sync_directions": [d.value for d in adapter.supported_sync_directions],
                "supports_incremental_sync": adapter.supports_incremental_sync,
                "supports_webhooks": adapter.supports_webhooks,
                "config_schema": adapter.get_config_schema(),
            })
        return result

    def get_tenant_integrations(self, tenant_id: int) -> List[Dict[str, Any]]:
        """List all integrations configured for a tenant."""
        db = SessionLocal()
        try:
            integrations = (
                db.query(TenantIntegration)
                .filter(TenantIntegration.tenant_id == tenant_id)
                .all()
            )
            result = []
            for ti in integrations:
                adapter = AdapterRegistry.get(ti.integration_id)
                last_sync = self._get_last_sync_log(db, tenant_id, ti.integration_id)

                result.append({
                    "id": ti.id,
                    "integration_id": ti.integration_id,
                    "display_name": adapter.display_name if adapter else ti.integration_id,
                    "category": adapter.category if adapter else "unknown",
                    "status": ti.status,
                    "enabled": ti.enabled,
                    "sync_direction": ti.sync_direction,
                    "sync_interval_minutes": ti.sync_interval_minutes,
                    "last_sync_at": ti.last_sync_at.isoformat() if ti.last_sync_at else None,
                    "last_sync_status": ti.last_sync_status,
                    "last_sync_message": ti.last_sync_message,
                    "last_sync_log": last_sync,
                    "created_at": ti.created_at.isoformat() if ti.created_at else None,
                })
            return result
        finally:
            db.close()

    # ── Connection Test ──────────────────────────────────────────────────

    async def test_connection(
        self,
        tenant_id: int,
        integration_id: str,
        config: Dict[str, Any],
    ) -> ConnectionTestResult:
        """Test connection to an external integration.

        This is called during the setup wizard BEFORE saving credentials.
        """
        adapter = AdapterRegistry.get(integration_id)
        if not adapter:
            return ConnectionTestResult(
                success=False,
                message=f"Unbekannte Integration: {integration_id}",
            )

        try:
            result = await adapter.test_connection(config)
            logger.info(
                "sync_core.connection_test",
                tenant_id=tenant_id,
                integration_id=integration_id,
                success=result.success,
            )
            return result
        except Exception as e:
            logger.error(
                "sync_core.connection_test_error",
                tenant_id=tenant_id,
                integration_id=integration_id,
                error=str(e),
            )
            return ConnectionTestResult(
                success=False,
                message=f"Verbindungstest fehlgeschlagen: {str(e)}",
            )

    # ── Save / Update Integration Config ─────────────────────────────────

    def save_integration(
        self,
        tenant_id: int,
        integration_id: str,
        config: Dict[str, Any],
        sync_direction: str = "inbound",
        sync_interval_minutes: int = 60,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """Save or update an integration configuration for a tenant.

        Credentials are stored in the Vault (encrypted), non-secret
        config is stored in tenant_integrations.config_json.
        """
        adapter = AdapterRegistry.get(integration_id)
        if not adapter:
            raise ValueError(f"Unbekannte Integration: {integration_id}")

        # Separate secrets from non-secret config
        schema = adapter.get_config_schema()
        secret_fields = {f["key"] for f in schema.get("fields", []) if f.get("type") == "password"}
        secrets = {k: v for k, v in config.items() if k in secret_fields}
        non_secrets = {k: v for k, v in config.items() if k not in secret_fields}

        db = SessionLocal()
        try:
            # Upsert tenant_integration record
            ti = (
                db.query(TenantIntegration)
                .filter(
                    TenantIntegration.tenant_id == tenant_id,
                    TenantIntegration.integration_id == integration_id,
                )
                .first()
            )

            if ti:
                ti.config_json = json.dumps(non_secrets, ensure_ascii=False)
                ti.sync_direction = sync_direction
                ti.sync_interval_minutes = sync_interval_minutes
                ti.enabled = enabled
                ti.status = "configured"
                ti.updated_at = datetime.now(timezone.utc)
            else:
                ti = TenantIntegration(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    config_json=json.dumps(non_secrets, ensure_ascii=False),
                    sync_direction=sync_direction,
                    sync_interval_minutes=sync_interval_minutes,
                    enabled=enabled,
                    status="configured",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(ti)

            db.commit()
            db.refresh(ti)

            # Store secrets in Vault
            if secrets:
                self.vault.store_credentials(tenant_id, integration_id, secrets)

            logger.info(
                "sync_core.integration_saved",
                tenant_id=tenant_id,
                integration_id=integration_id,
                enabled=enabled,
            )

            return {
                "id": ti.id,
                "integration_id": integration_id,
                "status": ti.status,
                "enabled": enabled,
                "message": "Integration erfolgreich gespeichert.",
            }

        except Exception as e:
            db.rollback()
            logger.error("sync_core.save_failed", error=str(e))
            raise
        finally:
            db.close()

    def delete_integration(self, tenant_id: int, integration_id: str) -> Dict[str, Any]:
        """Remove an integration configuration for a tenant."""
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
                return {"success": False, "message": "Integration nicht gefunden."}

            db.delete(ti)
            db.commit()

            # Remove credentials from Vault
            self.vault.delete_credentials(tenant_id, integration_id)

            logger.info("sync_core.integration_deleted", tenant_id=tenant_id, integration_id=integration_id)
            return {"success": True, "message": "Integration erfolgreich entfernt."}
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    # ── Run Sync ─────────────────────────────────────────────────────────

    async def run_sync(
        self,
        tenant_id: int,
        integration_id: str,
        sync_mode: Optional[SyncMode] = None,
        triggered_by: str = "manual",
    ) -> Dict[str, Any]:
        """Execute a contact sync for a specific integration.

        Steps:
          1. Load tenant integration config + credentials
          2. Resolve adapter
          3. Call adapter.get_contacts()
          4. Pass NormalizedContacts to ContactSyncService
          5. Log results to sync_logs
          6. Update tenant_integration status

        Args:
            tenant_id: Tenant to sync
            integration_id: Which integration to sync
            sync_mode: FULL or INCREMENTAL (auto-detected if None)
            triggered_by: Who triggered the sync (manual, scheduler, webhook)

        Returns:
            Dict with sync result summary
        """
        adapter = AdapterRegistry.get(integration_id)
        if not adapter:
            return {"success": False, "error": f"Unbekannte Integration: {integration_id}"}

        db = SessionLocal()
        sync_start = datetime.now(timezone.utc)

        try:
            # Load tenant integration config
            ti = (
                db.query(TenantIntegration)
                .filter(
                    TenantIntegration.tenant_id == tenant_id,
                    TenantIntegration.integration_id == integration_id,
                )
                .first()
            )
            if not ti:
                return {"success": False, "error": "Integration nicht konfiguriert für diesen Tenant."}

            if not ti.enabled:
                return {"success": False, "error": "Integration ist deaktiviert."}

            # Build full config (non-secrets from DB + secrets from Vault)
            config = {}
            if ti.config_json:
                try:
                    config = json.loads(ti.config_json)
                except (json.JSONDecodeError, TypeError):
                    config = {}

            # Merge credentials from Vault
            try:
                creds = self.vault.get_credentials(tenant_id, integration_id)
                config.update(creds)
            except Exception:
                pass  # No credentials stored yet

            # Determine sync mode
            if sync_mode is None:
                if ti.last_sync_at and adapter.supports_incremental_sync:
                    sync_mode = SyncMode.INCREMENTAL
                else:
                    sync_mode = SyncMode.FULL

            last_sync_at = ti.last_sync_at

            logger.info(
                "sync_core.sync_started",
                tenant_id=tenant_id,
                integration_id=integration_id,
                sync_mode=sync_mode.value,
                triggered_by=triggered_by,
            )

            # Update status to syncing
            ti.status = "syncing"
            ti.last_sync_status = "running"
            db.commit()

        except Exception as e:
            db.close()
            return {"success": False, "error": f"Konfiguration konnte nicht geladen werden: {str(e)}"}

        # Execute sync (outside the config-loading try block)
        try:
            # Step 1: Fetch contacts from external source via adapter
            adapter_result: SyncResult = await adapter.get_contacts(
                tenant_id=tenant_id,
                config=config,
                last_sync_at=last_sync_at,
                sync_mode=sync_mode,
            )

            if not adapter_result.success:
                # Adapter failed – log and update status
                self._log_sync(
                    db, tenant_id, integration_id, sync_start,
                    success=False, error_message=adapter_result.error_message,
                    triggered_by=triggered_by, sync_mode=sync_mode,
                )
                ti.status = "error"
                ti.last_sync_status = "error"
                ti.last_sync_message = adapter_result.error_message or "Adapter-Fehler"
                db.commit()
                db.close()
                return {
                    "success": False,
                    "error": adapter_result.error_message,
                    "integration_id": integration_id,
                }

            # Step 2: Convert adapter NormalizedContacts to sync_service NormalizedContacts
            from app.contacts.sync_service import NormalizedContact as SvcNormalizedContact

            svc_contacts = []
            for nc in adapter_result.contacts:
                svc_nc = SvcNormalizedContact(
                    source_id=nc.external_id,
                    first_name=nc.first_name,
                    last_name=nc.last_name,
                    email=nc.email,
                    phone=nc.phone,
                    company=nc.company,
                    lifecycle_stage=nc.lifecycle_stage or "subscriber",
                    tags=nc.tags,
                    custom_fields=nc.custom_fields,
                    consent_email=nc.custom_fields.get("consent_email", False) if nc.custom_fields else False,
                    consent_sms=nc.custom_fields.get("consent_sms", False) if nc.custom_fields else False,
                )
                svc_contacts.append(svc_nc)

            # Step 3: Upsert into contacts table
            svc_result = self.sync_service.sync_contacts(
                tenant_id=tenant_id,
                source=integration_id,
                contacts=svc_contacts,
                full_sync=(sync_mode == SyncMode.FULL),
                delete_missing=False,
                performed_by_name=f"{adapter.display_name} Sync ({triggered_by})",
            )

            # Step 4: Log success
            sync_end = datetime.now(timezone.utc)
            duration_ms = (sync_end - sync_start).total_seconds() * 1000

            summary = {
                "records_fetched": adapter_result.records_fetched,
                "records_created": svc_result.created,
                "records_updated": svc_result.updated,
                "records_unchanged": svc_result.unchanged,
                "records_deleted": svc_result.deleted,
                "records_failed": svc_result.errors,
                "duration_ms": duration_ms,
                "sync_mode": sync_mode.value,
                "triggered_by": triggered_by,
            }

            self._log_sync(
                db, tenant_id, integration_id, sync_start,
                success=True, summary=summary,
                triggered_by=triggered_by, sync_mode=sync_mode,
                records_fetched=adapter_result.records_fetched,
                records_created=svc_result.created,
                records_updated=svc_result.updated,
                records_failed=svc_result.errors,
                duration_ms=duration_ms,
            )

            # Step 5: Update tenant_integration status
            ti.status = "connected"
            ti.last_sync_at = sync_end
            ti.last_sync_status = "success"
            ti.last_sync_message = (
                f"Sync erfolgreich: {svc_result.created} erstellt, "
                f"{svc_result.updated} aktualisiert, "
                f"{svc_result.unchanged} unverändert."
            )
            db.commit()

            logger.info(
                "sync_core.sync_completed",
                tenant_id=tenant_id,
                integration_id=integration_id,
                **summary,
            )

            return {"success": True, "integration_id": integration_id, **summary}

        except Exception as e:
            # Unexpected error
            error_msg = f"Sync fehlgeschlagen: {str(e)}"
            tb = traceback.format_exc()
            logger.error(
                "sync_core.sync_error",
                tenant_id=tenant_id,
                integration_id=integration_id,
                error=str(e),
                traceback=tb,
            )

            try:
                self._log_sync(
                    db, tenant_id, integration_id, sync_start,
                    success=False, error_message=error_msg,
                    triggered_by=triggered_by, sync_mode=sync_mode,
                )
                ti.status = "error"
                ti.last_sync_status = "error"
                ti.last_sync_message = error_msg
                db.commit()
            except Exception:
                db.rollback()

            return {"success": False, "error": error_msg, "integration_id": integration_id}

        finally:
            db.close()

    # ── Webhook Dispatch ─────────────────────────────────────────────────

    async def handle_webhook(
        self,
        tenant_id: int,
        integration_id: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Dispatch incoming webhook to the correct adapter.

        Called by the webhook receiver endpoint when an external system
        sends a webhook notification.
        """
        adapter = AdapterRegistry.get(integration_id)
        if not adapter:
            return {"success": False, "error": f"Kein Adapter für {integration_id}"}

        if not adapter.supports_webhooks:
            return {"success": False, "error": f"{integration_id} unterstützt keine Webhooks"}

        db = SessionLocal()
        try:
            # Load config
            ti = (
                db.query(TenantIntegration)
                .filter(
                    TenantIntegration.tenant_id == tenant_id,
                    TenantIntegration.integration_id == integration_id,
                )
                .first()
            )
            if not ti:
                return {"success": False, "error": "Integration nicht konfiguriert"}

            config = {}
            if ti.config_json:
                try:
                    config = json.loads(ti.config_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            try:
                creds = self.vault.get_credentials(tenant_id, integration_id)
                config.update(creds)
            except Exception:
                pass

            # Dispatch to adapter
            result = await adapter.handle_webhook(tenant_id, config, payload, headers)

            if result.success and result.contacts:
                from app.contacts.sync_service import NormalizedContact as SvcNormalizedContact

                svc_contacts = []
                for nc in result.contacts:
                    svc_nc = SvcNormalizedContact(
                        source_id=nc.external_id,
                        first_name=nc.first_name,
                        last_name=nc.last_name,
                        email=nc.email,
                        phone=nc.phone,
                        company=nc.company,
                        lifecycle_stage=nc.lifecycle_stage or "subscriber",
                        tags=nc.tags,
                        custom_fields=nc.custom_fields,
                    )
                    svc_contacts.append(svc_nc)

                svc_result = self.sync_service.sync_contacts(
                    tenant_id=tenant_id,
                    source=integration_id,
                    contacts=svc_contacts,
                    full_sync=False,
                    performed_by_name=f"{adapter.display_name} Webhook",
                )

                return {
                    "success": True,
                    "created": svc_result.created,
                    "updated": svc_result.updated,
                }

            return {"success": result.success, "metadata": result.metadata}

        except Exception as e:
            logger.error("sync_core.webhook_error", error=str(e))
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    # ── Sync History ─────────────────────────────────────────────────────

    def get_sync_history(
        self,
        tenant_id: int,
        integration_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get sync history for a tenant, optionally filtered by integration."""
        db = SessionLocal()
        try:
            query = db.query(SyncLog).filter(SyncLog.tenant_id == tenant_id)
            if integration_id:
                query = query.filter(SyncLog.integration_id == integration_id)
            logs = query.order_by(desc(SyncLog.started_at)).limit(limit).all()

            return [
                {
                    "id": log.id,
                    "integration_id": log.integration_id,
                    "sync_mode": log.sync_mode,
                    "status": log.status,
                    "triggered_by": log.triggered_by,
                    "records_fetched": log.records_fetched,
                    "records_created": log.records_created,
                    "records_updated": log.records_updated,
                    "records_failed": log.records_failed,
                    "duration_ms": log.duration_ms,
                    "error_message": log.error_message,
                    "started_at": log.started_at.isoformat() if log.started_at else None,
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                }
                for log in logs
            ]
        finally:
            db.close()

    # ── Private Helpers ──────────────────────────────────────────────────

    def _log_sync(
        self,
        db: Session,
        tenant_id: int,
        integration_id: str,
        started_at: datetime,
        success: bool,
        error_message: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        triggered_by: str = "manual",
        sync_mode: Optional[SyncMode] = None,
        records_fetched: int = 0,
        records_created: int = 0,
        records_updated: int = 0,
        records_failed: int = 0,
        duration_ms: float = 0,
    ) -> None:
        """Write a sync log entry."""
        completed_at = datetime.now(timezone.utc)
        if not duration_ms:
            duration_ms = (completed_at - started_at).total_seconds() * 1000

        log = SyncLog(
            tenant_id=tenant_id,
            integration_id=integration_id,
            sync_mode=sync_mode.value if sync_mode else "full",
            status="success" if success else "error",
            triggered_by=triggered_by,
            records_fetched=records_fetched,
            records_created=records_created,
            records_updated=records_updated,
            records_failed=records_failed,
            duration_ms=int(duration_ms),
            error_message=error_message,
            summary_json=json.dumps(summary, ensure_ascii=False, default=str) if summary else None,
            started_at=started_at,
            completed_at=completed_at,
        )
        db.add(log)
        try:
            db.commit()
        except Exception:
            db.rollback()

    def _get_last_sync_log(
        self, db: Session, tenant_id: int, integration_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent sync log for an integration."""
        log = (
            db.query(SyncLog)
            .filter(
                SyncLog.tenant_id == tenant_id,
                SyncLog.integration_id == integration_id,
            )
            .order_by(desc(SyncLog.started_at))
            .first()
        )
        if not log:
            return None
        return {
            "status": log.status,
            "records_fetched": log.records_fetched,
            "records_created": log.records_created,
            "records_updated": log.records_updated,
            "duration_ms": log.duration_ms,
            "started_at": log.started_at.isoformat() if log.started_at else None,
        }


# Singleton instance
sync_core = SyncCore()
