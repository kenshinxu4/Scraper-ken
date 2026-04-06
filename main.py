#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           🔥 KENSHIN ANIME BOT - FIXED EDITION v4.3 🔥                         ║
║              Edit Fixed | Group Silent | Private Only No-Match                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

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

# Environment
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
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

class Database:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: Dict[str, Any] = {}
        self._ensure_dir()
        self._load()
    
    def _ensure_dir(self):
        db_dir = os.path.dirname(self.filepath)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                return
            except Exception as e:
                logger.error(f"DB Load Error: {e}")
        
        self.data = {
            "users": [],
            "animes": {},
            "aliases": {},
            "settings": {
                "start_image": DEFAULT_START_IMAGE,
                "start_message": None
            }
        }
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
            name_lower = name.lower().strip()
            self.data["animes"][name_lower] = data
            
            for alias in data.get("aliases", []):
                self.data["aliases"][alias.lower().strip()] = name_lower
            
            return self.save()
        except Exception as e:
            logger.error(f"Add failed: {e}")
            return False
    
    def get_anime(self, name: str) -> Optional[Dict[str, Any]]:
        name_lower = name.lower().strip()
        
        # Direct match
        if name_lower in self.data.get("animes", {}):
            result = self.data["animes"][name_lower].copy()
            result["_key"] = name_lower
            return result
        
        # Alias match
        if name_lower in self.data.get("aliases", {}):
            original = self.data["aliases"][name_lower]
            if original in self.data.get("animes", {}):
                result = self.data["animes"][original].copy()
                result["_key"] = original
                return result
        
        return None
    
    def get_all_animes(self) -> Dict[str, Any]:
        return self.data.get("animes", {})
    
    def update_anime_field(self, name: str, field: str, value: Any) -> bool:
        try:
            name_lower = name.lower().strip()
            if name_lower in self.data.get("animes", {}):
                self.data["animes"][name_lower][field] = value
                
                if field == "aliases":
                    for alias, target in list(self.data.get("aliases", {}).items()):
                        if target == name_lower:
                            del self.data["aliases"][alias]
                    for alias in value:
                        self.data["aliases"][alias.lower().strip()] = name_lower
                
                return self.save()
            return False
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False
    
    def delete_anime(self, name: str) -> bool:
        try:
            name_lower = name.lower().strip()
            if name_lower in self.data.get("animes", {}):
                anime_data = self.data["animes"][name_lower]
                for alias in anime_data.get("aliases", []):
                    alias_lower = alias.lower().strip()
                    if alias_lower in self.data.get("aliases", {}):
                        del self.data["aliases"][alias_lower]
                
                del self.data["animes"][name_lower]
                return self.save()
            return False
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
    
    def add_user(self, user_id: int) -> bool:
        if user_id not in self.data.get("users", []):
            self.data["users"].append(user_id)
            return self.save()
        return True
    
    def get_setting(self, key: str, default=None):
        return self.data.get("settings", {}).get(key, default)
    
    def set_setting(self, key: str, value: Any) -> bool:
        self.data["settings"][key] = value
        return self.save()

db = Database(DB_FILE)

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class StateManager:
    def __init__(self):
        self.states: Dict[int, Dict[str, Any]] = {}
    
    def set(self, user_id: int, state: str, data: Dict[str, Any] = None):
        self.states[user_id] = {"state": state, "data": data or {}}
    
    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.states.get(user_id)
    
    def clear(self, user_id: int):
        if user_id in self.states:
            del self.states[user_id]
    
    def is_admin(self, user_id: int) -> bool:
        return user_id == ADMIN_ID

