#!/usr/bin/env python3
"""KENSHIN ANIME BOT — Real-time anime scraper for animedubhindi.me"""

import asyncio, re, os, json, traceback
from io import BytesIO
from urllib.parse import quote_plus, urljoin
from telethon import TelegramClient, events, Button
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from aiohttp import ClientSession, ClientTimeout
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, SESSION, OWNER_USERNAME, BOT_NAME

# ─── State ────────────────────────────────────────────────
user_thumbs = {}          # uid -> bytes
user_captions = {}        # uid -> str
user_states = {}          # uid -> {"page":str,"data":dict}
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

# ─── Telethon Client ──────────────────────────────────────
bot = TelegramClient(
    StringSession(SESSION) if SESSION else "bot",
    API_ID, API_HASH
).start(bot_token=BOT_TOKEN)

# ─── Helpers ──────────────────────────────────────────────
def _h(text):
    return re.sub(r'<[^>]+>', '', text).strip()

def _cap(anime, ep, season, quality):
    raw = user_captions.get("global", DEF_CAP)
    return raw.format(anime_name=anime, ep=ep, season=season, quality=quality, owner=OWNER_USERNAME)

def _fname(ep, season, quality):
    return f"[{OWNER_USERNAME}] {ep} {season} {quality}.mkv"

# ─── Real-time Web Fetchers ───────────────────────────────
async def _get(url, session, retries=3):
    headers = {"User-Agent": ua.random, "Referer": "https://animedubhindi.me/"}
    for i in range(retries):
        try:
            async with session.get(url, headers=headers, timeout=ClientTimeout(total=25), ssl=False) as r:
                if r.status == 200:
                    return await r.text(errors="replace")
                await asyncio.sleep(1)
        except Exception:
            await asyncio.sleep(2 ** i)
    return None

