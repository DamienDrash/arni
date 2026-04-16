"""ARIIA v2.3 – Gold Standard Message Renderer with CSS Inlining & Tracking.

Combines campaign content with templates and personalizes via Jinja2.
Uses css-inline to convert <style> blocks into inline style attributes
for maximum email client compatibility (Gmail, Outlook, Apple Mail, etc.).

Supports email (full HTML wrapping), WhatsApp, SMS, and Telegram channels.

@ARCH: Campaign Refactoring Phase 1, Task 1.3 – Gold Standard
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

from app.core.contact_models import Contact
from app.domains.campaigns.models import Campaign, CampaignTemplate
from app.domains.identity.models import Tenant

logger = structlog.get_logger()

# Lazy-load css_inline to avoid hard crash if not installed
_css_inliner = None

def _get_css_inliner():
    global _css_inliner
    if _css_inliner is None:
        try:
            import css_inline
            _css_inliner = css_inline.CSSInliner(
                inline_style_tags=True,
                keep_style_tags=True,   # Keep <style> for media queries
            )
            logger.info("renderer.css_inliner_loaded")
        except ImportError:
            logger.warning("renderer.css_inline_not_installed",
                           msg="pip install css-inline for Gold Standard email rendering")
            _css_inliner = False  # Sentinel: tried but failed
    return _css_inliner if _css_inliner is not False else None


# Base URL for tracking endpoints – configurable via env
TRACKING_BASE_URL = os.environ.get(
    "TRACKING_BASE_URL",
    "https://www.ariia.ai",
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
        context = self._build_context(contact, campaign, db=db, recipient_id=recipient_id)

        # 3. Compose HTML parts
        # Use content_html first, fall back to content_body
        raw_body = campaign.content_html or campaign.content_body or ""
        body = self._render_part(raw_body, context)

        # If content was plain text (no content_html), convert to HTML
        if not campaign.content_html and campaign.content_body:
            body = self._plaintext_to_html(body)

        # 4. Wrap in full HTML structure (email only)
        if campaign.channel == "email":
            primary_color = (template.primary_color if template else "#6C5CE7") or "#6C5CE7"
            logo_url = (template.logo_url if template else None) or None

            raw_header = (template.header_html or "") if template else ""
            header = self._render_part(raw_header, context) if raw_header else ""
            footer = self._render_part(template.footer_html, context) if template and template.footer_html else ""
            full_html = self._wrap_email_html(header, body, footer, primary_color, logo_url)

            # Gold Standard: CSS Inlining
            full_html = self._inline_css(full_html)
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

    def _build_context(
        self,
        contact: Contact,
        campaign: Campaign,
        db: Session | None = None,
        recipient_id: int | None = None,
    ) -> dict:
        """Build the Jinja2 template context from contact and campaign data."""
        # Resolve tenant/studio name
        studio_name = ""
        if db:
            tenant = db.query(Tenant).filter(Tenant.id == campaign.tenant_id).first()
            studio_name = tenant.name if tenant else ""

        # Unsubscribe URL — unique per contact/recipient
        if recipient_id:
            unsubscribe_url = f"{TRACKING_BASE_URL}/unsubscribe/{recipient_id}"
        elif contact.id:
            unsubscribe_url = f"{TRACKING_BASE_URL}/unsubscribe/c/{contact.id}"
        else:
            unsubscribe_url = f"{TRACKING_BASE_URL}/unsubscribe"

        return {
            "contact": {
                "first_name": contact.first_name or "",
                "last_name": contact.last_name or "",
                "full_name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                "email": contact.email or "",
                "phone": contact.phone or "",
                "company": contact.company or studio_name,
            },
            "campaign": {
                "name": campaign.name,
                "channel": campaign.channel,
            },
            # Top-level placeholders
            "first_name": contact.first_name or "",
            "last_name": contact.last_name or "",
            "full_name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
            "studio_name": studio_name,
            "unsubscribe_url": unsubscribe_url,
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

    @staticmethod
    def _extract_style_blocks(html: str) -> tuple[str, str]:
        """Extract all <style>...</style> blocks from HTML.

        Returns:
            tuple: (extracted_css, html_without_style_tags)
        """
        style_pattern = re.compile(r'<style[^>]*>(.*?)</style>', re.DOTALL | re.IGNORECASE)
        styles = []
        for match in style_pattern.finditer(html):
            styles.append(match.group(1))
        cleaned = style_pattern.sub('', html)
        return '\n'.join(styles), cleaned.strip()

    def _wrap_email_html(
        self,
        header: str,
        body: str,
        footer: str,
        color: str,
        logo_url: Optional[str] = None,
    ) -> str:
        """Wrap content in a table-based responsive email HTML structure.

        Gold Standard approach:
        1. Extract <style> from template header_html → merge into <head>
        2. Use table-based layout for Outlook compatibility
        3. Include both base + template CSS in <head> (for Gmail/Apple Mail)
        4. css-inline will later convert these to inline styles (for Outlook)
        5. Dark mode meta tags to force light rendering
        """
        logo_block = ""
        if logo_url:
            logo_block = (
                f'<img src="{logo_url}" alt="Logo" '
                f'style="max-width:180px;height:auto;margin-bottom:12px;display:block;" />'
            )

        # Extract <style> blocks from header content and move to <head>
        template_css, header_content = self._extract_style_blocks(header)

        return f"""<!DOCTYPE html>
