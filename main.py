# main.py
"""Main entry point for Reddit post monitoring CLI."""

import argparse
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

from src.interfaces.cli.commands import (
    cmd_fetch,
    cmd_score,
    cmd_notify,
    cmd_run,
    cmd_stats,
    cmd_view,
    cmd_daemon,
    cmd_cleanup,
)


def setup_logging(verbose: bool = False):
    """Configure console and file logging."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def _add_db_arg(parser: argparse.ArgumentParser) -> None:
    """Add the --database argument to a subparser."""
    parser.add_argument(
        "--database", "-db",
        type=Path,
        default=Path("posts.db"),
        help="Path to SQLite database (default: posts.db)"
    )


def _add_config_arg(parser: argparse.ArgumentParser) -> None:
    """Add the --config argument to a subparser."""
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config file (default: config.yaml)"
    )


def _add_cleanup_args(parser: argparse.ArgumentParser) -> None:
    """Add --cleanup and --cleanup-until arguments to a subparser."""
    parser.add_argument(
        "--cleanup",
        action="store_const",
        const=True,
        default=None,
        help="Enable cleanup before execution (overrides config cleanup_before_fetch)"
    )
    parser.add_argument(
        "--cleanup-until",
        type=str,
        default=None,
        dest="cleanup_until",
        help=(
            "Delete posts older than this point. "
            "Accepts YYYY-MM-DD (e.g. 2026-06-01) or day offset (e.g. 30= keep last 30 days). "
            "Overrides config cleanup_until. Has no effect if cleanup is disabled."
        )
    )


def main():
    """Run the Reddit post monitoring CLI."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Reddit Job Post Monitor - Track and score job posts from subreddits",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch new posts from Reddit")
    _add_config_arg(fetch_parser)
    _add_db_arg(fetch_parser)
    _add_cleanup_args(fetch_parser)

    # Score command
    score_parser = subparsers.add_parser("score", help="Score pending posts")
    _add_config_arg(score_parser)
    _add_db_arg(score_parser)

    # Notify command
    notify_parser = subparsers.add_parser("notify", help="Send notifications for unnotified accepted posts")
    _add_config_arg(notify_parser)
    _add_db_arg(notify_parser)

    # Run command (fetch + score + notify)
    run_parser = subparsers.add_parser("run", help="Fetch, score, and notify in one pass")
    _add_config_arg(run_parser)
    _add_db_arg(run_parser)
    _add_cleanup_args(run_parser)

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Delete old posts from database")
    _add_config_arg(cleanup_parser)
    _add_db_arg(cleanup_parser)
    cleanup_parser.add_argument(
        "--until",
        type=str,
        required=False,
        help=(
            "Delete posts older than this point. "
            "Accepts YYYY-MM-DD (e.g. 2026-06-01) or day offset (e.g. 30= keep last 30 days). "
            "Overrides config cleanup_until. Has no effect if cleanup is disabled."
        )
    )

    # View command
    view_parser = subparsers.add_parser("view", help="View posts from database")
    view_parser.add_argument(
        "--accepted",
        action="store_true",
        help="Show accepted posts"
    )
    view_parser.add_argument(
        "--rejected",
        action="store_true",
        help="Show rejected posts"
    )
    view_parser.add_argument(
        "--pending",
        action="store_true",
        help="Show pending posts"
    )
    view_parser.add_argument(
        "--unnotified",
        action="store_true",
        help="Show accepted posts that haven't been notified yet"
    )
    view_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of posts to display"
    )
    view_parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="View a single post by ID"
    )
    view_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        dest="view_verbose",
        help="Include raw_response in AI metadata display"
    )
    view_parser.add_argument(
        "--since",
        type=str,
        default=None,
        help=(
            "Filter posts from this date/day onwards. "
            "Accepts YYYY-MM-DD format (e.g. 2026-06-20) or day offset (0=today, 1=yesterday, 2=day before, etc.). "
            "Ignored when --id is used."
        )
    )
    view_parser.add_argument(
        "--until",
        type=str,
        default=None,
        help=(
            "Filter posts up to this date/day. "
            "Accepts YYYY-MM-DD format (e.g. 2026-06-27) or day offset (0=today, 1=yesterday, 2=day before, etc.). "
            "Ignored when --id is used."
        )
    )
    _add_db_arg(view_parser)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Display database statistics")
    stats_parser.add_argument(
        "--providers",
        action="store_true",
        help="Show AI provider usage statistics"
    )
    _add_db_arg(stats_parser)

    # Daemon command
    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Run as daemon with scheduled daily execution"
    )
    daemon_parser.add_argument(
        "--run-time",
        type=str,
        required=True,
        help="Time of day to run in HH:MM format (e.g. 03:00, 20:30) — UTC"
    )
    _add_config_arg(daemon_parser)
    _add_db_arg(daemon_parser)

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "fetch":
            cmd_fetch(
                config_path=args.config,
                db_path=args.database,
                cleanup=args.cleanup,
                cleanup_until=args.cleanup_until,)

        elif args.command == "score":
            cmd_score(config_path=args.config, db_path=args.database)

        elif args.command == "notify":
            cmd_notify(config_path=args.config, db_path=args.database)

        elif args.command == "run":
            cmd_run(
                config_path=args.config,
                db_path=args.database,
                cleanup=args.cleanup,
                cleanup_until=args.cleanup_until,
            )

        elif args.command == "cleanup":
            cmd_cleanup(
                config_path=args.config,
                db_path=args.database,
                until=args.until
            )

        elif args.command == "view":
            show_accepted = args.accepted or (
                not args.accepted and not args.rejected and not args.pending and not args.unnotified and not args.id
            )
            cmd_view(
                db_path=args.database,
                show_accepted=show_accepted,
                show_rejected=args.rejected,
                show_pending=args.pending,
                show_unnotified=args.unnotified,
                limit=args.limit,
                post_id=args.id,
                verbose=args.view_verbose,
                since=args.since,
                until=args.until,
            )

        elif args.command == "stats":
            cmd_stats(db_path=args.database, providers_only=args.providers)

        elif args.command == "daemon":
            cmd_daemon(config_path=args.config, db_path=args.database, run_time=args.run_time)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