state = StateManager()

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
# SEARCH ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class SearchEngine:
    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        return text
    
    @staticmethod
    def find_anime_in_text(user_text: str) -> Optional[Dict[str, Any]]:
        if not user_text:
            return None
        
        user_text_clean = SearchEngine.normalize(user_text)
        animes = db.get_all_animes()
        
        if not animes:
            return None
        
        best_match = None
        best_priority = 999
        
        # Sort by length (longest first) to prioritize longer matches
        sorted_animes = sorted(animes.items(), 
                              key=lambda x: len(x[1].get("name_display", x[0])), 
                              reverse=True)
        
        for key, data in sorted_animes:
            # Check main name
            main_name = SearchEngine.normalize(data.get("name_display", key))
            
            if main_name and main_name in user_text_clean:
                priority = 100 - len(main_name)
                if priority < best_priority:
                    best_priority = priority
                    best_match = {**data, "_key": key, "_matched_by": "name"}
                    continue
            
            # Check aliases
            for alias in data.get("aliases", []):
                alias_clean = SearchEngine.normalize(alias)
                if alias_clean and alias_clean in user_text_clean:
                    priority = 50 - len(alias_clean)
                    if priority < best_priority:
                        best_priority = priority
                        best_match = {**data, "_key": key, "_matched_by": "alias"}
                        break
        
        return best_match

# ═══════════════════════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════════════════════

def clean_text(text: str, is_group: bool = False) -> str:
    if not text:
        return ""
    if is_group and BOT_USERNAME:
        text = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.IGNORECASE)
    return ' '.join(text.split()).strip()

# ═══════════════════════════════════════════════════════════════════════════════
# USER COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("start") & filters.private)
async def start_private(client, message):
    user_id = message.from_user.id
    db.add_user(user_id)
    
    start_img = db.get_setting("start_image", DEFAULT_START_IMAGE)
    custom_msg = db.get_setting("start_message")
    
    if custom_msg:
        welcome_text = custom_msg
    else:
        welcome_text = (
            "🌸 <b>Welcome to KENSHIN ANIME Search!</b> 🌸\n\n"
            "<blockquote>Official bot of ⚜️ @KENSHIN_ANIME ⚜️</blockquote>\n\n"
            "🍿 I provide high-quality Anime links instantly!\n\n"
            "👉 <b>How to find Anime?</b>\n"
            "Just type the name anywhere in your message!\n"
            "💡 <code>Examples:</code>\n"
            "• <code>Bhai solo leveling hai kya?</code>\n"
            "• <code>jjk ka link do</code>\n"
            "• <code>I want to watch attack on titan</code>\n\n"
            "Use /help to see all features."
        )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Join Channel ✨", url=CHANNEL_LINK)],
        [InlineKeyboardButton("💬 Support Group 💬", url=SUPPORT_GROUP)],
        [InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{OWNER_USERNAME.replace('@','')}")]
    ])
    
    try:
        await message.reply_photo(photo=start_img, caption=welcome_text, reply_markup=buttons)
    except:
        await message.reply(welcome_text, reply_markup=buttons)

@bot.on_message(filters.command("start") & filters.group)
async def start_group(client, message):
    await message.reply(
        f"👋 <b>Hey {message.from_user.first_name}!</b>\n\n"
        f"🍿 I'm Kenshin Anime Bot!\n"
        f"Type any anime name in any sentence and I'll find it!\n\n"
        f"<i>DM me for full features → @{BOT_USERNAME or 'Bot'}</i>"
    )

@bot.on_message(filters.command("help"))
async def help_cmd(client, message):
    is_admin = state.is_admin(message.from_user.id)
    
    text = (
        "🛠 <b>USER COMMANDS</b>\n\n"
        "• /start - Start the bot\n"
        "• /help - Show this menu\n"
        "• /report &lt;msg&gt; - Report issue\n\n"
        "🔍 <b>HOW TO SEARCH:</b>\n"
        "Just type anime name anywhere in your message!\n"
        "• <code>solo leveling ka link do</code>\n"
        "• <code>bhai jjk hai kya?</code>\n"
        "• <code>I want to watch attack on titan</code>\n\n"
        "Bot will automatically detect anime names!"
    )
    
    if is_admin:
        text += (
            "\n\n⚡ <b>ADMIN COMMANDS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "• /add_ani - Add new anime\n"
            "• /edit_ani - Edit anime\n"
            "• /delete_ani - Delete anime\n"
            "• /add_alias - Add alias to anime\n"
            "• /set_start_img - Change banner\n"
            "• /set_start_msg - Edit welcome\n"
            "• /list - List all animes\n"
            "• /broadcast - Broadcast message\n"
            "• /cancel - Cancel operation"
        )
    
    await message.reply(text)

