# src/interfaces/cli/commands.py
"""CLI commands for Reddit post monitoring.

These are thin presentation wrappers: they load config, drive the core
pipeline, and print results. All processing logic lives in
`src.interfaces.core.pipeline`.
"""

from pathlib import Path
from typing import Optional

from src.config import load_config
from src.interfaces.core.pipeline import FetchPipeline, ScoringPipeline, ScoredPost
from src.scoring.ai import AIScoringError
from src.storage.database import Database

_DB_PATH = "posts.db"


def cmd_fetch(config_path: Path = Path("config.yaml")) -> None:
    """Fetch new posts from Reddit and save as pending."""
    config = load_config(config_path)

    print("Configuration loaded:")
    print(f"  Subreddits: {', '.join(config.subreddits)}")
    print(f"  Fetch limit: {config.fetch_limit}")
    print()

    db = Database(_DB_PATH)
    pipeline = FetchPipeline(config, db)

    print("Fetching posts from Reddit...")

    try:
        report = pipeline.run()
    except Exception as e:
        print(f"  ✗ Error during fetch: {e}")
        return

    print()
    print("=== Fetch Summary ===")
    print(f"Total fetched:       {report.total_fetched}")
    print(f"Duplicates skipped:  {report.duplicates}")
    print(f"Saved as pending:    {report.saved_pending}")
    print("=" * 10)


def cmd_score(config_path: Path = Path("config.yaml")) -> None:
    """Score pending posts with keyword + AI scoring."""
    config = load_config(config_path)

    print("Configuration loaded:")
    print(f"  Keywords: {len(config.keywords)} keywords")
    print(f"  Keyword threshold: {config.scoring.keyword_threshold}")

    db = Database(_DB_PATH)
    pipeline = ScoringPipeline(config, db)

    print(f"  AI scoring: {'enabled' if pipeline.ai_scorer else 'disabled'}")
    print()
    print("Scoring pending posts...")

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
        print(f"  ✗ Error during scoring: {e}")
        return

    if report.accepted:
        print()
        print("Accepted posts:")
        for sp in report.accepted:
            post = sp.post
            keywords = ", ".join(sp.matched_keywords)
            print(f"  ✓ [{post.subreddit}] {post.title[:50]}...")
            print(f"    Score: {sp.score} | Keywords: {keywords}")

    print()
    print("=== Scoring Summary ===")
    print(f"Pending processed:   {report.total_pending}")
    print(f"Keyword passed:      {report.keyword_passed}")
    print(f"Accepted:            {report.accepted_count}")
    print(f"Rejected:            {report.rejected_count}")
    print("=" * 10)


def cmd_run(config_path: Path = Path("config.yaml")) -> None:
    """Run both fetch and score pipelines sequentially."""
    print("Running fetch pipeline...")
    cmd_fetch(config_path)
    print()
    print("Running scoring pipeline...")
    cmd_score(config_path)


def cmd_view(
    show_accepted: bool = True,
    show_rejected: bool = False,
    show_pending: bool = False,
    limit: Optional[int] = None,
) -> None:
    """View posts from database."""
    db = Database(_DB_PATH)

    if show_accepted:
        print("=== Accepted Posts ===\n")
        posts = db.get_posts_by_status("accepted", limit=limit)
        if not posts:
            print("No accepted posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                keywords = ", ".join(post.matched_keywords)
                print(f"{idx}. [/r/{post.subreddit}]: {post.title}")
                print(f"   Score: {post.score} | Keywords: {keywords}")
                print(f"   URL: {post.url}")
                print(f"   Scored at: {post.scored_at}")
                if post.body:
                    body_preview = post.body[:150].replace("\n", " ")
                    suffix = "..." if len(post.body) > 150 else ""
                    print(f"   Body: {body_preview}{suffix}")
                print()

    if show_rejected:
        print("=== Rejected Posts ===\n")
        posts = db.get_posts_by_status("rejected", limit=limit)
        if not posts:
            print("No rejected posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                keywords = ", ".join(post.matched_keywords)
                print(f"{idx}. [/r/{post.subreddit}]: {post.title}")
                print(f"   Score: {post.score} | Keywords: {keywords}")
                print(f"   URL: {post.url}")
                print(f"   Scored at: {post.scored_at}")
                if post.rejection_reason:
                    print(f"   Reason: {post.rejection_reason}")
                print()

    if show_pending:
        print("=== Pending Posts ===\n")
        posts = db.get_posts_by_status("pending", limit=limit)
        if not posts:
            print("No pending posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                print(f"{idx}. [/r/{post.subreddit}]: {post.title}")
                print(f"   URL: {post.url}")
                print(f"   Fetched at: {post.fetched_at}")
                print()


def cmd_stats() -> None:
    """Display database statistics."""
    db = Database(_DB_PATH)

    counts = db.count_posts_by_status()
    accepted_count = counts.get("accepted", 0)
    rejected_count = counts.get("rejected", 0)
    pending_count = counts.get("pending", 0)

    print("=== Database Statistics ===\n")
    print(f"Accepted posts: {accepted_count}")
    print(f"Rejected posts: {rejected_count}")
    print(f"Pending posts:  {pending_count}")
    print(f"Total posts:    {accepted_count + rejected_count + pending_count}")
    print()

    top_subreddits = db.get_top_subreddits(limit=5)
    if top_subreddits:
        print("Top subreddits (accepted):")
        for sr, count in top_subreddits:
            print(f"  r/{sr}: {count} posts")
