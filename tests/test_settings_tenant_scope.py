import time

from app.core.db import SessionLocal
from app.core.models import Tenant
from app.gateway.persistence import persistence


def _ensure_tenant(slug: str, name: str) -> Tenant:
    db = SessionLocal()
    try:
        row = db.query(Tenant).filter(Tenant.slug == slug).first()
        if row:
            return row
        row = Tenant(slug=slug, name=name, is_active=True)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def test_settings_are_isolated_per_tenant() -> None:
    unique = int(time.time() * 1000)
    tenant_a = _ensure_tenant(f"settings-a-{unique}", f"Settings A {unique}")
    tenant_b = _ensure_tenant(f"settings-b-{unique}", f"Settings B {unique}")

    persistence.upsert_setting("magicline_tenant_id", "alpha", tenant_id=tenant_a.id)
    persistence.upsert_setting("magicline_tenant_id", "beta", tenant_id=tenant_b.id)

    assert persistence.get_setting("magicline_tenant_id", tenant_id=tenant_a.id) == "alpha"
    assert persistence.get_setting("magicline_tenant_id", tenant_id=tenant_b.id) == "beta"


def test_global_billing_setting_is_system_scoped() -> None:
    unique = int(time.time() * 1000)
    system = _ensure_tenant("system", "System")
    tenant_x = _ensure_tenant(f"billing-x-{unique}", f"Billing X {unique}")
    tenant_y = _ensure_tenant(f"billing-y-{unique}", f"Billing Y {unique}")

    persistence.upsert_setting("billing_default_provider", "stripe", tenant_id=tenant_x.id)
    assert persistence.get_setting("billing_default_provider", tenant_id=tenant_y.id) == "stripe"
    assert persistence.get_setting("billing_default_provider", tenant_id=system.id) == "stripe"
