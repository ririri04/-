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


@responses.activate
def test_post_carousel_creates_children_then_publishes():
    creds = InstagramCredentials(access_token="tok", ig_user_id="123")
    image_urls = [
        "https://example.com/1.png",
        "https://example.com/2.png",
        "https://example.com/3.png",
    ]

    for i in range(3):
        responses.add(
            responses.POST,
            f"{GRAPH_API_BASE}/123/media",
            json={"id": f"child{i}"},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{GRAPH_API_BASE}/child{i}",
            json={"status_code": "FINISHED"},
            status=200,
        )

    responses.add(
        responses.POST,
        f"{GRAPH_API_BASE}/123/media",
        json={"id": "carousel1"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{GRAPH_API_BASE}/carousel1",
        json={"status_code": "FINISHED"},
        status=200,
    )
    responses.add(
        responses.POST,
        f"{GRAPH_API_BASE}/123/media_publish",
        json={"id": "media_carousel"},
        status=200,
    )

    poster = InstagramPoster(creds)
    media_id = poster.post_carousel(image_urls, "caption")

    assert media_id == "media_carousel"

    carousel_create_call = responses.calls[6]
    body = carousel_create_call.request.body
    assert "media_type=CAROUSEL" in body
    assert "children=child0%2Cchild1%2Cchild2" in body


@responses.activate
def test_post_carousel_with_single_image_falls_back_to_post_image():
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
    media_id = poster.post_carousel(["https://example.com/img.png"], "caption")

    assert media_id == "media1"
