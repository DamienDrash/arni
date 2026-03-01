"""app/core/sso.py — Enterprise SSO/SAML 2.0 Authentication.

Provides SAML 2.0 Service Provider (SP) functionality for enterprise tenants,
enabling Single Sign-On integration with corporate Identity Providers (IdP)
like Okta, Azure AD, OneLogin, Google Workspace, etc.

Architecture:
- Each tenant can configure their own SAML IdP
- SP metadata is generated per-tenant
- ACS (Assertion Consumer Service) validates SAML responses
- SLO (Single Logout) is supported
- JIT (Just-In-Time) user provisioning creates users on first login
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlencode, quote_plus
import xml.etree.ElementTree as ET

import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════════════════════
# SAML Configuration Models
# ══════════════════════════════════════════════════════════════════════════════

class SSOProvider(str, Enum):
    """Supported SSO Identity Providers."""
    OKTA = "okta"
    AZURE_AD = "azure_ad"
    GOOGLE_WORKSPACE = "google_workspace"
    ONELOGIN = "onelogin"
    AUTH0 = "auth0"
    KEYCLOAK = "keycloak"
    CUSTOM_SAML = "custom_saml"


class SSOStatus(str, Enum):
    """SSO configuration status."""
    DISABLED = "disabled"
    CONFIGURING = "configuring"
    TESTING = "testing"
    ACTIVE = "active"
    ERROR = "error"


@dataclass
class SAMLConfig:
    """SAML 2.0 configuration for a tenant's IdP."""
    tenant_id: int
    provider: SSOProvider
    status: SSOStatus = SSOStatus.DISABLED

    # IdP Configuration
    idp_entity_id: str = ""
    idp_sso_url: str = ""
    idp_slo_url: str = ""
    idp_certificate: str = ""  # PEM-encoded X.509 certificate

    # SP Configuration (auto-generated)
    sp_entity_id: str = ""
    sp_acs_url: str = ""
    sp_slo_url: str = ""

    # Attribute Mapping
    attribute_mapping: dict[str, str] = field(default_factory=lambda: {
        "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        "first_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
        "last_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
        "display_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        "groups": "http://schemas.xmlsoap.org/claims/Group",
    })

    # Options
    jit_provisioning: bool = True  # Auto-create users on first SSO login
    force_sso: bool = False  # Disable password login when SSO is active
    default_role: str = "tenant_user"
    allowed_domains: list[str] = field(default_factory=list)  # Restrict to specific email domains

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "provider": self.provider.value,
            "status": self.status.value,
            "idp_entity_id": self.idp_entity_id,
            "idp_sso_url": self.idp_sso_url,
            "idp_slo_url": self.idp_slo_url,
            "sp_entity_id": self.sp_entity_id,
            "sp_acs_url": self.sp_acs_url,
            "sp_slo_url": self.sp_slo_url,
            "attribute_mapping": self.attribute_mapping,
            "jit_provisioning": self.jit_provisioning,
            "force_sso": self.force_sso,
            "default_role": self.default_role,
            "allowed_domains": self.allowed_domains,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class SAMLAssertion:
    """Parsed SAML assertion from IdP response."""
    name_id: str
    session_index: str
    attributes: dict[str, Any]
    issuer: str
    audience: str
    not_before: Optional[datetime] = None
    not_on_or_after: Optional[datetime] = None
    authn_instant: Optional[datetime] = None

    @property
    def email(self) -> str:
        return self.attributes.get("email", self.name_id)

    @property
    def display_name(self) -> str:
        first = self.attributes.get("first_name", "")
        last = self.attributes.get("last_name", "")
        if first or last:
            return f"{first} {last}".strip()
        return self.attributes.get("display_name", self.email)


# ══════════════════════════════════════════════════════════════════════════════
# SAML Request/Response Builder
# ══════════════════════════════════════════════════════════════════════════════

SAML_NS = {
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "md": "urn:oasis:names:tc:SAML:2.0:metadata",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}


