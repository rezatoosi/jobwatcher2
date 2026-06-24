# src/storage/database.py
"""Database layer for posts storage."""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class Database:
    """SQLite database manager for posts."""

    def __init__(self, db_path: str | Path):
        """Initialize database connection and ensure schema exists."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Create posts table if it doesn't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id TEXT PRIMARY KEY,
                subreddit TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                score REAL,
                matched_keywords TEXT,
                ai_metadata TEXT,
                rejection_reason TEXT,
                fetched_at TIMESTAMP NOT NULL,
                scored_at TIMESTAMP
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON posts(status)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_fetched_at ON posts(fetched_at)")
        self._conn.commit()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a row to a dict, deserializing JSON fields."""
        record = dict(row)
        
        # Parse ai_metadata
        raw_ai = record.get("ai_metadata")
        record["ai_metadata"] = json.loads(raw_ai) if raw_ai else None
        
        # Parse matched_keywords from comma-separated string to list
        raw_keywords = record.get("matched_keywords")
        if raw_keywords:
            record["matched_keywords"] = raw_keywords.split(",")
        else:
            record["matched_keywords"] = []
        
        return record

    def post_exists(self, post_id: str) -> bool:
        """Check if a post already exists in the database."""
        cursor = self._conn.execute("SELECT 1 FROM posts WHERE post_id = ?", (post_id,))
        return cursor.fetchone() is not None

    def save_fetched_post(
        self,
        post_id: str,
        subreddit: str,
        title: str,
        body: Optional[str],
        url: str,
        fetched_at: datetime,
    ):
        """Save a newly fetched post with status='pending'."""
        self._conn.execute(
            """
            INSERT INTO posts (post_id, subreddit, title, body, url, status, fetched_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (post_id, subreddit, title, body, url, fetched_at),
        )
        self._conn.commit()

    def update_post_accepted(
        self,
        post_id: str,
        score: float,
        matched_keywords: list[str],
        ai_metadata: Optional[dict],
        scored_at: datetime,
    ):
        """Update a post to status='accepted' with scoring metadata."""
        self._conn.execute(
            """
            UPDATE posts
            SET status = 'accepted',
                score = ?,
                matched_keywords = ?,
                ai_metadata = ?,
                scored_at = ?
            WHERE post_id = ?
            """,
            (
                score,
                ",".join(matched_keywords) if matched_keywords else None,
                json.dumps(ai_metadata) if ai_metadata else None,
                scored_at,
                post_id,
            ),
        )
        self._conn.commit()

    def update_post_rejected(
        self,
        post_id: str,
        rejection_reason: str,
        score: Optional[float],
        matched_keywords: Optional[list[str]],
        ai_metadata: Optional[dict],
        scored_at: datetime,
    ):
        """Update a post to status='rejected' with rejection metadata."""
        self._conn.execute(
            """
            UPDATE posts
            SET status = 'rejected',
                rejection_reason = ?,
                score = ?,
                matched_keywords = ?,
                ai_metadata = ?,
                scored_at = ?
            WHERE post_id = ?
            """,
            (
                rejection_reason,
                score,
                ",".join(matched_keywords) if matched_keywords else None,
                json.dumps(ai_metadata) if ai_metadata else None,
                scored_at,
                post_id,
            ),
        )
        self._conn.commit()

    def get_pending_posts(self, limit: Optional[int] = None) -> list[dict]:
        """Get all posts with status='pending'."""
        query = "SELECT * FROM posts WHERE status = 'pending' ORDER BY fetched_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor = self._conn.execute(query)
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_accepted_posts(self, limit: Optional[int] = None) -> list[dict]:
        """Get all accepted posts."""
        query = "SELECT * FROM posts WHERE status = 'accepted' ORDER BY scored_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor = self._conn.execute(query)
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_rejected_posts(self, limit: Optional[int] = None) -> list[dict]:
        """Get all rejected posts."""
        query = "SELECT * FROM posts WHERE status = 'rejected' ORDER BY scored_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor = self._conn.execute(query)
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def count_posts_by_status(self, status: str) -> int:
        """Count posts by status."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM posts WHERE status = ?", (status,))
        return cursor.fetchone()[0]

    def count_all_posts(self) -> int:
        """Count all posts regardless of status."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM posts")
        return cursor.fetchone()[0]

    def get_top_subreddits(self, status: str = "accepted", limit: int = 5) -> list[tuple[str, int]]:
        """Get top subreddits by post count for a given status."""
        cursor = self._conn.execute(
            """
            SELECT subreddit, COUNT(*) as count
            FROM posts
            WHERE status = ?
            GROUP BY subreddit
            ORDER BY count DESC
            LIMIT ?
            """,
            (status, limit),
        )
        return [(row["subreddit"], row["count"]) for row in cursor.fetchall()]

    def get_rejection_stats(self) -> list[tuple[str, int]]:
        """Get rejection statistics grouped by reason."""
        cursor = self._conn.execute(
            """
            SELECT rejection_reason, COUNT(*) as count
            FROM posts
            WHERE status = 'rejected' AND rejection_reason IS NOT NULL
            GROUP BY rejection_reason
            ORDER BY count DESC
            """
        )
        return [(row["rejection_reason"], row["count"]) for row in cursor.fetchall()]

    def delete_old_rejected_posts(self, days: int = 30) -> int:
        """Delete rejected posts older than specified days. Returns count of deleted posts."""
        cutoff = datetime.now() - timedelta(days=days)
        cursor = self._conn.execute(
            "DELETE FROM posts WHERE status = 'rejected' AND scored_at < ?",
            (cutoff,),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self):
        """Close database connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
