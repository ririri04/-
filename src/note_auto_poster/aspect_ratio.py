"""Groups image URLs by aspect ratio, so callers can pick a set of photos
that will lay out consistently together (e.g. a 2-photo X post)."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Dict, List, Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# ratios within this fraction of each other are treated as "the same"
RATIO_BUCKET_SIZE = 0.05


def image_aspect_ratio(url: str, session: Optional[requests.Session] = None) -> Optional[float]:
    session = session or requests.Session()
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        image = Image.open(BytesIO(resp.content))
        width, height = image.size
        if height == 0:
            return None
        return width / height
    except Exception:
        logger.exception("failed to inspect image dimensions for %s", url)
        return None


def _bucket(ratio: float) -> float:
    return round(ratio / RATIO_BUCKET_SIZE) * RATIO_BUCKET_SIZE


def group_by_aspect_ratio(
    image_urls: List[str], session: Optional[requests.Session] = None
) -> Dict[float, List[str]]:
    session = session or requests.Session()
    groups: Dict[float, List[str]] = {}
    for url in image_urls:
        ratio = image_aspect_ratio(url, session)
        if ratio is None:
            continue
        groups.setdefault(_bucket(ratio), []).append(url)
    return groups


def best_matching_group(
    image_urls: List[str], min_size: int = 2, session: Optional[requests.Session] = None
) -> List[str]:
    """Returns the largest set of image URLs that share an aspect ratio,
    or an empty list if no such set of at least `min_size` exists."""
    groups = group_by_aspect_ratio(image_urls, session)
    eligible = [g for g in groups.values() if len(g) >= min_size]
    if not eligible:
        return []
    return max(eligible, key=len)
