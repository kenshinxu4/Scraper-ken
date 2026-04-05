# ╔══════════════════════════════════════════════════════════════╗
# ║      @KENSHIN_ANIME — AnimeDubHindi Telegram Bot v2.0        ║
# ║      Engine : Pyrofork | Cloudflare Bypass: curl_cffi        ║
# ║      Scrapes: animedubhindi.me + links.animedubhindi.me      ║
# ╚══════════════════════════════════════════════════════════════╝

import asyncio
import io
import logging
import os
import re
from functools import partial
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as cf_req
from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ─── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("KenshinAnime")

# ─── Config ─────────────────────────────────────────────────────
API_ID    = int(os.environ["API_ID"])
API_HASH  = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID  = int(os.environ.get("ADMIN_ID", 0))

# ─── Constants ──────────────────────────────────────────────────
MAIN_SITE    = "https://www.animedubhindi.me"
LINKS_SITE   = "https://links.animedubhindi.me"
FILEPRESS    = "https://new2.filepress.wiki"
CHANNEL_TAG  = "@KENSHIN_ANIME"

# FilePress regex — matches all known variants
FP_RE = re.compile(
    r"https?://(?:[\w\-]+\.)*filepress\.(?:wiki|store|in|me)"
    r"/(?:file|download|d)/([A-Za-z0-9]+)",
    re.IGNORECASE,
)

QUALITY_ORDER = {"360p": 0, "480p": 1, "720p": 2, "1080p": 3, "2160p": 4}

# ─── Default caption ────────────────────────────────────────────
DEFAULT_CAPTION = (
    "<b><blockquote>✨ {anime_name} ✨</blockquote>\n"
    "🌸 Episode : {ep} [S{season}]\n"
    "🌸 Quality : {quality}\n"
    "🌸 Audio : Hindi Dub 🎙️ | Official\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "<blockquote>🚀 For More Join 🔰 [@KENSHIN_ANIME]</blockquote></b>\n"
    "━━━━━━━━━━━━━━━━━━━━━"
)

# ─── In-memory stores ───────────────────────────────────────────
user_captions:   dict[int, str]   = {}
user_thumbnails: dict[int, bytes] = {}
user_sessions:   dict[int, dict]  = {}

# ════════════════════════════════════════════════════════════════
#  HTTP — curl_cffi (Cloudflare bypass via Chrome fingerprint)
# ════════════════════════════════════════════════════════════════

CF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# Shared curl_cffi session (thread-safe for executor)
_cf_session = cf_req.Session(impersonate="chrome120")


