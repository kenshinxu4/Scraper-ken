#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    KENSHIN ANIME SEARCH BOT - PRO EDITION                     ║
║                         Version 3.0 - Ultimate Build                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any

from pyrogram import Client, filters, errors, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import UserIsBlocked

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger("KenshinBot")

# Environment variables
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").replace("@", "")

# Paths
DB_FILE = os.environ.get("DB_FILE", "/data/kenshin_data.json")
DEFAULT_START_IMAGE = "https://files.catbox.moe/v4oy6s.jpg"
CHANNEL_LINK = "https://t.me/KENSHIN_ANIME"
SUPPORT_GROUP = "https://t.me/KENSHIN_ANIME_CHAT"
OWNER_USERNAME = "@KENSHIN_ANIME_OWNER"

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class DatabaseEngine:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: Dict[str, Any] = {}
        self._ensure_dir()
        self._load_or_init()
    
    def _ensure_dir(self):
        db_dir = os.path.dirname(self.filepath)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    def _load_or_init(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                # Migrate old data
                self._migrate()
                return
            except Exception as e:
                logger.error(f"DB Load Error: {e}")
        
        self.data = {
            "users": [],
            "animes": {},
            "settings": {
                "start_image": DEFAULT_START_IMAGE,
                "start_message": None
            }
        }
        self.save()
    
    def _migrate(self):
        """Migrate old 'description key to 'desc'"""
        animes = self.data.get("animes", {})
        migrated = False
        for name, data in animes.items():
            if "description" in data and "desc" not in data:
                data["desc"] = data.pop("description")
                migrated = True
                logger.info(f"Migrated: {name}")
        if migrated:
            self.save()
    
    def save(self) -> bool:
        try:
            temp = self.filepath + ".tmp"
            with open(temp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(temp, self.filepath)
            return True
        except Exception as e:
            logger.error(f"DB Save Error: {e}")
            return False
    
    def add_anime(self, name: str, data: Dict[str, Any]) -> bool:
        try:
            self.data["animes"][name.lower()] = data
            return self.save()
        except Exception as e:
            logger.error(f"Add anime failed: {e}")
            return False
    
    def get_anime(self, name: str):
        return self.data.get("animes", {}).get(name.lower())
    
    def get_all_animes(self):
        return self.data.get("animes", {})
    
    def add_user(self, user_id: int):
        if user_id not in self.data["users"]:
            self.data["users"].append(user_id)
            self.save()
    
    def get_setting(self, key: str, default=None):
        return self.data.get("settings", {}).get(key, default)
    
    def set_setting(self, key: str, value: Any):
        self.data["settings"][key] = value
        return self.save()

db_engine = DatabaseEngine(DB_FILE)

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

admin_states = {}
temp_data = {}

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

async def admin_filter(_, __, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ <b>Access Denied!</b> Only Owner can use this.")
        return False
    return True

admin_only = filters.create(admin_filter)

def clean_text(text: str, is_group: bool = False) -> str:
    if not text:
        return ""
    if is_group and BOT_USERNAME:
        text = text.replace(f"@{BOT_USERNAME}", "").replace(f"@{BOT_USERNAME.lower()}", "")
    return ' '.join(text.split()).strip()

# ═══════════════════════════════════════════════════════════════════════════════
# BOT INIT
# ═══════════════════════════════════════════════════════════════════════════════

bot = Client(
    "kenshin_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
)

# ═══════════════════════════════════════════════════════════════════════════════
# USER COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("start") & filters.private)
async def start_private(client: Client, message: Message):
    user_id = message.from_user.id
    db_engine.add_user(user_id)
    
    start_img = db_engine.get_setting("start_image", DEFAULT_START_IMAGE)
    custom_msg = db_engine.get_setting("start_message")
    
    if custom_msg:
        welcome_text = custom_msg
    else:
        welcome_text = (
            "🌸 <b>Welcome to KENSHIN ANIME Search!</b> 🌸\n\n"
            "<blockquote>Official bot of ⚜️ @KENSHIN_ANIME ⚜️</blockquote>\n\n"
            "🍿 I provide high-quality Anime links instantly.\n\n"
            "👉 <b>How to find Anime?</b>\n"
            "Just type the name. I can detect it even in sentences!\n"
            "💡 <code>Example: Bhai solo leveling hai kya?</code>\n\n"
            "Use /help to see all features."
        )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Join Channel ✨", url=CHANNEL_LINK)],
        [InlineKeyboardButton("💬 Support Group 💬", url=SUPPORT_GROUP)],
        [InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{OWNER_USERNAME.replace('@','')}")]
    ])
    
    try:
        await message.reply_photo(photo=start_img, caption=welcome_text, reply_markup=buttons)
    except Exception as e:
        logger.error(f"Start photo error: {e}")
        await message.reply(welcome_text, reply_markup=buttons)

@bot.on_message(filters.command("start") & filters.group)
async def start_group(client: Client, message: Message):
    await message.reply(
        f"👋 <b>Hey {message.from_user.first_name}!</b>\n\n"
        f"🍿 I'm Kenshin Anime Bot!\n"
        f"Type any anime name and I'll find it for you!\n\n"
        f"<i>DM me for full features → @{BOT_USERNAME or 'Bot'}</i>"
    )

@bot.on_message(filters.command("help") & (filters.private | filters.group))
async def help_cmd(client: Client, message: Message):
    text = (
        "🛠 <b>USER MENU</b>\n\n"
        "• /start - Wake up bot\n"
        "• /report &lt;msg&gt; - Report issue\n"
        "• /help - This menu\n\n"
        "🔍 <b>PRO TIP:</b> Just type anime name directly!"
    )
    
    if is_admin(message.from_user.id):
        text += (
            "\n\n⚡ <b>ADMIN PANEL</b>\n"
            "• /add_ani - Add anime (step-by-step)\n"
            "• /edit_ani - Edit anime\n"
            "• /set_start_img - Change banner\n"
            "• /set_start_msg - Edit welcome\n"
            "• /view_start_img - Preview banner\n"
            "• /bulk - Bulk upload guide\n"
            "• /list - All animes\n"
            "• /stats - Statistics\n"
            "• /broadcast - Message all users\n"
            "• /cancel - Cancel operation"
        )
    await message.reply(text)

@bot.on_message(filters.command("report") & (filters.private | filters.group))
async def report_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply(
            "📝 <b>Report Format:</b>\n"
            "<code>/report Your message here</code>"
        )
        return
    
    report_text = " ".join(message.command[1:])
    user = message.from_user
    
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📢 <b>REPORT</b>\n\n"
            f"From: {user.first_name}\n"
            f"ID: <code>{user.id}</code>\n"
            f"Chat: {'Private' if message.chat.type == 'private' else message.chat.title}\n\n"
            f"📝 {report_text}"
        )
        await message.reply("✅ Report sent!")
    except Exception as e:
        logger.error(f"Report failed: {e}")
        await message.reply("❌ Failed to send.")

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("stats") & admin_only & filters.private)
async def stats_cmd(client: Client, message: Message):
    animes = db_engine.get_all_animes()
    users = db_engine.data.get("users", [])
    
    await message.reply(
        f"📊 <b>STATISTICS</b>\n\n"
        f"👥 Users: <code>{len(users)}</code>\n"
        f"🎬 Animes: <code>{len(animes)}</code>\n"
        f"💾 DB: <code>{DB_FILE}</code>"
    )

