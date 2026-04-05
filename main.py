import os
from telethon import TelegramClient, events, Button

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

bot = TelegramClient('kenshin_media_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# In-Memory Database (Fast & Supports Media Objects)
anime_db = {}  
admin_states = {}

# --- COMMANDS ---

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "👋 **Kenshin Anime Search Bot**\n\n"
        "Anime ka naam likho aur Download link pao!\n\n"
        "**Admin Commands:**\n"
        "➕ /add_ani - Image + Link add karein\n"
        "🔄 /edit_ani - Purana data badlein\n"
        "📜 /list - Sabhi anime dekhein\n"
        "❌ /cancel - Rokne ke liye"
    )

@bot.on(events.NewMessage(pattern='/list'))
async def list_ani(event):
    if not anime_db:
        return await event.reply("⚠️ Database khali hai bahi!")
    msg = "📂 **Available Animes:**\n\n" + "\n".join([f"• `{n.title()}`" for n in anime_db.keys()])
    await event.reply(msg)

@bot.on(events.NewMessage(pattern='/cancel'))
async def cancel(event):
    if event.sender_id in admin_states:
        del admin_states[event.sender_id]
        await event.reply("✅ Cancelled!")

# --- ADMIN FLOW (Image + Caption + Link) ---

@bot.on(events.NewMessage(pattern='/add_ani|/edit_ani'))
async def admin_init(event):
    if event.sender_id != ADMIN_ID: return
    
    mode = "ADD" if "/add_ani" in event.text else "EDIT"
    admin_states[event.sender_id] = {"step": "GET_NAME", "mode": mode}
    await event.reply(f"🚀 **{mode} Mode ON**\n\nAnime ka **Naam** bhejo:")

@bot.on(events.NewMessage)
async def handle_steps(event):
    user_id = event.sender_id
    if user_id not in admin_states or event.text.startswith('/'): return

    state = admin_states[user_id]
    step = state["step"]

    # STEP 1: Get Name
    if step == "GET_NAME":
        name = event.text.strip().lower()
        if state["mode"] == "EDIT" and name not in anime_db:
            return await event.reply("❌ Ye naam database mein nahi hai!")
        state["name"] = name
        state["step"] = "GET_MEDIA"
        await event.reply(f"✅ Name: `{name.title()}`\n\n👉 Ab **IMAGE** bhejo (Caption ke saath jo users ko dikhana hai):")

    # STEP 2: Get Media (Image/Video)
    elif step == "GET_MEDIA":
        if not event.media:
            return await event.reply("⚠️ Bahi, Image bhejni zaroori hai! Photo select karo aur caption likh kar send karo.")
        
        # Storing the entire message object to preserve media and caption
        state["media_msg"] = event.message
        state["step"] = "GET_LINK"
        await event.reply("🖼 Image Saved!\n\n👉 Ab **LINK** bhejo (Jo dono buttons par lagega):")

    # STEP 3: Get Link & Save
    elif step == "GET_LINK":
        link = event.text.strip()
        if not link.startswith("http"):
            return await event.reply("⚠️ Sahi link bhejo (http...)")

        anime_name = state["name"]
        anime_db[anime_name] = {
            "media": state["media_msg"],
            "link": link
        }
        
        del admin_states[user_id]
        await event.reply(f"🎊 **Done!** `{anime_name.title()}` ab search ke liye ready hai!")

# --- USER SEARCH FLOW (Image Reply) ---

@bot.on(events.NewMessage)
async def search_handler(event):
    if event.sender_id in admin_states or event.text.startswith('/'): return

    query = event.text.strip().lower()
    
    for name, data in anime_db.items():
        # Match logic: exact or partial
        if query == name or (len(query) > 2 and query in name):
            media_msg = data["media"]
            link = data["link"]
            
            buttons = [
                [Button.url("▪︎ DOWNLOAD NOW ▪︎", link)],
                [Button.url("▪︎ WATCH NOW ▪︎", link)]
            ]
            
            # Sending the stored media with its original caption and our buttons
            await bot.send_file(
                event.chat_id,
                media_msg.media,
                caption=media_msg.text,
                buttons=buttons
            )
            return

print("✅ Bot is Running (No JSON - Full Media Support)")
bot.run_until_disconnected()
