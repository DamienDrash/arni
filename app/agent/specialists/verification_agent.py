"""ARIIA v2.0 – VerificationAgent.

A specialized agent that validates the output of other agents against
a checklist before critical operations are executed.

Use cases:
- Before cancelling a membership: verify all conditions are met
- Before booking: verify slot availability and user consent
- Before data changes: verify data integrity

Architecture:
    SpecialistAgent → produces result → VerificationAgent → validates → passed/failed
"""
from __future__ import annotations

import json
import structlog
from dataclasses import dataclass, field
from typing import Any, Optional

from app.swarm.llm import LLMClient

logger = structlog.get_logger()


@dataclass
class VerificationResult:
    """Result of a verification check."""
    passed: bool
    issues: list[str] = field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0
    checklist_results: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "issues": self.issues,
            "summary": self.summary,
            "confidence": self.confidence,
            "checklist_results": self.checklist_results,
        }


# ─── Pre-built Checklists ────────────────────────────────────────────────────

CANCELLATION_CHECKLIST = [
    "Hat der Nutzer die Kündigung explizit bestätigt?",
    "Wurde die Kündigungsfrist korrekt berechnet und kommuniziert?",
    "Wurde das Vertragsende-Datum genannt?",
    "Wurden dem Nutzer Alternativen angeboten (Pause, Downgrade)?",
    "Enthält die Antwort keine falschen Versprechungen?",
]

BOOKING_CHECKLIST = [
    "Hat der Nutzer die Buchung explizit bestätigt?",
    "Sind Datum und Uhrzeit korrekt angegeben?",
    "Ist der Kurs-/Terminname korrekt?",
    "Gibt es Konflikte mit bestehenden Buchungen?",
    "Wurde der Nutzer über eventuelle Kosten informiert?",
]

DATA_CHANGE_CHECKLIST = [
    "Sind die zu ändernden Daten korrekt?",
    "Hat der Nutzer die Änderung bestätigt?",
    "Gibt es Sicherheitsbedenken bei dieser Änderung?",
    "Wurden die Auswirkungen der Änderung erklärt?",
]

DEFAULT_CHECKLIST = [
    "Ist die Antwort sachlich korrekt?",
    "Enthält die Antwort alle relevanten Informationen?",
    "Gibt es Sicherheitsbedenken?",
    "Ist die Antwort für den Nutzer verständlich?",
]

CHECKLISTS: dict[str, list[str]] = {
    "cancellation": CANCELLATION_CHECKLIST,
    "booking": BOOKING_CHECKLIST,
    "data_change": DATA_CHANGE_CHECKLIST,
    "default": DEFAULT_CHECKLIST,
}


VERIFICATION_SYSTEM_PROMPT = """Du bist der Verifikations-Agent von ARIIA.
Deine Aufgabe: Prüfe das Ergebnis eines anderen Agenten anhand einer Checkliste.

CHECKLISTE:
{checklist}

KONTEXT DER AKTION:
{action_context}

PRÜFE das folgende Ergebnis und antworte NUR mit einem JSON-Objekt:
{{
  "passed": true/false,
  "checklist_results": {{
    "Frage 1": true/false,
    "Frage 2": true/false
  }},
  "issues": ["Problem 1", "Problem 2"],
  "summary": "Zusammenfassung der Prüfung",
  "confidence": 0.0-1.0
}}

REGELN:
- Sei streng bei sicherheitskritischen Prüfpunkten.
- "passed" ist nur true, wenn ALLE kritischen Punkte erfüllt sind.
- Nenne konkrete Issues, wenn etwas nicht passt.
- Confidence = wie sicher du dir bei deinem Urteil bist."""


class VerificationAgent:
    """Agent that validates outputs of other agents against checklists."""

    def __init__(self, llm: LLMClient):
        self._llm = llm

    async def verify(
        self,
        result_to_verify: str,
        checklist_type: str = "default",
        custom_checklist: Optional[list[str]] = None,
        action_context: str = "",
    ) -> VerificationResult:
        """Verify a result against a checklist.

        Args:
            result_to_verify: The output text to verify
            checklist_type: One of "cancellation", "booking", "data_change", "default"
            custom_checklist: Optional custom checklist items (overrides type)
            action_context: Additional context about what action was performed

        Returns:
            VerificationResult with passed/failed status and details
        """
        checklist = custom_checklist or CHECKLISTS.get(
            checklist_type, DEFAULT_CHECKLIST
        )

        checklist_text = "\n".join(f"- {item}" for item in checklist)

        system_prompt = VERIFICATION_SYSTEM_PROMPT.format(
            checklist=checklist_text,
            action_context=action_context or "Keine zusätzlichen Kontextinformationen.",
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Zu prüfendes Ergebnis:\n\n{result_to_verify}"},
        ]

        try:
            response = await self._llm.chat(
                messages, temperature=0.1, max_tokens=1000
            )
            return self._parse_verification_response(response, checklist)

        except Exception as e:
            logger.error("verification.error", error=str(e))
            return VerificationResult(
                passed=False,
                issues=[f"Verifikation fehlgeschlagen: {str(e)}"],
                summary="Die Verifikation konnte nicht durchgeführt werden.",
                confidence=0.0,
            )

    def _parse_verification_response(
        self, response: str, checklist: list[str]
    ) -> VerificationResult:
        """Parse the LLM's verification response."""
        try:
            # Extract JSON from response
            text = response.strip()
            if "```json" in text:
                text = text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in text:
                text = text.split("```", 1)[1].split("```", 1)[0]

            data = json.loads(text.strip())

            return VerificationResult(
                passed=data.get("passed", False),
                issues=data.get("issues", []),
                summary=data.get("summary", ""),
                confidence=data.get("confidence", 0.5),
                checklist_results=data.get("checklist_results", {}),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(
                "verification.parse_error",
                error=str(e),
                response_preview=response[:200],
            )
            # Conservative fallback: fail the verification
            return VerificationResult(
                passed=False,
                issues=["Verifikations-Antwort konnte nicht geparst werden."],
                summary=response[:500],
                confidence=0.3,
            )

    async def verify_cancellation(
        self, result: str, context: str = ""
    ) -> VerificationResult:
        """Convenience method for cancellation verification."""
        return await self.verify(
            result, checklist_type="cancellation", action_context=context
        )

    async def verify_booking(
        self, result: str, context: str = ""
    ) -> VerificationResult:
        """Convenience method for booking verification."""
        return await self.verify(
            result, checklist_type="booking", action_context=context
        )

    async def verify_data_change(
        self, result: str, context: str = ""
    ) -> VerificationResult:
        """Convenience method for data change verification."""
        return await self.verify(
            result, checklist_type="data_change", action_context=context
        )
