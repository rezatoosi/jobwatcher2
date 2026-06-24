"""CLI commands for Reddit post monitoring.

These are thin presentation wrappers: they load config, drive the core
pipeline, and print results. All processing logic lives in
`src.interfaces.core.pipeline`.
"""

from pathlib import Path
from typing import Optional

from src.config import load_config
from src.interfaces.core.pipeline import FetchPipeline, ScoredPost
from src.scoring.ai import AIScoringError
from src.storage.database import Database

_DB_PATH = "posts.db"


def cmd_fetch(config_path: Path = Path("config.yaml")) -> None:
    """Fetch new posts from Reddit and process them through the pipeline."""
    config = load_config(config_path)

    print("Configuration loaded:")
    print(f"  Subreddits: {', '.join(config.subreddits)}")
    print(f"  Keywords: {len(config.keywords)} keywords")
    print(f"  Keyword threshold: {config.scoring.keyword_threshold}")
    print(f"  Fetch limit: {config.fetch_limit}")

    db = Database(_DB_PATH)
    pipeline = FetchPipeline(config, db)

    print(f"  AI scoring: {'enabled' if pipeline.ai_scorer else 'disabled'}")
    print()
    print("Fetching posts from Reddit...")

    def _on_ai_scored(idx: int, total: int, scored: ScoredPost) -> None:
        post = scored.post
        is_relevant = bool(
            scored.ai_metadata and scored.ai_metadata.get("is_relevant") == 1
        )
        mark = "✓" if is_relevant else "·"
        print(f"  [{idx}/{total}] {mark} [{post.subreddit}] {post.title[:50]}")

    try:
        report = pipeline.run(progress=_on_ai_scored)
    except AIScoringError as e:
        print(f"  ✗ AI scoring aborted, batch stopped: {e}")
        return
    except Exception as e:
        print(f"  ✗ Error during fetch: {e}")
        return

    pipeline.persist(report)

    if report.accepted:
        print()
        print("Accepted posts:")
        for sp in report.accepted:
            post = sp.post
            keywords = ", ".join(sp.matched_keywords)
            print(f"  ✓ [{post.subreddit}] {post.title[:50]}...")
            print(f"    Score: {sp.score} | Keywords: {keywords}")

    print()
    print("=== Fetch Summary ===\n")
    print(f"Total fetched:       {report.total_fetched}")
    print(f"Filtered out:        {report.filtered_out}")
    print(f"Duplicates skipped:  {report.duplicates}")
    print(f"Keyword passed:      {report.keyword_passed}")
    print(f"Accepted:            {report.accepted_count}")
    print(f"Rejected:            {report.rejected_count}")
    print("=" * 10)


def cmd_view(
    show_accepted: bool = True,
    show_rejected: bool = False,
    limit: Optional[int] = None,
) -> None:
    """View posts from database."""
    db = Database(_DB_PATH)

    if show_accepted:
        print("=== Accepted Posts ===\n")
        posts = db.get_all_posts(limit=limit)
        if not posts:
            print("No accepted posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                print(f"{idx}. [/r/{post['subreddit']}]: {post['title']}")
                print(f"   Score: {post['score']} | Keywords: {post['matched_keywords']}")
                print(f"   URL: {post['url']}")
                print(f"   Created: {post['created_at']}")
                if post['body']:
                    body_preview = post['body'][:150].replace('\n', ' ')
                    suffix = '...' if len(post['body']) > 150 else ''
                    print(f"   Body: {body_preview}{suffix}")
                print()

    if show_rejected:
        print("=== Rejected Posts ===\n")
        posts = db.get_rejected_posts(limit=limit)
        if not posts:
            print("No rejected posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                print(f"{idx}. [/r/{post['subreddit']}]: {post['title']}")
                print(f"   Score: {post['score']} | Keywords: {post['matched_keywords']}")
                print(f"   URL: {post['url']}")
                print(f"   Rejected: {post['rejected_at']}")
                print()


def cmd_stats() -> None:
    """Display database statistics."""
    db = Database(_DB_PATH)

    accepted_count = db.count_posts()
    rejected_count = db.count_rejected_posts()

    print("=== Database Statistics ===\n")
    print(f"Accepted posts: {accepted_count}")
    print(f"Rejected posts: {rejected_count}")
    print(f"Total posts: {accepted_count + rejected_count}")
    print()

    top_subreddits = db.get_top_subreddits(limit=5)
    if top_subreddits:
        print("Top subreddits (accepted):")
        for sr, count in top_subreddits:
            print(f"  r/{sr}: {count} posts")
