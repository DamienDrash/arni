"""ARIIA – Markdown to WhatsApp Formatting Converter (UX-1).

Converts standard Markdown formatting to WhatsApp-compatible formatting.

WhatsApp supports a limited subset of formatting:
  - *bold* (single asterisks)
  - _italic_ (single underscores)
  - ~strikethrough~ (tildes)
  - ```monospace``` (triple backticks for code blocks)
  - `monospace` (single backticks for inline code – supported on newer clients)
  - > blockquote (supported on newer clients)
  - Numbered and bulleted lists (plain text, no special syntax)

Markdown features NOT supported by WhatsApp:
  - Headers (# ## ###) → converted to *bold*
  - Links [text](url) → converted to "text (url)"
  - Images ![alt](url) → converted to "[Bild: alt]"
  - Tables → converted to plain text
  - Horizontal rules (---) → removed
"""

import re
from typing import Optional

import structlog

logger = structlog.get_logger()


def convert_markdown_to_whatsapp(text: str) -> str:
    """Convert Markdown-formatted text to WhatsApp-compatible formatting.

    This function handles the most common Markdown patterns that LLMs
    produce and converts them to WhatsApp's limited formatting syntax.

    Args:
        text: The Markdown-formatted text from the LLM response.

    Returns:
        WhatsApp-compatible formatted text.
    """
    if not text:
        return text

    result = text

    # 1. Code blocks: ```lang\ncode\n``` → ```code``` (WhatsApp supports triple backticks)
    result = re.sub(
        r"```\w*\n(.*?)```",
        r"```\1```",
        result,
        flags=re.DOTALL,
    )

    # 2. Headers: # Header → *Header* (bold)
    # Handle h1-h6, converting to bold text
    result = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", result, flags=re.MULTILINE)

    # 3. Bold: **text** → *text* (WhatsApp uses single asterisks for bold)
    result = re.sub(r"\*\*(.+?)\*\*", r"*\1*", result)

    # 4. Bold with underscores: __text__ → *text*
    result = re.sub(r"__(.+?)__", r"*\1*", result)

    # 5. Italic: _text_ stays as _text_ (WhatsApp supports this)
    # No conversion needed for single underscores

    # 6. Strikethrough: ~~text~~ → ~text~ (WhatsApp uses single tildes)
    result = re.sub(r"~~(.+?)~~", r"~\1~", result)

    # 7. Images: ![alt](url) → [Bild: alt]
    result = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"[Bild: \1]", result)

    # 8. Links: [text](url) → text (url)
    result = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r"\1 (\2)", result)

    # 9. Horizontal rules: --- or *** or ___ → remove
    result = re.sub(r"^[-*_]{3,}\s*$", "", result, flags=re.MULTILINE)

    # 10. Blockquotes: > text → > text (WhatsApp supports this on newer clients)
    # Keep as-is since WhatsApp now supports blockquotes

    # 11. Unordered lists: - item or * item → • item
    result = re.sub(r"^[\s]*[-*+]\s+", "• ", result, flags=re.MULTILINE)

    # 12. Ordered lists: 1. item → 1. item (keep as-is, WhatsApp renders fine)
    # No conversion needed

    # 13. Clean up excessive blank lines (max 2 consecutive)
    result = re.sub(r"\n{3,}", "\n\n", result)

    # 14. Clean up trailing whitespace on each line
    result = re.sub(r"[ \t]+$", "", result, flags=re.MULTILINE)

    return result.strip()


def format_for_platform(text: str, platform: str) -> str:
    """Format text appropriately for the target messaging platform.

    Args:
        text: The raw text (typically Markdown from LLM).
        platform: The target platform identifier.

    Returns:
        Platform-appropriate formatted text.
    """
    if not text:
        return text

    platform_lower = (platform or "").lower()

    if platform_lower == "whatsapp":
        return convert_markdown_to_whatsapp(text)
    elif platform_lower == "telegram":
        # Telegram supports Markdown natively, minimal conversion needed
        return text
    elif platform_lower in ("sms", "phone", "voice"):
        # SMS/Voice: Strip all formatting, plain text only
        return _strip_all_formatting(text)
    elif platform_lower == "email":
        # Email: Keep Markdown as-is (can be rendered as HTML later)
        return text
    else:
        # Unknown platform: return as-is
        return text


def _strip_all_formatting(text: str) -> str:
    """Remove all Markdown formatting for plain-text channels (SMS, Voice).

    Args:
        text: Markdown-formatted text.

    Returns:
        Plain text without any formatting markers.
    """
    result = text

    # Remove code blocks
    result = re.sub(r"```\w*\n(.*?)```", r"\1", result, flags=re.DOTALL)
    result = re.sub(r"`([^`]+)`", r"\1", result)

    # Remove headers
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)

    # Remove bold/italic markers
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)
    result = re.sub(r"__(.+?)__", r"\1", result)
    result = re.sub(r"\*(.+?)\*", r"\1", result)
    result = re.sub(r"_(.+?)_", r"\1", result)

    # Remove strikethrough
    result = re.sub(r"~~(.+?)~~", r"\1", result)

    # Convert images
    result = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"[Bild: \1]", result)

    # Convert links
    result = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r"\1 (\2)", result)

    # Remove horizontal rules
    result = re.sub(r"^[-*_]{3,}\s*$", "", result, flags=re.MULTILINE)

    # Convert list markers
    result = re.sub(r"^[\s]*[-*+]\s+", "- ", result, flags=re.MULTILINE)

    # Remove blockquote markers
    result = re.sub(r"^>\s?", "", result, flags=re.MULTILINE)

    # Clean up
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()