async def search_anime(query, session):
    """Search animedubhindi.me for anime matching query. Returns [(title, url), ...]"""
    html = await _get(f"https://animedubhindi.me/?s={quote_plus(query)}", session)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for a in soup.select("article a[rel='bookmark']"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if title and href and "/?" not in href:
            results.append((title, href))
    return results[:10]

async def get_episodes(anime_url, session):
    """Get episode list from anime page. Returns [(ep_title, links_page_url), ...]"""
    html = await _get(anime_url, session)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    episodes = []
    for a in soup.select("a[href*='links.animedubhindi.me']"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if title and href:
            episodes.append((title, href))
    # Fallback: any links that look like episode pages
    if not episodes:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "links.animedubhindi.me" in href or "/episode/" in href:
                title = a.get_text(strip=True) or "Episode"
                episodes.append((title, href))
    return episodes

async def get_qualities(links_page_url, session):
    """Get quality options from links.animedubhindi.me page. Returns [(quality, filepress_url), ...]"""
    html = await _get(links_page_url, session)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    qualities = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()
        if "filepress" in href or "filepress" in text:
            for q in ["2160p", "1080p", "720p", "480p", "360p"]:
                if q in text or q in href:
                    qualities.append((q, href))
                    break
            else:
                qualities.append(("Unknown", href))
    # Fallback: find any filepress links
    if not qualities:
        for a in soup.find_all("a", href=True):
            if "filepress" in a["href"]:
                qualities.append(("Available", a["href"]))
    return qualities

async def resolve_filepress(fp_url, session):
    """Resolve FilePress page to direct download URL. Returns str or None."""
    headers = {"User-Agent": ua.random, "Referer": fp_url}
    try:
        async with session.get(fp_url, headers=headers, timeout=ClientTimeout(total=20), ssl=False, allow_redirects=True) as r:
            final_url = str(r.url)
            text = await r.text(errors="replace")
            # Check for /download/ in final URL
            if "/download/" in final_url:
                return final_url
            # Check page content for download links
            soup = BeautifulSoup(text, "html.parser")
            for a in soup.find_all("a", href=True):
                if "/download/" in a["href"]:
                    return a["href"]
            # Try to find in JS/JSON
            dl_match = re.search(r'(https?://[^"\']+?/download/[^"\']+)', text)
            if dl_match:
                return dl_match.group(1)
            # Check for redirect patterns
            redir_match = re.search(r'window\.location\s*=\s*["\'](.*?)["\']', text)
            if redir_match:
                return redir_match.group(1)
    except Exception:
        pass
    return None

# ─── Progress Edit Helper ─────────────────────────────────
async def edit_prog(event, text, buttons=None):
    try:
        await event.edit(text, buttons=buttons)
    except Exception:
        pass

# ─── /start ───────────────────────────────────────────────
@bot.on(events.NewMessage(pattern="/start"))
async def start_cmd(e):
    uid = e.sender_id
    user_states.pop(uid, None)
    await e.reply(
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>🌸 Welcome to {BOT_NAME} 🌸</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎬 <i>I can fetch anime from animedubhindi.me</i>\n"
        f"📡 <i>Real-time scraping with live progress</i>\n\n"
        f"📌 <b>How to use:</b>\n"
        f"  • Send anime name (e.g: <code>jjk season 3</code>)\n"
        f"  • Choose from results\n"
        f"  • Select episodes\n"
        f"  • Pick quality\n"
        f"  • Receive video links!\n\n"
        f"⚙️ <b>Commands:</b>\n"
        f"  /help — All commands\n"
        f"  /set_caption — Custom caption\n"
        f"  /reset_caption — Reset caption\n"
        f"  /remove_thumb — Remove thumbnail\n"
        f"  /report — Report an issue\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>🚀 {OWNER_USERNAME}</blockquote>",
        buttons=[
            [Button.inline("🔎 Search Anime", data="search_start")],
            [Button.url("📢 Channel", f"https://t.me/{OWNER_USERNAME.replace('@','')}")]
        ],
        parse_mode="html"
    )

# ─── /help ────────────────────────────────────────────────
@bot.on(events.NewMessage(pattern="/help"))
async def help_cmd(e):
    await e.reply(
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>📋 HELP MENU</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔍 <b>Search:</b>\n"
        "  Send any anime name\n"
        "  Example: <code>jujutsu kaisen season 3</code>\n\n"
        "🖼️ <b>Thumbnail:</b>\n"
        "  Send any image to set as thumbnail\n\n"
        "📝 <b>Caption:</b>\n"
        "  /set_caption &lt;your caption&gt;\n"
        "  Use: {anime_name}, {ep}, {season}, {quality}, {owner}\n"
        "  /reset_caption — Reset to default\n\n"
        "🗑️ <b>Other:</b>\n"
        "  /remove_thumb — Remove thumbnail\n"
        "  /report &lt;message&gt; — Report to admin\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>🚀 {OWNER_USERNAME}</blockquote>",
        parse_mode="html"
    )

# ─── /set_caption ─────────────────────────────────────────
@bot.on(events.NewMessage(pattern=r"/set_caption\s+(.*)", from_users=ADMIN_ID))
async def set_cap(e):
    cap = e.pattern_match.group(1).strip()
    user_captions["global"] = cap
    await e.reply("✅ <b>Global caption updated!</b>", parse_mode="html")

# ─── /reset_caption ───────────────────────────────────────
@bot.on(events.NewMessage(pattern="/reset_caption", from_users=ADMIN_ID))
async def reset_cap(e):
    user_captions.pop("global", None)
    await e.reply("✅ <b>Caption reset to default!</b>", parse_mode="html")

# ─── /remove_thumb ────────────────────────────────────────
@bot.on(events.NewMessage(pattern="/remove_thumb"))
async def rem_thumb(e):
    uid = e.sender_id
    if uid in user_thumbs:
        del user_thumbs[uid]
        await e.reply("🗑️ <b>Thumbnail removed!</b>", parse_mode="html")
    else:
        await e.reply("⚠️ <b>No thumbnail set.</b>", parse_mode="html")

# ─── /report ──────────────────────────────────────────────
@bot.on(events.NewMessage(pattern=r"/report\s*(.*)"))
async def report_cmd(e):
    msg = e.pattern_match.group(1).strip()
    if not msg:
        await e.reply("⚠️ <b>Usage:</b> /report &lt;your message&gt;", parse_mode="html")
        return
    await bot.send_message(
        ADMIN_ID,
        f"📝 <b>New Report</b>\n👤 User: <code>{e.sender_id}</code>\n\n{msg}",
        parse_mode="html"
    )
    await e.reply("✅ <b>Report sent to admin!</b>", parse_mode="html")

# ─── Thumbnail Handler (image = thumbnail) ────────────────
@bot.on(events.NewMessage(func=lambda e: e.photo and not e.text.startswith("/")))
async def thumb_handler(e):
    uid = e.sender_id
    buf = BytesIO()
    await e.download_media(file=buf)
    buf.seek(0)
    user_thumbs[uid] = buf.read()
    buf.close()
    await e.reply("🖼️ <b>Thumbnail set!</b>\n\nThis will be used for all videos you send.", parse_mode="html")

# ─── Search Inline Button ─────────────────────────────────
@bot.on(events.CallbackQuery(data=b"search_start"))
async def search_inline(e):
    await e.answer("Send anime name to search...")
    user_states[e.sender_id] = {"page": "awaiting_query"}
    await e.edit("🔍 <b>Now send the anime name you want to search:</b>", parse_mode="html")

# ─── Main Message Handler (anime name input) ──────────────
@bot.on(events.NewMessage(func=lambda e: e.text and not e.text.startswith("/") and e.text.strip()))
async def anime_search(e):
    uid = e.sender_id
    query = e.text.strip()
    if len(query) < 2:
        return

    prog = await e.reply(f"🔄 <b>Searching for:</b> <i>{query}</i>\n⏳ Connecting to animedubhindi.me...", parse_mode="html")

    async with ClientSession() as session:
        results = await search_anime(query, session)

    if not results:
        await edit_prog(prog, f"❌ <b>No results found for:</b> <i>{query}</i>\n\n💡 Try different keywords.")
        return

    user_states[uid] = {"page": "select_anime", "data": {"results": results, "query": query}}

    btns = []
    for i, (title, url) in enumerate(results):
        short = title[:55] + "..." if len(title) > 55 else title
        btns.append([Button.inline(f"📌 {short}", data=f"anime_{i}")])
    btns.append([Button.inline("❌ Cancel", data="cancel")])

    await edit_prog(
        prog,
        f"🔍 <b>Results for:</b> <i>{query}</i>\n"
        f"📊 Found: <b>{len(results)}</b> anime\n\n"
        f"👇 <b>Choose one:</b>",
        buttons=btns
    )

# ─── Callback: Select Anime ───────────────────────────────
@bot.on(events.CallbackQuery(pattern=r"^anime_(\d+)$"))
async def cb_select_anime(e):
    uid = e.sender_id
    idx = int(e.pattern_match.group(1))
    state = user_states.get(uid)
    if not state or state["page"] != "select_anime":
        await e.answer("❌ Session expired. Search again.", alert=True)
        return

    results = state["data"]["results"]
    if idx >= len(results):
        await e.answer("❌ Invalid choice", alert=True)
        return

    title, url = results[idx]
    await e.answer(f"Fetching: {title[:40]}...")

    await edit_prog(e, f"📺 <b>{title}</b>\n⏳ Fetching episodes from page...\n🔄 Real-time scraping...")

    async with ClientSession() as session:
        episodes = await get_episodes(url, session)

    if not episodes:
        await edit_prog(e, f"❌ <b>No episodes found!</b>\n\nThis anime page may not have episode links.")
        return

    user_states[uid] = {
        "page": "select_episodes",
        "data": {
            "anime_title": title,
            "anime_url": url,
            "episodes": episodes
        }
    }

    btns = []
    for i, (ep_title, ep_url) in enumerate(episodes):
        short = ep_title[:50] + "..." if len(ep_title) > 50 else ep_title
        btns.append([Button.inline(f"▶️ {short}", data=f"ep_{i}")])
    btns.append([Button.inline("📥 ALL Episodes", data="ep_all")])
    btns.append([Button.inline("⬅️ Back", data="back_search"), Button.inline("❌ Cancel", data="cancel")])

    await edit_prog(
        e,
        f"📺 <b>{title}</b>\n"
        f"📊 Episodes found: <b>{len(episodes)}</b>\n\n"
        f"👇 <b>Select episode(s):</b>",
        buttons=btns
    )

# ─── Callback: Select Episode ─────────────────────────────
@bot.on(events.CallbackQuery(pattern=r"^ep_(\d+|all)$"))
async def cb_select_ep(e):
    uid = e.sender_id
    choice = e.pattern_match.group(1)
    state = user_states.get(uid)
    if not state or state["page"] != "select_episodes":
        await e.answer("❌ Session expired.", alert=True)
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
            "current_ep_idx": 0
        }
    }

    # Start with first selected episode's qualities
    ep_title, ep_url = episodes[selected[0]]
    await e.answer(f"Loading qualities for: {ep_title[:30]}...")
    await edit_prog(e, f"📺 <b>{anime_title}</b>\n▶️ <b>{ep_title}</b>\n⏳ Fetching available qualities...\n🔄 Scraping links page...")

    async with ClientSession() as session:
        qualities = await get_qualities(ep_url, session)

    if not qualities:
        await edit_prog(e, f"❌ <b>No download links found!</b>\n\nThis episode may not have FilePress links.")
        return

    user_states[uid]["data"]["qualities"] = qualities

    btns = []
    for i, (q, qurl) in enumerate(qualities):
        btns.append([Button.inline(f"🎞️ {q}", data=f"qual_{i}")])
    btns.append([Button.inline("⬅️ Back to Episodes", data="back_eps"), Button.inline("❌ Cancel", data="cancel")])

    label = f"({len(selected)} episodes)" if len(selected) > 1 else ""
    await edit_prog(
        e,
        f"📺 <b>{anime_title}</b>\n"
        f"▶️ <b>{ep_title}</b> {label}\n"
        f"📊 Qualities found: <b>{len(qualities)}</b>\n\n"
        f"👇 <b>Select quality:</b>",
        buttons=btns
    )

