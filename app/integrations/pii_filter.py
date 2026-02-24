"""ARIIA v1.4 – PII Filter Middleware.

@SEC: Gold Standard Upgrade
Decoupled from persistence to prevent circular imports.
"""

import re
import structlog

logger = structlog.get_logger()

PATTERNS: dict[str, re.Pattern[str]] = {
    "phone_de": re.compile(r"(\+49|0049|0)\s?(\d{2,4})\s?(\d{3,8})\s?(\d{0,5})"),
    "phone_intl": re.compile(r"\+\d{1,3}\s?\d{3,14}"),
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "iban": re.compile(r"[A-Z]{2}\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{0,2}"),
    "credit_card": re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"),
    "date_of_birth": re.compile(r"\b\d{2}[./]\d{2}[./]\d{4}\b"),
}

class PIIFilter:
    def __init__(self, enabled: bool = True, patterns: dict[str, re.Pattern[str]] | None = None) -> None:
        self._enabled = enabled
        self._patterns = patterns or PATTERNS

    def contains_pii(self, text: str) -> bool:
        if not self._enabled:
            return False
        for name, pattern in self._patterns.items():
            if pattern.search(text):
                return True
        return False

    def mask(self, text: str) -> str:
        if not self._enabled:
            return text
            
        result = text

        def mask_phone(match: re.Match[str]) -> str:
            full = match.group(0)
            return full[:5] + "****" if len(full) > 5 else "****"

        result = self._patterns["phone_de"].sub(mask_phone, result)
        result = self._patterns["phone_intl"].sub(mask_phone, result)

        def mask_email(match: re.Match[str]) -> str:
            email = match.group(0)
            parts = email.split("@")
            if len(parts) == 2:
                local = parts[0][0] + "****" if parts[0] else "****"
                domain_parts = parts[1].rsplit(".", 1)
                domain = domain_parts[0][0] + "****" if domain_parts[0] else "****"
                tld = domain_parts[1] if len(domain_parts) > 1 else "com"
                return f"{local}@{domain}.{tld}"
            return "****@****.com"

        result = self._patterns["email"].sub(mask_email, result)

        def mask_iban(match: re.Match[str]) -> str:
            iban = match.group(0).replace(" ", "")
            return iban[:4] + "****" + iban[-4:] if len(iban) > 8 else "****"

        result = self._patterns["iban"].sub(mask_iban, result)

        def mask_cc(match: re.Match[str]) -> str:
            cc = match.group(0).replace(" ", "").replace("-", "")
            return cc[:4] + " **** **** " + cc[-4:] if len(cc) >= 8 else "****"

        result = self._patterns["credit_card"].sub(mask_cc, result)
        result = self._patterns["date_of_birth"].sub("**/**/**", result)

        return result
