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
        integration_context: str = "",
        tenant_id: int,
        studio_name: str = "",
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
            "email": "Erstelle einen E-Mail-Betreff (subject) und den Textinhalt (body) als strukturierten Fließtext mit Absätzen. KEIN HTML, KEIN <html>, KEIN <body> — der HTML-Designer übernimmt die Formatierung. Nur {{ contact.first_name }} als Jinja2-Platzhalter.",
            "whatsapp": "Erstelle eine kurze WhatsApp-Nachricht (max 1000 Zeichen). Emojis sparsam.",
            "telegram": "Erstelle eine Telegram-Nachricht. Markdown erlaubt.",
            "sms": "Erstelle eine SMS (max 160 Zeichen). Kurz und prägnant.",
        }
        channel_instruction = channel_instructions.get(channel, channel_instructions["email"])

        sender_name = studio_name or "Unser Team"
        context_parts = [f"Kampagne: {campaign_name}", f"Kanal: {channel}", f"Studio/Absender: {sender_name}"]
        if knowledge_context:
            context_parts.append(f"Wissensbasis:\n{knowledge_context}")
        else:
            context_parts.append("Wissensbasis: (leer – keine studiospezifischen Inhalte verfügbar)")
        if chat_context:
            context_parts.append(f"Aktuelle Mitglieder-Themen:\n{chat_context}")
        if integration_context:
            context_parts.append(integration_context)

        system_prompt = f"""Du bist ein Top-Texter für Fitness-E-Mail-Marketing mit 15 Jahren Erfahrung. Dein Ton ist {tone_desc}.
{channel_instruction}

KONTEXT:
{chr(10).join(context_parts)}

COPYWRITING-STRUKTUR (für E-Mail body):
1. HOOK (1 Satz): Packender Einstieg — Frage, überraschende Aussage oder konkreter Nutzen
2. PROBLEM/RELEVANZ (1–2 Sätze): Warum ist das Thema für den Leser wichtig?
3. LÖSUNG/ANGEBOT (2–4 Absätze): Konkrete Vorteile, was das Mitglied bekommt/erlebt. Nutze Aufzählungen wenn sinnvoll (max. 3–4 Punkte).
4. SOCIAL PROOF oder VERKNAPPUNG (optional, 1 Satz): Wenn möglich aus der Wissensbasis.
5. CTA (1 klarer Aufruf): Direkt, handlungsorientiert. Wenn keine echte URL → [BUCHUNGS-URL].
6. ABSCHLUSS: Kurz, warm, persönlich. Signiert mit "{sender_name}".

BETREFF-FORMELN (wähle die passendste):
- Neugier: "Hast du das schon gehört, {{{{ contact.first_name }}}}?"
- Nutzen: "[konkreter Vorteil] in [Zeitraum]"
- Direktheit: "[Handlung] + [Ergebnis]"
- Verknappung: "Nur noch [X] Plätze: [Angebot]"

REGELN:
1. IMMER "du/dein/dir" — niemals "Sie/Ihr/Ihnen". Kein Mischen.
2. Wissensbasis = Faktenquelle. Keine Dokumenttitel, Dateinamen oder Quellenangaben zitieren — alles in eigenen Worten umformulieren. Keine Preise/Fakten erfinden die nicht darin stehen.
3. Einziger Jinja2-Platzhalter: {{{{ contact.first_name }}}} — keine anderen contact.*-Variablen.
4. Absender "{sender_name}" nur als Klartext im Abschluss — nicht als Variable.
5. CTA-Link: Echte URL aus Wissensbasis verwenden, sonst [BUCHUNGS-URL] — keine erfundenen URLs oder E-Mails.
6. Zielgruppe: Fitnessstudio-Mitglieder (B2C), nicht Trainer — außer der Prompt sagt explizit B2B.
7. Kein HTML im body — der Designer übernimmt die Formatierung.
8. Antwort NUR als JSON: {{"subject": "...", "body": "...", "variables": {{"first_name": "Max"}}}}
9. Sprache: Deutsch — außer der Prompt verlangt explizit eine andere Sprache.
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
