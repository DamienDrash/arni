"""ARIIA v2.0 – Security subpackage."""

from app.core.security.vault import CredentialVault, get_vault

__all__ = ["CredentialVault", "get_vault"]
