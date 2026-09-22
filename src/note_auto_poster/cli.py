from __future__ import annotations

import argparse
import logging
import random
import sys
from dataclasses import replace
from datetime import date, datetime
from typing import List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

import requests

from .captions import INSTAGRAM_CAPTION, X_CAPTION_EVENING, X_CAPTION_MORNING
from .config import Config
from .image_selector import ImageSelector
from .instagram_poster import InstagramCredentials, InstagramPoster
from .note_client import NoteArticle, NoteClient
from .sessions import session_key
from .state import PostedState
from .x_poster import XCredentials, XPoster

logger = logging.getLogger("note_auto_poster")

INITIAL_FETCH_LIMIT = 30
MAX_FETCH_LIMIT = 200
JST = ZoneInfo("Asia/Tokyo")
# midpoint between the 06:00 and 20:00 JST scheduled runs
MORNING_CUTOFF_HOUR = 13


def _current_x_caption() -> str:
    now_jst = datetime.now(JST)
    return X_CAPTION_MORNING if now_jst.hour < MORNING_CUTOFF_HOUR else X_CAPTION_EVENING


def run(config: Config) -> int:
    state = PostedState(config.state_file)
    note_client = NoteClient(config.note_username)
    selector = ImageSelector(config.anthropic_api_key, config.anthropic_model)

    candidates = _gather_candidates(note_client, state)

    today = datetime.now(JST).date()
    recent_article_keys = state.get_recent_article_keys()
    avoid_sessions = state.get_recent_session_keys(today, window_days=3)

    posted_count = 0

    x_pick = _select_candidate(
        candidates,
        exclude_article_keys=set(),
        exclude_sessions=set(),
        recent_article_keys=recent_article_keys,
        avoid_sessions=avoid_sessions,
        target_count=1,
    )
    if config.post_to_x:
        if _handle_x_post(x_pick, config, selector, state, today):
            posted_count += 1
    else:
        logger.info("POST_TO_X=false のためXへの投稿はスキップします")

    ig_exclude_articles = {x_pick[0].key} if x_pick else set()
    ig_exclude_sessions = {session_key(x_pick[0].title)} if x_pick else set()
    ig_pick = _select_candidate(
        candidates,
        exclude_article_keys=ig_exclude_articles,
        exclude_sessions=ig_exclude_sessions,
        recent_article_keys=recent_article_keys,
        avoid_sessions=avoid_sessions,
        target_count=config.instagram_image_count,
    )
    if config.post_to_instagram:
        if _handle_instagram_post(ig_pick, config, selector, state, today):
            posted_count += 1
    else:
        logger.info("POST_TO_INSTAGRAM=false のためInstagramへの投稿はスキップします")

    return posted_count


def _gather_candidates(
    note_client: NoteClient, state: PostedState
) -> List[Tuple[NoteArticle, List[str]]]:
    """Fetches recent articles, pairing each with its not-yet-posted images.
    Fetches progressively deeper into the account's archive until at least
    two distinct usable articles are found (or the account is exhausted),
    so old articles remain in play once recent ones run out of fresh photos.
    """
    limit = INITIAL_FETCH_LIMIT
    while True:
        articles = note_client.fetch_recent_articles(limit=limit)
        candidates = []
        for article in articles:
            unused = [u for u in article.image_urls if not state.is_image_posted(u)]
            if unused:
                candidates.append((article, unused))

        reached_end_of_account = len(articles) < limit
        if len(candidates) >= 2 or reached_end_of_account or limit >= MAX_FETCH_LIMIT:
            return candidates
        limit *= 2


def _select_candidate(
    candidates: List[Tuple[NoteArticle, List[str]]],
    exclude_article_keys: Set[str],
    exclude_sessions: Set[str],
    recent_article_keys: List[str],
    avoid_sessions: Set[str],
    target_count: int,
) -> Optional[Tuple[NoteArticle, List[str]]]:
    # hard exclusions: never pick these within this run (e.g. whatever the
    # other platform just picked, so X and Instagram never share an article
    # or an obviously-the-same-shoot session in one run)
    pool = [
        (a, imgs)
        for a, imgs in candidates
        if a.key not in exclude_article_keys and session_key(a.title) not in exclude_sessions
    ]
    if not pool:
        return None

    # soft preferences, relaxed one at a time until something is left:
    # 1) not a recently-used article AND not a recently-used session
    # 2) not a recently-used session (a different article from the same
    #    recent session is still fine here, just not preferred)
    # 3) not a recently-used article
    # 4) anything in the hard-filtered pool
    tiers = [
        [p for p in pool if p[0].key not in recent_article_keys and session_key(p[0].title) not in avoid_sessions],
        [p for p in pool if session_key(p[0].title) not in avoid_sessions],
        [p for p in pool if p[0].key not in recent_article_keys],
        pool,
    ]
    search_pool = next((tier for tier in tiers if tier), pool)

    # among articles that can fully satisfy the target count, pick randomly
    # (rather than always the newest) so usage spreads across the archive
    full = [p for p in search_pool if len(p[1]) >= target_count]
    if full:
        return random.choice(full)

    max_len = max(len(imgs) for _, imgs in search_pool)
    best = [p for p in search_pool if len(p[1]) == max_len]
    return random.choice(best)


