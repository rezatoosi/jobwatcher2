"""Main entry point for Reddit post monitoring."""

from pathlib import Path

from src.config import load_config
from src.fetcher.reddit import RedditFetcher
from src.fetcher.reddit import RedditRSSFetcher
from src.scoring.scorer import KeywordScorer
from src.storage.database import Database


def main():
    """Run the Reddit post monitoring workflow."""
    # Load configuration
    config_path = Path("config.yaml")
    config = load_config(config_path)
    
    print(f"Configuration loaded successfully:")
    print(f"  Subreddits: {', '.join(config.subreddits)}")
    print(f"  Keywords: {len(config.keywords)} keywords")
    print(f"  Min score threshold: {config.min_score}")
    print(f"  Fetch Limit: {config.fetch_limit}")
    print()
    
    # Initialize components
    db = Database("posts.db")
    
    # Build proxy URL from network config
    proxy_url = None
    # if config.network.proxy:
    #     proxy_url = config.network.proxy
    
    # fetcher = RedditFetcher(
    #     request_delay=config.request_delay,
    #     proxy_http=proxy_url,
    #     timeout=config.network.request_timeout
    # )

    fetcher = RedditRSSFetcher(
        subreddits=config.subreddits,
        limit=config.fetch_limit,
        request_delay=config.request_delay,
        proxy_http=proxy_url
    )
    
    scorer = KeywordScorer(keywords=config.keywords)
    
    # Fetch and process posts
    print("Fetching posts from Reddit...")
    new_posts_count = 0
    rejected_posts_count = 0
    duplicate_posts_count = 0
    
    for post in fetcher.fetch_posts():
        print(f"  Found: r/{post.subreddit} - {post.title[:50]}...")
        
        # Check if post already exists
        if db.post_exists(post.post_id):
            duplicate_posts_count += 1
            continue
        
        # Score the post
        scored_post = scorer.score_post(post)
        
        # Decide based on score threshold
        if scored_post.score >= config.min_score:
            db.save_post(
                post_id=post.post_id,
                subreddit=post.subreddit,
                title=post.title,
                body=post.body,
                url=post.url,
                score=scored_post.score,
                matched_keywords=scored_post.matched_keywords
            )
            new_posts_count += 1
            print(f"    ✓ Accepted (score: {scored_post.score}, keywords: {', '.join(scored_post.matched_keywords)})")
        else:
            db.save_rejected_post(
                post_id=post.post_id,
                subreddit=post.subreddit,
                title=post.title,
                body=post.body,
                url=post.url,
                score=scored_post.score,
                matched_keywords=scored_post.matched_keywords
            )
            rejected_posts_count += 1
            print(f"    ✗ Rejected (score: {scored_post.score})")
    
    print()
    print(f"Summary:")
    print(f"  New posts saved: {new_posts_count}")
    print(f"  Posts rejected: {rejected_posts_count}")
    print(f"  Duplicate posts skipped: {duplicate_posts_count}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        raise
