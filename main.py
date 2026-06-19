# main.py
"""Main entry point for Reddit post monitoring CLI."""

import argparse
import sys
from pathlib import Path

from src.cli.commands import cmd_fetch, cmd_stats, cmd_view


def main():
    """Run the Reddit post monitoring CLI."""
    parser = argparse.ArgumentParser(
        description="Reddit Job Post Monitor - Track and score job posts from subreddits",
        formatter_class=argparse.RawDescriptionHelpFormatter
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
        "--limit",
        type=int,
        default=None,
        help="Limit number of posts to display"
    )
    
    # Stats command
    subparsers.add_parser("stats", help="Display database statistics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == "fetch":
            cmd_fetch(config_path=args.config)
        
        elif args.command == "view":
            # Default: show accepted if nothing specified
            show_accepted = args.accepted or (not args.accepted and not args.rejected)
            show_rejected = args.rejected
            cmd_view(
                show_accepted=show_accepted,
                show_rejected=show_rejected,
                limit=args.limit
            )
        
        elif args.command == "stats":
            cmd_stats()
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
