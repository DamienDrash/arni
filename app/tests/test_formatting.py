"""UX-1/UX-2: Tests for Markdown to WhatsApp formatting conversion."""

import pytest
from app.gateway.formatting import convert_markdown_to_whatsapp, format_for_platform


class TestMarkdownToWhatsApp:
    """Test convert_markdown_to_whatsapp function."""

    def test_bold_conversion(self):
        assert convert_markdown_to_whatsapp("**bold text**") == "*bold text*"

    def test_double_underscore_bold(self):
        assert convert_markdown_to_whatsapp("__bold text__") == "*bold text*"

    def test_italic_preserved(self):
        assert convert_markdown_to_whatsapp("_italic text_") == "_italic text_"

    def test_strikethrough(self):
        assert convert_markdown_to_whatsapp("~~deleted~~") == "~deleted~"

    def test_header_h1(self):
        assert convert_markdown_to_whatsapp("# Title") == "*Title*"

    def test_header_h2(self):
        assert convert_markdown_to_whatsapp("## Subtitle") == "*Subtitle*"

    def test_header_h3(self):
        assert convert_markdown_to_whatsapp("### Section") == "*Section*"

    def test_link_conversion(self):
        result = convert_markdown_to_whatsapp("[Click here](https://example.com)")
        assert result == "Click here (https://example.com)"

    def test_image_conversion(self):
        result = convert_markdown_to_whatsapp("![Logo](https://example.com/logo.png)")
        assert result == "[Bild: Logo]"

    def test_unordered_list(self):
        md = "- Item 1\n- Item 2\n- Item 3"
        result = convert_markdown_to_whatsapp(md)
        assert "• Item 1" in result
        assert "• Item 2" in result
        assert "• Item 3" in result

    def test_ordered_list_preserved(self):
        md = "1. First\n2. Second\n3. Third"
        result = convert_markdown_to_whatsapp(md)
        assert "1. First" in result
        assert "2. Second" in result

    def test_horizontal_rule_removed(self):
        md = "Text above\n---\nText below"
        result = convert_markdown_to_whatsapp(md)
        assert "---" not in result
        assert "Text above" in result
        assert "Text below" in result

    def test_code_block_preserved(self):
        md = "```python\nprint('hello')\n```"
        result = convert_markdown_to_whatsapp(md)
        assert "```" in result
        assert "print('hello')" in result

    def test_inline_code_preserved(self):
        md = "Use `pip install` to install"
        result = convert_markdown_to_whatsapp(md)
        assert "`pip install`" in result

    def test_excessive_newlines_cleaned(self):
        md = "Line 1\n\n\n\n\nLine 2"
        result = convert_markdown_to_whatsapp(md)
        assert "\n\n\n" not in result

    def test_empty_string(self):
        assert convert_markdown_to_whatsapp("") == ""

    def test_none_passthrough(self):
        assert convert_markdown_to_whatsapp(None) is None

    def test_complex_llm_response(self):
        """Test a realistic LLM response with mixed formatting."""
        md = """## Deine Trainingszeiten

Hier sind die **verfügbaren Kurse** für heute:

- **Yoga** um 10:00 Uhr
- **Spinning** um 14:00 Uhr
- **CrossFit** um 18:00 Uhr

Möchtest du einen Kurs buchen? [Hier klicken](https://booking.example.com)

---

_Hinweis: Änderungen vorbehalten._"""

        result = convert_markdown_to_whatsapp(md)

        # Headers should be bold
        assert "*Deine Trainingszeiten*" in result
        # Bold should be converted
        assert "*verfügbaren Kurse*" in result
        # Lists should use bullet points
        assert "• *Yoga*" in result or "• *Yoga* um" in result
        # Links should be expanded
        assert "Hier klicken (https://booking.example.com)" in result
        # Horizontal rule should be removed
        assert "---" not in result
        # Italic should be preserved
        assert "_Hinweis:" in result


class TestFormatForPlatform:
    """Test format_for_platform routing."""

    def test_whatsapp_formatting(self):
        result = format_for_platform("**bold**", "whatsapp")
        assert result == "*bold*"

    def test_telegram_passthrough(self):
        result = format_for_platform("**bold**", "telegram")
        assert result == "**bold**"

    def test_sms_strips_formatting(self):
        result = format_for_platform("**bold** and _italic_", "sms")
        assert "**" not in result
        assert "bold" in result

    def test_email_passthrough(self):
        result = format_for_platform("**bold**", "email")
        assert result == "**bold**"

    def test_unknown_platform_passthrough(self):
        result = format_for_platform("**bold**", "unknown")
        assert result == "**bold**"

    def test_empty_text(self):
        assert format_for_platform("", "whatsapp") == ""

    def test_none_text(self):
        assert format_for_platform(None, "whatsapp") is None
