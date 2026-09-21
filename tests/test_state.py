import json

from note_auto_poster.state import PostedState


def test_mark_posted_persists_to_disk(tmp_path):
    path = tmp_path / "state.json"
    state = PostedState(str(path))
    assert not state.is_posted("abc")

    state.mark_posted("abc", "https://example.com/img.png", x_post_id="1", ig_post_id="2")

    assert state.is_posted("abc")
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["posted_articles"]["abc"]["x_post_id"] == "1"
    assert saved["posted_articles"]["abc"]["ig_post_id"] == "2"

    reloaded = PostedState(str(path))
    assert reloaded.is_posted("abc")
    assert not reloaded.is_posted("other")
