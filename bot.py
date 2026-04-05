# ╔══════════════════════════════════════════════════════════╗
# ║         @KENSHIN_ANIME — AnimeDubHindi Telegram Bot      ║
# ║         Made with Pyrofork | Real Scraping Engine        ║
# ╚══════════════════════════════════════════════════════════╝

import asyncio
import re
import io
import os
import logging
from urllib.parse import quote_plus, urljoin

import aiohttp
from bs4 import BeautifulSoup
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# ─── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("KenshinAnime")

# ─── Config from env ───────────────────────────────────────
API_ID       = int(os.environ["API_ID"])
API_HASH     = os.environ["API_HASH"]
BOT_TOKEN    = os.environ["BOT_TOKEN"]
ADMIN_ID     = int(os.environ.get("ADMIN_ID", 0))

# ─── Constants ─────────────────────────────────────────────
MAIN_SITE    = "https://www.animedubhindi.me"
LINKS_SITE   = "https://links.animedubhindi.me"
FILEPRESS    = "https://new2.filepress.wiki"
CHANNEL_TAG  = "@KENSHIN_ANIME"

DEFAULT_CAPTION = (
    "<b><blockquote>✨ {anime_name} ✨</blockquote>\n"
    "🌸 Episode : {ep} [S{season}]\n"
    "🌸 Quality : {quality}\n"
    "🌸 Audio : Hindi Dub 🎙️ | Official\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "<blockquote>🚀 For More Join 🔰 [@KENSHIN_ANIME]</blockquote></b>\n"
    "━━━━━━━━━━━━━━━━━━━━━"
)

# ─── In-memory session stores ──────────────────────────────
user_captions:   dict[int, str] = {}   # uid → caption template
user_thumbnails: dict[int, bytes] = {} # uid → photo bytes
user_state:      dict[int, dict] = {}  # uid → current session data

QUALITIES = ["360p", "480p", "720p", "1080p", "2160p"]

# ─── HTTP helpers ──────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

async def fetch_html(url: str, session: aiohttp.ClientSession) -> str | None:
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status == 200:
                return await r.text(errors="replace")
            log.warning(f"HTTP {r.status} for {url}")
    except Exception as e:
        log.error(f"fetch_html error {url}: {e}")
    return None


# ─── 1. Search animedubhindi.me ────────────────────────────
async def search_anime(query: str) -> list[dict]:
    """
    Returns list of {title, url, thumb} from site search.
    """
    url = f"{MAIN_SITE}/?s={quote_plus(query)}"
    async with aiohttp.ClientSession() as s:
        html = await fetch_html(url, s)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    results = []

    # WordPress typical article card selectors
    for article in soup.select("article, .post, .item-post")[:8]:
        a_tag = (
            article.select_one("h2 a, h3 a, .entry-title a, .post-title a")
            or article.select_one("a[href]")
        )
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        href  = a_tag.get("href", "")
        if not href.startswith("http"):
            href = urljoin(MAIN_SITE, href)
        # thumbnail
        img = article.select_one("img")
        thumb = ""
        if img:
            thumb = img.get("data-src") or img.get("src") or ""
        if title and href and MAIN_SITE in href:
            results.append({"title": title, "url": href, "thumb": thumb})

    # De-duplicate by URL
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return unique


# ─── 2. Extract download-page slug from anime page ─────────
async def get_download_page_url(anime_url: str) -> str | None:
    """
    Fetches the anime post page, finds the links.animedubhindi.me episode URL.
    Returns something like: https://links.animedubhindi.me/episode/jujutsu-kaisen-season-3/
    """
    async with aiohttp.ClientSession() as s:
        html = await fetch_html(anime_url, s)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "links.animedubhindi.me/episode/" in href:
            return href.rstrip("/") + "/"
    return None


# ─── 3. Scrape episode list + quality → FilePress IDs ──────
def _parse_quality_from_text(text: str) -> str:
    for q in ["2160p", "1080p", "720p", "480p", "360p"]:
        if q.lower() in text.lower():
            return q
    return "Unknown"

