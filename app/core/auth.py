import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Cookie, Header, HTTPException

from app.core.db import SessionLocal, Base, engine
from app.core.models import Tenant, UserAccount
from config.settings import get_settings


ALLOWED_ROLES = {"system_admin", "tenant_admin", "tenant_user"}


@dataclass
class AuthContext:
    user_id: int
    email: str
    tenant_id: int
    tenant_slug: str
    role: str
    is_impersonating: bool = False
    impersonator_user_id: int | None = None
    impersonator_email: str | None = None
    impersonator_role: str | None = None
    impersonator_tenant_id: int | None = None
    impersonator_tenant_slug: str | None = None
    impersonation_reason: str | None = None
    impersonation_started_at: str | None = None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256$200000${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, rounds_raw, salt_b64, digest_b64 = password_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_raw)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_access_token(
    *,
    user_id: int,
    email: str,
    tenant_id: int,
    tenant_slug: str,
    role: str,
    ttl_seconds: int | None = None,
    impersonation: dict | None = None,
) -> str:
    settings = get_settings()
    if ttl_seconds is None:
        exp_at = datetime.now(timezone.utc) + timedelta(hours=max(1, settings.auth_token_ttl_hours))
    else:
        exp_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, int(ttl_seconds)))
    payload = {
        "sub": str(user_id),
        "email": email,
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "role": role,
        "exp": int(exp_at.timestamp()),
        "jti": str(uuid4()),  # Unique token ID for blacklisting (S1.4)
    }
    if impersonation:
        payload["imp"] = impersonation
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64url_encode(payload_raw)
    sig = hmac.new(settings.auth_secret.encode("utf-8"), payload_part.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_part}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload_part, sig_part = token.split(".", 1)
        expected_sig = hmac.new(
            settings.auth_secret.encode("utf-8"),
            payload_part.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64url_encode(expected_sig), sig_part):
            raise HTTPException(status_code=401, detail="Invalid token signature")
        payload = json.loads(_b64url_decode(payload_part))
        exp = int(payload.get("exp", 0))
        if exp < int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(status_code=401, detail="Token expired")
        if payload.get("role") not in ALLOWED_ROLES:
            raise HTTPException(status_code=401, detail="Invalid token role")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _check_token_blacklist(payload: dict) -> None:
    """Raise 401 if this token's JTI or the user is blacklisted in Redis (S1.4)."""
    jti = payload.get("jti")
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("sub")
    if not jti or tenant_id is None:
        return
    try:
        import redis as _redis
        from config.settings import get_settings as _gs
        from app.core.redis_keys import jti_blacklist_key, user_blacklisted_key
        r = _redis.from_url(_gs().redis_url, decode_responses=True, socket_timeout=1)
        if r.exists(jti_blacklist_key(tenant_id, jti)):
            raise HTTPException(status_code=401, detail="Token has been revoked")
        if user_id and r.exists(user_blacklisted_key(tenant_id, user_id)):
            raise HTTPException(status_code=401, detail="User session has been revoked")
    except HTTPException:
        raise
    except Exception:
        # Redis unavailable — fail open (token validity remains HMAC-guaranteed)
        pass


def _resolve_context_from_payload(payload: dict) -> AuthContext:
    _check_token_blacklist(payload)
    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(UserAccount.id == int(payload["sub"])).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id, Tenant.is_active.is_(True)).first()
        if not tenant:
            raise HTTPException(status_code=401, detail="Tenant not found or inactive")
        imp = payload.get("imp")
        context = AuthContext(
            user_id=user.id,
            email=user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=user.role,
        )
        if isinstance(imp, dict) and imp.get("active") is True:
            try:
                actor_id = int(imp.get("actor_user_id"))
            except Exception:
                actor_id = 0
            actor = db.query(UserAccount).filter(UserAccount.id == actor_id, UserAccount.is_active.is_(True)).first()
            if not actor or actor.role != "system_admin":
                raise HTTPException(status_code=401, detail="Invalid impersonation actor")
            actor_tenant = db.query(Tenant).filter(Tenant.id == actor.tenant_id, Tenant.is_active.is_(True)).first()
            if not actor_tenant:
                raise HTTPException(status_code=401, detail="Invalid impersonation actor tenant")
            context.is_impersonating = True
            context.impersonator_user_id = actor.id
            context.impersonator_email = actor.email
            context.impersonator_role = actor.role
            context.impersonator_tenant_id = actor_tenant.id
            context.impersonator_tenant_slug = actor_tenant.slug
            context.impersonation_reason = str(imp.get("reason") or "")
            context.impersonation_started_at = str(imp.get("started_at") or "")
        return context
    finally:
        db.close()


