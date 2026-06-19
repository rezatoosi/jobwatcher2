# src/storage/database.py
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
            
            # Main posts table for accepted posts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    post_id TEXT PRIMARY KEY,
                    subreddit TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT,
                    url TEXT NOT NULL,
                    score REAL NOT NULL,
                    matched_keywords TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Rejected posts table for audit
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rejected_posts (
                    post_id TEXT PRIMARY KEY,
                    subreddit TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT,
                    url TEXT NOT NULL,
                    score REAL NOT NULL,
                    matched_keywords TEXT NOT NULL,
                    rejected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def post_exists(self, post_id: str) -> bool:
        """Check if a post exists in either posts or rejected_posts table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM posts WHERE post_id = ? UNION SELECT 1 FROM rejected_posts WHERE post_id = ?",
                (post_id, post_id)
            )
            return cursor.fetchone() is not None
    
    def save_post(
        self,
        post_id: str,
        subreddit: str,
        title: str,
        body: Optional[str],
        url: str,
        score: float,
        matched_keywords: list[str]
    ) -> bool:
        """Save an accepted post to the database. Returns True if successful."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO posts 
                       (post_id, subreddit, title, body, url, score, matched_keywords) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (post_id, subreddit, title, body, url, score, ",".join(matched_keywords))
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
    
    def save_rejected_post(
        self,
        post_id: str,
        subreddit: str,
        title: str,
        body: Optional[str],
        url: str,
        score: float,
        matched_keywords: list[str]
    ) -> bool:
        """Save a rejected post for audit. Returns True if successful."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO rejected_posts 
                       (post_id, subreddit, title, body, url, score, matched_keywords) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (post_id, subreddit, title, body, url, score, ",".join(matched_keywords))
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
    
    def get_all_posts(self, limit: Optional[int] = None) -> list[dict]:
        """Get all accepted posts, ordered by creation date (newest first)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM posts ORDER BY created_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_rejected_posts(self, limit: Optional[int] = None) -> list[dict]:
        """Get all rejected posts, ordered by rejection date (newest first)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM rejected_posts ORDER BY rejected_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def count_posts(self) -> int:
        """Count total accepted posts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM posts")
            return cursor.fetchone()[0]
    
    def count_rejected_posts(self) -> int:
        """Count total rejected posts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rejected_posts")
            return cursor.fetchone()[0]
    
    def get_top_subreddits(self, limit: int = 5) -> list[tuple[str, int]]:
        """Get top subreddits by post count (accepted posts only)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT subreddit, COUNT(*) as count 
                   FROM posts 
                   GROUP BY subreddit 
                   ORDER BY count DESC 
                   LIMIT ?""",
                (limit,)
            )
            return cursor.fetchall()
