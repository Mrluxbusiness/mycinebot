import requests
import json
import os
import re
import asyncio
from datetime import date, datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

# ─── CONFIG ───────────────────────────────────────────
TMDB_API_KEY = os.environ["TMDB_API_KEY"]
BOT_TOKEN    = os.environ["BOT_TOKEN"]

_cid = os.environ.get("CHANNEL_ID", "0")
CHANNEL_ID = int(_cid) if _cid.lstrip("-").isdigit() else _cid

WATCH_BASE    = "https://mycinebd.cloud"
POSTED_FILE   = "posted_movies.json"
BOT_NAME      = "MyCineBD"
CHANNEL_USER  = "@mycinebd"

# ─── SCHEDULE CONFIG ──────────────────────────────────
POSTS_PER_SLOT   = 2
POST_GAP_SEC     = 3 * 60       # 3 min gap between posts
EMBED_DELAY_DAYS = 30

# ─── YEAR PRIORITY ────────────────────────────────────
YEAR_PRIORITY      = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015]
MAX_PAGES_PER_YEAR = 10

# ─── API ──────────────────────────────────────────────
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG  = "https://image.tmdb.org/t/p/w500"

# ─── GENRE MAPS ──────────────────────────────────────
GENRE_MAP = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "SciFi", 10770: "TVMovie",
    53: "Thriller", 10752: "War", 37: "Western"
}

TV_GENRE_MAP = {
    10759: "ActionAdventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10751: "Family", 10762: "Kids",
    9648: "Mystery", 878: "SciFi", 10766: "Soap", 37: "Western"
}

# ─── CONTENT SCHEDULE (day 0=Mon … 6=Sun) ─────────────
CONTENT_SCHEDULE = {
    "morning": {
        0: ("movie", "hi",    "bollywood",    2),
        1: ("movie", "ta",    "south_indian", 2),
        2: ("movie", "hi",    "bollywood",    2),
        3: ("movie", "te",    "south_indian", 2),
        4: ("movie", "hi",    "bollywood",    2),
        5: ("movie", "hi",    "bollywood",    2),
        6: ("movie", "hi",    "bollywood",    2),
    },
    "afternoon": {
        0: ("trending", None,  "trending", 2),
        1: ("movie",    "ko",  "korean",   2),
        2: ("trending", None,  "trending", 2),
        3: ("poll",     None,  "poll",     1),
        4: ("movie",    "ja",  "japanese", 2),
        5: ("top5",     None,  "top5",     1),
        6: ("tv",       None,  "tv_series", 2),
    },
    "evening": {
        0: ("movie", "en", "hollywood", 2),
        1: ("movie", "en", "hollywood", 2),
        2: ("movie", "en", "hollywood", 2),
        3: ("movie", "en", "hollywood", 2),
        4: ("movie", "en", "hollywood", 2),
        5: ("movie", "en", "hollywood", 2),
        6: ("movie", "en", "hollywood", 2),
    },
}

# ─── BADGE MAP ────────────────────────────────────────
BADGE_MAP = {
    "hollywood":    "🎥 HOLLYWOOD",
    "bollywood":    "🎞️ BOLLYWOOD",
    "south_indian": "🎬 SOUTH INDIAN",
    "korean":       "🇰🇷 KOREAN CINEMA",
    "japanese":     "🇯🇵 JAPANESE CINEMA",
    "tv_series":    "📺 TV SERIES",
    "trending":     "🔥 TRENDING NOW",
}

# ═══════════════════════════════════════════════════════
#  STATE MANAGEMENT
# ═══════════════════════════════════════════════════════

def _default_cat() -> dict:
    return {"posted_ids": [], "last_year": YEAR_PRIORITY[0], "last_page": 1}


def load_full_state() -> dict:
    if not os.path.exists(POSTED_FILE):
        return {}
    with open(POSTED_FILE, "r") as f:
        data = json.load(f)
    # migrate legacy list format
    if isinstance(data, list):
        data = {"hollywood": {**_default_cat(), "posted_ids": data}}
    return data


