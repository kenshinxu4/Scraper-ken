import os
import json
import asyncio
import re
from telethon import TelegramClient, events, Button

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

# Keeping the database file name simple
DB_FILE = "kenshin_data.json"
DEFAULT_START_IMAGE = "https://files.catbox.moe/v4oy6s.jpg"
SUPPORT_GROUP = "https://t.me/KENSHIN_ANIME_CHAT"
CHANNEL_LINK = "https://t.me/KENSHIN_ANIME"
OWNER_USERNAME = "@KENSHIN_ANIME_OWNER"

bot = TelegramClient('kenshin_pro_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- DATABASE LOGIC ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: 
                return json.load(f)
        except:
            pass
    return {"users": [], "animes": {}, "settings": {"start_img": DEFAULT_START_IMAGE}}

def save_db(data):
    with open(DB_FILE, "w") as f: 
        json.dump(data, f, indent=4)

db = load_db()
admin_states = {}

def add_user_to_db(chat_id):
    if chat_id not in db["users"]:
        db["users"].append(chat_id)
        save_db(db)

# --- USER COMMANDS ---

@bot.on(events.NewMessage(pattern=r'(?i)^/start'))
async def start_cmd(event):
    add_user_to_db(event.chat_id)
    start_img = db.get("settings", {}).get("start_img", DEFAULT_START_IMAGE)
    
    welcome_text = (
        "🌸 **Welcome to KENSHIN ANIME Search!** 🌸\n\n"
        "Official bot of ⚜️ **@KENSHIN_ANIME** ⚜️\n\n"
        "🍿 I provide high-quality Anime links instantly.\n\n"
        "👉 **How to find Anime?**\n"
        "Just type the name. I can detect it even in long sentences!\n"
        "Example: `Bhai solo leveling hai kya?`.\n\n"
        "Use `/help` to see more options."
    )
    
    buttons = [
        [Button.url("✨ Join Channel ✨", CHANNEL_LINK)],
        [Button.url("💬 Support Group 💬", SUPPORT_GROUP)]
    ]
    
    try:
        await bot.send_file(event.chat_id, start_img, caption=welcome_text, buttons=buttons)
    except:
        await event.reply(welcome_text, buttons=buttons)

@bot.on(events.NewMessage(pattern=r'(?i)^/help'))
async def help_cmd(event):
    help_text = (
        "🛠 **User Menu**\n\n"
        "• `/start` - Start the bot\n"
        "• `/report <msg>` - Request anime or report links\n"
        "• `/help` - Show this menu\n\n"
        "🔍 **Search:** Just type the anime name directly."
    )
    
    if event.sender_id == ADMIN_ID:
        help_text += (
            "\n\n👑 **Admin Commands:**\n"
            "• `/add_ani` - Add anime\n"
            "• `/edit_ani` - Edit existing\n"
            "• `/set_start_img <url>` - Change /start image\n"
            "• `/bulk` - Get bulk upload info\n"
            "• `/list` - View all anime names\n"
            "• `/broadcast` - (Reply to msg) to broadcast\n"
            "• `/cancel` - Stop current task"
        )
    await event.reply(help_text)

@bot.on(events.NewMessage(pattern=r'(?i)^/report(?: |$)(.*)'))
async def report_cmd(event):
    msg = event.pattern_match.group(1).strip()
    if not msg:
        return await event.reply("⚠️ **Usage:** `/report I need Naruto episodes`.")
    
    user = await event.get_sender()
    username = f"@{user.username}" if user.username else f"ID: {user.id}"
    
    try:
        await bot.send_message(ADMIN_ID, f"📢 **NEW REQUEST**\n\n👤 **From:** {username}\n📝 **Message:** {msg}")
        await event.reply(f"✅ Sent to **{OWNER_USERNAME}**. Please wait!")
    except:
        await event.reply("❌ Error. Contact owner directly.")

# --- ADMIN COMMANDS ---

@bot.on(events.NewMessage(pattern=r'(?i)^/set_start_img(?: |$)(.*)'))
async def set_img(event):
    if event.sender_id != ADMIN_ID: return
    link = event.pattern_match.group(1).strip()
    if not link.startswith("http"):
        return await event.reply("⚠️ Invalid URL.")
    
    if "settings" not in db: db["settings"] = {}
    db["settings"]["start_img"] = link
    save_db(db)
    await event.reply("✅ Start image updated successfully!")

@bot.on(events.NewMessage(pattern=r'(?i)^/broadcast'))
async def broadcast_cmd(event):
    if event.sender_id != ADMIN_ID: return
    reply = await event.get_reply_message()
    if not reply:
        return await event.reply("⚠️ Reply to a message with `/broadcast`.")
    
    status = await event.reply("📡 Broadcasting... Please wait.")
    success, failed = 0, 0
    for uid in db.get("users", []):
        try:
            await bot.send_message(uid, reply)
            success += 1
            await asyncio.sleep(0.3)
        except:
            failed += 1
    await status.edit(f"✅ **Broadcast Done!**\n\nSuccess: {success}\nFailed: {failed}")

@bot.on(events.NewMessage(pattern=r'(?i)^/list'))
async def list_ani(event):
    if event.sender_id != ADMIN_ID: return
    animes = db.get("animes", {})
    if not animes: return await event.reply("DB is empty.")
    
    names = "\n".join([f"• `{n.title()}`" for n in animes.keys()])
    await event.reply(f"📂 **Anime List:**\n\n{names}"[:4000])

@bot.on(events.NewMessage(pattern=r'(?i)^/bulk'))
async def bulk_info(event):
    if event.sender_id != ADMIN_ID: return
    await event.reply(
        "📁 **Bulk Upload Guide**\n\n"
        "Send a `.txt` file with this format:\n"
        "`Name | Image_URL | Link | Synopsis`"
    )

# --- ADMIN FLOW HANDLERS ---

@bot.on(events.NewMessage(pattern=r'(?i)^/(add_ani|edit_ani)$'))
async def admin_init(event):
    if event.sender_id != ADMIN_ID: return
    mode = "ADD" if "add" in event.text.lower() else "EDIT"
    admin_states[event.sender_id] = {"step": "NAME", "mode": mode}
    await event.reply(f"🚀 **{mode} Mode**\nEnter Anime Name:")

@bot.on(events.NewMessage)
async def main_handler(event):
    uid = event.sender_id
    text = (event.text or "").strip().lower()

    # 1. Bulk File Processing
    if uid == ADMIN_ID and event.document and event.file.name.endswith(".txt"):
        file_bytes = await event.download_media(bytes)
        lines = file_bytes.decode('utf-8').splitlines()
        count = 0
        for line in lines:
            if "|" in line:
                try:
                    p = line.split("|")
                    db["animes"][p[0].strip().lower()] = {
                        "img": p[1].strip(), "link": p[2].strip(), "desc": p[3].strip()
                    }
                    count += 1
                except: continue
        save_db(db)
        return await event.reply(f"✅ Bulk Upload success! Added **{count}** entries.")

    # 2. Admin Logic Steps
    if uid in admin_states and not text.startswith('/'):
        state = admin_states[uid]
        if state["step"] == "NAME":
            state["name"] = text
            state["step"] = "IMG"
            await event.reply("👉 Now send Image URL:")
        elif state["step"] == "IMG":
            state["img"] = text
            state["step"] = "LINK"
            await event.reply("👉 Now send Download/Watch Link:")
        elif state["step"] == "LINK":
            state["link"] = text
            state["step"] = "DESC"
            await event.reply("👉 Now enter Synopsis/Description:")
        elif state["step"] == "DESC":
            db["animes"][state["name"]] = {
                "img": state["img"], "link": state["link"], "desc": event.text
            }
            save_db(db)
            del admin_states[uid]
            await event.reply(f"✅ `{state['name'].title()}` has been saved!")
        return

    # 3. Smart Search (Works in Private and Groups)
    if text and not text.startswith('/') and uid not in admin_states:
        add_user_to_db(event.chat_id)
        
        # Priority matching (Longest names first)
        sorted_keys = sorted(db.get("animes", {}).keys(), key=len, reverse=True)
        
        for name in sorted_keys:
            if name in text:
                data = db["animes"][name]
                btns = [[Button.url("▪︎ DOWNLOAD / WATCH ▪︎", data['link'])]]
                cap = f"🎬 **{name.upper()}**\n\n📖 **Synopsis:**\n{data['desc']}\n\n✨ Powered by **@KENSHIN_ANIME**"
                try:
                    await event.reply(cap, file=data['img'], buttons=btns)
                except:
                    await event.reply(f"⚠️ Image Error\n\n{cap}", buttons=btns)
                return

@bot.on(events.NewMessage(pattern=r'(?i)^/cancel'))
async def cancel_task(event):
    if event.sender_id in admin_states:
        del admin_states[event.sender_id]
        await event.reply("✅ Process cancelled.")

print("🚀 KENSHIN BOT STARTED SUCCESSFULLY!")
bot.run_until_disconnected()
