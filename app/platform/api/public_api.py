"""app/platform/api/public_api.py — Public API & White-Labeling Engine.

Provides:
1. White-Labeling: Tenant-specific branding (logo, colors, fonts, custom domain)
2. Public API: API-Key-authenticated endpoints for enterprise customers
   to integrate ARIIA into their own systems programmatically.

The Public API enables:
- Sending messages to the agent
- Retrieving conversation history
- Managing members/contacts
- Querying analytics
- Managing knowledge base
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════════════════════
# WHITE-LABELING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class BrandingTheme(str, Enum):
    """Available base themes."""
    LIGHT = "light"
    DARK = "dark"
    CUSTOM = "custom"


@dataclass
class WhiteLabelConfig:
    """White-label branding configuration for a tenant."""
    tenant_id: int

    # Brand Identity
    brand_name: str = "ARIIA"
    logo_url: str = ""
    favicon_url: str = ""
    support_email: str = ""
    support_url: str = ""

    # Colors
    primary_color: str = "#6366f1"  # Indigo
    secondary_color: str = "#8b5cf6"  # Violet
    accent_color: str = "#06b6d4"  # Cyan
    background_color: str = "#ffffff"
    text_color: str = "#1f2937"
    error_color: str = "#ef4444"
    success_color: str = "#22c55e"

    # Typography
    font_family: str = "Inter, system-ui, sans-serif"
    heading_font: str = ""  # Falls back to font_family

    # Theme
    theme: BrandingTheme = BrandingTheme.LIGHT

    # Custom CSS (injected into portal)
    custom_css: str = ""

    # Custom Domain
    custom_domain: str = ""  # e.g., "support.customer.com"

    # Agent Branding
    agent_name: str = "ARIIA Assistant"
    agent_avatar_url: str = ""
    welcome_message: str = "Hallo! Wie kann ich Ihnen helfen?"
    powered_by_visible: bool = True  # Show "Powered by ARIIA"

    # Email Branding
    email_from_name: str = ""
    email_header_html: str = ""
    email_footer_html: str = ""

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "brand_name": self.brand_name,
            "logo_url": self.logo_url,
            "favicon_url": self.favicon_url,
            "support_email": self.support_email,
            "support_url": self.support_url,
            "colors": {
                "primary": self.primary_color,
                "secondary": self.secondary_color,
                "accent": self.accent_color,
                "background": self.background_color,
                "text": self.text_color,
                "error": self.error_color,
                "success": self.success_color,
            },
            "typography": {
                "font_family": self.font_family,
                "heading_font": self.heading_font or self.font_family,
            },
            "theme": self.theme.value,
            "custom_css": self.custom_css,
            "custom_domain": self.custom_domain,
            "agent": {
                "name": self.agent_name,
                "avatar_url": self.agent_avatar_url,
                "welcome_message": self.welcome_message,
                "powered_by_visible": self.powered_by_visible,
            },
        }

    def to_css_variables(self) -> str:
        """Generate CSS custom properties for injection."""
        return (
            f":root {{\n"
            f"  --ariia-primary: {self.primary_color};\n"
            f"  --ariia-secondary: {self.secondary_color};\n"
            f"  --ariia-accent: {self.accent_color};\n"
            f"  --ariia-bg: {self.background_color};\n"
            f"  --ariia-text: {self.text_color};\n"
            f"  --ariia-error: {self.error_color};\n"
            f"  --ariia-success: {self.success_color};\n"
            f"  --ariia-font: {self.font_family};\n"
            f"  --ariia-heading-font: {self.heading_font or self.font_family};\n"
            f"}}\n"
            f"{self.custom_css}"
        )


class WhiteLabelManager:
    """Manages white-label configurations for tenants."""

    def __init__(self):
        self._configs: dict[int, WhiteLabelConfig] = {}

    def set_config(self, tenant_id: int, **kwargs) -> WhiteLabelConfig:
        """Create or update white-label config for a tenant."""
        existing = self._configs.get(tenant_id)
        if existing:
            for key, value in kwargs.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            return existing
        else:
            config = WhiteLabelConfig(tenant_id=tenant_id, **kwargs)
            self._configs[tenant_id] = config
            return config

    def get_config(self, tenant_id: int) -> WhiteLabelConfig:
        """Get white-label config, returning defaults if not configured."""
        return self._configs.get(tenant_id, WhiteLabelConfig(tenant_id=tenant_id))

    def delete_config(self, tenant_id: int) -> bool:
        if tenant_id in self._configs:
            del self._configs[tenant_id]
            return True
        return False


# ══════════════════════════════════════════════════════════════════════════════
# API KEY MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

class APIKeyScope(str, Enum):
    """Scopes for API key permissions."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    CONVERSATIONS = "conversations"
    MEMBERS = "members"
    KNOWLEDGE = "knowledge"
    ANALYTICS = "analytics"
    WEBHOOKS = "webhooks"