def save_full_state(data: dict):
    with open(POSTED_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_category(data: dict, cat: str):
    cd = data.get(cat, _default_cat())
    return set(cd.get("posted_ids", [])), cd.get("last_year", YEAR_PRIORITY[0]), cd.get("last_page", 1)


def save_category(data: dict, cat: str, posted: set, year: int, page: int):
    data[cat] = {"posted_ids": list(posted), "last_year": year, "last_page": page}
    save_full_state(data)

# ═══════════════════════════════════════════════════════
#  TMDB FETCH HELPERS
# ═══════════════════════════════════════════════════════

def fetch_discover_movies(language: str, year: int, page: int = 1):
    today = date.today()
    date_to = (today - timedelta(days=EMBED_DELAY_DAYS)).isoformat() if year >= today.year else f"{year}-12-31"
    params = {
        "api_key": TMDB_API_KEY, "language": "en-US",
        "with_original_language": language, "sort_by": "popularity.desc",
        "vote_count.gte": 5,
        "primary_release_date.gte": f"{year}-01-01",
        "primary_release_date.lte": date_to,
        "page": page,
    }
    r = requests.get(f"{TMDB_BASE}/discover/movie", params=params, timeout=10)
    r.raise_for_status()
    p = r.json()
    return p.get("results", []), p.get("total_pages", 1)


def fetch_trending_movies(page: int = 1):
    r = requests.get(f"{TMDB_BASE}/trending/movie/week",
                     params={"api_key": TMDB_API_KEY, "language": "en-US", "page": page}, timeout=10)
    r.raise_for_status()
    p = r.json()
    return p.get("results", []), p.get("total_pages", 1)


def fetch_trending_tv(page: int = 1):
    r = requests.get(f"{TMDB_BASE}/trending/tv/week",
                     params={"api_key": TMDB_API_KEY, "language": "en-US", "page": page}, timeout=10)
    r.raise_for_status()
    p = r.json()
    return p.get("results", []), p.get("total_pages", 1)

# ═══════════════════════════════════════════════════════
#  CAPTION BUILDERS
# ═══════════════════════════════════════════════════════

def _fmt_votes(n: int) -> str:
    return f"{n/1000:.1f}K" if n >= 1000 else str(n)


def _stars(r: float) -> str:
    if r >= 7.5: return "⭐⭐⭐⭐⭐"
    if r >= 6.5: return "⭐⭐⭐⭐"
    if r >= 5.5: return "⭐⭐⭐"
    return "⭐⭐"


def get_genres(ids: list, tv=False) -> str:
    gm = TV_GENRE_MAP if tv else GENRE_MAP
    return " • ".join(filter(None, [gm.get(g, "") for g in ids[:3]])) or "N/A"


def _hashtags(item: dict, category: str, tv=False) -> str:
    tags = []
    title = item.get("name" if tv else "title", "")
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', title)
    words = clean.split()
    if words:
        tags.append("#" + "".join(w.capitalize() for w in words[:4]))

    gm = TV_GENRE_MAP if tv else GENRE_MAP
    for gid in item.get("genre_ids", [])[:2]:
        g = gm.get(gid, "")
        if g:
            tags.append(f"#{g}")

    df = "first_air_date" if tv else "release_date"
    yr = item.get(df, "")[:4]
    if yr:
        tags.append(f"#{'Series' if tv else 'Movie'}{yr}")

    cat_tags = {
        "hollywood": ["#Hollywood"], "bollywood": ["#Bollywood", "#HindiMovie"],
        "south_indian": ["#SouthIndian", "#Tollywood"],
        "korean": ["#KoreanMovie"], "japanese": ["#JapaneseMovie"],
        "tv_series": ["#TVSeries", "#WebSeries"], "trending": ["#Trending"],
    }
    tags.extend(cat_tags.get(category, []))
    tags.extend(["#FreeMovie", "#WatchOnline", "#MyCineBD"])

    seen = set()
    unique = []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)
    return " ".join(unique[:10])


def _why_watch(movie: dict) -> list:
    hooks = []
    rating = movie.get("vote_average", 0)
    votes = movie.get("vote_count", 0)
    pop = movie.get("popularity", 0)
    gids = set(movie.get("genre_ids", []))

    if rating >= 8.5:   hooks.append("🏆 Masterpiece — rated above 8.5")
    elif rating >= 7.5: hooks.append("⭐ Critically acclaimed ratings")
    if pop >= 100:       hooks.append("🔥 Trending worldwide right now")
    elif votes >= 10000: hooks.append("👥 Fan favorite — over 10K votes")

    gh = {28: "💥 Non-stop action", 27: "😱 Edge-of-your-seat horror",
          10749: "💕 Beautiful love story", 878: "🚀 Mind-bending sci-fi",
          35: "😂 Guaranteed laughs", 53: "🔍 Gripping thriller with twists",
          18: "🎭 Powerful dramatic performance", 16: "🎨 Stunning animation"}
    for g in gids:
        if g in gh and len(hooks) < 3:
            hooks.append(gh[g])
    return hooks[:2] or ["🎬 A must-watch movie experience"]


