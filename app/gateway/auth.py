from datetime import datetime, timezone
import secrets

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status

logger = structlog.get_logger()
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import (
    AuthContext,
    create_access_token,
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


router = APIRouter(prefix="/auth", tags=["auth"])
RESERVED_TENANT_SLUGS = {"system", "admin", "api"}
AUTH_COOKIE = "ariia_access_token"
CSRF_COOKIE = "ariia_csrf_token"
IMPERSONATION_TTL_SECONDS = 45 * 60


def _set_auth_cookies(response: Response, token: str) -> None:
    # Secure cookie session for browser clients.
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


class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=120)
    tenant_slug: str | None = None
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str


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
        # Legacy SQLite fallback
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


@router.post("/register")
async def register(req: RegisterRequest, response: Response) -> dict:
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

        tenant = Tenant(name=req.tenant_name.strip(), slug=slug, is_active=True)
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        user = UserAccount(
            tenant_id=tenant.id,
            email=email,
            full_name=req.full_name,
            role="tenant_admin",
            password_hash=hash_password(req.password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # S5: Seed Starter subscription + prompt defaults for new tenants
        try:
            from app.core.models import Plan, Subscription as Sub
            starter = db.query(Plan).filter(Plan.slug == "starter", Plan.is_active.is_(True)).first()
            if starter:
                db.add(Sub(tenant_id=tenant.id, plan_id=starter.id, status="active"))
                db.commit()
        except Exception as _sub_err:
            logger.wariiang("tenant.register.subscription_seed_failed", tenant_id=tenant.id, error=str(_sub_err))

        try:
            from app.core.prompt_builder import seed_prompt_settings
            from app.gateway.persistence import persistence as _ps
            seed_prompt_settings(_ps, tenant.id)
            # Seed tenant display name from registration name
            _ps.upsert_setting("tenant_display_name", tenant.name, tenant_id=tenant.id)
        except Exception as _ps_err:
            logger.wariiang("tenant.register.prompt_seed_failed", tenant_id=tenant.id, error=str(_ps_err))

        token = create_access_token(
            user_id=user.id,
            email=user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=user.role,
        )
        _set_auth_cookies(response, token)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": tenant.id,
                "tenant_slug": tenant.slug,
            },
        }
    finally:
        db.close()


@router.post("/login")
async def login(req: LoginRequest, response: Response) -> dict:
    db = SessionLocal()
    try:
        email = _normalize_email(req.email)
        user = db.query(UserAccount).filter(UserAccount.email == email).first()
        if not user or not user.is_active or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant or not tenant.is_active:
            raise HTTPException(status_code=401, detail="Tenant inactive")
        token = create_access_token(
            user_id=user.id,
            email=user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=user.role,
        )
        _set_auth_cookies(response, token)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": tenant.id,
                "tenant_slug": tenant.slug,
            },
        }
    finally:
        db.close()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie(AUTH_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me")
async def me(user: AuthContext = Depends(get_current_user)) -> dict:
    payload = {
        "id": user.user_id,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "tenant_slug": user.tenant_slug,
    }
    if user.is_impersonating:
        payload["impersonation"] = {
            "active": True,
            "actor_user_id": user.impersonator_user_id,
            "actor_email": user.impersonator_email,
            "actor_role": user.impersonator_role,
            "actor_tenant_id": user.impersonator_tenant_id,
            "actor_tenant_slug": user.impersonator_tenant_slug,
            "reason": user.impersonation_reason or "",
            "started_at": user.impersonation_started_at or "",
        }
    return payload


@router.get("/profile-settings")
async def get_profile_settings(user: AuthContext = Depends(get_current_user)) -> dict:
    db = SessionLocal()
    try:
        row = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "id": row.id,
            "email": row.email,
            "full_name": row.full_name or "",
            "role": row.role,
            "locale": persistence.get_setting(_user_pref_key(user.user_id, "locale"), "de-DE", tenant_id=user.tenant_id) or "de-DE",
            "timezone": persistence.get_setting(_user_pref_key(user.user_id, "timezone"), "Europe/Berlin", tenant_id=user.tenant_id) or "Europe/Berlin",
            "notify_email": persistence.get_setting(_user_pref_key(user.user_id, "notify_email"), "true", tenant_id=user.tenant_id) or "true",
            "notify_telegram": persistence.get_setting(_user_pref_key(user.user_id, "notify_telegram"), "false", tenant_id=user.tenant_id) or "false",
            "compact_mode": persistence.get_setting(_user_pref_key(user.user_id, "compact_mode"), "false", tenant_id=user.tenant_id) or "false",
        }
    finally:
        db.close()