@dataclass
class APIKey:
    """Represents an API key for a tenant."""
    id: str
    tenant_id: int
    name: str
    key_hash: str  # SHA-256 hash of the actual key
    key_prefix: str  # First 8 chars for identification (e.g., "ariia_pk_")
    scopes: list[APIKeyScope]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    rate_limit: int = 1000  # Requests per hour
    request_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def has_scope(self, scope: APIKeyScope) -> bool:
        return APIKeyScope.ADMIN in self.scopes or scope in self.scopes

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scopes": [s.value for s in self.scopes],
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
            "rate_limit": self.rate_limit,
            "request_count": self.request_count,
        }


class APIKeyManager:
    """Manages API keys for tenant Public API access."""

    KEY_PREFIX = "ariia_pk_"

    def __init__(self):
        self._keys: dict[str, APIKey] = {}  # key_hash -> APIKey
        self._tenant_keys: dict[int, list[str]] = {}  # tenant_id -> [key_hash]
        self._rate_windows: dict[str, list[float]] = {}  # key_hash -> [timestamps]

    def create_key(
        self,
        tenant_id: int,
        name: str,
        scopes: Optional[list[APIKeyScope]] = None,
        expires_in_days: Optional[int] = None,
        rate_limit: int = 1000,
    ) -> tuple[str, APIKey]:
        """Create a new API key for a tenant.

        Returns (raw_key, api_key_object). The raw_key is only shown once.
        """
        raw_secret = secrets.token_urlsafe(32)
        raw_key = f"{self.KEY_PREFIX}{raw_secret}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:16]

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        api_key = APIKey(
            id=secrets.token_hex(8),
            tenant_id=tenant_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=scopes or [APIKeyScope.READ, APIKeyScope.CONVERSATIONS],
            expires_at=expires_at,
            rate_limit=rate_limit,
        )

        self._keys[key_hash] = api_key
        if tenant_id not in self._tenant_keys:
            self._tenant_keys[tenant_id] = []
        self._tenant_keys[tenant_id].append(key_hash)

        logger.info("api_key.created",
                     tenant_id=tenant_id,
                     key_id=api_key.id,
                     name=name,
                     scopes=[s.value for s in api_key.scopes])

        return raw_key, api_key

    def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """Validate an API key and return the associated APIKey object."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = self._keys.get(key_hash)

        if not api_key:
            return None
        if not api_key.is_active:
            return None
        if api_key.is_expired:
            return None

        # Rate limiting check
        if not self._check_rate_limit(key_hash, api_key.rate_limit):
            logger.warning("api_key.rate_limited",
                           tenant_id=api_key.tenant_id,
                           key_id=api_key.id)
            return None

        # Update usage
        api_key.last_used_at = datetime.now(timezone.utc)
        api_key.request_count += 1

        return api_key

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key by its ID."""
        for key_hash, api_key in self._keys.items():
            if api_key.id == key_id:
                api_key.is_active = False
                logger.info("api_key.revoked",
                             tenant_id=api_key.tenant_id,
                             key_id=key_id)
                return True
        return False

    def list_keys(self, tenant_id: int) -> list[dict]:
        """List all API keys for a tenant (without exposing the actual keys)."""
        key_hashes = self._tenant_keys.get(tenant_id, [])
        return [self._keys[kh].to_dict() for kh in key_hashes if kh in self._keys]

    def rotate_key(self, key_id: str) -> Optional[tuple[str, APIKey]]:
        """Rotate an API key: revoke old, create new with same config."""
        for key_hash, api_key in self._keys.items():
            if api_key.id == key_id and api_key.is_active:
                # Revoke old
                api_key.is_active = False
                # Create new with same config
                return self.create_key(
                    tenant_id=api_key.tenant_id,
                    name=f"{api_key.name} (rotated)",
                    scopes=api_key.scopes,
                    rate_limit=api_key.rate_limit,
                )
        return None

    def _check_rate_limit(self, key_hash: str, limit: int) -> bool:
        """Sliding window rate limiting per API key."""
        now = time.time()
        window = 3600  # 1 hour

        if key_hash not in self._rate_windows:
            self._rate_windows[key_hash] = []

        # Remove expired entries
        self._rate_windows[key_hash] = [
            t for t in self._rate_windows[key_hash]
            if now - t < window
        ]

        if len(self._rate_windows[key_hash]) >= limit:
            return False

        self._rate_windows[key_hash].append(now)
        return True


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API ROUTER
# ══════════════════════════════════════════════════════════════════════════════

