import pytest
import responses

from note_auto_poster.instagram_poster import (
    GRAPH_API_BASE,
    InstagramCredentials,
    InstagramPoster,
)


@responses.activate
def test_post_image_creates_container_and_publishes():
    creds = InstagramCredentials(access_token="tok", ig_user_id="123")
    responses.add(
        responses.POST,
        f"{GRAPH_API_BASE}/123/media",
        json={"id": "container1"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{GRAPH_API_BASE}/container1",
        json={"status_code": "FINISHED"},
        status=200,
    )
    responses.add(
        responses.POST,
        f"{GRAPH_API_BASE}/123/media_publish",
        json={"id": "media1"},
        status=200,
    )

    poster = InstagramPoster(creds)
    media_id = poster.post_image("https://example.com/img.png", "caption")

    assert media_id == "media1"


@responses.activate
def test_post_image_raises_on_container_error_status():
    creds = InstagramCredentials(access_token="tok", ig_user_id="123")
    responses.add(
        responses.POST,
        f"{GRAPH_API_BASE}/123/media",
        json={"id": "container1"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{GRAPH_API_BASE}/container1",
        json={"status_code": "ERROR"},
        status=200,
    )

    poster = InstagramPoster(creds)
    with pytest.raises(RuntimeError):
        poster.post_image("https://example.com/img.png", "caption")