@bot.on_message(filters.command("set_start_img") & admin_only & filters.private)
async def set_start_img(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Quick mode: /set_start_img <url>
    if len(message.command) > 1:
        url = message.command[1]
        if not url.startswith(("http://", "https://")):
            await message.reply("❌ Invalid URL!")
            return
        
        try:
            test = await message.reply_photo(photo=url, caption="Testing...")
            db_engine.set_setting("start_image", url)
            await test.edit_caption(f"✅ Banner updated!\n\n<code>{url}</code>")
        except Exception as e:
            await message.reply(f"❌ Invalid image: {e}")
        return
    
    # Interactive mode
    current = db_engine.get_setting("start_image", DEFAULT_START_IMAGE)
    admin_states[user_id] = "SET_START_IMG"
    
    await message.reply(
        f"🖼 <b>Update Banner</b>\n\n"
        f"Current: <code>{current}</code>\n\n"
        f"Send new image URL or <code>cancel</code>\n\n"
        f"Quick: <code>/set_start_img &lt;url&gt;</code>"
    )

@bot.on_message(filters.command("view_start_img") & admin_only & filters.private)
async def view_start_img(client: Client, message: Message):
    current = db_engine.get_setting("start_image", DEFAULT_START_IMAGE)
    try:
        await message.reply_photo(
            photo=current,
            caption=f"👁 Current Banner\n\n<code>{current}</code>"
        )
    except:
        await message.reply(f"⚠️ Current URL:\n<code>{current}</code>")

@bot.on_message(filters.command("set_start_msg") & admin_only & filters.private)
async def set_start_msg(client: Client, message: Message):
    user_id = message.from_user.id
    
    if len(message.command) > 1:
        new_msg = " ".join(message.command[1:])
        db_engine.set_setting("start_message", new_msg)
        await message.reply("✅ Welcome message updated!")
        return
    
    admin_states[user_id] = "SET_START_MSG"
    await message.reply(
        "📝 <b>Update Welcome Text</b>\n\n"
        f"Send new message or <code>cancel</code>\n\n"
        f"Quick: <code>/set_start_msg &lt;text&gt;</code>"
    )

@bot.on_message(filters.command("view_start_msg") & admin_only & filters.private)
async def view_start_msg(client: Client, message: Message):
    current = db_engine.get_setting("start_message")
    if not current:
        await message.reply("ℹ️ Using default message")
    else:
        await message.reply(f"👁 Current Message:\n\n{current}")

@bot.on_message(filters.command("bulk") & admin_only & filters.private)
async def bulk_cmd(client: Client, message: Message):
    await message.reply(
        "📦 <b>BULK UPLOAD</b>\n\n"
        "Format per line:\n"
        "<code>Name | Image URL | Link | Description</code>\n\n"
        "Send <code>.txt</code> file to bot."
    )

@bot.on_message(filters.command("list") & admin_only & filters.private)
async def list_cmd(client: Client, message: Message):
    animes = db_engine.get_all_animes()
    if not animes:
        await message.reply("📭 Database empty!")
        return
    
    items = sorted(animes.items())
    for i in range(0, len(items), 20):
        chunk = items[i:i+20]
        text = f"📚 <b>LIST</b> ({i+1}-{min(i+20, len(items))}/{len(items)})\n\n"
        for idx, (name, data) in enumerate(chunk, i+1):
            display = data.get("name_display", name)
            desc = data.get("desc", "N/A")[:40]
            text += f"<code>{idx}.</code> <b>{display}</b>\n    └ <i>{desc}...</i>\n\n"
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.5)

