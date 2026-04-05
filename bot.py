from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ParseMode
import os
import asyncio
from datetime import datetime

# ========== CONFIG ==========
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL")  # @username or -100xxxx
# ============================

app = Client(
    "anime_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# Store pinned messages
pinned_messages = []

async def load_pinned():
    """Load all pinned messages from channel"""
    global pinned_messages
    try:
        # Get pinned messages
        chat = await app.get_chat(SOURCE_CHANNEL)
        pinned_messages = []
        
        # Get recent messages and filter pinned
        async for msg in app.get_chat_history(SOURCE_CHANNEL, limit=100):
            if msg.pinned:
                pinned_messages.append(msg)
        
        print(f"✅ Loaded {len(pinned_messages)} pinned messages")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def search_anime(query: str):
    """Search in pinned messages"""
    query = query.lower().strip()
    results = []
    
    for msg in pinned_messages:
        text = (msg.caption or msg.text or "").lower()
        
        # Simple contains search
        if query in text:
            results.append(msg)
    
    return results[:5]  # Max 5 results

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(
        "👋 <b>Anime Search Bot</b>\n\n"
        "🔍 Send any anime name\n"
        "Example: <code>solo leveling</code>, <code>jjk</code>, <code>attack on titan</code>\n\n"
        "I'll search pinned messages and resend matching posts!",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("reload") & filters.user(ADMIN_ID))
async def reload(client, message: Message):
    """Admin: Refresh pinned messages cache"""
    status = await message.reply("🔄 Loading pinned messages...")
    
    if await load_pinned():
        await status.edit(f"✅ Loaded {len(pinned_messages)} pinned messages!")
    else:
        await status.edit("❌ Failed! Check bot is admin in channel")

@app.on_message(filters.text & ~filters.command(["start", "reload"]))
async def search(client, message: Message):
    user_query = message.text.strip()
    
    if len(user_query) < 2:
        await message.reply("⚠️ Type at least 2 characters!", quote=True)
        return
    
    # Load if empty
    if not pinned_messages:
        await load_pinned()
    
    # Search
    status = await message.reply(f"🔍 Searching for: <b>{user_query}</b>...", quote=True)
    
    results = search_anime(user_query)
    
    if not results:
        await status.edit(
            f"😔 No results for: <b>{user_query}</b>\n\n"
            f"💡 Try:\n"
            f"• Shorter keywords (e.g., 'solo' instead of 'solo leveling')\n"
            f"• Check spelling\n"
            f"• Use /reload to refresh cache"
        )
        return
    
    # Delete status
    await status.delete()
    
    # Resend matching pinned messages
    for msg in results:
        try:
            # Forward the exact message
            await msg.forward(message.chat.id)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Forward error: {e}")
            # If forward fails, try copy
            try:
                await msg.copy(message.chat.id)
                await asyncio.sleep(0.5)
            except Exception as e2:
                print(f"Copy error: {e2}")
    
    await message.reply(
        f"✅ Found <b>{len(results)}</b> result(s)!\n\n"
        f"Send another anime name to search again.",
        quote=True,
        parse_mode=ParseMode.HTML
    )

async def main():
    await app.start()
    print("🤖 Bot started!")
    
    # Initial load
    await load_pinned()
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