@bot.on_message(filters.command("report"))
async def report_cmd(client, message):
    if len(message.command) < 2:
        await message.reply("📝 <b>Usage:</b> <code>/report your message here</code>")
        return
    
    report_text = " ".join(message.command[1:])
    user = message.from_user
    
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📢 <b>REPORT</b>\n\n"
            f"From: {user.first_name} (@{user.username or 'N/A'})\n"
            f"ID: <code>{user.id}</code>\n\n"
            f"📝 {report_text}"
        )
        await message.reply("✅ Report sent!")
    except Exception as e:
        logger.error(f"Report failed: {e}")
        await message.reply("❌ Failed to send report.")

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN COMMANDS - FIXED EDIT ANI
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("add_ani") & filters.private)
async def add_ani_cmd(client, message):
    user_id = message.from_user.id
    if not state.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    # Quick mode
    if len(message.command) > 1:
        full_text = " ".join(message.command[1:])
        if "|" in full_text:
            parts = [p.strip() for p in full_text.split("|")]
            if len(parts) >= 4:
                name, img, link, desc = parts[0], parts[1], parts[2], parts[3]
                aliases = [a.strip() for a in parts[4].split(",")] if len(parts) > 4 and parts[4] else []
                
                success = db.add_anime(name, {
                    "name_display": name,
                    "image_url": img,
                    "download_link": link,
                    "desc": desc,
                    "aliases": aliases,
                    "added_by": user_id,
                    "added_at": datetime.now().isoformat(),
                    "views": 0
                })
                
                await message.reply(f"✅ <b>{name}</b> added!" if success else "❌ Failed!")
                return
    
    # Interactive
    state.set(user_id, "ADD_NAME", {})
    await message.reply(
        "🚀 <b>ADD NEW ANIME - STEP 1/5</b>\n\n"
        "<b>Send the anime name:</b>\n\n"
        "Examples:\n"
        "• <code>Solo Leveling</code>\n"
        "• <code>Jujutsu Kaisen</code>\n"
        "• <code>Attack on Titan</code>\n\n"
        "❌ Send <code>cancel</code> to abort."
    )

@bot.on_message(filters.command("edit_ani") & filters.private)
async def edit_ani_cmd(client, message):
    """FIXED: Edit anime with proper number selection"""
    user_id = message.from_user.id
    if not state.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    animes = db.get_all_animes()
    if not animes:
        await message.reply("📭 No anime in database!")
        return
    
    # Sort animes by display name
    items = sorted(animes.items(), key=lambda x: x[1].get("name_display", x[0]))
    
    list_text = "<b>✏️ EDIT ANIME</b>\n\n<b>Available Animes:</b>\n\n"
    anime_list = []
    
    for i, (key, data) in enumerate(items[:50], 1):
        display = data.get("name_display", key)
        list_text += f"<code>{i:2d}.</code> {display}\n"
        anime_list.append((key, display))
    
    if len(items) > 50:
        list_text += f"\n<i>... and {len(items) - 50} more</i>\n"
    
    list_text += (
        "\n✏️ <b>How to select:</b>\n"
        "• Send the <b>number</b> (e.g., <code>27</code>)\n"
        "• Or send the <b>exact anime name</b>\n"
        "• Or send an <b>alias</b>\n\n"
        "❌ <code>cancel</code> to abort."
    )
    
    # Store anime list in state
    state.set(user_id, "EDIT_SELECT", {"anime_list": anime_list})
    await message.reply(list_text, disable_web_page_preview=True)

@bot.on_message(filters.command("delete_ani") & filters.private)
async def delete_ani_cmd(client, message):
    user_id = message.from_user.id
    if not state.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    if len(message.command) < 2:
        await message.reply("🗑 <b>Usage:</b> <code>/delete_ani anime_name</code>")
        return
    
    name = " ".join(message.command[1:])
    anime_data = db.get_anime(name)
    
    if not anime_data:
        await message.reply(f"❌ Anime '<code>{name}</code>' not found!")
        return
    
    display_name = anime_data.get("name_display", name)
    actual_key = anime_data.get("_key", name.lower())
    
    state.set(user_id, "DELETE_CONFIRM", {
        "target": actual_key,
        "display_name": display_name
    })
    
    await message.reply(
        f"⚠️ <b>Delete '{display_name}'?</b>\n\n"
        f"Send <code>yes</code> to confirm, or <code>cancel</code>."
    )