# ═══════════════════════════════════════════════════════════════════════════════
# ADD/EDIT ANIME - FIXED WITH CLEAR PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("add_ani") & admin_only & filters.private)
async def add_ani(client: Client, message: Message):
    user_id = message.from_user.id
    admin_states[user_id] = "ADD_NAME"
    temp_data[user_id] = {}
    
    await message.reply(
        "╔════════════════════════════════════╗\n"
        "║     🚀 ADD NEW ANIME                 ║\n"
        "╚════════════════════════════════════╝\n\n"
        "<b>Step 1 of 4: Anime Name</b>\n\n"
        "Send the <b>exact anime name</b>.\n\n"
        "💡 Examples: <code>Solo Leveling</code>, <code>Jujutsu Kaisen</code>\n\n"
        "❌ Send <code>cancel</code> to abort.\n\n"
        "⏳ <b>Waiting for name...</b>"
    )

@bot.on_message(filters.command("edit_ani") & admin_only & filters.private)
async def edit_ani(client: Client, message: Message):
    animes = db_engine.get_all_animes()
    if not animes:
        await message.reply("📭 No anime to edit!")
        return
    
    items = sorted(animes.items())
    text = f"✏️ <b>EDIT ANIME</b> ({len(items)} total)\n\n"
    for i, (name, data) in enumerate(items[:50], 1):
        display = data.get("name_display", name)
        text += f"<code>{i}.</code> {display}\n"
    
    text += "\n✏️ Send anime name to edit:\n❌ Send <code>cancel</code> to abort."
    
    admin_states[message.from_user.id] = "EDIT_SELECT"
    await message.reply(text)

