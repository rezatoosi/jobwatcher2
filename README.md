# Reddit Job Watcher

This tool monitors Reddit posts, uses AI to filter out the noise, and sends you a Telegram notification when something actually matches what you're looking for. Set it up once, let it run daily, and check your phone instead of refreshing Reddit tabs.

Why? Because you don't have time to scroll through dozens of subreddits every day looking for gigs. Neither do I.

Built to automate my own job hunt. Runs in GitHub Actions with zero hosting cost.

## Features

- **Multi-subreddit monitoring** with configurable fetch intervals
- **Dual-stage scoring pipeline**:
  - Fast keyword-based filtering
  - AI-powered relevance scoring (supports OpenAI, Anthropic, and custom providers)
- **Automatic failover** between AI providers with exponential backoff
- **Telegram notifications** for high-scoring posts
- **SQLite persistence** for posts, scores, and notification history
- **Daemon mode** for continuous background monitoring
- **CLI interface** for manual fetching, scoring, and database inspection

## How It Works

1. **Fetch**: Pulls new posts from configured subreddits
2. **Score**:
   - First pass: keyword matching
   - Second pass: AI scoring
3. **Notify**: Sends accepted posts to Telegram
4. **Store**: SQLite database tracks everything (posts.db)

## Installation
```bash
git clone https://github.com/rezatoosi/jobwatcher2.git
cd jobwatcher2
pip install -r requirements.txt
```
Copy `.env.sample` to `.env` and fill in your credentials:
- Reddit API (Not needed: Currently uses rss)
- AI provider API keys (Groq, Google, OpenRouter, etc.)
- Telegram bot (bot_token, chat_id)

## Configuration

Edit `config.yaml` to customize:
- Subreddits to monitor
- Keywords and scores
- AI system prompt
- AI providers and priorities
- Scoring thresholds
- Notification settings

Example keywords section:

```yaml
keywords:
  python: 5
  django: 5
  react: 5
  instagram: 5
  social media: 5
  bot: 5
```

Example Providers Section:

```yaml
ai_providers:
  enabled: true
  max_tokens: 2048
  providers:
    - name: groq
      enabled: true
      api_key: ${GROQ_API_KEY}
      model: llama-3.3-70b-versatile
      priority: 2
    - name: google
      enabled: true
      api_key: ${GOOGLE_API_KEY}
      model: gemini-2.5-flash
      priority: 3
```

AI evaluates posts based on system prompt configured in config file.

In my case, AI evaluates job anouncements on five dimensions:
- **match**: how well required skills align with my profile
- **value**: budget quality, long-term potential
- **urgency**: time-sensitivity (ASAP, immediate start)
- **risk_free**: job clarity and reliability (0=sketchy, 100=solid)
- **score**: overall attractiveness (0-100)

## Error Handling
- **Rate limiting**: Exponential backoff with configurable retry limits
- **AI provider failures**: Automatic failover to next provider by priority
- **Network errors**: Retry with timeout and backoff
- **Duplicate detection**: Posts are fetched once and marked as fetched

## Usage

```bash
# Fetch new posts
python main.py fetch

# Score pending posts
python main.py score

# Send notifications for accepted posts
python main.py notify

# Run all three steps
python main.py run

# View accepted posts (default)
python main.py view

# View by status
python main.py view --pending
python main.py view --rejected
python main.py view --unnotified

# View specific post with AI breakdown
python main.py view --id 1uekog8

# View by date range (int = days ago, or a date like 2026-06-20)
python main.py view --since 0                # today
python main.py view --since 1                # yesterday onward
python main.py view --since 2026-06-20
python main.py view --since 7 --until 1      # from 7 days ago to yesterday
python main.py view --until 3                # up to 3 days ago

# Database stats
python main.py stats
python main.py stats --providers

# Run as daemon (daily at 08:00 UTC)
python main.py daemon --run-time 08:00
```

Sample output:

```
[freelance_forhire] [Hiring] Freelance Social Media Assistant
  Post ID:   1uekog8
  Status:    accepted
  Score:     55.0
  Keywords:  social media, instagram

  Provider:  openrouter (inclusionai/ling-2.6-flash)
  Breakdown: match=60, value=40, urgency=20, risk_free=70
  Reason:    Low-skill social media task that aligns with your broad
platform experience, but limited growth and very low pay.
```

## Notes

**Why is posts.db in the repo?**
Yes, there’s a database file in the repo. No, it’s not best practice. it’s because I run this on GitHub Actions for my own job hunt. 🤷
Also there's a config.yaml which is my own configs.

**Future plans:**
- Support fetching content from other websites
- Web dashboard for browsing posts (or maybe a saas project)
- Send notifications using other services (like email, etc.)

**If this helps you make money**, buy me a coffee ☕ 

USDT (TRC20):
TYtn7uGkpMM3sNxujjSmjv6cscaxvy2SZJ

USDT (BEP20)
0xe84aa87CB91a88dcdE0577E3aB39F5e1b744A947

## License

AGPL-3.0 — see [LICENSE](./LICENSE)
