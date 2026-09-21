from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from typing import List, Optional, Set, Tuple

import requests

from .captions import INSTAGRAM_CAPTION, X_CAPTION
from .config import Config
from .image_selector import ImageSelector
from .instagram_poster import InstagramCredentials, InstagramPoster
from .note_client import NoteArticle, NoteClient
from .state import PostedState
from .x_poster import XCredentials, XPoster

logger = logging.getLogger("note_auto_poster")

INITIAL_FETCH_LIMIT = 20
MAX_FETCH_LIMIT = 200


def run(config: Config) -> int:
    state = PostedState(config.state_file)
    note_client = NoteClient(config.note_username)
    selector = ImageSelector(config.anthropic_api_key, config.anthropic_model)

    candidates = _gather_candidates(note_client, state)

    posted_count = 0

    x_pick = _select_candidate(
        candidates,
        exclude_article_keys=set(),
        last_article_key=state.get_last_article_key("x"),
        target_count=1,
    )
    if config.post_to_x:
        if _handle_x_post(x_pick, config, selector, state):
            posted_count += 1
    else:
        logger.info("POST_TO_X=false のためXへの投稿はスキップします")

    ig_exclude = {x_pick[0].key} if x_pick else set()
    ig_pick = _select_candidate(
        candidates,
        exclude_article_keys=ig_exclude,
        last_article_key=state.get_last_article_key("instagram"),
        target_count=config.instagram_image_count,
    )
    if config.post_to_instagram:
        if _handle_instagram_post(ig_pick, config, selector, state):
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
    last_article_key: Optional[str],
    target_count: int,
) -> Optional[Tuple[NoteArticle, List[str]]]:
    pool = [(a, imgs) for a, imgs in candidates if a.key not in exclude_article_keys]
    if not pool:
        return None

    # prefer a different article than the one used last time for this platform
    fresh = [p for p in pool if p[0].key != last_article_key]
    search_pool = fresh or pool

    # prefer an article that can fully satisfy the target count
    full = [p for p in search_pool if len(p[1]) >= target_count]
    if full:
        return full[0]

    return max(search_pool, key=lambda p: len(p[1]))


def _handle_x_post(
    pick: Optional[Tuple[NoteArticle, List[str]]],
    config: Config,
    selector: ImageSelector,
    state: PostedState,
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

    if config.dry_run:
        logger.info("[dry-run] X投稿予定: %s\nキャプション:\n%s", chosen[0], X_CAPTION)
        return False

    if not config.twitter_api_key:
        logger.info("X用の認証情報が未設定のためスキップします")
        return False

    post_id = _post_to_x(config, chosen[0])
    if post_id is None:
        return False

    state.mark_images_posted(chosen)
    state.set_last_article_key("x", article.key)
    logger.info("posted to X: %s (記事「%s」)", post_id, article.title)
    return True


def _handle_instagram_post(
    pick: Optional[Tuple[NoteArticle, List[str]]],
    config: Config,
    selector: ImageSelector,
    state: PostedState,
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
    state.set_last_article_key("instagram", article.key)
    logger.info("posted to Instagram: %s (記事「%s」)", post_id, article.title)
    return True


def _post_to_x(config: Config, image_url: str) -> Optional[str]:
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
        return poster.post_image(image_bytes, X_CAPTION)
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
