"""
SMTP Configuration Router
Provides endpoints for System-Admin and Tenant-Admin to configure SMTP settings.
System-level SMTP is used as fallback for all tenants.
Tenant-level SMTP overrides system SMTP for that specific tenant.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
import structlog
import asyncio
import smtplib

from app.core.auth import get_current_user, AuthContext
from app.gateway.persistence import persistence

logger = structlog.get_logger()

router = APIRouter(
    prefix="/admin/smtp",
    tags=["smtp-config"],
    dependencies=[Depends(get_current_user)],
)

REDACTED = "••••••••"


class SmtpConfig(BaseModel):
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""
    from_name: str = "ARIIA"
    use_starttls: bool = True


class SmtpTestRequest(BaseModel):
    to_email: str


# ─── System-Level SMTP (System-Admin only) ─────────────────────────────────

@router.get("/system")
@router.get("/system/")
async def get_system_smtp(user: AuthContext = Depends(get_current_user)) -> dict:
    """Get system-level SMTP configuration (System-Admin only)."""
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System-Admin required")
    
    host = persistence.get_setting("platform_email_smtp_host", "", tenant_id=1)
    port = persistence.get_setting("platform_email_smtp_port", "587", tenant_id=1)
    username = persistence.get_setting("platform_email_smtp_user", "", tenant_id=1)
    password = persistence.get_setting("platform_email_smtp_pass", "", tenant_id=1)
    from_email = persistence.get_setting("platform_email_from_addr", "", tenant_id=1)
    from_name = persistence.get_setting("platform_email_from_name", "ARIIA", tenant_id=1)
    
    return {
        "host": host or "",
        "port": int(port or 587),
        "username": username or "",
        "password": REDACTED if password else "",
        "from_email": from_email or "",
        "from_name": from_name or "",
        "use_starttls": True,
        "configured": bool(host and username and password),
    }


@router.put("/system")
@router.put("/system/")
async def update_system_smtp(
    config: SmtpConfig,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Update system-level SMTP configuration (System-Admin only)."""
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System-Admin required")
    
    persistence.upsert_setting("platform_email_smtp_host", config.host, "SMTP Host", tenant_id=1)
    persistence.upsert_setting("platform_email_smtp_port", str(config.port), "SMTP Port", tenant_id=1)
    persistence.upsert_setting("platform_email_smtp_user", config.username, "SMTP Username", tenant_id=1)
    
    # Only update password if not redacted
    if config.password and config.password != REDACTED:
        persistence.upsert_setting("platform_email_smtp_pass", config.password, "SMTP Password", tenant_id=1)
    
    persistence.upsert_setting("platform_email_from_addr", config.from_email, "From Email", tenant_id=1)
    persistence.upsert_setting("platform_email_from_name", config.from_name, "From Name", tenant_id=1)
    
    logger.info("smtp.system_config_updated", actor=user.email)
    return {"status": "ok", "message": "System-SMTP-Konfiguration aktualisiert"}


