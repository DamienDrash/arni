"""Magicline Integration Package."""

from app.integrations.magicline.client import MagiclineClient
from config.settings import get_settings

_client_instances: dict[int | str, MagiclineClient] = {}


def get_client(tenant_id: int | None = None) -> MagiclineClient:
    """Get or create a tenant-aware MagiclineClient.

    Reads base_url, api_key, and studio_id from the tenant's Settings table.
    Falls back to global env settings when tenant-specific settings are missing.

    Note: magicline_tenant_id was removed from global settings (S3.1).
    The studio_id is now per-tenant via the 'magicline_studio_id' setting key.
    """
    settings = get_settings()
    base_url = settings.magicline_base_url
    api_key = settings.magicline_api_key

    cache_key: int | str = "global"
    if tenant_id is not None:
        cache_key = tenant_id
        try:
            from app.gateway.persistence import persistence

            base_url = (
                persistence.get_setting("magicline_base_url", base_url, tenant_id=tenant_id)
                or base_url
            )
            api_key = (
                persistence.get_setting("magicline_api_key", api_key, tenant_id=tenant_id)
                or api_key
            )
        except Exception:
            # Persistence layer may be unavailable in isolated contexts; keep env fallback.
            pass

    client = _client_instances.get(cache_key)
    if client is not None:
        if client.base_url == (base_url or "").rstrip("/") and client.api_key == api_key:
            return client

    _client_instances[cache_key] = MagiclineClient(
        base_url=base_url,
        api_key=api_key,
    )
    return _client_instances[cache_key]


def get_studio_id(tenant_id: int | None = None) -> str:
    """Return the Magicline studio/tenant ID for a given tenant (S3.1).

    Reads 'magicline_studio_id' from the tenant's Settings table.
    Falls back to the global env setting magicline_studio_id.
    Returns empty string if not configured (sync will be skipped).
    """
    settings = get_settings()
    fallback = settings.magicline_studio_id or ""
    if tenant_id is None:
        return fallback
    try:
        from app.gateway.persistence import persistence
        val = persistence.get_setting("magicline_studio_id", fallback, tenant_id=tenant_id)
        return (val or fallback).strip()
    except Exception:
        return fallback