def _sync_get(url: str, stream: bool = False, timeout: int = 30):
    """Synchronous GET with Chrome impersonation."""
    try:
        r = _cf_session.get(
            url,
            headers=CF_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        log.info(f"GET {url} → {r.status_code}")
        return r
    except Exception as e:
        log.error(f"_sync_get error [{url}]: {e}")
        return None


async def async_get_html(url: str, timeout: int = 30) -> str | None:
    """Async wrapper around sync curl_cffi GET. Returns HTML text or None."""
    loop = asyncio.get_event_loop()
    r = await loop.run_in_executor(None, partial(_sync_get, url, False, timeout))
    if r is None:
        return None
    if r.status_code == 200:
        return r.text
    log.warning(f"HTTP {r.status_code} for {url}")
    return None


async def async_download_bytes(
    url: str,
    on_progress=None,
    timeout: int = 3600,
) -> io.BytesIO | None:
    """
    Download file bytes via curl_cffi (Cloudflare-safe).
    Calls on_progress(done_bytes, total_bytes) periodically.
    """
    loop = asyncio.get_event_loop()

    def _download():
        try:
            r = _cf_session.get(
                url,
                headers=CF_HEADERS,
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
            if r.status_code not in (200, 206):
                log.error(f"Download HTTP {r.status_code}: {url}")
                return None
            total = int(r.headers.get("Content-Length", 0))
            buf   = io.BytesIO()
            done  = 0
            for chunk in r.iter_content(chunk_size=524288):  # 512 KB
                if chunk:
                    buf.write(chunk)
                    done += len(chunk)
            buf.seek(0)
            return buf, total
        except Exception as e:
            log.error(f"_download error: {e}")
            return None

    result = await loop.run_in_executor(None, _download)
    if result is None:
        return None
    buf, total = result
    if on_progress:
        await on_progress(buf.getbuffer().nbytes, total or buf.getbuffer().nbytes)
    return buf


# ════════════════════════════════════════════════════════════════
#  SCRAPER 1 — Search animedubhindi.me
# ════════════════════════════════════════════════════════════════

async def search_anime(query: str) -> list[dict]:
    url  = f"{MAIN_SITE}/?s={quote_plus(query)}"
    html = await async_get_html(url)
    if not html:
        return []

    soup    = BeautifulSoup(html, "lxml")
    results = []
    seen    = set()

    # Primary: article cards
    for article in soup.select("article"):
        a = (
            article.select_one("h2 a, h3 a, .entry-title a, .post-title a")
            or article.select_one("a[href]")
        )
        if not a:
            continue
        href  = a.get("href", "")
        title = a.get_text(strip=True)
        if not href.startswith("http"):
            href = urljoin(MAIN_SITE, href)
        if MAIN_SITE in href and href not in seen and title:
            seen.add(href)
            # Thumbnail
            img   = article.select_one("img[data-src], img[src]")
            thumb = (img.get("data-src") or img.get("src", "")) if img else ""
            results.append({"title": title, "url": href, "thumb": thumb})

    # Fallback: all links that look like anime posts
    if not results:
        for a in soup.select("a[href]"):
            href  = a.get("href", "")
            title = a.get_text(strip=True)
            if (
                MAIN_SITE in href
                and href not in seen
                and len(title) > 10
                and re.search(r"season|episode|hindi|multi", href, re.I)
            ):
                seen.add(href)
                results.append({"title": title, "url": href, "thumb": ""})

    return results[:8]


# ════════════════════════════════════════════════════════════════
#  SCRAPER 2 — Anime post page → download page URL
# ════════════════════════════════════════════════════════════════

async def get_download_page_url(anime_url: str) -> str | None:
    html = await async_get_html(anime_url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    # Strategy 1: Direct link with links.animedubhindi.me/episode/
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "links.animedubhindi.me/episode/" in href:
            url = href.rstrip("/") + "/"
            log.info(f"Found DL page (direct): {url}")
            return url

    # Strategy 2: Grep raw HTML
    m = re.search(
        r"https?://links\.animedubhindi\.me/episode/([\w\-]+)/?", html
    )
    if m:
        url = f"{LINKS_SITE}/episode/{m.group(1)}/"
        log.info(f"Found DL page (regex): {url}")
        return url

    # Strategy 3: Build from post slug by stripping noise
    slug = anime_url.rstrip("/").split("/")[-1]
    clean_slug = re.sub(
        r"[-_](hindi|tamil|telugu|english|japanese|multi.?audio|"
        r"dubbed|bluray|web.?dl|hd|fhd|cr.?dub|crunchyroll|"
        r"episodes?.?download|free|from|animedubhindi|com|org|me)"
        r".*$",
        "",
        slug,
        flags=re.I,
    ).strip("-_")

    if clean_slug:
        guessed = f"{LINKS_SITE}/episode/{clean_slug}/"
        log.info(f"Guessing DL page: {guessed}")
        # Verify it actually returns 200
        test = await async_get_html(guessed)
        if test and len(test) > 500:
            return guessed

    return None


# ════════════════════════════════════════════════════════════════
#  SCRAPER 3 — links.animedubhindi.me/episode/{slug}/
# ════════════════════════════════════════════════════════════════

def _parse_quality(text: str) -> str:
    for q in ["2160p", "1080p", "720p", "480p", "360p"]:
        if q.lower() in text.lower():
            return q
    return "Unknown"


def _parse_episode(text: str) -> str:
    # Patterns: S03E04, E04, ep04, episode 4, Episode-04
    patterns = [
        r"[Ss]\d{1,2}[Ee](\d{1,3})",        # S03E04
        r"[Ee][Pp]?[\.\s\-_]?(\d{1,3})",    # E04 / EP04 / ep-04
        r"[Ee]pisode[\s\.\-_]?(\d{1,3})",   # Episode 4
        r"[\s\-_](\d{1,3})[\s\-_]",         # standalone number
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).zfill(2)
    return "??"


def _parse_season(text: str) -> str:
    m = re.search(r"[Ss](?:eason)?[\s\.\-_]?0*(\d{1,2})", text)
    return m.group(1).zfill(2) if m else "01"


async def scrape_episodes(dl_page_url: str) -> list[dict]:
    html = await async_get_html(dl_page_url)
    if not html:
        log.error(f"Empty HTML from {dl_page_url}")
        return []

    log.info(f"DL page HTML length: {len(html)} chars")
    soup = BeautifulSoup(html, "lxml")

    episodes_raw: list[dict] = []

    # ── Strategy A: Find all <a> tags with filepress href ──────
    fp_links = soup.find_all("a", href=FP_RE)
    log.info(f"FilePress <a> tags found: {len(fp_links)}")

    for a in fp_links:
        href = a.get("href", "")
        m    = FP_RE.search(href)
        if not m:
            continue
        fp_id = m.group(1)

        # Get as much surrounding text as possible for context
        ctx_parts = [a.get_text(" ", strip=True)]

        # Walk up parents to find more context
        for parent in a.parents:
            tag = parent.name
            if tag in ("tr", "td", "li", "div", "p", "span", "section"):
                ctx_parts.append(parent.get_text(" ", strip=True))
                break
            if tag in ("table", "ul", "ol", "article", "body"):
                break

        ctx = " ".join(ctx_parts)

        quality = _parse_quality(ctx)
        ep_num  = _parse_episode(ctx)
        season  = _parse_season(ctx)

        # Also try to parse from the href itself (filenames sometimes embedded)
        if quality == "Unknown":
            quality = _parse_quality(href)
        if ep_num == "??":
            ep_num = _parse_episode(href)
        if season == "01":
            s2 = _parse_season(href)
            if s2 != "01":
                season = s2

        log.info(f"  EP {ep_num} S{season} {quality} → FP:{fp_id}")
        episodes_raw.append({
            "ep":          ep_num,
            "season":      season,
            "quality":     quality,
            "filepress_id": fp_id,
        })

    # ── Strategy B: Grep raw HTML for filepress URLs ────────────
    if not episodes_raw:
        log.info("Strategy A found nothing, trying raw HTML grep...")
        for m in FP_RE.finditer(html):
            fp_id = m.group(1)
            # Grab surrounding context
            start   = max(0, m.start() - 300)
            end     = min(len(html), m.end() + 100)
            ctx_raw = html[start:end]
            ctx     = BeautifulSoup(ctx_raw, "lxml").get_text(" ")

            quality = _parse_quality(ctx)
            ep_num  = _parse_episode(ctx)
            season  = _parse_season(ctx)

            if quality == "Unknown":
                quality = _parse_quality(m.group(0))
            if ep_num == "??":
                ep_num = _parse_episode(m.group(0))

            log.info(f"  [grep] EP {ep_num} S{season} {quality} → FP:{fp_id}")
            episodes_raw.append({
                "ep":           ep_num,
                "season":       season,
                "quality":      quality,
                "filepress_id": fp_id,
            })

    # ── Strategy C: data-id / data-file-id attributes ───────────
    if not episodes_raw:
        log.info("Strategy B found nothing, trying data-* attributes...")
        for tag in soup.find_all(attrs={"data-id": True}):
            val = tag.get("data-id", "")
            if re.fullmatch(r"[A-Za-z0-9]{10,}", val):
                ctx     = tag.get_text(" ", strip=True)
                quality = _parse_quality(ctx)
                ep_num  = _parse_episode(ctx)
                season  = _parse_season(ctx)
                episodes_raw.append({
                    "ep": ep_num, "season": season,
                    "quality": quality, "filepress_id": val,
                })

    if not episodes_raw:
        log.error("All strategies failed — no FilePress links found!")
        # Debug: print first 2000 chars of HTML
        log.debug(f"Page HTML preview:\n{html[:2000]}")
        return []

    # ── Build final list ─────────────────────────────────────────
    seen    = set()
    final   = []
    for ep in episodes_raw:
        key = (ep["ep"], ep["quality"], ep["filepress_id"])
        if key in seen:
            continue
        seen.add(key)
        ep["filename"] = (
            f"[{CHANNEL_TAG}]E{ep['ep']}S{ep['season']}{ep['quality']}.mkv"
        )
        ep["label"] = f"E{ep['ep']} — {ep['quality']}"
        final.append(ep)

    # Sort: episode asc, then quality
    final.sort(
        key=lambda x: (
            int(x["ep"]) if x["ep"].isdigit() else 999,
            QUALITY_ORDER.get(x["quality"], 5),
        )
    )
    log.info(f"Total episodes scraped: {len(final)}")
    return final


# ════════════════════════════════════════════════════════════════
#  SCRAPER 4 — FilePress → real direct download URL
# ════════════════════════════════════════════════════════════════

async def resolve_filepress(fp_id: str) -> tuple[str | None, str | None]:
    """
    Returns (direct_download_url, filename).
    Uses 7-strategy waterfall.
    """
    file_page = f"{FILEPRESS}/file/{fp_id}"
    html = await async_get_html(file_page, timeout=20)

    if not html:
        log.error(f"FilePress page empty for ID: {fp_id}")
        return None, None

    soup = BeautifulSoup(html, "lxml")

    # ── Strategy 1: Direct <a href> with .mkv/.mp4 ──────────────
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"\.(mkv|mp4|avi|mov|webm)(\?|$)", href, re.I):
            fname = href.split("/")[-1].split("?")[0]
            log.info(f"FP Strategy 1 (direct ext): {href}")
            return href, fname

    # ── Strategy 2: /download/ path ─────────────────────────────
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/download/" in href and "filepress" in href:
            fname = href.split("/download/")[-1].split("?")[0]
            log.info(f"FP Strategy 2 (/download/ path): {href}")
            return href, fname

    # ── Strategy 3: Page <title> as filename ────────────────────
    title_tag = soup.find("title")
    if title_tag:
        raw = title_tag.get_text(strip=True)
        # Remove common site prefixes
        for noise in ["FilePress -", "FilePress–", "Download -", "| FilePress"]:
            raw = raw.replace(noise, "").strip()
        fname_m = re.search(r"([\w\[\]\(\)\s\.\-]+\.(?:mkv|mp4))", raw, re.I)
        if fname_m:
            fname = fname_m.group(1).strip()
            dl_url = f"{FILEPRESS}/download/{quote_plus(fname)}"
            log.info(f"FP Strategy 3 (title): {dl_url}")
            return dl_url, fname

    # ── Strategy 4: JS variable with URL ────────────────────────
    js_patterns = [
        r"""(?:url|link|file|src)\s*[:=]\s*["']([^"']+\.(?:mkv|mp4)[^"']*)["']""",
        r"""["'](https?://[^"']+\.(?:mkv|mp4)[^"']*)["']""",
        r"""["'](https?://[^"']+/download/[^"']+)["']""",
    ]
    for pat in js_patterns:
        jm = re.search(pat, html, re.IGNORECASE)
        if jm:
            href  = jm.group(1)
            fname = href.split("/")[-1].split("?")[0]
            log.info(f"FP Strategy 4 (JS var): {href}")
            return href, fname

    # ── Strategy 5: Raw HTML grep for download links ─────────────
    for pat in [
        r"https?://[^\s\"'<>]+\.mkv[^\s\"'<>]*",
        r"https?://[^\s\"'<>]+\.mp4[^\s\"'<>]*",
        r"https?://[^\s\"'<>]+/download/[^\s\"'<>]+",
    ]:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            href  = m.group(0).strip()
            fname = href.split("/")[-1].split("?")[0]
            log.info(f"FP Strategy 5 (raw grep): {href}")
            return href, fname

    # ── Strategy 6: HEAD request on /download/{id} ──────────────
    loop = asyncio.get_event_loop()

    def _head_check():
        try:
            r = _cf_session.head(
                f"{FILEPRESS}/download/{fp_id}",
                headers=CF_HEADERS,
                timeout=15,
                allow_redirects=True,
            )
            if r.status_code in (200, 206):
                final_url = str(r.url)
                fname     = final_url.split("/")[-1].split("?")[0] or f"{fp_id}.mkv"
                return final_url, fname
        except Exception as e:
            log.warning(f"HEAD check failed: {e}")
        return None, None

    dl_url, fname = await loop.run_in_executor(None, _head_check)
    if dl_url:
        log.info(f"FP Strategy 6 (HEAD redirect): {dl_url}")
        return dl_url, fname

    # ── Strategy 7: Try alternate FilePress endpoints ────────────
    for alt_base in [
        "https://filepress.wiki",
        "https://new.filepress.wiki",
        "https://filepress.store",
    ]:
        alt_url = f"{alt_base}/file/{fp_id}"
        alt_html = await async_get_html(alt_url, timeout=15)
        if alt_html:
            m = re.search(
                r"https?://[^\s\"'<>]+\.(?:mkv|mp4)[^\s\"'<>]*",
                alt_html, re.I,
            )
            if m:
                href  = m.group(0)
                fname = href.split("/")[-1].split("?")[0]
                log.info(f"FP Strategy 7 (alt endpoint {alt_base}): {href}")
                return href, fname

    log.error(f"All FilePress strategies failed for ID: {fp_id}")
    return None, None


# ════════════════════════════════════════════════════════════════
#  PYROGRAM CLIENT
# ════════════════════════════════════════════════════════════════

app = Client(
    "kenshin_anime_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ─── Helpers ────────────────────────────────────────────────────

def get_caption(uid: int) -> str:
    return user_captions.get(uid, DEFAULT_CAPTION)


def clean_anime_name(raw: str) -> str:
    return re.sub(
        r"\s*[\|\-]\s*(hindi|tamil|telugu|english|japanese|multi.?audio"
        r"|dubbed|bluray|web.?dl|episodes?\s*download.*)",
        "",
        raw,
        flags=re.I,
    ).strip()


def build_kb(buttons: list[list]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(buttons)


# ════════════════════════════════════════════════════════════════
#  COMMANDS
# ════════════════════════════════════════════════════════════════

@app.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    await msg.reply_text(
        "<b>🔥 @KENSHIN_ANIME Anime Bot 🔥</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🎌 <b>Hindi Dubbed Anime Download Bot!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 <b>Usage:</b> Just type any anime name:\n"
        "<code>Jujutsu Kaisen Season 3</code>\n"
        "<code>Attack on Titan Season 4</code>\n\n"
        "📋 Use /help for all commands.\n\n"
        "<blockquote>🚀 Join ➜ @KENSHIN_ANIME</blockquote>",
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True,
    )


@app.on_message(filters.command("help"))
async def cmd_help(_, msg: Message):
    await msg.reply_text(
        "<b>📖 Help — @KENSHIN_ANIME Bot</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>🔍 Search:</b> Type anime name directly\n"
        "<code>Naruto Shippuden Season 5</code>\n\n"
        "<b>⚙️ Commands:</b>\n"
        "/start — Welcome\n"
        "/help — This guide\n"
        "/set_caption &lt;text&gt; — Custom caption\n"
        "  Variables: {anime_name} {ep} {season} {quality}\n"
        "/get_caption — View caption\n"
        "/reset_caption — Reset caption\n\n"
        "<b>🖼️ Thumbnail:</b> Send any photo to set thumbnail\n\n"
        "<b>📦 Qualities:</b> 360p • 480p • 720p • 1080p • 2160p\n\n"
        "<b>📥 Flow:</b>\n"
        "1️⃣ Type name → 2️⃣ Select anime\n"
        "3️⃣ Select episode → 4️⃣ Select quality\n"
        "5️⃣ Bot sends video! ✅\n\n"
        "<blockquote>🚀 Join ➜ @KENSHIN_ANIME</blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(filters.command("set_caption"))
async def cmd_set_caption(_, msg: Message):
    uid  = msg.from_user.id
    args = msg.text.split(None, 1)
    if len(args) < 2:
        await msg.reply_text(
            "❌ <b>Usage:</b> <code>/set_caption Your text here</code>\n\n"
            "<b>Variables:</b> {anime_name} {ep} {season} {quality}",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    user_captions[uid] = args[1].strip()
    await msg.reply_text("✅ Caption updated!", parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.command("get_caption"))
async def cmd_get_caption(_, msg: Message):
    uid = msg.from_user.id
    cap = get_caption(uid)
    await msg.reply_text(
        f"<b>📝 Current Caption:</b>\n<code>{cap}</code>",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(filters.command("reset_caption"))
async def cmd_reset_caption(_, msg: Message):
    user_captions.pop(msg.from_user.id, None)
    await msg.reply_text("✅ Caption reset to default!", parse_mode=enums.ParseMode.HTML)


# ─── Photo → set thumbnail ──────────────────────────────────────
@app.on_message(filters.photo & filters.private)
async def handle_photo(_, msg: Message):
    uid = msg.from_user.id
    dl  = await msg.download(in_memory=True)
    dl.seek(0)
    user_thumbnails[uid] = dl.read()
    await msg.reply_text(
        "🖼️ <b>Thumbnail set!</b> Used for all future uploads.",
        parse_mode=enums.ParseMode.HTML,
    )


# ─── Text → search ─────────────────────────────────────────────
@app.on_message(
    filters.text
    & filters.private
    & ~filters.command(
        ["start", "help", "set_caption", "get_caption", "reset_caption"]
    )
)
async def handle_search(_, msg: Message):
    query = msg.text.strip()
    if not query:
        return
    uid = msg.from_user.id

    wait = await msg.reply_text(
        f"🔍 <b>Searching:</b> <code>{query}</code>...",
        parse_mode=enums.ParseMode.HTML,
    )

    results = await search_anime(query)
    if not results:
        await wait.edit_text(
            f"❌ <b>No results found for:</b> <code>{query}</code>\n"
            "Try a different search term.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    user_sessions[uid] = {"results": results, "query": query, "page": 0}

    buttons = [
        [InlineKeyboardButton(
            f"🎬 {r['title'][:50]}{'…' if len(r['title'])>50 else ''}",
            callback_data=f"asel|{uid}|{i}",
        )]
        for i, r in enumerate(results)
    ]

    await wait.edit_text(
        f"🎌 <b>Results for:</b> <i>{query}</i>\n"
        f"📋 Found <b>{len(results)}</b> anime. Choose one:",
        reply_markup=build_kb(buttons),
        parse_mode=enums.ParseMode.HTML,
    )


# ════════════════════════════════════════════════════════════════
#  CALLBACKS
# ════════════════════════════════════════════════════════════════

# ─── Anime selected ────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^asel\|(\d+)\|(\d+)$"))
async def cb_anime_select(_, cq: CallbackQuery):
    uid = int(cq.matches[0].group(1))
    idx = int(cq.matches[0].group(2))
    if cq.from_user.id != uid:
        return await cq.answer("❌ Not your session!", show_alert=True)

    sess = user_sessions.get(uid, {})
    results = sess.get("results", [])
    if idx >= len(results):
        return await cq.answer("❌ Session expired.", show_alert=True)

    chosen = results[idx]
    await cq.answer()
    await cq.message.edit_text(
        f"⏳ <b>Fetching episodes for:</b>\n<i>{chosen['title']}</i>",
        parse_mode=enums.ParseMode.HTML,
    )

    dl_url = await get_download_page_url(chosen["url"])
    if not dl_url:
        await cq.message.edit_text(
            f"❌ <b>Download page not found!</b>\n"
            f"Anime: <i>{chosen['title']}</i>\n\n"
            "The website may not have download links for this anime yet.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    await cq.message.edit_text(
        f"⏳ <b>Scraping episode list...</b>\n"
        f"<code>{dl_url}</code>",
        parse_mode=enums.ParseMode.HTML,
    )

    episodes = await scrape_episodes(dl_url)
    if not episodes:
        await cq.message.edit_text(
            f"❌ <b>No episodes found!</b>\n"
            f"Anime: <i>{chosen['title']}</i>\n\n"
            f"🔗 Try manually: <a href='{dl_url}'>Open Download Page</a>",
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    user_sessions[uid].update({
        "chosen":   chosen,
        "dl_url":   dl_url,
        "episodes": episodes,
        "page":     0,
    })

    await _render_episode_page(cq.message, uid, episodes, chosen["title"], page=0)


# ─── Episode page render ────────────────────────────────────────
async def _render_episode_page(
    msg, uid: int, episodes: list[dict], title: str, page: int
):
    per_page = 8
    start    = page * per_page
    end      = min(start + per_page, len(episodes))
    chunk    = episodes[start:end]
    total_p  = (len(episodes) - 1) // per_page + 1

    buttons = []
    for i, ep in enumerate(chunk):
        buttons.append([InlineKeyboardButton(
            f"▶️ {ep['label']}",
            callback_data=f"epsel|{uid}|{start+i}",
        )])

    # All on this page
    buttons.append([InlineKeyboardButton(
        f"📦 All Episodes (Page {page+1})",
        callback_data=f"epalp|{uid}|{page}",
    )])

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"eppg|{uid}|{page-1}"))
    if end < len(episodes):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"eppg|{uid}|{page+1}"))
    if nav:
        buttons.append(nav)

    short = title[:45] + ("…" if len(title) > 45 else "")
    await msg.edit_text(
        f"🎌 <b>{short}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>{len(episodes)} episodes</b> found | Page {page+1}/{total_p}\n\n"
        "Choose an episode:",
        reply_markup=build_kb(buttons),
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_callback_query(filters.regex(r"^eppg\|(\d+)\|(\d+)$"))
async def cb_ep_page(_, cq: CallbackQuery):
    uid  = int(cq.matches[0].group(1))
    page = int(cq.matches[0].group(2))
    if cq.from_user.id != uid:
        return await cq.answer("❌ Not your session!", show_alert=True)
    await cq.answer()
    sess = user_sessions.get(uid, {})
    user_sessions[uid]["page"] = page
    await _render_episode_page(
        cq.message, uid,
        sess.get("episodes", []),
        sess.get("chosen", {}).get("title", "Anime"),
        page,
    )


# ─── Episode selected → quality keyboard ───────────────────────
@app.on_callback_query(filters.regex(r"^epsel\|(\d+)\|(\d+)$"))
async def cb_ep_select(_, cq: CallbackQuery):
    uid = int(cq.matches[0].group(1))
    idx = int(cq.matches[0].group(2))
    if cq.from_user.id != uid:
        return await cq.answer("❌ Not your session!", show_alert=True)
    await cq.answer()

    sess     = user_sessions.get(uid, {})
    episodes = sess.get("episodes", [])
    if idx >= len(episodes):
        return await cq.message.edit_text("❌ Session expired. Search again.")

    ep = episodes[idx]
    # Find all quality variants for this episode
    variants = [
        (i, e) for i, e in enumerate(episodes)
        if e["ep"] == ep["ep"] and e["season"] == ep["season"]
    ]
    user_sessions[uid]["sel_ep_idx"] = idx

    q_icons = {"360p":"📱","480p":"📺","720p":"🖥️","1080p":"🎬","2160p":"🔮","Unknown":"🎞️"}
    buttons = [
        [InlineKeyboardButton(
            f"{q_icons.get(v['quality'],'🎞️')} {v['quality']}",
            callback_data=f"dlsingle|{uid}|{vi}",
        )]
        for vi, v in variants
    ]
    page = sess.get("page", 0)
    buttons.append([InlineKeyboardButton(
        "🔙 Back", callback_data=f"eppg|{uid}|{page}",
    )])

    title = sess.get("chosen", {}).get("title", "Anime")
    await cq.message.edit_text(
        f"🎌 <b>{title[:45]}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Episode {ep['ep']} — Season {ep['season']}</b>\n\n"
        "🎥 Choose quality:",
        reply_markup=build_kb(buttons),
        parse_mode=enums.ParseMode.HTML,
    )


# ─── Single episode download ────────────────────────────────────
@app.on_callback_query(filters.regex(r"^dlsingle\|(\d+)\|(\d+)$"))
async def cb_dl_single(_, cq: CallbackQuery):
    uid = int(cq.matches[0].group(1))
    idx = int(cq.matches[0].group(2))
    if cq.from_user.id != uid:
        return await cq.answer("❌ Not your session!", show_alert=True)
    await cq.answer("⏳ Preparing download...")

    sess     = user_sessions.get(uid, {})
    episodes = sess.get("episodes", [])
    if idx >= len(episodes):
        return await cq.message.edit_text("❌ Session expired.")

    ep         = episodes[idx]
    anime_name = clean_anime_name(sess.get("chosen", {}).get("title", "Anime"))

    await _fetch_and_send(cq.message, uid, ep, anime_name)


# ─── All episodes on page ──────────────────────────────────────
@app.on_callback_query(filters.regex(r"^epalp\|(\d+)\|(\d+)$"))
async def cb_ep_all_page(_, cq: CallbackQuery):
    uid  = int(cq.matches[0].group(1))
    page = int(cq.matches[0].group(2))
    if cq.from_user.id != uid:
        return await cq.answer("❌ Not your session!", show_alert=True)
    await cq.answer()

    sess     = user_sessions.get(uid, {})
    episodes = sess.get("episodes", [])
    title    = sess.get("chosen", {}).get("title", "Anime")

    per_page = 8
    start    = page * per_page
    chunk    = episodes[start:start + per_page]

    # Quality selection for bulk
    avail_q = sorted(
        set(e["quality"] for e in chunk),
        key=lambda q: QUALITY_ORDER.get(q, 9),
    )
    q_icons = {"360p":"📱","480p":"📺","720p":"🖥️","1080p":"🎬","2160p":"🔮","Unknown":"🎞️"}
    buttons = [
        [InlineKeyboardButton(
            f"{q_icons.get(q,'🎞️')} All — {q}",
            callback_data=f"dlallq|{uid}|{page}|{q}",
        )]
        for q in avail_q
    ]
    buttons.append([InlineKeyboardButton(
        "🔙 Back", callback_data=f"eppg|{uid}|{page}",
    )])

    await cq.message.edit_text(
        f"📦 <b>All Episodes — Page {page+1}</b>\n"
        f"🎌 {title[:45]}\n\n"
        "Choose quality for bulk download:",
        reply_markup=build_kb(buttons),
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_callback_query(filters.regex(r"^dlallq\|(\d+)\|(\d+)\|(.+)$"))
async def cb_dl_all_quality(_, cq: CallbackQuery):
    uid     = int(cq.matches[0].group(1))
    page    = int(cq.matches[0].group(2))
    quality = cq.matches[0].group(3)
    if cq.from_user.id != uid:
        return await cq.answer("❌ Not your session!", show_alert=True)
    await cq.answer(f"📦 Starting bulk — {quality}")

    sess       = user_sessions.get(uid, {})
    episodes   = sess.get("episodes", [])
    title      = sess.get("chosen", {}).get("title", "Anime")
    anime_name = clean_anime_name(title)

    per_page = 8
    start    = page * per_page
    chunk    = [
        e for e in episodes[start:start + per_page]
        if e["quality"] == quality
    ]

    if not chunk:
        return await cq.message.edit_text(
            f"❌ No episodes with quality {quality} on this page."
        )

    await cq.message.edit_text(
        f"📦 <b>Bulk Download Started!</b>\n"
        f"🎌 {title[:45]}\n"
        f"🎥 {quality} | 📋 {len(chunk)} episodes\n\n"
        "Sending one by one... ⏳",
        parse_mode=enums.ParseMode.HTML,
    )

    for ep in chunk:
        await _fetch_and_send(cq.message, uid, ep, anime_name, reply=False)
        await asyncio.sleep(3)

    await cq.message.reply_text(
        f"✅ <b>All {len(chunk)} episodes sent!</b>\n\n"
        "<blockquote>🚀 For More Join 🔰 @KENSHIN_ANIME</blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )


# ════════════════════════════════════════════════════════════════
#  CORE — Fetch & Send
# ════════════════════════════════════════════════════════════════

async def _fetch_and_send(
    msg: Message,
    uid: int,
    ep: dict,
    anime_name: str,
    reply: bool = True,
):
    status = await msg.reply_text(
        f"🔗 <b>Resolving download link...</b>\n"
        f"📌 Episode {ep['ep']} | {ep['quality']}",
        parse_mode=enums.ParseMode.HTML,
    )

    dl_url, filename = await resolve_filepress(ep["filepress_id"])
    if not dl_url:
        await status.edit_text(
            f"❌ <b>Link resolve failed!</b>\n"
            f"Episode {ep['ep']} | {ep['quality']}\n"
            f"FilePress ID: <code>{ep['filepress_id']}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    await status.edit_text(
        f"⬇️ <b>Downloading...</b>\n"
        f"📌 Episode {ep['ep']} | {ep['quality']}",
        parse_mode=enums.ParseMode.HTML,
    )

    last_edit = [0.0]

    async def on_progress(done: int, total: int):
        now = asyncio.get_event_loop().time()
        if now - last_edit[0] < 4:
            return
        last_edit[0] = now
        pct    = (done * 100 // total) if total else 0
        done_m = done / 1048576
        tot_m  = total / 1048576 if total else 0
        bar    = "█" * (pct // 10) + "░" * (10 - pct // 10)
        try:
            await status.edit_text(
                f"⬇️ <b>Downloading:</b> {pct}%\n"
                f"[{bar}]\n"
                f"📦 {done_m:.1f} MB / {tot_m:.1f} MB\n"
                f"📌 Episode {ep['ep']} | {ep['quality']}",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass

    buf = await async_download_bytes(dl_url, on_progress=on_progress)
    if not buf:
        await status.edit_text(
            f"❌ <b>Download failed!</b>\n"
            f"Episode {ep['ep']} | URL: <code>{dl_url[:80]}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    await status.edit_text(
        f"📤 <b>Uploading to Telegram...</b>\n"
        f"📌 Episode {ep['ep']} | {ep['quality']}",
        parse_mode=enums.ParseMode.HTML,
    )

    # Build caption
    cap_template = get_caption(uid)
    season       = ep.get("season", "01")
    caption      = cap_template.format(
        anime_name=anime_name,
        ep=ep["ep"],
        season=season,
        quality=ep["quality"],
    )

    # Filename
    bot_filename = ep["filename"]
    buf.name     = bot_filename

    # Thumbnail
    thumb = None
    if uid in user_thumbnails:
        tb     = io.BytesIO(user_thumbnails[uid])
        tb.name = "thumb.jpg"
        thumb  = tb

    try:
        await msg.reply_video(
            video=buf,
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
            file_name=bot_filename,
            thumb=thumb,
            supports_streaming=True,
        )
        try:
            await status.delete()
        except Exception:
            pass
    except Exception as e:
        log.error(f"Upload error: {e}")
        await status.edit_text(
            f"❌ <b>Upload failed!</b>\n<code>{str(e)[:200]}</code>",
            parse_mode=enums.ParseMode.HTML,
        )


# ════════════════════════════════════════════════════════════════
#  RUN
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log.info("🚀 @KENSHIN_ANIME Bot starting (v2.0 — Cloudflare bypass)...")
    app.run()