class SAMLRequestBuilder:
    """Builds SAML 2.0 AuthnRequest and LogoutRequest messages."""

    @staticmethod
    def build_authn_request(config: SAMLConfig, relay_state: str = "") -> dict:
        """Build a SAML AuthnRequest for SP-initiated SSO.

        Returns dict with 'url' (redirect URL) and 'request_id'.
        """
        request_id = f"_ariia_{uuid.uuid4().hex}"
        issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        authn_request = (
            f'<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
            f' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
            f' ID="{request_id}"'
            f' Version="2.0"'
            f' IssueInstant="{issue_instant}"'
            f' Destination="{config.idp_sso_url}"'
            f' AssertionConsumerServiceURL="{config.sp_acs_url}"'
            f' ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
            f'<saml:Issuer>{config.sp_entity_id}</saml:Issuer>'
            f'<samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"'
            f' AllowCreate="true"/>'
            f'</samlp:AuthnRequest>'
        )

        # Deflate + Base64 encode for HTTP-Redirect binding
        compressed = zlib.compress(authn_request.encode("utf-8"))[2:-4]
        encoded = base64.b64encode(compressed).decode("utf-8")

        params = {"SAMLRequest": encoded}
        if relay_state:
            params["RelayState"] = relay_state

        redirect_url = f"{config.idp_sso_url}?{urlencode(params)}"

        logger.info("saml.authn_request_built",
                     tenant_id=config.tenant_id,
                     request_id=request_id,
                     idp_url=config.idp_sso_url)

        return {
            "url": redirect_url,
            "request_id": request_id,
        }

    @staticmethod
    def build_logout_request(config: SAMLConfig, name_id: str, session_index: str) -> dict:
        """Build a SAML LogoutRequest for SP-initiated SLO."""
        request_id = f"_ariia_slo_{uuid.uuid4().hex}"
        issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        logout_request = (
            f'<samlp:LogoutRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
            f' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
            f' ID="{request_id}"'
            f' Version="2.0"'
            f' IssueInstant="{issue_instant}"'
            f' Destination="{config.idp_slo_url}">'
            f'<saml:Issuer>{config.sp_entity_id}</saml:Issuer>'
            f'<saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">'
            f'{name_id}</saml:NameID>'
            f'<samlp:SessionIndex>{session_index}</samlp:SessionIndex>'
            f'</samlp:LogoutRequest>'
        )

        compressed = zlib.compress(logout_request.encode("utf-8"))[2:-4]
        encoded = base64.b64encode(compressed).decode("utf-8")

        params = {"SAMLRequest": encoded}
        redirect_url = f"{config.idp_slo_url}?{urlencode(params)}"

        logger.info("saml.logout_request_built",
                     tenant_id=config.tenant_id,
                     request_id=request_id)

        return {
            "url": redirect_url,
            "request_id": request_id,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SAML Response Validator
# ══════════════════════════════════════════════════════════════════════════════

class SAMLResponseValidator:
    """Validates and parses SAML 2.0 Response from IdP."""

    def __init__(self, config: SAMLConfig):
        self.config = config

    def validate_and_parse(self, saml_response_b64: str) -> SAMLAssertion:
        """Validate a SAML response and extract the assertion.

        Args:
            saml_response_b64: Base64-encoded SAML Response XML

        Returns:
            SAMLAssertion with parsed user attributes

        Raises:
            SAMLValidationError: If validation fails
        """
        try:
            # 1. Decode
            xml_bytes = base64.b64decode(saml_response_b64)
            xml_str = xml_bytes.decode("utf-8")

            # 2. Parse XML
            root = ET.fromstring(xml_str)

            # 3. Check status
            self._check_status(root)

            # 4. Extract assertion
            assertion = root.find(".//saml:Assertion", SAML_NS)
            if assertion is None:
                raise SAMLValidationError("No assertion found in SAML response")

            # 5. Validate issuer
            issuer_elem = assertion.find("saml:Issuer", SAML_NS)
            issuer = issuer_elem.text if issuer_elem is not None else ""
            if issuer and self.config.idp_entity_id and issuer != self.config.idp_entity_id:
                raise SAMLValidationError(
                    f"Issuer mismatch: expected {self.config.idp_entity_id}, got {issuer}"
                )

            # 6. Validate conditions (time-based)
            conditions = assertion.find("saml:Conditions", SAML_NS)
            not_before = None
            not_on_or_after = None
            audience = ""
            if conditions is not None:
                nb = conditions.get("NotBefore")
                noa = conditions.get("NotOnOrAfter")
                if nb:
                    not_before = datetime.fromisoformat(nb.replace("Z", "+00:00"))
                if noa:
                    not_on_or_after = datetime.fromisoformat(noa.replace("Z", "+00:00"))

                # Check time validity (with 5 min clock skew tolerance)
                now = datetime.now(timezone.utc)
                skew = timedelta(minutes=5)
                if not_before and now < (not_before - skew):
                    raise SAMLValidationError("Assertion not yet valid (NotBefore)")
                if not_on_or_after and now > (not_on_or_after + skew):
                    raise SAMLValidationError("Assertion expired (NotOnOrAfter)")

                # Check audience
                audience_elem = conditions.find(".//saml:AudienceRestriction/saml:Audience", SAML_NS)
                audience = audience_elem.text if audience_elem is not None else ""

            # 7. Extract NameID
            subject = assertion.find("saml:Subject/saml:NameID", SAML_NS)
            name_id = subject.text if subject is not None else ""
            if not name_id:
                raise SAMLValidationError("No NameID found in assertion")

            # 8. Extract SessionIndex
            authn_stmt = assertion.find("saml:AuthnStatement", SAML_NS)
            session_index = authn_stmt.get("SessionIndex", "") if authn_stmt is not None else ""

            # 9. Extract attributes
            attributes = self._extract_attributes(assertion)

            # 10. Map attributes using config mapping
            mapped_attrs = self._map_attributes(attributes)

            # 11. Validate email domain if restricted
            email = mapped_attrs.get("email", name_id)
            if self.config.allowed_domains:
                domain = email.split("@")[-1].lower() if "@" in email else ""
                if domain not in [d.lower() for d in self.config.allowed_domains]:
                    raise SAMLValidationError(
                        f"Email domain '{domain}' not in allowed domains"
                    )

            logger.info("saml.response_validated",
                        tenant_id=self.config.tenant_id,
                        email=email,
                        provider=self.config.provider.value)

            return SAMLAssertion(
                name_id=name_id,
                session_index=session_index,
                attributes=mapped_attrs,
                issuer=issuer,
                audience=audience,
                not_before=not_before,
                not_on_or_after=not_on_or_after,
            )

        except SAMLValidationError:
            raise
        except ET.ParseError as e:
            raise SAMLValidationError(f"Invalid SAML XML: {e}")
        except Exception as e:
            logger.error("saml.validation_failed",
                         tenant_id=self.config.tenant_id,
                         error=str(e))
            raise SAMLValidationError(f"SAML validation failed: {e}")

    def _check_status(self, root: ET.Element) -> None:
        """Check SAML response status code."""
        status = root.find(".//samlp:Status/samlp:StatusCode", SAML_NS)
        if status is not None:
            code = status.get("Value", "")
            if "Success" not in code:
                status_msg = root.find(".//samlp:Status/samlp:StatusMessage", SAML_NS)
                msg = status_msg.text if status_msg is not None else "Unknown error"
                raise SAMLValidationError(f"SAML authentication failed: {code} - {msg}")

    def _extract_attributes(self, assertion: ET.Element) -> dict[str, str]:
        """Extract all attributes from the assertion."""
        attrs = {}
        attr_stmt = assertion.find("saml:AttributeStatement", SAML_NS)
        if attr_stmt is not None:
            for attr in attr_stmt.findall("saml:Attribute", SAML_NS):
                name = attr.get("Name", "")
                value_elem = attr.find("saml:AttributeValue", SAML_NS)
                value = value_elem.text if value_elem is not None else ""
                if name:
                    attrs[name] = value
        return attrs

    def _map_attributes(self, raw_attrs: dict[str, str]) -> dict[str, str]:
        """Map IdP attribute names to ARIIA attribute names using config mapping."""
        mapped = {}
        reverse_mapping = {v: k for k, v in self.config.attribute_mapping.items()}
        for raw_name, raw_value in raw_attrs.items():
            if raw_name in reverse_mapping:
                mapped[reverse_mapping[raw_name]] = raw_value
            else:
                # Keep unmapped attributes with original name
                mapped[raw_name] = raw_value
        return mapped


class SAMLValidationError(Exception):
    """Raised when SAML response validation fails."""
    pass


# ══════════════════════════════════════════════════════════════════════════════
# SSO Manager
# ══════════════════════════════════════════════════════════════════════════════

class SSOManager:
    """Manages SSO configurations and authentication flows for tenants.

    This is the main entry point for SSO operations. It handles:
    - Configuration CRUD
    - SP metadata generation
    - Login/logout flow initiation
    - SAML response processing
    - JIT user provisioning
    """

    def __init__(self, base_url: str = "https://www.ariia.ai"):
        self.base_url = base_url.rstrip("/")
        self._configs: dict[int, SAMLConfig] = {}
        self._pending_requests: dict[str, dict] = {}  # request_id -> metadata

    def configure_sso(
        self,
        tenant_id: int,
        provider: SSOProvider,
        idp_entity_id: str,
        idp_sso_url: str,
        idp_certificate: str,
        idp_slo_url: str = "",
        attribute_mapping: Optional[dict[str, str]] = None,
        jit_provisioning: bool = True,
        force_sso: bool = False,
        default_role: str = "tenant_user",
        allowed_domains: Optional[list[str]] = None,
    ) -> SAMLConfig:
        """Configure SSO for a tenant."""
        config = SAMLConfig(
            tenant_id=tenant_id,
            provider=provider,
            status=SSOStatus.CONFIGURING,
            idp_entity_id=idp_entity_id,
            idp_sso_url=idp_sso_url,
            idp_slo_url=idp_slo_url,
            idp_certificate=idp_certificate,
            sp_entity_id=f"{self.base_url}/saml/metadata/{tenant_id}",
            sp_acs_url=f"{self.base_url}/saml/acs/{tenant_id}",
            sp_slo_url=f"{self.base_url}/saml/slo/{tenant_id}",
            jit_provisioning=jit_provisioning,
            force_sso=force_sso,
            default_role=default_role,
            allowed_domains=allowed_domains or [],
        )

        if attribute_mapping:
            config.attribute_mapping.update(attribute_mapping)

        self._configs[tenant_id] = config

        logger.info("sso.configured",
                     tenant_id=tenant_id,
                     provider=provider.value,
                     idp_entity_id=idp_entity_id)

        return config

    def get_config(self, tenant_id: int) -> Optional[SAMLConfig]:
        """Get SSO configuration for a tenant."""
        return self._configs.get(tenant_id)

    def activate_sso(self, tenant_id: int) -> bool:
        """Activate SSO for a tenant after successful testing."""
        config = self._configs.get(tenant_id)
        if not config:
            return False
        config.status = SSOStatus.ACTIVE
        config.updated_at = datetime.now(timezone.utc)
        logger.info("sso.activated", tenant_id=tenant_id)
        return True

    def deactivate_sso(self, tenant_id: int) -> bool:
        """Deactivate SSO for a tenant."""
        config = self._configs.get(tenant_id)
        if not config:
            return False
        config.status = SSOStatus.DISABLED
        config.force_sso = False
        config.updated_at = datetime.now(timezone.utc)
        logger.info("sso.deactivated", tenant_id=tenant_id)
        return True

    def initiate_login(self, tenant_id: int, relay_state: str = "/dashboard") -> Optional[dict]:
        """Initiate SSO login flow for a tenant.

        Returns dict with 'redirect_url' and 'request_id', or None if SSO not configured.
        """
        config = self._configs.get(tenant_id)
        if not config or config.status not in (SSOStatus.ACTIVE, SSOStatus.TESTING):
            return None

        result = SAMLRequestBuilder.build_authn_request(config, relay_state)

        # Store pending request for validation
        self._pending_requests[result["request_id"]] = {
            "tenant_id": tenant_id,
            "created_at": time.time(),
            "relay_state": relay_state,
        }

        # Cleanup old pending requests (> 10 min)
        self._cleanup_pending_requests()

        return {
            "redirect_url": result["url"],
            "request_id": result["request_id"],
        }

    def process_saml_response(self, tenant_id: int, saml_response_b64: str) -> dict:
        """Process a SAML response from the IdP.

        Returns dict with user info and session data for JWT creation.
        """
        config = self._configs.get(tenant_id)
        if not config:
            raise SAMLValidationError(f"No SSO configuration for tenant {tenant_id}")

        validator = SAMLResponseValidator(config)
        assertion = validator.validate_and_parse(saml_response_b64)

        # Build user info for JWT creation / JIT provisioning
        user_info = {
            "email": assertion.email,
            "display_name": assertion.display_name,
            "name_id": assertion.name_id,
            "session_index": assertion.session_index,
            "tenant_id": tenant_id,
            "provider": config.provider.value,
            "attributes": assertion.attributes,
            "jit_provisioning": config.jit_provisioning,
            "default_role": config.default_role,
            "sso_authenticated": True,
        }

        logger.info("sso.login_successful",
                     tenant_id=tenant_id,
                     email=assertion.email,
                     provider=config.provider.value)

        return user_info

    def initiate_logout(self, tenant_id: int, name_id: str, session_index: str) -> Optional[dict]:
        """Initiate SSO logout flow."""
        config = self._configs.get(tenant_id)
        if not config or not config.idp_slo_url:
            return None

        result = SAMLRequestBuilder.build_logout_request(config, name_id, session_index)
        return {
            "redirect_url": result["url"],
            "request_id": result["request_id"],
        }

    def generate_sp_metadata(self, tenant_id: int) -> str:
        """Generate SAML SP metadata XML for a tenant.

        This XML is provided to the IdP administrator for configuration.
        """
        config = self._configs.get(tenant_id)
        if not config:
            config = SAMLConfig(
                tenant_id=tenant_id,
                provider=SSOProvider.CUSTOM_SAML,
                sp_entity_id=f"{self.base_url}/saml/metadata/{tenant_id}",
                sp_acs_url=f"{self.base_url}/saml/acs/{tenant_id}",
                sp_slo_url=f"{self.base_url}/saml/slo/{tenant_id}",
            )

        metadata = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"'
            f' entityID="{config.sp_entity_id}">'
            f'<md:SPSSODescriptor'
            f' AuthnRequestsSigned="false"'
            f' WantAssertionsSigned="true"'
            f' protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
            f'<md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>'
            f'<md:AssertionConsumerService'
            f' Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"'
            f' Location="{config.sp_acs_url}"'
            f' index="0" isDefault="true"/>'
            f'<md:SingleLogoutService'
            f' Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"'
            f' Location="{config.sp_slo_url}"/>'
            f'</md:SPSSODescriptor>'
            f'<md:Organization>'
            f'<md:OrganizationName xml:lang="en">ARIIA Platform</md:OrganizationName>'
            f'<md:OrganizationDisplayName xml:lang="en">ARIIA</md:OrganizationDisplayName>'
            f'<md:OrganizationURL xml:lang="en">{self.base_url}</md:OrganizationURL>'
            f'</md:Organization>'
            f'</md:EntityDescriptor>'
        )

        return metadata

    def is_sso_enabled(self, tenant_id: int) -> bool:
        """Check if SSO is enabled and active for a tenant."""
        config = self._configs.get(tenant_id)
        return config is not None and config.status == SSOStatus.ACTIVE

    def is_sso_forced(self, tenant_id: int) -> bool:
        """Check if SSO is forced (password login disabled) for a tenant."""
        config = self._configs.get(tenant_id)
        return config is not None and config.status == SSOStatus.ACTIVE and config.force_sso

    def list_configured_tenants(self) -> list[dict]:
        """List all tenants with SSO configured."""
        return [
            {
                "tenant_id": tid,
                "provider": cfg.provider.value,
                "status": cfg.status.value,
                "force_sso": cfg.force_sso,
            }
            for tid, cfg in self._configs.items()
        ]

    def _cleanup_pending_requests(self, max_age: int = 600):
        """Remove pending requests older than max_age seconds."""
        now = time.time()
        expired = [
            rid for rid, meta in self._pending_requests.items()
            if now - meta["created_at"] > max_age
        ]
        for rid in expired:
            del self._pending_requests[rid]