# Global managers
_api_key_manager: Optional[APIKeyManager] = None
_white_label_manager: Optional[WhiteLabelManager] = None


def get_api_key_manager() -> APIKeyManager:
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def get_white_label_manager() -> WhiteLabelManager:
    global _white_label_manager
    if _white_label_manager is None:
        _white_label_manager = WhiteLabelManager()
    return _white_label_manager


# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> APIKey:
    """Dependency to verify API key from header."""
    if not api_key:
        raise HTTPException(401, "API key required. Pass via X-API-Key header.")
    manager = get_api_key_manager()
    key_obj = manager.validate_key(api_key)
    if not key_obj:
        raise HTTPException(403, "Invalid, expired, or rate-limited API key.")
    return key_obj


def require_scope(scope: APIKeyScope):
    """Dependency factory to require a specific API key scope."""
    async def _check(key: APIKey = Depends(verify_api_key)):
        if not key.has_scope(scope):
            raise HTTPException(
                403,
                f"API key lacks required scope: {scope.value}"
            )
        return key
    return _check


# ── Pydantic Models ──────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    """Send a message to the ARIIA agent."""
    user_id: str = Field(..., description="External user identifier")
    message: str = Field(..., description="Message text", max_length=4096)
    platform: str = Field("api", description="Source platform")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class SendMessageResponse(BaseModel):
    """Response after sending a message."""
    message_id: str
    status: str
    queued_at: str


class ConversationResponse(BaseModel):
    """Conversation data."""
    session_id: str
    user_id: str
    platform: str
    message_count: int
    created_at: str
    last_message_at: Optional[str] = None


class MemberResponse(BaseModel):
    """Member/contact data."""
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str
    created_at: str


class KnowledgeUploadRequest(BaseModel):
    """Upload knowledge to the tenant's knowledge base."""
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content (text or markdown)")
    category: str = Field("general", description="Knowledge category")
    metadata: dict = Field(default_factory=dict)


class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., description="Descriptive name for the key")
    scopes: list[str] = Field(
        default=["read", "conversations"],
        description="Permission scopes"
    )
    expires_in_days: Optional[int] = Field(None, description="Days until expiration")
    rate_limit: int = Field(1000, description="Max requests per hour")


class WhiteLabelRequest(BaseModel):
    """Request to update white-label branding."""
    brand_name: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    font_family: Optional[str] = None
    heading_font: Optional[str] = None
    theme: Optional[str] = None
    custom_css: Optional[str] = None
    custom_domain: Optional[str] = None
    agent_name: Optional[str] = None
    agent_avatar_url: Optional[str] = None
    welcome_message: Optional[str] = None
    powered_by_visible: Optional[bool] = None
    support_email: Optional[str] = None
    support_url: Optional[str] = None


# ── Public API Router ────────────────────────────────────────────────────────

