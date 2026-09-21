from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests
from requests_oauthlib import OAuth1

UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
TWEET_URL = "https://api.twitter.com/2/tweets"
MAX_CAPTION_LEN = 280


@dataclass
class XCredentials:
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str


class XPoster:
    """Posts an image + caption to X using OAuth1.0a user-context credentials.

    Media upload still requires the v1.1 endpoint; the tweet itself is
    created through the v2 endpoint referencing the uploaded media id.
    """

    def __init__(self, credentials: XCredentials, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self._auth = OAuth1(
            credentials.api_key,
            credentials.api_secret,
            credentials.access_token,
            credentials.access_token_secret,
        )

    def post_image(self, image_bytes: bytes, caption: str) -> str:
        media_id = self._upload_media(image_bytes)
        text = caption[:MAX_CAPTION_LEN]
        resp = self.session.post(
            TWEET_URL,
            json={"text": text, "media": {"media_ids": [media_id]}},
            auth=self._auth,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"]["id"]

    def _upload_media(self, image_bytes: bytes) -> str:
        resp = self.session.post(
            UPLOAD_URL,
            files={"media": image_bytes},
            auth=self._auth,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["media_id_string"]