def build_movie_caption(movie: dict, category: str) -> str:
    title   = movie.get("title", "Unknown")
    year    = movie.get("release_date", "")[:4] or "N/A"
    rating  = round(movie.get("vote_average", 0), 1)
    votes   = movie.get("vote_count", 0)
    overview = movie.get("overview", "No description available.")
    genres  = get_genres(movie.get("genre_ids", []))
    lang    = movie.get("original_language", "").upper()
    badge   = BADGE_MAP.get(category, "🎬 MOVIE")

    if len(overview) > 200:
        overview = overview[:197] + "..."

    why = _why_watch(movie)
    why_text = "\n".join(f"✅ {h}" for h in why)
    tags = _hashtags(movie, category)

    return (
        f"{badge}\n\n"
        f"🎬 <b>{title}</b> ({year})\n"
        f"{_stars(rating)} <b>{rating}/10</b> ┃ 🗳 {_fmt_votes(votes)} votes ┃ 🎭 {genres}\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📖 {overview}\n\n"
        f"🔥 <b>Why Watch?</b>\n{why_text}\n\n"
        f"🌐 Language: {lang}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"{tags}"
    )


def build_tv_caption(show: dict, category: str) -> str:
    name    = show.get("name", "Unknown")
    year    = show.get("first_air_date", "")[:4] or "N/A"
    rating  = round(show.get("vote_average", 0), 1)
    votes   = show.get("vote_count", 0)
    overview = show.get("overview", "No description available.")
    genres  = get_genres(show.get("genre_ids", []), tv=True)
    lang    = show.get("original_language", "").upper()

    if len(overview) > 200:
        overview = overview[:197] + "..."

    tags = _hashtags(show, category, tv=True)

    return (
        f"📺 TV SERIES\n\n"
        f"🎬 <b>{name}</b> ({year})\n"
        f"{_stars(rating)} <b>{rating}/10</b> ┃ 🗳 {_fmt_votes(votes)} votes ┃ 🎭 {genres}\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📖 {overview}\n\n"
        f"🌐 Language: {lang}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"{tags}"
    )


def build_keyboard(item: dict, is_tv=False) -> InlineKeyboardMarkup:
    item_id = item.get("id")
    media_type = "tv" if is_tv else "movie"
    watch_url = f"{WATCH_BASE}/?type={media_type}&id={item_id}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️  WATCH FREE  ▶️", url=watch_url)],
        [InlineKeyboardButton(f"📢 Join {CHANNEL_USER}", url="https://t.me/mycinebd")],
    ])

# ═══════════════════════════════════════════════════════
#  POSTING FUNCTIONS
# ═══════════════════════════════════════════════════════

async def _send_poster(bot: Bot, item: dict, caption: str, keyboard, is_tv=False):
    poster = item.get("poster_path")
    title = item.get("name" if is_tv else "title", "Unknown")
    if poster:
        await bot.send_photo(chat_id=CHANNEL_ID, photo=f"{TMDB_IMG}{poster}",
                             caption=caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=CHANNEL_ID, text=caption,
                               parse_mode=ParseMode.HTML, reply_markup=keyboard)
    print(f"  ✅ Posted: {title}")


