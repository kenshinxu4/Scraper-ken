import os
import json
import asyncio
import re
import logging
from datetime import datetime
from telethon import TelegramClient, events, Button, errors

# --- LOGGING SETUP (Professional touch) ---
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

# File Names & Links
DB_FILE = "kenshin_data.json"
DEFAULT_START_IMAGE = "https://files.catbox.moe/v4oy6s.jpg"
SUPPORT_GROUP = "https://t.me/KENSHIN_ANIME_CHAT"
CHANNEL_LINK = "https://t.me/KENSHIN_ANIME"
OWNER_USERNAME = "@KENSHIN_ANIME_OWNER"

# --- INITIALIZE BOT ---
print("🛡️ Booting up Kenshin Anime Engine...")
bot = TelegramClient('kenshin_pro_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- DATABASE ENGINE ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: 
                return json.load(f)
        except Exception as e:
            logger.error(f"DB Load Error: {e}")
    return {"users": [], "animes": {}, "settings": {"start_img": DEFAULT_START_IMAGE}}

def save_db(data):
    try:
        with open(DB_FILE, "w") as f: 
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"DB Save Error: {e}")

db = load_db()
admin_states = {}

def add_user_to_db(chat_id):
    if chat_id not in db["users"]:
        db["users"].append(chat_id)
        save_db(db)
        logger.info(f"New User Added: {chat_id}")

# --- HELPER FUNCTIONS ---
async def is_admin(event):
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ **Access Denied!** Only Owner can use this.")
        return False
    return True

# --- USER INTERFACE COMMANDS ---

@bot.on(events.NewMessage(pattern=r'(?i)^/start'))
async def start_cmd(event):
    add_user_to_db(event.chat_id)
    start_img = db.get("settings", {}).get("start_img", DEFAULT_START_IMAGE)
    
    welcome_text = (
        "🌸 **Welcome to KENSHIN ANIME Search!** 🌸\n\n"
        "Official bot of ⚜️ **@KENSHIN_ANIME** ⚜️\n\n"
        "🍿 I provide high-quality Anime links instantly.\n\n"
        "👉 **How to find Anime?**\n"
        "Just type the name. I can detect it even in sentences!\n"
        "Example: `Bhai solo leveling hai kya?`.\n\n"
        "Use `/help` to see all features."
    )
    
    buttons = [
        [Button.url("✨ Join Channel ✨", CHANNEL_LINK)],
        [Button.url("💬 Support Group 💬", SUPPORT_GROUP)],
        [Button.url("👑 Contact Owner", f"https://t.me/{OWNER_USERNAME.replace('@','')}")]
    ]
    
    try:
        await bot.send_file(event.chat_id, start_img, caption=welcome_text, buttons=buttons)
    except Exception:
        await event.reply(welcome_text, buttons=buttons)

@bot.on(events.NewMessage(pattern=r'(?i)^/help'))
async def help_cmd(event):
    help_text = (
        "🛠 **USER INTERFACE MENU**\n\n"
        "• `/start` - Wake up the bot\n"
        "• `/report <msg>` - Request anime or report broken links\n"
        "• `/help` - Show this detailed menu\n\n"
        "🔍 **PRO TIP:** You don't need commands to search. Just send the anime name directly in the chat!"
    )
    
    if event.sender_id == ADMIN_ID:
        help_text += (
            "\n\n⚡ **ADMINISTRATOR PANEL**\n"
            "• `/add_ani` - Add a new entry\n"
            "• `/edit_ani` - Modify existing data\n"
            "• `/set_start_img` - Update bot banner\n"
            "• `/bulk` - Instruction for mass upload\n"
            "• `/list` - Database overview\n"
            "• `/stats` - Total users & animes\n"
            "• `/broadcast` - Global announcement\n"
            "• `/cancel` - Abort ongoing setup"
        )
    await event.reply(help_text)

@bot.on(events.NewMessage(pattern=r'(?i)^/stats'))
async def stats_cmd(event):
    if not await is_admin(event): return
    total_users = len(db.get("users", []))
    total_animes = len(db.get("animes", {}))
    await event.reply(f"📊 **BOT STATISTICS**\n\n👥 Total Users: `{total_users}`\n🎬 Total Animes: `{total_animes}`")

# --- ADMIN CORE OPERATIONS ---

