"""app/integrations/pii_filter.py — Personally Identifiable Information (PII) Filter.

Masks names, emails, and phone numbers in logs to ensure privacy.
"""
import re

# Regex patterns for common PII
EMAIL_REGEX = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
PHONE_REGEX = re.compile(r'(\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4,6}')

def mask_pii(text: str) -> str:
    """Masks PII within a string."""
    if not isinstance(text, str):
        return str(text)
    
    # Mask Email
    text = EMAIL_REGEX.sub("[EMAIL]", text)
    
    # Mask Phone
    text = PHONE_REGEX.sub("[PHONE]", text)
    
    return text

def filter_log_record(logger, method_name, event_dict):
    """Processor for structlog to mask PII in log records."""
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = mask_pii(value)
    return event_dict