async def post_regular_movies(bot: Bot, lang: str, category: str, count: int):
    """Post discover-based movies (Hollywood, Bollywood, South Indian, Korean, Japanese)."""
    state = load_full_state()
    posted, resume_year, resume_page = load_category(state, category)
    label = BADGE_MAP.get(category, category)
    print(f"\n  🎬 {label} — posting {count} movies")
    print(f"  📂 {len(posted)} already posted | resume {resume_year} pg {resume_page}")

    done = 0
    try:
        start_idx = YEAR_PRIORITY.index(resume_year)
    except ValueError:
        start_idx = 0

    cur_year = resume_year
    cur_page = resume_page

    for yi in range(start_idx, len(YEAR_PRIORITY)):
        year = YEAR_PRIORITY[yi]
        if year != cur_year:
            cur_page = 1
        cur_year = year
        if done >= count:
            break

        while done < count:
            try:
                movies, total = fetch_discover_movies(lang, year, cur_page)
            except Exception as e:
                print(f"  ⚠️ TMDB error: {e}")
                cur_page += 1
                await asyncio.sleep(3)
                continue

            cap = min(total, MAX_PAGES_PER_YEAR)
            if not movies or cur_page > cap:
                print(f"  ℹ️ {year} exhausted. Next year.")
                break

            for m in movies:
                if done >= count:
                    break
                mid = str(m["id"])
                if mid in posted or not m.get("poster_path"):
                    continue
                try:
                    caption = build_movie_caption(m, category)
                    kb = build_keyboard(m)
                    await _send_poster(bot, m, caption, kb)
                    posted.add(mid)
                    done += 1
                    save_category(state, category, posted, cur_year, cur_page)
                    if done < count:
                        print(f"  ⏳ [{done}/{count}] Waiting {POST_GAP_SEC//60} min...")
                        await asyncio.sleep(POST_GAP_SEC)
                except Exception as e:
                    print(f"  ❌ Error [{m.get('title')}]: {e}")
                    await asyncio.sleep(3)

            if cur_page >= cap:
                break
            cur_page += 1

    save_category(state, category, posted, cur_year, cur_page)
    print(f"  🎉 {label} done — {done}/{count} posted")


async def post_trending_movies(bot: Bot, count: int):
    """Post from TMDB trending/movie/week."""
    state = load_full_state()
    posted, _, _ = load_category(state, "trending")
    print(f"\n  🔥 TRENDING — posting {count} movies")

    done = 0
    for page in range(1, 4):
        if done >= count:
            break
        try:
            movies, _ = fetch_trending_movies(page)
        except Exception as e:
            print(f"  ⚠️ Trending fetch error: {e}")
            continue
        for m in movies:
            if done >= count:
                break
            mid = str(m["id"])
            if mid in posted or not m.get("poster_path"):
                continue
            try:
                caption = build_movie_caption(m, "trending")
                kb = build_keyboard(m)
                await _send_poster(bot, m, caption, kb)
                posted.add(mid)
                done += 1
                save_category(state, "trending", posted, YEAR_PRIORITY[0], 1)
                if done < count:
                    print(f"  ⏳ [{done}/{count}] Waiting {POST_GAP_SEC//60} min...")
                    await asyncio.sleep(POST_GAP_SEC)
            except Exception as e:
                print(f"  ❌ Error [{m.get('title')}]: {e}")
                await asyncio.sleep(3)

    print(f"  🎉 Trending done — {done}/{count} posted")


async def post_tv_series(bot: Bot, count: int):
    """Post trending TV series."""
    state = load_full_state()
    posted, _, _ = load_category(state, "tv_series")
    print(f"\n  📺 TV SERIES — posting {count}")

    done = 0
    for page in range(1, 4):
        if done >= count:
            break
        try:
            shows, _ = fetch_trending_tv(page)
        except Exception as e:
            print(f"  ⚠️ TV fetch error: {e}")
            continue
        for s in shows:
            if done >= count:
                break
            sid = str(s["id"])
            if sid in posted or not s.get("poster_path"):
                continue
            try:
                caption = build_tv_caption(s, "tv_series")
                kb = build_keyboard(s, is_tv=True)
                await _send_poster(bot, s, caption, kb, is_tv=True)
                posted.add(sid)
                done += 1
                save_category(state, "tv_series", posted, YEAR_PRIORITY[0], 1)
                if done < count:
                    print(f"  ⏳ [{done}/{count}] Waiting {POST_GAP_SEC//60} min...")
                    await asyncio.sleep(POST_GAP_SEC)
            except Exception as e:
                print(f"  ❌ Error [{s.get('name')}]: {e}")
                await asyncio.sleep(3)

    print(f"  🎉 TV Series done — {done}/{count} posted")


