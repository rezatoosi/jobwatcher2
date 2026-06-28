# src/interfaces/cli/commands.py
"""CLI commands for Reddit post monitoring.

These are thin presentation wrappers: they load config, drive the core
pipeline, and print results. All processing logic lives in
`src.interfaces.core.pipeline`.
"""

from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

from src.config import load_config
from src.interfaces.core.pipeline import FetchPipeline, ScoringPipeline, ScoredPost
from src.scoring.ai import AIScoringError
from src.scoring.base import ScoredPost as BaseScoredPost
from src.storage.database import Database

from src.notifiers.factory import build_notifiers
from src.notifications.service import notify_accepted_posts


_DEFAULT_DB_PATH = "posts.db"
_DEFAULT_CONFIG_PATH = "config.yaml"


def cmd_fetch(
        config_path: Path = Path(_DEFAULT_CONFIG_PATH),
        db_path: Path = Path(_DEFAULT_DB_PATH)
        ) -> None:
    """Fetch new posts from Reddit and save as pending."""
    config = load_config(config_path)

    print("Configuration loaded:")
    print(f"  Subreddits: {', '.join(config.subreddits)}")
    print(f"  Fetch limit: {config.fetch_limit}")
    print()

    db = Database(db_path)
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


def cmd_score(
        config_path: Path = Path(_DEFAULT_CONFIG_PATH),
        db_path: Path = Path(_DEFAULT_DB_PATH)
        ) -> None:
    """Score pending posts with keyword + AI scoring."""
    config = load_config(config_path)

    print("Configuration loaded:")
    print(f"  Keywords: {len(config.keywords)} keywords")
    print(f"  Keyword threshold: {config.scoring.keyword_threshold}")

    db = Database(db_path)
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


def cmd_notify(
        config_path: Path = Path(_DEFAULT_CONFIG_PATH),
        db_path: Path = Path(_DEFAULT_DB_PATH)
        ) -> None:
    """Send notifications for accepted posts that haven't been notified yet."""
    config = load_config(config_path)

    if not config.notifiers.enabled:
        print("Notifications are disabled in config.")
        return

    db = Database(db_path)
    records = db.get_accepted_unnotified()

    if not records:
        print("No unnotified accepted posts found.")
        return

    print(f"Found {len(records)} unnotified accepted post(s).")
    print("Sending notifications...")

    notifiers = build_notifiers(config.notifiers)
    if not notifiers:
        print("  No notifiers configured.")
        return

    scored_posts = [
        BaseScoredPost(
            post=record,
            score=record.score or 0.0,
            matched_keywords=record.matched_keywords,
            ai_metadata=record.ai_metadata,
        )
        for record in records
    ]

    notify_accepted_posts(notifiers, scored_posts)

    post_ids = [record.post_id for record in records]
    db.mark_as_notified(post_ids)

    print(f"  Notified via {len(notifiers)} notifier(s).")
    print(f"  Marked {len(post_ids)} post(s) as notified.")


def cmd_run(
        config_path: Path = Path(_DEFAULT_CONFIG_PATH),
        db_path: Path = Path(_DEFAULT_DB_PATH)
        ) -> None:
    """Run fetch, score, and notify pipelines sequentially."""
    print("Running fetch pipeline...")
    cmd_fetch(config_path, db_path)
    print()
    print("Running scoring pipeline...")
    cmd_score(config_path, db_path)
    print()
    print("Running notification pipeline...")
    cmd_notify(config_path, db_path)


def _parse_date_filter(value: str, *, end_of_day: bool = False) -> datetime:
    """Parse a user-supplied date filter into a datetime boundary.

    Accepts either form:
      - a non-negative day offset: "0"=today, "1"=yesterday, "2"=two days
        ago, and so on.
      - an absolute date in "YYYY-MM-DD" format.

    The returned datetime is snapped to a day boundary so the value can be
    compared directly against the stored `fetched_at` timestamps:
      - end_of_day=False -> start of the day (00:00:00), used for `since`.
      - end_of_day=True  -> end of the day (23:59:59.999999), used for `until`.

    Raises:
        ValueError: if the value is neither a valid day offset nor a
            valid YYYY-MM-DD date.
    """
    value = value.strip()

    if value.isdigit():
        offset = int(value)
        day = (datetime.now(timezone.utc) - timedelta(days=offset)).date()
    else:
        try:
            day = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(
                f"Invalid date filter '{value}'. "
                "Use a day offset (0=today, 1=yesterday, 2=two days ago, ...) "
                "or an absolute date in YYYY-MM-DD format."
            )

    if end_of_day:
        return datetime.combine(day, time(23, 59, 59, 999999))
    return datetime.combine(day, time.min)