@router.post("/system/test")
@router.post("/system/test/")
async def test_system_smtp(
    req: SmtpTestRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Send a test email using system SMTP configuration."""
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System-Admin required")
    
    return await _send_test_email(req.to_email, tenant_id=1, use_system=True)


# ─── Tenant-Level SMTP (Tenant-Admin) ──────────────────────────────────────

@router.get("/tenant")
@router.get("/tenant/")
async def get_tenant_smtp(user: AuthContext = Depends(get_current_user)) -> dict:
    """Get tenant-level SMTP configuration. Shows whether tenant uses own SMTP or system fallback."""
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    
    tid = user.tenant_id
    host = persistence.get_setting("smtp_host", None, tenant_id=tid)
    port = persistence.get_setting("smtp_port", "587", tenant_id=tid)
    username = persistence.get_setting("smtp_username", None, tenant_id=tid)
    password = persistence.get_setting("smtp_password", None, tenant_id=tid)
    from_email = persistence.get_setting("smtp_from_email", None, tenant_id=tid)
    from_name = persistence.get_setting("smtp_from_name", "ARIIA", tenant_id=tid)
    
    has_own_smtp = bool(host and username and password)
    
    # Check if system SMTP is configured
    sys_host = persistence.get_setting("platform_email_smtp_host", None, tenant_id=1)
    sys_user = persistence.get_setting("platform_email_smtp_user", None, tenant_id=1)
    sys_pass = persistence.get_setting("platform_email_smtp_pass", None, tenant_id=1)
    system_configured = bool(sys_host and sys_user and sys_pass)
    
    return {
        "host": host or "",
        "port": int(port or 587),
        "username": username or "",
        "password": REDACTED if password else "",
        "from_email": from_email or "",
        "from_name": from_name or "",
        "use_starttls": True,
        "has_own_smtp": has_own_smtp,
        "uses_system_smtp": not has_own_smtp,
        "system_smtp_configured": system_configured,
    }


@router.put("/tenant")
@router.put("/tenant/")
async def update_tenant_smtp(
    config: SmtpConfig,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Update tenant-level SMTP configuration."""
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    
    tid = user.tenant_id
    persistence.upsert_setting("smtp_host", config.host, "Tenant SMTP Host", tenant_id=tid)
    persistence.upsert_setting("smtp_port", str(config.port), "Tenant SMTP Port", tenant_id=tid)
    persistence.upsert_setting("smtp_username", config.username, "Tenant SMTP Username", tenant_id=tid)
    
    if config.password and config.password != REDACTED:
        persistence.upsert_setting("smtp_password", config.password, "Tenant SMTP Password", tenant_id=tid)
    
    persistence.upsert_setting("smtp_from_email", config.from_email, "Tenant From Email", tenant_id=tid)
    persistence.upsert_setting("smtp_from_name", config.from_name, "Tenant From Name", tenant_id=tid)
    
    logger.info("smtp.tenant_config_updated", tenant_id=tid, actor=user.email)
    return {"status": "ok", "message": "Tenant-SMTP-Konfiguration aktualisiert"}


@router.delete("/tenant")
@router.delete("/tenant/")
async def delete_tenant_smtp(user: AuthContext = Depends(get_current_user)) -> dict:
    """Remove tenant-level SMTP configuration (falls back to system SMTP)."""
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    
    tid = user.tenant_id
    for key in ["smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_from_email", "smtp_from_name"]:
        persistence.delete_setting(key, tenant_id=tid)
    
    logger.info("smtp.tenant_config_deleted", tenant_id=tid, actor=user.email)
    return {"status": "ok", "message": "Tenant-SMTP entfernt. System-SMTP wird verwendet."}


@router.post("/tenant/test")
@router.post("/tenant/test/")
async def test_tenant_smtp(
    req: SmtpTestRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict:
    """Send a test email using tenant SMTP (or system fallback)."""
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    
    return await _send_test_email(req.to_email, tenant_id=user.tenant_id, use_system=False)


# ─── Helper ────────────────────────────────────────────────────────────────

async def _send_test_email(to_email: str, tenant_id: int, use_system: bool) -> dict:
    """Send a test email to verify SMTP configuration."""
    if use_system:
        host = persistence.get_setting("platform_email_smtp_host", None, tenant_id=1)
        port_raw = persistence.get_setting("platform_email_smtp_port", "587", tenant_id=1)
        username = persistence.get_setting("platform_email_smtp_user", None, tenant_id=1)
        password = persistence.get_setting("platform_email_smtp_pass", None, tenant_id=1)
        from_email = persistence.get_setting("platform_email_from_addr", username, tenant_id=1)
        from_name = persistence.get_setting("platform_email_from_name", "ARIIA", tenant_id=1)
    else:
        # Try tenant first, then system fallback
        host = persistence.get_setting("smtp_host", None, tenant_id=tenant_id)
        username = persistence.get_setting("smtp_username", None, tenant_id=tenant_id)
        password = persistence.get_setting("smtp_password", None, tenant_id=tenant_id)
        port_raw = persistence.get_setting("smtp_port", "587", tenant_id=tenant_id)
        from_email = persistence.get_setting("smtp_from_email", None, tenant_id=tenant_id)
        from_name = persistence.get_setting("smtp_from_name", "ARIIA", tenant_id=tenant_id)
        
        if not all([host, username, password]):
            host = persistence.get_setting("platform_email_smtp_host", None, tenant_id=1)
            port_raw = persistence.get_setting("platform_email_smtp_port", "587", tenant_id=1)
            username = persistence.get_setting("platform_email_smtp_user", None, tenant_id=1)
            password = persistence.get_setting("platform_email_smtp_pass", None, tenant_id=1)
            from_email = persistence.get_setting("platform_email_from_addr", username, tenant_id=1)
            from_name = persistence.get_setting("platform_email_from_name", "ARIIA", tenant_id=1)
    
    if not from_email:
        from_email = username
    
    if not all([host, username, password, from_email]):
        raise HTTPException(status_code=400, detail="SMTP nicht konfiguriert. Bitte zuerst SMTP-Daten eingeben.")
    
    try:
        from app.integrations.email import SMTPMailer
        port = int(port_raw or "587")
        mailer = SMTPMailer(
            host=host,
            port=port,
            username=username,
            password=password,
            from_email=from_email,
            from_name=from_name,
            use_starttls=True,
        )
        subject = "ARIIA SMTP Test"
        body = "Diese E-Mail bestätigt, dass die SMTP-Konfiguration korrekt funktioniert.\n\nARIIA Platform"
        await asyncio.to_thread(mailer.send_text_mail, to_email, subject, body)
        logger.info("smtp.test_email_sent", to=to_email)
        return {"status": "ok", "message": f"Test-E-Mail erfolgreich an {to_email} gesendet"}
    except smtplib.SMTPAuthenticationError as e:
        logger.warning("smtp.test_auth_failed", error=str(e))
        raise HTTPException(status_code=400, detail=f"SMTP-Authentifizierung fehlgeschlagen: {e}")
    except smtplib.SMTPException as e:
        logger.warning("smtp.test_failed", error=str(e))
        raise HTTPException(status_code=400, detail=f"SMTP-Fehler: {e}")
    except Exception as e:
        logger.error("smtp.test_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Unerwarteter Fehler: {e}")
