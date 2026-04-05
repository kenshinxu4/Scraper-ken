#!/usr/bin/env python3
"""KENSHIN ANIME BOT — Real-time anime scraper for animedubhindi.me (PyroGram)"""

import asyncio, re, os
from io import BytesIO
from urllib.parse import quote_plus
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton
)
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from aiohttp import ClientSession, ClientTimeout
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, SESSION, OWNER_USERNAME, BOT_NAME

# ─── State ────────────────────────────────────────────────
user_thumbs = {}
user_captions = {}
user_states = {}
ua = UserAgent()

DEF_CAP = (
    "<b><blockquote>✨ {anime_name} ✨</blockquote>"
    "🌸 Episode : {ep} [S{season}]\n"
    "🌸 Quality : {quality}\n"
    "🌸 Audio : Hindi Dub 🎙️ | Official\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "<blockquote>🚀 For More Join 🔰 {owner}</blockquote></b>\n"
    "━━━━━━━━━━━━━━━━━━━━━"
)

# ─── PyroGram Client ─────────────────────────────────────
if SESSION:
    bot = Client(
        "kenshin_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        session_string=SESSION
    )
else:
    bot = Client(
        "kenshin_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

# ─── Helpers ──────────────────────────────────────────────
def _cap(anime, ep, season, quality):
    raw = user_captions.get("global", DEF_CAP)
    return raw.format(
        anime_name=anime, ep=ep,
        season=season, quality=quality,
        owner=OWNER_USERNAME
    )

def _fname(ep, season, quality):
    return f"[{OWNER_USERNAME}] {ep} {season} {quality}.mkv"

def _bar(pct, length=15):
    filled = int((pct / 100) * length)
    return "█" * filled + "░" * (length - filled)

# ─── Web Fetchers ─────────────────────────────────────────
async def _get(url, session, retries=3):
    headers = {
        "User-Agent": ua.random,
        "Referer": "https://animedubhindi.me/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    for i in range(retries):
        try:
            async with session.get(
                url, headers=headers,
                timeout=ClientTimeout(total=30),
                ssl=False, allow_redirects=True
            ) as r:
                if r.status == 200:
                    return await r.text(errors="replace")
                if r.status == 404:
                    return None
                await asyncio.sleep(1.5)
        except Exception:
            await asyncio.sleep(2 ** i)
    return None


async def search_anime(query, session):
    html = await _get(
        f"https://animedubhindi.me/?s={quote_plus(query)}", session
    )
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()
    for tag in soup.select("article"):
        a = tag.select_one("a[rel='bookmark']") or tag.select_one("h2 a") or tag.select_one("a[href]")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if title and href and "/?" not in href and href not in seen:
            seen.add(href)
            results.append((title, href))
    if not results:
        for a in soup.select("a[href]"):
            href = a["href"]
            if "/?" not in href and "animedubhindi.me" in href and href not in seen:
                title = a.get_text(strip=True)
                if title and len(title) > 5:
                    seen.add(href)
                    results.append((title, href))
    return results[:12]


async def get_episodes(anime_url, session):
    html = await _get(anime_url, session)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    episodes = []
    seen = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if ("links.animedubhindi.me" in href or "/episode/" in href) and href not in seen and text:
            seen.add(href)
            episodes.append((text, href))
    if not episodes:
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href not in seen and text and (
                re.search(r'ep(?:isode)?\s*\d+', text, re.I)
                or re.search(r'\d+\s*(?:st|nd|rd|th)\s*ep', text, re.I)
            ):
                seen.add(href)
                episodes.append((text, href))
    if not episodes:
        for match in re.finditer(r'href=["\'](https?://links\.animedubhindi\.me/[^"\']+)["\']', html):
            url = match.group(1)
            if url not in seen:
                seen.add(url)
                label = re.search(r'/episode/([^/]+)/?$', url)
                name = label.group(1).replace("-", " ").title() if label else f"Episode {len(episodes)+1}"
                episodes.append((name, url))
    return episodes


async def get_qualities(links_page_url, session):
    html = await _get(links_page_url, session)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    qualities = []
    seen = set()
    QUAL_ORDER = ["2160p", "1080p", "720p", "480p", "360p"]
    found = {}

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True).lower()
        if ("filepress" in href or "filepress" in text) and href not in seen:
            seen.add(href)
            for q in QUAL_ORDER:
                if q in text or q in href.lower():
                    if q not in found:
                        found[q] = href
                    break
            else:
                if "unknown" not in found:
                    found["unknown"] = href

    for match in re.finditer(r'(https?://[^\s"\']+?filepress[^\s"\']+)', html, re.I):
        url = match.group(1)
        if url not in seen:
            seen.add(url)
            url_lower = url.lower()
            for q in QUAL_ORDER:
                if q in url_lower:
                    if q not in found:
                        found[q] = url
                    break

    for q in QUAL_ORDER:
        if q in found:
            qualities.append((q, found[q]))
    if "unknown" in found and not qualities:
        qualities.append(("Available", found["unknown"]))
    return qualities


async def resolve_filepress(fp_url, session):
    headers = {
        "User-Agent": ua.random,
        "Referer": fp_url,
        "Accept": "text/html,application/xhtml+xml,*/*",
    }
    try:
        async with session.get(
            fp_url, headers=headers,
            timeout=ClientTimeout(total=20),
            ssl=False, allow_redirects=True
        ) as r:
            final_url = str(r.url)
            text = await r.text(errors="replace")

            if "/download/" in final_url:
                return final_url

            soup = BeautifulSoup(text, "html.parser")
            for a in soup.select("a[href*='/download/']"):
                return a["href"]

            dl_match = re.search(r'(https?://[^"\']+?/download/[^"\']+)', text)
            if dl_match:
                return dl_match.group(1)

            redir = re.search(r'window\.location\s*=\s*["\'](.*?)["\']', text)
            if redir:
                return redir.group(1)

            meta = re.search(r'content=["\']\d+;\s*url=(.*?)["\']', text, re.I)
            if meta:
                return meta.group(1)
    except Exception:
        pass
    return None


# ─── /start ───────────────────────────────────────────────
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    user_states.pop(m.from_user.id, None)
    await m.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>🌸 Welcome to {BOT_NAME} 🌸</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎬 <i>Real-time anime scraper for animedubhindi.me</i>\n"
        f"📡 <i>Live progress bars while fetching</i>\n\n"
        f"📌 <b>How to use:</b>\n"
        f"  • Send anime name (e.g: <code>jjk season 3</code>)\n"
        f"  • Choose from search results\n"
        f"  • Select episodes (or ALL)\n"
        f"  • Pick quality\n"
        f"  • Get direct download links!\n\n"
        f"⚙️ <b>Commands:</b>\n"
        f"  /help — All commands\n"
        f"  /set_caption — Set custom caption\n"
        f"  /reset_caption — Reset to default\n"
        f"  /remove_thumb — Remove thumbnail\n"
        f"  /report — Report issue to admin\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>🚀 For More Join 🔰 {OWNER_USERNAME}</blockquote>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 Search Anime", callback_data="search_start")],
            [InlineKeyboardButton("📢 Channel", url=f"https://t.me/{OWNER_USERNAME.replace('@','')}")]
        ]),
        disable_web_page_preview=True
    )