def cmd_view(
    db_path: Path = Path(_DEFAULT_DB_PATH),
    show_accepted: bool = True,
    show_rejected: bool = False,
    show_pending: bool = False,
    show_unnotified: bool = False,
    limit: Optional[int] = None,
    post_id: Optional[str] = None,
    verbose: bool = False,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> None:
    """View posts from database.

    The `since`/`until` filters apply to every listing mode (accepted,
    rejected, pending, unnotified) and are matched against each post's
    `fetched_at` timestamp. They are ignored when `post_id` is given,
    since a single post is always shown in full.
    """
    db = Database(db_path)

    if post_id:
        _render_single_post(db, post_id, verbose)
        return

    try:
        since_dt = _parse_date_filter(since, end_of_day=False) if since else None
        until_dt = _parse_date_filter(until, end_of_day=True) if until else None
    except ValueError as e:
        print(f"Error: {e}")
        return

    if show_unnotified:
        print("=== Unnotified Accepted Posts ===\n")
        posts = db.get_accepted_unnotified(limit=limit)
        if since_dt or until_dt:
            posts = [
                p for p in posts
                if (not since_dt or p.fetched_at >= since_dt)
                and (not until_dt or p.fetched_at <= until_dt)
            ]
        if not posts:
            print("No unnotified accepted posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                keywords = ", ".join(post.matched_keywords)
                print(f"{idx}. [/r/{post.subreddit}]: {post.title}")
                print(f"   Post ID:   {post.post_id}")
                print(f"   Score: {post.score} | Keywords: {keywords}")
                print(f"   URL: {post.url}")
                print(f"   Fetched at: {post.fetched_at}")
                print(f"   Scored at: {post.scored_at}")
                if post.body:
                    body_preview = post.body[:150].replace("\n", " ")
                    suffix = "..." if len(post.body) > 150 else ""
                    print(f"   Body: {body_preview}{suffix}")
                print()

    if show_accepted:
        print("=== Accepted Posts ===\n")
        posts = db.get_posts_by_status(
            "accepted", limit=limit, since=since_dt, until=until_dt
        )
        if not posts:
            print("No accepted posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                keywords = ", ".join(post.matched_keywords)
                print(f"{idx}. [/r/{post.subreddit}]: {post.title}")
                print(f"   Post ID:   {post.post_id}")
                print(f"   Score: {post.score} | Keywords: {keywords}")
                print(f"   URL: {post.url}")
                print(f"   Fetched at: {post.fetched_at}")
                print(f"   Scored at: {post.scored_at}")
                if post.body:
                    body_preview = post.body[:150].replace("\n", " ")
                    suffix = "..." if len(post.body) > 150 else ""
                    print(f"   Body: {body_preview}{suffix}")
                print()

    if show_rejected:
        print("=== Rejected Posts ===\n")
        posts = db.get_posts_by_status(
            "rejected", limit=limit, since=since_dt, until=until_dt
        )
        if not posts:
            print("No rejected posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                keywords = ", ".join(post.matched_keywords)
                print(f"{idx}. [/r/{post.subreddit}]: {post.title}")
                print(f"   Post ID:   {post.post_id}")
                print(f"   Score: {post.score} | Keywords: {keywords}")
                print(f"   URL: {post.url}")
                print(f"   Fetched at: {post.fetched_at}")
                print(f"   Scored at: {post.scored_at}")
                if post.rejection_reason:
                    print(f"   Reason: {post.rejection_reason}")
                print()

    if show_pending:
        print("=== Pending Posts ===\n")
        posts = db.get_posts_by_status(
            "pending", limit=limit, since=since_dt, until=until_dt
        )
        if not posts:
            print("No pending posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                print(f"{idx}. [/r/{post.subreddit}]: {post.title}")
                print(f"   Post ID:   {post.post_id}")
                print(f"   URL: {post.url}")
                print(f"   Fetched at: {post.fetched_at}")
                print()


def _render_single_post(db: Database, post_id: str, verbose: bool = False) -> None:
    """Render a single post by ID with optional AI metadata."""
    post = db.get_post_by_id(post_id)
    if post is None:
        print(f"Post '{post_id}' not found.")
        return
    
    print(f"[{post.subreddit}] {post.title}")
    print(f"  Post ID:   {post.post_id}")
    print(f"  URL:       {post.url}")
    print(f"  Status:    {post.status}")
    if post.fetched_at:
        print(f"  Fetched at: {post.fetched_at}")
    if post.scored_at:
        print(f"  Scored at: {post.scored_at}")
    if post.score is not None:
        print(f"  Score:     {post.score}")
    if post.matched_keywords:
        print(f"  Keywords:  {', '.join(post.matched_keywords)}")
    if post.rejection_reason:
        print(f"  Reason:    {post.rejection_reason}")
    if post.body:
        print(f"  Body:      {post.body}")

    if post.ai_metadata and post.ai_metadata.get("provider"):
        print()
        print("  --- AI Metadata ---")
        meta = post.ai_metadata

        if meta.get("provider"):
            print(f"  Provider:   {meta['provider']}")
        if meta.get("model"):
            print(f"  Model:      {meta['model']}")
        if meta.get("tokens_used"):
            print(f"  Tokens:     {meta['tokens_used']}")
        if meta.get("is_relevant") is not None:
            print(f"  Relevant:   {meta['is_relevant']}")
        if meta.get("score") is not None:
            print(f"  Score:      {meta['score']}")

        # Per-dimension scores (any extra numeric breakdown fields)
        _known = {
            "provider", "model", "tokens_used", "is_relevant", "score",
            "reason", "error", "raw_response", "status",
        }
        breakdown = {
            k: v for k, v in meta.items()
            if k not in _known and isinstance(v, (int, float))
        }
        if breakdown:
            print("  Breakdown:")
            for k, v in breakdown.items():
                print(f"    {k}: {v}")

        if meta.get("reason"):
            print(f"  Reason:     {meta['reason']}")
        if meta.get("error"):
            print(f"  Error:      {meta['error']}")
        if verbose and meta.get("raw_response"):
            print()
            print("  --- Raw Response ---")
            print(meta["raw_response"])


def cmd_stats(
        db_path: Path = Path(_DEFAULT_DB_PATH),
        providers_only: bool = False
        ) -> None:
    """Display database statistics."""
    db = Database(db_path)

    if providers_only:
        _render_provider_stats(db)
        return

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


def _render_provider_stats(db: Database) -> None:
    """Render provider-level stats aggregated from ai_metadata."""
    metadata_list = db.get_all_ai_metadata()
    providers: dict[str, dict] = {}
    for meta in metadata_list:
        if not meta:
            continue

        key = meta.get("provider") or "unknown"
        model = meta.get("model") or "unknown"
        status = meta.get("status") or ("error" if meta.get("error") else "success")

        if key not in providers:
            providers[key] = {"models": {}}
        if model not in providers[key]["models"]:
            providers[key]["models"][model] = {"total": 0, "success": 0, "error": 0}

        bucket = providers[key]["models"][model]
        bucket["total"] += 1
        if status == "success":
            bucket["success"] += 1
        else:
            bucket["error"] += 1

    if not providers:
        print("No AI scoring data found.")
        return

    print("=== Provider Statistics ===\n")
    for provider, info in sorted(providers.items()):
        total_reqs = sum(m["total"] for m in info["models"].values())
        total_success = sum(m["success"] for m in info["models"].values())
        total_errors = total_reqs - total_success
        rate = (total_success / total_reqs * 100) if total_reqs else 0

        print(f"{provider} ({total_reqs} requests, {rate:.1f}% success)")
        for model, stats in sorted(info["models"].items()):
            print(
                f"  {model}: {stats['total']} reqs | "
                f"{stats['success']} OK | {stats['error']} err"
            )
        print()


def cmd_daemon(
        config_path: Path = Path(_DEFAULT_CONFIG_PATH),
        db_path: Path = Path(_DEFAULT_DB_PATH),
        run_time: str = ""
        ) -> None:
    """Start daemon mode for scheduled runs.
    
    Args:
        run_time: Time of day in "HH:MM" format (UTC)
    """
    import re
    
    if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', run_time):
        print("Error: run_time must be in HH:MM format (00:00 to 23:59).")
        return
    
    from src.interfaces.scheduler.daemon import run_daemon
    run_daemon(config_path, db_path, run_time)
