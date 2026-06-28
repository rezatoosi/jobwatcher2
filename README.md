# Reddit Job Watcher

A Python tool that monitors Reddit job boards, scores posts with AI, and sends you Telegram notifications for relevant opportunities.

Built to automate my own job hunt. Runs daily on GitHub Actions with zero hosting cost.

## How It Works

1. **Fetch**: Pulls new posts from configured subreddits (forhire, freelance_forhire, slavelabour, etc.)
2. **Score**: 
   - First pass: keyword matching (python, django, react, instagram, etc.)
   - Second pass: AI scoring (relevance, skill match, opportunity value, urgency, risk)
3. **Notify**: Sends accepted posts to Telegram
4. **Store**: SQLite database tracks everything (posts.db)

## Installation
```bash
git clone https://github.com/yourusername/jobwatcher2.git
cd jobwatcher2
pip install -r requirements.txt

Copy `.env.example` to `.env` and fill in your credentials:
- Reddit API (client_id, client_secret, user_agent)
- AI provider API keys (Groq, Google, OpenRouter, etc.)
- Telegram bot (token, chat_id)

## Configuration

Edit `config.yaml` to customize:
- Subreddits to monitor
- Keywords and scores
- AI providers and priorities
- Scoring thresholds
- Notification settings

Example keywords section:
yaml
keywords:
  python: 5
  django: 5
  react: 5
  instagram: 5
  social media: 5
  bot: 5

AI evaluates posts on five dimensions:
- **match**: how well required skills align with your profile
- **value**: budget quality, long-term potential
- **urgency**: time-sensitivity (ASAP, immediate start)
- **risk_free**: job clarity and reliability (0=sketchy, 100=solid)
- **score**: overall attractiveness (0-100)

## Usage

bash
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

# View recent posts
python main.py view --since 0     # today
python main.py view --since 1     # yesterday
python main.py view --since 2026-06-20

# Database stats
python main.py stats
python main.py stats --providers

# Run as daemon (daily at 08:00 UTC)
python main.py daemon --run-time 08:00

Sample output:

[freelance_forhire] [Hiring] Freelance Social Media Assistant
  Post ID:   1uekog8
  Status:    accepted
  Score:     55.0
  Keywords:  social media, instagram
  
  Provider:  openrouter (inclusionai/ling-2.6-flash)
  Breakdown: match=60, value=40, urgency=20, risk_free=70
  Reason:    Low-skill social media task that aligns with your broad 
platform experience, but limited growth and very low pay.

## GitHub Actions (Optional)

The repo includes `.github/workflows/daily-run.yml` that runs automatically every day at 08:00 UTC.

**Setup:**
1. Add repository secrets in Settings → Secrets and variables → Actions:
   - `REDDIT_CLIENT_ID`
   - `REDDIT_CLIENT_SECRET`
   - `REDDIT_USER_AGENT`
   - `GROQ_API_KEY` (or your preferred AI provider)
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

2. Workflow handles the database automatically:
   - First run: uses `posts.db` from repo
   - Subsequent runs: downloads artifact from previous run, updates it, re-uploads
   - Artifacts retained for 90 days

Manual trigger: Actions tab → daily-run → Run workflow

## Notes

**Why is posts.db in the repo?**  
Because I run this on GitHub Actions for my own job search. The workflow downloads the previous artifact, but needs a seed database for the first run. Not best practice for a team project, but works perfectly for a personal automation tool.

**Future plans:**  
- Support for LinkedIn, Indeed, and other job boards
- Web dashboard for browsing posts
- Configurable notification templates

**If this helps you land paid work**, consider [buying me a coffee](https://ko-fi.com/yourusername) ☕

## License

AGPL-3.0 — see [LICENSE](LICENSE)