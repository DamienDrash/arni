"""
ARIIA MFA/TOTP Service
======================
Handles TOTP setup, verification, and backup code management.
Uses pyotp for TOTP generation/verification.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import struct
import time
from typing import Optional

import structlog

logger = structlog.get_logger()

# ─── TOTP Implementation (no external dependency) ─────────────────────────

def _hotp(key: bytes, counter: int, digits: int = 6) -> str:
    """Generate HOTP value (RFC 4226)."""
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def _totp(key: bytes, period: int = 30, digits: int = 6) -> str:
    """Generate current TOTP value (RFC 6238)."""
    counter = int(time.time()) // period
    return _hotp(key, counter, digits)


def _base32_encode(data: bytes) -> str:
    """RFC 4648 base32 encoding."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    result = []
    buffer = 0
    bits = 0
    for byte in data:
        buffer = (buffer << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            result.append(alphabet[(buffer >> bits) & 0x1F])
    if bits > 0:
        result.append(alphabet[(buffer << (5 - bits)) & 0x1F])
    return "".join(result)


def _base32_decode(encoded: str) -> bytes:
    """RFC 4648 base32 decoding."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    encoded = encoded.upper().rstrip("=")
    result = []
    buffer = 0
    bits = 0
    for char in encoded:
        if char not in alphabet:
            continue
        buffer = (buffer << 5) | alphabet.index(char)
        bits += 5
        if bits >= 8:
            bits -= 8
            result.append((buffer >> bits) & 0xFF)
    return bytes(result)


# ─── Public API ────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    """Generate a new TOTP secret (base32 encoded, 160-bit)."""
    raw = secrets.token_bytes(20)
    return _base32_encode(raw)


def get_totp_uri(secret: str, email: str, issuer: str = "ARIIA") -> str:
    """Generate otpauth:// URI for QR code generation."""
    from urllib.parse import quote
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Verify a TOTP code with a time window tolerance.
    
    Args:
        secret: Base32-encoded TOTP secret
        code: 6-digit code to verify
        window: Number of time steps to check before/after current time
    
    Returns:
        True if code is valid
    """
    if not code or len(code) != 6 or not code.isdigit():
        return False
    
    try:
        key = _base32_decode(secret)
    except Exception:
        return False
    
    current_counter = int(time.time()) // 30
    
    for offset in range(-window, window + 1):
        expected = _hotp(key, current_counter + offset, 6)
        if hmac.compare_digest(expected, code):
            return True
    
    return False


def generate_backup_codes(count: int = 8) -> list[str]:
    """Generate a set of backup codes (8-character alphanumeric)."""
    codes = []
    for _ in range(count):
        # Format: XXXX-XXXX for readability
        raw = secrets.token_hex(4).upper()
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def hash_backup_codes(codes: list[str]) -> str:
    """Hash backup codes for secure storage. Returns JSON string of hashed codes."""
    hashed = []
    for code in codes:
        normalized = code.replace("-", "").upper()
        h = hashlib.sha256(normalized.encode()).hexdigest()
        hashed.append(h)
    return json.dumps(hashed)


def verify_backup_code(code: str, hashed_codes_json: str) -> tuple[bool, str]:
    """Verify a backup code and return updated hashed codes (with used code removed).
    
    Returns:
        (is_valid, updated_hashed_codes_json)
    """
    if not code or not hashed_codes_json:
        return False, hashed_codes_json or "[]"
    
    normalized = code.replace("-", "").replace(" ", "").upper()
    code_hash = hashlib.sha256(normalized.encode()).hexdigest()
    
    try:
        hashed_list = json.loads(hashed_codes_json)
    except (json.JSONDecodeError, TypeError):
        return False, hashed_codes_json or "[]"
    
    if code_hash in hashed_list:
        hashed_list.remove(code_hash)
        return True, json.dumps(hashed_list)
    
    return False, hashed_codes_json


def encrypt_secret(secret: str, encryption_key: str) -> str:
    """Simple XOR-based encryption for TOTP secret storage.
    
    In production, use AES-256-GCM or a proper KMS.
    For now, this provides basic at-rest protection.
    """
    key_bytes = hashlib.sha256(encryption_key.encode()).digest()
    secret_bytes = secret.encode()
    encrypted = bytes(a ^ b for a, b in zip(secret_bytes, key_bytes * (len(secret_bytes) // len(key_bytes) + 1)))
    return _base32_encode(encrypted)


def decrypt_secret(encrypted: str, encryption_key: str) -> str:
    """Decrypt a TOTP secret."""
    key_bytes = hashlib.sha256(encryption_key.encode()).digest()
    encrypted_bytes = _base32_decode(encrypted)
    decrypted = bytes(a ^ b for a, b in zip(encrypted_bytes, key_bytes * (len(encrypted_bytes) // len(key_bytes) + 1)))
    return decrypted.decode()