# ─── /help ────────────────────────────────────────────────
@bot.on_message(filters.command("help") & filters.private)
async def help_cmd(c, m):
    await m.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>📋 HELP MENU</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔍 <b>Search:</b>\n"
        "  Send any anime name\n"
        "  Example: <code>jujutsu kaisen season 3</code>\n\n"
        "🖼️ <b>Thumbnail:</b>\n"
        "  Send any image → becomes thumbnail\n\n"
        "📝 <b>Caption:</b>\n"
        "  /set_caption &lt;caption&gt;\n"
        "  Placeholders: {anime_name} {ep} {season} {quality} {owner}\n"
        "  /reset_caption — Reset to default\n\n"
        "🗑️ <b>Other:</b>\n"
        "  /remove_thumb — Remove thumbnail\n"
        "  /report &lt;msg&gt; — Report to admin\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>🚀 For More Join 🔰 {OWNER_USERNAME}</blockquote>",
        disable_web_page_preview=True
    )


# ─── /set_caption (admin) ─────────────────────────────────
@bot.on_message(filters.command("set_caption") & filters.user(ADMIN_ID) & filters.private)
async def set_cap(c, m):
    cap = m.text.split(None, 1)
    if len(cap) < 2:
        await m.reply_text("⚠️ <b>Usage:</b> /set_caption <i>&lt;your caption&gt;</i>")
        return
    user_captions["global"] = cap[1]
    await m.reply_text(
        "✅ <b>Global caption updated!</b>\n\n"
        f"Preview:\n{cap[1].format(anime_name='Anime', ep='E01', season='01', quality='1080p', owner=OWNER_USERNAME)}"
    )


