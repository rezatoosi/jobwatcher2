# src/filtering/post_filter.py
from typing import Optional
from src.fetcher.reddit import RedditPost


class PostFilter:
    """Pre-filter posts based on subreddit-specific rules before scoring."""
    
    def __init__(self, filters: dict[str, dict]):
        """
        Initialize filter with subreddit-specific rules.
        
        Args:
            filters: Dictionary mapping subreddit names to filter rules
                    Example: {
                        "forhire": {
                            "title_must_contain": ["[Hiring]"],
                            "title_must_not_contain": ["[For Hire]"]
                        }
                    }
        """
        self.filters = filters or {}
    
    def should_process(self, post: RedditPost) -> bool:
        """
        Check if a post should proceed to scoring stage.
        
        Args:
            post: Reddit post to filter
        
        Returns:
            True if post passes filters (or no filter defined for subreddit)
        """
        subreddit = post.subreddit.lower()
        
        # If no filter defined for this subreddit, allow it
        if subreddit not in self.filters:
            return True
        
        filter_rules = self.filters[subreddit]
        title_lower = post.title.lower()
        
        # Check must_contain rules
        if "title_must_contain" in filter_rules:
            must_contain = filter_rules["title_must_contain"]
            if not any(phrase.lower() in title_lower for phrase in must_contain):
                return False
        
        # Check must_not_contain rules
        if "title_must_not_contain" in filter_rules:
            must_not_contain = filter_rules["title_must_not_contain"]
            if any(phrase.lower() in title_lower for phrase in must_not_contain):
                return False
        
        return True
    
    def filter_posts(self, posts: list[RedditPost]) -> list[RedditPost]:
        """
        Filter a list of posts, returning only those that pass rules.
        
        Args:
            posts: List of Reddit posts
        
        Returns:
            Filtered list of posts
        """
        return [post for post in posts if self.should_process(post)]
