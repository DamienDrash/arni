"""
ARIIA Auth Router – Refactored
==============================
Handles registration, login, logout, email verification, password reset,
profile management, user/tenant CRUD, impersonation, and audit logging.

Security features:
  - Rate-limiting on auth endpoints (in-memory token bucket)
  - Progressive account lockout after failed login attempts
  - Email verification with 6-digit code
  - Secure password reset with time-limited tokens
  - DSGVO consent tracking
  - Password complexity validation
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import hashlib
import math
import re
import secrets
import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import (
    AuthContext,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    hash_password,
    invalidate_user_sessions,
    normalize_tenant_slug,
    require_role,
    verify_password,
)
from app.core.db import SessionLocal
from app.core.models import AuditLog, Tenant, UserAccount
from app.gateway.persistence import persistence

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])
RESERVED_TENANT_SLUGS = {"system", "admin", "api"}
AUTH_COOKIE = "ariia_access_token"
CSRF_COOKIE = "ariia_csrf_token"
IMPERSONATION_TTL_SECONDS = 45 * 60

# ─── Rate Limiting (per-endpoint, in-memory) ────────────────────────────────

class _SlidingWindowCounter:
    """Simple sliding-window rate limiter."""
    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        window = self._windows[key]
        # Remove expired entries
        cutoff = now - window_seconds
        self._windows[key] = [t for t in window if t > cutoff]
        if len(self._windows[key]) >= max_requests:
            return False
        self._windows[key].append(now)
        return True

_rate_limiter = _SlidingWindowCounter()

def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _check_rate_limit(request: Request, endpoint: str, max_requests: int, window_seconds: int, extra_key: str = ""):
    import os
    if os.getenv("ENVIRONMENT") == "testing":
        return  # Skip rate limiting in test mode
    ip = _get_client_ip(request)
    key = f"{endpoint}:{ip}:{extra_key}"
    if not _rate_limiter.is_allowed(key, max_requests, window_seconds):
        logger.warning("auth.rate_limit_exceeded", endpoint=endpoint, ip=ip)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
        )

# ─── Account Lockout ────────────────────────────────────────────────────────

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATIONS = [15, 30, 60]  # minutes: progressive lockout

def _check_account_lockout(user: UserAccount) -> None:
    """Raise 423 if account is currently locked."""
    if user.locked_until:
        # SQLite returns naive datetimes even with timezone=True columns; normalise.
        lu = user.locked_until
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if lu <= now:
            return
        remaining = (lu - now).total_seconds()
        logger.warning("auth.account_locked", user_id=user.id, remaining_seconds=remaining)
        raise HTTPException(
            status_code=423,
            detail="Account temporarily locked due to too many failed login attempts. Please try again later.",
        )

def _record_failed_login(db, user: UserAccount) -> None:
    """Increment failed attempts and lock if threshold exceeded."""
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    user.last_failed_login_at = datetime.now(timezone.utc)

    if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
        # Progressive lockout: 15min → 30min → 60min
        lockout_index = min(
            (user.failed_login_attempts - LOCKOUT_THRESHOLD) // LOCKOUT_THRESHOLD,
            len(LOCKOUT_DURATIONS) - 1,
        )
        lockout_minutes = LOCKOUT_DURATIONS[lockout_index]
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
        logger.warning("auth.account_lockout_triggered", user_id=user.id, minutes=lockout_minutes)

    db.commit()

def _reset_failed_logins(db, user: UserAccount) -> None:
    """Reset lockout state on successful login."""
    if user.failed_login_attempts > 0 or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_failed_login_at = None
        db.commit()

# ─── Password Complexity ────────────────────────────────────────────────────

COMMON_PASSWORDS = {
    "password", "12345678", "123456789", "1234567890", "qwerty123",
    "password1", "iloveyou", "sunshine1", "princess1", "football1",
    "charlie1", "trustno1", "computer", "whatever", "dragon12",
    "master12", "monkey12", "shadow12", "michael1", "jennifer",
}

def validate_password_strength(password: str) -> str | None:
    """Validate password complexity. Returns error message or None if valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    if password.lower() in COMMON_PASSWORDS:
        return "This password is too common. Please choose a more secure password."
    return None

# ─── Verification Code Generation ───────────────────────────────────────────

def _generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return f"{secrets.randbelow(1000000):06d}"

def _hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()

# ─── Cookie Helpers ─────────────────────────────────────────────────────────

def _set_auth_cookies(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=secrets.token_urlsafe(24),
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
    )

# ─── Request/Response Models ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=120)
    tenant_slug: str | None = None
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)
    accept_tos: bool = False
    accept_privacy: bool = False

class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str

class VerifyEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=6)

class ResendVerificationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

class ResetPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=200)

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)
    role: str = "tenant_user"
    tenant_id: int | None = None

class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    role: str | None = None
    is_active: bool | None = None
    tenant_id: int | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)

class UpdateTenantRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = None
    is_active: bool | None = None

class StartImpersonationRequest(BaseModel):
    reason: str = Field(min_length=8, max_length=500)

class ProfileSettingsUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    locale: str | None = None
    timezone: str | None = None
    notify_email: str | None = None
    notify_telegram: str | None = None
    compact_mode: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=200)

# ─── Helpers ────────────────────────────────────────────────────────────────

def _normalize_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise HTTPException(status_code=422, detail="Invalid email format")
    return normalized

def _user_pref_key(user_id: int, name: str) -> str:
    return f"user:{user_id}:pref:{name}"

def _audit_table_has_column(db, column: str) -> bool:
    try:
        bind = db.get_bind()
        columns = inspect(bind).get_columns("audit_logs")
        return any(c.get("name") == column for c in columns)
    except Exception:
        try:
            bind = db.get_bind()
            if getattr(bind, "dialect", None) and bind.dialect.name != "sqlite":
                return False
            rows = db.execute(text("PRAGMA table_info(audit_logs)")).fetchall()
            return any(row[1] == column for row in rows)
        except Exception:
            return False

def _safe_iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)