def _parse_episode_from_text(text: str) -> str:
    """Extract episode number from filename/text."""
    # Patterns: S01E04, E04, Episode 4, Ep4, ep.04
    m = re.search(r"[Ee][Pp]?[\.\s]?0*(\d+)", text)
    if m:
        return m.group(1).zfill(2)
    m = re.search(r"[Ss]\d+[Ee]0*(\d+)", text)
    if m:
        return m.group(1).zfill(2)
    m = re.search(r"(?:episode|ep)[\s\.\-_]?(\d+)", text, re.IGNORECASE)
    if m:
        return m.group(1).zfill(2)
    return "??"

def _parse_season_from_text(text: str) -> str:
    m = re.search(r"[Ss](?:eason)?[\s\.\-_]?0*(\d+)", text)
    if m:
        return m.group(1).zfill(2)
    return "01"

async def scrape_episodes(download_page_url: str) -> list[dict]:
    """
    Scrapes links.animedubhindi.me/episode/{slug}/
    Returns list of:
    {
      ep: "01", season: "03", quality: "1080p",
      filepress_id: "697b9d76bf879ec71ab5ac99",
      filename: "[AnimeDubHindi] JJK S03E01 1080p.mkv",
      label: "E01 — 1080p"
    }
    """
    async with aiohttp.ClientSession() as s:
        html = await fetch_html(download_page_url, s)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    episodes = []

    # FilePress links: new2.filepress.wiki/file/{id}
    fp_pattern = re.compile(
        r"https?://(?:new2|new|www)\.filepress\.wiki/(?:file|download)/([A-Za-z0-9]+)"
    )

    # Each download row / table row / list item
    # Try multiple selectors common on such sites
    rows = (
        soup.select("tr")                        # table rows
        or soup.select(".entry-content p")        # paragraphs
        or soup.select(".download-links a")
        or soup.select("a[href*='filepress']")
    )

    # Strategy: collect ALL filepress links with their surrounding text
    all_links = soup.find_all("a", href=fp_pattern)
    if not all_links:
        # fallback: grep raw HTML
        for m in fp_pattern.finditer(html):
            fp_id = m.group(1)
            # find context around match
            start = max(0, m.start() - 200)
            context = html[start: m.end() + 50]
            ctxt_text = BeautifulSoup(context, "lxml").get_text(" ")
            quality  = _parse_quality_from_text(ctxt_text)
            ep_num   = _parse_episode_from_text(ctxt_text)
            season   = _parse_season_from_text(ctxt_text)
            episodes.append({
                "ep": ep_num, "season": season, "quality": quality,
                "filepress_id": fp_id,
                "filename": f"[{CHANNEL_TAG}]E{ep_num}S{season}{quality}.mkv",
                "label": f"E{ep_num} — {quality}"
            })
        return _dedup_episodes(episodes)

    for a in all_links:
        href = a.get("href", "")
        m = fp_pattern.search(href)
        if not m:
            continue
        fp_id = m.group(1)
        # Get surrounding text (parent row/div/td for context)
        context_el = a.find_parent("tr") or a.find_parent("div") or a.find_parent("p") or a
        ctx_text = context_el.get_text(" ", strip=True)
        if not ctx_text:
            ctx_text = a.get_text(" ", strip=True)

        quality = _parse_quality_from_text(ctx_text)
        ep_num  = _parse_episode_from_text(ctx_text)
        season  = _parse_season_from_text(ctx_text)

        episodes.append({
            "ep": ep_num, "season": season, "quality": quality,
            "filepress_id": fp_id,
            "filename": f"[{CHANNEL_TAG}]E{ep_num}S{season}{quality}.mkv",
            "label": f"E{ep_num} — {quality}"
        })

    return _dedup_episodes(episodes)


