from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatType, ParseMode  # ParseMode import kiya
import os
import re
import asyncio
from datetime import datetime

# ========== CONFIG ==========
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL")
# ============================

app = Client(
    "anime_search_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

pinned_cache = []
last_cache_update = None

def normalize_text(text):
    """Convert fancy unicode fonts to normal text for searching"""
    if not text:
        return ""
    
    fancy_to_normal = {
        'ᴀ': 'a', 'ʙ': 'b', 'ᴄ': 'c', 'ᴅ': 'd', 'ᴇ': 'e', 'ғ': 'f', 'ɢ': 'g',
        'ʜ': 'h', 'ɪ': 'i', 'ᴊ': 'j', 'ᴋ': 'k', 'ʟ': 'l', 'ᴍ': 'm', 'ɴ': 'n',
        'ᴏ': 'o', 'ᴘ': 'p', 'ǫ': 'q', 'ʀ': 'r', 's': 's', 'ᴛ': 't', 'ᴜ': 'u',
        'ᴠ': 'v', 'ᴡ': 'w', 'x': 'x', 'ʏ': 'y', 'ᴢ': 'z',
        '【': '[', '】': ']', '（': '(', '）': ')', '：': ':', '，': ','
    }
    
    normalized = ""
    for char in text.lower():
        normalized += fancy_to_normal.get(char, char)
    
    return normalized

async def update_cache():
    """Fetch ALL messages with media from source channel"""
    global pinned_cache, last_cache_update
    
    try:
        messages = []
        async for message in app.get_chat_history(SOURCE_CHANNEL, limit=200):
            if message.photo or message.video or message.document:
                messages.append(message)
        
        pinned_cache = messages
        last_cache_update = datetime.now()
        print(f"✅ Cache updated: {len(messages)} messages")
        return True
    except Exception as e:
        print(f"❌ Cache update failed: {e}")
        return False

def search_messages(query: str):
    """Smart search with scoring"""
    if not pinned_cache:
        return []
    
    query_clean = normalize_text(query).lower().strip()
    query_words = query_clean.split()
    
    results = []
    scores = {}
    
    for msg in pinned_cache:
        raw_text = (msg.caption or msg.text or "")
        search_text = normalize_text(raw_text).lower()
        
        if not search_text:
            continue
        
        score = 0
        
        # Exact match
        if query_clean in search_text:
            score += 100
        
        # All words match
        if all(word in search_text for word in query_words):
            score += 50
        
        # Partial word matches
        matching_words = sum(1 for word in query_words if word in search_text)
        score += matching_words * 10
        
        # Extract anime name from format
        anime_match = re.search(r'anime\s*[:：]\s*([^\n【]+)', search_text, re.IGNORECASE)
        if anime_match:
            anime_name = anime_match.group(1).strip().lower()
            if any(word in anime_name for word in query_words):
                score += 30
        
        if score > 0:
            scores[msg.id] = score
            results.append(msg)
    
    results.sort(key=lambda x: scores.get(x.id, 0), reverse=True)
    return results[:5]

def create_result_text(msg):
    """Format message text"""
    original_text = msg.caption or msg.text or ""
    lines = original_text.split('\n')
    
    # Extract title
    title = "Anime Content"
    for line in lines[:3]:
        if '🎬' in line or 'ᴀɴɪᴍᴇ' in line.lower():
            title = re.sub(r'^[🎬ᴀɴɪᴍᴇ\s:【】]+', '', line, flags=re.IGNORECASE).strip()
            if title:
                break
    
    if not title or title == "Anime Content":
        title = lines[0][:50] if lines else "Anime Content"
    
    # Use HTML formatting instead of Markdown
    return f"<b>{title}</b>\n\n▪️ DOWNLOAD NOW\n▪️ WATCH NOW"

def create_inline_buttons(msg):
    """Create buttons with message link"""
    try:
        if msg.chat.username:
            link = f"https://t.me/{msg.chat.username}/{msg.id}"
        else:
            chat_id_str = str(msg.chat.id).replace('-100', '')
            link = f"https://t.me/c/{chat_id_str}/{msg.id}"
    except:
        link = f"https://t.me/c/{str(SOURCE_CHANNEL).replace('-100', '')}/{msg.id}"
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 DOWNLOAD NOW", url=link),
            InlineKeyboardButton("▶️ WATCH NOW", url=link)
        ]
    ])

