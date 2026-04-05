from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatType
import os
import re
import asyncio
from datetime import datetime
import unicodedata

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
    
    # Replace common fancy characters with normal ones
    fancy_to_normal = {
        'ᴀ': 'a', 'ʙ': 'b', 'ᴄ': 'c', 'ᴅ': 'd', 'ᴇ': 'e', 'ғ': 'f', 'ɢ': 'g',
        'ʜ': 'h', 'ɪ': 'i', 'ᴊ': 'j', 'ᴋ': 'k', 'ʟ': 'l', 'ᴍ': 'm', 'ɴ': 'n',
        'ᴏ': 'o', 'ᴘ': 'p', 'ǫ': 'q', 'ʀ': 'r', 's': 's', 'ᴛ': 't', 'ᴜ': 'u',
        'ᴠ': 'v', 'ᴡ': 'w', 'x': 'x', 'ʏ': 'y', 'ᴢ': 'z',
        'ᴀ': 'A', 'ʙ': 'B', 'ᴄ': 'C', 'ᴅ': 'D', 'ᴇ': 'E', 'ғ': 'F', 'ɢ': 'G',
        'ʜ': 'H', 'ɪ': 'I', 'ᴊ': 'J', 'ᴋ': 'K', 'ʟ': 'L', 'ᴍ': 'M', 'ɴ': 'N',
        'ᴏ': 'O', 'ᴘ': 'P', 'ǫ': 'Q', 'ʀ': 'R', 's': 'S', 'ᴛ': 'T', 'ᴜ': 'U',
        'ᴠ': 'V', 'ᴡ': 'W', 'x': 'X', 'ʏ': 'Y', 'ᴢ': 'Z',
        '【': '[', '】': ']', '「': '<', '」': '>', '（': '(', '）': ')',
        '：': ':', '，': ',', '！': '!', '？': '?', '。': '.'
    }
    
    normalized = ""
    for char in text.lower():
        normalized += fancy_to_normal.get(char, char)
    
    return normalized

async def update_cache():
    """Fetch ALL messages (not just pinned) from source channel"""
    global pinned_cache, last_cache_update
    
    try:
        messages = []
        # Get last 200 messages (adjust if needed)
        async for message in app.get_chat_history(SOURCE_CHANNEL, limit=200):
            # Check if message has media (photo/video/doc) - anime posts usually have these
            if message.photo or message.video or message.document:
                messages.append(message)
        
        pinned_cache = messages
        last_cache_update = datetime.now()
        print(f"✅ Cache updated: {len(messages)} messages with media")
        return True
    except Exception as e:
        print(f"❌ Cache update failed: {e}")
        return False

def search_messages(query: str):
    """Smart search with multiple matching strategies"""
    if not pinned_cache:
        return []
    
    query_clean = normalize_text(query).lower().strip()
    query_words = query_clean.split()
    
    results = []
    scores = {}  # Message ID -> match score
    
    for msg in pinned_cache:
        # Get text from caption or text
        raw_text = (msg.caption or msg.text or "")
        search_text = normalize_text(raw_text).lower()
        
        if not search_text:
            continue
        
        score = 0
        
        # 1. Exact match (highest priority)
        if query_clean in search_text:
            score += 100
        
        # 2. All words match (partial)
        if all(word in search_text for word in query_words):
            score += 50
        
        # 3. Any word matches
        matching_words = sum(1 for word in query_words if word in search_text)
        score += matching_words * 10
        
        # 4. Check for common anime patterns in your format
        # Extract anime name from your specific format
        anime_name_match = re.search(r'anime\s*[:：]\s*([^\n【「]+)', search_text, re.IGNORECASE)
        if anime_name_match:
            anime_name = anime_name_match.group(1).strip().lower()
            if any(word in anime_name for word in query_words):
                score += 30
        
        # 5. Season/Episode number matching
        season_match = re.search(r'season[:\s]*(\d+)', search_text, re.IGNORECASE)
        if season_match and any(char.isdigit() for char in query_clean):
            query_num = re.search(r'(\d+)', query_clean)
            if query_num and query_num.group(1) == season_match.group(1):
                score += 25
        
        if score > 0:
            scores[msg.id] = score
            results.append(msg)
    
    # Sort by score (highest first) and return top 5
    results.sort(key=lambda x: scores.get(x.id, 0), reverse=True)
    return results[:5]