def _write_audit(
    *,
    actor: AuthContext | None,
    action: str,
    category: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            AuditLog(
                actor_user_id=actor.user_id if actor else None,
                actor_email=actor.email if actor else None,
                tenant_id=actor.tenant_id if actor else None,
                action=action,
                category=category,
                target_type=target_type,
                target_id=target_id,
                details_json=str(details or {}),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()


def _send_verification_email(user: UserAccount, code: str) -> None:
    """Send verification email in background (non-blocking)."""
    try:
        from app.core.auth_email import render_verification_email, send_auth_email
        from config.settings import Settings
        settings = Settings()
        base_url = settings.gateway_public_url or "https://www.ariia.ai"
        verify_url = f"{base_url.rstrip('/')}/verify-email?email={user.email}&code={code}"
        subject, html, plaintext = render_verification_email(user.full_name, code, verify_url)
        send_auth_email(user.email, subject, html, plaintext)
    except Exception as e:
        logger.error("auth.verification_email_failed", user_id=user.id, error=str(e))


def _send_password_reset_email(user: UserAccount, code: str) -> None:
    """Send password reset email."""
    try:
        from app.core.auth_email import render_password_reset_email, send_auth_email
        from config.settings import Settings
        settings = Settings()
        base_url = settings.gateway_public_url or "https://www.ariia.ai"
        reset_url = f"{base_url.rstrip('/')}/reset-password?email={user.email}&code={code}"
        subject, html, plaintext = render_password_reset_email(user.full_name, code, reset_url)
        send_auth_email(user.email, subject, html, plaintext)
    except Exception as e:
        logger.error("auth.password_reset_email_failed", user_id=user.id, error=str(e))


def _send_welcome_email(user: UserAccount, tenant: Tenant) -> None:
    """Send welcome email after verification."""
    try:
        from app.core.auth_email import render_welcome_email, send_auth_email
        from config.settings import Settings
        settings = Settings()
        base_url = settings.gateway_public_url or "https://www.ariia.ai"
        login_url = f"{base_url.rstrip('/')}/dashboard"
        subject, html, plaintext = render_welcome_email(user.full_name, tenant.name, login_url)
        send_auth_email(user.email, subject, html, plaintext)
    except Exception as e:
        logger.error("auth.welcome_email_failed", user_id=user.id, error=str(e))


def _send_password_changed_email(user: UserAccount) -> None:
    """Send password changed notification."""
    try:
        from app.core.auth_email import render_password_changed_email, send_auth_email
        subject, html, plaintext = render_password_changed_email(user.full_name)
        send_auth_email(user.email, subject, html, plaintext)
    except Exception as e:
        logger.error("auth.password_changed_email_failed", user_id=user.id, error=str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/register")
async def register(req: RegisterRequest, request: Request, response: Response) -> dict:
    # Rate limit: 3 registrations per IP per hour
    _check_rate_limit(request, "register", max_requests=3, window_seconds=3600)

    # Password complexity check
    pw_error = validate_password_strength(req.password)
    if pw_error:
        raise HTTPException(status_code=422, detail=pw_error)

    # DSGVO consent check
    if not req.accept_tos or not req.accept_privacy:
        raise HTTPException(
            status_code=422,
            detail="You must accept the Terms of Service and Privacy Policy to register.",
        )

    db = SessionLocal()
    try:
        slug_base = normalize_tenant_slug(req.tenant_slug or req.tenant_name)
        if slug_base in RESERVED_TENANT_SLUGS:
            raise HTTPException(status_code=422, detail="Tenant slug is reserved")
        slug = slug_base
        i = 1
        while db.query(Tenant).filter(Tenant.slug == slug).first():
            i += 1
            slug = f"{slug_base}-{i}"

        email = _normalize_email(req.email)
        if db.query(UserAccount).filter(UserAccount.email == email).first():
            raise HTTPException(status_code=409, detail="Email already registered")

        now = datetime.now(timezone.utc)
        tenant = Tenant(
            name=req.tenant_name.strip(),
            slug=slug,
            is_active=True,
            tos_accepted_at=now,
            privacy_accepted_at=now,
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        # Generate email verification code
        verification_code = _generate_verification_code()

        user = UserAccount(
            tenant_id=tenant.id,
            email=email,
            full_name=req.full_name,
            role="tenant_admin",
            password_hash=hash_password(req.password),
            is_active=True,
            email_verified=False,
            email_verification_token=_hash_token(verification_code),
            email_verification_sent_at=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Seed Trial subscription
        try:
            from app.core.models import Plan, Subscription as Sub
            trial_plan = db.query(Plan).filter(Plan.slug == "trial", Plan.is_active.is_(True)).first()
            if trial_plan:
                trial_end = now + timedelta(days=14)
                db.add(Sub(
                    tenant_id=tenant.id,
                    plan_id=trial_plan.id,
                    status="trialing",
                    trial_ends_at=trial_end,
                    current_period_start=now,
                    current_period_end=trial_end,
                ))
                db.commit()
                logger.info("tenant.register.trial_started", tenant_id=tenant.id, trial_ends_at=trial_end.isoformat())
            else:
                starter = db.query(Plan).filter(Plan.slug == "starter", Plan.is_active.is_(True)).first()
                if starter:
                    db.add(Sub(tenant_id=tenant.id, plan_id=starter.id, status="active"))
                    db.commit()
        except Exception as _sub_err:
            logger.warning("tenant.register.subscription_seed_failed", tenant_id=tenant.id, error=str(_sub_err))

        # Seed prompt settings
        try:
            from app.core.prompt_builder import seed_prompt_settings
            from app.gateway.persistence import persistence as _ps
            seed_prompt_settings(_ps, tenant.id)
            _ps.upsert_setting("tenant_display_name", tenant.name, tenant_id=tenant.id)
        except Exception as _ps_err:
            logger.warning("tenant.register.prompt_seed_failed", tenant_id=tenant.id, error=str(_ps_err))

        # Send verification email
        _send_verification_email(user, verification_code)

        # Create token (limited access until verified)
        token = create_access_token(
            user_id=user.id,
            email=user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=user.role,
        )
        _set_auth_cookies(response, token)

        logger.info("auth.register.success", user_id=user.id, tenant_id=tenant.id, email_verified=False)

        return {
            "access_token": token,
            "token_type": "bearer",
            "email_verification_required": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": tenant.id,
                "tenant_slug": tenant.slug,
                "email_verified": False,
            },
        }
    finally:
        db.close()


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, request: Request) -> dict:
    """Verify email address with 6-digit code."""
    _check_rate_limit(request, "verify-email", max_requests=5, window_seconds=900)

    db = SessionLocal()
    try:
        email = _normalize_email(req.email)
        user = db.query(UserAccount).filter(UserAccount.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.email_verified:
            return {"verified": True, "message": "Email already verified"}

        # Check token expiry (30 minutes)
        if user.email_verification_sent_at:
            sent_at = user.email_verification_sent_at
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - sent_at).total_seconds()
            if elapsed > 1800:
                raise HTTPException(status_code=410, detail="Verification code expired. Please request a new one.")

        # Verify code
        code_hash = _hash_token(req.code)
        if not user.email_verification_token or user.email_verification_token != code_hash:
            raise HTTPException(status_code=401, detail="Invalid verification code")

        # Mark as verified
        now = datetime.now(timezone.utc)
        user.email_verified = True
        user.email_verified_at = now
        user.email_verification_token = None
        user.email_verification_sent_at = None
        db.commit()

        # Send welcome email
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if tenant:
            _send_welcome_email(user, tenant)

        logger.info("auth.email_verified", user_id=user.id)
        return {"verified": True, "message": "Email successfully verified"}
    finally:
        db.close()


@router.post("/resend-verification")
async def resend_verification(req: ResendVerificationRequest, request: Request) -> dict:
    """Resend email verification code (max 3 per hour)."""
    _check_rate_limit(request, "resend-verification", max_requests=3, window_seconds=3600)

    db = SessionLocal()
    try:
        email = _normalize_email(req.email)
        user = db.query(UserAccount).filter(UserAccount.email == email).first()

        # Always return success to prevent email enumeration
        if not user or user.email_verified:
            return {"message": "If the email exists and is not yet verified, a new code has been sent."}

        # Generate new code
        code = _generate_verification_code()
        user.email_verification_token = _hash_token(code)
        user.email_verification_sent_at = datetime.now(timezone.utc)
        db.commit()

        _send_verification_email(user, code)

        return {"message": "If the email exists and is not yet verified, a new code has been sent."}
    finally:
        db.close()


@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response) -> dict:
    # Rate limit: 10 login attempts per IP per 15 minutes
    _check_rate_limit(request, "login", max_requests=10, window_seconds=900)

    db = SessionLocal()
    try:
        email = _normalize_email(req.email)
        user = db.query(UserAccount).filter(UserAccount.email == email).first()

        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Check account lockout
        _check_account_lockout(user)

        # Verify password
        if not user.password_hash or not verify_password(req.password, user.password_hash):
            _record_failed_login(db, user)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant or not tenant.is_active:
            raise HTTPException(status_code=401, detail="Tenant inactive")

        # Reset failed login counter
        _reset_failed_logins(db, user)

        # Update last_login_at
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()

        # Check if MFA is required
        if user.mfa_enabled:
            # Create a short-lived MFA challenge token (5 min TTL)
            mfa_challenge = secrets.token_urlsafe(48)
            mfa_challenge_hash = _hash_token(mfa_challenge)
            # Store hash in email_verification_token temporarily (repurposed for MFA challenge)
            user.email_verification_token = f"mfa:{mfa_challenge_hash}"
            user.email_verification_sent_at = datetime.now(timezone.utc)
            db.commit()
            return {
                "mfa_required": True,
                "mfa_challenge_token": mfa_challenge,
                "user_id": user.id,
            }

        token = create_access_token(
            user_id=user.id,
            email=user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=user.role,
        )
        _set_auth_cookies(response, token)

        # Create refresh token
        refresh_token, _family = create_refresh_token(
            user_id=user.id,
            tenant_id=tenant.id,
        )
        response.set_cookie(
            key="ariia_refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/proxy/auth/refresh",
            max_age=30 * 24 * 3600,  # 30 days
        )

        logger.info("auth.login.success", user_id=user.id, tenant_id=tenant.id)

        return {
            "access_token": token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": tenant.id,
                "tenant_slug": tenant.slug,
                "email_verified": bool(user.email_verified),
                "mfa_enabled": bool(user.mfa_enabled),
            },
        }
    finally:
        db.close()


@router.post("/refresh")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    req: RefreshTokenRequest | None = None,
) -> dict:
    """Rotate refresh token and issue new access + refresh token pair.
    
    Accepts refresh token from:
    1. Request body (JSON)
    2. HttpOnly cookie (ariia_refresh_token)
    """
    _check_rate_limit(request, "refresh", max_requests=30, window_seconds=900)

    # Get refresh token from body or cookie
    rt = None
    if req and req.refresh_token:
        rt = req.refresh_token
    else:
        rt = request.cookies.get("ariia_refresh_token")

    if not rt:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    # Decode and verify
    payload = decode_refresh_token(rt)
    user_id = int(payload["sub"])
    tenant_id = int(payload["tenant_id"])

    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(UserAccount.id == user_id, UserAccount.is_active.is_(True)).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active.is_(True)).first()
        if not tenant:
            raise HTTPException(status_code=401, detail="Tenant not found or inactive")

        # Issue new access token
        new_access = create_access_token(
            user_id=user.id,
            email=user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=user.role,
        )
        _set_auth_cookies(response, new_access)

        # Rotate refresh token
        new_refresh, _family = create_refresh_token(
            user_id=user.id,
            tenant_id=tenant.id,
        )
        response.set_cookie(
            key="ariia_refresh_token",
            value=new_refresh,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/proxy/auth/refresh",
            max_age=30 * 24 * 3600,
        )

        logger.info("auth.token_refreshed", user_id=user.id)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": tenant.id,
                "tenant_slug": tenant.slug,
                "email_verified": bool(user.email_verified),
                "mfa_enabled": bool(user.mfa_enabled),
            },
        }
    finally:
        db.close()


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, request: Request) -> dict:
    """Send password reset email. Always returns 200 to prevent email enumeration."""
    _check_rate_limit(request, "forgot-password", max_requests=3, window_seconds=3600)

    db = SessionLocal()
    try:
        email = _normalize_email(req.email)
        user = db.query(UserAccount).filter(UserAccount.email == email).first()

        if user and user.is_active:
            code = _generate_verification_code()
            user.password_reset_token = _hash_token(code)
            user.password_reset_sent_at = datetime.now(timezone.utc)
            db.commit()
            _send_password_reset_email(user, code)
            logger.info("auth.forgot_password.sent", user_id=user.id)

        # Always return same response
        return {"message": "If the email is registered, a password reset code has been sent."}
    finally:
        db.close()


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, request: Request) -> dict:
    """Reset password with code from email."""
    _check_rate_limit(request, "reset-password", max_requests=5, window_seconds=900)

    # Password complexity check
    pw_error = validate_password_strength(req.new_password)
    if pw_error:
        raise HTTPException(status_code=422, detail=pw_error)

    db = SessionLocal()
    try:
        email = _normalize_email(req.email)
        user = db.query(UserAccount).filter(UserAccount.email == email).first()

        if not user or not user.is_active:
            raise HTTPException(status_code=400, detail="Invalid reset request")

        # Check token exists and not expired (1 hour)
        if not user.password_reset_token or not user.password_reset_sent_at:
            raise HTTPException(status_code=400, detail="No password reset requested")

        _reset_sent = user.password_reset_sent_at
        if _reset_sent.tzinfo is None:
            _reset_sent = _reset_sent.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - _reset_sent).total_seconds()
        if elapsed > 3600:
            raise HTTPException(status_code=410, detail="Reset code expired. Please request a new one.")

        # Verify code
        code_hash = _hash_token(req.code)
        if user.password_reset_token != code_hash:
            raise HTTPException(status_code=401, detail="Invalid reset code")

        # Update password
        now = datetime.now(timezone.utc)
        user.password_hash = hash_password(req.new_password)
        user.password_changed_at = now
        user.password_reset_token = None
        user.password_reset_sent_at = None
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

        # Invalidate all sessions
        try:
            invalidate_user_sessions(user.id)
        except Exception:
            pass

        # Send notification
        _send_password_changed_email(user)

        logger.info("auth.password_reset.success", user_id=user.id)
        return {"message": "Password successfully reset. Please log in with your new password."}
    finally:
        db.close()


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, request: Request, user: AuthContext = Depends(get_current_user)) -> dict:
    """Change password for authenticated user."""
    _check_rate_limit(request, "change-password", max_requests=5, window_seconds=900)

    pw_error = validate_password_strength(req.new_password)
    if pw_error:
        raise HTTPException(status_code=422, detail=pw_error)

    db = SessionLocal()
    try:
        db_user = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify current password
        if not db_user.password_hash or not verify_password(req.current_password, db_user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        # Update password
        db_user.password_hash = hash_password(req.new_password)
        db_user.password_changed_at = datetime.now(timezone.utc)
        db.commit()

        # Send notification
        _send_password_changed_email(db_user)

        logger.info("auth.password_changed", user_id=user.user_id)
        return {"message": "Password successfully changed."}
    finally:
        db.close()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie(AUTH_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.delete_cookie("ariia_refresh_token", path="/proxy/auth/refresh")
    response.delete_cookie("ariia_refresh_token", path="/")  # Fallback path
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me")
async def me(user: AuthContext = Depends(get_current_user)) -> dict:
    db = SessionLocal()
    try:
        db_user = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        result = {
            "id": user.user_id,
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "tenant_slug": user.tenant_slug,
            "full_name": db_user.full_name if db_user else None,
            "language": db_user.language if db_user else "en",
            "email_verified": bool(db_user.email_verified) if db_user else False,
            "mfa_enabled": bool(db_user.mfa_enabled) if db_user else False,
        }
        if db_user:
            result["created_at"] = _safe_iso(db_user.created_at)
            result["last_login_at"] = _safe_iso(getattr(db_user, "last_login_at", None))
        if tenant:
            result["tenant_name"] = tenant.name
        if getattr(user, "impersonator_user_id", None):
            result["impersonating"] = True
            result["impersonator_user_id"] = user.impersonator_user_id
        return result
    finally:
        db.close()


@router.get("/profile-settings")
async def get_profile_settings(user: AuthContext = Depends(get_current_user)) -> dict:
    db = SessionLocal()
    try:
        db_user = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "full_name": db_user.full_name or "",
            "email": db_user.email,
            "locale": persistence.get_setting(_user_pref_key(user.user_id, "locale"), "en", tenant_id=user.tenant_id),
            "timezone": persistence.get_setting(_user_pref_key(user.user_id, "timezone"), "Europe/Berlin", tenant_id=user.tenant_id),
            "notify_email": persistence.get_setting(_user_pref_key(user.user_id, "notify_email"), "true", tenant_id=user.tenant_id),
            "notify_telegram": persistence.get_setting(_user_pref_key(user.user_id, "notify_telegram"), "false", tenant_id=user.tenant_id),
            "compact_mode": persistence.get_setting(_user_pref_key(user.user_id, "compact_mode"), "false", tenant_id=user.tenant_id),
            "email_verified": bool(db_user.email_verified),
            "mfa_enabled": bool(db_user.mfa_enabled),
        }
    finally:
        db.close()


@router.put("/profile-settings")
async def update_profile_settings(req: ProfileSettingsUpdate, user: AuthContext = Depends(get_current_user)) -> dict:
    db = SessionLocal()
    try:
        db_user = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        if req.full_name is not None:
            db_user.full_name = req.full_name.strip()
            db.commit()
        if req.locale is not None:
            persistence.upsert_setting(_user_pref_key(user.user_id, "locale"), req.locale, tenant_id=user.tenant_id)
        if req.timezone is not None:
            persistence.upsert_setting(_user_pref_key(user.user_id, "timezone"), req.timezone, tenant_id=user.tenant_id)
        if req.notify_email is not None:
            persistence.upsert_setting(_user_pref_key(user.user_id, "notify_email"), req.notify_email, tenant_id=user.tenant_id)
        if req.notify_telegram is not None:
            persistence.upsert_setting(_user_pref_key(user.user_id, "notify_telegram"), req.notify_telegram, tenant_id=user.tenant_id)
        if req.compact_mode is not None:
            persistence.upsert_setting(_user_pref_key(user.user_id, "compact_mode"), req.compact_mode, tenant_id=user.tenant_id)
        # Password change via profile settings
        if req.new_password:
            if not req.current_password:
                raise HTTPException(status_code=422, detail="Current password required to set new password")
            if not verify_password(req.current_password, db_user.password_hash):
                raise HTTPException(status_code=401, detail="Current password is incorrect")
            pw_error = validate_password_strength(req.new_password)
            if pw_error:
                raise HTTPException(status_code=422, detail=pw_error)
            db_user.password_hash = hash_password(req.new_password)
            db_user.password_changed_at = datetime.now(timezone.utc)
            db.commit()
            _send_password_changed_email(db_user)
        return {"ok": True}
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/users")
async def list_users(user: AuthContext = Depends(get_current_user)) -> list[dict]:
    db = SessionLocal()
    try:
        if user.role == "system_admin":
            users = db.query(UserAccount).all()
        else:
            users = db.query(UserAccount).filter(UserAccount.tenant_id == user.tenant_id).all()
        result = []
        for u in users:
            result.append({
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "tenant_id": u.tenant_id,
                "language": u.language,
                "created_at": _safe_iso(u.created_at),
                "email_verified": bool(u.email_verified),
                "mfa_enabled": bool(u.mfa_enabled),
                "last_login_at": _safe_iso(getattr(u, "last_login_at", None)),
            })
        return result
    finally:
        db.close()


@router.post("/users")
async def create_user(req: CreateUserRequest, user: AuthContext = Depends(get_current_user)) -> dict:
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Admin role required")

    pw_error = validate_password_strength(req.password)
    if pw_error:
        raise HTTPException(status_code=422, detail=pw_error)

    db = SessionLocal()
    try:
        email = _normalize_email(req.email)
        if db.query(UserAccount).filter(UserAccount.email == email).first():
            raise HTTPException(status_code=409, detail="Email already registered")

        target_tenant_id = req.tenant_id if (user.role == "system_admin" and req.tenant_id) else user.tenant_id
        allowed_roles = {"tenant_admin", "tenant_user"}
        if user.role == "system_admin":
            allowed_roles.add("system_admin")
        role = req.role if req.role in allowed_roles else "tenant_user"

        new_user = UserAccount(
            tenant_id=target_tenant_id,
            email=email,
            full_name=req.full_name,
            role=role,
            password_hash=hash_password(req.password),
            is_active=True,
            email_verified=True,  # Admin-created users are pre-verified
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        _write_audit(
            actor=user,
            action="user.created",
            category="auth",
            target_type="user",
            target_id=str(new_user.id),
            details={"email": email, "role": role, "tenant_id": target_tenant_id},
        )

        return {
            "id": new_user.id,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role,
            "is_active": new_user.is_active,
            "tenant_id": new_user.tenant_id,
        }
    finally:
        db.close()


@router.put("/users/{user_id}")
async def update_user(user_id: int, req: UpdateUserRequest, user: AuthContext = Depends(get_current_user)) -> dict:
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Admin role required")
    db = SessionLocal()
    try:
        target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if user.role == "tenant_admin" and target.tenant_id != user.tenant_id:
            raise HTTPException(status_code=403, detail="Not allowed to modify users in other tenants")
        changes = {}
        if req.full_name is not None:
            target.full_name = req.full_name.strip()
            changes["full_name"] = target.full_name
        if req.role is not None:
            allowed = {"tenant_admin", "tenant_user"}
            if user.role == "system_admin":
                allowed.add("system_admin")
            if req.role in allowed:
                target.role = req.role
                changes["role"] = req.role
        if req.is_active is not None:
            target.is_active = req.is_active
            changes["is_active"] = req.is_active
            if not req.is_active:
                try:
                    invalidate_user_sessions(target.id)
                except Exception:
                    pass
        if req.tenant_id is not None and user.role == "system_admin":
            target.tenant_id = req.tenant_id
            changes["tenant_id"] = req.tenant_id
        if req.password:
            pw_error = validate_password_strength(req.password)
            if pw_error:
                raise HTTPException(status_code=422, detail=pw_error)
            target.password_hash = hash_password(req.password)
            target.password_changed_at = datetime.now(timezone.utc)
            changes["password"] = "changed"
        db.commit()
        _write_audit(
            actor=user,
            action="user.updated",
            category="auth",
            target_type="user",
            target_id=str(user_id),
            details=changes,
        )
        return {
            "id": target.id,
            "email": target.email,
            "full_name": target.full_name,
            "role": target.role,
            "is_active": target.is_active,
            "tenant_id": target.tenant_id,
            "email_verified": bool(target.email_verified),
        }
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  TENANT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/tenants")
async def list_tenants(user: AuthContext = Depends(get_current_user)) -> list[dict]:
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin required")
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        return [{"id": t.id, "slug": t.slug, "name": t.name, "is_active": t.is_active, "created_at": _safe_iso(t.created_at)} for t in tenants]
    finally:
        db.close()


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = None

@router.post("/tenants")
async def create_tenant(req: CreateTenantRequest, user: AuthContext = Depends(get_current_user)) -> dict:
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin required")
    db = SessionLocal()
    try:
        slug_base = normalize_tenant_slug(req.slug or req.name)
        if slug_base in RESERVED_TENANT_SLUGS:
            raise HTTPException(status_code=422, detail="Tenant slug is reserved")
        slug = slug_base
        i = 1
        while db.query(Tenant).filter(Tenant.slug == slug).first():
            i += 1
            slug = f"{slug_base}-{i}"
        tenant = Tenant(name=req.name.strip(), slug=slug, is_active=True)
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        _write_audit(
            actor=user,
            action="tenant.created",
            category="auth",
            target_type="tenant",
            target_id=str(tenant.id),
            details={"name": tenant.name, "slug": tenant.slug},
        )
        return {"id": tenant.id, "slug": tenant.slug, "name": tenant.name, "is_active": tenant.is_active}
    finally:
        db.close()


@router.put("/tenants/{tenant_id}")
async def update_tenant(tenant_id: int, req: UpdateTenantRequest, user: AuthContext = Depends(get_current_user)) -> dict:
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin required")
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        changes = {}
        if req.name is not None:
            tenant.name = req.name.strip()
            changes["name"] = tenant.name
        if req.slug is not None:
            new_slug = normalize_tenant_slug(req.slug)
            if new_slug in RESERVED_TENANT_SLUGS:
                raise HTTPException(status_code=422, detail="Slug reserved")
            existing = db.query(Tenant).filter(Tenant.slug == new_slug, Tenant.id != tenant_id).first()
            if existing:
                raise HTTPException(status_code=409, detail="Slug already in use")
            tenant.slug = new_slug
            changes["slug"] = new_slug
        if req.is_active is not None:
            tenant.is_active = req.is_active
            changes["is_active"] = req.is_active
        db.commit()
        _write_audit(
            actor=user,
            action="tenant.updated",
            category="auth",
            target_type="tenant",
            target_id=str(tenant_id),
            details=changes,
        )
        return {"id": tenant.id, "slug": tenant.slug, "name": tenant.name, "is_active": tenant.is_active}
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  TEAM INVITATIONS
# ═══════════════════════════════════════════════════════════════════════════

class InviteTeamMemberRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: str = "tenant_user"


@router.post("/invitations")
async def invite_team_member(
    req: InviteTeamMemberRequest,
    request: Request,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Invite a new team member via email."""
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Admin role required to invite team members")

    _check_rate_limit(request, "invite", max_requests=20, window_seconds=3600)

    from app.core.models import PendingInvitation

    db = SessionLocal()
    try:
        email = _normalize_email(req.email)

        # Check if user already exists in this tenant
        existing_user = db.query(UserAccount).filter(
            UserAccount.email == email,
            UserAccount.tenant_id == user.tenant_id,
        ).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="User with this email already exists in your organization")

        # Check for pending invitation
        pending = db.query(PendingInvitation).filter(
            PendingInvitation.email == email,
            PendingInvitation.tenant_id == user.tenant_id,
            PendingInvitation.accepted_at.is_(None),
            PendingInvitation.expires_at > datetime.now(timezone.utc),
        ).first()
        if pending:
            raise HTTPException(status_code=409, detail="An invitation for this email is already pending")

        # Validate role
        allowed_roles = {"tenant_admin", "tenant_user"}
        role = req.role if req.role in allowed_roles else "tenant_user"

        # Create invitation
        token = secrets.token_urlsafe(48)
        invitation = PendingInvitation(
            tenant_id=user.tenant_id,
            email=email,
            role=role,
            token=_hash_token(token),
            invited_by=user.user_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(invitation)
        db.commit()
        db.refresh(invitation)

        # Send invitation email
        try:
            from app.core.auth_email import render_team_invitation_email, send_auth_email
            from config.settings import Settings
            settings = Settings()
            base_url = settings.gateway_public_url or "https://www.ariia.ai"
            invite_url = f"{base_url.rstrip('/')}/accept-invitation?token={token}"

            inviter_name = user.email
            db_user = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
            if db_user and db_user.full_name:
                inviter_name = db_user.full_name

            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            tenant_name = tenant.name if tenant else "your organization"

            subject, html, plaintext = render_team_invitation_email(
                inviter_name=inviter_name,
                tenant_name=tenant_name,
                role=role,
                invite_url=invite_url,
            )
            send_auth_email(email, subject, html, plaintext)
        except Exception as e:
            logger.error("auth.invitation_email_failed", email=email, error=str(e))

        _write_audit(
            actor=user,
            action="invitation.sent",
            category="auth",
            target_type="invitation",
            target_id=str(invitation.id),
            details={"email": email, "role": role},
        )

        logger.info("auth.invitation.sent", email=email, tenant_id=user.tenant_id)
        return {
            "id": invitation.id,
            "email": email,
            "role": role,
            "expires_at": _safe_iso(invitation.expires_at),
            "message": "Invitation sent successfully",
        }
    finally:
        db.close()


@router.get("/invitations")
async def list_invitations(user: AuthContext = Depends(get_current_user)) -> list[dict]:
    """List pending invitations for the current tenant."""
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Admin role required")

    from app.core.models import PendingInvitation

    db = SessionLocal()
    try:
        invitations = db.query(PendingInvitation).filter(
            PendingInvitation.tenant_id == user.tenant_id,
        ).order_by(PendingInvitation.created_at.desc()).all()

        result = []
        for inv in invitations:
            inviter = db.query(UserAccount).filter(UserAccount.id == inv.invited_by).first() if inv.invited_by else None
            result.append({
                "id": inv.id,
                "email": inv.email,
                "role": inv.role,
                "invited_by": inviter.email if inviter else None,
                "invited_by_name": inviter.full_name if inviter else None,
                "expires_at": _safe_iso(inv.expires_at),
                "accepted_at": _safe_iso(inv.accepted_at),
                "created_at": _safe_iso(inv.created_at),
                "status": "accepted" if inv.accepted_at else (
                    "expired" if (inv.expires_at.replace(tzinfo=timezone.utc) if inv.expires_at and inv.expires_at.tzinfo is None else inv.expires_at or datetime.now(timezone.utc)) < datetime.now(timezone.utc) else "pending"
                ),
            })
        return result
    finally:
        db.close()


@router.delete("/invitations/{invitation_id}")
async def revoke_invitation(
    invitation_id: int,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Revoke a pending invitation."""
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Admin role required")

    from app.core.models import PendingInvitation

    db = SessionLocal()
    try:
        invitation = db.query(PendingInvitation).filter(
            PendingInvitation.id == invitation_id,
            PendingInvitation.tenant_id == user.tenant_id,
        ).first()
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")
        if invitation.accepted_at:
            raise HTTPException(status_code=400, detail="Cannot revoke an accepted invitation")

        db.delete(invitation)
        db.commit()

        _write_audit(
            actor=user,
            action="invitation.revoked",
            category="auth",
            target_type="invitation",
            target_id=str(invitation_id),
            details={"email": invitation.email},
        )

        return {"message": "Invitation revoked"}
    finally:
        db.close()


@router.post("/accept-invitation")
async def accept_invitation(
    request: Request,
    response: Response,
) -> dict:
    """Accept a team invitation and create user account."""
    _check_rate_limit(request, "accept-invitation", max_requests=5, window_seconds=900)

    body = await request.json()
    token = body.get("token", "").strip()
    password = body.get("password", "")
    full_name = body.get("full_name", "").strip()

    if not token:
        raise HTTPException(status_code=422, detail="Invitation token is required")
    if not password:
        raise HTTPException(status_code=422, detail="Password is required")

    pw_error = validate_password_strength(password)
    if pw_error:
        raise HTTPException(status_code=422, detail=pw_error)

    from app.core.models import PendingInvitation

    db = SessionLocal()
    try:
        token_hash = _hash_token(token)
        invitation = db.query(PendingInvitation).filter(
            PendingInvitation.token == token_hash,
            PendingInvitation.accepted_at.is_(None),
        ).first()

        if not invitation:
            raise HTTPException(status_code=404, detail="Invalid or expired invitation")

        _exp = invitation.expires_at
        if _exp is not None and _exp.tzinfo is None:
            _exp = _exp.replace(tzinfo=timezone.utc)
        if _exp and _exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="This invitation has expired")

        # Check if email already registered
        if db.query(UserAccount).filter(UserAccount.email == invitation.email).first():
            raise HTTPException(status_code=409, detail="An account with this email already exists")

        tenant = db.query(Tenant).filter(Tenant.id == invitation.tenant_id, Tenant.is_active.is_(True)).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Organization not found or inactive")

        # Create user
        now = datetime.now(timezone.utc)
        new_user = UserAccount(
            tenant_id=tenant.id,
            email=invitation.email,
            full_name=full_name or None,
            role=invitation.role,
            password_hash=hash_password(password),
            is_active=True,
            email_verified=True,  # Invitation-based users are pre-verified
        )
        db.add(new_user)

        # Mark invitation as accepted
        invitation.accepted_at = now
        db.commit()
        db.refresh(new_user)

        # Create access token
        access_token = create_access_token(
            user_id=new_user.id,
            email=new_user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=new_user.role,
        )
        _set_auth_cookies(response, access_token)

        # Create refresh token
        refresh_tok, _ = create_refresh_token(
            user_id=new_user.id,
            tenant_id=tenant.id,
        )
        response.set_cookie(
            key="ariia_refresh_token",
            value=refresh_tok,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/proxy/auth/refresh",
            max_age=30 * 24 * 3600,
        )

        # Send welcome email
        try:
            from app.core.auth_email import render_welcome_email, send_auth_email
            from config.settings import Settings
            settings = Settings()
            base_url = settings.gateway_public_url or "https://www.ariia.ai"
            login_url = f"{base_url.rstrip('/')}/dashboard"
            subject, html, plaintext = render_welcome_email(new_user.full_name, tenant.name, login_url)
            send_auth_email(new_user.email, subject, html, plaintext)
        except Exception as e:
            logger.error("auth.welcome_email_failed", user_id=new_user.id, error=str(e))

        _write_audit(
            actor=None,
            action="invitation.accepted",
            category="auth",
            target_type="user",
            target_id=str(new_user.id),
            details={"email": invitation.email, "tenant_id": tenant.id, "role": invitation.role},
        )

        logger.info("auth.invitation.accepted", user_id=new_user.id, tenant_id=tenant.id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_tok,
            "token_type": "bearer",
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "role": new_user.role,
                "tenant_id": tenant.id,
                "tenant_slug": tenant.slug,
                "email_verified": True,
            },
        }
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  AUDIT LOGS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/audit")
async def list_audit_logs(limit: int = 200, user: AuthContext = Depends(get_current_user)) -> list[dict]:
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin required")
    db = SessionLocal()
    try:
        logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
        result = []
        for log in logs:
            entry = {
                "id": log.id,
                "action": log.action,
                "category": log.category,
                "actor_email": log.actor_email,
                "actor_user_id": log.actor_user_id,
                "tenant_id": log.tenant_id,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details_json,
                "created_at": _safe_iso(log.created_at),
            }
            result.append(entry)
        return result
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  IMPERSONATION
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/users/{user_id}/impersonate")
async def start_impersonation(
    user_id: int,
    req: StartImpersonationRequest,
    response: Response,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin required")
    if user.user_id == user_id:
        raise HTTPException(status_code=422, detail="Cannot impersonate yourself")
    db = SessionLocal()
    try:
        target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
        if not target or not target.is_active:
            raise HTTPException(status_code=404, detail="Target user not found or inactive")
        tenant = db.query(Tenant).filter(Tenant.id == target.tenant_id).first()
        if not tenant or not tenant.is_active:
            raise HTTPException(status_code=404, detail="Target tenant not found or inactive")
        token = create_access_token(
            user_id=target.id,
            email=target.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=target.role,
            extra_claims={
                "imp": True,
                "imp_by": user.user_id,
                "imp_email": user.email,
                "imp_reason": req.reason,
            },
            ttl_override_seconds=IMPERSONATION_TTL_SECONDS,
        )
        _set_auth_cookies(response, token)
        _write_audit(
            actor=user,
            action="impersonation.started",
            category="auth",
            target_type="user",
            target_id=str(user_id),
            details={
                "reason": req.reason,
                "impersonator_email": user.email,
                "target_email": target.email,
                "target_tenant": tenant.slug,
            },
        )
        logger.info(
            "impersonation.started",
            impersonator=user.email,
            target_user=target.email,
            target_tenant=tenant.slug,
            reason=req.reason,
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "impersonating": True,
            "user": {
                "id": target.id,
                "email": target.email,
                "role": target.role,
                "tenant_id": tenant.id,
                "tenant_slug": tenant.slug,
                "full_name": target.full_name,
            },
            "impersonator": {
                "user_id": user.user_id,
                "email": user.email,
            },
            "expires_in_seconds": IMPERSONATION_TTL_SECONDS,
        }
    finally:
        db.close()


@router.post("/impersonation/stop")
async def stop_impersonation(response: Response, user: AuthContext = Depends(get_current_user)) -> dict:
    impersonator_id = getattr(user, "impersonator_user_id", None)
    if not impersonator_id:
        raise HTTPException(status_code=400, detail="Not currently impersonating")
    db = SessionLocal()
    try:
        admin = db.query(UserAccount).filter(UserAccount.id == impersonator_id).first()
        if not admin or not admin.is_active:
            response.delete_cookie(AUTH_COOKIE, path="/")
            response.delete_cookie(CSRF_COOKIE, path="/")
            raise HTTPException(status_code=401, detail="Impersonator account not found")
        admin_tenant = db.query(Tenant).filter(Tenant.id == admin.tenant_id).first()
        if not admin_tenant:
            raise HTTPException(status_code=500, detail="Impersonator tenant not found")
        token = create_access_token(
            user_id=admin.id,
            email=admin.email,
            tenant_id=admin_tenant.id,
            tenant_slug=admin_tenant.slug,
            role=admin.role,
        )
        _set_auth_cookies(response, token)
        _write_audit(
            actor=user,
            action="impersonation.stopped",
            category="auth",
            target_type="user",
            target_id=str(user.user_id),
            details={
                "impersonator_email": admin.email,
                "was_impersonating_user_id": user.user_id,
            },
        )
        logger.info("impersonation.stopped", admin=admin.email, was_impersonating=user.user_id)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": admin.id,
                "email": admin.email,
                "role": admin.role,
                "tenant_id": admin_tenant.id,
                "tenant_slug": admin_tenant.slug,
            },
        }
    finally:
        db.close()



