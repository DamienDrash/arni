from app.memory.member_memory_analyzer import _extract_first_json_object, _format_llm_profile


def test_extract_first_json_object_from_fenced_response() -> None:
    raw = """```json
{"summary":"A","goals":["Muskelaufbau"],"preferences":[],"constraints":[],"risks":[],"motivation":"hoch","next_actions":[],"confidence":0.8}
```"""
    obj = _extract_first_json_object(raw)
    assert obj is not None
    assert obj.get("summary") == "A"
    assert obj.get("confidence") == 0.8


def test_extract_first_json_object_invalid_returns_none() -> None:
    assert _extract_first_json_object("kein json") is None


def test_format_llm_profile_renders_bullets() -> None:
    md = _format_llm_profile(
        {
            "summary": "Trainiert konstant",
            "goals": ["Kraft", "Mobilität"],
            "preferences": ["morgens"],
            "constraints": ["Knie"],
            "risks": ["Überlastung"],
            "motivation": "hoch",
            "next_actions": ["2x/Woche Plan"],
            "confidence": 0.73,
        }
    )
    assert "- Zusammenfassung: Trainiert konstant" in md
    assert "- Ziele: Kraft, Mobilität" in md
    assert "- Konfidenz: 0.73" in md