@bot.on_message(filters.command("add_alias") & filters.private)
async def add_alias_cmd(client, message):
    user_id = message.from_user.id
    if not state.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    if len(message.command) < 3:
        await message.reply(
            "🏷 <b>Usage:</b> <code>/add_alias anime_name | alias1, alias2, alias3</code>\n\n"
            "Example:\n<code>/add_alias Solo Leveling | sl, solo lev, sung jin-woo</code>"
        )
        return
    
    full_text = " ".join(message.command[1:])
    if "|" not in full_text:
        await message.reply("❌ Invalid format! Use: <code>anime | alias1, alias2</code>")
        return
    
    parts = [p.strip() for p in full_text.split("|", 1)]
    anime_name = parts[0]
    new_aliases = [a.strip() for a in parts[1].split(",") if a.strip()]
    
    anime_data = db.get_anime(anime_name)
    if not anime_data:
        await message.reply(f"❌ Anime '<code>{anime_name}</code>' not found!")
        return
    
    actual_key = anime_data.get("_key", anime_name.lower())
    existing_aliases = set(anime_data.get("aliases", []))
    existing_aliases.update(new_aliases)
    
    success = db.update_anime_field(actual_key, "aliases", list(existing_aliases))
    
    if success:
        await message.reply(
            f"✅ <b>Aliases added!</b>\n\n"
            f"📺 {anime_data.get('name_display', anime_name)}\n"
            f"🏷 <code>{', '.join(existing_aliases)}</code>"
        )
    else:
        await message.reply("❌ Failed!")

@bot.on_message(filters.command("set_start_img") & filters.private)
async def set_start_img_cmd(client, message):
    user_id = message.from_user.id
    if not state.is_admin(user_id):
        return
    
    if len(message.command) > 1:
        url = message.command[1]
        if not url.startswith(("http://", "https://")):
            await message.reply("❌ Invalid URL!")
            return
        
        try:
            test = await message.reply_photo(photo=url, caption="Testing...")
            db.set_setting("start_image", url)
            await test.edit_caption("✅ Banner updated!")
        except Exception as e:
            await message.reply(f"❌ Invalid image: {e}")
        return
    
    state.set(user_id, "SET_START_IMG", {})
    await message.reply("🖼 <b>Send new banner image URL:</b>\n\nOr <code>cancel</code>")

@bot.on_message(filters.command("set_start_msg") & filters.private)
async def set_start_msg_cmd(client, message):
    user_id = message.from_user.id
    if not state.is_admin(user_id):
        return
    
    if len(message.command) > 1:
        new_msg = " ".join(message.command[1:])
        db.set_setting("start_message", new_msg)
        await message.reply("✅ Welcome message updated!")
        return
    
    state.set(user_id, "SET_START_MSG", {})
    await message.reply("📝 <b>Send new welcome message:</b>\n\nOr <code>cancel</code>")

@bot.on_message(filters.command("list") & filters.private)
async def list_cmd(client, message):
    if not state.is_admin(message.from_user.id):
        return
    
    animes = db.get_all_animes()
    if not animes:
        await message.reply("📭 Database empty!")
        return
    
    items = sorted(animes.items(), key=lambda x: x[1].get("name_display", x[0]))
    
    for i in range(0, len(items), 15):
        chunk = items[i:i+15]
        text = f"📚 <b>LIST</b> ({i+1}-{min(i+15, len(items))}/{len(items)})\n\n"
        
        for idx, (key, data) in enumerate(chunk, i+1):
            display = data.get("name_display", key)
            aliases = len(data.get("aliases", []))
            text += f"<code>{idx}.</code> <b>{display}</b> 🏷{aliases}\n"
        
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.3)

@bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_cmd(client, message):
    if not state.is_admin(message.from_user.id):
        return
    
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message with <code>/broadcast</code>")
        return
    
    users = db.data.get("users", [])
    if not users:
        await message.reply("📭 No users!")
        return
    
    status = await message.reply(f"📡 Broadcasting to {len(users)} users...")
    
    sent, blocked = 0, 0
    for uid in users:
        try:
            await message.reply_to_message.copy(uid)
            sent += 1
            if sent % 50 == 0:
                await status.edit(f"📡 Progress: {sent}/{len(users)}")
            await asyncio.sleep(0.2)
        except UserIsBlocked:
            blocked += 1
        except Exception as e:
            logger.error(f"Broadcast failed for {uid}: {e}")
    
    await status.edit(f"📢 Done! ✅ {sent} | 🚫 {blocked}")

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message):
    user_id = message.from_user.id
    if state.get(user_id):
        state.clear(user_id)
        await message.reply("✅ Cancelled!")
    else:
        await message.reply("ℹ️ Nothing to cancel.")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN MESSAGE HANDLER - FIXED GROUP BEHAVIOR
# ═══════════════════════════════════════════════════════════════════════════════

async def send_anime_result(message: Message, anime_data: Dict[str, Any]):
    """Send anime result with YOUR EXACT CAPTION"""
    anime_key = anime_data.get("_key", "unknown")
    display_name = anime_data.get("name_display", anime_key)
    
    # Increment views
    if anime_key in db.data.get("animes", {}):
        db.data["animes"][anime_key]["views"] = anime_data.get("views", 0) + 1
        db.save()
    
    # Add user
    db.add_user(message.from_user.id)
    
    # YOUR EXACT CAPTION
    caption = (
        f"<blockquote>✨ <b>{display_name.upper()}</b> ✨</blockquote>\n\n"
        f"<b><blockquote>📖 {anime_data.get('desc', 'No description')}</blockquote></b>\n\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"🔰 <b>FOR MORE JOIN:</b>\n"
        f"<blockquote>👉 @KENSHIN_ANIME\n"
        f"👉 @MANWHA_VERSE</blockquote>"
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 DOWNLOAD / WATCH NOW", url=anime_data.get("download_link", CHANNEL_LINK))]
    ])
    
    try:
        await message.reply_photo(
            photo=anime_data.get("image_url"),
            caption=caption,
            reply_markup=buttons
        )
    except Exception as e:
        logger.error(f"Photo error: {e}")
        await message.reply(caption, reply_markup=buttons)

