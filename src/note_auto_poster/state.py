from __future__ import annotations

import json
import os
import threading
from typing import Iterable, Optional


class PostedState:
    """Tracks which note.com images have already been posted (so a photo is
    never reused across posts) and which article was last used per platform
    (so back-to-back posts prefer a different article when possible)."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {"posted_image_urls": [], "last_article_key": {}}
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _migrate(raw)

    def save(self) -> None:
        with self._lock:
            tmp_path = f"{self.path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)

    def is_image_posted(self, image_url: str) -> bool:
        return image_url in self._data["posted_image_urls"]

    def mark_images_posted(self, image_urls: Iterable[str]) -> None:
        existing = set(self._data["posted_image_urls"])
        for url in image_urls:
            if url not in existing:
                self._data["posted_image_urls"].append(url)
                existing.add(url)
        self.save()

    def get_last_article_key(self, platform: str) -> Optional[str]:
        return self._data["last_article_key"].get(platform)

    def set_last_article_key(self, platform: str, article_key: str) -> None:
        self._data["last_article_key"][platform] = article_key
        self.save()


def _migrate(raw: dict) -> dict:
    if "posted_image_urls" in raw:
        raw.setdefault("last_article_key", {})
        return raw

    # old schema: {"posted_articles": {key: {"image_url": ..., ...}}}
    posted_image_urls = []
    for entry in raw.get("posted_articles", {}).values():
        image_url = entry.get("image_url")
        if image_url and image_url not in posted_image_urls:
            posted_image_urls.append(image_url)

    return {"posted_image_urls": posted_image_urls, "last_article_key": {}}