<html lang="de" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" style="color-scheme: light dark;">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <![endif]-->
  <style>
    /* === Reset === */
    body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
    table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
    img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
    body {{ margin: 0 !important; padding: 0 !important; width: 100% !important; }}

    /* === Base Layout === */
    .email-wrapper {{ background-color: #ffffff; width: 100%; }}
    .email-container {{ max-width: 600px; margin: 0 auto; }}

    /* === Header === */
    .email-header {{ background-color: #ffffff; padding: 28px 24px; text-align: center; border-bottom: 2px solid #f0f0f0; }}
    .email-header h1 {{ margin: 0; font-size: 22px; font-weight: 600; color: #1a1a1a; }}

    /* === Body === */
    .email-body {{ background-color: #111111; padding: 40px 32px; line-height: 1.7; color: #f0f0f0; font-size: 15px; font-family: 'Funnel Sans', Arial, Helvetica, sans-serif; }}
    .email-body h1, .email-body h2, .email-body h3 {{ color: {color}; font-family: 'Funnel Sans', Arial, Helvetica, sans-serif; }}
    .email-body p {{ color: #f0f0f0; font-family: 'Funnel Sans', Arial, Helvetica, sans-serif; margin: 0 0 16px 0; }}
    .email-body a {{ color: {color}; text-decoration: underline; }}

    /* === CTA Button === */
    .email-btn {{ display: inline-block; padding: 14px 32px; background-color: {color}; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px; font-family: 'Funnel Sans', Arial, Helvetica, sans-serif; }}

    /* === Footer === */
    .email-footer {{ background-color: #ffffff; padding: 28px 24px; color: #666666; font-size: 12px; text-align: center; line-height: 1.5; border-top: 2px solid #f0f0f0; }}
    .email-footer a {{ color: {color}; text-decoration: none; }}

    /* === Responsive === */
    @media only screen and (max-width: 620px) {{
      .email-container {{ width: 100% !important; }}
      .email-body {{ padding: 24px 16px !important; }}
      .email-header {{ padding: 20px 16px !important; }}
      .email-footer {{ padding: 20px 16px !important; }}
    }}

    /* === Dark Mode — lock brand colors in all clients === */
    @media (prefers-color-scheme: dark) {{
      .email-wrapper {{ background-color: #ffffff !important; }}
      .email-header {{ background-color: #ffffff !important; border-bottom: 2px solid #f0f0f0 !important; }}
      .email-header h1 {{ color: #1a1a1a !important; }}
      .email-body {{ background-color: #111111 !important; color: #f0f0f0 !important; }}
      .email-body h1, .email-body h2, .email-body h3 {{ color: {color} !important; }}
      .email-body p, .email-body span, .email-body li, .email-body td {{ color: #f0f0f0 !important; }}
      .email-body a {{ color: {color} !important; }}
      .email-btn {{ background-color: {color} !important; color: #ffffff !important; }}
      .email-footer {{ background-color: #ffffff !important; color: #666666 !important; border-top: 2px solid #f0f0f0 !important; }}
      .email-footer a {{ color: {color} !important; }}
      /* Template footer classes */
      .footer {{ background-color: #ffffff !important; color: #666666 !important; }}
      .footer a {{ color: {color} !important; }}
    }}
    /* Outlook intelligent dark mode */
    [data-ogsb] .email-header, [data-ogsb] .footer {{ background-color: #ffffff !important; }}
    [data-ogsb] .email-body {{ background-color: #111111 !important; }}
    [data-ogsc] .email-body, [data-ogsc] .email-body p {{ color: #f0f0f0 !important; }}
    [data-ogsb] .email-btn {{ background-color: {color} !important; }}

    /* === Tenant Template Overrides === */
    {template_css}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#ffffff;font-family:'Funnel Sans',Arial,Helvetica,sans-serif;">
  <!--[if mso]>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td align="center">
  <![endif]-->
  <table role="presentation" class="email-wrapper" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;">
    <tr>
      <td align="center" style="padding:20px 0;">
        <!--[if mso]>
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0">
        <tr><td>
        <![endif]-->
        <table role="presentation" class="email-container" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;margin:0 auto;">
          <!-- HEADER -->
          <tr>
            <td class="email-header" style="background-color:#ffffff;padding:28px 24px;text-align:center;border-bottom:2px solid #f0f0f0;">
              {logo_block}
              {header_content}
            </td>
          </tr>
          <!-- BODY -->
          <tr>
            <td class="email-body" style="background-color:#111111;padding:40px 32px;line-height:1.7;color:#f0f0f0;font-size:15px;font-family:'Funnel Sans',Arial,Helvetica,sans-serif;">
              {body}
            </td>
          </tr>
          <!-- FOOTER -->
          <tr>
            <td class="email-footer" style="background-color:#ffffff;padding:28px 24px;color:#666666;font-size:12px;text-align:center;line-height:1.5;border-top:2px solid #f0f0f0;">
              {footer}
            </td>
          </tr>
        </table>
        <!--[if mso]>
        </td></tr></table>
        <![endif]-->
      </td>
    </tr>
  </table>
  <!--[if mso]>
  </td></tr></table>
  <![endif]-->
</body>
</html>"""

    @staticmethod
    def _inline_css(html: str) -> str:
        """Inline CSS from <style> blocks into element style attributes.

        Uses css-inline library for high-performance, spec-compliant inlining.
        Falls back to returning the original HTML if css-inline is not available.
        """
        inliner = _get_css_inliner()
        if inliner:
            try:
                return inliner.inline(html)
            except Exception as e:
                logger.warning("renderer.css_inline_failed", error=str(e))
        return html

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

    def _plaintext_to_html(self, text: str) -> str:
        """Convert plain text to HTML: auto-link URLs and convert newlines to <br>."""
        import html as html_module
        # Escape HTML special chars first
        text = html_module.escape(text)
        # Auto-link URLs (http/https)
        url_pattern = r'(https?://[^\s<>"&]+)'
        text = re.sub(url_pattern, r'<a href="\1">\1</a>', text)
        # Convert newlines to <br>
        text = text.replace('\n', '<br>\n')
        return text

    # ── Phase 3: Tracking ──────────────────────────────────────────────

    def _inject_tracking_pixel(self, html: str, recipient_id: int) -> str:
        """Inject a 1x1 transparent tracking pixel before </body>."""
        pixel_url = f"{TRACKING_BASE_URL}/tracking/open/{recipient_id}"
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
            if any(skip in original_url for skip in ["/tracking/", "mailto:", "tel:", "#"]):
                return match.group(0)
            encoded = url_quote(original_url, safe="")
            tracker_url = f"{TRACKING_BASE_URL}/tracking/click/{recipient_id}?url={encoded}"
            return f'href="{tracker_url}"'

        return re.sub(r'href="([^"]+)"', _replace_href, html)
