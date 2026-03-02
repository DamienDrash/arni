"""ARIIA v2.0 – Credential Vault.

@ARCH: Contacts-Sync Refactoring
Secure encryption/decryption service for integration credentials.
Uses AES-256-GCM via the `cryptography` library (Fernet wrapper).

The encryption key is derived from the application's auth_secret
using PBKDF2-HMAC-SHA256 with a fixed salt. This ensures that
credentials are encrypted at rest in the database.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Dict, Optional

import structlog
from cryptography.fernet import Fernet, InvalidToken

logger = structlog.get_logger()

# Fixed salt for key derivation (change requires re-encryption of all credentials)
_VAULT_SALT = b"ariia-vault-v2-salt-2026"


def _derive_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from the application secret."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        _VAULT_SALT,
        iterations=100_000,
        dklen=32,
    )
    return base64.urlsafe_b64encode(dk)


class CredentialVault:
    """Encrypt and decrypt integration credentials.

    Usage:
        vault = CredentialVault(secret="my-app-secret")
        encrypted = vault.encrypt({"api_key": "sk-...", "base_url": "https://..."})
        decrypted = vault.decrypt(encrypted)
    """

    def __init__(self, secret: Optional[str] = None):
        if secret is None:
            from config.settings import get_settings
            secret = get_settings().auth_secret
        self._fernet = Fernet(_derive_key(secret))

    def encrypt(self, data: Dict[str, Any]) -> str:
        """Encrypt a dictionary of credentials to a base64 string."""
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
        return self._fernet.encrypt(plaintext).decode("utf-8")

    def decrypt(self, encrypted: str) -> Dict[str, Any]:
        """Decrypt a base64 string back to a dictionary."""
        if not encrypted:
            return {}
        try:
            plaintext = self._fernet.decrypt(encrypted.encode("utf-8"))
            return json.loads(plaintext.decode("utf-8"))
        except (InvalidToken, json.JSONDecodeError, Exception) as e:
            logger.error("vault.decrypt_failed", error=str(e))
            return {}

    def encrypt_field(self, value: str) -> str:
        """Encrypt a single string value."""
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_field(self, encrypted: str) -> str:
        """Decrypt a single string value."""
        if not encrypted:
            return ""
        try:
            return self._fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception) as e:
            logger.error("vault.decrypt_field_failed", error=str(e))
            return ""


# Singleton instance (lazy-initialized)
_vault_instance: Optional[CredentialVault] = None


def get_vault() -> CredentialVault:
    """Get or create the global CredentialVault instance."""
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = CredentialVault()
    return _vault_instance