# ─── /reset_caption (admin) ───────────────────────────────
@bot.on_message(filters.command("reset_caption") & filters.user(ADMIN_ID) & filters.private)
async def reset_cap(c, m):
    user_captions.pop("global", None)
    await m.reply_text("✅ <b>Caption reset to default!</b>")


# ─── /remove_thumb ────────────────────────────────────────
@bot.on_message(filters.command("remove_thumb") & filters.private)
async def rem_thumb(c, m):
    uid = m.from_user.id
    if uid in user_thumbs:
        del user_thumbs[uid]
        await m.reply_text("🗑️ <b>Thumbnail removed!</b>")
    else:
        await m.reply_text("⚠️ <b>No thumbnail set.</b>")


# ─── /report ──────────────────────────────────────────────
@bot.on_message(filters.command("report") & filters.private)
async def report_cmd(c, m):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        await m.reply_text("⚠️ <b>Usage:</b> /report <i>&lt;your message&gt;</i>")
        return
    try:
        await c.send_message(
            ADMIN_ID,
            f"📝 <b>New Report</b>\n"
            f"👤 User: <code>{m.from_user.id}</code>\n"
            f"Name: {m.from_user.first_name}\n\n"
            f"{parts[1]}"
        )
        await m.reply_text("✅ <b>Report sent to admin!</b>")
    except Exception as e:
        await m.reply_text(f"❌ Failed to send report: {e}")


# ─── Thumbnail Handler (FIXED) ────────────────────────────
@bot.on_message(filters.photo & filters.private & ~filters.regex(r"^/"))
async def thumb_handler(c, m):
    uid = m.from_user.id
    buf = BytesIO()
    await m.download(file=buf)
    buf.seek(0)
    user_thumbs[uid] = buf.read()
    buf.close()
    await m.reply_text(
        "🖼️ <b>Thumbnail set successfully!</b>\n\n"
        "This will be used for videos you send.\n"
        "Use /remove_thumb to remove it."
    )


# ─── Search Inline Button ─────────────────────────────────
@bot.on_callback_query(filters.regex("^search_start$"))
async def search_inline(c, q):
    await q.answer("Send anime name to search...")
    user_states[q.from_user.id] = {"page": "awaiting_query"}
    try:
        await q.message.edit_text(
            "🔍 <b>Now send the anime name you want to search:</b>"
        )
    except Exception:
        await q.message.reply_text(
            "🔍 <b>Now send the anime name you want to search:</b>"
        )


# ─── Main Search Handler (FIXED) ──────────────────────────
@bot.on_message(filters.text & filters.private & ~filters.regex(r"^/"))
async def anime_search(c, m):
    uid = m.from_user.id
    query = m.text.strip()
    if len(query) < 2:
        return

    prog = await m.reply_text(
        f"🔄 <b>Searching:</b> <i>{query}</i>\n"
        f"⏳ [{_bar(5)}] 5% — Connecting to animedubhindi.me..."
    )

    try:
        await prog.edit_text(
            f"🔄 <b>Searching:</b> <i>{query}</i>\n"
            f"⏳ [{_bar(25)}] 25% — Fetching search page..."
        )

        async with ClientSession() as session:
            results = await search_anime(query, session)

        await prog.edit_text(
            f"🔄 <b>Searching:</b> <i>{query}</i>\n"
            f"⏳ [{_bar(60)}] 60% — Parsing {len(results)} results..."
        )
        await asyncio.sleep(0.3)

        await prog.edit_text(
            f"🔄 <b>Searching:</b> <i>{query}</i>\n"
            f"⏳ [{_bar(100)}] 100% — Done!"
        )
        await asyncio.sleep(0.3)

    except Exception as e:
        await prog.edit_text(f"❌ <b>Search error:</b> <code>{e}</code>")
        return

    if not results:
        await prog.edit_text(
            f"❌ <b>No results for:</b> <i>{query}</i>\n\n"
            f"💡 Try different keywords like:\n"
            f"  • <code>jujutsu kaisen</code>\n"
            f"  • <code>jjk season 3</code>\n"
            f"  • <code>demon slayer</code>"
        )
        return

    user_states[uid] = {"page": "select_anime", "data": {"results": results, "query": query}}

    btns = []
    for i, (title, url) in enumerate(results):
        short = (title[:52] + "...") if len(title) > 52 else title
        btns.append([InlineKeyboardButton(f"📌 {short}", callback_data=f"anime_{i}")])
    btns.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

    await prog.edit_text(
        f"🔍 <b>Results for:</b> <i>{query}</i>\n"
        f"📊 Found: <b>{len(results)}</b> anime\n\n"
        f"👇 <b>Choose one:</b>",
        reply_markup=InlineKeyboardMarkup(btns),
        disable_web_page_preview=True
    )


