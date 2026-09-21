import json

import responses

from note_auto_poster.x_poster import TWEET_URL, UPLOAD_URL, XCredentials, XPoster


@responses.activate
def test_post_image_uploads_then_tweets():
    responses.add(responses.POST, UPLOAD_URL, json={"media_id_string": "999"}, status=200)
    responses.add(responses.POST, TWEET_URL, json={"data": {"id": "111"}}, status=201)

    poster = XPoster(XCredentials("k", "s", "at", "ats"))
    tweet_id = poster.post_image(b"fake-image-bytes", "hello world")

    assert tweet_id == "111"
    assert len(responses.calls) == 2

    tweet_call = responses.calls[1]
    body = json.loads(tweet_call.request.body)
    assert body["text"] == "hello world"
    assert body["media"]["media_ids"] == ["999"]


@responses.activate
def test_post_image_truncates_caption_to_280_chars():
    responses.add(responses.POST, UPLOAD_URL, json={"media_id_string": "999"}, status=200)
    responses.add(responses.POST, TWEET_URL, json={"data": {"id": "111"}}, status=201)

    poster = XPoster(XCredentials("k", "s", "at", "ats"))
    long_caption = "a" * 500
    poster.post_image(b"fake-image-bytes", long_caption)

    body = json.loads(responses.calls[1].request.body)
    assert len(body["text"]) == 280
