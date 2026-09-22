"""Derives a "photo session" identity from an article title.

Articles like "夜撮影会 その④" and "夜撮影会 その⑤" are different write-ups
(different photographer, different note article) of the *same* photo
session -- same shoot, same outfit. Stripping the trailing "その<N>" (and
any decorative emoji) yields a stable key ("夜撮影会") shared by every
article from that session, so we can avoid posting from the same session
on consecutive days even though the underlying article differs.

This is a best-effort heuristic based on the naming convention observed
so far. If article titles start using a different numbering style, this
pattern may need updating.
"""

from __future__ import annotations

import re

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f100-\U0001f1ff"
    "\U00002600-\U000027bf"
    "\U0001f900-\U0001f9ff"
    "\U0001fa70-\U0001faff"
    "\U00002b00-\U00002bff"
    "\U00002190-\U000021ff"
    "]+"
)

_SESSION_SUFFIX_PATTERN = re.compile(
    r"[\s　]*その[0-9０-９①-⑳一二三四五六七八九十百]*[\s　]*$"
)


def session_key(title: str) -> str:
    cleaned = _EMOJI_PATTERN.sub("", title).strip()
    cleaned = _SESSION_SUFFIX_PATTERN.sub("", cleaned).strip()
    return cleaned or title.strip()
