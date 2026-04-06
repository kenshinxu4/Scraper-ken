import os
import json
import asyncio
import re
from telethon import TelegramClient, events, Button

# --- CONFIGURATION ---
# Get these from my.telegram.org and BotFather
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

DB_FILE = "database.json"
DEFAULT_START_IMAGE = "https://files.catbox.moe/v4oy6s.jpg"
SUPPORT_GROUP = "https://t.me/KENSHIN_ANIME_CHAT"
CHANNEL_LINK = "https://t.me/KENSHIN_ANIME"

bot = TelegramClient('kenshin_v8', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- DATABASE LOGIC ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: 
                data = json.load(f)
                if "settings" not in data: data["settings"] = {"start_img": DEFAULT_START_IMAGE}
                if "users" not in data: data["users"] = []
                if "animes" not in data: data["animes"] = {}
                return data
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
    start_img = db["settings"].get("start_img", DEFAULT_START_IMAGE)
    
    welcome_text = (
        "🌸 **Welcome to KENSHIN ANIME Search!** 🌸\n\n"
        "Official bot of ⚜️ **@KENSHIN_ANIME** ⚜️\n\n"
        "🍿 I can find Download and Watch links for you instantly.\n\n"
        "👉 **How to find Anime?**\n"
        "Just type the name in chat. I work in groups too!\n"
        "Example: `Solo Leveling` or `Can anyone send Naruto?`.\n\n"
        "Use `/help` for more. Enjoy! ✨"
    )
    
    buttons = [
        [Button.url("✨ Join Channel ✨", CHANNEL_LINK)],
        [Button.url("💬 Support Chat 💬", SUPPORT_GROUP)]
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
        "• `/report <msg>` - Request an anime or report issues\n"
        "• `/help` - Show this menu\n\n"
        "🔍 **Search:** Just type the anime name naturally."
    )
    
    if event.sender_id == ADMIN_ID:
        help_text += (
            "\n\n👑 **Admin Controls:**\n"
            "• `/add_ani` - Add one anime\n"
            "• `/edit_ani` - Update anime details\n"
            "• `/set_start_img <url>` - Change /start photo\n"
            "• `/bulk` - Bulk upload guide\n"
            "• `/list` - View all entries\n"
            "• `/broadcast` - (Reply to a message) to send to all users\n"
            "• `/cancel` - Stop current admin action"
        )
    await event.reply(help_text)

@bot.on(events.NewMessage(pattern=r'(?i)^/report(?: |$)(.*)'))
async def report_cmd(event):
    msg = event.pattern_match.group(1).strip()
    if not msg:
        return await event.reply("⚠️ **Usage:** `/report I need One Piece episodes`.")
    
    user = await event.get_sender()
    username = f"@{user.username}" if user.username else f"ID: {user.id}"
    
    try:
        await bot.send_message(ADMIN_ID, f"📢 **NEW USER REQUEST**\n\n👤 **From:** {username}\n📝 **Message:** {msg}")
        await event.reply("✅ Your request has been sent to **@KENSHIN_ANIME_OWNER**. Please wait for an update!")
    except:
        await event.reply("❌ Error sending report. Try again later.")

# --- ADMIN COMMANDS ---

@bot.on(events.NewMessage(pattern=r'(?i)^/set_start_img(?: |$)(.*)'))
async def set_img(event):
    if event.sender_id != ADMIN_ID: return
    link = event.pattern_match.group(1).strip()
    if not link.startswith("http"):
        return await event.reply("⚠️ Send a valid image link.")
    db["settings"]["start_img"] = link
    save_db(db)
    await event.reply("✅ Start image updated!")

@bot.on(events.NewMessage(pattern=r'(?i)^/broadcast'))
async def broadcast_cmd(event):
    if event.sender_id != ADMIN_ID: return
    reply = await event.get_reply_message()
    if not reply:
        return await event.reply("⚠️ Reply to a message with `/broadcast` to send it to all users.")
    
    prog = await event.reply("📡 Broadcasting...")
    success, failed = 0, 0
    for uid in db["users"]:
        try:
            await bot.send_message(uid, reply)
            success += 1
            await asyncio.sleep(0.3)
        except:
            failed += 1
    await prog.edit(f"✅ **Broadcast Done!**\n\nSent: {success}\nFailed: {failed}")

@bot.on(events.NewMessage(pattern=r'(?i)^/list'))
async def list_ani(event):
    if event.sender_id != ADMIN_ID: return
    if not db["animes"]: return await event.reply("DB is empty.")
    
    names = "\n".join([f"• `{n.title()}`" for n in db["animes"].keys()])
    await event.reply(f"📂 **Animes in DB:**\n\n{names}"[:4000])

@bot.on(events.NewMessage(pattern=r'(?i)^/bulk'))
async def bulk_cmd(event):
    if event.sender_id != ADMIN_ID: return
    await event.reply(
        "📊 **Bulk Upload Guide**\n\n"
        "Send a `.txt` file with this format in every line:\n"
        "`Name | Image_URL | Link | Synopsis`"
    )

@bot.on(events.NewMessage(pattern=r'(?i)^/add_ani$|(?i)^/edit_ani$'))
async def add_ani_init(event):
    if event.sender_id != ADMIN_ID: return
    mode = "ADD" if "add" in event.text.lower() else "EDIT"
    admin_states[event.sender_id] = {"step": "NAME", "mode": mode}
    await event.reply(f"🚀 **{mode} Mode**\nEnter the Anime Name:")

# --- MAIN HANDLER (Search + Admin Steps + Bulk File) ---

@bot.on(events.NewMessage)
async def main_handler(event):
    uid = event.sender_id
    text = event.text.strip().lower()

    # 1. Handle Bulk File
    if uid == ADMIN_ID and event.document and event.file.name.endswith(".txt"):
        file_data = await event.download_media(bytes)
        lines = file_data.decode('utf-8').splitlines()
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
        return await event.reply(f"✅ Successfully added **{count}** animes from file!")

    # 2. Handle Admin Steps
    if uid in admin_states and not text.startswith('/'):
        state = admin_states[uid]
        if state["step"] == "NAME":
            if state["mode"] == "EDIT" and text not in db["animes"]:
                return await event.reply("❌ Anime not found in DB!")
            state["name"] = text
            state["step"] = "IMG"
            await event.reply("👉 Send Image URL:")
        elif state["step"] == "IMG":
            state["img"] = text
            state["step"] = "LINK"
            await event.reply("👉 Send Download/Watch Link:")
        elif state["step"] == "LINK":
            state["link"] = text
            state["step"] = "DESC"
            await event.reply("👉 Enter Synopsis:")
        elif state["step"] == "DESC":
            db["animes"][state["name"]] = {"img": state["img"], "link": state["link"], "desc": event.text}
            save_db(db)
            del admin_states[uid]
            await event.reply(f"✅ `{state['name'].title()}` saved!")
        return

    # 3. Handle Smart Search
    if not text.startswith('/') and text:
        add_user_to_db(event.chat_id)
        
        # Sort keys by length (descending) to match "Solo Leveling S2" before "Solo Leveling"
        sorted_animes = sorted(db["animes"].items(), key=lambda x: len(x[0]), reverse=True)
        
        for name, data in sorted_animes:
            if name in text:
                btns = [[Button.url("▪︎ DOWNLOAD / WATCH NOW ▪︎", data['link'])]]
                cap = f"🎬 **{name.upper()}**\n\n📖 **Synopsis:**\n{data['desc']}\n\n✨ Powered by **@KENSHIN_ANIME**"
                try:
                    await event.reply(cap, file=data['img'], buttons=btns)
                except:
                    await event.reply(f"⚠️ Image Load Failed\n\n{cap}", buttons=btns)
                return

@bot.on(events.NewMessage(pattern=r'(?i)^/cancel'))
async def cancel_cmd(event):
    if event.sender_id in admin_states:
        del admin_states[event.sender_id]
        await event.reply("✅ Action cancelled.")

print("🚀 KENSHIN BOT IS ONLINE!")
bot.run_until_disconnected()
