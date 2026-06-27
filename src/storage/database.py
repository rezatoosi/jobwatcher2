# src/storage/database.py
"""Database layer for posts storage."""

import sqlite3
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class PostRecord:
    """A post as persisted in the database.

    Mirrors the `posts` table columns exactly. Fields that are only
    populated after scoring (score, matched_keywords, ai_metadata,
    rejection_reason, scored_at) are optional and default to empty/None
    for pending posts.
    """

    post_id: str
    subreddit: str
    title: str
    body: Optional[str]
    url: str
    status: str
    fetched_at: Any
    score: Optional[float] = None
    matched_keywords: list[str] = field(default_factory=list)
    ai_metadata: Optional[dict] = None
    rejection_reason: Optional[str] = None
    scored_at: Any = None


class Database:
    """Persistent storage for Reddit posts."""

    def __init__(self, db_path: str = "data/posts.db"):
        """Initialize database connection and create tables if needed."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Create the posts table if it doesn't exist."""
        self._conn.execute(
            """
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
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scored_at TIMESTAMP
            )
        """
        )
        self._conn.commit()

    @staticmethod
    def _parse_keywords(raw: Optional[str]) -> list[str]:
        """Deserialize comma-separated keywords into a list."""
        if not raw:
            return []
        return raw.split(",")

    @staticmethod
    def _parse_ai_metadata(raw: Optional[str]) -> Optional[dict]:
        """Deserialize the JSON ai_metadata field."""
        return json.loads(raw) if raw else None

    @classmethod
    def _row_to_record(cls, row: sqlite3.Row) -> PostRecord:
        """Convert a row into a PostRecord, deserializing JSON/CSV fields."""
        return PostRecord(
            post_id=row["post_id"],
            subreddit=row["subreddit"],
            title=row["title"],
            body=row["body"],
            url=row["url"],
            status=row["status"],
            fetched_at=row["fetched_at"],
            score=row["score"],
            matched_keywords=cls._parse_keywords(row["matched_keywords"]),
            ai_metadata=cls._parse_ai_metadata(row["ai_metadata"]),
            rejection_reason=row["rejection_reason"],
            scored_at=row["scored_at"],
        )

    def save_fetched_post(
        self,
        post_id: str,
        subreddit: str,
        title: str,
        body: Optional[str],
        url: str,
        fetched_at: Optional[datetime] = None,
    ):
        """Save a newly fetched Reddit post with status='pending'.

        If fetched_at is omitted, the column default (CURRENT_TIMESTAMP) is used.
        """
        if fetched_at is not None:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO posts
                    (post_id, subreddit, title, body, url, status, fetched_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (post_id, subreddit, title, body, url, fetched_at),
            )
        else:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO posts
                    (post_id, subreddit, title, body, url, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
                """,
                (post_id, subreddit, title, body, url),
            )
        self._conn.commit()

    def _finalize_post(
        self,
        post_id: str,
        status: str,
        score: Optional[float],
        matched_keywords: Optional[list[str]],
        ai_metadata: Optional[dict],
        rejection_reason: Optional[str],
        scored_at: Optional[datetime],
    ):
        """Shared update for accepted/rejected transitions."""
        keywords_str = ",".join(matched_keywords) if matched_keywords else None
        ai_metadata_str = json.dumps(ai_metadata) if ai_metadata else None

        if scored_at is not None:
            self._conn.execute(
                """
                UPDATE posts
                SET status = ?, score = ?, matched_keywords = ?,
                    ai_metadata = ?, rejection_reason = ?, scored_at = ?
                WHERE post_id = ?
                """,
                (
                    status,
                    score,
                    keywords_str,
                    ai_metadata_str,
                    rejection_reason,
                    scored_at,
                    post_id,
                ),
            )
        else:
            self._conn.execute(
                """
                UPDATE posts
                SET status = ?, score = ?, matched_keywords = ?,
                    ai_metadata = ?, rejection_reason = ?, scored_at = CURRENT_TIMESTAMP
                WHERE post_id = ?
                """,
                (
                    status,
                    score,
                    keywords_str,
                    ai_metadata_str,
                    rejection_reason,
                    post_id,
                ),
            )
        self._conn.commit()

    def update_post_accepted(
        self,
        post_id: str,
        score: float,
        matched_keywords: Optional[list[str]] = None,
        ai_metadata: Optional[dict] = None,
        scored_at: Optional[datetime] = None,
    ):
        """Mark a post as accepted with its final score and metadata."""
        self._finalize_post(
            post_id=post_id,
            status="accepted",
            score=score,
            matched_keywords=matched_keywords,
            ai_metadata=ai_metadata,
            rejection_reason=None,
            scored_at=scored_at,
        )

    def update_post_rejected(
        self,
        post_id: str,
        rejection_reason: str,
        score: float = 0.0,
        matched_keywords: Optional[list[str]] = None,
        ai_metadata: Optional[dict] = None,
        scored_at: Optional[datetime] = None,
    ):
        """Mark a post as rejected with a reason."""
        self._finalize_post(
            post_id=post_id,
            status="rejected",
            score=score,
            matched_keywords=matched_keywords,
            ai_metadata=ai_metadata,
            rejection_reason=rejection_reason,
            scored_at=scored_at,
        )

    def get_pending_posts(self, limit: Optional[int] = None) -> list[PostRecord]:
        """Get all posts with status='pending'."""
        query = "SELECT * FROM posts WHERE status = 'pending' ORDER BY fetched_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor = self._conn.execute(query)
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_accepted_posts(self, limit: Optional[int] = None) -> list[PostRecord]:
        """Get all accepted posts."""
        query = "SELECT * FROM posts WHERE status = 'accepted' ORDER BY scored_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor = self._conn.execute(query)
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_rejected_posts(self, limit: Optional[int] = None) -> list[PostRecord]:
        """Get all rejected posts."""
        query = "SELECT * FROM posts WHERE status = 'rejected' ORDER BY scored_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor = self._conn.execute(query)
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_posts_by_status(
        self,
        status: str,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> list[PostRecord]:
        """Get all posts with the given status, optionally filtered by date range.

        Args:
            status: Post status to filter by.
            limit: Maximum number of results to return.
            since: Only include posts fetched at or after this time.
            until: Only include posts fetched at or before this time.

        Both `since` and `until` are inclusive.
        """
        conditions = ["status = ?"]
        params: list[Any] = [status]

        if since is not None:
            conditions.append("fetched_at >= ?")
            params.append(since.strftime("%Y-%m-%d %H:%M:%S"))

        if until is not None:
            conditions.append("fetched_at <= ?")
            params.append(until.strftime("%Y-%m-%d %H:%M:%S"))

        where_clause = " AND ".join(conditions)
        query = f"SELECT * FROM posts WHERE {where_clause} ORDER BY fetched_at DESC"

        if limit:
            query += f" LIMIT {limit}"

        cursor = self._conn.execute(query, params)
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def count_posts_by_status(self) -> dict[str, int]:
        """Return a mapping of status -> count for all posts."""
        cursor = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM posts GROUP BY status"
        )
        return {row["status"]: row["n"] for row in cursor.fetchall()}

    def get_top_subreddits(self, limit: int = 10) -> list[tuple[str, int]]:
        """Return the most frequent subreddits as (subreddit, count) pairs."""
        cursor = self._conn.execute(
            """
            SELECT subreddit, COUNT(*) AS n
            FROM posts
            GROUP BY subreddit
            ORDER BY n DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [(row["subreddit"], row["n"]) for row in cursor.fetchall()]

    def post_exists(self, post_id: str) -> bool:
        """Check if a post already exists in the database."""
        cursor = self._conn.execute(
            "SELECT 1 FROM posts WHERE post_id = ?", (post_id,)
        )
        return cursor.fetchone() is not None

    def get_recent_post_ids(self, hours: int = 24) -> set[str]:
        """Get post IDs fetched in the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cursor = self._conn.execute(
            "SELECT post_id FROM posts WHERE fetched_at > ?", (cutoff.isoformat(),)
        )
        return {row["post_id"] for row in cursor.fetchall()}

    def close(self):
        """Close the database connection."""
        self._conn.close()