def create_result_text(msg):
    """Format message - preserve original caption but clean it"""
    original_text = msg.caption or msg.text or ""
    
    # Try to extract anime name from your format
    lines = original_text.split('\n')
    
    # Find the title line (usually has "🎬" or "ANIME" or first line)
    title = "Anime Content"
    for line in lines[:3]:  # Check first 3 lines
        if '🎬' in line or 'ᴀɴɪᴍᴇ' in line.lower() or 'anime' in line.lower():
            # Extract text after colon or emoji
            title = re.sub(r'^[🎬ᴀɴɪᴍᴇ\s:【】]+', '', line, flags=re.IGNORECASE).strip()
            if title:
                break
    
    if not title or title == "Anime Content":
        title = lines[0][:50] if lines else "Anime Content"
    
    # Create clean format
    result = f"**{title}**\n\n"
    result += "▪️ DOWNLOAD NOW\n"
    result += "▪️ WATCH NOW"
    
    return result

def create_inline_buttons(msg):
    """Create buttons with message link"""
    # Try to get the best possible link
    try:
        if msg.chat.username:
            link = f"https://t.me/{msg.chat.username}/{msg.id}"
        else:
            # For private channels
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
    await message.reply(
        f"👋 **Hey {message.from_user.mention}!**\n\n"
        f"🔍 **Send me anime name like:**\n"
        f"• `solo leveling`\n"
        f"• `jjk` or `jujutsu kaisen`\n"
        f"• `attack on titan`\n"
        f"• `demon slayer`\n\n"
        f"⚡ I search through all media posts in my channel!",
        quote=True,
        parse_mode="markdown"
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
    """Debug: Show what messages are in cache"""
    if not pinned_cache:
        await message.reply("❌ Cache empty!", quote=True)
        return
    
    debug_text = f"📊 **Cache Status:**\nTotal: {len(pinned_cache)} messages\n\n"
    debug_text += "**Recent 5 messages:**\n\n"
    
    for i, msg in enumerate(pinned_cache[:5], 1):
        text = (msg.caption or msg.text or "No text")[:50]
        debug_text += f"{i}. {text}...\n"
    
    await message.reply(debug_text, quote=True, parse_mode="markdown")

@app.on_message(filters.text & ~filters.command(["start", "refresh", "debug"]))
async def search_handler(client, message: Message):
    query = message.text.strip()
    
    if len(query) < 2:
        await message.reply("⚠️ Query too short! Send at least 2 characters.", quote=True)
        return
    
    status = await message.reply("🔍 Searching...", quote=True)
    
    # Update cache if empty or old (10 mins)
    if not pinned_cache or (last_cache_update and (datetime.now() - last_cache_update).seconds > 600):
        await update_cache()
    
    results = search_messages(query)
    
    if not results:
        # Try one more time with cache refresh
        await update_cache()
        results = search_messages(query)
        
        if not results:
            await status.edit(
                "😔 **No results found!**\n\n"
                f"🔍 Searched for: `{query}`\n"
                f"📁 Total posts in cache: {len(pinned_cache)}\n\n"
                f"💡 **Tips:**\n"
                f"• Try shorter keywords (e.g., 'solo' instead of 'solo leveling')\n"
                f"• Check spelling\n"
                f"• Use /debug to see cached messages",
                parse_mode="markdown"
            )
            return
    
    await status.delete()
    
    for i, msg in enumerate(results, 1):
        try:
            result_text = create_result_text(msg)
            buttons = create_inline_buttons(msg)
            
            # Send with media
            if msg.photo:
                await message.reply_photo(
                    photo=msg.photo.file_id,
                    caption=result_text,
                    reply_markup=buttons,
                    parse_mode="markdown",
                    quote=(i == 1)
                )
            elif msg.video:
                await message.reply_video(
                    video=msg.video.file_id,
                    caption=result_text,
                    reply_markup=buttons,
                    parse_mode="markdown",
                    quote=(i == 1)
                )
            elif msg.document:
                await message.reply_document(
                    document=msg.document.file_id,
                    caption=result_text,
                    reply_markup=buttons,
                    parse_mode="markdown",
                    quote=(i == 1)
                )
            else:
                await message.reply(
                    result_text,
                    reply_markup=buttons,
                    parse_mode="markdown",
                    quote=(i == 1)
                )
            
            await asyncio.sleep(0.3)
            
        except Exception as e:
            print(f"Error sending result {i}: {e}")
            continue
    
    if len(results) > 0:
        await message.reply(
            f"✅ **Found {len(results)} result(s)**\n\n"
            f"Click buttons above to access!",
            quote=True,
            parse_mode="markdown"
        )

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message: Message):
    await message.reply(
        f"📊 **Bot Stats**\n\n"
        f"📌 Cached Posts: `{len(pinned_cache)}`\n"
        f"🕐 Last Update: `{last_cache_update.strftime('%H:%M:%S') if last_cache_update else 'Never'}`\n"
        f"👤 Admin: `{ADMIN_ID}`\n"
        f"📢 Source: `{SOURCE_CHANNEL}`",
        quote=True,
        parse_mode="markdown"
    )

async def main():
    await app.start()
    print("🤖 Bot started!")
    
    # Initial cache load
    await update_cache()
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
