"""DesignerAgent: generates gold-standard HTML email newsletters.

Strategy: Build the table-based skeleton in Python, inject template CSS and
content from the LLM, so the LLM only needs to produce the inner body HTML
(tiles, paragraphs, CTA) — not the full boilerplate. This prevents token
overflow with small models (gpt-4o-mini) and guarantees correct structure.
"""
from __future__ import annotations
import re
import structlog
from app.swarm.base import BaseAgent

logger = structlog.get_logger()


class DesignerAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "designer"

    @property
    def description(self) -> str:
        return "Designer Agent – Assembles professional HTML newsletter from template + LLM-generated body sections"

    async def handle(self, message):
        return None

    async def generate_html(
        self,
        *,
        template=None,
        subject: str,
        body: str,
        variables: dict,
        tenant_id: int,
        media_context: str = "",
        studio_name: str = "",
    ) -> str:
        """Generate a gold-standard HTML newsletter email.

        Architecture:
        1. LLM generates ONLY the inner body HTML (sections, tiles, CTA)
        2. Python assembles the full table-based newsletter skeleton
        3. Template CSS, logo, hero image, and footer are injected by Python

        This keeps LLM output small and focused, avoids token overflow,
        and guarantees correct Outlook-compatible table structure.
        """
        # ── Template Branding ─────────────────────────────────────────
        primary_color = "#4A90E2"

        if template:
            primary_color = template.primary_color or primary_color

        # ── Hero Image ────────────────────────────────────────────────
        hero_url = ""
        hero_alt = "Newsletter Bild"
        if media_context:
            url_match = re.search(r'https?://\S+', media_context)
            if url_match:
                hero_url = url_match.group().rstrip(".,;)")
            desc_match = re.match(r'-\s*([^:(]+?)(?:\s*\(Tags:|\s*:)', media_context.split('\n')[0])
            if desc_match:
                hero_alt = desc_match.group(1).strip()

        # ── Step 1: LLM generates ONLY the inner body sections ────────
        inner_body_html = await self._generate_body_sections(
            subject=subject,
            body=body,
            primary_color=primary_color,
            tenant_id=tenant_id,
            studio_name=studio_name,
        )

        # ── Step 2: Prepend hero image if provided ────────────────────
        if hero_url:
            hero_block = (
                f'<div style="margin:-40px -32px 32px -32px;line-height:0;">'
                f'<img src="{hero_url}" alt="{hero_alt}" width="600" '
                f'style="display:block;width:100%;max-width:600px;height:240px;'
                f'object-fit:cover;border:0;outline:none;" /></div>'
            )
            inner_body_html = hero_block + inner_body_html

        # ── Step 3: Lock inline colors against dark-mode overrides ────
        return self._force_colors_important(inner_body_html)

    async def _generate_body_sections(
        self,
        *,
        subject: str,
        body: str,
        primary_color: str,
        tenant_id: int,
        studio_name: str = "",
    ) -> str:
        """Ask LLM to generate ONLY the inner body HTML — no skeleton, no CSS."""

        team_name = studio_name or "Unser Team"
        system_prompt = f"""Du bist ein E-Mail-Content-Designer. Erstelle NUR den inneren HTML-Body für einen Newsletter.

DEINE AUFGABE: Wandle den Textinhalt in strukturierte HTML-Kacheln um.

FARBEN: Primärfarbe {primary_color} | Text: #f0f0f0 (auf dunklem Hintergrund #111111)

AUSGABE-FORMAT (NUR dieser HTML-Block, KEIN DOCTYPE, KEIN <html>, KEIN <head>, KEIN <body>):

<!-- Begrüßung -->
<h1 style="color:{primary_color};font-family:'Funnel Sans',Arial,sans-serif;margin:0 0 20px 0;font-size:24px;">Hallo {{{{ contact.first_name }}}},</h1>

<!-- Intro -->
<p style="color:#f0f0f0;font-family:'Funnel Sans',Arial,sans-serif;font-size:16px;line-height:1.7;margin:0 0 24px 0;">
  [Intro-Text aus dem Inhalt]
</p>

<!-- Für jede inhaltliche Sektion eine Kachel: -->
<table width="100%" cellpadding="16" cellspacing="0" border="0" style="background-color:#1a1a1a;border-radius:8px;margin-bottom:16px;border-left:3px solid {primary_color};">
  <tr>
    <td>
      <strong style="color:{primary_color};font-family:'Funnel Sans',Arial,sans-serif;font-size:15px;display:block;margin-bottom:8px;">[Kachel-Titel]</strong>
      <span style="color:#f0f0f0;font-family:'Funnel Sans',Arial,sans-serif;font-size:14px;line-height:1.6;">[Kachel-Inhalt]</span>
    </td>
  </tr>
</table>

<!-- CTA Button -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:32px;margin-bottom:24px;">
  <tr>
    <td align="center">
      <a href="[URL aus dem Text]" class="am-btn"
         style="display:inline-block;background-color:{primary_color};color:#ffffff;font-family:'Funnel Sans',Arial,sans-serif;font-size:16px;font-weight:600;text-decoration:none;padding:16px 40px;border-radius:6px;">
        [CTA-Text]
      </a>
    </td>
  </tr>
</table>

<!-- Abschluss -->
<p style="color:#f0f0f0;font-family:'Funnel Sans',Arial,sans-serif;font-size:15px;line-height:1.6;margin-top:24px;">
  Mit freundlichen Grüßen,<br>
  <strong style="color:{primary_color};">Dein {team_name}</strong>
</p>

REGELN:
- Baue 2-4 Kacheln aus den verschiedenen Inhaltsbereichen
- CTA-Button: Wenn eine echte URL im Text vorhanden ist, verwende sie. Wenn keine URL vorhanden ist, lasse den CTA-Block weg (kein # als href)
- {{{{ contact.first_name }}}} und {{{{ unsubscribe_url }}}} korrekt als Jinja2-Variablen
- Füge am Ende einen kleinen Abmelden-Link ein: <a href="{{{{ unsubscribe_url }}}}" style="color:#999;font-size:11px;">Abmelden</a>
- NUR HTML zurückgeben, KEIN Erklärungstext
"""

        # Strip HTML document wrapper if MarketingAgent returned full HTML instead of plain text
        clean_body = re.sub(r'<html[^>]*>|</html>|<head[^>]*>.*?</head>|<body[^>]*>|</body>', '', body, flags=re.DOTALL | re.IGNORECASE).strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Betreff: {subject}\n\nInhalt:\n{clean_body}"},
        ]

        try:
            # 2048 tokens ≈ 1500 words — sufficient for 4 tiles + greeting + CTA
            html = await self._chat_with_messages(
                messages=messages, tenant_id=tenant_id, max_tokens=2048
            )
            if not html:
                raise ValueError("No response from LLM")
            # Strip markdown fences
            html = re.sub(r'^```html?\s*', '', html.strip())
            html = re.sub(r'\s*```$', '', html)
            # Truncation guard: if the response was cut mid-element, close open tags
            html = self._repair_truncated_html(html)
            return html
        except Exception as e:
            logger.error("designer_agent.body_generation_failed", error=str(e), tenant_id=tenant_id)
            # Fallback: strip any HTML document wrapper before embedding raw body
            safe_body = re.sub(r'<html[^>]*>|</html>|<head[^>]*>.*?</head>|<body[^>]*>|</body>', '', body, flags=re.DOTALL | re.IGNORECASE).strip()
            return f"""<h1 style="color:{primary_color};">Hallo {{{{ contact.first_name }}}},</h1>
<p style="color:#f0f0f0;">{safe_body}</p>
<p style="margin-top:40px;color:#f0f0f0;font-size:15px;">
  Mit freundlichen Grüßen,<br>
  <strong style="color:{primary_color};">{team_name}</strong>
</p>
<p style="margin-top:24px;font-size:11px;">
  <a href="{{{{ unsubscribe_url }}}}" style="color:#999;">Abmelden</a>
</p>"""

    @staticmethod
    def _repair_truncated_html(html: str) -> str:
        """Close any block-level tags left open by a truncated LLM response.

        Handles the most common truncation points in newsletter bodies:
        <span>, <td>, <tr>, <table>, <p>, <a>.
        Does nothing if the HTML is already well-formed.
        """
        # Tags that, if opened, must be closed in reverse order
        CLOSEABLE = ["span", "strong", "a", "p", "td", "tr", "table"]
        stack = []
        tag_re = re.compile(r'<(/?)(\w+)[^>]*?(/?)>', re.IGNORECASE)
        for m in tag_re.finditer(html):
            is_closing, tag, self_closing = m.group(1), m.group(2).lower(), m.group(3)
            if self_closing or tag in {"br", "hr", "img", "meta", "link", "input"}:
                continue
            if is_closing:
                if stack and stack[-1] == tag:
                    stack.pop()
            else:
                if tag in CLOSEABLE:
                    stack.append(tag)
        # Append missing closing tags in reverse
        for tag in reversed(stack):
            html += f"</{tag}>"
            logger.warning("designer_agent.truncation_repaired", closed_tag=tag)
        return html

    @staticmethod
    def _force_colors_important(html: str) -> str:
        """Add !important to every inline color and background-color declaration.

        Dark-mode email clients (Gmail Android, Apple Mail, Samsung Mail) override
        inline styles that lack !important. This is the single most effective
        technique to lock colors regardless of the viewer's display mode.

        Skips declarations already carrying !important and skips content inside
        <style> blocks (those are handled separately via @media queries).
        """
        # Properties whose inline values must be locked
        LOCK_PROPS = re.compile(
            r'(?<![a-z-])((?:background-)?color|background)\s*:\s*([^;!"]+?)\s*(?:!important)?\s*(?=;|")',
            re.IGNORECASE,
        )

        def _process_style_attr(m: re.Match) -> str:
            """Add !important to every color/background inside one style="..." attr."""
            style_value = m.group(1)

            def _lock(pm: re.Match) -> str:
                return f"{pm.group(1)}: {pm.group(2).strip()} !important"

            locked = LOCK_PROPS.sub(_lock, style_value)
            return f'style="{locked}"'

        # Process only style="..." attributes, not <style> blocks
        # Split around <style>...</style> to leave CSS blocks untouched
        parts = re.split(r'(<style[^>]*>.*?</style>)', html, flags=re.IGNORECASE | re.DOTALL)
        result = []
        for part in parts:
            if part.lower().startswith('<style'):
                result.append(part)  # Leave CSS blocks unchanged
            else:
                result.append(re.sub(r'style="([^"]*)"', _process_style_attr, part))
        return ''.join(result)


