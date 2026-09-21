import json

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


def test_last_article_key_per_platform(tmp_path):
    state = PostedState(str(tmp_path / "state.json"))
    assert state.get_last_article_key("x") is None

    state.set_last_article_key("x", "abc123")
    state.set_last_article_key("instagram", "def456")

    assert state.get_last_article_key("x") == "abc123"
    assert state.get_last_article_key("instagram") == "def456"

    reloaded = PostedState(str(tmp_path / "state.json"))
    assert reloaded.get_last_article_key("x") == "abc123"
    assert reloaded.get_last_article_key("instagram") == "def456"


def test_migrates_old_schema(tmp_path):
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
    assert state.get_last_article_key("x") is None
