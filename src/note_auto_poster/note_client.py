from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

NOTE_API_BASE = "https://note.com/api"

# note is an article's inline/eyecatch images are served from this asset CDN.
# Filtering on it keeps out unrelated icons, avatars and emoji served from
# other note.com domains.
NOTE_IMAGE_HOST = "assets.st-note.com"

MAX_LIST_PAGES = 20


@dataclass
class NoteArticle:
    key: str
    title: str
    url: str
    published_at: Optional[str]
    excerpt: str = ""
    image_urls: List[str] = field(default_factory=list)


class NoteClient:
    """Reads a creator's public articles from note.com's unofficial JSON API."""

    def __init__(self, username: str, session: Optional[requests.Session] = None, timeout: int = 15):
        self.username = username
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch_recent_articles(self, limit: int = 5) -> List[NoteArticle]:
        stubs: List[NoteArticle] = []
        page = 1
        while len(stubs) < limit and page <= MAX_LIST_PAGES:
            contents = self._fetch_list_page(page)
            if not contents:
                break
            for item in contents:
                if item.get("type") not in (None, "TextNote"):
                    # skip magazines/memberships/other non-article content
                    continue
                key = item.get("key")
                if not key:
                    continue
                stubs.append(self._to_stub(item))
                if len(stubs) >= limit:
                    break
            page += 1
        return [self._hydrate(article) for article in stubs]

    def _fetch_list_page(self, page: int) -> list:
        url = f"{NOTE_API_BASE}/v2/creators/{self.username}/contents"
        resp = self.session.get(url, params={"kind": "note", "page": page}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("contents", [])

    def _to_stub(self, item: dict) -> NoteArticle:
        key = item["key"]
        return NoteArticle(
            key=key,
            title=item.get("name", ""),
            url=f"https://note.com/{self.username}/n/{key}",
            published_at=item.get("publish_at") or item.get("publishAt"),
        )

    def _hydrate(self, article: NoteArticle) -> NoteArticle:
        data = self._fetch_detail(article.key)
        body_html = data.get("body") or ""
        images = self._extract_image_urls(body_html)
        eyecatch = data.get("eyecatch")
        if eyecatch and NOTE_IMAGE_HOST in eyecatch and eyecatch not in images:
            images.insert(0, eyecatch)
        article.excerpt = _strip_html(body_html)[:280]
        article.image_urls = images
        return article

    def _fetch_detail(self, key: str) -> dict:
        url = f"{NOTE_API_BASE}/v3/notes/{key}"
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("data", {})

    @staticmethod
    def _extract_image_urls(body_html: str) -> List[str]:
        soup = BeautifulSoup(body_html, "html.parser")
        urls: List[str] = []
        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("src")
            if not src or NOTE_IMAGE_HOST not in src:
                continue
            if src not in urls:
                urls.append(src)
        return urls


def _strip_html(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
