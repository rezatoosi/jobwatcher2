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