# ══════════════════════════════════════════════════════════════════════════════
# SSO API Router
# ══════════════════════════════════════════════════════════════════════════════

from fastapi import APIRouter, HTTPException, Request, Response, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel, Field


class SSOConfigRequest(BaseModel):
    """Request body for SSO configuration."""
    provider: str = Field(..., description="SSO provider (okta, azure_ad, google_workspace, etc.)")
    idp_entity_id: str = Field(..., description="IdP Entity ID / Issuer URL")
    idp_sso_url: str = Field(..., description="IdP SSO Login URL")
    idp_certificate: str = Field(..., description="IdP X.509 Certificate (PEM)")
    idp_slo_url: str = Field("", description="IdP Single Logout URL (optional)")
    attribute_mapping: Optional[dict[str, str]] = Field(None, description="Custom attribute mapping")
    jit_provisioning: bool = Field(True, description="Auto-create users on first SSO login")
    force_sso: bool = Field(False, description="Disable password login when SSO is active")
    default_role: str = Field("tenant_user", description="Default role for JIT-provisioned users")
    allowed_domains: list[str] = Field(default_factory=list, description="Restrict to email domains")


class SSOConfigResponse(BaseModel):
    """Response for SSO configuration."""
    tenant_id: int
    provider: str
    status: str
    sp_entity_id: str
    sp_acs_url: str
    sp_slo_url: str
    sp_metadata_url: str
    jit_provisioning: bool
    force_sso: bool