@bot.on_message(filters.command("cancel") & (filters.private | filters.group))
async def cancel_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in admin_states:
        del admin_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    
    await message.reply("✅ Cancelled!")

# ═══════════════════════════════════════════════════════════════════════════════
# BROADCAST
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("broadcast") & admin_only & filters.private)
async def broadcast(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to broadcast!")
        return
    
    users = db_engine.data.get("users", [])
    status = await message.reply(f"📡 Broadcasting to {len(users)} users...")
    
    sent, blocked = 0, 0
    for uid in users:
        try:
            await message.reply_to_message.copy(uid)
            sent += 1
            if sent % 50 == 0:
                await status.edit(f"📡 Progress: {sent}/{len(users)}")
            await asyncio.sleep(0.3)
        except UserIsBlocked:
            blocked += 1
        except Exception as e:
            logger.error(f"Broadcast to {uid} failed: {e}")
    
    await status.edit(f"📢 Done! ✅ {sent} | 🚫 {blocked}")

# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT HANDLER (BULK UPLOAD)
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.document & filters.private)
async def doc_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    if not message.document.file_name.endswith('.txt'):
        return
    
    status = await message.reply("⏳ Processing...")
    
    try:
        path = await message.download()
        added = 0
        errors = []
        
        with open(path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#') or '|' not in line:
                    continue
                
                parts = line.split('|')
                if len(parts) < 4:
                    errors.append(f"Line {line_num}: Incomplete")
                    continue
                
                name, img, link, desc = [p.strip() for p in parts[:4]]
                if not all([name, img, link]):
                    continue
                
                # ✅ FIXED: Use 'desc' key (not 'description')
                db_engine.add_anime(name.lower(), {
                    "name_display": name,
                    "image_url": img,
                    "download_link": link,
                    "desc": desc,  # ✅ CORRECT KEY
                    "added_by": message.from_user.id,
                    "added_at": datetime.now().isoformat(),
                    "views": 0
                })
                added += 1
        
        if os.path.exists(path):
            os.remove(path)
        
        result = f"✅ Added: <code>{added}</code>\n❌ Errors: <code>{len(errors)}</code>"
        if errors:
            result += f"\n<pre>{chr(10).join(errors[:10])}</pre>"
        
        await status.edit(result)
        
    except Exception as e:
        logger.error(f"Bulk error: {e}")
        await status.edit(f"❌ Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN MESSAGE HANDLER - ADMIN STATES & SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

COMMANDS = ["start", "help", "report", "stats", "set_start_img", "set_start_msg",
            "view_start_img", "view_start_msg", "bulk", "list", "add_ani", "edit_ani",
            "broadcast", "cancel"]

@bot.on_message(filters.text & (filters.private | filters.group) & ~filters.command(COMMANDS))
async def main_handler(client: Client, message: Message):
    user_id = message.from_user.id
    is_group = message.chat.type != "private"
    text = clean_text(message.text, is_group).lower()
    
    if not text:
        return
    
    # Handle cancel
    if text == "cancel":
        if user_id in admin_states:
            del admin_states[user_id]
        if user_id in temp_data:
            del temp_data[user_id]
        await message.reply("✅ Cancelled!")
        return
    
    # ═════════════════════════════════════════════════════════════════
    # ADMIN STATES (Private only)
    # ═════════════════════════════════════════════════════════════════
    if not is_group and is_admin(user_id) and user_id in admin_states:
        state = admin_states[user_id]
        
        # SET START IMAGE
        if state == "SET_START_IMG":
            if not text.startswith(("http://", "https://")):
                await message.reply("❌ Invalid URL!")
                return
            
            try:
                test = await message.reply_photo(photo=text, caption="Testing...")
                db_engine.set_setting("start_image", text)
                await test.edit_caption(f"✅ Banner updated!\n\n<code>{text}</code>")
            except:
                await message.reply("❌ Invalid image URL!")
            
            del admin_states[user_id]
            return
        
        # SET START MESSAGE
        if state == "SET_START_MSG":
            db_engine.set_setting("start_message", message.text)
            await message.reply("✅ Welcome message updated!")
            del admin_states[user_id]
            return
        
        # ADD ANIME FLOW - FIXED WITH CLEAR PROMPTS
        if state == "ADD_NAME":
            temp_data[user_id] = {"name": message.text, "name_lower": text}
            admin_states[user_id] = "ADD_IMAGE"
            
            await message.reply(
                f"✅ <b>Name saved:</b> <code>{message.text}</code>\n\n"
                f"<b>Step 2 of 4: Image URL</b>\n\n"
                f"📸 Send the <b>anime poster image URL</b>.\n\n"
                f"💡 Recommended: Catbox.moe, Telegraph\n\n"
                f"❌ Send <code>cancel</code> to abort.\n\n"
                f"⏳ <b>Waiting for image URL...</b>"
            )
            return
        
        if state == "ADD_IMAGE":
            if not text.startswith(("http://", "https://")):
                await message.reply("❌ Invalid URL! Must start with http:// or https://")
                return
            
            temp_data[user_id]["image"] = message.text
            admin_states[user_id] = "ADD_LINK"
            
            await message.reply(
                f"✅ <b>Image saved!</b>\n\n"
                f"<b>Step 3 of 4: Download Link</b>\n\n"
                f"🔗 Send the <b>Telegram channel link</b> or <b>download URL</b>.\n\n"
                f"💡 Example: <code>https://t.me/joinchat/ABC123</code>\n\n"
                f"❌ Send <code>cancel</code> to abort.\n\n"
                f"⏳ <b>Waiting for download link...</b>"
            )
            return
        
        if state == "ADD_LINK":
            if not text.startswith(("http://", "https://", "t.me/")):
                await message.reply("❌ Invalid link!")
                return
            
            temp_data[user_id]["link"] = message.text
            admin_states[user_id] = "ADD_DESC"
            
            await message.reply(
                f"✅ <b>Link saved!</b>\n\n"
                f"<b>Step 4 of 4: Description</b>\n\n"
                f"📝 Send a <b>short synopsis</b> of the anime.\n\n"
                f"💡 Example: <code>A weak hunter gains infinite power! Ultimate action fantasy anime!</code>\n\n"
                f"❌ Send <code>cancel</code> to abort.\n\n"
                f"⏳ <b>Waiting for description...</b>"
            )
            return
        
        if state == "ADD_DESC":
            if len(message.text) < 10:
                await message.reply("❌ Too short! Minimum 10 characters.")
                return
            
            # ✅ FIXED: Use 'desc' key
            data = temp_data[user_id]
            db_engine.add_anime(data["name_lower"], {
                "name_display": data["name"],
                "image_url": data["image"],
                "download_link": data["link"],
                "desc": message.text,  # ✅ CORRECT KEY
                "added_by": user_id,
                "added_at": datetime.now().isoformat(),
                "views": 0
            })
            
            await message.reply(
                f"╔════════════════════════════════════╗\n"
                f"║     🎯 SUCCESS! ANIME ADDED          ║\n"
                f"╚════════════════════════════════════╝\n\n"
                f"✅ <b>{data['name']}</b> added to database!\n\n"
                f"Users can now search for this anime."
            )
            
            del admin_states[user_id]
            del temp_data[user_id]
            return
        
        # EDIT ANIME FLOW
        if state == "EDIT_SELECT":
            target = text
            animes = db_engine.get_all_animes()
            
            # Find match
            if target in animes:
                anime = animes[target]
            else:
                matches = [k for k in animes.keys() if target in k]
                if len(matches) == 1:
                    target = matches[0]
                    anime = animes[target]
                else:
                    await message.reply(f"❌ No match for '<code>{message.text}</code>'")
                    return
            
            temp_data[user_id] = {"edit_target": target, "anime": anime}
            admin_states[user_id] = "EDIT_FIELD"
            
            await message.reply(
                f"✏️ <b>Editing:</b> <code>{anime.get('name_display', target)}</code>\n\n"
                f"<b>Current Data:</b>\n"
                f"1️⃣ Name: <code>{anime.get('name_display', target)}</code>\n"
                f"2️⃣ Image: <code>{anime.get('image_url', 'N/A')[:50]}...</code>\n"
                f"3️⃣ Link: <code>{anime.get('download_link', 'N/A')[:50]}...</code>\n"
                f"4️⃣ Desc: <code>{anime.get('desc', 'N/A')[:100]}...</code>\n\n"
                f"✏️ Send <code>1</code>, <code>2</code>, <code>3</code>, or <code>4</code>\n"
                f"❌ Send <code>cancel</code> to abort."
            )
            return
        
        if state == "EDIT_FIELD":
            choice = message.text.strip()
            if choice not in ["1", "2", "3", "4"]:
                await message.reply("❌ Send 1, 2, 3, or 4!")
                return
            
            field_map = {
                "1": ("name_display", "Name"),
                "2": ("image_url", "Image URL"),
                "3": ("download_link", "Download Link"),
                "4": ("desc", "Description")  # ✅ CORRECT KEY
            }
            
            field, field_name = field_map[choice]
            temp_data[user_id]["edit_field"] = field
            temp_data[user_id]["edit_field_name"] = field_name
            admin_states[user_id] = "EDIT_VALUE"
            
            await message.reply(
                f"✏️ <b>Editing {field_name}</b>\n\n"
                f"Send new value for <code>{temp_data[user_id]['edit_target']}</code>:\n\n"
                f"❌ Send <code>cancel</code> to abort."
            )
            return
        
        if state == "EDIT_VALUE":
            target = temp_data[user_id]["edit_target"]
            field = temp_data[user_id]["edit_field"]
            
            db_engine.data["animes"][target][field] = message.text
            db_engine.save()
            
            await message.reply(
                f"✅ <b>Updated!</b>\n\n"
                f"<b>{target}</b> - {temp_data[user_id]['edit_field_name']} changed."
            )
            
            del admin_states[user_id]
            del temp_data[user_id]
            return
    
    # ═════════════════════════════════════════════════════════════════
    # ANIME SEARCH (All users)
    # ═════════════════════════════════════════════════════════════════
    if not text.startswith("/"):
        animes = db_engine.get_all_animes()
        
        if not animes:
            if not is_group:
                await message.reply("📭 No anime in database yet!")
            return
        
        # Search
        for name in sorted(animes.keys(), key=len, reverse=True):
            if name in text:
                data = animes[name]
                
                # Increment views
                data["views"] = data.get("views", 0) + 1
                db_engine.save()
                
                display_name = data.get("name_display", name)
                
                # ✅ YOUR EXACT CAPTION STYLE
                caption = (
                    f"<blockquote>✨ <b>{display_name.upper()}</b> ✨</blockquote>\n\n"
                    f"<b><blockquote>📖 {data.get('desc', 'No description')}</blockquote></b>\n\n"
                    f"➖➖➖➖➖➖➖➖➖➖\n"
                    f"🔰 <b>FOR MORE JOIN:</b>\n"
                    f"<blockquote>👉 @KENSHIN_ANIME\n"
                    f"👉 @MANWHA_VERSE</blockquote>"
                )
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 DOWNLOAD / WATCH NOW", url=data["download_link"])]
                ])
                
                try:
                    await message.reply_photo(
                        photo=data["image_url"],
                        caption=caption,
                        reply_markup=buttons
                    )
                except Exception as e:
                    logger.error(f"Photo error: {e}")
                    await message.reply(caption, reply_markup=buttons)
                
                db_engine.add_user(user_id)
                return
        
        # No match
        if not is_group:
            await message.reply(
                f"🔍 No results for '<code>{message.text[:30]}</code>'\n\n"
                f"Try different spelling or /report to request."
            )

# ═══════════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"💎 Kenshin Bot v3.0 Starting...")
    print(f"💾 Database: {DB_FILE}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    bot.run()