# ─── Callback: Select Anime ───────────────────────────────
@bot.on_callback_query(filters.regex(r"^anime_(\d+)$"))
async def cb_select_anime(c, q):
    uid = q.from_user.id
    idx = int(q.pattern_match.group(1))
    state = user_states.get(uid)
    if not state or state["page"] != "select_anime":
        await q.answer("❌ Session expired. Search again.", show_alert=True)
        return

    results = state["data"]["results"]
    if idx >= len(results):
        await q.answer("❌ Invalid", show_alert=True)
        return

    title, url = results[idx]
    await q.answer(f"Fetching: {title[:40]}...")

    try:
        await q.message.edit_text(
            f"📺 <b>{title}</b>\n"
            f"⏳ [{_bar(10)}] 10% — Loading anime page..."
        )

        async with ClientSession() as session:
            episodes = await get_episodes(url, session)

        await q.message.edit_text(
            f"📺 <b>{title}</b>\n"
            f"⏳ [{_bar(80)}] 80% — Found {len(episodes)} episodes..."
        )
        await asyncio.sleep(0.3)

        await q.message.edit_text(
            f"📺 <b>{title}</b>\n"
            f"⏳ [{_bar(100)}] 100% — Done!"
        )
        await asyncio.sleep(0.2)

    except Exception as e:
        await q.message.edit_text(f"❌ <b>Error:</b> <code>{e}</code>")
        return

    if not episodes:
        await q.message.edit_text(
            f"❌ <b>No episodes found!</b>\n\n"
            f"This anime page may not have episode download links."
        )
        return

    user_states[uid] = {
        "page": "select_episodes",
        "data": {"anime_title": title, "anime_url": url, "episodes": episodes}
    }

    btns = []
    for i, (ep_title, ep_url) in enumerate(episodes):
        short = (ep_title[:48] + "...") if len(ep_title) > 48 else ep_title
        btns.append([InlineKeyboardButton(f"▶️ {short}", callback_data=f"ep_{i}")])
    btns.append([InlineKeyboardButton("📥 ALL Episodes", callback_data="ep_all")])
    btns.append([
        InlineKeyboardButton("⬅️ Back", callback_data="back_search"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ])

    await q.message.edit_text(
        f"📺 <b>{title}</b>\n"
        f"📊 Episodes: <b>{len(episodes)}</b>\n\n"
        f"👇 <b>Select episode(s):</b>",
        reply_markup=InlineKeyboardMarkup(btns),
        disable_web_page_preview=True
    )


# ─── Callback: Select Episode ─────────────────────────────
@bot.on_callback_query(filters.regex(r"^ep_(\d+|all)$"))
async def cb_select_ep(c, q):
    uid = q.from_user.id
    choice = q.pattern_match.group(1)
    state = user_states.get(uid)
    if not state or state["page"] != "select_episodes":
        await q.answer("❌ Session expired.", show_alert=True)
        return

    episodes = state["data"]["episodes"]
    anime_title = state["data"]["anime_title"]

    if choice == "all":
        selected = list(range(len(episodes)))
    else:
        selected = [int(choice)]

    user_states[uid] = {
        "page": "select_quality",
        "data": {
            "anime_title": anime_title,
            "episodes": episodes,
            "selected_eps": selected,
        }
    }

    ep_title, ep_url = episodes[selected[0]]
    await q.answer(f"Loading: {ep_title[:30]}...")

    try:
        await q.message.edit_text(
            f"📺 <b>{anime_title}</b>\n"
            f"▶️ <b>{ep_title}</b>\n"
            f"⏳ [{_bar(15)}] 15% — Fetching links page..."
        )

        async with ClientSession() as session:
            qualities = await get_qualities(ep_url, session)

        await q.message.edit_text(
            f"📺 <b>{anime_title}</b>\n"
            f"▶️ <b>{ep_title}</b>\n"
            f"⏳ [{_bar(90)}] 90% — Found {len(qualities)} qualities..."
        )
        await asyncio.sleep(0.2)

        await q.message.edit_text(
            f"📺 <b>{anime_title}</b>\n"
            f"▶️ <b>{ep_title}</b>\n"
            f"⏳ [{_bar(100)}] 100% — Done!"
        )
        await asyncio.sleep(0.2)

    except Exception as e:
        await q.message.edit_text(f"❌ <b>Error:</b> <code>{e}</code>")
        return

    if not qualities:
        await q.message.edit_text(
            f"❌ <b>No download links found!</b>\n\n"
            f"This episode may not have FilePress links.\n"
            f"Try another episode."
        )
        return

    user_states[uid]["data"]["qualities"] = qualities
    user_states[uid]["data"]["ref_qualities"] = qualities

    btns = []
    for i, (q_name, q_url) in enumerate(qualities):
        btns.append([InlineKeyboardButton(f"🎞️ {q_name}", callback_data=f"qual_{i}")])
    btns.append([
        InlineKeyboardButton("⬅️ Back to Episodes", callback_data="back_eps"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ])

    label = f"({len(selected)} episodes)" if len(selected) > 1 else ""
    await q.message.edit_text(
        f"📺 <b>{anime_title}</b>\n"
        f"▶️ <b>{ep_title}</b> {label}\n"
        f"📊 Qualities: <b>{len(qualities)}</b>\n\n"
        f"👇 <b>Select quality:</b>",
        reply_markup=InlineKeyboardMarkup(btns),
        disable_web_page_preview=True
    )


# ─── Callback: Select Quality & Resolve ───────────────────
@bot.on_callback_query(filters.regex(r"^qual_(\d+)$"))
async def cb_select_qual(c, q):
    uid = q.from_user.id
    qidx = int(q.pattern_match.group(1))
    state = user_states.get(uid)
    if not state or state["page"] != "select_quality":
        await q.answer("❌ Session expired.", show_alert=True)
        return

    d = state["data"]
    anime_title = d["anime_title"]
    episodes = d["episodes"]
    selected_eps = d["selected_eps"]
    quality_name, fp_url = d["qualities"][qidx]

    season_match = re.search(r'season\s*(\d+)', anime_title, re.I)
    season = season_match.group(1) if season_match else "01"

    await q.answer(f"Resolving {quality_name}...")

    all_results = []
    total = len(selected_eps)

    for ep_i, ep_idx in enumerate(selected_eps):
        ep_title, ep_url = episodes[ep_idx]
        ep_match = re.search(r'ep(?:isode)?\s*(\d+)', ep_title, re.I)
        ep_num = ep_match.group(1) if ep_match else str(ep_idx + 1)

        pct = int(((ep_i + 1) / total) * 100)

        await q.message.edit_text(
            f"🔄 <b>Resolving Links...</b>\n\n"
            f"📺 {anime_title}\n"
            f"▶️ Episode {ep_num} [{ep_i+1}/{total}]\n"
            f"🎞️ Quality: {quality_name}\n\n"
            f"[{_bar(pct)}] {pct}%\n"
            f"⏳ Fetching links page..."
        )

        async with ClientSession() as session:
            if total == 1:
                dl_url = await resolve_filepress(fp_url, session)
            else:
                quals = await get_qualities(ep_url, session)
                ep_fp = fp_url
                for qn, qu in quals:
                    if quality_name in qn:
                        ep_fp = qu
                        break
                dl_url = await resolve_filepress(ep_fp, session)

        if dl_url:
            fname = _fname(f"E{ep_num}", f"S{season}", quality_name)
            caption = _cap(anime_title, f"Episode {ep_num}", season, quality_name)
            all_results.append({
                "ep_title": ep_title,
                "ep_num": ep_num,
                "quality": quality_name,
                "season": season,
                "dl_url": dl_url,
                "filename": fname,
                "caption": caption,
            })

        await asyncio.sleep(0.8)

    if not all_results:
        await q.message.edit_text(
            "❌ <b>Could not resolve any download links!</b>\n\n"
            "Possible reasons:\n"
            "• FilePress is blocking requests\n"
            "• Links are dead/expired\n"
            "• Website structure changed\n\n"
            "💡 Try again later or try a different quality."
        )
        return

    await q.message.edit_text(
        f"✅ <b>{len(all_results)} link(s) resolved!</b>\n\n"
        f"📺 {anime_title}\n"
        f"🎞️ {quality_name}\n\n"
        f"⏳ Sending results..."
    )

    for item in all_results:
        try:
            await c.send_message(
                uid,
                f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<blockquote>✨ {anime_title} ✨</blockquote>\n"
                f"🌸 Episode : {item['ep_num']} [S{item['season']}]\n"
                f"🌸 Quality : {item['quality']}\n"
                f"🌸 Audio : Hindi Dub 🎙️ | Official\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 <code>{item['filename']}</code>\n\n"
                f"⬇️ <b>Download Link:</b>\n"
                f"<code>{item['dl_url']}</code>\n\n"
                f"<blockquote>🚀 For More Join 🔰 {OWNER_USERNAME}</blockquote>",
                disable_web_page_preview=False
            )
            await asyncio.sleep(0.5)
        except Exception:
            pass

    try:
        await q.message.edit_text(
            f"✅ <b>Completed!</b>\n\n"
            f"📺 {anime_title}\n"
            f"📊 {len(all_results)} episode(s)\n"
            f"🎞️ {quality_name}\n\n"
            f"💡 <i>Click download links above to save.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 New Search", callback_data="search_start")]
            ])
        )
    except Exception:
        pass