@bot.on_message(filters.text & (filters.private | filters.group))
async def main_handler(client, message):
    """Main handler - Fixed for groups and edit"""
    user_id = message.from_user.id
    is_group = message.chat.type != "private"
    text = clean_text(message.text, is_group)
    text_lower = text.lower().strip()
    
    if not text or text.startswith("/"):
        return
    
    # Handle cancel
    if text_lower == "cancel":
        if state.get(user_id):
            state.clear(user_id)
            await message.reply("✅ Cancelled!")
        else:
            await message.reply("ℹ️ Nothing to cancel.")
        return
    
    # Admin state machine - ONLY IN PRIVATE
    if not is_group and state.is_admin(user_id):
        st = state.get(user_id)
        if st:
            current_state = st.get("state")
            data = st.get("data", {})
            
            logger.info(f"Admin {user_id} in state: {current_state}, text: {text[:50]}")
            
            # ADD ANIME FLOW
            if current_state == "ADD_NAME":
                if len(text) < 2:
                    await message.reply("❌ Name too short!")
                    return
                
                existing = db.get_anime(text)
                if existing:
                    await message.reply(f"⚠️ <b>'{text}' already exists!</b>\nSend different name:")
                    return
                
                state.set(user_id, "ADD_IMAGE", {
                    "name": text,
                    "name_lower": text.lower().strip()
                })
                await message.reply(f"✅ <b>Name:</b> <code>{text}</code>\n\n<b>Step 2/5: Image URL</b>")
                return
            
            if current_state == "ADD_IMAGE":
                if not text.startswith(("http://", "https://")):
                    await message.reply("❌ Invalid URL!")
                    return
                
                state.set(user_id, "ADD_LINK", {**data, "image": text})
                await message.reply(f"✅ <b>Image saved!</b>\n\n<b>Step 3/5: Download Link</b>")
                return
            
            if current_state == "ADD_LINK":
                if not text.startswith(("http://", "https://", "t.me/")):
                    await message.reply("❌ Invalid link!")
                    return
                
                state.set(user_id, "ADD_DESC", {**data, "link": text})
                await message.reply(f"✅ <b>Link saved!</b>\n\n<b>Step 4/5: Description</b>")
                return
            
            if current_state == "ADD_DESC":
                if len(text) < 10:
                    await message.reply(f"❌ Too short! ({len(text)} chars, need 10+)")
                    return
                
                state.set(user_id, "ADD_ALIASES", {**data, "desc": text})
                await message.reply(
                    f"✅ <b>Description saved!</b>\n\n"
                    f"<b>Step 5/5: Aliases (Optional)</b>\n"
                    f"Send aliases separated by commas, or <code>skip</code>:"
                )
                return
            
            if current_state == "ADD_ALIASES":
                aliases = []
                if text_lower != "skip":
                    aliases = [a.strip() for a in text.split(",") if a.strip()]
                
                anime_data = {
                    "name_display": data["name"],
                    "image_url": data["image"],
                    "download_link": data["link"],
                    "desc": data["desc"],
                    "aliases": aliases,
                    "added_by": user_id,
                    "added_at": datetime.now().isoformat(),
                    "views": 0
                }
                
                success = db.add_anime(data["name_lower"], anime_data)
                
                if success:
                    alias_text = ", ".join(aliases) if aliases else "None"
                    await message.reply(
                        f"╔════════════════════════════════════╗\n"
                        f"║     🎯 SUCCESS! ANIME ADDED          ║\n"
                        f"╚════════════════════════════════════╝\n\n"
                        f"✅ <b>{data['name']}</b> added!\n\n"
                        f"🏷 Aliases: <code>{alias_text}</code>\n\n"
                        f"🎉 Users can now search!\n\n"
                        f"Add another? Use /add_ani"
                    )
                else:
                    await message.reply("❌ <b>Failed to save!</b>")
                
                state.clear(user_id)
                return
            
            # ═════════════════════════════════════════════════════════════
            # FIXED EDIT ANIME FLOW
            # ═════════════════════════════════════════════════════════════
            if current_state == "EDIT_SELECT":
                anime_list = data.get("anime_list", [])
                selected_key = None
                
                logger.info(f"EDIT_SELECT: User sent '{text}', anime_list has {len(anime_list)} items")
                
                # Check if number input
                if text.isdigit():
                    num = int(text)
                    if 1 <= num <= len(anime_list):
                        selected_key = anime_list[num - 1][0]  # Get the key
                        logger.info(f"Selected by number: {num} -> {selected_key}")
                    else:
                        await message.reply(f"❌ Invalid number! Send 1-{len(anime_list)}:")
                        return
                else:
                    # Search by name/alias
                    anime_data = db.get_anime(text)
                    if anime_data:
                        selected_key = anime_data.get("_key", text.lower())
                        logger.info(f"Selected by name: {selected_key}")
                    else:
                        await message.reply(
                            f"❌ '<code>{text}</code>' not found!\n\n"
                            f"Send a number from the list (1-{len(anime_list)}) or exact name:"
                        )
                        return
                
                # Get full data
                anime_data = db.get_anime(selected_key)
                if not anime_data:
                    await message.reply("❌ Error loading anime data!")
                    state.clear(user_id)
                    return
                
                actual_key = anime_data.get("_key", selected_key)
                display_name = anime_data.get("name_display", actual_key)
                
                await message.reply(
                    f"<b>✏️ EDITING: {display_name}</b>\n\n"
                    f"<b>Current Data:</b>\n\n"
                    f"1️⃣ <b>Name:</b> <code>{display_name}</code>\n"
                    f"2️⃣ <b>Image:</b> <code>{anime_data.get('image_url', 'N/A')[:50]}...</code>\n"
                    f"3️⃣ <b>Link:</b> <code>{anime_data.get('download_link', 'N/A')[:50]}...</code>\n"
                    f"4️⃣ <b>Desc:</b> <code>{anime_data.get('desc', 'N/A')[:80]}...</code>\n"
                    f"5️⃣ <b>Aliases:</b> <code>{', '.join(anime_data.get('aliases', []))}</code>\n\n"
                    f"✏️ <b>Send 1-5 to edit:</b>\n❌ <code>cancel</code> to abort"
                )
                
                state.set(user_id, "EDIT_FIELD", {
                    "edit_target": actual_key,
                    "anime_data": anime_data
                })
                return
            
            if current_state == "EDIT_FIELD":
                choice = text.strip()
                if choice not in ["1", "2", "3", "4", "5"]:
                    await message.reply("❌ Send <code>1</code>-<code>5</code>:")
                    return
                
                field_map = {
                    "1": ("name_display", "Name"),
                    "2": ("image_url", "Image URL"),
                    "3": ("download_link", "Download Link"),
                    "4": ("desc", "Description"),
                    "5": ("aliases", "Aliases (comma separated)")
                }
                
                field, field_name = field_map[choice]
                current_value = data["anime_data"].get(field, "N/A")
                if isinstance(current_value, list):
                    current_value = ", ".join(current_value)
                
                await message.reply(
                    f"✏️ <b>Editing {field_name}</b>\n\n"
                    f"<b>Current:</b> <code>{current_value[:200]}</code>\n\n"
                    f"Send new {field_name}:"
                )
                
                state.set(user_id, "EDIT_VALUE", {
                    **data,
                    "edit_field": field,
                    "edit_field_name": field_name
                })
                return
            
            if current_state == "EDIT_VALUE":
                target = data["edit_target"]
                field = data["edit_field"]
                field_name = data["edit_field_name"]
                
                if field == "aliases":
                    value = [a.strip() for a in text.split(",") if a.strip()]
                else:
                    value = text
                
                success = db.update_anime_field(target, field, value)
                
                if success:
                    await message.reply(f"✅ <b>{field_name}</b> updated for <code>{target}</code>!")
                else:
                    await message.reply("❌ <b>Update failed!</b>")
                
                state.clear(user_id)
                return
            
            # DELETE CONFIRM
            if current_state == "DELETE_CONFIRM":
                if text_lower == "yes":
                    target = data.get("target")
                    display = data.get("display_name")
                    
                    if db.delete_anime(target):
                        await message.reply(f"🗑 <b>'{display}' deleted!</b>")
                    else:
                        await message.reply("❌ <b>Failed!</b>")
                else:
                    await message.reply("❌ Cancelled.")
                
                state.clear(user_id)
                return
            
            # SETTINGS
            if current_state == "SET_START_IMG":
                if not text.startswith(("http://", "https://")):
                    await message.reply("❌ Invalid URL!")
                    return
                
                try:
                    test = await message.reply_photo(photo=text, caption="Testing...")
                    db.set_setting("start_image", text)
                    await test.edit_caption("✅ Banner updated!")
                except Exception as e:
                    await message.reply(f"❌ Error: {e}")
                
                state.clear(user_id)
                return
            
            if current_state == "SET_START_MSG":
                db.set_setting("start_message", text)
                await message.reply("✅ Welcome message updated!")
                state.clear(user_id)
                return
    
    # ═════════════════════════════════════════════════════════════════
    # ANIME SEARCH - DIFFERENT BEHAVIOR FOR PRIVATE VS GROUP
    # ═════════════════════════════════════════════════════════════════
    
    if len(text) < 2:
        return
    
    # Search for anime
    result = SearchEngine.find_anime_in_text(text)
    
    if result:
        # Found match - send result (works in both private and group)
        await send_anime_result(message, result)
    else:
        # No match found
        if not is_group:
            # PRIVATE CHAT: Show no match message
            await message.reply(
                f"🔍 <b>No match for '</b><code>{text[:40]}</code><b>'</b>\n\n"
                f"Try different spelling or /report to request this anime."
            )
        # GROUP CHAT: Silent - no message sent
        # This prevents spam in groups when random text doesn't match

# ═══════════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     🔥 KENSHIN ANIME BOT v4.3 - FIXED 🔥                        ║")
    print("║     Edit Fixed | Group Silent | Private No-Match                ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"💾 Database: {DB_FILE}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("Starting bot...")
    
    bot.run()
