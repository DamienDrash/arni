from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.platform.models import TenantConfig


class PlatformQueries:
    """Cross-domain access for platform-owned tenant settings."""

    def get_tenant_config(self, db: Session, *, tenant_id: int, key: str) -> TenantConfig | None:
        return (
            db.query(TenantConfig)
            .filter(TenantConfig.tenant_id == tenant_id, TenantConfig.key == key)
            .first()
        )

    def set_tenant_config(self, db: Session, *, tenant_id: int, key: str, value: str) -> TenantConfig:
        row = self.get_tenant_config(db, tenant_id=tenant_id, key=key)
        if row:
            row.value = value
            return row
        row = TenantConfig(tenant_id=tenant_id, key=key, value=value)
        db.add(row)
        return row


platform_queries = PlatformQueries()
