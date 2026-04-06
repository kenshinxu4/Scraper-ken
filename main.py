import os
import json
import asyncio
from telethon import TelegramClient, events, Button

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

DB_FILE = "database.json"

bot = TelegramClient('kenshin_bulk_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- DB FUNCTIONS ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

anime_db = load_db()

# --- COMMANDS ---

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("🔥 **Kenshin Bot v6 (Bulk Enabled)**\n\nCommands:\n/add_ani - Single Add\n/bulk - Bulk Upload Guide\n/list - View DB")

@bot.on(events.NewMessage(pattern='/bulk'))
async def bulk_guide(event):
    if event.sender_id != ADMIN_ID: return
    guide = (
        "📊 **Bulk Upload Guide**\n\n"
        "1. Ek `.txt` file banayein.\n"
        "2. Format: `Naam | Photo_URL | Link | Synopsis` (Har line par naya anime)\n"
        "3. Wo file bot ko send karein.\n\n"
        "⚠️ **Note:** Photo_URL direct link hona chahiye (e.g. .jpg ya .png)"
    )
    await event.reply(guide)

# --- BULK FILE HANDLER ---
@bot.on(events.NewMessage)
async def handle_bulk_file(event):
    if event.sender_id != ADMIN_ID or not event.document: return
    
    if event.document.mime_type == "text/plain":
        file = await event.download_media(bytes)
        content = file.decode('utf-8').split('\n')
        
        count = 0
        for line in content:
            if "|" in line:
                try:
                    parts = line.split('|')
                    name = parts[0].strip().lower()
                    img = parts[1].strip()
                    link = parts[2].strip()
                    desc = parts[3].strip()
                    
                    anime_db[name] = {
                        "img": img,
                        "link": link,
                        "desc": desc
                    }
                    count += 1
                except:
                    continue
        
        save_db(anime_db)
        await event.reply(f"✅ Bulk Upload Success! **{count}** animes added to DB.")

# --- USER SEARCH ---
@bot.on(events.NewMessage)
async def search(event):
    if event.text.startswith('/'): return
    
    query = event.text.strip().lower()
    for name, data in anime_db.items():
        if query == name or (len(query) > 3 and query in name):
            buttons = [[Button.url("▪︎ DOWNLOAD / WATCH ▪︎", data['link'])]]
            
            # Agar image URL hai toh send_file, warna simple message
            try:
                await bot.send_file(
                    event.chat_id, 
                    data['img'], 
                    caption=f"🎬 **{name.upper()}**\n\n📖 **Synopsis:**\n{data['desc']}", 
                    buttons=buttons
                )
            except:
                await event.reply(f"🎬 **{name.upper()}**\n\n{data['desc']}", buttons=buttons)
            return

print("✅ Bulk Bot is Running...")
bot.run_until_disconnected()
