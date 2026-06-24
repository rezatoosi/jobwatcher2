# src/filtering/filter.py
"""Pre-filter posts based on subreddit-specific rules before scoring."""

from src.scoring.base import ScorablePost


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
    
    def should_process(self, post: ScorablePost) -> bool:
        subreddit = post.subreddit.lower()
        
        if subreddit not in self.filters:
            return True
        
        filter_rules = self.filters[subreddit]
        title_lower = post.title.lower()
        
        # Check must_contain rules
        if filter_rules.title_must_contain:
            if not any(phrase.lower() in title_lower for phrase in filter_rules.title_must_contain):
                return False
        
        # Check must_not_contain rules
        if filter_rules.title_must_not_contain:
            if any(phrase.lower() in title_lower for phrase in filter_rules.title_must_not_contain):
                return False
        
        return True
    
    def filter_posts(self, posts: list[ScorablePost]) -> list[ScorablePost]:
        """
        Filter a list of posts, returning only those that pass rules.
        
        Args:
            posts: List of posts
        
        Returns:
            Filtered list of posts
        """
        return [post for post in posts if self.should_process(post)]
