# src/cli/commands.py
"""CLI commands for Reddit post monitoring."""

from pathlib import Path
from typing import Optional

from src.config import load_config
from src.fetcher.reddit import RedditRSSFetcher
from src.scoring.scorer import KeywordScorer
from src.storage.database import Database


def cmd_fetch(config_path: Path = Path("config.yaml")):
    """Fetch new posts from Reddit and process them."""
    config = load_config(config_path)
    
    print(f"Configuration loaded:")
    print(f"  Subreddits: {', '.join(config.subreddits)}")
    print(f"  Keywords: {len(config.keywords)} keywords")
    print(f"  Min score: {config.min_score}")
    print(f"  Fetch limit: {config.fetch_limit}")
    print()
    
    db = Database("posts.db")
    
    proxy_url = None
    # if config.network.proxy:
    #     proxy_url = config.network.proxy
    
    fetcher = RedditRSSFetcher(
        subreddits=config.subreddits,
        limit=config.fetch_limit,
        request_delay=config.request_delay,
        proxy_http=proxy_url
    )
    
    scorer = KeywordScorer(keywords=config.keywords)
    
    print("Fetching posts from Reddit...")
    new_posts = 0
    rejected_posts = 0
    duplicate_posts = 0
    
    for post in fetcher.fetch_posts():
        print(f"  Found: r/{post.subreddit} - {post.title[:50]}...")
        
        if db.post_exists(post.post_id):
            duplicate_posts += 1
            continue
        
        scored_post = scorer.score_post(post)
        
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
            new_posts += 1
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
            rejected_posts += 1
            print(f"    ✗ Rejected (score: {scored_post.score})")
    
    print()
    print(f"Summary:")
    print(f"  New posts: {new_posts}")
    print(f"  Rejected: {rejected_posts}")
    print(f"  Duplicates: {duplicate_posts}")


def cmd_view(show_accepted: bool = True, show_rejected: bool = False, limit: Optional[int] = None):
    """View posts from database."""
    db = Database("posts.db")
    
    if show_accepted:
        print("=== Accepted Posts ===\n")
        posts = db.get_all_posts(limit=limit)
        
        if not posts:
            print("No accepted posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                print(f"{idx}. [{post['subreddit']}] {post['title']}")
                print(f"   Score: {post['score']} | Keywords: {post['matched_keywords']}")
                print(f"   URL: {post['url']}")
                print(f"   Created: {post['created_at']}")
                if post['body']:
                    body_preview = post['body'][:150].replace('\n', ' ')
                    print(f"   Body: {body_preview}{'...' if len(post['body']) > 150 else ''}")
                print()
    
    if show_rejected:
        print("=== Rejected Posts ===\n")
        posts = db.get_rejected_posts(limit=limit)
        
        if not posts:
            print("No rejected posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                print(f"{idx}. [{post['subreddit']}] {post['title']}")
                print(f"   Score: {post['score']} | Keywords: {post['matched_keywords']}")
                print(f"   URL: {post['url']}")
                print(f"   Created: {post['created_at']}")
                print()


def cmd_stats():
    """Display database statistics."""
    db = Database("posts.db")
    
    accepted_count = db.count_posts()
    rejected_count = db.count_rejected_posts()
    
    print("=== Database Statistics ===\n")
    print(f"Accepted posts: {accepted_count}")
    print(f"Rejected posts: {rejected_count}")
    print(f"Total posts: {accepted_count + rejected_count}")
    print()
    
    # Top subreddits
    top_subreddits = db.get_top_subreddits(limit=5)
    if top_subreddits:
        print("Top subreddits (accepted):")
        for sr, count in top_subreddits:
            print(f"  r/{sr}: {count} posts")
