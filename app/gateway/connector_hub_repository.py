from __future__ import annotations

import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.domains.identity.models import Tenant
from app.domains.platform.models import Setting

_ENABLED_KEY_RE = re.compile(r"^integration_(?P<connector>.+)_(?P<tenant_id>\d+)_enabled$")


class ConnectorHubRepository:
    """Focused DB reads for connector hub catalog and admin helpers."""

    def get_tenant_by_id(self, db: Session, tenant_id: int) -> Tenant | None:
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def list_tenants(self, db: Session) -> list[Tenant]:
        return db.query(Tenant).all()

    def count_enabled_connectors_by_type(self, db: Session) -> dict[str, int]:
        rows = (
            db.query(Setting.key)
            .filter(
                Setting.value == "true",
                or_(
                    Setting.key.like("tenant:%:integration\\_%\\_enabled", escape="\\"),
                    Setting.key.like("integration\\_%\\_enabled", escape="\\"),
                ),
            )
            .all()
        )

        tenant_connector_pairs: set[tuple[str, str]] = set()
        for (raw_key,) in rows:
            key = raw_key or ""
            if key.startswith("tenant:"):
                parts = key.split(":", 2)
                if len(parts) == 3:
                    _, tenant_id, key = parts
                else:
                    continue
            else:
                tenant_id = ""

            match = _ENABLED_KEY_RE.match(key)
            if not match:
                continue

            connector_id = match.group("connector")
            parsed_tenant_id = match.group("tenant_id")
            tenant_connector_pairs.add((tenant_id or parsed_tenant_id, connector_id))

        usage: dict[str, int] = {}
        for _, connector_id in tenant_connector_pairs:
            usage[connector_id] = usage.get(connector_id, 0) + 1
        return usage

    def read_tenant_setting_value(
        self,
        db: Session,
        *,
        tenant_id: int,
        storage_key: str,
        legacy_key: str,
    ) -> str | None:
        row = (
            db.query(Setting)
            .filter(Setting.tenant_id == tenant_id, Setting.key.in_([storage_key, legacy_key]))
            .order_by(Setting.key.desc())
            .first()
        )
        if not row:
            return None
        return row.value


connector_hub_repository = ConnectorHubRepository()