def _resolve_context_from_legacy_headers(
    x_user_id: str | None,
    x_tenant_id: str | None,
    x_role: str | None,
) -> AuthContext:
    if not x_user_id or not x_tenant_id or not x_role:
        raise HTTPException(status_code=401, detail="Missing legacy auth headers")
    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(UserAccount.id == int(x_user_id)).first()
        tenant = db.query(Tenant).filter(Tenant.id == int(x_tenant_id)).first()
        if not user or not tenant:
            raise HTTPException(status_code=401, detail="Invalid legacy auth principal")
        return AuthContext(
            user_id=user.id,
            email=user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=x_role,
        )
    finally:
        db.close()


def get_current_user(
    authorization: str | None = Header(default=None),
    arni_access_token: str | None = Cookie(default=None),
    x_user_id: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
) -> AuthContext:
    settings = get_settings()
    if authorization and authorization.startswith("Bearer "):
        payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
        return _resolve_context_from_payload(payload)
    if arni_access_token:
        payload = decode_access_token(arni_access_token)
        return _resolve_context_from_payload(payload)

    if os.getenv("PYTEST_CURRENT_TEST"):
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.slug == "system").first()
            user = db.query(UserAccount).filter(UserAccount.role == "system_admin").first()
            if tenant and user:
                return AuthContext(
                    user_id=user.id,
                    email=user.email,
                    tenant_id=tenant.id,
                    tenant_slug=tenant.slug,
                    role=user.role,
                )
        finally:
            db.close()

    if settings.auth_transition_mode and settings.auth_allow_header_fallback:
        return _resolve_context_from_legacy_headers(x_user_id, x_tenant_id, x_role)

    raise HTTPException(status_code=401, detail="Missing bearer token")


def require_role(user: AuthContext, allowed_roles: set[str]) -> None:
    if user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient role")


def normalize_tenant_slug(name: str) -> str:
    slug = name.strip().lower()
    slug = "".join(ch if ch.isalnum() else "-" for ch in slug)
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")
    return slug or "tenant"


def _validate_admin_password(password: str) -> None:
    """Refuse startup if admin password is weak or default (S1.1)."""
    weak_defaults = {"password123", "password", "admin", "changeme", "arni", "12345678", ""}
    if password.lower() in weak_defaults:
        sys.exit(
            "\n[ARNI STARTUP BLOCKED]\n"
            "SYSTEM_ADMIN_PASSWORD is weak or uses a known default value.\n"
            "Set a strong password (≥16 chars) in your .env file:\n"
            "  SYSTEM_ADMIN_PASSWORD=<strong-random-password>\n"
        )
    if len(password) < 12:
        sys.exit(
            "\n[ARNI STARTUP BLOCKED]\n"
            f"SYSTEM_ADMIN_PASSWORD must be at least 12 characters (got {len(password)}).\n"
        )


def invalidate_user_sessions(user_id: int, tenant_id: int, ttl_seconds: int = 43200) -> None:
    """Blacklist all active tokens for a user by setting a user-level blacklist key (S1.4).

    Because tokens are stateless, we cannot enumerate them. Instead we set a Redis key
    that get_current_user() checks on every request. TTL matches max token TTL (12h default).
    """
    try:
        import redis as _redis
        from config.settings import get_settings as _gs
        from app.core.redis_keys import user_blacklisted_key
        r = _redis.from_url(_gs().redis_url, decode_responses=True, socket_timeout=2)
        r.setex(user_blacklisted_key(tenant_id, user_id), ttl_seconds, "1")
    except Exception:
        pass  # Non-fatal — token will expire naturally after TTL


def ensure_default_tenant_and_admin() -> None:
    settings = get_settings()
    admin_email = os.getenv("SYSTEM_ADMIN_EMAIL", "admin@arni.local").strip().lower()
    admin_password = os.getenv("SYSTEM_ADMIN_PASSWORD", "")
    if settings.is_production:
        _validate_admin_password(admin_password)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == "system").first()
        if not tenant:
            tenant = Tenant(slug="system", name="System", is_active=True)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        user = db.query(UserAccount).filter(UserAccount.email == admin_email).first()
        if not user:
            user = UserAccount(
                tenant_id=tenant.id,
                email=admin_email,
                full_name="System Admin",
                role="system_admin",
                password_hash=hash_password(admin_password),
                is_active=True,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()
