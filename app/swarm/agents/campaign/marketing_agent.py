"""MarketingAgent: generates campaign text content (subject, body, Jinja2 variables)."""
from __future__ import annotations
import json
import structlog
from app.swarm.base import BaseAgent

logger = structlog.get_logger()


class MarketingAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "marketing"

    @property
    def description(self) -> str:
        return "Marketing Agent – Generates campaign text content"

    async def handle(self, message):
        """Required by BaseAgent; not used in campaign context."""
        return None

    async def generate(
        self,
        *,
        campaign_name: str,
        channel: str,
        tone: str,
        prompt: str,
        knowledge_context: str = "",
        chat_context: str = "",
        tenant_id: int,
    ) -> dict:
        """Generate subject, body and Jinja2 variables for a campaign."""
        tone_map = {
            "professional": "professionell und seriös",
            "casual": "locker und freundlich",
            "motivational": "motivierend und energiegeladen",
            "urgent": "dringend und handlungsorientiert",
        }
        tone_desc = tone_map.get(tone, "professionell")

        channel_instructions = {
            "email": "Erstelle einen E-Mail-Betreff und HTML-Body. Verwende Jinja2-Variablen wie {{ contact.first_name }}.",
            "whatsapp": "Erstelle eine kurze WhatsApp-Nachricht (max 1000 Zeichen). Emojis sparsam.",
            "telegram": "Erstelle eine Telegram-Nachricht. Markdown erlaubt.",
            "sms": "Erstelle eine SMS (max 160 Zeichen). Kurz und prägnant.",
        }
        channel_instruction = channel_instructions.get(channel, channel_instructions["email"])

        context_parts = [f"Kampagne: {campaign_name}", f"Kanal: {channel}"]
        if knowledge_context:
            context_parts.append(f"Wissensbasis:\n{knowledge_context}")
        if chat_context:
            context_parts.append(f"Aktuelle Mitglieder-Themen:\n{chat_context}")

        system_prompt = f"""Du bist ein erfahrener Marketing-Experte und Content Creator für Fitnessstudios.
Dein Ton ist {tone_desc}.
{channel_instruction}

KONTEXT:
{chr(10).join(context_parts)}

REGELN:
1. Nutze die Wissensbasis als primäre Quelle für Fakten und Angebote.
2. Erfinde KEINE Fakten oder Preise die nicht in der Wissensbasis stehen.
3. Verwende Jinja2-Platzhalter: {{{{ contact.first_name }}}}, {{{{ contact.company }}}} etc.
4. Antworte NUR als JSON: {{"subject": "...", "body": "...", "variables": {{"first_name": "Max"}}}}
5. Schreibe auf Deutsch, außer der Prompt verlangt explizit eine andere Sprache.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._chat_with_messages(
                messages=messages,
                tenant_id=tenant_id,
            )

            if not response:
                return {"subject": "", "body": "", "variables": {}, "error": "No response from LLM"}

            import re

            def _extract_json(text: str) -> dict | None:
                """Try several strategies to extract a JSON object from LLM output."""
                # Strip markdown fences
                cleaned = re.sub(r'^```[a-z]*\n?', '', text.strip())
                cleaned = re.sub(r'\n?```$', '', cleaned).strip()
                # Direct parse
                try:
                    return json.loads(cleaned)
                except (json.JSONDecodeError, ValueError):
                    pass
                # Find first JSON object containing "subject"
                match = re.search(r'\{[^<>]*?"subject"[^<>]*?\}', cleaned, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except (json.JSONDecodeError, ValueError):
                        pass
                return None

            parsed = _extract_json(response)
            if not parsed:
                return {"subject": "", "body": response, "variables": {}}

            # If body is itself a JSON string (LLM nested the response), unwrap it
            body_raw = parsed.get("body", "")
            if isinstance(body_raw, str) and body_raw.strip().startswith("{"):
                inner = _extract_json(body_raw)
                if inner and (inner.get("subject") or inner.get("body")):
                    return {
                        "subject": inner.get("subject") or parsed.get("subject", ""),
                        "body": inner.get("body", ""),
                        "html": inner.get("html", ""),
                        "variables": inner.get("variables") or parsed.get("variables", {}),
                    }

            return parsed
        except Exception as e:
            logger.error("marketing_agent.generate_failed", error=str(e), tenant_id=tenant_id)
            return {"subject": "", "body": "", "variables": {}, "error": str(e)}
