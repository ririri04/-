from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace

import requests

from .config import Config
from .image_selector import ImageSelector
from .instagram_poster import InstagramCredentials, InstagramPoster
from .note_client import NoteArticle, NoteClient
from .state import PostedState
from .x_poster import XCredentials, XPoster

logger = logging.getLogger("note_auto_poster")


def run(config: Config) -> int:
    state = PostedState(config.state_file)
    note_client = NoteClient(config.note_username)
    selector = ImageSelector(config.anthropic_api_key, config.anthropic_model)

    # over-fetch since some recent articles may already be posted or have no images
    articles = note_client.fetch_recent_articles(limit=max(config.max_articles_per_run * 3, 5))

    posted_count = 0
    for article in articles:
        if posted_count >= config.max_articles_per_run:
            break
        if state.is_posted(article.key):
            continue
        if not article.image_urls:
            logger.info("skip %s: no eligible images", article.key)
            continue

        _process_article(article, config, selector, state)
        posted_count += 1

    return posted_count


def _process_article(article: NoteArticle, config: Config, selector: ImageSelector, state: PostedState) -> None:
    selection = selector.select(article.title, article.excerpt, article.image_urls, article.url)
    if selection is None:
        logger.info("skip %s: no image selected", article.key)
        return

    logger.info("selected image for %s: %s (%s)", article.key, selection.image_url, selection.reason)

    x_post_id = None
    ig_post_id = None

    if config.dry_run:
        logger.info("[dry-run] would post to X: %s", selection.caption_x)
        logger.info("[dry-run] would post to Instagram: %s", selection.caption_instagram)
    else:
        if config.post_to_x and config.twitter_api_key:
            x_post_id = _post_to_x(config, selection)
        if config.post_to_instagram and config.ig_access_token:
            ig_post_id = _post_to_instagram(config, selection)

    state.mark_posted(article.key, selection.image_url, x_post_id, ig_post_id)


def _post_to_x(config: Config, selection) -> str | None:
    try:
        image_bytes = requests.get(selection.image_url, timeout=15).content
        poster = XPoster(
            XCredentials(
                config.twitter_api_key,
                config.twitter_api_secret,
                config.twitter_access_token,
                config.twitter_access_token_secret,
            )
        )
        post_id = poster.post_image(image_bytes, selection.caption_x)
        logger.info("posted to X: %s", post_id)
        return post_id
    except Exception:
        logger.exception("failed to post to X")
        return None


def _post_to_instagram(config: Config, selection) -> str | None:
    try:
        poster = InstagramPoster(InstagramCredentials(config.ig_access_token, config.ig_user_id))
        post_id = poster.post_image(selection.image_url, selection.caption_instagram)
        logger.info("posted to Instagram: %s", post_id)
        return post_id
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

    run_parser = sub.add_parser("run", help="新着記事をチェックして投稿する")
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
        logger.info("done: %d article(s) processed", count)
        return 0

    if args.command == "list":
        return _list_articles(config, args.limit)

    return 1


if __name__ == "__main__":
    sys.exit(main())
