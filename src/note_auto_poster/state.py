from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional


class PostedState:
    """Tracks which note.com articles have already been posted, so repeated
    runs never post the same article twice."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {"posted_articles": {}}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self) -> None:
        with self._lock:
            tmp_path = f"{self.path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)

    def is_posted(self, article_key: str) -> bool:
        return article_key in self._data["posted_articles"]

    def mark_posted(
        self,
        article_key: str,
        image_url: str,
        x_post_id: Optional[str] = None,
        ig_post_id: Optional[str] = None,
    ) -> None:
        self._data["posted_articles"][article_key] = {
            "image_url": image_url,
            "x_post_id": x_post_id,
            "ig_post_id": ig_post_id,
            "posted_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()