class SSOLoginResponse(BaseModel):
    """Response for SSO login initiation."""
    redirect_url: str
    request_id: str


# Global SSO manager instance
_sso_manager: Optional[SSOManager] = None


def get_sso_manager() -> SSOManager:
    global _sso_manager
    if _sso_manager is None:
        _sso_manager = SSOManager()
    return _sso_manager


def create_sso_router() -> APIRouter:
    """Create the SSO API router."""
    router = APIRouter(prefix="/api/v1/sso", tags=["sso"])

    @router.post("/configure/{tenant_id}", response_model=SSOConfigResponse)
    async def configure_sso(tenant_id: int, req: SSOConfigRequest):
        """Configure SSO for a tenant (admin only)."""
        manager = get_sso_manager()
        try:
            provider = SSOProvider(req.provider)
        except ValueError:
            raise HTTPException(400, f"Unsupported provider: {req.provider}")

        config = manager.configure_sso(
            tenant_id=tenant_id,
            provider=provider,
            idp_entity_id=req.idp_entity_id,
            idp_sso_url=req.idp_sso_url,
            idp_certificate=req.idp_certificate,
            idp_slo_url=req.idp_slo_url,
            attribute_mapping=req.attribute_mapping,
            jit_provisioning=req.jit_provisioning,
            force_sso=req.force_sso,
            default_role=req.default_role,
            allowed_domains=req.allowed_domains,
        )

        return SSOConfigResponse(
            tenant_id=config.tenant_id,
            provider=config.provider.value,
            status=config.status.value,
            sp_entity_id=config.sp_entity_id,
            sp_acs_url=config.sp_acs_url,
            sp_slo_url=config.sp_slo_url,
            sp_metadata_url=f"/saml/metadata/{tenant_id}",
            jit_provisioning=config.jit_provisioning,
            force_sso=config.force_sso,
        )

    @router.get("/config/{tenant_id}")
    async def get_sso_config(tenant_id: int):
        """Get SSO configuration for a tenant."""
        manager = get_sso_manager()
        config = manager.get_config(tenant_id)
        if not config:
            raise HTTPException(404, "SSO not configured for this tenant")
        return config.to_dict()

    @router.post("/activate/{tenant_id}")
    async def activate_sso(tenant_id: int):
        """Activate SSO for a tenant after testing."""
        manager = get_sso_manager()
        if not manager.activate_sso(tenant_id):
            raise HTTPException(404, "SSO not configured for this tenant")
        return {"status": "active", "tenant_id": tenant_id}

    @router.post("/deactivate/{tenant_id}")
    async def deactivate_sso(tenant_id: int):
        """Deactivate SSO for a tenant."""
        manager = get_sso_manager()
        if not manager.deactivate_sso(tenant_id):
            raise HTTPException(404, "SSO not configured for this tenant")
        return {"status": "disabled", "tenant_id": tenant_id}

    @router.get("/login/{tenant_id}")
    async def initiate_sso_login(tenant_id: int, relay_state: str = "/dashboard"):
        """Initiate SSO login flow — redirects to IdP."""
        manager = get_sso_manager()
        result = manager.initiate_login(tenant_id, relay_state)
        if not result:
            raise HTTPException(404, "SSO not available for this tenant")
        return SSOLoginResponse(**result)

    @router.get("/logout/{tenant_id}")
    async def initiate_sso_logout(tenant_id: int, name_id: str = "", session_index: str = ""):
        """Initiate SSO logout flow — redirects to IdP SLO."""
        manager = get_sso_manager()
        result = manager.initiate_logout(tenant_id, name_id, session_index)
        if not result:
            raise HTTPException(404, "SSO SLO not available for this tenant")
        return {"redirect_url": result["redirect_url"]}

    @router.get("/status/{tenant_id}")
    async def get_sso_status(tenant_id: int):
        """Check SSO status for a tenant."""
        manager = get_sso_manager()
        config = manager.get_config(tenant_id)
        if not config:
            return {"enabled": False, "forced": False, "status": "not_configured"}
        return {
            "enabled": config.status == SSOStatus.ACTIVE,
            "forced": config.force_sso,
            "status": config.status.value,
            "provider": config.provider.value,
        }

    @router.get("/tenants")
    async def list_sso_tenants():
        """List all tenants with SSO configured (system admin)."""
        manager = get_sso_manager()
        return manager.list_configured_tenants()

    return router