@app.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    # HTML formatting use kiya instead of markdown
    await message.reply(
        f"👋 <b>Hey {message.from_user.mention}!</b>\n\n"
        f"🔍 <b>Send me anime name like:</b>\n"
        f"• <code>solo leveling</code>\n"
        f"• <code>jjk</code> or <code>jujutsu kaisen</code>\n"
        f"• <code>attack on titan</code>\n"
        f"• <code>demon slayer</code>\n\n"
        f"⚡ I search through all media posts in my channel!",
        quote=True,
        parse_mode=ParseMode.HTML  # YEH SAHI TARIKA
    )

@app.on_message(filters.command("refresh") & filters.user(ADMIN_ID))
async def refresh_cache(client, message: Message):
    status = await message.reply("🔄 Refreshing cache...")
    
    if await update_cache():
        await status.edit(f"✅ Cache updated!\n📌 Found {len(pinned_cache)} media posts")
    else:
        await status.edit("❌ Failed to update cache. Check bot is admin in channel!")

@app.on_message(filters.command("debug") & filters.user(ADMIN_ID))
async def debug_handler(client, message: Message):
    if not pinned_cache:
        await message.reply("❌ Cache empty!", quote=True)
        return
    
    debug_text = f"📊 <b>Cache Status:</b>\nTotal: {len(pinned_cache)} messages\n\n"
    debug_text += "<b>Recent 5 messages:</b>\n\n"
    
    for i, msg in enumerate(pinned_cache[:5], 1):
        text = (msg.caption or msg.text or "No text")[:50]
        debug_text += f"{i}. {text}...\n"
    
    await message.reply(debug_text, quote=True, parse_mode=ParseMode.HTML)

@app.on_message(filters.text & ~filters.command(["start", "refresh", "debug", "stats"]))
async def search_handler(client, message: Message):
    query = message.text.strip()
    
    if len(query) < 2:
        await message.reply("⚠️ Query too short! Send at least 2 characters.", quote=True)
        return
    
    status = await message.reply("🔍 Searching...")
    
    if not pinned_cache or (last_cache_update and (datetime.now() - last_cache_update).seconds > 600):
        await update_cache()
    
    results = search_messages(query)
    
    if not results:
        await update_cache()
        results = search_messages(query)
        
        if not results:
            await status.edit(
                "😔 <b>No results found!</b>\n\n"
                f"🔍 Searched for: <code>{query}</code>\n"
                f"📁 Total posts in cache: {len(pinned_cache)}\n\n"
                f"💡 <b>Tips:</b>\n"
                f"• Try shorter keywords (e.g., 'solo' instead of 'solo leveling')\n"
                f"• Check spelling\n"
                f"• Use /debug to see cached messages",
                parse_mode=ParseMode.HTML
            )
            return
    
    await status.delete()
    
    for i, msg in enumerate(results, 1):
        try:
            result_text = create_result_text(msg)
            buttons = create_inline_buttons(msg)
            
            if msg.photo:
                await message.reply_photo(
                    photo=msg.photo.file_id,
                    caption=result_text,
                    reply_markup=buttons,
                    parse_mode=ParseMode.HTML
                )
            elif msg.video:
                await message.reply_video(
                    video=msg.video.file_id,
                    caption=result_text,
                    reply_markup=buttons,
                    parse_mode=ParseMode.HTML
                )
            elif msg.document:
                await message.reply_document(
                    document=msg.document.file_id,
                    caption=result_text,
                    reply_markup=buttons,
                    parse_mode=ParseMode.HTML
                )
            else:
                await message.reply(
                    result_text,
                    reply_markup=buttons,
                    parse_mode=ParseMode.HTML
                )
            
            await asyncio.sleep(0.3)
            
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    if len(results) > 0:
        await message.reply(
            f"✅ <b>Found {len(results)} result(s)</b>\n\nClick buttons above to access!",
            quote=True,
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message: Message):
    await message.reply(
        f"📊 <b>Bot Stats</b>\n\n"
        f"📌 Cached Posts: <code>{len(pinned_cache)}</code>\n"
        f"🕐 Last Update: <code>{last_cache_update.strftime('%H:%M:%S') if last_cache_update else 'Never'}</code>\n"
        f"👤 Admin: <code>{ADMIN_ID}</code>\n"
        f"📢 Source: <code>{SOURCE_CHANNEL}</code>",
        quote=True,
        parse_mode=ParseMode.HTML
    )

async def main():
    await app.start()
    print("🤖 Bot started!")
    
    await update_cache()
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
