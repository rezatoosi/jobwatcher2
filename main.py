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
    cmd_run,
    cmd_stats,
    cmd_view,
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
    fetch_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config file (default: config.yaml)"
    )

    # Score command
    score_parser = subparsers.add_parser("score", help="Score pending posts")
    score_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config file (default: config.yaml)"
    )

    # Run command (fetch + score)
    run_parser = subparsers.add_parser("run", help="Fetch then score in one pass")
    run_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config file (default: config.yaml)"
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

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Display database statistics")
    stats_parser.add_argument(
        "--providers",
        action="store_true",
        help="Show AI provider usage statistics"
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "fetch":
            cmd_fetch(config_path=args.config)

        elif args.command == "score":
            cmd_score(config_path=args.config)

        elif args.command == "run":
            cmd_run(config_path=args.config)

        elif args.command == "view":
            # Default: show accepted if nothing specified
            show_accepted = args.accepted or (
                not args.accepted and not args.rejected and not args.pending and not args.id
            )
            cmd_view(
                show_accepted=show_accepted,
                show_rejected=args.rejected,
                show_pending=args.pending,
                limit=args.limit,
                post_id=args.id,
                verbose=args.view_verbose,
                since=args.since,
                until=args.until,
            )

        elif args.command == "stats":
            cmd_stats(providers_only=args.providers)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