async def post_top5(bot: Bot):
    """Post weekly Top 5 trending movies list."""
    print("\n  🏆 TOP 5 LIST — generating...")
    try:
        movies, _ = fetch_trending_movies(1)
    except Exception as e:
        print(f"  ⚠️ Top 5 fetch error: {e}")
        return

    top = [m for m in movies if m.get("poster_path")][:5]
    if len(top) < 5:
        print("  ⚠️ Not enough movies for Top 5")
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = ["🔥 <b>WEEKLY TOP 5 — TRENDING MOVIES</b>\n", "━━━━━━━━━━━━━━━━━━━━\n"]

    for i, m in enumerate(top):
        title = m.get("title", "Unknown")
        yr = m.get("release_date", "")[:4]
        rt = round(m.get("vote_average", 0), 1)
        g = get_genres(m.get("genre_ids", []))
        lines.append(f"{medals[i]} <b>{title}</b> ({yr})")
        lines.append(f"     ⭐ {rt}/10 • {g}\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━\n")
    lines.append("#Top5Movies #WeeklyPick #Trending")
    lines.append("#MyCineBD #FreeMovie #WatchOnline")
    lines.append(f"\n🍿 <i>Watch all FREE on {BOT_NAME}!</i>")

    caption = "\n".join(lines)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Watch All FREE", url=WATCH_BASE)],
        [InlineKeyboardButton(f"📢 Join {CHANNEL_USER}", url="https://t.me/mycinebd")],
    ])

    poster = top[0].get("poster_path", "")
    if poster:
        await bot.send_photo(chat_id=CHANNEL_ID, photo=f"{TMDB_IMG}{poster}",
                             caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await bot.send_message(chat_id=CHANNEL_ID, text=caption,
                               parse_mode=ParseMode.HTML, reply_markup=kb)
    print("  ✅ Top 5 posted!")


async def post_poll(bot: Bot):
    """Post an engagement poll with 4 trending movies."""
    print("\n  🗳 POLL — generating...")
    try:
        movies, _ = fetch_trending_movies(1)
    except Exception as e:
        print(f"  ⚠️ Poll fetch error: {e}")
        return

    opts = [m for m in movies if m.get("title")][:4]
    if len(opts) < 4:
        print("  ⚠️ Not enough movies for poll")
        return

    question = "🎬 Which movie should you watch this weekend?"
    options = [f"{m['title']} ({m.get('release_date','')[:4]})"[:100] for m in opts]

    await bot.send_poll(chat_id=CHANNEL_ID, question=question,
                        options=options, is_anonymous=True, allows_multiple_answers=False)
    print("  ✅ Poll posted!")

# ═══════════════════════════════════════════════════════
#  MAIN SESSION RUNNER
# ═══════════════════════════════════════════════════════

async def run_slot(slot: str):
    """Run a posting session for the given time slot (morning/afternoon/evening)."""
    bd_now = datetime.utcnow() + timedelta(hours=6)
    dow = bd_now.weekday()  # 0=Mon … 6=Sun

    print(f"\n{'='*50}")
    print(f"🚀 {BOT_NAME} Bot — {slot.upper()} Session")
    print(f"📅 {bd_now.strftime('%Y-%m-%d %A')} (BD Time)")
    print(f"{'='*50}")

    bot = Bot(token=BOT_TOKEN)

    try:
        me = await bot.get_me()
        print(f"  🤖 Bot: @{me.username}")
    except Exception as e:
        print(f"  ❌ Bot token invalid: {e}")
        return

    try:
        chat = await bot.get_chat(CHANNEL_ID)
        print(f"  ✅ Channel: {chat.title}")
    except Exception as e:
        print(f"  ❌ Channel error: {e}")
        return

    schedule = CONTENT_SCHEDULE.get(slot, {})
    config = schedule.get(dow)
    if not config:
        print(f"  ⚠️ No config for {slot} day={dow}")
        return

    content_type, lang, category, count = config
    print(f"  📋 Content: {content_type} | Category: {category} | Count: {count}")

    if content_type == "movie":
        await post_regular_movies(bot, lang, category, count)
    elif content_type == "trending":
        await post_trending_movies(bot, count)
    elif content_type == "tv":
        await post_tv_series(bot, count)
    elif content_type == "top5":
        await post_top5(bot)
    elif content_type == "poll":
        await post_poll(bot)
        # Also post 1 trending movie after the poll
        await asyncio.sleep(POST_GAP_SEC)
        await post_trending_movies(bot, 1)

    print(f"\n{'='*50}")
    print(f"✅ {BOT_NAME} — {slot.upper()} session complete!")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    import sys
    slot = sys.argv[1] if len(sys.argv) > 1 else "evening"
    print(f"🤖 {BOT_NAME} Telegram Bot")
    print(f"📢 Channel: {CHANNEL_ID}")
    print(f"🌐 Website: {WATCH_BASE}")
    print(f"🎯 Slot: {slot}")
    asyncio.run(run_slot(slot))