@router.put("/profile-settings")
async def update_profile_settings(req: ProfileSettingsUpdate, user: AuthContext = Depends(get_current_user)) -> dict:
    db = SessionLocal()
    try:
        row = db.query(UserAccount).filter(UserAccount.id == user.user_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        changed: dict[str, str | bool] = {}
        if req.full_name is not None and req.full_name != row.full_name:
            row.full_name = req.full_name
            changed["full_name"] = True

        if req.new_password:
            if not req.current_password or not verify_password(req.current_password, row.password_hash):
                raise HTTPException(status_code=422, detail="Current password is invalid")
            row.password_hash = hash_password(req.new_password)
            changed["password"] = True

        pref_updates = {
            "locale": req.locale,
            "timezone": req.timezone,
            "notify_email": req.notify_email,
            "notify_telegram": req.notify_telegram,
            "compact_mode": req.compact_mode,
        }
        for key, value in pref_updates.items():
            if value is None:
                continue
            persistence.upsert_setting(_user_pref_key(user.user_id, key), str(value), tenant_id=user.tenant_id)
            changed[f"pref:{key}"] = True

        if changed:
            db.commit()
            _write_audit(
                actor=user,
                action="profile.settings.update",
                category="identity",
                target_type="user",
                target_id=str(user.user_id),
                details=changed,
            )
        else:
            db.rollback()
        return {"status": "ok", "changed": sorted(changed.keys())}
    finally:
        db.close()


@router.get("/users")
async def list_users(user: AuthContext = Depends(get_current_user)) -> list[dict]:
    db = SessionLocal()
    try:
        q = db.query(UserAccount)
        if user.role != "system_admin":
            q = q.filter(UserAccount.tenant_id == user.tenant_id)
        rows = q.order_by(UserAccount.created_at.desc()).all()
        tenant_ids = {row.tenant_id for row in rows}
        tenants = {
            t.id: t
            for t in db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()
        } if tenant_ids else {}
        return [
            {
                "id": row.id,
                "email": row.email,
                "full_name": row.full_name,
                "role": row.role,
                "tenant_id": row.tenant_id,
                "tenant_slug": tenants.get(row.tenant_id).slug if tenants.get(row.tenant_id) else None,
                "tenant_name": tenants.get(row.tenant_id).name if tenants.get(row.tenant_id) else None,
                "is_active": row.is_active,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    finally:
        db.close()


@router.post("/users")
async def create_user(req: CreateUserRequest, user: AuthContext = Depends(get_current_user)) -> dict:
    if req.role not in {"tenant_admin", "tenant_user"} and user.role != "system_admin":
        raise HTTPException(status_code=403, detail="Only system admin may assign this role")

    if user.role == "tenant_user":
        raise HTTPException(status_code=403, detail="Tenant user cannot create users")

    db = SessionLocal()
    try:
        if req.role == "system_admin":
            require_role(user, {"system_admin"})
            tenant = db.query(Tenant).filter(Tenant.slug == "system", Tenant.is_active.is_(True)).first()
            if not tenant:
                raise HTTPException(status_code=500, detail="System tenant missing")
            if req.tenant_id and req.tenant_id != tenant.id:
                raise HTTPException(status_code=422, detail="system_admin must belong to system tenant")
            tenant_id = tenant.id
        elif user.role == "system_admin":
            if req.tenant_id is None:
                raise HTTPException(status_code=422, detail="tenant_id is required for system admin user creation")
            tenant_id = req.tenant_id
        else:
            tenant_id = user.tenant_id

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active.is_(True)).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        email = _normalize_email(req.email)
        if db.query(UserAccount).filter(UserAccount.email == email).first():
            raise HTTPException(status_code=409, detail="Email already in use")

        row = UserAccount(
            tenant_id=tenant.id,
            email=email,
            full_name=req.full_name,
            role=req.role,
            password_hash=hash_password(req.password),
            is_active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        _write_audit(
            actor=user,
            action="user.create",
            category="identity",
            target_type="user",
            target_id=str(row.id),
            details={"email": row.email, "tenant_id": row.tenant_id, "role": row.role},
        )

        return {
            "id": row.id,
            "email": row.email,
            "role": row.role,
            "tenant_id": row.tenant_id,
            "tenant_slug": tenant.slug,
        }
    finally:
        db.close()


@router.put("/users/{user_id}")
async def update_user(user_id: int, req: UpdateUserRequest, user: AuthContext = Depends(get_current_user)) -> dict:
    if user.role == "tenant_user":
        raise HTTPException(status_code=403, detail="Tenant user cannot update users")
    db = SessionLocal()
    try:
        target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        actor_is_system = user.role == "system_admin"
        if not actor_is_system and target.tenant_id != user.tenant_id:
            raise HTTPException(status_code=403, detail="Cross-tenant user update is not allowed")
        if not actor_is_system and target.role == "system_admin":
            raise HTTPException(status_code=403, detail="Cannot edit system admin")

        changes: dict[str, str | int | bool | None] = {}
        if req.full_name is not None and req.full_name != target.full_name:
            target.full_name = req.full_name
            changes["full_name"] = req.full_name

        if req.role is not None:
            if req.role not in {"system_admin", "tenant_admin", "tenant_user"}:
                raise HTTPException(status_code=422, detail="Invalid role")
            if not actor_is_system and req.role == "system_admin":
                raise HTTPException(status_code=403, detail="Only system admin may assign system_admin")
            if req.role != target.role:
                target.role = req.role
                changes["role"] = req.role

        if req.is_active is not None and req.is_active != target.is_active:
            target.is_active = req.is_active
            changes["is_active"] = req.is_active
            # Immediately revoke all active tokens when deactivating a user (S1.4)
            if not req.is_active:
                invalidate_user_sessions(target.id, target.tenant_id)

        if req.tenant_id is not None and req.tenant_id != target.tenant_id:
            if not actor_is_system:
                raise HTTPException(status_code=403, detail="Only system admin may change tenant_id")
            tenant = db.query(Tenant).filter(Tenant.id == req.tenant_id, Tenant.is_active.is_(True)).first()
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")
            target.tenant_id = req.tenant_id
            changes["tenant_id"] = req.tenant_id

        if req.password:
            target.password_hash = hash_password(req.password)
            changes["password_reset"] = True

        if not changes:
            return {"status": "noop", "id": target.id}

        db.commit()
        db.refresh(target)
        _write_audit(
            actor=user,
            action="user.update",
            category="identity",
            target_type="user",
            target_id=str(target.id),
            details=changes,
        )
        return {
            "status": "ok",
            "id": target.id,
            "email": target.email,
            "role": target.role,
            "tenant_id": target.tenant_id,
            "is_active": target.is_active,
        }
    finally:
        db.close()


@router.get("/tenants")
async def list_tenants(user: AuthContext = Depends(get_current_user)) -> list[dict]:
    db = SessionLocal()
    try:
        q = db.query(Tenant)
        if user.role != "system_admin":
            q = q.filter(Tenant.id == user.tenant_id)
        rows = q.order_by(Tenant.created_at.asc()).all()
        return [{"id": t.id, "slug": t.slug, "name": t.name, "is_active": t.is_active} for t in rows]
    finally:
        db.close()


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = None


@router.post("/tenants")
async def create_tenant(req: CreateTenantRequest, user: AuthContext = Depends(get_current_user)) -> dict:
    require_role(user, {"system_admin"})
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
        row = Tenant(name=req.name.strip(), slug=slug, is_active=True)
        db.add(row)
        db.commit()
        db.refresh(row)

        # S5: Seed Starter subscription + prompt defaults for new tenants
        try:
            from app.core.models import Plan, Subscription
            starter = db.query(Plan).filter(Plan.slug == "starter", Plan.is_active.is_(True)).first()
            if starter:
                db.add(Subscription(tenant_id=row.id, plan_id=starter.id, status="active"))
                db.commit()
        except Exception as _sub_err:
            logger.wariiang("tenant.create.subscription_seed_failed", tenant_id=row.id, error=str(_sub_err))

        try:
            from app.core.prompt_builder import seed_prompt_settings
            from app.gateway.persistence import persistence as _ps
            seed_prompt_settings(_ps, row.id)
            _ps.upsert_setting("tenant_display_name", row.name, tenant_id=row.id)
        except Exception as _ps_err:
            logger.wariiang("tenant.create.prompt_seed_failed", tenant_id=row.id, error=str(_ps_err))

        _write_audit(
            actor=user,
            action="tenant.create",
            category="tenant",
            target_type="tenant",
            target_id=str(row.id),
            details={"slug": row.slug, "name": row.name},
        )
        return {"id": row.id, "slug": row.slug, "name": row.name}
    finally:
        db.close()


@router.put("/tenants/{tenant_id}")
async def update_tenant(tenant_id: int, req: UpdateTenantRequest, user: AuthContext = Depends(get_current_user)) -> dict:
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        row = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Tenant not found")
        changes: dict[str, str | bool] = {}
        if req.name is not None and req.name.strip() and req.name != row.name:
            row.name = req.name.strip()
            changes["name"] = row.name
        if req.slug is not None:
            slug_base = normalize_tenant_slug(req.slug)
            if slug_base in RESERVED_TENANT_SLUGS and slug_base != row.slug:
                raise HTTPException(status_code=422, detail="Tenant slug is reserved")
            existing = db.query(Tenant).filter(Tenant.slug == slug_base, Tenant.id != row.id).first()
            if existing:
                raise HTTPException(status_code=409, detail="Tenant slug already exists")
            if slug_base != row.slug:
                row.slug = slug_base
                changes["slug"] = slug_base
        if req.is_active is not None and req.is_active != row.is_active:
            row.is_active = req.is_active
            changes["is_active"] = req.is_active
        if not changes:
            return {"status": "noop", "id": row.id}
        db.commit()
        db.refresh(row)
        _write_audit(
            actor=user,
            action="tenant.update",
            category="tenant",
            target_type="tenant",
            target_id=str(row.id),
            details=changes,
        )
        return {"status": "ok", "id": row.id, "slug": row.slug, "name": row.name, "is_active": row.is_active}
    finally:
        db.close()


@router.get("/audit")
async def list_audit_logs(limit: int = 200, user: AuthContext = Depends(get_current_user)) -> list[dict]:
    db = SessionLocal()
    try:
        tenant_filter_supported = _audit_table_has_column(db, "tenant_id")
        q = db.query(AuditLog)
        if user.role != "system_admin" and tenant_filter_supported:
            q = q.filter(AuditLog.tenant_id == user.tenant_id)
        elif user.role != "system_admin" and not tenant_filter_supported:
            return []
        rows = q.order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 1000))).all()
        return [
            {
                "id": row.id,
                "created_at": _safe_iso(row.created_at),
                "actor_user_id": row.actor_user_id,
                "actor_email": row.actor_email,
                "tenant_id": row.tenant_id,
                "action": row.action,
                "category": row.category,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "details_json": row.details_json,
            }
            for row in rows
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"Audit query failed: {exc.__class__.__name__}") from exc
    finally:
        db.close()


