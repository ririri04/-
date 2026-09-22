from datetime import datetime

from note_auto_poster import cli
from note_auto_poster.captions import X_CAPTION_EVENING, X_CAPTION_MORNING
from note_auto_poster.config import Config
from note_auto_poster.note_client import NoteArticle
from note_auto_poster.state import PostedState


def _make_config(tmp_path, **overrides) -> Config:
    defaults = dict(
        note_username="testuser",
        anthropic_api_key=None,
        anthropic_model="claude-sonnet-5",
        twitter_api_key="k",
        twitter_api_secret="s",
        twitter_access_token="at",
        twitter_access_token_secret="ats",
        ig_access_token="igtok",
        ig_user_id="123",
        post_to_x=True,
        post_to_instagram=True,
        instagram_image_count=5,
        state_file=str(tmp_path / "state.json"),
        dry_run=True,
    )
    defaults.update(overrides)
    return Config(**defaults)


def _article(key, title, n_images) -> NoteArticle:
    return NoteArticle(
        key=key,
        title=title,
        url=f"https://note.com/testuser/n/{key}",
        published_at=None,
        excerpt="",
        image_urls=[f"https://assets.st-note.com/img/{key}-{i}.png" for i in range(n_images)],
    )


def _stub_select_first_n(monkeypatch):
    monkeypatch.setattr(
        cli.ImageSelector,
        "select",
        lambda self, title, excerpt, image_urls, article_url, count=1: image_urls[:count],
    )


def test_run_picks_different_articles_for_x_and_instagram(tmp_path, monkeypatch):
    article_a = _article("a1", "記事A", 3)
    article_b = _article("b1", "記事B", 6)
    monkeypatch.setattr(cli.NoteClient, "fetch_recent_articles", lambda self, limit: [article_a, article_b])
    _stub_select_first_n(monkeypatch)
    monkeypatch.setattr(cli.random, "choice", lambda seq: seq[0])

    posted_x = {}
    posted_ig = {}
    monkeypatch.setattr(
        cli, "_post_to_x", lambda config, url, caption: posted_x.setdefault("url", url) or "tweet1"
    )
    monkeypatch.setattr(
        cli, "_post_to_instagram", lambda config, urls: posted_ig.setdefault("urls", urls) or "media1"
    )

    config = _make_config(tmp_path, dry_run=False)
    count = cli.run(config)

    assert count == 2
    assert posted_x["url"] == article_a.image_urls[0]
    assert posted_ig["urls"] == article_b.image_urls[:5]

    state = PostedState(config.state_file)
    assert state.is_image_posted(article_a.image_urls[0])
    for url in article_b.image_urls[:5]:
        assert state.is_image_posted(url)
    assert set(state.get_recent_article_keys()) == {"a1", "b1"}


def test_dry_run_does_not_post_or_update_state(tmp_path, monkeypatch):
    article_a = _article("a1", "記事A", 3)
    article_b = _article("b1", "記事B", 6)
    monkeypatch.setattr(cli.NoteClient, "fetch_recent_articles", lambda self, limit: [article_a, article_b])
    _stub_select_first_n(monkeypatch)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("posting should not happen during dry-run")

    monkeypatch.setattr(cli, "_post_to_x", _fail_if_called)
    monkeypatch.setattr(cli, "_post_to_instagram", _fail_if_called)

    config = _make_config(tmp_path, dry_run=True)
    count = cli.run(config)

    assert count == 0
    state = PostedState(config.state_file)
    assert not state.is_image_posted(article_a.image_urls[0])
    assert state.get_recent_article_keys() == []


def test_run_skips_platform_when_disabled(tmp_path, monkeypatch):
    article_a = _article("a1", "記事A", 3)
    monkeypatch.setattr(cli.NoteClient, "fetch_recent_articles", lambda self, limit: [article_a])
    _stub_select_first_n(monkeypatch)

    monkeypatch.setattr(cli, "_post_to_x", lambda config, url, caption: "tweet1")

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("instagram posting should not happen when disabled")

    monkeypatch.setattr(cli, "_post_to_instagram", _fail_if_called)

    config = _make_config(tmp_path, dry_run=False, post_to_instagram=False)
    count = cli.run(config)

    assert count == 1


