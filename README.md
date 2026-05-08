# MyCineBD Telegram Bot 🎬

Automated movie & TV series posting bot for [@mycinebd](https://t.me/mycinebd) channel with **organic SEO optimization**.

## Features
- 🎥 **Hollywood** — Prime time evening posts
- 🎞️ **Bollywood** — Morning slot
- 🎬 **South Indian** (Tamil/Telugu) — Alternating mornings
- 🇰🇷 **Korean Cinema** — Tuesday afternoon
- 🇯🇵 **Japanese Cinema** — Friday afternoon
- 📺 **TV Series** — Sunday afternoon (trending)
- 🔥 **Trending Movies** — TMDB trending API priority
- 🏆 **Weekly Top 5** — Saturday afternoon (viral content)
- 🗳 **Polls** — Thursday afternoon (engagement boost)
- 🏷️ **Auto Hashtags** — SEO-optimized for Telegram search
- 💬 **Why Watch?** — Engagement hooks in every post

## Daily Schedule (BD Time)

| Slot | Time | Content | Posts |
|------|------|---------|-------|
| 🌅 Morning | 10:00 AM | Bollywood / South Indian | 2 |
| 🌆 Afternoon | 3:00 PM | Trending / Korean / Series / Poll / Top 5 | 1-2 |
| 🌙 Evening | 8:30 PM | Hollywood (Prime Time) | 2 |

**Total: 5-6 posts/day** — optimized for maximum organic reach.

## Setup

### 1. Install locally
```bash
pip install -r requirements.txt
```

### 2. Environment Variables
```bash
export TMDB_API_KEY="your_tmdb_api_key"
export BOT_TOKEN="your_telegram_bot_token"
export CHANNEL_ID="@mycinebd"
```

### 3. Run locally
```bash
python mycinebd_bot.py morning    # Morning session
python mycinebd_bot.py afternoon  # Afternoon session
python mycinebd_bot.py evening    # Evening session
```

### 4. GitHub Actions (Auto Daily Post)
1. Push to GitHub repository
2. Go to Settings → Secrets → Add:
   - `BOT_TOKEN` — Telegram bot token
   - `TMDB_API_KEY` — TMDB API key
   - `CHANNEL_ID` — Channel ID (e.g. `@mycinebd` or numeric ID)
3. Actions will run automatically 3x/day ✅

## Weekly Content Calendar

| Day | Morning | Afternoon | Evening |
|-----|---------|-----------|---------|
| Mon | Bollywood | Trending | Hollywood |
| Tue | South Indian (Tamil) | Korean | Hollywood |
| Wed | Bollywood | Trending | Hollywood |
| Thu | South Indian (Telugu) | 🗳 Poll + Trending | Hollywood |
| Fri | Bollywood | Japanese | Hollywood |
| Sat | Bollywood | 🏆 Top 5 List | Hollywood |
| Sun | Bollywood | 📺 TV Series | Hollywood |

## Post Format
- 🖼 High-quality movie poster
- ⭐ Rating + vote count
- 🎭 Genre
- 📖 Short overview (max 200 chars)
- 🔥 "Why Watch?" engagement hooks
- 🏷️ Auto-generated hashtags (8-10 per post)
- [▶️ Watch Free] button → mycinebd.cloud
- [📢 Join @mycinebd] button

## Files
- `mycinebd_bot.py` — Main bot
- `requirements.txt` — Dependencies
- `.github/workflows/daily_post.yml` — GitHub Actions (3x daily)
- `posted_movies.json` — Posted history (auto-managed)
