import pytest

from note_auto_poster.image_selector import ImageSelector, _parse_json


def test_select_returns_empty_when_no_candidates():
    selector = ImageSelector(api_key=None)
    assert selector.select("title", "excerpt", [], "https://note.com/x/n/1", count=1) == []


def test_fallback_used_when_no_api_key():
    selector = ImageSelector(api_key=None)
    result = selector.select(
        "title",
        "excerpt",
        ["https://example.com/a.png", "https://example.com/b.png", "https://example.com/c.png"],
        "https://note.com/x/n/1",
        count=2,
    )
    assert result == ["https://example.com/a.png", "https://example.com/b.png"]


def test_parse_json_extracts_embedded_object():
    text = 'ここに説明があります {"selected_indices": [2, 0], "reason": "ok"} 以上'
    parsed = _parse_json(text)
    assert parsed["selected_indices"] == [2, 0]
    assert parsed["reason"] == "ok"


def test_parse_json_raises_when_no_object_found():
    with pytest.raises(ValueError):
        _parse_json("no json here")
