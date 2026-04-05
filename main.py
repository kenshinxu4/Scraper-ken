from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatType
import os
import re
import asyncio
from datetime import datetime

# ========== CONFIG ==========
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL")  # e.g., -1001234567890 or @channelusername
# ============================

app = Client(
    "anime_search_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# Cache for pinned messages
pinned_cache = []
last_cache_update = None

async def update_cache():
    """Fetch and cache pinned messages from source channel"""
    global pinned_cache, last_cache_update
    
    try:
        messages = []
        async for message in app.get_chat_history(SOURCE_CHANNEL, limit=100):
            if message.pinned:
                messages.append(message)
        
        pinned_cache = messages
        last_cache_update = datetime.now()
        print(f"Cache updated: {len(messages)} pinned messages")
        return True
    except Exception as e:
        print(f"Cache update failed: {e}")
        return False

def search_messages(query: str):
    """Search cached messages for query"""
    if not pinned_cache:
        return []
    
    query_lower = query.lower()
    results = []
    
    for msg in pinned_cache:
        text = (msg.caption or msg.text or "").lower()
        if query_lower in text:
            results.append(msg)
    
    return results[:10]  # Max 10 results

def create_result_text(msg):
    """Format message text for reply"""
    text = msg.caption or msg.text or "No caption"
    
    # Clean up text - remove existing buttons/links if needed
    lines = text.split('\n')
    clean_lines = []
    
    for line in lines:
        # Skip existing button lines or URLs you don't want
        if not any(x in line.lower() for x in ['t.me/', 'http', 'download', 'watch']):
            clean_lines.append(line)
    
    title = clean_lines[0] if clean_lines else "Anime Content"
    
    return f"{title}\n\n▪️ DOWNLOAD NOW\n▪️ WATCH NOW"

def create_inline_buttons(msg):
    """Create inline buttons with message link"""
    # Get the message link
    if msg.chat.username:
        link = f"https://t.me/{msg.chat.username}/{msg.id}"
    else:
        # For private channels, you need to use the channel ID format
        # This requires the channel to have a public invite link or username
        link = f"https://t.me/c/{str(msg.chat.id).replace('-100', '')}/{msg.id}"
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 DOWNLOAD NOW", url=link),
            InlineKeyboardButton("▶️ WATCH NOW", url=link)
        ]
    ])

@app.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    await message.reply(
        f"👋 Hey {message.from_user.mention}!\n\n"
        f"🔍 Send me anime name like:\n"
        f"• `jjk season 3`\n"
        f"• `demon slayer`\n"
        f"• `attack on titan`\n\n"
        f"I'll search my channel's pinned posts!",
        quote=True
    )

@app.on_message(filters.command("refresh") & filters.user(ADMIN_ID))
async def refresh_cache(client, message: Message):
    """Admin command to refresh cache"""
    status = await message.reply("🔄 Refreshing cache...")
    
    if await update_cache():
        await status.edit(f"✅ Cache updated!\n📌 Found {len(pinned_cache)} pinned messages")
    else:
        await status.edit("❌ Failed to update cache")

@app.on_message(filters.text & ~filters.command(["start", "refresh"]))
async def search_handler(client, message: Message):
    """Handle search queries"""
    query = message.text.strip()
    
    if len(query) < 2:
        await message.reply("⚠️ Query too short! Send at least 2 characters.", quote=True)
        return
    
    # Show searching status
    status = await message.reply("🔍 Searching in pinned messages...", quote=True)
    
    # Update cache if empty or old (older than 30 mins)
    if not pinned_cache or (last_cache_update and (datetime.now() - last_cache_update).seconds > 1800):
        await update_cache()
    
    results = search_messages(query)
    
    if not results:
        await status.edit("😔 No results found!\n\nTry different keywords or check /start")
        return
    
    # Delete status message
    await status.delete()
    
    # Send results
    for i, msg in enumerate(results, 1):
        try:
            result_text = create_result_text(msg)
            buttons = create_inline_buttons(msg)
            
            # If message has photo/video/document with thumbnail
            if msg.photo:
                await message.reply_photo(
                    photo=msg.photo.file_id,
                    caption=result_text,
                    reply_markup=buttons,
                    quote=True if i == 1 else False
                )
            elif msg.video and msg.video.thumbs:
                await message.reply_video(
                    video=msg.video.file_id,
                    caption=result_text,
                    reply_markup=buttons,
                    quote=True if i == 1 else False
                )
            elif msg.document and msg.document.thumbs:
                await message.reply_document(
                    document=msg.document.file_id,
                    caption=result_text,
                    reply_markup=buttons,
                    quote=True if i == 1 else False
                )
            else:
                # Text only
                await message.reply(
                    result_text,
                    reply_markup=buttons,
                    quote=True if i == 1 else False,
                    disable_web_page_preview=True
                )
            
            # Small delay to avoid flood
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"Error sending result {i}: {e}")
            continue
    
    await message.reply(
        f"✅ Found {len(results)} result(s)\n\n"
        f"Send another query or click buttons above!",
        quote=True
    )

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message: Message):
    """Bot statistics"""
    await message.reply(
        f"📊 Bot Stats:\n\n"
        f"📌 Cached Messages: {len(pinned_cache)}\n"
        f"🕐 Last Update: {last_cache_update.strftime('%Y-%m-%d %H:%M') if last_cache_update else 'Never'}\n"
        f"👤 Admin: {ADMIN_ID}\n"
        f"📢 Source: {SOURCE_CHANNEL}",
        quote=True
    )

async def main():
    await app.start()
    print("Bot started!")
    
    # Initial cache load
    await update_cache()
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