@bot.on(events.NewMessage(pattern=r'(?i)^/(add_ani|edit_ani)$'))
async def admin_init(event):
    if not await is_admin(event): return
    mode = "ADD" if "add" in event.text.lower() else "EDIT"
    admin_states[event.sender_id] = {"step": "NAME", "mode": mode}
    await event.reply(f"🚀 **ENTRY {mode} INITIATED**\n\nStep 1: Please enter the **Anime Name**:")

@bot.on(events.NewMessage)
async def system_handler(event):
    uid = event.sender_id
    raw_text = (event.text or "").strip()
    lower_text = raw_text.lower()

    # --- 1. Bulk Database Update ---
    if uid == ADMIN_ID and event.document and event.file.name.endswith(".txt"):
        msg = await event.reply("⏳ **Processing Bulk File...**")
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
        await msg.edit(f"✅ **Bulk Update Complete!**\nAdded `{count}` new records to the database.")
        return

    # --- 2. Step-by-Step Entry Logic (CASE SENSITIVE SAFE) ---
    if uid in admin_states and not raw_text.startswith('/'):
        state = admin_states[uid]
        
        if state["step"] == "NAME":
            state["name"] = lower_text
            state["step"] = "IMG"
            await event.reply("🔗 **Step 2:** Send the **Image URL** (Catbox/Telegraph):")
            
        elif state["step"] == "IMG":
            state["img"] = raw_text
            state["step"] = "LINK"
            await event.reply("📥 **Step 3:** Send the **Download/Join Link** (Case Sensitive):")
            
        elif state["step"] == "LINK":
            state["link"] = raw_text # PRESERVING CASE FOR TELEGRAM LINKS
            state["step"] = "DESC"
            await event.reply("📝 **Step 4:** Send a short **Synopsis/Description**:")
            
        elif state["step"] == "DESC":
            db["animes"][state["name"]] = {
                "img": state["img"], 
                "link": state["link"], 
                "desc": raw_text
            }
            save_db(db)
            del admin_states[uid]
            await event.reply(f"🎯 **SUCCESS!**\n`{state['name'].upper()}` is now live in the database.")
        return

    # --- 3. Smart Search Engine ---
    if lower_text and not lower_text.startswith('/') and uid not in admin_states:
        # Longest match priority
        anime_keys = sorted(db.get("animes", {}).keys(), key=len, reverse=True)
        
        for name in anime_keys:
            if name in lower_text:
                data = db["animes"][name]
                btn = [[Button.url("🚀 DOWNLOAD / WATCH NOW 🚀", data['link'])]]
                caption = (
                    f"🎬 **ANIME FOUND: {name.upper()}**\n\n"
                    f"📖 **SYNOPSIS:**\n{data['desc']}\n\n"
                    f"✨ **Channel:** @KENSHIN_ANIME"
                )
                try:
                    await event.reply(caption, file=data['img'], buttons=btn)
                    add_user_to_db(event.chat_id) # Save user on search
                except Exception as e:
                    await event.reply(f"⚠️ **Image Error, sending text only.**\n\n{caption}", buttons=btn)
                return

# --- UTILITY COMMANDS ---

@bot.on(events.NewMessage(pattern=r'(?i)^/broadcast'))
async def broadcast_cmd(event):
    if not await is_admin(event): return
    reply = await event.get_reply_message()
    if not reply: return await event.reply("❌ Reply to a message to broadcast it.")
    
    confirm = await event.reply("📡 **Global Broadcast Started...**")
    count, deleted = 0, 0
    
    for user_id in db.get("users", []):
        try:
            await bot.send_message(user_id, reply)
            count += 1
            await asyncio.sleep(0.2) # Flood prevention
        except errors.UserIsBlockedError:
            deleted += 1
        except: pass
        
    await confirm.edit(f"📢 **Broadcast Finished!**\n\n✅ Delivered: `{count}`\n🚫 Blocked/Failed: `{deleted}`")

@bot.on(events.NewMessage(pattern=r'(?i)^/cancel'))
async def cancel_task(event):
    if event.sender_id in admin_states:
        del admin_states[event.sender_id]
        await event.reply("✅ **Current task cancelled.**")

print("💎 Kenshin Pro Version is Online!")
bot.run_until_disconnected()
