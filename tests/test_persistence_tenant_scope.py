import time

from app.core.db import SessionLocal
from app.core.models import Tenant
from app.gateway.persistence import persistence
from app.gateway.schemas import Platform


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


def test_chat_history_is_tenant_scoped_for_same_user_id() -> None:
    unique = int(time.time() * 1000)
    external_user_id = f"tenant-scope-user-{unique}"

    system = _ensure_tenant("system", "System")
    tenant_b = _ensure_tenant(f"scope-{unique}", f"Scope {unique}")

    persistence.save_message(
        user_id=external_user_id,
        role="user",
        content="hello-from-system",
        platform=Platform.TELEGRAM,
        metadata={"scope": "system"},
        tenant_id=system.id,
    )
    persistence.save_message(
        user_id=external_user_id,
        role="user",
        content="hello-from-tenant-b",
        platform=Platform.TELEGRAM,
        metadata={"scope": "tenant-b"},
        tenant_id=tenant_b.id,
    )

    system_history = persistence.get_chat_history(external_user_id, tenant_id=system.id, limit=20)
    tenant_b_history = persistence.get_chat_history(external_user_id, tenant_id=tenant_b.id, limit=20)

    system_contents = [m.content for m in system_history]
    tenant_b_contents = [m.content for m in tenant_b_history]

    assert "hello-from-system" in system_contents
    assert "hello-from-tenant-b" not in system_contents

    assert "hello-from-tenant-b" in tenant_b_contents
    assert "hello-from-system" not in tenant_b_contents


def test_recent_sessions_are_tenant_scoped() -> None:
    unique = int(time.time() * 1000)
    user_a = f"tenant-a-user-{unique}"
    user_b = f"tenant-b-user-{unique}"

    system = _ensure_tenant("system", "System")
    tenant_b = _ensure_tenant(f"scope2-{unique}", f"Scope2 {unique}")

    persistence.save_message(
        user_id=user_a,
        role="user",
        content="message-a",
        platform=Platform.WHATSAPP,
        tenant_id=system.id,
    )
    persistence.save_message(
        user_id=user_b,
        role="user",
        content="message-b",
        platform=Platform.WHATSAPP,
        tenant_id=tenant_b.id,
    )

    system_sessions = persistence.get_recent_sessions(limit=50, tenant_id=system.id)
    tenant_b_sessions = persistence.get_recent_sessions(limit=50, tenant_id=tenant_b.id)

    system_users = {s.user_id for s in system_sessions}
    tenant_b_users = {s.user_id for s in tenant_b_sessions}

    assert user_a in system_users
    assert user_b not in system_users
    assert user_b in tenant_b_users
    assert user_a not in tenant_b_users