# ═══════════════════════════════════════════════════════════════════════════
#  MFA / TWO-FACTOR AUTHENTICATION (TOTP)
# ═══════════════════════════════════════════════════════════════════════════

class MfaSetupRequest(BaseModel):
    password: str  # Require password confirmation to enable MFA

class MfaVerifySetupRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)

class MfaLoginRequest(BaseModel):
    mfa_challenge_token: str
    code: str = Field(min_length=6, max_length=10)  # 6 for TOTP, up to 9 for backup codes
    user_id: int

class MfaDisableRequest(BaseModel):
    password: str
    code: str = Field(min_length=6, max_length=6)


@router.post("/mfa/setup")
async def mfa_setup(
    req: MfaSetupRequest,
    request: Request,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Begin MFA setup: generate TOTP secret and QR code URI."""
    _check_rate_limit(request, "mfa-setup", max_requests=5, window_seconds=900)

    from app.core.mfa import generate_totp_secret, get_totp_uri, encrypt_secret

    db = SessionLocal()
    try:
        db_user = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        if db_user.mfa_enabled:
            raise HTTPException(status_code=400, detail="MFA is already enabled")

        # Verify password
        if not db_user.password_hash or not verify_password(req.password, db_user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")

        # Generate secret
        secret = generate_totp_secret()
        uri = get_totp_uri(secret, db_user.email)

        # Store encrypted secret (pending confirmation)
        from config.settings import get_settings
        settings = get_settings()
        encryption_key = settings.auth_secret
        encrypted = encrypt_secret(secret, encryption_key)
        db_user.mfa_secret_encrypted = f"pending:{encrypted}"
        db.commit()

        logger.info("auth.mfa.setup_started", user_id=user.user_id)

        return {
            "secret": secret,
            "uri": uri,
            "message": "Scan the QR code with your authenticator app, then verify with a code.",
        }
    finally:
        db.close()


@router.post("/mfa/verify-setup")
async def mfa_verify_setup(
    req: MfaVerifySetupRequest,
    request: Request,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Complete MFA setup by verifying a TOTP code. Returns backup codes."""
    _check_rate_limit(request, "mfa-verify-setup", max_requests=5, window_seconds=900)

    from app.core.mfa import verify_totp, decrypt_secret, generate_backup_codes, hash_backup_codes

    db = SessionLocal()
    try:
        db_user = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        if db_user.mfa_enabled:
            raise HTTPException(status_code=400, detail="MFA is already enabled")

        # Check pending secret exists
        if not db_user.mfa_secret_encrypted or not db_user.mfa_secret_encrypted.startswith("pending:"):
            raise HTTPException(status_code=400, detail="MFA setup not started. Call /mfa/setup first.")

        # Decrypt secret
        from config.settings import get_settings
        settings = get_settings()
        encrypted = db_user.mfa_secret_encrypted.removeprefix("pending:")
        secret = decrypt_secret(encrypted, settings.auth_secret)

        # Verify code
        if not verify_totp(secret, req.code):
            raise HTTPException(status_code=401, detail="Invalid verification code. Please try again.")

        # Generate backup codes
        backup_codes = generate_backup_codes(8)
        backup_hash = hash_backup_codes(backup_codes)

        # Activate MFA
        from app.core.mfa import encrypt_secret as _enc
        db_user.mfa_secret_encrypted = _enc(secret, settings.auth_secret)
        db_user.mfa_backup_codes_hash = backup_hash
        db_user.mfa_enabled = True
        db_user.mfa_enabled_at = datetime.now(timezone.utc)
        db.commit()

        # Send notification email
        try:
            from app.core.auth_email import render_mfa_enabled_email, send_auth_email
            subject, html, plaintext = render_mfa_enabled_email(db_user.full_name)
            send_auth_email(db_user.email, subject, html, plaintext)
        except Exception as e:
            logger.error("auth.mfa_email_failed", user_id=user.user_id, error=str(e))

        _write_audit(
            actor=user,
            action="mfa.enabled",
            category="auth",
            target_type="user",
            target_id=str(user.user_id),
            details={},
        )

        logger.info("auth.mfa.enabled", user_id=user.user_id)

        return {
            "mfa_enabled": True,
            "backup_codes": backup_codes,
            "message": "MFA is now enabled. Save these backup codes securely – they won't be shown again.",
        }
    finally:
        db.close()


@router.post("/mfa/verify")
async def mfa_verify_login(
    req: MfaLoginRequest,
    request: Request,
    response: Response,
) -> dict:
    """Verify MFA code during login (step 2 of 2-step login)."""
    _check_rate_limit(request, "mfa-verify", max_requests=10, window_seconds=900)

    from app.core.mfa import verify_totp, decrypt_secret, verify_backup_code

    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(
            UserAccount.id == req.user_id,
            UserAccount.is_active.is_(True),
        ).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Verify MFA challenge token
        if not user.email_verification_token or not user.email_verification_token.startswith("mfa:"):
            raise HTTPException(status_code=401, detail="No MFA challenge pending")

        stored_hash = user.email_verification_token.removeprefix("mfa:")
        challenge_hash = _hash_token(req.mfa_challenge_token)
        if stored_hash != challenge_hash:
            raise HTTPException(status_code=401, detail="Invalid MFA challenge token")

        # Check challenge expiry (5 minutes)
        if user.email_verification_sent_at:
            sent_at = user.email_verification_sent_at
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - sent_at).total_seconds()
            if elapsed > 300:
                user.email_verification_token = None
                user.email_verification_sent_at = None
                db.commit()
                raise HTTPException(status_code=410, detail="MFA challenge expired. Please log in again.")

        # Check account lockout
        _check_account_lockout(user)

        # Decrypt TOTP secret
        from config.settings import get_settings
        settings = get_settings()
        secret = decrypt_secret(user.mfa_secret_encrypted, settings.auth_secret)

        # Try TOTP code first
        code = req.code.strip()
        verified = verify_totp(secret, code)

        # If TOTP fails, try backup code
        if not verified and user.mfa_backup_codes_hash:
            backup_valid, updated_hash = verify_backup_code(code, user.mfa_backup_codes_hash)
            if backup_valid:
                verified = True
                user.mfa_backup_codes_hash = updated_hash
                logger.info("auth.mfa.backup_code_used", user_id=user.id)

        if not verified:
            _record_failed_login(db, user)
            raise HTTPException(status_code=401, detail="Invalid MFA code")

        # Clear MFA challenge
        user.email_verification_token = None
        user.email_verification_sent_at = None
        _reset_failed_logins(db, user)
        db.commit()

        # Issue tokens
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant or not tenant.is_active:
            raise HTTPException(status_code=401, detail="Tenant inactive")

        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=user.role,
        )
        _set_auth_cookies(response, access_token)

        refresh_tok, _ = create_refresh_token(
            user_id=user.id,
            tenant_id=tenant.id,
        )
        response.set_cookie(
            key="ariia_refresh_token",
            value=refresh_tok,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/proxy/auth/refresh",
            max_age=30 * 24 * 3600,
        )

        logger.info("auth.mfa.login.success", user_id=user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_tok,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": tenant.id,
                "tenant_slug": tenant.slug,
                "email_verified": bool(user.email_verified),
                "mfa_enabled": True,
            },
        }
    finally:
        db.close()