def create_public_api_router() -> APIRouter:
    """Create the Public API router for enterprise customers."""
    router = APIRouter(prefix="/api/v1/public", tags=["public-api"])

    # ── Messages ─────────────────────────────────────────────────────────
    @router.post("/messages", response_model=SendMessageResponse)
    async def send_message(
        req: SendMessageRequest,
        key: APIKey = Depends(require_scope(APIKeyScope.CONVERSATIONS)),
    ):
        """Send a message to the ARIIA agent on behalf of a user."""
        import uuid
        message_id = f"api_{uuid.uuid4().hex[:12]}"

        logger.info("public_api.message_sent",
                     tenant_id=key.tenant_id,
                     user_id=req.user_id,
                     message_length=len(req.message))

        return SendMessageResponse(
            message_id=message_id,
            status="queued",
            queued_at=datetime.now(timezone.utc).isoformat(),
        )

    @router.get("/conversations")
    async def list_conversations(
        limit: int = 50,
        offset: int = 0,
        key: APIKey = Depends(require_scope(APIKeyScope.CONVERSATIONS)),
    ):
        """List recent conversations for the tenant."""
        return {
            "tenant_id": key.tenant_id,
            "conversations": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
        }

    @router.get("/conversations/{session_id}")
    async def get_conversation(
        session_id: str,
        key: APIKey = Depends(require_scope(APIKeyScope.CONVERSATIONS)),
    ):
        """Get a specific conversation with messages."""
        return {
            "session_id": session_id,
            "tenant_id": key.tenant_id,
            "messages": [],
        }

    # ── Members ──────────────────────────────────────────────────────────
    @router.get("/members")
    async def list_members(
        limit: int = 50,
        offset: int = 0,
        search: str = "",
        key: APIKey = Depends(require_scope(APIKeyScope.MEMBERS)),
    ):
        """List members/contacts for the tenant."""
        return {
            "tenant_id": key.tenant_id,
            "members": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
        }

    @router.get("/members/{member_id}")
    async def get_member(
        member_id: int,
        key: APIKey = Depends(require_scope(APIKeyScope.MEMBERS)),
    ):
        """Get a specific member's details."""
        return {
            "member_id": member_id,
            "tenant_id": key.tenant_id,
        }

    # ── Knowledge Base ───────────────────────────────────────────────────
    @router.post("/knowledge")
    async def upload_knowledge(
        req: KnowledgeUploadRequest,
        key: APIKey = Depends(require_scope(APIKeyScope.KNOWLEDGE)),
    ):
        """Upload a document to the tenant's knowledge base."""
        import uuid
        doc_id = f"kb_{uuid.uuid4().hex[:12]}"

        logger.info("public_api.knowledge_uploaded",
                     tenant_id=key.tenant_id,
                     title=req.title,
                     category=req.category)

        return {
            "document_id": doc_id,
            "title": req.title,
            "category": req.category,
            "status": "processing",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @router.get("/knowledge")
    async def list_knowledge(
        category: str = "",
        limit: int = 50,
        key: APIKey = Depends(require_scope(APIKeyScope.KNOWLEDGE)),
    ):
        """List knowledge base documents."""
        return {
            "tenant_id": key.tenant_id,
            "documents": [],
            "total": 0,
        }

    @router.delete("/knowledge/{document_id}")
    async def delete_knowledge(
        document_id: str,
        key: APIKey = Depends(require_scope(APIKeyScope.KNOWLEDGE)),
    ):
        """Delete a knowledge base document."""
        return {"document_id": document_id, "status": "deleted"}

    # ── Analytics ────────────────────────────────────────────────────────
    @router.get("/analytics/summary")
    async def get_analytics_summary(
        days: int = 30,
        key: APIKey = Depends(require_scope(APIKeyScope.ANALYTICS)),
    ):
        """Get analytics summary for the tenant."""
        return {
            "tenant_id": key.tenant_id,
            "period_days": days,
            "conversations": {"total": 0, "trend": 0.0},
            "messages": {"total": 0, "trend": 0.0},
            "avg_response_time_ms": 0,
            "satisfaction_score": 0.0,
            "escalation_rate": 0.0,
        }

    @router.get("/analytics/intents")
    async def get_intent_analytics(
        days: int = 30,
        limit: int = 20,
        key: APIKey = Depends(require_scope(APIKeyScope.ANALYTICS)),
    ):
        """Get top intents detected in conversations."""
        return {
            "tenant_id": key.tenant_id,
            "period_days": days,
            "intents": [],
        }

    # ── Webhooks ─────────────────────────────────────────────────────────
    @router.post("/webhooks")
    async def register_webhook(
        url: str,
        events: list[str] = ["conversation.created", "escalation.triggered"],
        key: APIKey = Depends(require_scope(APIKeyScope.WEBHOOKS)),
    ):
        """Register a webhook for event notifications."""
        import uuid
        webhook_id = f"wh_{uuid.uuid4().hex[:12]}"

        return {
            "webhook_id": webhook_id,
            "url": url,
            "events": events,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @router.get("/webhooks")
    async def list_webhooks(
        key: APIKey = Depends(require_scope(APIKeyScope.WEBHOOKS)),
    ):
        """List registered webhooks."""
        return {"tenant_id": key.tenant_id, "webhooks": []}

    @router.delete("/webhooks/{webhook_id}")
    async def delete_webhook(
        webhook_id: str,
        key: APIKey = Depends(require_scope(APIKeyScope.WEBHOOKS)),
    ):
        """Delete a webhook."""
        return {"webhook_id": webhook_id, "status": "deleted"}

    # ── API Info ─────────────────────────────────────────────────────────
    @router.get("/info")
    async def api_info(key: APIKey = Depends(verify_api_key)):
        """Get API information and key details."""
        return {
            "api_version": "v1",
            "tenant_id": key.tenant_id,
            "key_name": key.name,
            "scopes": [s.value for s in key.scopes],
            "rate_limit": key.rate_limit,
            "request_count": key.request_count,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        }

    return router


# ── API Key Management Router ────────────────────────────────────────────────

def create_api_key_management_router() -> APIRouter:
    """Create the API key management router (for tenant admins)."""
    router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])

    @router.post("/")
    async def create_api_key(req: APIKeyCreateRequest):
        """Create a new API key for the tenant."""
        manager = get_api_key_manager()
        scopes = []
        for s in req.scopes:
            try:
                scopes.append(APIKeyScope(s))
            except ValueError:
                raise HTTPException(400, f"Invalid scope: {s}")

        # Default tenant_id=1 for now; in production, extract from auth context
        raw_key, api_key = manager.create_key(
            tenant_id=1,
            name=req.name,
            scopes=scopes,
            expires_in_days=req.expires_in_days,
            rate_limit=req.rate_limit,
        )

        return {
            "key": raw_key,  # Only shown once!
            "key_info": api_key.to_dict(),
            "warning": "Store this key securely. It will not be shown again.",
        }

    @router.get("/")
    async def list_api_keys():
        """List all API keys for the tenant."""
        manager = get_api_key_manager()
        return {"keys": manager.list_keys(1)}

    @router.delete("/{key_id}")
    async def revoke_api_key(key_id: str):
        """Revoke an API key."""
        manager = get_api_key_manager()
        if not manager.revoke_key(key_id):
            raise HTTPException(404, "API key not found")
        return {"status": "revoked", "key_id": key_id}

    @router.post("/{key_id}/rotate")
    async def rotate_api_key(key_id: str):
        """Rotate an API key (revoke old, create new with same config)."""
        manager = get_api_key_manager()
        result = manager.rotate_key(key_id)
        if not result:
            raise HTTPException(404, "API key not found or already revoked")
        raw_key, api_key = result
        return {
            "new_key": raw_key,
            "key_info": api_key.to_dict(),
            "warning": "Store this key securely. It will not be shown again.",
        }

    return router