def _handle_x_post(
    pick: Optional[Tuple[NoteArticle, List[str]]],
    config: Config,
    selector: ImageSelector,
    state: PostedState,
    today: date,
) -> bool:
    if pick is None:
        logger.info("X用に投稿できる新しい画像が見つかりませんでした")
        return False

    article, unused_images = pick
    chosen = selector.select(article.title, article.excerpt, unused_images, article.url, count=1)
    if not chosen:
        logger.info("X用の画像選定に失敗しました(記事「%s」 / %s)", article.title, article.key)
        return False

    logger.info("X用に記事「%s」(%s)から画像を選定しました: %s", article.title, article.key, chosen[0])
    caption = _current_x_caption()

    if config.dry_run:
        logger.info("[dry-run] X投稿予定: %s\nキャプション:\n%s", chosen[0], caption)
        return False

    if not config.twitter_api_key:
        logger.info("X用の認証情報が未設定のためスキップします")
        return False

    post_id = _post_to_x(config, chosen[0], caption)
    if post_id is None:
        return False

    state.mark_images_posted(chosen)
    state.record_article_use(article.key)
    state.record_session_use(today, session_key(article.title))
    logger.info("posted to X: %s (記事「%s」)", post_id, article.title)
    return True


def _handle_instagram_post(
    pick: Optional[Tuple[NoteArticle, List[str]]],
    config: Config,
    selector: ImageSelector,
    state: PostedState,
    today: date,
) -> bool:
    if pick is None:
        logger.info("Instagram用に投稿できる新しい画像が見つかりませんでした")
        return False

    article, unused_images = pick
    target = min(config.instagram_image_count, len(unused_images))
    chosen = selector.select(article.title, article.excerpt, unused_images, article.url, count=target)
    if not chosen:
        logger.info("Instagram用の画像選定に失敗しました(記事「%s」 / %s)", article.title, article.key)
        return False

    logger.info(
        "Instagram用に記事「%s」(%s)から%d枚選定しました: %s",
        article.title,
        article.key,
        len(chosen),
        chosen,
    )

    if config.dry_run:
        logger.info("[dry-run] Instagram投稿予定: %s\nキャプション:\n%s", chosen, INSTAGRAM_CAPTION)
        return False

    if not config.ig_access_token:
        logger.info("Instagram用の認証情報が未設定のためスキップします")
        return False

    post_id = _post_to_instagram(config, chosen)
    if post_id is None:
        return False

    state.mark_images_posted(chosen)
    state.record_article_use(article.key)
    state.record_session_use(today, session_key(article.title))
    logger.info("posted to Instagram: %s (記事「%s」)", post_id, article.title)
    return True


def _post_to_x(config: Config, image_url: str, caption: str) -> Optional[str]:
    try:
        image_bytes = requests.get(image_url, timeout=15).content
        poster = XPoster(
            XCredentials(
                config.twitter_api_key,
                config.twitter_api_secret,
                config.twitter_access_token,
                config.twitter_access_token_secret,
            )
        )
        return poster.post_image(image_bytes, caption)
    except Exception:
        logger.exception("failed to post to X")
        return None


def _post_to_instagram(config: Config, image_urls: List[str]) -> Optional[str]:
    try:
        poster = InstagramPoster(InstagramCredentials(config.ig_access_token, config.ig_user_id))
        if len(image_urls) == 1:
            return poster.post_image(image_urls[0], INSTAGRAM_CAPTION)
        return poster.post_carousel(image_urls, INSTAGRAM_CAPTION)
    except Exception:
        logger.exception("failed to post to Instagram")
        return None


def _list_articles(config: Config, limit: int) -> int:
    client = NoteClient(config.note_username)
    for article in client.fetch_recent_articles(limit=limit):
        print(f"- {article.title} ({article.url})")
        for url in article.image_urls:
            print(f"    image: {url}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="note.com の画像をAIが選んでX/Instagramに自動投稿する"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Xに1枚、Instagramに複数枚(別記事から)投稿する")
    run_parser.add_argument(
        "--dry-run", action="store_true", help="実際には投稿せず選定結果のみ表示する"
    )

    list_parser = sub.add_parser("list", help="直近の記事と画像候補を表示する")
    list_parser.add_argument("--limit", type=int, default=5)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = Config.from_env()

    if args.command == "run":
        if args.dry_run:
            config = replace(config, dry_run=True)
        count = run(config)
        logger.info("done: %d platform(s) posted", count)
        return 0

    if args.command == "list":
        return _list_articles(config, args.limit)

    return 1


if __name__ == "__main__":
    sys.exit(main())
