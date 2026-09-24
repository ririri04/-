from io import BytesIO

import responses
from PIL import Image

from note_auto_poster.aspect_ratio import (
    best_matching_group,
    group_by_aspect_ratio,
    image_aspect_ratio,
)


def _png_bytes(width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


@responses.activate
def test_image_aspect_ratio_computes_width_over_height():
    responses.add(responses.GET, "https://example.com/a.png", body=_png_bytes(1080, 1350), status=200)
    ratio = image_aspect_ratio("https://example.com/a.png")
    assert abs(ratio - (1080 / 1350)) < 1e-6


@responses.activate
def test_image_aspect_ratio_returns_none_on_download_failure():
    responses.add(responses.GET, "https://example.com/broken.png", status=404)
    assert image_aspect_ratio("https://example.com/broken.png") is None


@responses.activate
def test_group_by_aspect_ratio_groups_near_identical_ratios():
    # two portrait 4:5 photos with slightly different exact pixel sizes,
    # one square photo, one landscape photo
    responses.add(responses.GET, "https://example.com/1.png", body=_png_bytes(1080, 1350), status=200)
    responses.add(responses.GET, "https://example.com/2.png", body=_png_bytes(1079, 1349), status=200)
    responses.add(responses.GET, "https://example.com/3.png", body=_png_bytes(1080, 1080), status=200)
    responses.add(responses.GET, "https://example.com/4.png", body=_png_bytes(1920, 1080), status=200)

    groups = group_by_aspect_ratio(
        [
            "https://example.com/1.png",
            "https://example.com/2.png",
            "https://example.com/3.png",
            "https://example.com/4.png",
        ]
    )

    portrait_group = next(g for g in groups.values() if "https://example.com/1.png" in g)
    assert set(portrait_group) == {"https://example.com/1.png", "https://example.com/2.png"}


@responses.activate
def test_best_matching_group_returns_largest_group_meeting_min_size():
    responses.add(responses.GET, "https://example.com/1.png", body=_png_bytes(1080, 1350), status=200)
    responses.add(responses.GET, "https://example.com/2.png", body=_png_bytes(1080, 1350), status=200)
    responses.add(responses.GET, "https://example.com/3.png", body=_png_bytes(1080, 1350), status=200)
    responses.add(responses.GET, "https://example.com/4.png", body=_png_bytes(1080, 1080), status=200)

    group = best_matching_group(
        [
            "https://example.com/1.png",
            "https://example.com/2.png",
            "https://example.com/3.png",
            "https://example.com/4.png",
        ],
        min_size=2,
    )

    assert set(group) == {
        "https://example.com/1.png",
        "https://example.com/2.png",
        "https://example.com/3.png",
    }


@responses.activate
def test_best_matching_group_returns_empty_when_no_group_meets_min_size():
    responses.add(responses.GET, "https://example.com/1.png", body=_png_bytes(1080, 1350), status=200)
    responses.add(responses.GET, "https://example.com/2.png", body=_png_bytes(1080, 1080), status=200)

    group = best_matching_group(
        ["https://example.com/1.png", "https://example.com/2.png"], min_size=2
    )

    assert group == []
