from __future__ import annotations

from app.domains.support.module import get_support_routers


def test_support_module_assembly_includes_consent_and_contacts_surfaces() -> None:
    routers = get_support_routers()
    prefixes = {getattr(router, "prefix", "") for router in routers}

    assert "/v2/contacts" in prefixes
    assert "/v2/admin/contacts" in prefixes
    assert "/admin/contacts" in prefixes
    assert "/admin/chats" in prefixes
    assert "/admin/agent-teams" in prefixes
