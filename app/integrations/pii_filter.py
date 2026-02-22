"""ARIIA v1.4 – PII Filter Middleware.

@SEC: Sprint 3, Task 3.8
Regex-based PII detection and masking for log safety.
Applied to messages before logging, NOT to actual user content.
"""

import re

import structlog

logger = structlog.get_logger()


# ──────────────────────────────────────────
# PII Patterns (DSGVO_BASELINE compliant)
# ──────────────────────────────────────────

PATTERNS: dict[str, re.Pattern[str]] = {
    "phone_de": re.compile(
        r"(\+49|0049|0)\s?(\d{2,4})\s?(\d{3,8})\s?(\d{0,5})"
    ),
    "phone_intl": re.compile(
        r"\+\d{1,3}\s?\d{3,14}"
    ),
    "email": re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    ),
    "iban": re.compile(
        r"[A-Z]{2}\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{0,2}"
    ),
    "credit_card": re.compile(
        r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"
    ),
    "date_of_birth": re.compile(
        r"\b\d{2}[./]\d{2}[./]\d{4}\b"
    ),
}


class PIIFilter:
    """PII detection and masking middleware.

    Usage:
        pii = PIIFilter()
        safe_text = pii.mask(user_message)  # For logging only
        has_pii = pii.contains_pii(user_message)
    """

    def __init__(self, patterns: dict[str, re.Pattern[str]] | None = None) -> None:
        self._patterns = patterns or PATTERNS

    def contains_pii(self, text: str) -> bool:
        """Check if text contains any PII patterns.

        Args:
            text: Text to scan.

        Returns:
            True if PII detected.
        """
        for name, pattern in self._patterns.items():
            if pattern.search(text):
                logger.debug("pii.detected", pattern_name=name)
                return True
        return False

    def mask(self, text: str) -> str:
        """Mask all PII in text for safe logging.

        Replaces detected PII with masked versions:
        - Phone: +4917012345 → +49170****
        - Email: user@example.com → u****@e****.com
        - IBAN: DE89370400440532013000 → DE89****0130****
        - Credit Card: 4111 1111 1111 1111 → 4111 **** **** 1111

        Args:
            text: Text containing potential PII.

        Returns:
            Text with PII masked.
        """
        result = text

        # Phone numbers – keep first 5, mask rest
        def mask_phone(match: re.Match[str]) -> str:
            full = match.group(0)
            if len(full) > 5:
                return full[:5] + "****"
            return "****"

        result = self._patterns["phone_de"].sub(mask_phone, result)
        result = self._patterns["phone_intl"].sub(mask_phone, result)

        # Email – keep first char + domain TLD
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

        # IBAN – keep first 4 + last 4
        def mask_iban(match: re.Match[str]) -> str:
            iban = match.group(0).replace(" ", "")
            if len(iban) > 8:
                return iban[:4] + "****" + iban[-4:]
            return "****"

        result = self._patterns["iban"].sub(mask_iban, result)

        # Credit Card – keep first 4 + last 4
        def mask_cc(match: re.Match[str]) -> str:
            cc = match.group(0).replace(" ", "").replace("-", "")
            if len(cc) >= 8:
                return cc[:4] + " **** **** " + cc[-4:]
            return "****"

        result = self._patterns["credit_card"].sub(mask_cc, result)

        # Date of birth – full mask
        result = self._patterns["date_of_birth"].sub("**/**/**", result)

        return result

    def scan_and_report(self, text: str) -> dict[str, list[str]]:
        """Scan text and return all PII findings by category.

        Args:
            text: Text to scan.

        Returns:
            Dict of pattern_name → list of masked matches.
        """
        findings: dict[str, list[str]] = {}
        for name, pattern in self._patterns.items():
            matches = pattern.findall(text)
            if matches:
                # Return masked versions only
                masked = [self.mask(str(m)) for m in matches]
                findings[name] = masked
        return findings
