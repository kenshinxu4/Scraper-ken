"""
🎌 AnimeDubHindi Telegram Bot - @KENSHIN_ANIME
Single-file bot with real-time progress tracking
Scrapes: animedubhindi.me | Downloads from: filepress.wiki
"""

import os
import re
import time
import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==================== CONFIG ====================
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

BASE_URL = "https://www.animedubhindi.me"
LINKS_URL = "https://links.animedubhindi.me"
FILEPRESS_BASE = "https://new2.filepress.wiki"

DEFAULT_CAPTION = """<b><blockquote>✨ {anime_name} ✨</blockquote>
🌸 Episode : {ep} [S{season}]
🌸 Quality : {quality}
🌸 Audio : Hindi Dub 🎙️ | Official
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join 🔰 [@KENSHIN_ANIME]</blockquote></b>
━━━━━━━━━━━━━━━━━━━━━"""

user_data, user_captions, user_thumbnails = {}, {}, {}

app = Client("anime_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, parse_mode=enums.ParseMode.HTML)

# ==================== PROGRESS HELPERS ====================
def format_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def format_time(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m {int(seconds%60)}s"
    else:
        return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m"

def create_progress_bar(percentage, length=20):
    filled = int(length * percentage / 100)
    return '█' * filled + '░' * (length - filled)

# ==================== SCRAPING ====================
async def fetch_html(url, session):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        async with session.get(url, headers=headers, timeout=30) as resp:
            return await resp.text() if resp.status == 200 else None
    except Exception as e:
        print(f"Fetch error: {e}")
        return None

async def search_anime(query, session):
    url = f"{BASE_URL}/?s={query.replace(' ', '+')}"
    html = await fetch_html(url, session)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    
    for article in soup.find_all('article', class_='post'):
        try:
            title_elem = article.find('h2', class_='entry-title')
            if title_elem and title_elem.find('a'):
                link = title_elem.find('a')
                img = article.find('img')
                results.append({
                    'title': link.text.strip(),
                    'link': link.get('href', ''),
                    'image': img.get('src', '') if img else ''
                })
        except:
            continue
    return results

async def get_anime_details(anime_url, session):
    html = await fetch_html(anime_url, session)
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    details = {'title': '', 'image': '', 'episodes_link': '', 'total_episodes': 0, 'qualities': []}
    
    try:
        title = soup.find('h1', class_='entry-title')
        if title:
            details['title'] = title.text.strip()
        
        img = soup.find('img', class_='wp-post-image')
        if img:
            details['image'] = img.get('src', '')
        
        slug = re.search(r'/([^/]+)/?$', anime_url)
        if slug:
            details['episodes_link'] = f"{LINKS_URL}/episode/{slug.group(1).split('?')[0].split('#')[0]}/"
        
        content = soup.find('div', class_='entry-content')
        if content:
            text = content.get_text()
            ep_match = re.search(r'Total Episode[s]?\s*[:]?\s*(\d+)', text, re.I)
            if ep_match:
                details['total_episodes'] = int(ep_match.group(1))
            
            q_match = re.search(r'Quality\s*[:]?\s*([^\n]+)', text, re.I)
            if q_match:
                details['qualities'] = [q.strip() for q in re.split(r'[|\s,]+', q_match.group(1)) if 'p' in q.lower()]
    except Exception as e:
        print(f"Details error: {e}")
    
    return details

async def get_episodes(episodes_url, session):
    html = await fetch_html(episodes_url, session)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.find('div', class_='entry-content')
    if not content:
        return []
    
    episodes = []
    current_ep = None
    
    for elem in content.find_all(['p', 'div']):
        text = elem.get_text(strip=True)
        
        ep_match = re.match(r'Episode\s*[:]?\s*(\d+)', text, re.I)
        if ep_match:
            current_ep = {'episode': ep_match.group(1).zfill(2), 'qualities': {}}
            episodes.append(current_ep)
            continue
        
        if current_ep:
            for quality in ['480P', '720P', '1080P', '2160P', '360P']:
                if quality in text.upper() and quality not in current_ep['qualities']:
                    current_ep['qualities'][quality] = {'fprs': '', 'mega': '', 'gdflix': '', 'hubcloud': ''}
                    
                    parent = elem if elem.name == 'p' else elem.find_parent('p')
                    if parent:
                        for link in parent.find_all('a', href=True):
                            href = link.get('href', '')
                            
                            if 'fpgo.xyz' in href or 'filepress' in href:
                                current_ep['qualities'][quality]['fprs'] = href
                            elif 'mega' in href or 'redirect.php' in href:
                                current_ep['qualities'][quality]['mega'] = href
                            elif 'gdflix' in href:
                                current_ep['qualities'][quality]['gdflix'] = href
                            elif 'hubcloud' in href:
                                current_ep['qualities'][quality]['hubcloud'] = href
    
    if not episodes:
        all_links = content.find_all('a', href=True)
        ep_num = None
        
        for link in all_links:
            parent_text = link.parent.get_text() if link.parent else ''
            ep_in_text = re.search(r'Episode\s*[:]?\s*(\d+)', parent_text, re.I)
            
            if ep_in_text:
                ep_num = ep_in_text.group(1).zfill(2)
                if not any(ep['episode'] == ep_num for ep in episodes):
                    episodes.append({'episode': ep_num, 'qualities': {}})
            
            if ep_num:
                ep_obj = next((ep for ep in episodes if ep['episode'] == ep_num), None)
                if ep_obj:
                    href = link.get('href', '')
                    for quality in ['480P', '720P', '1080P', '2160P', '360P']:
                        if quality in parent_text.upper():
                            if quality not in ep_obj['qualities']:
                                ep_obj['qualities'][quality] = {'fprs': '', 'mega': '', 'gdflix': '', 'hubcloud': ''}
                            
                            if 'fpgo.xyz' in href or 'filepress' in href:
                                ep_obj['qualities'][quality]['fprs'] = href
                            elif 'mega' in href or 'redirect.php' in href:
                                ep_obj['qualities'][quality]['mega'] = href
                            elif 'gdflix' in href:
                                ep_obj['qualities'][quality]['gdflix'] = href
                            elif 'hubcloud' in href:
                                ep_obj['qualities'][quality]['hubcloud'] = href
    
    return episodes

async def get_filepress_link(filepress_url, session):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        async with session.get(filepress_url, headers=headers, timeout=30) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                for a in soup.find_all('a', href=True):
                    if 'download' in a.get_text(strip=True).lower():
                        href = a.get('href')
                        if href and href.startswith('http'):
                            return href
                
                for script in soup.find_all('script'):
                    if script.string:
                        url_match = re.search(r'["\'](https?://[^"\']+\.mkv)["\']', script.string)
                        if url_match:
                            return url_match.group(1)
                        
                        data_match = re.search(r'["\'"]downloadUrl["\'"]\s*:\s*["\'"]([^"\']+)["\'"]', script.string)
                        if data_match:
                            return data_match.group(1)
        
        return filepress_url
    except Exception as e:
        print(f"Filepress error: {e}")
        return filepress_url

# ==================== DOWNLOAD WITH PROGRESS ====================
async def download_with_progress(url, filepath, session, status_msg, ep_num):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"}
    
    try:
        async with session.get(url, headers=headers, timeout=600) as resp:
            if resp.status != 200:
                return False
            
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()
            last_update = 0
            
            async with aiofiles.open(filepath, 'wb') as f:
                async for chunk in resp.content.iter_chunked(8192):
                    await f.write(chunk)
                    downloaded += len(chunk)
                    
                    current_time = time.time()
                    if current_time - last_update >= 3 and total_size > 0:
                        elapsed = current_time - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        percentage = (downloaded / total_size) * 100
                        eta = (total_size - downloaded) / speed if speed > 0 else 0
                        
                        progress_bar = create_progress_bar(percentage)
                        
                        try:
                            await status_msg.edit_text(
                                f"<b>📥 Downloading Episode {ep_num}</b>\n\n"
                                f"<code>{progress_bar}</code>\n"
                                f"<b>Progress:</b> {percentage:.1f}%\n"
                                f"<b>Downloaded:</b> {format_size(downloaded)} / {format_size(total_size)}\n"
                                f"<b>Speed:</b> {format_size(speed)}/s\n"
                                f"<b>ETA:</b> {format_time(eta)}"
                            )
                        except:
                            pass
                        
                        last_update = current_time
            
            return True
    except Exception as e:
        print(f"Download error: {e}")
        return False

# ==================== COMMANDS ====================
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        f"<b>👋 Welcome {message.from_user.first_name}!</b>\n\n"
        f"<i>🎌 Official Anime Downloader by @KENSHIN_ANIME</i>\n\n"
        f"<b>✨ Features:</b>\n"
        f"• 🔍 Search from animedubhindi.me\n"
        f"• 📥 Download with real-time progress\n"
        f"• 🎬 Multiple qualities (360p-2160p)\n"
        f"• 🖼️ Custom thumbnails & captions\n\n"
        f"<b>📌 Commands:</b>\n"
        f"<code>/start</code> - Start bot\n"
        f"<code>/help</code> - Show help\n"
        f"<code>/set_caption</code> - Custom caption\n\n"
        f"<b>🎯 Just send anime name to search!</b>\n\n"
        f"<b>🚀 Join:</b> @KENSHIN_ANIME",
        disable_web_page_preview=True
    )

@app.on_message(filters.command("help"))
async def help_cmd(client, message):
    await message.reply_text(
        "<b>📖 Help Guide</b>\n\n"
        "<b>🔍 Search:</b>\n"
        "Just type anime name like:\n"
        "• <code>jjk season 3</code>\n"
        "• <code>demon slayer</code>\n\n"
        "<b>📝 Caption Variables:</b>\n"
        "• <code>{anime_name}</code> - Title\n"
        "• <code>{ep}</code> - Episode\n"
        "• <code>{season}</code> - Season\n"
        "• <code>{quality}</code> - Quality\n\n"
        "<b>🖼️ Thumbnail:</b>\n"
        "Send any image to set thumbnail!\n\n"
        "<b>⚠️ Note:</b> Videos auto-delete after sending!\n\n"
        "<b>🚀 @KENSHIN_ANIME</b>"
    )

@app.on_message(filters.command("set_caption"))
async def set_caption_cmd(client, message):
    user_id = message.from_user.id
    
    if len(message.command) < 2:
        await message.reply_text(
            f"<b>📝 Current Caption:</b>\n{get_user_caption(user_id)}\n\n"
            f"<b>To set:</b> <code>/set_caption Your caption</code>\n\n"
            f"<b>Variables:</b> <code>{{anime_name}}</code>, <code>{{ep}}</code>, <code>{{season}}</code>, <code>{{quality}}</code>"
        )
        return
    
    user_captions[user_id] = message.text.split(" ", 1)[1]
    await message.reply_text("<b>✅ Caption set!</b>")

@app.on_message(filters.command("reset_caption"))
async def reset_caption_cmd(client, message):
    user_id = message.from_user.id
    if user_id in user_captions:
        del user_captions[user_id]
    await message.reply_text("<b>✅ Caption reset to default!</b>")

@app.on_message(filters.command("reset_thumbnail"))
async def reset_thumb_cmd(client, message):
    user_id = message.from_user.id
    if user_id in user_thumbnails:
        path = user_thumbnails[user_id]
        if os.path.exists(path):
            os.remove(path)
        del user_thumbnails[user_id]
    await message.reply_text("<b>✅ Thumbnail removed!</b>")

@app.on_message(filters.photo)
async def handle_photo(client, message):
    user_id = message.from_user.id
    os.makedirs("thumbs", exist_ok=True)
    path = f"thumbs/{user_id}.jpg"
    await message.download(file_name=path)
    user_thumbnails[user_id] = path
    await message.reply_text("<b>✅ Thumbnail set!</b>")

# ==================== HELPERS ====================
def get_user_caption(uid):
    return user_captions.get(uid, DEFAULT_CAPTION)

def get_user_thumb(uid):
    return user_thumbnails.get(uid, None)

def format_filename(anime, ep, season, quality):
    clean_anime = re.sub(r'[^\w\s-]', '', anime).strip()[:30]
    return f"[@KENSHIN_ANIME]_{clean_anime}_EP{ep}_S{season}_{quality}.mkv"

def format_caption(template, anime, ep, season, quality):
    return template.format(anime_name=anime, ep=ep, season=season, quality=quality)

# ==================== MAIN FLOW ====================
@app.on_message(filters.text & ~filters.command(["start", "help", "set_caption", "reset_caption", "reset_thumbnail"]))
async def search_handler(client, message):
    query = message.text.strip()
    user_id = message.from_user.id
    
    if len(query) < 2:
        await message.reply_text("<b>⚠️ Enter at least 2 characters!</b>")
        return
    
    msg = await message.reply_text(f"<b>🔍 Searching:</b> <code>{query}</code>")
    
    async with aiohttp.ClientSession() as session:
        results = await search_anime(query, session)
    
    if not results:
        await msg.edit_text(f"<b>❌ No results for:</b> <code>{query}</code>")
        return
    
    user_data[user_id] = {'search_results': results, 'step': 'selecting'}
    
    buttons = []
    for i, r in enumerate(results[:10], 1):
        title = r['title'][:45] + "..." if len(r['title']) > 45 else r['title']
        buttons.append([InlineKeyboardButton(f"{i}. {title}", callback_data=f"anime_{i}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    
    await msg.edit_text(
        f"<b>🎯 Found {len(results)} results</b>\n<i>Select anime:</i>",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query()
async def callback_handler(client, callback):
    user_id = callback.from_user.id
    data = callback.data
    
    try:
        if data == "cancel":
            if user_id in user_data:
                del user_data[user_id]
            await callback.message.edit_text("<b>❌ Cancelled!</b>")
            return
        
        if data.startswith("anime_"):
            idx = int(data.split("_")[1]) - 1
            
            if user_id not in user_data or 'search_results' not in user_data[user_id]:
                await callback.answer("Session expired! Search again.", show_alert=True)
                return
            
            results = user_data[user_id]['search_results']
            if idx >= len(results):
                await callback.answer("Invalid!", show_alert=True)
                return
            
            selected = results[idx]
            await callback.message.edit_text(f"<b>🔄 Fetching:</b> <code>{selected['title']}</code>")
            
            async with aiohttp.ClientSession() as session:
                details = await get_anime_details(selected['link'], session)
            
            if not details:
                await callback.message.edit_text("<b>❌ Failed to fetch details!</b>")
                return
            
            user_data[user_id].update({
                'selected_anime': selected,
                'anime_details': details,
                'step': 'episodes'
            })
            
            async with aiohttp.ClientSession() as session:
                episodes = await get_episodes(details['episodes_link'], session)
                user_data[user_id]['episodes'] = episodes
            
            total_eps = len(episodes) or details.get('total_episodes', 0)
            
            if total_eps == 0:
                await callback.message.edit_text("<b>❌ No episodes found!</b>")
                return
            
            buttons = []
            row = []
            for i in range(1, min(total_eps + 1, 25)):
                row.append(InlineKeyboardButton(f"EP{i}", callback_data=f"ep_{str(i).zfill(2)}"))
                if len(row) == 5:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            
            buttons.append([InlineKeyboardButton("📥 ALL EPISODES", callback_data="ep_all")])
            buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_search")])
            
            await callback.message.edit_text(
                f"<b>🎌 {details['title']}</b>\n"
                f"📊 <b>Episodes:</b> {total_eps}\n"
                f"🎥 <b>Qualities:</b> {', '.join(details.get('qualities', ['480p', '720p', '1080p']))}\n\n"
                f"<i>Select episode(s):</i>",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        elif data == "back_search":
            if user_id not in user_data or 'search_results' not in user_data[user_id]:
                await callback.answer("Session expired!", show_alert=True)
                return
            
            results = user_data[user_id]['search_results']
            buttons = []
            for i, r in enumerate(results[:10], 1):
                title = r['title'][:45] + "..." if len(r['title']) > 45 else r['title']
                buttons.append([InlineKeyboardButton(f"{i}. {title}", callback_data=f"anime_{i}")])
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
            
            await callback.message.edit_text(
                f"<b>🎯 Search Results</b>\n<i>Select anime:</i>",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        elif data.startswith("ep_"):
            ep_sel = data.split("_")[1]
            
            if user_id not in user_data:
                await callback.answer("Session expired!", show_alert=True)
                return
            
            user_data[user_id]['selected_episodes'] = ep_sel
            user_data[user_id]['step'] = 'quality'
            
            qualities = ['360P', '480P', '720P', '1080P', '2160P']
            buttons = []
            row = []
            for q in qualities:
                row.append(InlineKeyboardButton(q, callback_data=f"qual_{q}"))
                if len(row) == 3:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_eps")])
            
            await callback.message.edit_text(
                f"<b>🎥 Selected:</b> {ep_sel.upper() if ep_sel == 'all' else f'EP {ep_sel}'}\n"
                f"<i>Select quality:</i>",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        elif data == "back_eps":
            if user_id not in user_data or 'anime_details' not in user_data[user_id]:
                await callback.answer("Session expired!", show_alert=True)
                return
            
            details = user_data[user_id]['anime_details']
            episodes = user_data[user_id].get('episodes', [])
            total_eps = len(episodes) or details.get('total_episodes', 0)
            
            buttons = []
            row = []
            for i in range(1, min(total_eps + 1, 25)):
                row.append(InlineKeyboardButton(f"EP{i}", callback_data=f"ep_{str(i).zfill(2)}"))
                if len(row) == 5:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            
            buttons.append([InlineKeyboardButton("📥 ALL EPISODES", callback_data="ep_all")])
            buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_search")])
            
            await callback.message.edit_text(
                f"<b>🎌 {details['title']}</b>\n"
                f"📊 <b>Episodes:</b> {total_eps}\n\n"
                f"<i>Select episode(s):</i>",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        elif data.startswith("qual_"):
            quality = data.split("_")[1]
            
            if user_id not in user_data:
                await callback.answer("Session expired!", show_alert=True)
                return
            
            user_data[user_id]['selected_quality'] = quality
            
            anime = user_data[user_id]['selected_anime']
            episodes = user_data[user_id].get('episodes', [])
            ep_sel = user_data[user_id]['selected_episodes']
            details = user_data[user_id]['anime_details']
            
            season_match = re.search(r'Season\s*(\d+)', anime['title'], re.I)
            season = season_match.group(1) if season_match else "1"
            
            await callback.message.edit_text(
                f"<b>🔄 Processing...</b>\n"
                f"🎌 <b>Anime:</b> {anime['title'][:40]}...\n"
                f"📺 <b>Episode(s):</b> {ep_sel.upper() if ep_sel == 'all' else ep_sel}\n"
                f"🎥 <b>Quality:</b> {quality}\n\n"
                f"<i>Fetching links...</i>"
            )
            
            if not episodes:
                async with aiohttp.ClientSession() as session:
                    episodes = await get_episodes(details['episodes_link'], session)
                    user_data[user_id]['episodes'] = episodes
            
            if not episodes:
                await callback.message.edit_text("<b>❌ No episodes found!</b>")
                return
            
            if ep_sel == "all":
                to_download = episodes
            else:
                to_download = [ep for ep in episodes if ep['episode'] == ep_sel]
            
            if not to_download:
                await callback.message.edit_text("<b>❌ Episode not found!</b>")
                return
            
            for episode in to_download:
                ep_num = episode['episode']
                
                q = quality
                if q not in episode['qualities']:
                    available = list(episode['qualities'].keys())
                    if available:
                        q = available[0]
                    else:
                        await callback.message.reply_text(f"<b>⚠️ EP{ep_num}:</b> Quality not available, skipping...")
                        continue
                
                ep_data = episode['qualities'][q]
                link = ep_data.get('fprs', '') or ep_data.get('gdflix', '') or ep_data.get('mega', '') or ep_data.get('hubcloud', '')
                
                if not link:
                    await callback.message.reply_text(f"<b>❌ EP{ep_num}:</b> No download link!")
                    continue
                
                status_msg = await callback.message.reply_text(f"<b>🔄 EP{ep_num}:</b> Getting download link...")
                
                async with aiohttp.ClientSession() as session:
                    direct_link = await get_filepress_link(link, session)
                
                if not direct_link:
                    await status_msg.edit_text(f"<b>❌ EP{ep_num}:</b> Failed to get link!")
                    continue
                
                os.makedirs("downloads", exist_ok=True)
                filename = format_filename(anime['title'], ep_num, season, q)
                filepath = f"downloads/{filename}"
                caption = format_caption(get_user_caption(user_id), anime['title'], ep_num, season, q)
                thumb = get_user_thumb(user_id)
                
                await status_msg.edit_text(f"<b>📥 EP{ep_num}:</b> Starting download...")
                
                async with aiohttp.ClientSession() as session:
                    success = await download_with_progress(direct_link, filepath, session, status_msg, ep_num)
                
                if not success or not os.path.exists(filepath):
                    await status_msg.edit_text(f"<b>❌ EP{ep_num}:</b> Download failed!")
                    continue
                
                file_size = os.path.getsize(filepath)
                
                await status_msg.edit_text(
                    f"<b>📤 EP{ep_num}:</b> Uploading to Telegram...\n"
                    f"📦 Size: {format_size(file_size)}"
                )
                
                try:
                    await client.send_video(
                        chat_id=callback.message.chat.id,
                        video=filepath,
                        caption=caption,
                        thumb=thumb if thumb and os.path.exists(thumb) else None,
                        supports_streaming=True,
                        width=1920,
                        height=1080
                    )
                    await status_msg.delete()
                except Exception as e:
                    print(f"Upload error: {e}")
                    await status_msg.edit_text(f"<b>❌ EP{ep_num}:</b> Upload failed!")
                
                finally:
                    if os.path.exists(filepath):
                        os.remove(filepath)
            
            await callback.message.reply_text(
                "<b>✅ All episodes processed!</b>\n\n"
                "<i>Send anime name to search again!</i>"
            )
            
            if user_id in user_data:
                del user_data[user_id]
                
    except Exception as e:
        print(f"Callback error: {e}")
        await callback.answer(f"Error: {str(e)[:100]}", show_alert=True)

# ==================== RUN ====================
if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("thumbs", exist_ok=True)
    
    print("=" * 50)
    print("🎌 AnimeDubHindi Bot - @KENSHIN_ANIME")
    print("=" * 50)
    
    app.run()
