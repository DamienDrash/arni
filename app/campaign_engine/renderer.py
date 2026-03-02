"""ARIIA v2.2 – Message Renderer with Tracking.

Combines campaign content with templates and personalizes via Jinja2.
Supports email (full HTML wrapping), WhatsApp, SMS, and Telegram channels.

@ARCH: Campaign Refactoring Phase 1, Task 1.3
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote as url_quote

import jinja2
import structlog
from sqlalchemy.orm import Session

from app.core.models import Campaign, CampaignTemplate
from app.core.contact_models import Contact

logger = structlog.get_logger()


# Base URL for tracking endpoints – configurable via env
TRACKING_BASE_URL = os.environ.get(
    "TRACKING_BASE_URL",
    "https://api.ariia.app",
)


@dataclass
class RenderedMessage:
    """Final, ready-to-send message."""
    subject: str
    body_html: str
    body_text: str
    channel: str
    recipient_id: int | None = None


class MessageRenderer:
    """Renders campaign content with template wrapping and personalization.

    Template resolution priority chain:
    1. template_override (if provided)
    2. campaign.template_id (if set on the campaign)
    3. Tenant default template for the campaign's channel
    4. No template (raw content only)
    """

    def __init__(self):
        self._jinja_env = jinja2.Environment(
            autoescape=jinja2.select_autoescape(["html"]),
            undefined=jinja2.Undefined,  # Graceful handling of missing vars
        )

    async def render(
        self,
        db: Session,
        campaign: Campaign,
        contact: Contact,
        template_override: Optional[CampaignTemplate] = None,
        recipient_id: Optional[int] = None,
    ) -> RenderedMessage:
        """Render a personalized message for a single contact."""
        # 1. Resolve template
        template = self._resolve_template(db, campaign, template_override)

        # 2. Build context dict for Jinja2
        context = self._build_context(contact, campaign)

        # 3. Compose HTML
        header = self._render_part(template.header_html, context) if template and template.header_html else ""
        footer = self._render_part(template.footer_html, context) if template and template.footer_html else ""

        # Use content_html first, fall back to content_body
        raw_body = campaign.content_html or campaign.content_body or ""
        body = self._render_part(raw_body, context)

        # 4. Wrap in full HTML structure (email only)
        if campaign.channel == "email":
            primary_color = (template.primary_color if template else "#6C5CE7") or "#6C5CE7"
            logo_url = (template.logo_url if template else None) or None
            full_html = self._wrap_email_html(header, body, footer, primary_color, logo_url)
        else:
            full_html = body  # WhatsApp/SMS/Telegram: no HTML wrapping

        # 5. Render subject
        subject = self._render_part(campaign.content_subject or campaign.name or "", context)

        # 6. Generate plain text fallback
        body_text = self._html_to_text(full_html)

        logger.debug(
            "renderer.rendered",
            campaign_id=campaign.id,
            contact_id=contact.id,
            channel=campaign.channel,
            has_template=template is not None,
        )

        # 7. Inject tracking (email only, requires recipient_id)
        if campaign.channel == "email" and recipient_id:
            full_html = self._inject_tracking_pixel(full_html, recipient_id)
            full_html = self._rewrite_links(full_html, recipient_id)

        return RenderedMessage(
            subject=subject,
            body_html=full_html,
            body_text=body_text,
            channel=campaign.channel,
            recipient_id=recipient_id,
        )

    def _resolve_template(
        self,
        db: Session,
        campaign: Campaign,
        template_override: Optional[CampaignTemplate],
    ) -> Optional[CampaignTemplate]:
        """Resolve the template to use for rendering."""
        if template_override:
            return template_override

        # Try campaign's explicit template_id
        if campaign.template_id:
            template = db.query(CampaignTemplate).filter(
                CampaignTemplate.id == campaign.template_id,
                CampaignTemplate.is_active.is_(True),
            ).first()
            if template:
                return template

        # Fall back to tenant default for this channel
        return db.query(CampaignTemplate).filter(
            CampaignTemplate.tenant_id == campaign.tenant_id,
            CampaignTemplate.type == campaign.channel,
            CampaignTemplate.is_default.is_(True),
            CampaignTemplate.is_active.is_(True),
        ).first()

    def _build_context(self, contact: Contact, campaign: Campaign) -> dict:
        """Build the Jinja2 template context from contact and campaign data."""
        return {
            "contact": {
                "first_name": contact.first_name or "",
                "last_name": contact.last_name or "",
                "full_name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                "email": contact.email or "",
                "phone": contact.phone or "",
                "company": contact.company or "",
            },
            "campaign": {
                "name": campaign.name,
                "channel": campaign.channel,
            },
            # Legacy placeholders for backward compatibility
            "first_name": contact.first_name or "",
            "last_name": contact.last_name or "",
            "studio_name": contact.company or "",
        }

    def _render_part(self, template_str: str, context: dict) -> str:
        """Render a single template string with Jinja2."""
        if not template_str:
            return ""
        try:
            tmpl = self._jinja_env.from_string(template_str)
            return tmpl.render(**context)
        except Exception as e:
            logger.warning("renderer.jinja_error", error=str(e), template=template_str[:100])
            return template_str  # Return unrendered on error

    def _wrap_email_html(
        self,
        header: str,
        body: str,
        footer: str,
        color: str,
        logo_url: Optional[str] = None,
    ) -> str:
        """Wrap content parts in a responsive email HTML structure."""
        logo_block = ""
        if logo_url:
            logo_block = f'<img src="{logo_url}" alt="Logo" style="max-width:180px;height:auto;margin-bottom:12px;" />'

        return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #f4f4f7; -webkit-font-smoothing: antialiased; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .header {{ background: {color}; color: #ffffff; padding: 28px 24px; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; }}
    .body {{ padding: 32px 24px; line-height: 1.7; color: #333333; font-size: 15px; }}
    .body h2 {{ color: {color}; font-size: 18px; margin-top: 24px; }}
    .body a {{ color: {color}; text-decoration: underline; }}
    .footer {{ padding: 24px; background: #f4f4f7; color: #666666; font-size: 12px; text-align: center; line-height: 1.5; }}
    .footer a {{ color: {color}; text-decoration: none; }}
    .btn {{ display: inline-block; padding: 12px 28px; background: {color}; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 16px 0; }}
    @media only screen and (max-width: 620px) {{
      .container {{ margin: 0 !important; border-radius: 0 !important; }}
      .body {{ padding: 24px 16px !important; }}
    }}
  </style>
</head>
<body>
  <div style="padding: 20px 0;">
    <div class="container">
      <div class="header">
        {logo_block}
        {header}
      </div>
      <div class="body">
        {body}
      </div>
      <div class="footer">
        {footer}
      </div>
    </div>
  </div>
</body>
</html>"""

    def _html_to_text(self, html: str) -> str:
        """Simple HTML to plain text conversion."""
        text = re.sub(r'<br\s*/?>', '\n', html)
        text = re.sub(r'</p>', '\n\n', text)
        text = re.sub(r'</h[1-6]>', '\n\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        return text.strip()

    # ── Phase 3: Tracking ──────────────────────────────────────────────

    def _inject_tracking_pixel(self, html: str, recipient_id: int) -> str:
        """Inject a 1x1 transparent tracking pixel before </body>."""
        pixel_url = f"{TRACKING_BASE_URL}/track/open/{recipient_id}"
        pixel_tag = (
            f'<img src="{pixel_url}" width="1" height="1" '
            f'alt="" style="display:none;border:0;" />'
        )
        # Insert before </body> if present, otherwise append
        if "</body>" in html:
            return html.replace("</body>", f"{pixel_tag}\n</body>")
        return html + pixel_tag

    def _rewrite_links(self, html: str, recipient_id: int) -> str:
        """Rewrite all <a href="..."> links to pass through the click tracker."""
        def _replace_href(match: re.Match) -> str:
            original_url = match.group(1)
            # Skip tracking/unsubscribe/mailto links
            if any(skip in original_url for skip in ["/track/", "mailto:", "tel:", "#"]):
                return match.group(0)
            encoded = url_quote(original_url, safe="")
            tracker_url = f"{TRACKING_BASE_URL}/track/click/{recipient_id}?url={encoded}"
            return f'href="{tracker_url}"'

        return re.sub(r'href="([^"]+)"', _replace_href, html)
