import re

def clean_text_for_tts(text: str, lang: str = "de") -> str:
    """
    Prepares text for TTS by removing emojis and normalizing time formats.
    
    Args:
        text: The input text to clean.
        lang: Language code (default "de").
        
    Returns:
        Cleaned text string optimized for TTS.
    """
    if not text:
        return ""

    # 1. Remove Emojis (Unicode ranges for Emoticons, Misc Symbols, etc.)
    # This is a broad regex for many common emojis
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "\U0001f900-\U0001f9ff"  # supplemental symbols
        "\U0001fa00-\U0001faf6"  # extended symbols
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "\U0000200d"             # ZWJ
        "\U0000fe0f"             # Variation Selector
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub("", text)

    # 2. Markdown Cleanup
    # Remove bold/italic markers (*, _, ~) but keep structure if possible
    text = re.sub(r"[\*_~`]", "", text)

    # 3. Time Normalization (German)
    if lang == "de":
        # pattern: 14:00 -> 14 Uhr
        text = re.sub(r"(\d{1,2}):00", r"\1 Uhr", text)
        # pattern: 14:30 -> 14 Uhr 30
        text = re.sub(r"(\d{1,2}):(\d{2})", r"\1 Uhr \2", text)

    # 4. Whitespace Cleanup
    text = re.sub(r"\s+", " ", text).strip()
    
    return text
