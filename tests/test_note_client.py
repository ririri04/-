import responses
from responses import matchers

from note_auto_poster.note_client import NOTE_API_BASE, NoteClient

LIST_PAYLOAD = {
    "data": {
        "contents": [
            {
                "key": "abc123",
                "name": "テスト記事",
                "publish_at": "2026-09-01T00:00:00+09:00",
                "type": "TextNote",
            },
            {
                "key": "membership1",
                "name": "会員限定コンテンツ",
                "type": "Membership",
            },
        ]
    }
}

DETAIL_PAYLOAD = {
    "data": {
        "eyecatch": "https://assets.st-note.com/img/eyecatch.png",
        "body": (
            "<p>本文です</p>"
            '<img src="https://assets.st-note.com/img/inline1.png">'
            '<img src="https://other-cdn.example.com/icon.png">'
        ),
    }
}


@responses.activate
def test_fetch_recent_articles_extracts_note_hosted_images_only():
    responses.add(
        responses.GET,
        f"{NOTE_API_BASE}/v2/creators/testuser/contents",
        json=LIST_PAYLOAD,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{NOTE_API_BASE}/v3/notes/abc123",
        json=DETAIL_PAYLOAD,
        status=200,
    )

    client = NoteClient("testuser")
    articles = client.fetch_recent_articles(limit=1)

    assert len(articles) == 1
    article = articles[0]
    assert article.key == "abc123"
    assert article.title == "テスト記事"
    assert article.url == "https://note.com/testuser/n/abc123"
    assert article.image_urls == [
        "https://assets.st-note.com/img/eyecatch.png",
        "https://assets.st-note.com/img/inline1.png",
    ]
    assert "本文です" in article.excerpt


@responses.activate
def test_fetch_recent_articles_skips_non_text_note_content():
    responses.add(
        responses.GET,
        f"{NOTE_API_BASE}/v2/creators/testuser/contents",
        json=LIST_PAYLOAD,
        status=200,
        match=[matchers.query_param_matcher({"kind": "note", "page": "1"})],
    )
    responses.add(
        responses.GET,
        f"{NOTE_API_BASE}/v2/creators/testuser/contents",
        json={"data": {"contents": []}},
        status=200,
        match=[matchers.query_param_matcher({"kind": "note", "page": "2"})],
    )
    responses.add(
        responses.GET,
        f"{NOTE_API_BASE}/v3/notes/abc123",
        json=DETAIL_PAYLOAD,
        status=200,
    )

    client = NoteClient("testuser")
    articles = client.fetch_recent_articles(limit=5)

    assert [a.key for a in articles] == ["abc123"]
