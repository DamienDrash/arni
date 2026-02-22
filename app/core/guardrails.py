
import re
import yaml
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

class GuardrailsService:
    """Deterministic Safety Layer (The Iron Dome).
    
    Checks inputs against defined rules in `config/guardrails.yaml`.
    This runs BEFORE any LLM call to save costs and ensure safety.
    """
    
    _instance: Optional["GuardrailsService"] = None

    def __init__(self):
        self.config = self._load_config()
        self.enabled = self.config.get("enabled", True)
        self.block_msg = self.config.get("block_response", "I cannot answer that.")
        
        # Compile Regexes once
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.config.get("patterns", [])]
        self.phrases = [p.lower() for p in self.config.get("blocked_phrases", [])]
        
    def _load_config(self) -> dict:
        try:
            path = Path(__file__).parents[2] / "config" / "guardrails.yaml"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("guardrails.config_load_failed", error=str(e))
        return {}

    @classmethod
    def get_instance(cls) -> "GuardrailsService":
        if cls._instance is None:
            cls._instance = GuardrailsService()
        return cls._instance

    def check(self, text: str) -> Optional[str]:
        """Returns blocking message if violation found, else None."""
        if not self.enabled or not text:
            return None
            
        lowered = text.lower()
        
        # 1. Check Blocked Phrases
        for phrase in self.phrases:
            if phrase in lowered:
                logger.warning("guardrails.violation", type="phrase", match=phrase)
                return self.block_msg
                
        # 2. Check Regex Patterns (PII)
        for pattern in self.patterns:
            if pattern.search(text):
                logger.warning("guardrails.violation", type="pattern_pii")
                return "Entschuldigung, bitte sende keine sensiblen Daten wie IBAN oder Kreditkartennummern."
                
        return None

def get_guardrails() -> GuardrailsService:
    return GuardrailsService.get_instance()
