import os
import json
import asyncio
import re
import logging
from telethon import TelegramClient, events, Button, errors

# --- LOGGING SETUP ---
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)

# --- CONFIGURATION ---
# Yahan apni asli ID daalein agar environment variable kaam nahi kar raha
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

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
            with open(DB_FILE, "r") as f: return json.load(f)
        except: pass
    return {"users": [], "animes": {}, "settings": {"start_img": DEFAULT_START_IMAGE}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

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
        "👉 **How to find Anime?**\n"
        "Just type the name. Example: `Solo Leveling`\n\n"
        "Use `/help` to see more options."
    )
    btns = [[Button.url("✨ Channel", CHANNEL_LINK), Button.url("💬 Support", SUPPORT_GROUP)]]
    try:
        await bot.send_file(event.chat_id, start_img, caption=welcome_text, buttons=btns)
    except:
        await event.reply(welcome_text, buttons=btns)

@bot.on(events.NewMessage(pattern=r'(?i)^/help'))
async def help_cmd(event):
    help_text = "🛠 **User Menu**\n• `/start` • `/report <msg>`\n\n🔍 Search by name directly."
    if event.sender_id == ADMIN_ID:
        help_text += (
            "\n\n👑 **Admin Commands:**\n"
            "• `/add_ani` - Add New\n• `/edit_ani` - Edit Entry\n"
            "• `/list` - See All Anime\n• `/stats` - Bot Stats\n"
            "• `/bulk` - Bulk Upload Info\n• `/broadcast` - Global Msg\n"
            "• `/set_start_img <url>` - Change Banner\n• `/cancel` - Stop Task"
        )
    await event.reply(help_text)

@bot.on(events.NewMessage(pattern=r'(?i)^/report(?:\s+(.*))?$'))
async def report_cmd(event):
    msg = event.pattern_match.group(1)
    if not msg: return await event.reply("⚠️ Usage: `/report I need Naruto`.")
    user = await event.get_sender()
    name = f"@{user.username}" if user.username else f"ID: {user.id}"
    await bot.send_message(ADMIN_ID, f"📢 **REPORT FROM {name}:**\n{msg}")
    await event.reply("✅ Sent to Admin!")

# --- ADMIN COMMANDS ---

@bot.on(events.NewMessage(pattern=r'(?i)^/stats$'))
async def stats_cmd(event):
    if event.sender_id != ADMIN_ID: return
    u = len(db.get("users", []))
    a = len(db.get("animes", {}))
    await event.reply(f"📊 **STATS**\n\nUsers: `{u}`\nAnimes: `{a}`")

@bot.on(events.NewMessage(pattern=r'(?i)^/list$'))
async def list_cmd(event):
    if event.sender_id != ADMIN_ID: return
    animes = db.get("animes", {})
    if not animes: return await event.reply("📂 DB is empty.")
    text = "📂 **ANIME LIST:**\n\n" + "\n".join([f"• `{k.title()}`" for k in animes.keys()])
    await event.reply(text[:4000])

@bot.on(events.NewMessage(pattern=r'(?i)^/set_start_img\s+(.*)'))
async def set_img(event):
    if event.sender_id != ADMIN_ID: return
    url = event.pattern_match.group(1).strip()
    db["settings"]["start_img"] = url
    save_db(db)
    await event.reply("✅ Start image updated!")

@bot.on(events.NewMessage(pattern=r'(?i)^/bulk$'))
async def bulk_info(event):
    if event.sender_id != ADMIN_ID: return
    await event.reply("📁 **Bulk Upload:** Send `.txt` file.\nFormat: `Name | Image | Link | Desc`")

@bot.on(events.NewMessage(pattern=r'(?i)^/broadcast$'))
async def broadcast_cmd(event):
    if event.sender_id != ADMIN_ID: return
    reply = await event.get_reply_message()
    if not reply: return await event.reply("⚠️ Reply to a message with `/broadcast`.")
    msg = await event.reply("📡 Sending...")
    count = 0
    for uid in db.get("users", []):
        try:
            await bot.send_message(uid, reply)
            count += 1
            await asyncio.sleep(0.3)
        except: pass
    await msg.edit(f"✅ Sent to `{count}` users.")

# --- MAIN ENGINE (Add/Search/Bulk) ---

@bot.on(events.NewMessage(pattern=r'(?i)^/(add_ani|edit_ani)$'))
async def admin_init(event):
    if event.sender_id != ADMIN_ID: return
    mode = "ADD" if "add" in event.text.lower() else "EDIT"
    admin_states[event.sender_id] = {"step": "NAME", "mode": mode}
    await event.reply(f"🚀 **{mode} Mode**\nEnter Anime Name:")

@bot.on(events.NewMessage)
async def main_handler(event):
    uid = event.sender_id
    raw_text = (event.text or "").strip()
    lower_text = raw_text.lower()

    # 1. Bulk File
    if uid == ADMIN_ID and event.document and event.file.name.endswith(".txt"):
        file_bytes = await event.download_media(bytes)
        lines = file_bytes.decode('utf-8').splitlines()
        for line in lines:
            if "|" in line:
                try:
                    p = line.split("|")
                    db["animes"][p[0].strip().lower()] = {"img": p[1].strip(), "link": p[2].strip(), "desc": p[3].strip()}
                except: continue
        save_db(db)
        return await event.reply("✅ Bulk Added Successfully!")

    # 2. Admin Logic
    if uid in admin_states and not raw_text.startswith('/'):
        state = admin_states[uid]
        if state["step"] == "NAME":
            state["name"] = lower_text
            state["step"] = "IMG"
            await event.reply("👉 Send Image URL:")
        elif state["step"] == "IMG":
            state["img"] = raw_text
            state["step"] = "LINK"
            await event.reply("👉 Send Download Link (Case Sensitive):")
        elif state["step"] == "LINK":
            state["link"] = raw_text # 🔥 Case preserved
            state["step"] = "DESC"
            await event.reply("👉 Send Description:")
        elif state["step"] == "DESC":
            db["animes"][state["name"]] = {"img": state["img"], "link": state["link"], "desc": raw_text}
            save_db(db)
            del admin_states[uid]
            await event.reply(f"✅ Saved `{state['name'].title()}`")
        return

    # 3. Search
    if lower_text and not lower_text.startswith('/') and uid not in admin_states:
        keys = sorted(db.get("animes", {}).keys(), key=len, reverse=True)
        for name in keys:
            if name in lower_text:
                data = db["animes"][name]
                btn = [[Button.url("▪︎ DOWNLOAD / WATCH ▪︎", data['link'])]]
                cap = f"🎬 **{name.upper()}**\n\n📖 **Synopsis:**\n{data['desc']}\n\n✨ @KENSHIN_ANIME"
                try: await event.reply(cap, file=data['img'], buttons=btn)
                except: await event.reply(f"⚠️ Image Error\n\n{cap}", buttons=btn)
                return

@bot.on(events.NewMessage(pattern=r'(?i)^/cancel'))
async def cancel_task(event):
    if event.sender_id in admin_states:
        del admin_states[event.sender_id]
        await event.reply("✅ Cancelled.")

print("🚀 Bot is Online!")
bot.run_until_disconnected()