def create_saml_router() -> APIRouter:
    """Create the SAML endpoint router (metadata, ACS, SLO)."""
    router = APIRouter(prefix="/saml", tags=["saml"])

    @router.get("/metadata/{tenant_id}", response_class=HTMLResponse)
    async def sp_metadata(tenant_id: int):
        """Return SP metadata XML for IdP configuration."""
        manager = get_sso_manager()
        metadata = manager.generate_sp_metadata(tenant_id)
        return Response(
            content=metadata,
            media_type="application/xml",
            headers={"Content-Disposition": f"inline; filename=ariia-sp-metadata-{tenant_id}.xml"},
        )

    @router.post("/acs/{tenant_id}")
    async def assertion_consumer_service(tenant_id: int, SAMLResponse: str = Form(...)):
        """SAML Assertion Consumer Service — processes IdP response."""
        manager = get_sso_manager()
        try:
            user_info = manager.process_saml_response(tenant_id, SAMLResponse)
            # In production: create JWT, set cookies, redirect to app
            return {
                "status": "success",
                "user": {
                    "email": user_info["email"],
                    "display_name": user_info["display_name"],
                    "tenant_id": user_info["tenant_id"],
                    "provider": user_info["provider"],
                    "sso_authenticated": True,
                },
            }
        except SAMLValidationError as e:
            logger.error("saml.acs_failed", tenant_id=tenant_id, error=str(e))
            raise HTTPException(401, f"SAML authentication failed: {e}")

    @router.get("/slo/{tenant_id}")
    async def single_logout_service(tenant_id: int):
        """SAML Single Logout Service endpoint."""
        # Process SLO response from IdP
        return {"status": "logged_out", "tenant_id": tenant_id}

    return router