# ─── Callback: Select Quality & Resolve ───────────────────
@bot.on(events.CallbackQuery(pattern=r"^qual_(\d+)$"))
async def cb_select_qual(e):
    uid = e.sender_id
    qidx = int(e.pattern_match.group(1))
    state = user_states.get(uid)
    if not state or state["page"] != "select_quality":
        await e.answer("❌ Session expired.", alert=True)
        return

    d = state["data"]
    anime_title = d["anime_title"]
    episodes = d["episodes"]
    selected_eps = d["selected_eps"]
    quality_name, fp_url = d["qualities"][qidx]

    await e.answer(f"Resolving {quality_name} links...")

    # Extract season info from anime title
    season_match = re.search(r'season\s*(\d+)', anime_title, re.I)
    season = season_match.group(1) if season_match else "01"

    all_results = []

    for ep_i, ep_idx in enumerate(selected_eps):
        ep_title, ep_url = episodes[ep_idx]

        # Extract episode number
        ep_match = re.search(r'ep(?:isode)?\s*(\d+)', ep_title, re.I)
        ep_num = ep_match.group(1) if ep_match else str(ep_idx + 1)

        progress_pct = int(((ep_i + 1) / len(selected_eps)) * 100)
        bar_len = 15
        filled = int((progress_pct / 100) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        await edit_prog(
            e,
            f"🔄 <b>Resolving Links...</b>\n\n"
            f"📺 {anime_title}\n"
            f"▶️ Episode {ep_num} ({ep_i+1}/{len(selected_eps)})\n"
            f"🎞️ Quality: {quality_name}\n\n"
            f"[{bar}] {progress_pct}%\n"
            f"⏳ Fetching FilePress page..."
        )

        async with ClientSession() as session:
            # For single episode, use the already-fetched quality URL
            if len(selected_eps) == 1:
                dl_url = await resolve_filepress(fp_url, session)
            else:
                # For multiple episodes, fetch each episode's quality links
                quals = await get_qualities(ep_url, session)
                ep_fp_url = fp_url  # fallback
                for qn, qu in quals:
                    if quality_name in qn:
                        ep_fp_url = qu
                        break
                dl_url = await resolve_filepress(ep_fp_url, session)

        if dl_url:
            # Build filename
            fname = _fname(f"E{ep_num}", f"S{season}", quality_name)
            caption = _cap(anime_title, f"Episode {ep_num}", season, quality_name)

            all_results.append({
                "ep_title": ep_title,
                "ep_num": ep_num,
                "quality": quality_name,
                "season": season,
                "dl_url": dl_url,
                "filename": fname,
                "caption": caption
            })

        # Small delay to avoid rate limiting
        await asyncio.sleep(1)

    if not all_results:
        await edit_prog(e, "❌ <b>Could not resolve any download links!</b>\n\nFilePress may be blocking requests or links are dead.")
        return

    # Send results
    await edit_prog(e, f"✅ <b>Done! {len(all_results)} link(s) resolved.</b>\n\nPreparing results...")

    for item in all_results:
        thumb = user_thumbs.get(uid)
        try:
            await bot.send_message(
                uid,
                f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<blockquote>✨ {anime_title} ✨</blockquote>\n"
                f"🌸 Episode : {item['ep_num']} [S{item['season']}]\n"
                f"🌸 Quality : {item['quality']}\n"
                f"🌸 Audio : Hindi Dub 🎙️ | Official\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 File : <code>{item['filename']}</code>\n\n"
                f"⬇️ <b>Download Link:</b>\n"
                f"<code>{item['dl_url']}</code>\n\n"
                f"<blockquote>🚀 For More Join 🔰 {OWNER_USERNAME}</blockquote>",
                parse_mode="html"
            )
            await asyncio.sleep(0.5)
        except Exception:
            pass

    await edit_prog(
        e,
        f"✅ <b>Completed!</b>\n\n"
        f"📺 {anime_title}\n"
        f"📊 {len(all_results)} episode(s)\n"
        f"🎞️ {quality_name}\n\n"
        f"💡 <i>Click the download links above to save.</i>",
        buttons=[Button.inline("🔍 New Search", data="search_start")]
    )

# ─── Back Buttons ─────────────────────────────────────────
@bot.on(events.CallbackQuery(data=b"back_search"))
async def cb_back_search(e):
    user_states.pop(e.sender_id, None)
    await e.edit("🔍 <b>Send anime name to search:</b>", parse_mode="html")

@bot.on(events.CallbackQuery(data=b"back_eps"))
async def cb_back_eps(e):
    uid = e.sender_id
    state = user_states.get(uid)
    if not state:
        await e.answer("❌ Expired", alert=True)
        return
    # Rebuild episodes list
    d = state["data"]
    btns = []
    for i, (ep_title, ep_url) in enumerate(d["episodes"]):
        short = ep_title[:50] + "..." if len(ep_title) > 50 else ep_title
        btns.append([Button.inline(f"▶️ {short}", data=f"ep_{i}")])
    btns.append([Button.inline("📥 ALL Episodes", data="ep_all")])
    btns.append([Button.inline("⬅️ Back", data="back_search"), Button.inline("❌ Cancel", data="cancel")])

    await e.edit(
        f"📺 <b>{d['anime_title']}</b>\n"
        f"📊 Episodes: <b>{len(d['episodes'])}</b>\n\n"
        f"👇 <b>Select episode(s):</b>",
        buttons=btns
    )

# ─── Cancel ───────────────────────────────────────────────
@bot.on(events.CallbackQuery(data=b"cancel"))
async def cb_cancel(e):
    user_states.pop(e.sender_id, None)
    await e.edit("❌ <b>Cancelled.</b>\n\nSend anime name to search again.", parse_mode="html")

# ─── Alive / Ping (admin only) ────────────────────────────
@bot.on(events.NewMessage(pattern="/ping", from_users=ADMIN_ID))
async def ping_cmd(e):
    start = asyncio.get_event_loop().time()
    msg = await e.reply("🏓 Pinging...")
    end = asyncio.get_event_loop().time()
    await msg.edit(f"🏓 <b>Pong!</b> <code>{int((end - start) * 1000)}ms</code>", parse_mode="html")

@bot.on(events.NewMessage(pattern="/stats", from_users=ADMIN_ID))
async def stats_cmd(e):
    await e.reply(
        f"📊 <b>Bot Stats</b>\n\n"
        f"👥 Thumbnails set: <code>{len(user_thumbs)}</code>\n"
        f"📝 Custom captions: <code>{len(user_captions)}</code>\n"
        f"🔄 Active sessions: <code>{len(user_states)}</code>",
        parse_mode="html"
    )

# ─── Main ─────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🚀 {BOT_NAME} is starting...")
    bot.run_until_disconnected()
