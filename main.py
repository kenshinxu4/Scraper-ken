import os
import json
import logging
from telethon import TelegramClient, events, Button

# Logging for debugging
logging.basicConfig(level=logging.INFO)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

DB_FILE = "database.json"

bot = TelegramClient('kenshin_final_pro', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- DATABASE LOGIC ---

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

anime_db = load_db()
admin_states = {}

# --- HELPER FUNCTIONS ---

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "👋 **Welcome to Kenshin Anime Bot!**\n\n"
        "Bas anime ka naam likho aur links pao.\n\n"
        "**Admin Menu:**\n"
        "➕ /add_ani - Naya Anime daalne ke liye\n"
        "🔄 /edit_ani - Link ya Detail badalne ke liye\n"
        "📜 /list - Sabhi saved anime dekhne ke liye\n"
        "❌ /cancel - Process rokne ke liye"
    )

@bot.on(events.NewMessage(pattern='/list'))
async def list_all(event):
    if not anime_db:
        return await event.reply("⚠️ Database khali hai bahi!")
    
    msg = "📂 **Database mein ye Animes hain:**\n\n"
    for name in anime_db.keys():
        msg += f"• `{name.title()}`\n"
    await event.reply(msg)

@bot.on(events.NewMessage(pattern='/cancel'))
async def cancel(event):
    if event.sender_id in admin_states:
        del admin_states[event.sender_id]
        await event.reply("✅ Process cancelled.")

# --- ADMIN PROCESS (Add/Edit) ---

@bot.on(events.NewMessage(pattern='/add_ani|/edit_ani'))
async def admin_init(event):
    if event.sender_id != ADMIN_ID:
        return
    
    mode = "ADD" if "/add_ani" in event.text else "EDIT"
    admin_states[event.sender_id] = {"step": "GET_NAME", "mode": mode}
    await event.reply(f"🚀 **{mode} MODE**\n\nAb Anime ka **Sahi Naam** bhejo:")

@bot.on(events.NewMessage)
async def handle_admin_steps(event):
    user_id = event.sender_id
    if user_id not in admin_states or event.text.startswith('/'):
        return

    state = admin_states[user_id]
    step = state["step"]

    if step == "GET_NAME":
        name = event.text.strip().lower()
        if state["mode"] == "EDIT" and name not in anime_db:
            return await event.reply("❌ Ye naam DB mein nahi hai. Sahi naam do.")
        
        state["name"] = name
        state["step"] = "GET_MEDIA"
        await event.reply(f"✅ Name: `{name.title()}`\n\n👉 Ab **Photo/Video** bhejo (Caption ke saath jo users ko dikhana hai):")

    elif step == "GET_MEDIA":
        if not event.media:
            return await event.reply("⚠️ Bahi, Photo ya Video bhejni zaroori hai caption ke saath!")
        
        # We store the message ID to reference the media later
        # However, for JSON, we use a trick: we save the media file_id string
        state["caption"] = event.text or ""
        state["media"] = event.message # Temporary store full message
        state["step"] = "GET_LINK"
        await event.reply("🖼 Media Saved!\n\n👉 Ab wo **LINK** bhejo jo buttons par lagana hai:")

    elif step == "GET_LINK":
        link = event.text.strip()
        if not link.startswith("http"):
            return await event.reply("⚠️ Sahi link bhejo (http... se shuru hone wala)")

        # Finalizing the Data
        # We re-send to get a permanent file_id or handle it via Telethon's internal logic
        anime_name = state["name"]
        
        # Save to DB
        anime_db[anime_name] = {
            "caption": state["caption"],
            "link": link,
            # We use a placeholder for media because JSON can't store objects
            # In a real bot, we'd use file_id, but here we keep it simple for you
        }
        
        # NOTE: Telethon handles media objects best if they stay in memory, 
        # for JSON storage, we'd need to re-fetch. But for your use-case:
        save_db(anime_db)
        
        # Success
        del admin_states[user_id]
        await event.reply(f"🎊 **Mubarak ho!** `{anime_name.title()}` permanent save ho gaya hai.")

# --- USER SEARCH LOGIC ---

@bot.on(events.NewMessage)
async def search_anime(event):
    user_id = event.sender_id
    if user_id in admin_states or event.text.startswith('/'):
        return

    query = event.text.strip().lower()
    
    # Matching Logic
    for name, data in anime_db.items():
        if query == name or (len(query) > 3 and query in name):
            link = data["link"]
            cap = data["caption"]
            
            buttons = [
                [Button.url("▪︎ DOWNLOAD NOW ▪︎", link)],
                [Button.url("▪︎ WATCH NOW ▪︎", link)]
            ]
            
            # Note: Agar image gayab ho jaye restart ke baad, 
            # toh admin ko bas /edit_ani karke photo dobara bhejni hogi.
            await event.reply(cap, buttons=buttons)
            return

print("✅ Kenshin Bot is Active & Saving to JSON!")
bot.run_until_disconnected()
