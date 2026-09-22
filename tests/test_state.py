import json
from datetime import date

from note_auto_poster.state import PostedState


def test_mark_images_posted_persists_to_disk(tmp_path):
    path = tmp_path / "state.json"
    state = PostedState(str(path))
    assert not state.is_image_posted("https://example.com/a.png")

    state.mark_images_posted(["https://example.com/a.png", "https://example.com/b.png"])

    assert state.is_image_posted("https://example.com/a.png")
    assert state.is_image_posted("https://example.com/b.png")
    assert not state.is_image_posted("https://example.com/c.png")

    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["posted_image_urls"] == [
        "https://example.com/a.png",
        "https://example.com/b.png",
    ]

    reloaded = PostedState(str(path))
    assert reloaded.is_image_posted("https://example.com/a.png")


def test_mark_images_posted_does_not_duplicate(tmp_path):
    state = PostedState(str(tmp_path / "state.json"))
    state.mark_images_posted(["https://example.com/a.png"])
    state.mark_images_posted(["https://example.com/a.png", "https://example.com/b.png"])

    with open(tmp_path / "state.json", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["posted_image_urls"] == [
        "https://example.com/a.png",
        "https://example.com/b.png",
    ]


def test_recent_article_keys_tracks_combined_history_capped(tmp_path):
    state = PostedState(str(tmp_path / "state.json"))
    assert state.get_recent_article_keys() == []

    for i in range(8):
        state.record_article_use(f"a{i}")

    # capped at RECENT_ARTICLE_HISTORY (6), oldest entries dropped
    assert state.get_recent_article_keys() == ["a2", "a3", "a4", "a5", "a6", "a7"]

    reloaded = PostedState(str(tmp_path / "state.json"))
    assert reloaded.get_recent_article_keys() == ["a2", "a3", "a4", "a5", "a6", "a7"]


def test_session_history_window(tmp_path):
    state = PostedState(str(tmp_path / "state.json"))
    today = date(2026, 1, 10)

    state.record_session_use(today, "夜撮影会")
    state.record_session_use(date(2026, 1, 8), "BBQ撮影会")
    state.record_session_use(date(2026, 1, 1), "制服撮影会")  # outside a 3-day window

    recent = state.get_recent_session_keys(today, window_days=3)
    assert recent == {"夜撮影会", "BBQ撮影会"}


def test_migrates_intermediate_last_article_key_schema(tmp_path):
    path = tmp_path / "state.json"
    old_schema = {
        "posted_image_urls": ["https://example.com/old.png"],
        "last_article_key": {"x": "abc123", "instagram": "def456"},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(old_schema, f)

    state = PostedState(str(path))
    assert state.is_image_posted("https://example.com/old.png")
    assert set(state.get_recent_article_keys()) == {"abc123", "def456"}


def test_migrates_oldest_posted_articles_schema(tmp_path):
    path = tmp_path / "state.json"
    old_schema = {
        "posted_articles": {
            "abc123": {
                "image_url": "https://example.com/old.png",
                "x_post_id": "1",
                "ig_post_id": "2",
                "posted_at": "2026-01-01T00:00:00+00:00",
            }
        }
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(old_schema, f)

    state = PostedState(str(path))
    assert state.is_image_posted("https://example.com/old.png")
    assert state.get_recent_article_keys() == []
