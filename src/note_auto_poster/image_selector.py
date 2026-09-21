from __future__ import annotations

import base64
import json
import logging
from io import BytesIO
from typing import List, Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

MAX_IMAGE_EDGE = 1024
MAX_CANDIDATES = 10

SELECTION_PROMPT_TEMPLATE = (
    "あなたはnote記事からSNS投稿用の画像を選ぶ担当者です。\n"
    "記事タイトル: {title}\n"
    "記事概要: {excerpt}\n"
    "記事URL: {article_url}\n\n"
    "以下の画像候補の中から、SNS投稿に最も適した画像を{count}枚選んでください。"
    "判断基準: 視覚的な魅力、記事内容との関連性、文字が小さすぎたり読みにくい"
    "スクリーンショットではないこと、結論部分のネタバレにならないこと。\n"
    "各画像には0始まりのインデックス番号を付けています。\n"
    "回答は次のJSON形式のみで返してください(前置きや説明文は不要):\n"
    '{{"selected_indices": [<おすすめ順に並べた最大{count}個のint>], "reason": "<選定理由>"}}'
)


class ImageSelector:
    """Picks the best `count` social-media images for an article using Claude
    vision. Falls back to the first `count` candidates when no API key is
    configured or the model call fails, so the pipeline keeps working even
    without AI selection configured.
    """

    def __init__(
        self,
        api_key: Optional[str],
        model: str = "claude-sonnet-5",
        session: Optional[requests.Session] = None,
    ):
        self.model = model
        self.session = session or requests.Session()
        self._client = None
        if api_key:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)

    def select(
        self,
        title: str,
        excerpt: str,
        image_urls: List[str],
        article_url: str,
        count: int = 1,
    ) -> List[str]:
        candidates = image_urls[:MAX_CANDIDATES]
        if not candidates:
            return []
        if self._client is None:
            return candidates[:count]

        downloaded = [
            (url, data)
            for url, data in ((u, self._download_and_resize(u)) for u in candidates)
            if data is not None
        ]
        if not downloaded:
            return []

        try:
            parsed = self._ask_claude(title, excerpt, article_url, downloaded, count)
            indices = parsed["selected_indices"][:count]
            urls = [downloaded[i][0] for i in indices if isinstance(i, int) and 0 <= i < len(downloaded)]
            return urls or [u for u, _ in downloaded[:count]]
        except Exception:
            logger.exception("AI image selection failed, falling back to heuristic")
            return [u for u, _ in downloaded[:count]]

    def _ask_claude(self, title, excerpt, article_url, downloaded, count) -> dict:
        content: list = [
            {
                "type": "text",
                "text": SELECTION_PROMPT_TEMPLATE.format(
                    title=title, excerpt=excerpt, article_url=article_url, count=count
                ),
            }
        ]
        for idx, (_url, data) in enumerate(downloaded):
            content.append({"type": "text", "text": f"画像インデックス {idx}:"})
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": data},
                }
            )

        response = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        return _parse_json(text)

    def _download_and_resize(self, url: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            image = Image.open(BytesIO(resp.content)).convert("RGB")
            image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode("ascii")
        except Exception:
            logger.exception("failed to download/resize image %s", url)
            return None


def _parse_json(text: str) -> dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"could not find JSON object in response: {text!r}")
    return json.loads(text[start : end + 1])
