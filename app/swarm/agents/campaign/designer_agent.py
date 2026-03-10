"""DesignerAgent: generates HTML email from template + marketing content."""
from __future__ import annotations
import structlog
from app.swarm.base import BaseAgent

logger = structlog.get_logger()


class DesignerAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "designer"

    @property
    def description(self) -> str:
        return "Designer Agent – Composes HTML email using tenant template and branding"

    async def handle(self, message):
        """Required by BaseAgent; not used in campaign context."""
        return None

    async def generate_html(
        self,
        *,
        template=None,  # CampaignTemplate | None
        subject: str,
        body: str,
        variables: dict,
        tenant_id: int,
        media_context: str = "",
    ) -> str:
        """Generate full HTML email. Uses template branding if available."""
        primary_color = "#6C5CE7"
        logo_url = None
        header_html = ""
        footer_html = ""
        body_template = ""

        if template:
            primary_color = template.primary_color or primary_color
            logo_url = template.logo_url
            header_html = template.header_html or ""
            footer_html = template.footer_html or ""
            body_template = template.body_template or ""

        logo_block = f'<img src="{logo_url}" alt="Logo" style="max-width:180px;height:auto;margin-bottom:12px;" />' if logo_url else ""

        system_prompt = f"""Du bist ein HTML-E-Mail-Designer. Erstelle ein responsives, modernes HTML-E-Mail-Template.

BRANDING:
- Primärfarbe: {primary_color}
- Logo: {"vorhanden (bereits eingebettet)" if logo_url else "keins"}

TEMPLATE-STRUKTUR:
Header: {header_html[:200] if header_html else "Standard-Header verwenden"}
Footer: {footer_html[:200] if footer_html else "Standard-Footer verwenden"}
Body-Template: {body_template[:300] if body_template else "Freies Layout"}

ANFORDERUNGEN:
1. Table-basiertes Layout (Outlook-kompatibel)
2. Max-Width 600px, responsive
3. Verwende die Primärfarbe {primary_color} für Überschriften und Buttons
4. Bette den Body-Inhalt vollständig ein
5. Gib NUR den vollständigen HTML-Code zurück, kein Erklärungstext
6. Füge {{{{ unsubscribe_url }}}} im Footer ein
"""

        if media_context:
            system_prompt += f"\n\nVERFÜGBARE BILDER FÜR DIESEN NEWSLETTER:\n{media_context}\nFüge das erste passende Bild als <img src=\"URL\" alt=\"beschreibung\" style=\"max-width:100%;height:auto;\"> in den HTML-Body an einer sinnvollen Stelle ein. Wenn kein Bild gut passt, lasse den img-Tag weg."

        user_prompt = f"""Betreff: {subject}

Inhalt:
{body}

{logo_block}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            html = await self._chat_with_messages(
                messages=messages,
                tenant_id=tenant_id,
            )
            if not html:
                raise ValueError("No response from LLM")
            # Strip markdown code blocks if present
            import re
            html = re.sub(r'^```html?\s*', '', html.strip())
            html = re.sub(r'\s*```$', '', html)
            return html
        except Exception as e:
            logger.error("designer_agent.generate_html_failed", error=str(e), tenant_id=tenant_id)
            # Fallback: minimal HTML wrapper
            return f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<title>{subject}</title></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
{body}
<p style="font-size:11px;color:#999;margin-top:40px;">
<a href="{{{{ unsubscribe_url }}}}">Abmelden</a>
</p></body></html>"""