@router.post("/mfa/disable")
async def mfa_disable(
    req: MfaDisableRequest,
    request: Request,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Disable MFA. Requires password and current TOTP code."""
    _check_rate_limit(request, "mfa-disable", max_requests=3, window_seconds=900)

    from app.core.mfa import verify_totp, decrypt_secret

    db = SessionLocal()
    try:
        db_user = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        if not db_user.mfa_enabled:
            raise HTTPException(status_code=400, detail="MFA is not enabled")

        # Verify password
        if not verify_password(req.password, db_user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")

        # Verify TOTP code
        from config.settings import get_settings
        settings = get_settings()
        secret = decrypt_secret(db_user.mfa_secret_encrypted, settings.auth_secret)
        if not verify_totp(secret, req.code):
            raise HTTPException(status_code=401, detail="Invalid MFA code")

        # Disable MFA
        db_user.mfa_enabled = False
        db_user.mfa_secret_encrypted = None
        db_user.mfa_backup_codes_hash = None
        db_user.mfa_enabled_at = None
        db.commit()

        _write_audit(
            actor=user,
            action="mfa.disabled",
            category="auth",
            target_type="user",
            target_id=str(user.user_id),
            details={},
        )

        logger.info("auth.mfa.disabled", user_id=user.user_id)
        return {"mfa_enabled": False, "message": "Two-factor authentication has been disabled."}
    finally:
        db.close()


@router.post("/mfa/regenerate-backup-codes")
async def mfa_regenerate_backup_codes(
    request: Request,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Regenerate backup codes. Requires authenticated user with MFA enabled."""
    _check_rate_limit(request, "mfa-backup", max_requests=3, window_seconds=3600)

    from app.core.mfa import generate_backup_codes, hash_backup_codes

    db = SessionLocal()
    try:
        db_user = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        if not db_user.mfa_enabled:
            raise HTTPException(status_code=400, detail="MFA is not enabled")

        # Generate new backup codes
        backup_codes = generate_backup_codes(8)
        db_user.mfa_backup_codes_hash = hash_backup_codes(backup_codes)
        db.commit()

        logger.info("auth.mfa.backup_codes_regenerated", user_id=user.user_id)

        return {
            "backup_codes": backup_codes,
            "message": "New backup codes generated. Save them securely – the old codes are no longer valid.",
        }
    finally:
        db.close()
