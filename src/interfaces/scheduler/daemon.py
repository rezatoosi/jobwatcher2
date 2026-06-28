# src/interfaces/scheduler/daemon.py
"""Daemon mode for scheduled job monitoring runs."""

import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import schedule
import pytz

from src.interfaces.cli.commands import cmd_run


def run_daemon(config_path: Path, db_path: Path, run_time: str) -> None:
    """Run as daemon with scheduled daily execution.

    Args:
        config_path: Path to config.yaml
        run_time: Time of day in "HH:MM" format (UTC)

    The daemon runs fetch + score at the specified time each day.
    Press Ctrl+C to stop gracefully.
    """

    def job():
        """Single scheduled run."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"\n[{now}] Starting scheduled run...")
        try:
            cmd_run(config_path, db_path)
        except Exception as e:
            print(f"[{now}] Error during run: {e}")
        else:
            print(f"[{now}] Scheduled run completed.\n")

    schedule.every().day.at(run_time, pytz.utc).do(job)

    # Graceful shutdown handler
    def _signal_handler(sig, frame):
        print("\n\nDaemon stopped by user.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)

    print(f"Daemon started. Will run daily at {run_time} UTC.")
    print("Press Ctrl+C to stop.\n")

    while True:
        schedule.run_pending()
        time.sleep(60)
