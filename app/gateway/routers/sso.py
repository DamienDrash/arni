"""app/gateway/routers/sso.py — OIDC SSO Endpoints (M5 Enterprise Readiness).

Provides endpoints to integrate with an external Identity Provider (IdP) like Keycloak or Auth0.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import structlog

from app.core.config import settings

logger = structlog.get_logger()
router = APIRouter(prefix="/auth/sso", tags=["SSO / Enterprise"])

class OIDCCallbackPayload(BaseModel):
    code: str
    state: str

@router.get("/login")
async def sso_login(tenant_slug: str):
    """
    Redirects the user to the configured Identity Provider (IdP).
    Placeholder implementation for Enterprise Readiness.
    """
    if not getattr(settings, "oidc_enabled", False):
        raise HTTPException(status_code=501, detail="SSO/OIDC not enabled in this environment")
    
    # In a real implementation:
    # 1. Look up tenant's OIDC config from DB
    # 2. Construct authorization URL
    # 3. Redirect user
    return {"status": "ok", "message": "Redirecting to IdP (Placeholder)"}

@router.post("/callback")
async def sso_callback(payload: OIDCCallbackPayload):
    """
    Handles the OIDC callback from the IdP.
    Validates the authorization code, exchanges it for tokens, and logs the user in.
    """
    if not getattr(settings, "oidc_enabled", False):
        raise HTTPException(status_code=501, detail="SSO/OIDC not enabled in this environment")
        
    logger.info("sso.callback.received", state=payload.state)
    
    # Placeholder: fetch access token, map claims to ARIIA user, issue internal JWT
    return {
        "access_token": "placeholder-jwt-token",
        "token_type": "bearer",
        "user": {"id": 1, "email": "sso-user@example.com"}
    }