def _dedup_episodes(eps: list[dict]) -> list[dict]:
    seen = set()
    out  = []
    for e in eps:
        key = (e["ep"], e["quality"], e["filepress_id"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    # Sort by episode then quality
    quality_order = {"360p": 0, "480p": 1, "720p": 2, "1080p": 3, "2160p": 4, "Unknown": 5}
    out.sort(key=lambda x: (x["ep"], quality_order.get(x["quality"], 9)))
    return out


# ─── 4. Resolve FilePress → direct download URL ────────────
async def resolve_filepress(fp_id: str) -> tuple[str | None, str | None]:
    """
    Returns (direct_download_url, filename)
    Tries /file/{id} page, extracts real download link.
    """
    file_page = f"{FILEPRESS}/file/{fp_id}"
    async with aiohttp.ClientSession() as s:
        html = await fetch_html(file_page, s)
        if not html:
            return None, None
        soup = BeautifulSoup(html, "lxml")

        # Look for download button / direct link
        dl_patterns = [
            re.compile(r"https?://[^\"'>\s]+\.(?:mkv|mp4|avi|mov)[^\"'>\s]*", re.IGNORECASE),
            re.compile(rf"https?://(?:new2|new)\.filepress\.wiki/download/([^\"'>\s]+)")
        ]

        # Check <a> tags
        for a in soup.find_all("a", href=True):
            href = a["href"]
            for pat in dl_patterns:
                if pat.search(href):
                    filename = href.split("/")[-1].split("?")[0]
                    return href, filename

        # Check title for filename
        title_tag = soup.find("title")
        title_text = title_tag.get_text(strip=True) if title_tag else ""
        # title is often the filename
        fname_match = re.search(r"([\w\[\]\(\)\s\.\-]+\.(?:mkv|mp4))", title_text)
        if fname_match:
            raw_fname = fname_match.group(1).strip()
            dl_url = f"{FILEPRESS}/download/{quote_plus(raw_fname)}"
            return dl_url, raw_fname

        # Grep raw HTML for download links
        for pat in dl_patterns:
            m = pat.search(html)
            if m:
                href = m.group(0).strip("\"'")
                filename = href.split("/")[-1].split("?")[0]
                return href, filename

        # Last resort: construct from ID
        # Try fetching /download/{id} directly
        dl_url = f"{FILEPRESS}/download/{fp_id}"
        # Check if it redirects to actual file
        try:
            async with s.head(dl_url, headers=HEADERS,
                               allow_redirects=True,
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status in (200, 206):
                    final_url = str(r.url)
                    filename = final_url.split("/")[-1].split("?")[0] or f"{fp_id}.mkv"
                    return final_url, filename
        except Exception:
            pass

    return None, None


# ─── 5. Download bytes from URL ────────────────────────────
async def download_file(url: str, progress_cb=None) -> io.BytesIO | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=HEADERS,
                              timeout=aiohttp.ClientTimeout(total=3600)) as r:
                if r.status not in (200, 206):
                    log.error(f"Download failed {r.status}: {url}")
                    return None
                total  = int(r.headers.get("Content-Length", 0))
                buf    = io.BytesIO()
                done   = 0
                async for chunk in r.content.iter_chunked(1024 * 512):  # 512 KB chunks
                    buf.write(chunk)
                    done += len(chunk)
                    if progress_cb and total:
                        await progress_cb(done, total)
                buf.seek(0)
                return buf
    except Exception as e:
        log.error(f"download_file error: {e}")
        return None


# ─── Bot App ───────────────────────────────────────────────
app = Client(
    "kenshin_anime_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ─── /start ────────────────────────────────────────────────
@app.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    await msg.reply_text(
        "<b>🎌 Welcome to <a href='https://t.me/KENSHIN_ANIME'>@KENSHIN_ANIME</a> Anime Bot! 🎌</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>How to use:</b>\n"
        "Just type any anime name and I'll search it for you!\n\n"
        "🔍 <b>Example:</b>\n"
        "<code>Jujutsu Kaisen Season 3</code>\n"
        "<code>Attack on Titan Season 4</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Use /help to see all commands.\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<blockquote>🚀 Join ➜ @KENSHIN_ANIME for latest anime!</blockquote>",
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


# ─── /help ─────────────────────────────────────────────────
@app.on_message(filters.command("help"))
async def cmd_help(_, msg: Message):
    await msg.reply_text(
        "<b>📖 @KENSHIN_ANIME Bot — Help Guide</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>🔍 Search Anime:</b>\n"
        "Just type the anime name! No command needed.\n"
        "<code>Jujutsu Kaisen Season 3</code>\n\n"
        "<b>🎬 Then:</b>\n"
        "1️⃣ Choose anime from search results\n"
        "2️⃣ Choose episode(s) or all at once\n"
        "3️⃣ Choose quality (360p/480p/720p/1080p/2160p)\n"
        "4️⃣ Bot sends video directly! ✅\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>⚙️ Commands:</b>\n"
        "/start — Welcome message\n"
        "/help — This guide\n"
        "/set_caption &lt;text&gt; — Set custom caption\n"
        "   Variables: <code>{anime_name}</code> <code>{ep}</code> <code>{season}</code> <code>{quality}</code>\n"
        "/get_caption — View your current caption\n"
        "/reset_caption — Reset to default caption\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>🖼️ Set Thumbnail:</b>\n"
        "Send any photo → it becomes your thumbnail!\n\n"
        "<b>📦 File Name Format:</b>\n"
        "<code>[@KENSHIN_ANIME]E01S03720p.mkv</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<blockquote>🚀 For More Join 🔰 @KENSHIN_ANIME</blockquote>",
        parse_mode=enums.ParseMode.HTML
    )


# ─── /set_caption ──────────────────────────────────────────
@app.on_message(filters.command("set_caption"))
async def cmd_set_caption(_, msg: Message):
    uid  = msg.from_user.id
    text = msg.text.split(None, 1)
    if len(text) < 2:
        await msg.reply_text(
            "❌ Usage: <code>/set_caption Your caption here</code>\n\n"
            "Available variables:\n"
            "<code>{anime_name}</code> — Anime title\n"
            "<code>{ep}</code> — Episode number\n"
            "<code>{season}</code> — Season number\n"
            "<code>{quality}</code> — Video quality",
            parse_mode=enums.ParseMode.HTML
        )
        return
    user_captions[uid] = text[1].strip()
    await msg.reply_text("✅ Custom caption set successfully!", parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.command("get_caption"))
async def cmd_get_caption(_, msg: Message):
    uid = msg.from_user.id
    cap = user_captions.get(uid, DEFAULT_CAPTION)
    await msg.reply_text(
        f"<b>📝 Your current caption:</b>\n<code>{cap}</code>",
        parse_mode=enums.ParseMode.HTML
    )


@app.on_message(filters.command("reset_caption"))
async def cmd_reset_caption(_, msg: Message):
    uid = msg.from_user.id
    user_captions.pop(uid, None)
    await msg.reply_text("✅ Caption reset to default!", parse_mode=enums.ParseMode.HTML)


# ─── Photo → set as thumbnail ──────────────────────────────
@app.on_message(filters.photo & filters.private)
async def handle_photo(_, msg: Message):
    uid  = msg.from_user.id
    photo = msg.photo
    dl   = await msg.download(in_memory=True)
    dl.seek(0)
    user_thumbnails[uid] = dl.read()
    await msg.reply_text(
        "✅ <b>Thumbnail set!</b>\nThis image will be used as thumbnail for all your future video uploads.",
        parse_mode=enums.ParseMode.HTML
    )


# ─── Text message → Search ─────────────────────────────────
@app.on_message(filters.text & filters.private & ~filters.command(["start","help","set_caption","get_caption","reset_caption"]))
async def handle_search(_, msg: Message):
    query = msg.text.strip()
    if not query:
        return
    uid = msg.from_user.id

    wait = await msg.reply_text(
        f"🔍 <b>Searching for:</b> <code>{query}</code>\n⏳ Please wait...",
        parse_mode=enums.ParseMode.HTML
    )

    results = await search_anime(query)

    if not results:
        await wait.edit_text(
            f"❌ No results found for <b>{query}</b>\n\n"
            "Try a different spelling or shorter name.",
            parse_mode=enums.ParseMode.HTML
        )
        return

    # Store results in session
    user_state[uid] = {"results": results, "query": query}

    # Build inline keyboard
    buttons = []
    for i, r in enumerate(results):
        short_title = r["title"][:50] + ("…" if len(r["title"]) > 50 else "")
        buttons.append([InlineKeyboardButton(
            f"🎬 {short_title}",
            callback_data=f"anime_select|{uid}|{i}"
        )])

    await wait.edit_text(
        f"🔍 <b>Results for:</b> <code>{query}</code>\n\n"
        f"📋 Found <b>{len(results)}</b> result(s). Choose one:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


# ─── Callback: anime selected ──────────────────────────────
@app.on_callback_query(filters.regex(r"^anime_select\|"))
async def cb_anime_select(_, cq: CallbackQuery):
    _, uid_str, idx_str = cq.data.split("|")
    uid = int(uid_str)
    if cq.from_user.id != uid:
        await cq.answer("❌ This is not your session!", show_alert=True)
        return

    idx     = int(idx_str)
    results = user_state.get(uid, {}).get("results", [])
    if idx >= len(results):
        await cq.answer("Session expired. Search again.", show_alert=True)
        return

    chosen = results[idx]
    await cq.answer()
    await cq.message.edit_text(
        f"✅ <b>Selected:</b> {chosen['title']}\n\n"
        f"🔗 Fetching episode list from website...\n⏳ Please wait...",
        parse_mode=enums.ParseMode.HTML
    )

    # Fetch download page URL
    dl_page_url = await get_download_page_url(chosen["url"])
    if not dl_page_url:
        await cq.message.edit_text(
            f"❌ Could not find download page for:\n<b>{chosen['title']}</b>\n\n"
            "This anime may not have download links yet.",
            parse_mode=enums.ParseMode.HTML
        )
        return

    # Scrape episodes
    episodes = await scrape_episodes(dl_page_url)
    if not episodes:
        await cq.message.edit_text(
            f"❌ No episodes found for:\n<b>{chosen['title']}</b>",
            parse_mode=enums.ParseMode.HTML
        )
        return

    # Save to session
    user_state[uid]["chosen"]       = chosen
    user_state[uid]["dl_page_url"]  = dl_page_url
    user_state[uid]["episodes"]     = episodes
    user_state[uid]["page"]         = 0

    await _show_episode_list(cq.message, uid, episodes, chosen["title"], page=0)


async def _show_episode_list(msg, uid: int, episodes: list[dict], anime_title: str, page: int = 0):
    """Paginated episode list with quality buttons."""
    per_page = 8
    total    = len(episodes)
    start    = page * per_page
    end      = min(start + per_page, total)
    page_eps = episodes[start:end]

    buttons = []

    # Episode buttons
    for i, ep in enumerate(page_eps):
        real_idx = start + i
        buttons.append([InlineKeyboardButton(
            f"▶️ {ep['label']}",
            callback_data=f"ep_select|{uid}|{real_idx}"
        )])

    # All Episodes button
    buttons.append([InlineKeyboardButton(
        "📦 All Episodes (Current Page Quality)",
        callback_data=f"ep_all|{uid}|{page}"
    )])

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"ep_page|{uid}|{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"ep_page|{uid}|{page+1}"))
    if nav:
        buttons.append(nav)

    short_title = anime_title[:40] + ("…" if len(anime_title) > 40 else "")
    await msg.edit_text(
        f"🎌 <b>{short_title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Total Episodes: <b>{total}</b> | Page {page+1}/{(total-1)//per_page+1}\n\n"
        f"Choose an episode to download:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


# ─── Callback: episode page navigation ─────────────────────
@app.on_callback_query(filters.regex(r"^ep_page\|"))
async def cb_ep_page(_, cq: CallbackQuery):
    _, uid_str, page_str = cq.data.split("|")
    uid  = int(uid_str)
    page = int(page_str)
    if cq.from_user.id != uid:
        await cq.answer("❌ Not your session!", show_alert=True)
        return
    await cq.answer()
    state    = user_state.get(uid, {})
    episodes = state.get("episodes", [])
    title    = state.get("chosen", {}).get("title", "Anime")
    user_state[uid]["page"] = page
    await _show_episode_list(cq.message, uid, episodes, title, page)


# ─── Callback: single episode selected → quality choice ────
@app.on_callback_query(filters.regex(r"^ep_select\|"))
async def cb_ep_select(_, cq: CallbackQuery):
    _, uid_str, idx_str = cq.data.split("|")
    uid = int(uid_str)
    idx = int(idx_str)
    if cq.from_user.id != uid:
        await cq.answer("❌ Not your session!", show_alert=True)
        return
    await cq.answer()

    state    = user_state.get(uid, {})
    episodes = state.get("episodes", [])
    if idx >= len(episodes):
        await cq.answer("Session expired!", show_alert=True)
        return

    ep = episodes[idx]
    user_state[uid]["selected_ep_idx"] = idx

    # Find all quality variants for this episode
    ep_variants = [
        (i, e) for i, e in enumerate(episodes)
        if e["ep"] == ep["ep"] and e["season"] == ep["season"]
    ]

    buttons = []
    for real_i, variant in ep_variants:
        buttons.append([InlineKeyboardButton(
            f"🎥 {variant['quality']}",
            callback_data=f"dl_single|{uid}|{real_i}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"ep_page|{uid}|{state.get('page',0)}")])

    title = state.get("chosen", {}).get("title", "Anime")
    await cq.message.edit_text(
        f"🎌 <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Episode {ep['ep']} — Season {ep['season']}</b>\n\n"
        "Choose quality:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


# ─── Callback: download single episode ─────────────────────
@app.on_callback_query(filters.regex(r"^dl_single\|"))
async def cb_dl_single(_, cq: CallbackQuery):
    _, uid_str, idx_str = cq.data.split("|")
    uid = int(uid_str)
    idx = int(idx_str)
    if cq.from_user.id != uid:
        await cq.answer("❌ Not your session!", show_alert=True)
        return
    await cq.answer("⏳ Fetching download link...")

    state    = user_state.get(uid, {})
    episodes = state.get("episodes", [])
    if idx >= len(episodes):
        await cq.message.edit_text("❌ Session expired. Search again.")
        return

    ep         = episodes[idx]
    anime_name = state.get("chosen", {}).get("title", "Anime")
    # Clean anime name (strip quality tags etc)
    anime_name_clean = re.sub(r"\s*\(.*?\)|\s*\[.*?\]", "", anime_name).strip()

    await cq.message.edit_text(
        f"⏳ <b>Resolving download link...</b>\n"
        f"📌 Episode {ep['ep']} | {ep['quality']}",
        parse_mode=enums.ParseMode.HTML
    )

    dl_url, filename = await resolve_filepress(ep["filepress_id"])
    if not dl_url:
        await cq.message.edit_text(
            f"❌ <b>Failed to resolve download link!</b>\n"
            f"FilePress ID: <code>{ep['filepress_id']}</code>\n\n"
            "The file may have been removed or the link expired.",
            parse_mode=enums.ParseMode.HTML
        )
        return

    # Final filename override
    bot_filename = ep["filename"]

    # Build caption
    cap_template = user_captions.get(uid, DEFAULT_CAPTION)
    caption = cap_template.format(
        anime_name=anime_name_clean,
        ep=ep["ep"],
        season=ep["season"],
        quality=ep["quality"]
    )

    await _download_and_send(cq.message, uid, dl_url, bot_filename, caption, ep)


# ─── Callback: all episodes (page) ─────────────────────────
@app.on_callback_query(filters.regex(r"^ep_all\|"))
async def cb_ep_all(_, cq: CallbackQuery):
    _, uid_str, page_str = cq.data.split("|")
    uid  = int(uid_str)
    page = int(page_str)
    if cq.from_user.id != uid:
        await cq.answer("❌ Not your session!", show_alert=True)
        return
    await cq.answer()

    state    = user_state.get(uid, {})
    episodes = state.get("episodes", [])
    title    = state.get("chosen", {}).get("title", "Anime")

    # Get unique episodes on this page (first quality variant)
    per_page = 8
    start    = page * per_page
    end      = min(start + per_page, len(episodes))
    page_eps = episodes[start:end]

    # Show quality selection for bulk download
    # Use the qualities available across these episodes
    available_qualities = sorted(
        set(e["quality"] for e in page_eps),
        key=lambda q: ["360p","480p","720p","1080p","2160p","Unknown"].index(q)
        if q in ["360p","480p","720p","1080p","2160p","Unknown"] else 9
    )

    buttons = [[InlineKeyboardButton(
        f"📦 All — {q}",
        callback_data=f"dl_all_quality|{uid}|{page}|{q}"
    )] for q in available_qualities]
    buttons.append([InlineKeyboardButton(
        "🔙 Back",
        callback_data=f"ep_page|{uid}|{page}"
    )])

    await cq.message.edit_text(
        f"📦 <b>Download All Episodes (Page {page+1})</b>\n"
        f"🎌 {title}\n\n"
        "Choose quality for bulk download:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(filters.regex(r"^dl_all_quality\|"))
async def cb_dl_all_quality(_, cq: CallbackQuery):
    parts   = cq.data.split("|")
    uid     = int(parts[1])
    page    = int(parts[2])
    quality = parts[3]
    if cq.from_user.id != uid:
        await cq.answer("❌ Not your session!", show_alert=True)
        return
    await cq.answer(f"⏳ Starting bulk download — {quality}")

    state    = user_state.get(uid, {})
    episodes = state.get("episodes", [])
    title    = state.get("chosen", {}).get("title", "Anime")
    anime_name_clean = re.sub(r"\s*\(.*?\)|\s*\[.*?\]", "", title).strip()

    per_page = 8
    start    = page * per_page
    end      = min(start + per_page, len(episodes))
    page_eps = [e for e in episodes[start:end] if e["quality"] == quality]

    if not page_eps:
        await cq.message.edit_text(f"❌ No episodes found for quality: {quality}")
        return

    await cq.message.edit_text(
        f"📦 <b>Bulk Download Started!</b>\n"
        f"🎌 {title}\n"
        f"🎥 Quality: {quality}\n"
        f"📋 Episodes: {len(page_eps)}\n\n"
        f"⏳ Sending one by one...",
        parse_mode=enums.ParseMode.HTML
    )

    for ep in page_eps:
        cap_template = user_captions.get(uid, DEFAULT_CAPTION)
        caption = cap_template.format(
            anime_name=anime_name_clean,
            ep=ep["ep"],
            season=ep["season"],
            quality=ep["quality"]
        )
        dl_url, _ = await resolve_filepress(ep["filepress_id"])
        if not dl_url:
            await cq.message.reply_text(
                f"❌ Episode {ep['ep']} — Link expired/not found.",
                parse_mode=enums.ParseMode.HTML
            )
            continue
        await _download_and_send(
            cq.message, uid, dl_url, ep["filename"], caption, ep, reply=False
        )
        await asyncio.sleep(2)  # Flood control

    await cq.message.reply_text(
        f"✅ <b>All {len(page_eps)} episodes sent!</b>\n\n"
        f"<blockquote>🚀 For More Join 🔰 @KENSHIN_ANIME</blockquote>",
        parse_mode=enums.ParseMode.HTML
    )


# ─── Core: download from URL and send video ────────────────
async def _download_and_send(
    msg: Message,
    uid: int,
    dl_url: str,
    filename: str,
    caption: str,
    ep: dict,
    reply: bool = True
):
    # Status message
    status_msg = await msg.reply_text(
        f"⬇️ <b>Downloading...</b>\n"
        f"📌 Episode {ep['ep']} | {ep['quality']}\n"
        f"🔗 <code>{dl_url[:60]}...</code>",
        parse_mode=enums.ParseMode.HTML
    ) if reply else msg

    last_update = [0.0]

    async def progress(done: int, total: int):
        now = asyncio.get_event_loop().time()
        if now - last_update[0] < 3:
            return
        last_update[0] = now
        pct  = done * 100 // total
        mb_d = done / 1024 / 1024
        mb_t = total / 1024 / 1024
        bar  = "█" * (pct // 10) + "░" * (10 - pct // 10)
        try:
            await status_msg.edit_text(
                f"⬇️ <b>Downloading:</b> {pct}%\n"
                f"[{bar}]\n"
                f"📦 {mb_d:.1f} MB / {mb_t:.1f} MB\n"
                f"📌 Episode {ep['ep']} | {ep['quality']}",
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass

    video_bytes = await download_file(dl_url, progress_cb=progress)

    if not video_bytes:
        await status_msg.edit_text(
            f"❌ <b>Download failed!</b>\n"
            f"Could not download Episode {ep['ep']}.\n"
            f"URL: <code>{dl_url[:80]}</code>",
            parse_mode=enums.ParseMode.HTML
        )
        return

    try:
        await status_msg.edit_text(
            f"📤 <b>Uploading to Telegram...</b>\n"
            f"📌 Episode {ep['ep']} | {ep['quality']}",
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass

    # Thumbnail
    thumb = None
    thumb_bytes = user_thumbnails.get(uid)
    if thumb_bytes:
        thumb = io.BytesIO(thumb_bytes)
        thumb.name = "thumb.jpg"

    # Rename BytesIO
    video_bytes.name = filename

    try:
        sent = await msg.reply_video(
            video=video_bytes,
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
            file_name=filename,
            thumb=thumb,
            supports_streaming=True,
        )
        # Delete status message after successful send
        try:
            await status_msg.delete()
        except Exception:
            pass
    except Exception as e:
        log.error(f"Send video error: {e}")
        await status_msg.edit_text(
            f"❌ <b>Upload failed!</b>\n<code>{str(e)[:200]}</code>",
            parse_mode=enums.ParseMode.HTML
        )


# ─── Run ───────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("🚀 @KENSHIN_ANIME Bot starting...")
    app.run()
