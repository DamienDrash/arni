"""ARIIA AI Config – API Key Encryption Utility.

Uses Fernet symmetric encryption for API keys at rest.
The encryption key is derived from AUTH_SECRET via PBKDF2.
"""

import base64
import hashlib
import structlog
from cryptography.fernet import Fernet
from config.settings import get_settings

logger = structlog.get_logger()

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-init Fernet cipher from AUTH_SECRET."""
    global _fernet
    if _fernet is None:
        settings = get_settings()
        # Derive a 32-byte key from AUTH_SECRET using PBKDF2
        key_bytes = hashlib.pbkdf2_hmac(
            "sha256",
            settings.auth_secret.encode("utf-8"),
            b"ariia-ai-config-salt-v1",
            iterations=100_000,
        )
        fernet_key = base64.urlsafe_b64encode(key_bytes[:32])
        _fernet = Fernet(fernet_key)
    return _fernet


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt an API key for database storage."""
    if not plain_key:
        return ""
    try:
        return _get_fernet().encrypt(plain_key.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error("ai_config.encrypt_failed", error=str(e))
        raise ValueError("Failed to encrypt API key") from e


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key from database storage."""
    if not encrypted_key:
        return ""
    try:
        return _get_fernet().decrypt(encrypted_key.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error("ai_config.decrypt_failed", error=str(e))
        raise ValueError("Failed to decrypt API key") from e
