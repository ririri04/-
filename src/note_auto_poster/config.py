from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    note_username: str

    anthropic_api_key: Optional[str]
    anthropic_model: str

    twitter_api_key: Optional[str]
    twitter_api_secret: Optional[str]
    twitter_access_token: Optional[str]
    twitter_access_token_secret: Optional[str]

    ig_access_token: Optional[str]
    ig_user_id: Optional[str]

    post_to_x: bool
    post_to_instagram: bool
    max_articles_per_run: int
    state_file: str
    dry_run: bool

    @classmethod
    def from_env(cls) -> "Config":
        note_username = os.getenv("NOTE_USERNAME", "").strip()
        if not note_username:
            raise ValueError("NOTE_USERNAME is required (set it in .env)")

        return cls(
            note_username=note_username,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
            twitter_api_key=os.getenv("TWITTER_API_KEY") or None,
            twitter_api_secret=os.getenv("TWITTER_API_SECRET") or None,
            twitter_access_token=os.getenv("TWITTER_ACCESS_TOKEN") or None,
            twitter_access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET") or None,
            ig_access_token=os.getenv("IG_ACCESS_TOKEN") or None,
            ig_user_id=os.getenv("IG_USER_ID") or None,
            post_to_x=_bool_env("POST_TO_X", True),
            post_to_instagram=_bool_env("POST_TO_INSTAGRAM", True),
            max_articles_per_run=int(os.getenv("MAX_ARTICLES_PER_RUN", "1")),
            state_file=os.getenv("STATE_FILE", "state.json"),
            dry_run=_bool_env("DRY_RUN", False),
        )
