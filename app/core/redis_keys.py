"""ARIIA – Tenant-scoped Redis key factory.

All Redis keys MUST go through this module to ensure tenant isolation.
No key may be stored without a tenant prefix.

Key schema:
    t{tenant_id}:{domain}:{identifier}

Examples:
    t7:token:123456
    t7:user_token:+4915112345678
    t7:human_mode:+4915112345678
    t7:dialog:+4915112345678
    t7:blacklist:jti:{jti}
    t7:user_blacklisted:{user_id}
"""


def redis_key(tenant_id: int | str, *parts: str) -> str:
    """Build a tenant-scoped Redis key.

    Args:
        tenant_id: Numeric tenant ID. Will be prefixed as 't{id}'.
        *parts:    Key path segments joined with ':'.

    Returns:
        Fully-qualified key string like 't7:token:123456'.
    """
    if not parts:
        raise ValueError("redis_key requires at least one path part")
    return f"t{tenant_id}:" + ":".join(str(p) for p in parts)


def token_key(tenant_id: int | str, token: str) -> str:
    return redis_key(tenant_id, "token", token)


def user_token_key(tenant_id: int | str, user_id: str) -> str:
    return redis_key(tenant_id, "user_token", user_id)


def human_mode_key(tenant_id: int | str, user_id: str) -> str:
    return redis_key(tenant_id, "human_mode", user_id)


def dialog_context_key(tenant_id: int | str, user_id: str) -> str:
    return redis_key(tenant_id, "dialog", user_id)


def jti_blacklist_key(tenant_id: int | str, jti: str) -> str:
    return redis_key(tenant_id, "blacklist", "jti", jti)


def user_blacklisted_key(tenant_id: int | str, user_id: int | str) -> str:
    return redis_key(tenant_id, "user_blacklisted", str(user_id))
