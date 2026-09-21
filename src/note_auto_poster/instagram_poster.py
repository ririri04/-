from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.instagram.com/v21.0"
PUBLISH_POLL_ATTEMPTS = 10
PUBLISH_POLL_DELAY_SECONDS = 3


@dataclass
class InstagramCredentials:
    access_token: str
    ig_user_id: str


class InstagramPoster:
    """Posts an image + caption via the Instagram API with Instagram Login
    (content publishing on graph.instagram.com).

    Uses an Instagram-scoped access token obtained through Instagram Business
    Login, so no linked Facebook Page is required. The image is referenced by
    URL rather than uploaded directly, so it must already be publicly
    reachable -- note.com's asset CDN URLs qualify.
    """

    def __init__(self, credentials: InstagramCredentials, session: Optional[requests.Session] = None):
        self.credentials = credentials
        self.session = session or requests.Session()

    def post_image(self, image_url: str, caption: str) -> str:
        creation_id = self._create_container(image_url, caption)
        self._wait_until_ready(creation_id)
        return self._publish(creation_id)

    def post_carousel(self, image_urls: list[str], caption: str) -> str:
        if len(image_urls) < 2:
            return self.post_image(image_urls[0], caption)

        child_ids = []
        for url in image_urls:
            child_id = self._create_container(url, caption=None, is_carousel_item=True)
            self._wait_until_ready(child_id)
            child_ids.append(child_id)

        creation_id = self._create_carousel_container(child_ids, caption)
        self._wait_until_ready(creation_id)
        return self._publish(creation_id)

    def _create_container(
        self, image_url: str, caption: Optional[str], is_carousel_item: bool = False
    ) -> str:
        url = f"{GRAPH_API_BASE}/{self.credentials.ig_user_id}/media"
        data = {
            "image_url": image_url,
            "access_token": self.credentials.access_token,
        }
        if caption is not None:
            data["caption"] = caption
        if is_carousel_item:
            data["is_carousel_item"] = "true"
        resp = self.session.post(url, data=data, timeout=30)
        resp.raise_for_status()
        return resp.json()["id"]

    def _create_carousel_container(self, child_ids: list[str], caption: str) -> str:
        url = f"{GRAPH_API_BASE}/{self.credentials.ig_user_id}/media"
        resp = self.session.post(
            url,
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
                "access_token": self.credentials.access_token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _wait_until_ready(self, creation_id: str) -> None:
        url = f"{GRAPH_API_BASE}/{creation_id}"
        for _ in range(PUBLISH_POLL_ATTEMPTS):
            resp = self.session.get(
                url,
                params={"fields": "status_code", "access_token": self.credentials.access_token},
                timeout=15,
            )
            resp.raise_for_status()
            status = resp.json().get("status_code")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise RuntimeError(f"Instagram media container {creation_id} failed processing")
            time.sleep(PUBLISH_POLL_DELAY_SECONDS)
        logger.warning(
            "Instagram container %s not confirmed FINISHED after polling; attempting publish anyway",
            creation_id,
        )

    def _publish(self, creation_id: str) -> str:
        url = f"{GRAPH_API_BASE}/{self.credentials.ig_user_id}/media_publish"
        resp = self.session.post(
            url,
            data={"creation_id": creation_id, "access_token": self.credentials.access_token},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["id"]
