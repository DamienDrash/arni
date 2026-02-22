"""ARIIA v1.4 – Security Utilities.

@BACKEND: Phase 2 – Encryption for Sensitive Settings (BYOK)
Provides symmetric encryption using Fernet.
"""

import base64
import hashlib
import structlog
from cryptography.fernet import Fernet
from config.settings import get_settings

logger = structlog.get_logger()

# Internal Prefix to identify encrypted values in the database
ENCRYPTION_PREFIX = "ENC:"

_fernet_instance = None

def _get_fernet() -> Fernet:
    """Initialize Fernet instance lazily using AUTH_SECRET."""
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance
    
    settings = get_settings()
    # Deriving a 32-byte key from AUTH_SECRET
    # AUTH_SECRET should be a long random string.
    secret = settings.auth_secret or "insecure-fallback-secret-for-dev-only"
    
    # Use SHA256 to ensure we have exactly 32 bytes, then base64 encode
    key_bytes = hashlib.sha256(secret.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    
    _fernet_instance = Fernet(fernet_key)
    return _fernet_instance

def encrypt_value(plain_text: str) -> str:
    """Encrypt a string and return it with the ENC: prefix."""
    if not plain_text:
        return plain_text
    
    if plain_text.startswith(ENCRYPTION_PREFIX):
        return plain_text # Already encrypted
    
    try:
        f = _get_fernet()
        token = f.encrypt(plain_text.encode()).decode()
        return f"{ENCRYPTION_PREFIX}{token}"
    except Exception as e:
        logger.error("crypto.encryption_failed", error=str(e))
        return plain_text

def decrypt_value(encrypted_text: str) -> str:
    """Decrypt a string if it has the ENC: prefix."""
    if not encrypted_text or not encrypted_text.startswith(ENCRYPTION_PREFIX):
        return encrypted_text
    
    try:
        f = _get_fernet()
        token = encrypted_text[len(ENCRYPTION_PREFIX):]
        return f.decrypt(token.encode()).decode()
    except Exception as e:
        logger.error("crypto.decryption_failed", error=str(e))
        # If decryption fails, we might have an old key or invalid format.
        # Return original but log critical.
        return encrypted_text