# ── White-Label Router ───────────────────────────────────────────────────────

def create_white_label_router() -> APIRouter:
    """Create the white-label management router."""
    router = APIRouter(prefix="/api/v1/branding", tags=["branding"])

    @router.get("/{tenant_id}")
    async def get_branding(tenant_id: int):
        """Get white-label branding for a tenant."""
        manager = get_white_label_manager()
        config = manager.get_config(tenant_id)
        return config.to_dict()

    @router.put("/{tenant_id}")
    async def update_branding(tenant_id: int, req: WhiteLabelRequest):
        """Update white-label branding for a tenant."""
        manager = get_white_label_manager()
        update_data = {k: v for k, v in req.model_dump().items() if v is not None}

        if "theme" in update_data:
            try:
                update_data["theme"] = BrandingTheme(update_data["theme"])
            except ValueError:
                raise HTTPException(400, f"Invalid theme: {update_data['theme']}")

        config = manager.set_config(tenant_id, **update_data)

        logger.info("branding.updated", tenant_id=tenant_id, fields=list(update_data.keys()))

        return config.to_dict()

    @router.get("/{tenant_id}/css")
    async def get_branding_css(tenant_id: int):
        """Get CSS variables for white-label injection."""
        manager = get_white_label_manager()
        config = manager.get_config(tenant_id)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=config.to_css_variables(),
            media_type="text/css",
        )

    @router.delete("/{tenant_id}")
    async def reset_branding(tenant_id: int):
        """Reset branding to defaults."""
        manager = get_white_label_manager()
        manager.delete_config(tenant_id)
        return {"status": "reset", "tenant_id": tenant_id}

    @router.get("/{tenant_id}/preview")
    async def preview_branding(tenant_id: int):
        """Get a preview of the branding configuration."""
        manager = get_white_label_manager()
        config = manager.get_config(tenant_id)
        return {
            "branding": config.to_dict(),
            "css_variables": config.to_css_variables(),
            "preview_url": f"/branding/preview/{tenant_id}",
        }

    return router