# ─── Back Buttons ─────────────────────────────────────────
@bot.on_callback_query(filters.regex("^back_search$"))
async def cb_back_search(c, q):
    user_states.pop(q.from_user.id, None)
    await q.message.edit_text("🔍 <b>Send anime name to search:</b>")


@bot.on_callback_query(filters.regex("^back_eps$"))
async def cb_back_eps(c, q):
    uid = q.from_user.id
    state = user_states.get(uid)
    if not state:
        await q.answer("❌ Expired", show_alert=True)
        return
    d = state["data"]
    btns = []
    for i, (ep_title, ep_url) in enumerate(d["episodes"]):
        short = (ep_title[:48] + "...") if len(ep_title) > 48 else ep_title
        btns.append([InlineKeyboardButton(f"▶️ {short}", callback_data=f"ep_{i}")])
    btns.append([InlineKeyboardButton("📥 ALL Episodes", callback_data="ep_all")])
    btns.append([
        InlineKeyboardButton("⬅️ Back", callback_data="back_search"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ])
    await q.message.edit_text(
        f"📺 <b>{d['anime_title']}</b>\n"
        f"📊 Episodes: <b>{len(d['episodes'])}</b>\n\n"
        f"👇 <b>Select episode(s):</b>",
        reply_markup=InlineKeyboardMarkup(btns),
        disable_web_page_preview=True
    )


# ─── Cancel ───────────────────────────────────────────────
@bot.on_callback_query(filters.regex("^cancel$"))
async def cb_cancel(c, q):
    user_states.pop(q.from_user.id, None)
    await q.message.edit_text(
        "❌ <b>Cancelled.</b>\n\nSend anime name to search again."
    )


# ─── Admin: /ping ─────────────────────────────────────────
@bot.on_message(filters.command("ping") & filters.user(ADMIN_ID) & filters.private)
async def ping_cmd(c, m):
    start = asyncio.get_event_loop().time()
    msg = await m.reply_text("🏓 Pinging...")
    end = asyncio.get_event_loop().time()
    await msg.edit_text(f"🏓 <b>Pong!</b> <code>{int((end - start) * 1000)}ms</code>")


# ─── Admin: /stats ────────────────────────────────────────
@bot.on_message(filters.command("stats") & filters.user(ADMIN_ID) & filters.private)
async def stats_cmd(c, m):
    await m.reply_text(
        f"📊 <b>Bot Stats</b>\n\n"
        f"👥 Thumbnails set: <code>{len(user_thumbs)}</code>\n"
        f"📝 Custom captions: <code>{len(user_captions)}</code>\n"
        f"🔄 Active sessions: <code>{len(user_states)}</code>"
    )


# ─── Admin: /broadcast ────────────────────────────────────
@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.private)
async def broadcast_cmd(c, m):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        await m.reply_text("⚠️ <b>Usage:</b> /broadcast <i>&lt;message&gt;</i>")
        return
    sent = 0
    for uid in list(user_states.keys()):
        try:
            await c.send_message(uid, parts[1])
            sent += 1
        except Exception:
            pass
    await m.reply_text(f"✅ <b>Broadcast sent to {sent} users.</b>")


# ─── Main ─────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🚀 {BOT_NAME} starting...")
    bot.run()
