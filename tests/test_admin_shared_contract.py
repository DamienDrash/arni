from __future__ import annotations

import json

from app.core.auth import AuthContext
from app.core.db import SessionLocal
from app.core.models import AuditLog, Tenant
from app.gateway.admin_shared import resolve_tenant_id_for_slug, write_admin_audit


def _ensure_tenant(*, slug: str, name: str) -> int:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
        if tenant is None:
            tenant = Tenant(slug=slug, name=name, is_active=True)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        return int(tenant.id)
    finally:
        db.close()


def test_resolve_tenant_id_for_slug_uses_target_tenant_for_system_admin() -> None:
    system_tenant_id = _ensure_tenant(slug="system", name="System")
    target_tenant_id = _ensure_tenant(slug="admin-shared-target", name="Admin Shared Target")
    actor = AuthContext(
        user_id="system-admin",
        email="system@example.test",
        tenant_id=system_tenant_id,
        tenant_slug="system",
        role="system_admin",
    )

    resolved = resolve_tenant_id_for_slug(actor, "admin-shared-target")

    assert resolved == target_tenant_id


def test_write_admin_audit_uses_impersonator_identity() -> None:
    db = SessionLocal()
    try:
        db.query(AuditLog).filter(AuditLog.action == "admin.shared.contract").delete()
        db.commit()
    finally:
        db.close()

    actor = AuthContext(
        user_id="tenant-admin",
        email="tenant@example.test",
        tenant_id=99,
        tenant_slug="tenant-99",
        role="tenant_admin",
        is_impersonating=True,
        impersonator_user_id="system-admin",
        impersonator_email="system@example.test",
        impersonator_tenant_id=1,
    )

    write_admin_audit(
        actor=actor,
        action="admin.shared.contract",
        category="admin",
        target_type="setting",
        target_id="voice_channel_enabled",
        details={"value": "true"},
    )

    db = SessionLocal()
    try:
        row = (
            db.query(AuditLog)
            .filter(AuditLog.action == "admin.shared.contract")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert row is not None
        assert row.actor_user_id == "system-admin"
        assert row.actor_email == "system@example.test"
        assert row.tenant_id == 1
        assert json.loads(row.details_json or "{}") == {"value": "true"}
    finally:
        db.close()
