from __future__ import annotations

import json
import os
import threading
from datetime import date, timedelta
from typing import Iterable, List, Set

RECENT_ARTICLE_HISTORY = 6
SESSION_HISTORY_RETENTION_DAYS = 14


class PostedState:
    """Tracks which note.com images have already been posted (so a photo is
    never reused across posts), a short combined history of recently used
    articles across both platforms (so back-to-back posts prefer a
    different article), and which "photo session" (see sessions.py) was
    used on which date (so the same session -- and therefore the same
    outfit -- doesn't get posted on consecutive days)."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {"posted_image_urls": [], "recent_article_keys": [], "session_history": {}}
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

    def get_recent_article_keys(self) -> List[str]:
        return list(self._data["recent_article_keys"])

    def record_article_use(self, article_key: str) -> None:
        keys = self._data["recent_article_keys"]
        keys.append(article_key)
        del keys[:-RECENT_ARTICLE_HISTORY]
        self.save()

    def get_recent_session_keys(self, today: date, window_days: int = 3) -> Set[str]:
        cutoff = today - timedelta(days=window_days - 1)
        keys: Set[str] = set()
        for date_str, sessions in self._data["session_history"].items():
            parsed = _parse_date(date_str)
            if parsed is not None and parsed >= cutoff:
                keys.update(sessions)
        return keys

    def record_session_use(self, today: date, session: str) -> None:
        history = self._data["session_history"]
        date_str = today.isoformat()
        day_sessions = history.setdefault(date_str, [])
        if session not in day_sessions:
            day_sessions.append(session)

        cutoff = today - timedelta(days=SESSION_HISTORY_RETENTION_DAYS)
        for stale in [d for d in history if (_parse_date(d) or cutoff) < cutoff]:
            del history[stale]

        self.save()


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _migrate(raw: dict) -> dict:
    if "posted_image_urls" in raw and "recent_article_keys" in raw:
        raw.setdefault("session_history", {})
        return raw

    posted_image_urls = list(raw.get("posted_image_urls", []))
    recent_article_keys = list(raw.get("recent_article_keys", []))

    # oldest schema: {"posted_articles": {key: {"image_url": ..., ...}}}
    for entry in raw.get("posted_articles", {}).values():
        image_url = entry.get("image_url")
        if image_url and image_url not in posted_image_urls:
            posted_image_urls.append(image_url)

    # intermediate schema: {"last_article_key": {"x": ..., "instagram": ...}}
    for key in raw.get("last_article_key", {}).values():
        if key and key not in recent_article_keys:
            recent_article_keys.append(key)
    del recent_article_keys[:-RECENT_ARTICLE_HISTORY]

    return {
        "posted_image_urls": posted_image_urls,
        "recent_article_keys": recent_article_keys,
        "session_history": raw.get("session_history", {}),
    }
