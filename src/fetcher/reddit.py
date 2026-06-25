# src/fetcher/reddit.py
import time
import logging
from typing import Optional
from datetime import datetime, timezone
import requests
import xml.etree.ElementTree as ET
import html
import re

logger = logging.getLogger(__name__)


class RedditPost:
    """Represents a Reddit post with relevant fields."""
    
    def __init__(
        self,
        post_id: str,
        title: str,
        url: str,
        subreddit: str,
        author: str,
        created_utc: int,
        score: int = 0,
        num_comments: int = 0,
        body: str = ""
    ):
        self.post_id = post_id
        self.title = title
        self.url = url
        self.subreddit = subreddit
        self.author = author
        self.created_utc = created_utc
        self.score = score
        self.num_comments = num_comments
        self.body = body

    def __repr__(self):
        return f"<RedditPost {self.post_id}: {self.title[:50]}>"


class RedditFetcher:
    """Fetches posts from Reddit using JSON API."""
    
    def __init__(
        self,
        subreddits: list[str],
        limit: int = 25,
        request_delay: float = 2.0,
        proxy_http: Optional[str] = None,
        proxy_socks5: Optional[str] = None,
        timeout: int = 10
    ):
        self.subreddits = subreddits
        self.limit = limit
        self.request_delay = request_delay
        self.timeout = timeout
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'python:reddit-job-monitor:1.0 (by /u/findingjobs)'
        })
        
        if proxy_http:
            self.session.proxies.update({
                'http': proxy_http,
                'https': proxy_http
            })
            logger.info(f"Using HTTP proxy: {proxy_http}")
        elif proxy_socks5:
            self.session.proxies.update({
                'http': proxy_socks5,
                'https': proxy_socks5
            })
            logger.info(f"Using SOCKS5 proxy: {proxy_socks5}")

    def fetch_posts(self) -> list[RedditPost]:
        """Fetch posts from all configured subreddits."""
        all_posts = []
        
        for idx, subreddit in enumerate(self.subreddits):
            if idx > 0:
                time.sleep(self.request_delay)
            
            try:
                posts = self._fetch_subreddit(subreddit)
                all_posts.extend(posts)
                logger.info(f"Fetched {len(posts)} posts from r/{subreddit}")
            except Exception as e:
                logger.error(f"Failed to fetch r/{subreddit}: {e}")
                continue
        
        return all_posts


    def _fetch_subreddit(self, subreddit: str) -> list[RedditPost]:
        """Fetch posts from a single subreddit using JSON API."""
        url = f"https://www.reddit.com/r/{subreddit}/new.json"
        params = {'limit': self.limit}
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            for child in data.get('data', {}).get('children', []):
                post_data = child.get('data', {})
                
                post = RedditPost(
                    post_id=post_data.get('id', ''),
                    title=post_data.get('title', ''),
                    url=post_data.get('url', ''),
                    subreddit=post_data.get('subreddit', ''),
                    author=post_data.get('author', ''),
                    created_utc=int(post_data.get('created_utc', 0)),
                    score=post_data.get('score', 0),
                    num_comments=post_data.get('num_comments', 0),
                    body=post_data.get('selftext', '')
                )
                posts.append(post)
            
            return posts
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching r/{subreddit}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for r/{subreddit}: {e}")
            raise


class RedditRSSFetcher:
    """Fetches posts from Reddit using RSS feeds (Old Reddit)."""
    
    def __init__(
        self,
        subreddits: list[str],
        limit: int = 25,
        request_delay: float = 60,
        proxy_http: Optional[str] = None,
        proxy_socks5: Optional[str] = None,
        timeout: int = 10
    ):
        self.subreddits = subreddits
        self.limit = limit
        self.request_delay = request_delay
        self.timeout = timeout
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'python:reddit-job-monitor:1.0 (by /u/rezatoosi)'
        })
        
        if proxy_http:
            self.session.proxies.update({
                'http': proxy_http,
                'https': proxy_http
            })
            logger.info(f"RSS Fetcher using HTTP proxy: {proxy_http}")
        elif proxy_socks5:
            self.session.proxies.update({
                'http': proxy_socks5,
                'https': proxy_socks5
            })
            logger.info(f"RSS Fetcher using SOCKS5 proxy: {proxy_socks5}")

    def fetch_posts(self) -> list[RedditPost]:
        """Fetch posts from all configured subreddits."""
        all_posts = []
        
        for idx, subreddit in enumerate(self.subreddits):
            if idx > 0:
                time.sleep(self.request_delay)
            
            try:
                posts = self._fetch_subreddit(subreddit)
                all_posts.extend(posts)
                logger.info(f"Fetched {len(posts)} posts from r/{subreddit} via RSS")
            except Exception as e:
                logger.error(f"Failed to fetch r/{subreddit} via RSS: {e}")
                continue
        
        return all_posts

    def _fetch_subreddit(self, subreddit: str) -> list[RedditPost]:
        """Fetch posts from a single subreddit using RSS."""
        url = f"https://old.reddit.com/r/{subreddit}/new/.rss"
        params = {'limit': self.limit}
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse XML
            root = ET.fromstring(response.content)
            
            # Find all entry elements (Atom format)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('.//atom:entry', namespace)
            
            posts = []
            for entry in entries[:self.limit]:
                # Extract ID (format: t3_xxxxx)
                entry_id = entry.find('atom:id', namespace)
                post_id = entry_id.text.split('_')[-1] if entry_id is not None else ''
                
                # Extract title
                title_elem = entry.find('atom:title', namespace)
                title = title_elem.text if title_elem is not None else ''
                
                # Extract link
                link_elem = entry.find('atom:link', namespace)
                url = link_elem.get('href') if link_elem is not None else ''
                
                # Extract author
                author_elem = entry.find('atom:author/atom:name', namespace)
                author = author_elem.text.replace('/u/', '') if author_elem is not None else ''
                
                # Extract published time
                published_elem = entry.find('atom:published', namespace)
                if published_elem is not None:
                    try:
                        # Parse ISO 8601 format: 2026-06-19T12:34:56+00:00
                        dt = datetime.fromisoformat(published_elem.text.replace('Z', '+00:00'))
                        created_utc = int(dt.timestamp())
                    except:
                        created_utc = int(datetime.now(timezone.utc).timestamp())
                else:
                    created_utc = int(datetime.now(timezone.utc).timestamp())
                
                # Extract content/summary
                content_elem = entry.find('atom:content', namespace)
                if content_elem is None:
                    content_elem = entry.find('atom:summary', namespace)
                
                body = ''
                if content_elem is not None and content_elem.text:
                    # Decode HTML entities
                    text = html.unescape(content_elem.text)
                    # Remove HTML tags
                    text = re.sub(r'<[^>]+>', '', text)
                    # Clean up extra whitespace
                    body = ' '.join(text.split())
                
                # Extract category (subreddit)
                category_elem = entry.find('atom:category', namespace)
                subreddit_name = category_elem.get('term') if category_elem is not None else subreddit
                
                post = RedditPost(
                    post_id=post_id,
                    title=title,
                    url=url,
                    subreddit=subreddit_name,
                    author=author,
                    created_utc=created_utc,
                    score=0,
                    num_comments=0,
                    body=body
                )
                posts.append(post)
            
            return posts
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching RSS for r/{subreddit}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for r/{subreddit} RSS: {e}")
            raise
        except ET.ParseError as e:
            logger.error(f"XML parse error for r/{subreddit}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing RSS for r/{subreddit}: {e}")
            raise
