"""ARIIA v2.0 – Output Pipeline.

Every agent response passes through this pipeline before reaching the user.
The pipeline applies a series of filters and transformations:

1. PII Filter      – Detects and redacts personally identifiable information
2. Brand Voice     – Adjusts tone and style to match the tenant's brand
3. Toxicity Check  – Blocks harmful or inappropriate content
4. Confidence Gate – Triggers clarification if confidence is too low
5. Length Guard    – Ensures response isn't too long or too short

Architecture:
    AgentResponse → [PII] → [BrandVoice] → [Toxicity] → [Confidence] → [Length] → User
"""
from __future__ import annotations

import re
import structlog
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from app.swarm.base import AgentResponse

logger = structlog.get_logger()


# ─── Pipeline Stage Results ──────────────────────────────────────────────────

class PipelineAction(str, Enum):
    PASS = "pass"
    MODIFIED = "modified"
    BLOCKED = "blocked"
    NEEDS_CLARIFICATION = "needs_clarification"


@dataclass
class StageResult:
    """Result from a single pipeline stage."""
    action: PipelineAction
    content: str
    stage_name: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Final result after all pipeline stages."""
    content: str
    original_content: str
    action: PipelineAction
    stages: list[StageResult] = field(default_factory=list)
    pii_detected: bool = False
    pii_redacted_count: int = 0
    toxicity_blocked: bool = False
    confidence_gate_triggered: bool = False
    modifications: list[str] = field(default_factory=list)

    @property
    def was_modified(self) -> bool:
        return self.content != self.original_content

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "was_modified": self.was_modified,
            "pii_detected": self.pii_detected,
            "pii_redacted_count": self.pii_redacted_count,
            "toxicity_blocked": self.toxicity_blocked,
            "confidence_gate_triggered": self.confidence_gate_triggered,
            "modifications": self.modifications,
            "stages": [
                {"name": s.stage_name, "action": s.action.value}
                for s in self.stages
            ],
        }


# ─── PII Patterns ────────────────────────────────────────────────────────────

PII_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # German IBAN
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{0,2}\b"), "[IBAN-REDACTED]"),
    # Credit card numbers
    ("Kreditkarte", re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[KARTE-REDACTED]"),
    # German social security number (Sozialversicherungsnummer)
    ("SVN", re.compile(r"\b\d{2}\s?\d{6}\s?[A-Z]\s?\d{3}\b"), "[SVN-REDACTED]"),
    # Email addresses (only redact in outgoing responses, not when discussing)
    ("E-Mail", re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"), "[EMAIL-REDACTED]"),
    # German phone numbers
    ("Telefon", re.compile(r"\b(?:\+49|0049|0)\s?[\d\s/\-]{8,15}\b"), "[TEL-REDACTED]"),
    # German tax ID (Steuer-ID)
    ("Steuer-ID", re.compile(r"\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\b"), "[STEUERID-REDACTED]"),
    # Passport numbers
    ("Reisepass", re.compile(r"\b[CFGHJKLMNPRTVWXYZ]\d{8}\b"), "[PASS-REDACTED]"),
]

# ─── Toxicity Patterns ───────────────────────────────────────────────────────

TOXICITY_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(fick|scheiß|arschloch|hurensohn|wichser|missgeburt)\w*\b", re.IGNORECASE),
    re.compile(r"\b(kill\s+yourself|suicide\s+instructions|how\s+to\s+die)\b", re.IGNORECASE),
    re.compile(r"\b(bomb\s+making|weapon\s+instructions|drug\s+synthesis)\b", re.IGNORECASE),
]

TOXICITY_BLOCK_MESSAGE = (
    "Ich kann diese Anfrage leider nicht beantworten, da sie gegen unsere "
    "Nutzungsrichtlinien verstößt. Bitte formulieren Sie Ihr Anliegen neu."
)

# ─── Configuration ───────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 0.6
MIN_RESPONSE_LENGTH = 10
MAX_RESPONSE_LENGTH = 4000


@dataclass
class PipelineConfig:
    """Configuration for the output pipeline."""
    pii_filter_enabled: bool = True
    pii_redact_emails: bool = False  # Often emails are needed in context
    brand_voice_enabled: bool = True
    brand_voice_style: str = "professional"  # professional, casual, formal
    brand_voice_language: str = "de"
    toxicity_check_enabled: bool = True
    confidence_gate_enabled: bool = True
    confidence_threshold: float = CONFIDENCE_THRESHOLD
    length_guard_enabled: bool = True
    max_length: int = MAX_RESPONSE_LENGTH
    min_length: int = MIN_RESPONSE_LENGTH


class OutputPipeline:
    """Pipeline that processes every agent response before delivery.

    Each stage can:
    - PASS: Content unchanged
    - MODIFY: Content was altered (e.g., PII redacted)
    - BLOCK: Content is blocked entirely (e.g., toxicity)
    - NEEDS_CLARIFICATION: Confidence too low, ask user
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self._config = config or PipelineConfig()

    async def process(
        self,
        response: AgentResponse,
        tenant_config: Optional[dict[str, Any]] = None,
    ) -> PipelineResult:
        """Run the response through all pipeline stages.

        Args:
            response: The agent's response to process
            tenant_config: Optional tenant-specific configuration overrides

        Returns:
            PipelineResult with the processed content and metadata
        """
        content = response.content
        result = PipelineResult(
            content=content,
            original_content=content,
            action=PipelineAction.PASS,
        )

        # Apply tenant config overrides
        config = self._apply_tenant_config(tenant_config)

        # Stage 1: PII Filter
        if config.pii_filter_enabled:
            stage = self._apply_pii_filter(content, config)
            result.stages.append(stage)
            if stage.action == PipelineAction.MODIFIED:
                content = stage.content
                result.pii_detected = True
                result.pii_redacted_count = stage.details.get("redacted_count", 0)
                result.modifications.append("PII redacted")
                result.action = PipelineAction.MODIFIED

        # Stage 2: Toxicity Check
        if config.toxicity_check_enabled:
            stage = self._apply_toxicity_check(content)
            result.stages.append(stage)
            if stage.action == PipelineAction.BLOCKED:
                result.content = stage.content
                result.toxicity_blocked = True
                result.action = PipelineAction.BLOCKED
                logger.warning(
                    "output_pipeline.toxicity_blocked",
                    original_length=len(response.content),
                )
                return result

        # Stage 3: Confidence Gate
        if config.confidence_gate_enabled:
            stage = self._apply_confidence_gate(
                content, response.confidence, config.confidence_threshold
            )
            result.stages.append(stage)
            if stage.action == PipelineAction.NEEDS_CLARIFICATION:
                result.confidence_gate_triggered = True
                result.action = PipelineAction.NEEDS_CLARIFICATION
                content = stage.content

        # Stage 4: Brand Voice
        if config.brand_voice_enabled:
            stage = self._apply_brand_voice(content, config)
            result.stages.append(stage)
            if stage.action == PipelineAction.MODIFIED:
                content = stage.content
                result.modifications.append("Brand voice adjusted")
                if result.action == PipelineAction.PASS:
                    result.action = PipelineAction.MODIFIED

        # Stage 5: Length Guard
        if config.length_guard_enabled:
            stage = self._apply_length_guard(content, config)
            result.stages.append(stage)
            if stage.action == PipelineAction.MODIFIED:
                content = stage.content
                result.modifications.append("Length adjusted")
                if result.action == PipelineAction.PASS:
                    result.action = PipelineAction.MODIFIED

        result.content = content

        logger.info(
            "output_pipeline.processed",
            action=result.action.value,
            was_modified=result.was_modified,
            pii_redacted=result.pii_redacted_count,
            stages_count=len(result.stages),
        )

        return result

    # ─── Stage Implementations ────────────────────────────────────────────

    def _apply_pii_filter(self, content: str, config: PipelineConfig) -> StageResult:
        """Detect and redact PII from the response."""
        modified = content
        redacted_count = 0
        redacted_types: list[str] = []

        for pii_type, pattern, replacement in PII_PATTERNS:
            # Skip email redaction if configured
            if pii_type == "E-Mail" and not config.pii_redact_emails:
                continue

            matches = pattern.findall(modified)
            if matches:
                modified = pattern.sub(replacement, modified)
                redacted_count += len(matches)
                redacted_types.append(pii_type)

        if redacted_count > 0:
            logger.info(
                "output_pipeline.pii_redacted",
                count=redacted_count,
                types=redacted_types,
            )
            return StageResult(
                action=PipelineAction.MODIFIED,
                content=modified,
                stage_name="pii_filter",
                details={
                    "redacted_count": redacted_count,
                    "redacted_types": redacted_types,
                },
            )

        return StageResult(
            action=PipelineAction.PASS,
            content=content,
            stage_name="pii_filter",
        )

    def _apply_toxicity_check(self, content: str) -> StageResult:
        """Check for toxic or harmful content."""
        for pattern in TOXICITY_PATTERNS:
            if pattern.search(content):
                return StageResult(
                    action=PipelineAction.BLOCKED,
                    content=TOXICITY_BLOCK_MESSAGE,
                    stage_name="toxicity_check",
                    details={"pattern_matched": True},
                )

        return StageResult(
            action=PipelineAction.PASS,
            content=content,
            stage_name="toxicity_check",
        )

    def _apply_confidence_gate(
        self, content: str, confidence: float, threshold: float
    ) -> StageResult:
        """Check if confidence is above threshold."""
        if confidence < threshold:
            # Prepend a disclaimer
            disclaimer = (
                "⚠️ *Hinweis: Ich bin mir bei dieser Antwort nicht vollständig sicher. "
                "Bitte überprüfen Sie die Informationen oder stellen Sie eine "
                "präzisere Frage.*\n\n"
            )
            return StageResult(
                action=PipelineAction.NEEDS_CLARIFICATION,
                content=disclaimer + content,
                stage_name="confidence_gate",
                details={"confidence": confidence, "threshold": threshold},
            )

        return StageResult(
            action=PipelineAction.PASS,
            content=content,
            stage_name="confidence_gate",
            details={"confidence": confidence},
        )

    def _apply_brand_voice(
        self, content: str, config: PipelineConfig
    ) -> StageResult:
        """Apply brand voice adjustments.

        Note: Full brand voice transformation would use LLM.
        This is a lightweight rule-based version for performance.
        """
        modified = content

        # Ensure proper greeting style
        if config.brand_voice_style == "formal":
            modified = modified.replace("Hey!", "Guten Tag!")
            modified = modified.replace("Hi!", "Guten Tag!")
            modified = modified.replace("Hallo!", "Guten Tag!")
        elif config.brand_voice_style == "casual":
            modified = modified.replace("Sehr geehrte", "Liebe")
            modified = modified.replace("Sehr geehrter", "Lieber")

        # Ensure language-appropriate closing
        if config.brand_voice_language == "de" and modified.strip():
            # Remove English closings in German context
            for eng_closing in ["Best regards", "Kind regards", "Sincerely"]:
                if eng_closing in modified:
                    modified = modified.replace(eng_closing, "Mit freundlichen Grüßen")

        if modified != content:
            return StageResult(
                action=PipelineAction.MODIFIED,
                content=modified,
                stage_name="brand_voice",
                details={"style": config.brand_voice_style},
            )

        return StageResult(
            action=PipelineAction.PASS,
            content=content,
            stage_name="brand_voice",
        )

    def _apply_length_guard(
        self, content: str, config: PipelineConfig
    ) -> StageResult:
        """Ensure response length is within bounds."""
        if len(content) > config.max_length:
            # Truncate at last sentence boundary
            truncated = content[:config.max_length]
            last_period = truncated.rfind(".")
            last_excl = truncated.rfind("!")
            last_quest = truncated.rfind("?")
            cut_point = max(last_period, last_excl, last_quest)
            if cut_point > config.max_length // 2:
                truncated = truncated[:cut_point + 1]
            truncated += "\n\n*[Antwort gekürzt – bitte stellen Sie eine spezifischere Frage für weitere Details.]*"

            return StageResult(
                action=PipelineAction.MODIFIED,
                content=truncated,
                stage_name="length_guard",
                details={
                    "original_length": len(content),
                    "truncated_length": len(truncated),
                },
            )

        if len(content.strip()) < config.min_length:
            return StageResult(
                action=PipelineAction.MODIFIED,
                content=content + "\n\nKann ich Ihnen noch bei etwas anderem helfen?",
                stage_name="length_guard",
                details={"original_length": len(content), "padded": True},
            )

        return StageResult(
            action=PipelineAction.PASS,
            content=content,
            stage_name="length_guard",
        )

    # ─── Configuration ────────────────────────────────────────────────────

    def _apply_tenant_config(
        self, tenant_config: Optional[dict[str, Any]]
    ) -> PipelineConfig:
        """Create a config with tenant-specific overrides."""
        if not tenant_config:
            return self._config

        config = PipelineConfig(
            pii_filter_enabled=tenant_config.get(
                "pii_filter_enabled", self._config.pii_filter_enabled
            ),
            pii_redact_emails=tenant_config.get(
                "pii_redact_emails", self._config.pii_redact_emails
            ),
            brand_voice_enabled=tenant_config.get(
                "brand_voice_enabled", self._config.brand_voice_enabled
            ),
            brand_voice_style=tenant_config.get(
                "brand_voice_style", self._config.brand_voice_style
            ),
            brand_voice_language=tenant_config.get(
                "brand_voice_language", self._config.brand_voice_language
            ),
            toxicity_check_enabled=tenant_config.get(
                "toxicity_check_enabled", self._config.toxicity_check_enabled
            ),
            confidence_gate_enabled=tenant_config.get(
                "confidence_gate_enabled", self._config.confidence_gate_enabled
            ),
            confidence_threshold=tenant_config.get(
                "confidence_threshold", self._config.confidence_threshold
            ),
            length_guard_enabled=tenant_config.get(
                "length_guard_enabled", self._config.length_guard_enabled
            ),
            max_length=tenant_config.get(
                "max_length", self._config.max_length
            ),
            min_length=tenant_config.get(
                "min_length", self._config.min_length
            ),
        )
        return config

    def update_config(self, **kwargs) -> None:
        """Update pipeline configuration."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
