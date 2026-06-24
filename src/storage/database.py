# src/storage/database.py
import json
import sqlite3
from datetime import datetime
from typing import Optional


class Database:
    def __init__(self, db_path: str = "reddit_posts.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database and create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Single posts table with status-based workflow
            cursor.execute("""
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
            
            # Index for efficient status queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_posts_status 
                ON posts(status)
            """)
            
            conn.commit()
    
    def post_exists(self, post_id: str) -> bool:
        """Check if a post exists in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM posts WHERE post_id = ?", (post_id,))
            return cursor.fetchone() is not None
    
    def save_fetched_post(
        self,
        post_id: str,
        subreddit: str,
        title: str,
        body: Optional[str],
        url: str,
        fetched_at: Optional[datetime] = None
    ) -> bool:
        """
        Save a freshly fetched post with status='pending'.
        Returns True if successful, False if post already exists.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO posts 
                       (post_id, subreddit, title, body, url, status, fetched_at) 
                       VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
                    (
                        post_id,
                        subreddit,
                        title,
                        body,
                        url,
                        fetched_at or datetime.now()
                    )
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
    
    def update_post_accepted(
        self,
        post_id: str,
        score: float,
        matched_keywords: list[str],
        ai_metadata: Optional[dict] = None,
        scored_at: Optional[datetime] = None
    ) -> bool:
        """
        Update a post to accepted status with scoring data.
        Returns True if successful.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE posts 
                   SET status = 'accepted',
                       score = ?,
                       matched_keywords = ?,
                       ai_metadata = ?,
                       scored_at = ?
                   WHERE post_id = ?""",
                (
                    score,
                    ",".join(matched_keywords) if matched_keywords else "",
                    json.dumps(ai_metadata) if ai_metadata else None,
                    scored_at or datetime.now(),
                    post_id
                )
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def update_post_rejected(
        self,
        post_id: str,
        rejection_reason: str,
        score: float = 0.0,
        matched_keywords: Optional[list[str]] = None,
        ai_metadata: Optional[dict] = None,
        scored_at: Optional[datetime] = None
    ) -> bool:
        """
        Update a post to rejected status with rejection reason.
        Returns True if successful.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE posts 
                   SET status = 'rejected',
                       rejection_reason = ?,
                       score = ?,
                       matched_keywords = ?,
                       ai_metadata = ?,
                       scored_at = ?
                   WHERE post_id = ?""",
                (
                    rejection_reason,
                    score,
                    ",".join(matched_keywords) if matched_keywords else "",
                    json.dumps(ai_metadata) if ai_metadata else None,
                    scored_at or datetime.now(),
                    post_id
                )
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_pending_posts(self, limit: Optional[int] = None) -> list[dict]:
        """Get all pending posts for scoring."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM posts WHERE status = 'pending' ORDER BY fetched_at ASC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def get_accepted_posts(self, limit: Optional[int] = None) -> list[dict]:
        """Get all accepted posts, ordered by scored date (newest first)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM posts WHERE status = 'accepted' ORDER BY scored_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def get_rejected_posts(self, limit: Optional[int] = None) -> list[dict]:
        """Get all rejected posts, ordered by scored date (newest first)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM posts WHERE status = 'rejected' ORDER BY scored_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a row to a dict, deserializing ai_metadata from JSON."""
        record = dict(row)
        raw = record.get("ai_metadata")
        record["ai_metadata"] = json.loads(raw) if raw else None
        return record
    
    def count_posts_by_status(self, status: str) -> int:
        """Count posts by status (pending, accepted, rejected)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM posts WHERE status = ?", (status,))
            return cursor.fetchone()[0]
    
    def count_all_posts(self) -> int:
        """Count total posts in database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM posts")
            return cursor.fetchone()[0]
    
    def get_top_subreddits(self, status: str = "accepted", limit: int = 5) -> list[tuple[str, int]]:
        """Get top subreddits by post count for a given status."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT subreddit, COUNT(*) as count 
                   FROM posts 
                   WHERE status = ?
                   GROUP BY subreddit 
                   ORDER BY count DESC 
                   LIMIT ?""",
                (status, limit)
            )
            return cursor.fetchall()
    
    def get_rejection_stats(self) -> list[tuple[str, int]]:
        """Get rejection reasons with counts, ordered by frequency."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT rejection_reason, COUNT(*) as count 
                   FROM posts 
                   WHERE status = 'rejected' AND rejection_reason IS NOT NULL
                   GROUP BY rejection_reason 
                   ORDER BY count DESC"""
            )
            return cursor.fetchall()
    
    def delete_old_rejected_posts(self, days: int = 30) -> int:
        """
        Delete rejected posts older than specified days.
        Returns number of deleted rows.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """DELETE FROM posts 
                   WHERE status = 'rejected' 
                   AND scored_at < datetime('now', '-' || ? || ' days')""",
                (days,)
            )
            conn.commit()
            return cursor.rowcount
