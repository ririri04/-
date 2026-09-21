from note_auto_poster import cli
from note_auto_poster.config import Config
from note_auto_poster.image_selector import Selection
from note_auto_poster.note_client import NoteArticle
from note_auto_poster.state import PostedState


def _make_config(tmp_path, **overrides) -> Config:
    defaults = dict(
        note_username="testuser",
        anthropic_api_key=None,
        anthropic_model="claude-sonnet-5",
        twitter_api_key=None,
        twitter_api_secret=None,
        twitter_access_token=None,
        twitter_access_token_secret=None,
        ig_access_token=None,
        ig_user_id=None,
        post_to_x=True,
        post_to_instagram=True,
        max_articles_per_run=1,
        state_file=str(tmp_path / "state.json"),
        dry_run=True,
    )
    defaults.update(overrides)
    return Config(**defaults)


def test_run_dry_run_marks_article_posted_without_calling_posters(tmp_path, monkeypatch):
    article = NoteArticle(
        key="abc123",
        title="テスト記事",
        url="https://note.com/testuser/n/abc123",
        published_at="2026-09-01T00:00:00+09:00",
        excerpt="本文です",
        image_urls=["https://assets.st-note.com/img/eyecatch.png"],
    )

    monkeypatch.setattr(
        cli.NoteClient, "fetch_recent_articles", lambda self, limit: [article]
    )
    monkeypatch.setattr(
        cli.ImageSelector,
        "select",
        lambda self, title, excerpt, image_urls, article_url: Selection(
            image_url=image_urls[0],
            reason="test",
            caption_x="caption x",
            caption_instagram="caption ig",
        ),
    )

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("posting should not happen during dry-run")

    monkeypatch.setattr(cli, "_post_to_x", _fail_if_called)
    monkeypatch.setattr(cli, "_post_to_instagram", _fail_if_called)

    config = _make_config(tmp_path, dry_run=True)
    count = cli.run(config)

    assert count == 1
    state = PostedState(config.state_file)
    assert state.is_posted("abc123")


def test_run_skips_articles_without_images(tmp_path, monkeypatch):
    article = NoteArticle(
        key="noimg",
        title="画像なし記事",
        url="https://note.com/testuser/n/noimg",
        published_at=None,
        excerpt="",
        image_urls=[],
    )
    monkeypatch.setattr(
        cli.NoteClient, "fetch_recent_articles", lambda self, limit: [article]
    )

    config = _make_config(tmp_path, dry_run=True)
    count = cli.run(config)

    assert count == 0
    state = PostedState(config.state_file)
    assert not state.is_posted("noimg")


def test_run_skips_already_posted_articles(tmp_path, monkeypatch):
    article = NoteArticle(
        key="abc123",
        title="テスト記事",
        url="https://note.com/testuser/n/abc123",
        published_at=None,
        excerpt="",
        image_urls=["https://assets.st-note.com/img/eyecatch.png"],
    )
    monkeypatch.setattr(
        cli.NoteClient, "fetch_recent_articles", lambda self, limit: [article]
    )

    config = _make_config(tmp_path, dry_run=True)
    state = PostedState(config.state_file)
    state.mark_posted("abc123", "https://assets.st-note.com/img/eyecatch.png")

    count = cli.run(config)
    assert count == 0
