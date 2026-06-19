# Reddit Job Monitor - Project Documentation

## 📋 Overview
A Python-based automated system for monitoring Reddit posts across multiple subreddits, scoring them based on weighted keywords, and storing relevant posts in SQLite database.

## 🎯 Project Goal
Automatically fetch and filter job-related posts from Reddit based on configurable keywords and minimum score threshold, with full audit trail of accepted and rejected posts.

## 🏗️ Architecture

### Core Components
1. **Fetcher** (`src/fetcher/reddit.py`): Retrieves posts via Old Reddit RSS
2. **Scorer** (`src/scoring/scorer.py`): Calculates relevance score based on keywords
3. **Storage** (`src/storage/database.py`): SQLite database with dual-table design
4. **Config** (`src/config/loader.py`): YAML-based configuration management
5. **Main** (`main.py`): Orchestrates fetch → score → store pipeline

## 🔧 Technical Decisions & Solutions

### Reddit API Access Challenge
**Problem:** `403 Blocked` error when accessing `www.reddit.com/new.json`
- Tested various User-Agent formats (including Reddit's recommended format)
- Proxy configured (V2rayN via `172.26.32.1:32541`) but still blocked
- Root cause: Reddit detects Iranian IP addresses regardless of proxy/DNS

**Solutions Evaluated:**
1. ❌ Official Reddit API with OAuth (complex registration from Iran, IP detection issues)
2. ✅ **Old Reddit RSS** (`https://old.reddit.com/r/{subreddit}/new/.rss`)
   - No authentication required
   - Works with proxy
   - Returns 25 most recent posts per request

### RSS Implementation Details
**Class:** `RedditRSSFetcher`
- Uses `requests` with proxy support (HTTP/SOCKS5)
- XML parsing via `xml.etree.ElementTree` (not feedparser)
- User-Agent: `python:reddit-job-monitor:1.0 (by /u/rezatoosi)`
- Configurable timeout

**Data Extraction:**
- `post_id`: from entry ID
- `title`, `url`, `subreddit`, `author`
- `created_utc`: ISO format timestamp
- `selftext`: from `<content>` or `<summary>` tag
  - HTML entities decoded (`html.unescape`)
  - HTML tags stripped (`re.sub(r'<[^>]+>', '', text)`)
  - Whitespace normalized
- `score`, `num_comments`: set to 0 (not available in RSS)

## 📊 Database Schema

### Table: `posts` (accepted posts)
```sql
CREATE TABLE posts (
post_id TEXT PRIMARY KEY,
title TEXT NOT NULL,
url TEXT NOT NULL,
subreddit TEXT NOT NULL,
author TEXT,
created_utc TEXT NOT NULL,
body TEXT,
score REAL,
matched_keywords TEXT,
fetched_at TEXT NOT NULL
)

### Table: `rejected_posts` (audit trail)
sql
CREATE TABLE rejected_posts (
post_id TEXT PRIMARY KEY,
title TEXT NOT NULL,
url TEXT NOT NULL,
subreddit TEXT NOT NULL,
author TEXT,
created_utc TEXT NOT NULL,
body TEXT,
score REAL,
matched_keywords TEXT,
rejected_at TEXT NOT NULL
)

## 🎯 Scoring System

**Class:** `KeywordScorer`
- **Input:** Keywords dictionary `{keyword: weight}`
- **Scoring logic:**
  - Case-insensitive substring matching
  - Searches in: title + selftext (body)
  - Score = sum of matched keyword weights
- **Output:** `ScoredPost` (post, score, matched_keywords list)

**Decision:** Post accepted if `score >= min_score`, otherwise rejected

## ⚙️ Configuration

**File:** `config.yaml`

yaml
keywords:
  python: 15
  django: 12
  fastapi: 10
  # keyword: weight format

min_score: 10

subreddits:
  - forhire
  - remotework

network:
  proxy: "socks5://172.26.32.1:32541"  # or null
  timeout: 30

database:
  path: "data/reddit_jobs.db"

schedule:
  interval_minutes: 30

**Important Changes:**
- `keywords`: Changed from `list[str]` to `dict[str, int]`
- Removed: `keyword_weight` field (replaced bye weights)

## 🔄 Main Pipeline Flow


1. Load config.yaml
2. Initialize RedditRSSFetcher (with proxy)
3. Initialize KeywordScorer (with keywords + min_score)
4. Initialize Database (creates tables if needed)
5. Loop subreddits:
   a. Fetc RSS posts
   b. For each post:
- Check if exists (in posts OR rejected_posts)
- Score post
- If score >= min_score:
→ save_post()
- Else:
→ save_rejected_post()
6. Display statistics (new/rejected/duplicate counts)

## 📦 Dependencies

**File:** `requirements.txt`

pyyaml>=60
requests[socks]>=2.31.0
pysocks>=1.7.1

## 🚀 Usage

bash
# Install dependencies
pip install -r reuirements.txt

# Run once
python main.py

# Schedule (via cron/systemd/etc)
*/30 * * * * /path/to/venv/bin/python /path/to/main.py

## 🔍 Key Features
- ✅ Prox support (HTTP/SOCKS5) for accessing Reddit from restricted networks
- ✅ Weighted keyword matching with configurable thresholds
- ✅ Dual-table audit trail (accepted + rejected po