def test_run_returns_zero_when_no_unused_images(tmp_path, monkeypatch):
    article_a = _article("a1", "記事A", 1)
    monkeypatch.setattr(cli.NoteClient, "fetch_recent_articles", lambda self, limit: [article_a])
    _stub_select_first_n(monkeypatch)

    config = _make_config(tmp_path, dry_run=False)
    state = PostedState(config.state_file)
    state.mark_images_posted(article_a.image_urls)

    count = cli.run(config)
    assert count == 0


def _select(candidates, **overrides):
    kwargs = dict(
        exclude_article_keys=set(),
        exclude_sessions=set(),
        recent_article_keys=[],
        avoid_sessions=set(),
        target_count=1,
    )
    kwargs.update(overrides)
    return cli._select_candidate(candidates, **kwargs)


def test_select_candidate_prefers_article_not_in_recent_history():
    article_a = _article("a1", "記事A", 3)
    article_b = _article("b1", "記事B", 3)
    candidates = [(article_a, article_a.image_urls), (article_b, article_b.image_urls)]

    pick = _select(candidates, recent_article_keys=["a1"])
    assert pick[0].key == "b1"


def test_select_candidate_falls_back_to_recent_if_no_alternative():
    article_a = _article("a1", "記事A", 3)
    candidates = [(article_a, article_a.image_urls)]

    pick = _select(candidates, recent_article_keys=["a1"])
    assert pick[0].key == "a1"


def test_select_candidate_avoids_recent_session_across_different_articles():
    article_a = _article("a1", "夜撮影会 その①", 3)
    article_b = _article("b1", "夜撮影会 その②", 3)
    article_c = _article("c1", "BBQ撮影会", 3)
    candidates = [
        (article_a, article_a.image_urls),
        (article_b, article_b.image_urls),
        (article_c, article_c.image_urls),
    ]

    # "夜撮影会" was used recently (different article, same session/outfit)
    pick = _select(candidates, avoid_sessions={"夜撮影会"})
    assert pick[0].key == "c1"


def test_select_candidate_hard_excludes_session_used_by_other_platform_this_run():
    article_a = _article("a1", "夜撮影会 その①", 3)
    article_b = _article("b1", "夜撮影会 その②", 3)
    candidates = [(article_a, article_a.image_urls), (article_b, article_b.image_urls)]

    pick = _select(candidates, exclude_sessions={"夜撮影会"})
    assert pick is None


def test_select_candidate_picks_randomly_among_all_eligible_articles(monkeypatch):
    article_a = _article("a1", "記事A", 3)
    article_b = _article("b1", "記事B", 3)
    article_c = _article("c1", "記事C", 3)
    candidates = [
        (article_a, article_a.image_urls),
        (article_b, article_b.image_urls),
        (article_c, article_c.image_urls),
    ]

    seen_pools = []

    def _record_choice(seq):
        seen_pools.append(list(seq))
        return seq[0]

    monkeypatch.setattr(cli.random, "choice", _record_choice)

    _select(candidates)

    assert len(seen_pools[0]) == 3


class _FakeDatetime:
    def __init__(self, fixed):
        self._fixed = fixed

    def now(self, tz):
        return self._fixed


def test_current_x_caption_uses_morning_before_cutoff(monkeypatch):
    monkeypatch.setattr(cli, "datetime", _FakeDatetime(datetime(2026, 1, 1, 6, 0, tzinfo=cli.JST)))
    assert cli._current_x_caption() == X_CAPTION_MORNING


def test_current_x_caption_uses_evening_after_cutoff(monkeypatch):
    monkeypatch.setattr(cli, "datetime", _FakeDatetime(datetime(2026, 1, 1, 20, 0, tzinfo=cli.JST)))
    assert cli._current_x_caption() == X_CAPTION_EVENING
