"""QAAgent: validates campaign content against channel constraints and compliance rules."""
from __future__ import annotations
from dataclasses import dataclass, field
import re
import structlog

logger = structlog.get_logger()


@dataclass
class QAResult:
    passed: bool = True
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class QAAgent:
    """Rule-based content validator. No LLM calls for determinism."""

    def validate(
        self,
        *,
        channel: str,
        subject: str,
        body: str,
        html: str,
        tenant_id: int,
    ) -> QAResult:
        issues = []
        suggestions = []

        content = html or body

        # Channel-specific length checks
        if channel == "sms":
            if len(body) > 160:
                issues.append(f"SMS body is {len(body)} characters (max 160)")
        elif channel == "whatsapp":
            if len(body) > 1000:
                issues.append(f"WhatsApp body is {len(body)} characters (max 1000)")

        # Email-specific checks
        if channel == "email":
            if not subject:
                issues.append("Email subject is empty")
            # Check for unsubscribe link in HTML or body
            unsubscribe_patterns = ["unsubscribe_url", "unsubscribe", "abmelden", "abbestellen"]
            has_unsubscribe = any(p in content.lower() for p in unsubscribe_patterns)
            if not has_unsubscribe:
                issues.append("Email is missing an unsubscribe link (required by law)")

        # General checks
        if re.search(r'\bTODO\b|\bFIXME\b', content, re.IGNORECASE):
            issues.append("Content contains TODO or FIXME placeholder")

        # Unresolved double-brace syntax check (except known Jinja2 vars)
        known_vars = {"contact", "campaign", "first_name", "last_name", "studio_name",
                      "unsubscribe_url", "full_name", "email", "phone", "company"}
        unresolved = re.findall(r'\{\{\s*(\w+)', content)
        for var in unresolved:
            if var not in known_vars:
                suggestions.append(f"Unknown template variable: {{{{{var}}}}}")

        # Empty content check
        if not body and not html:
            issues.append("Campaign content is empty")

        passed = len(issues) == 0
        if issues:
            logger.warning("qa_agent.issues_found", issues=issues, channel=channel, tenant_id=tenant_id)
        else:
            logger.info("qa_agent.passed", channel=channel, tenant_id=tenant_id)

        return QAResult(passed=passed, issues=issues, suggestions=suggestions)