@router.post("/users/{user_id}/impersonate")
async def start_impersonation(
    user_id: int,
    req: StartImpersonationRequest,
    response: Response,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    require_role(user, {"system_admin"})
    if user.is_impersonating:
        raise HTTPException(status_code=409, detail="Already in impersonation mode")
    if user_id == user.user_id:
        raise HTTPException(status_code=422, detail="Self impersonation is not allowed")

    db = SessionLocal()
    try:
        target = db.query(UserAccount).filter(UserAccount.id == user_id, UserAccount.is_active.is_(True)).first()
        if not target:
            raise HTTPException(status_code=404, detail="Target user not found or inactive")
        if target.role == "system_admin":
            raise HTTPException(status_code=403, detail="Impersonating system admin accounts is not allowed")
        tenant = db.query(Tenant).filter(Tenant.id == target.tenant_id, Tenant.is_active.is_(True)).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Target tenant not found or inactive")

        token = create_access_token(
            user_id=target.id,
            email=target.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            role=target.role,
            ttl_seconds=IMPERSONATION_TTL_SECONDS,
            impersonation={
                "active": True,
                "actor_user_id": user.user_id,
                "actor_email": user.email,
                "actor_role": user.role,
                "actor_tenant_id": user.tenant_id,
                "actor_tenant_slug": user.tenant_slug,
                "reason": req.reason.strip(),
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        _set_auth_cookies(response, token)
        _write_audit(
            actor=user,
            action="auth.impersonation.start",
            category="security",
            target_type="user",
            target_id=str(target.id),
            details={
                "target_email": target.email,
                "target_role": target.role,
                "target_tenant_id": target.tenant_id,
                "reason": req.reason.strip(),
            },
        )
        return {
            "status": "ok",
            "mode": "ghost",
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": target.id,
                "email": target.email,
                "role": target.role,
                "tenant_id": tenant.id,
                "tenant_slug": tenant.slug,
                "impersonation": {
                    "active": True,
                    "actor_user_id": user.user_id,
                    "actor_email": user.email,
                    "actor_role": user.role,
                    "actor_tenant_id": user.tenant_id,
                    "actor_tenant_slug": user.tenant_slug,
                    "reason": req.reason.strip(),
                },
            },
        }
    finally:
        db.close()


@router.post("/impersonation/stop")
async def stop_impersonation(response: Response, user: AuthContext = Depends(get_current_user)) -> dict:
    if not user.is_impersonating:
        raise HTTPException(status_code=409, detail="No active impersonation session")
    if not user.impersonator_user_id:
        raise HTTPException(status_code=401, detail="Invalid impersonation actor")

    db = SessionLocal()
    try:
        actor = db.query(UserAccount).filter(UserAccount.id == user.impersonator_user_id, UserAccount.is_active.is_(True)).first()
        if not actor or actor.role != "system_admin":
            raise HTTPException(status_code=401, detail="Impersonation actor is invalid")
        actor_tenant = db.query(Tenant).filter(Tenant.id == actor.tenant_id, Tenant.is_active.is_(True)).first()
        if not actor_tenant:
            raise HTTPException(status_code=401, detail="Actor tenant not found or inactive")

        token = create_access_token(
            user_id=actor.id,
            email=actor.email,
            tenant_id=actor_tenant.id,
            tenant_slug=actor_tenant.slug,
            role=actor.role,
        )
        _set_auth_cookies(response, token)
        actor_ctx = AuthContext(
            user_id=actor.id,
            email=actor.email,
            tenant_id=actor_tenant.id,
            tenant_slug=actor_tenant.slug,
            role=actor.role,
        )
        _write_audit(
            actor=actor_ctx,
            action="auth.impersonation.stop",
            category="security",
            target_type="user",
            target_id=str(user.user_id),
            details={
                "target_email": user.email,
                "target_tenant_id": user.tenant_id,
                "reason": user.impersonation_reason or "",
            },
        )
        return {
            "status": "ok",
            "mode": "system_admin",
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": actor.id,
                "email": actor.email,
                "role": actor.role,
                "tenant_id": actor_tenant.id,
                "tenant_slug": actor_tenant.slug,
            },
        }
    finally:
        db.close()
