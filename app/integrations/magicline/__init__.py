"""Magicline Integration Package."""

from app.integrations.magicline.client import MagiclineClient

_client_instances: dict[int, MagiclineClient] = {}


def get_client(tenant_id: int) -> MagiclineClient:
    """Get or create a tenant-aware MagiclineClient.

    Reads base_url and api_key exclusively from the tenant's Settings table.
    No more global environment fallbacks for tenant-specific integrations.
    """
    if tenant_id is None:
        raise ValueError("MagiclineClient requires a tenant_id for configuration.")

    from app.gateway.persistence import persistence

    base_url = persistence.get_setting("magicline_base_url", tenant_id=tenant_id)
    api_key = persistence.get_setting("magicline_api_key", tenant_id=tenant_id)

    if not base_url or not api_key:
        raise ValueError(f"Magicline not configured for tenant {tenant_id}")

    cache_key = int(tenant_id)
    client = _client_instances.get(cache_key)
    
    if client is not None:
        if client.base_url == base_url.rstrip("/") and client.api_key == api_key:
            return client

    _client_instances[cache_key] = MagiclineClient(
        base_url=base_url,
        api_key=api_key,
    )
    return _client_instances[cache_key]


def get_studio_id(tenant_id: int) -> str:
    """Return the Magicline studio/tenant ID for a given tenant.

    Reads 'magicline_studio_id' from the tenant's Settings table.
    Returns empty string if not configured.
    """
    if tenant_id is None:
        return ""
    from app.gateway.persistence import persistence
    val = persistence.get_setting("magicline_studio_id", tenant_id=tenant_id)
    return (val or "").strip()
