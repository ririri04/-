import json

import pytest
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


@responses.activate
def test_post_images_uploads_each_then_tweets_once():
    responses.add(responses.POST, UPLOAD_URL, json={"media_id_string": "111"}, status=200)
    responses.add(responses.POST, UPLOAD_URL, json={"media_id_string": "222"}, status=200)
    responses.add(responses.POST, TWEET_URL, json={"data": {"id": "999"}}, status=201)

    poster = XPoster(XCredentials("k", "s", "at", "ats"))
    tweet_id = poster.post_images([b"img1", b"img2"], "2枚組です")

    assert tweet_id == "999"
    assert len(responses.calls) == 3

    tweet_call = responses.calls[2]
    body = json.loads(tweet_call.request.body)
    assert body["text"] == "2枚組です"
    assert body["media"]["media_ids"] == ["111", "222"]


def test_post_images_rejects_empty_list():
    poster = XPoster(XCredentials("k", "s", "at", "ats"))
    with pytest.raises(ValueError):
        poster.post_images([], "caption")


def test_post_images_rejects_more_than_four():
    poster = XPoster(XCredentials("k", "s", "at", "ats"))
    with pytest.raises(ValueError):
        poster.post_images([b"1", b"2", b"3", b"4", b"5"], "caption")
