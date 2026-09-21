import pytest

from note_auto_poster.image_selector import ImageSelector, _parse_json


def test_select_returns_none_when_no_candidates():
    selector = ImageSelector(api_key=None)
    assert selector.select("title", "excerpt", [], "https://note.com/x/n/1") is None


def test_fallback_used_when_no_api_key():
    selector = ImageSelector(api_key=None)
    result = selector.select(
        "title", "excerpt", ["https://example.com/a.png", "https://example.com/b.png"], "https://note.com/x/n/1"
    )
    assert result is not None
    assert result.image_url == "https://example.com/a.png"
    assert result.caption_x == "title"


def test_parse_json_extracts_embedded_object():
    text = 'ここに説明があります {"selected_index": 1, "reason": "ok"} 以上'
    parsed = _parse_json(text)
    assert parsed["selected_index"] == 1
    assert parsed["reason"] == "ok"


def test_parse_json_raises_when_no_object_found():
    with pytest.raises(ValueError):
        _parse_json("no json here")
