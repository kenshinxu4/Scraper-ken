#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           🔥 KENSHIN ANIME BOT - ULTIMATE EDITION v4.1 🔥                    ║
║              Fixed Search | Exact Match Priority | Smart Fuzzy                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher

from pyrogram import Client, filters, errors, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import UserIsBlocked, MessageNotModified

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("kenshin_bot.log")
    ]
)
logger = logging.getLogger("KenshinBotUltimate")

# Environment Configuration
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").replace("@", "")

# Paths & URLs
DB_FILE = os.environ.get("DB_FILE", "/data/kenshin_ultimate.json")
DEFAULT_START_IMAGE = "https://files.catbox.moe/v4oy6s.jpg"
CHANNEL_LINK = "https://t.me/KENSHIN_ANIME"
SUPPORT_GROUP = "https://t.me/KENSHIN_ANIME_CHAT"
OWNER_USERNAME = "@KENSHIN_ANIME_OWNER"

# Fuzzy Matching Threshold (0-100)
FUZZY_THRESHOLD = 60  # Thoda kam kiya for better matching

# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED DATABASE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class UltimateDatabase:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: Dict[str, Any] = {}
        self._ensure_dir()
        self._load_or_init()
        self._migrate_v4()
    
    def _ensure_dir(self):
        db_dir = os.path.dirname(self.filepath)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    def _load_or_init(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(f"Database loaded: {len(self.data.get('animes', {}))} animes")
                return
            except Exception as e:
                logger.error(f"DB Load Error: {e}")
        
        self.data = {
            "users": [],
            "animes": {},
            "aliases": {},
            "settings": {
                "start_image": DEFAULT_START_IMAGE,
                "start_message": None,
                "fuzzy_threshold": FUZZY_THRESHOLD
            },
            "stats": {
                "total_searches": 0,
                "successful_searches": 0,
                "popular_animes": {}
            }
        }
        self.save()
        logger.info("Initialized new database")
    
    def _migrate_v4(self):
        """Migrate to v4 format with aliases support"""
        migrated = False
        for name, data in list(self.data.get("animes", {}).items()):
            if "description" in data and "desc" not in data:
                data["desc"] = data.pop("description")
                migrated = True
            if "views" not in data:
                data["views"] = 0
                migrated = True
            if "aliases" not in data:
                data["aliases"] = []
                migrated = True
        
        if migrated:
            self.save()
            logger.info("Database migrated to v4 format")
    
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
            
            # Register aliases
            aliases = data.get("aliases", [])
            for alias in aliases:
                alias_lower = alias.lower().strip()
                self.data["aliases"][alias_lower] = name_lower
            
            return self.save()
        except Exception as e:
            logger.error(f"Add anime failed: {e}")
            return False
    
    def get_anime(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get anime by name - checks exact, aliases, and partial matches
        """
        name_lower = name.lower().strip()
        
        # 1. Direct match
        if name_lower in self.data.get("animes", {}):
            result = self.data["animes"][name_lower].copy()
            result["_matched_name"] = name_lower
            return result
        
        # 2. Alias match
        if name_lower in self.data.get("aliases", {}):
            original_name = self.data["aliases"][name_lower]
            if original_name in self.data.get("animes", {}):
                result = self.data["animes"][original_name].copy()
                result["_matched_name"] = original_name
                return result
        
        # 3. Check display names (case insensitive)
        for key, data in self.data.get("animes", {}).items():
            display = data.get("name_display", "").lower().strip()
            if display == name_lower:
                result = data.copy()
                result["_matched_name"] = key
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
                    # Refresh alias mappings
                    for alias, target in list(self.data.get("aliases", {}).items()):
                        if target == name_lower:
                            del self.data["aliases"][alias]
                    for alias in value:
                        self.data["aliases"][alias.lower().strip()] = name_lower
                
                return self.save()
            return False
        except Exception as e:
            logger.error(f"Update field failed: {e}")
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
            logger.error(f"Delete anime failed: {e}")
            return False
    
    def add_user(self, user_id: int) -> bool:
        if user_id not in self.data.get("users", []):
            self.data["users"].append(user_id)
            return self.save()
        return True
    
    def get_user_count(self) -> int:
        return len(self.data.get("users", []))
    
    def get_setting(self, key: str, default=None):
        return self.data.get("settings", {}).get(key, default)
    
    def set_setting(self, key: str, value: Any) -> bool:
        self.data["settings"][key] = value
        return self.save()
    
    def increment_search_stat(self, anime_name: str, success: bool = True):
        self.data["stats"]["total_searches"] = self.data["stats"].get("total_searches", 0) + 1
        if success:
            self.data["stats"]["successful_searches"] = self.data["stats"].get("successful_searches", 0) + 1
        
        popular = self.data["stats"].get("popular_animes", {})
        popular[anime_name] = popular.get(anime_name, 0) + 1
        self.data["stats"]["popular_animes"] = popular
        
        self.save()
    
    def get_stats(self) -> Dict[str, Any]:
        return self.data.get("stats", {})

db = UltimateDatabase(DB_FILE)

# ═══════════════════════════════════════════════════════════════════════════════
# FIXED FUZZY SEARCH ENGINE - PRIORITIZES EXACT MATCHES
# ═══════════════════════════════════════════════════════════════════════════════

class FuzzySearchEngine:
    """
    FIXED: Now properly finds exact matches and partial matches
    Priority: Exact > Contains > Fuzzy
    """
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for matching"""
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', ' ', text)  # Special chars ko space me convert
        text = ' '.join(text.split())  # Extra spaces remove
        return text
    
    @staticmethod
    def search_anime(query: str) -> Optional[Dict[str, Any]]:
        """
        MAIN SEARCH FUNCTION - Fixed Version
        Returns anime data or None
        """
        if not query or len(query) < 1:
            return None
        
        query_norm = FuzzySearchEngine.normalize_text(query)
        all_animes = db.get_all_animes()
        
        if not all_animes:
            return None
        
        best_match = None
        best_score = 0.0
        best_key = None
        
        for key, data in all_animes.items():
            # Get all possible names for this anime
            names_to_check = [key]
            
            # Add display name
            display = data.get("name_display", "")
            if display:
                names_to_check.append(display.lower().strip())
            
            # Add aliases
            for alias in data.get("aliases", []):
                names_to_check.append(alias.lower().strip())
            
            # Check each name
            for name in names_to_check:
                if not name:
                    continue
                
                name_norm = FuzzySearchEngine.normalize_text(name)
                
                # PRIORITY 1: Exact match (100 points)
                if query_norm == name_norm:
                    return {**data, "_matched_name": key, "_match_score": 100.0}
                
                # PRIORITY 2: Query is substring of name (90-95 points)
                if query_norm in name_norm:
                    score = 90 + (len(query_norm) / len(name_norm) * 5)
                    if score > best_score:
                        best_score = score
                        best_match = data
                        best_key = key
                    continue
                
                # PRIORITY 3: Name is substring of query (85-89 points)
                if name_norm in query_norm:
                    score = 85 + (len(name_norm) / len(query_norm) * 4)
                    if score > best_score:
                        best_score = score
                        best_match = data
                        best_key = key
                    continue
                
                # PRIORITY 4: Word matching (70-84 points)
                query_words = set(query_norm.split())
                name_words = set(name_norm.split())
                
                if query_words and name_words:
                    common_words = query_words & name_words
                    if common_words:
                        # Score based on how many words match
                        word_score = len(common_words) / max(len(query_words), len(name_words))
                        score = 70 + (word_score * 14)
                        
                        # Bonus if first word matches
                        if query_norm.split()[0] == name_norm.split()[0]:
                            score += 5
                        
                        if score > best_score:
                            best_score = score
                            best_match = data
                            best_key = key
                        continue
                
                # PRIORITY 5: Fuzzy/Sequence matching (0-69 points)
                if len(query_norm) >= 3 and len(name_norm) >= 3:
                    seq_ratio = SequenceMatcher(None, query_norm, name_norm).ratio()
                    # Only consider if ratio is decent
                    if seq_ratio > 0.5:
                        score = seq_ratio * 60
                        if score > best_score:
                            best_score = score
                            best_match = data
                            best_key = key
        
        # Return if above threshold
        threshold = db.get_setting("fuzzy_threshold", FUZZY_THRESHOLD)
        if best_match and best_score >= threshold:
            return {**best_match, "_matched_name": best_key, "_match_score": best_score}
        
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class StateManager:
    def __init__(self):
        self.states: Dict[int, Dict[str, Any]] = {}
    
    def set_state(self, user_id: int, state: str, data: Dict[str, Any] = None):
        self.states[user_id] = {
            "state": state,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"State set for user {user_id}: {state}")
    
    def get_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.states.get(user_id)
    
    def clear_state(self, user_id: int):
        if user_id in self.states:
            del self.states[user_id]
            logger.info(f"State cleared for user {user_id}")
    
    def is_admin(self, user_id: int) -> bool:
        return user_id == ADMIN_ID

state_mgr = StateManager()

# ═══════════════════════════════════════════════════════════════════════════════
# BOT INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

bot = Client(
    "kenshin_ultimate",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
)

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def clean_text(text: str, is_group: bool = False) -> str:
    """Clean user input"""
    if not text:
        return ""
    
    if is_group and BOT_USERNAME:
        text = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.IGNORECASE)
    
    text = ' '.join(text.split()).strip()
    return text

# ═══════════════════════════════════════════════════════════════════════════════
# USER COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("start") & filters.private)
async def start_private(client: Client, message: Message):
    """Start command"""
    user_id = message.from_user.id
    db.add_user(user_id)
    
    start_img = db.get_setting("start_image", DEFAULT_START_IMAGE)
    custom_msg = db.get_setting("start_message")
    
    if custom_msg:
        welcome_text = custom_msg
    else:
        welcome_text = (
            "🌸 <b>Welcome to KENSHIN ANIME Search Ultimate!</b> 🌸\n\n"
            "<blockquote>Official bot of ⚜️ @KENSHIN_ANIME ⚜️</blockquote>\n\n"
            "🍿 I provide high-quality Anime links instantly with <b>Smart Search!</b>\n\n"
            "👉 <b>How to find Anime?</b>\n"
            "Just type the name. I can detect it even with typos!\n"
            "💡 <code>Examples:</code>\n"
            "• <code>solo</code> → Solo Leveling\n"
            "• <code>jjk</code> → Jujutsu Kaisen\n"
            "• <code>couple of cuckoos</code> → A Couple of Cuckoos\n\n"
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
    """Group start"""
    await message.reply(
        f"👋 <b>Hey {message.from_user.first_name}!</b>\n\n"
        f"🍿 I'm Kenshin Anime Bot Ultimate!\n"
        f"Type any anime name and I'll find it!\n\n"
        f"<i>DM me for full features → @{BOT_USERNAME or 'Bot'}</i>"
    )

@bot.on_message(filters.command("help") & (filters.private | filters.group))
async def help_cmd(client: Client, message: Message):
    """Help command"""
    is_admin = state_mgr.is_admin(message.from_user.id)
    
    text = (
        "🛠 <b>USER MENU</b>\n\n"
        "• /start - Wake up bot\n"
        "• /help - This menu\n"
        "• /report &lt;msg&gt; - Report issue\n"
        "• /search &lt;name&gt; - Advanced search\n\n"
        "🔍 <b>SMART SEARCH TIPS:</b>\n"
        "• Use partial names: <code>solo</code> → Solo Leveling\n"
        "• Use abbreviations: <code>jjk</code> → Jujutsu Kaisen\n"
        "• Use aliases: <code>tonikawa</code> → Tonikaku Kawaii\n\n"
        "<b>Just type any anime name directly!</b>"
    )
    
    if is_admin:
        text += (
            "\n\n⚡ <b>ADMIN PANEL</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "• /add_ani - Add new anime\n"
            "• /edit_ani - Edit anime\n"
            "• /delete_ani - Delete anime\n"
            "• /add_alias - Add aliases\n"
            "• /set_start_img - Change banner\n"
            "• /set_start_msg - Edit welcome\n"
            "• /set_threshold - Search sensitivity\n"
            "• /bulk - Bulk upload\n"
            "• /list - All animes\n"
            "• /broadcast - Message all users\n"
            "• /cancel - Cancel operation"
        )
    
    await message.reply(text)

@bot.on_message(filters.command("report") & (filters.private | filters.group))
async def report_cmd(client: Client, message: Message):
    """Report command"""
    if len(message.command) < 2:
        await message.reply(
            "📝 <b>Report Format:</b>\n"
            "<code>/report Your message here</code>"
        )
        return
    
    report_text = " ".join(message.command[1:])
    user = message.from_user
    
    if len(report_text) < 10:
        await message.reply("❌ Report too short! Min 10 characters.")
        return
    
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📢 <b>REPORT</b>\n\n"
            f"From: {user.first_name}\n"
            f"ID: <code>{user.id}</code>\n\n"
            f"📝 {report_text}"
        )
        await message.reply("✅ Report sent!")
    except Exception as e:
        logger.error(f"Report failed: {e}")
        await message.reply("❌ Failed to send.")

@bot.on_message(filters.command("search") & (filters.private | filters.group))
async def search_cmd(client: Client, message: Message):
    """Explicit search"""
    if len(message.command) < 2:
        await message.reply("🔍 <b>Usage:</b> <code>/search anime name</code>")
        return
    
    query = " ".join(message.command[1:])
    await perform_anime_search(message, query)

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("add_ani") & filters.private)
async def add_ani_cmd(client: Client, message: Message):
    """Add anime"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
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
                
                success = db.add_anime(name.lower(), {
                    "name_display": name,
                    "image_url": img,
                    "download_link": link,
                    "desc": desc,
                    "aliases": aliases,
                    "added_by": user_id,
                    "added_at": datetime.now().isoformat(),
                    "views": 0
                })
                
                if success:
                    await message.reply(f"✅ <b>{name}</b> added!")
                else:
                    await message.reply("❌ Failed!")
                return
    
    # Interactive
    state_mgr.set_state(user_id, "ADD_NAME", {})
    
    await message.reply(
        "╔════════════════════════════════════╗\n"
        "║     🚀 ADD NEW ANIME - STEP 1/5      ║\n"
        "╚════════════════════════════════════╝\n\n"
        "<b>Send the exact anime name:</b>\n\n"
        "💡 Examples:\n"
        "• <code>Solo Leveling</code>\n"
        "• <code>Jujutsu Kaisen</code>\n"
        "• <code>A Couple of Cuckoos</code>\n\n"
        "❌ Send <code>cancel</code> to abort."
    )

@bot.on_message(filters.command("edit_ani") & filters.private)
async def edit_ani_cmd(client: Client, message: Message):
    """Edit anime"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    animes = db.get_all_animes()
    if not animes:
        await message.reply("📭 No anime in database!")
        return
    
    items = sorted(animes.items(), key=lambda x: x[1].get("name_display", x[0]))
    
    list_text = "╔════════════════════════════════════╗\n║     ✏️ EDIT ANIME                    ║\n╚════════════════════════════════════╝\n\n<b>Available Animes:</b>\n\n"
    
    anime_list = []
    for i, (name, data) in enumerate(items[:30], 1):
        display = data.get("name_display", name)
        list_text += f"<code>{i:2d}.</code> {display}\n"
        anime_list.append((name, display))
    
    if len(items) > 30:
        list_text += f"\n<i>... and {len(items) - 30} more</i>\n"
    
    list_text += "\n✏️ <b>Send number or name to edit:</b>\n❌ <code>cancel</code> to abort."
    
    state_mgr.set_state(user_id, "EDIT_SELECT", {"anime_list": anime_list})
    await message.reply(list_text, disable_web_page_preview=True)

@bot.on_message(filters.command("delete_ani") & filters.private)
async def delete_ani_cmd(client: Client, message: Message):
    """Delete anime"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
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
    actual_name = anime_data.get("_matched_name", name.lower())
    
    state_mgr.set_state(user_id, "DELETE_CONFIRM", {
        "target": actual_name,
        "display_name": display_name
    })
    
    await message.reply(
        f"⚠️ <b>Delete '{display_name}'?</b>\n\n"
        f"Send <code>yes</code> to confirm, or <code>cancel</code>."
    )

@bot.on_message(filters.command("add_alias") & filters.private)
async def add_alias_cmd(client: Client, message: Message):
    """Add alias"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    if len(message.command) < 3:
        await message.reply(
            "🏷 <b>Usage:</b> <code>/add_alias anime | alias1, alias2</code>"
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
    
    actual_name = anime_data.get("_matched_name", anime_name.lower())
    existing_aliases = set(anime_data.get("aliases", []))
    existing_aliases.update(new_aliases)
    
    success = db.update_anime_field(actual_name, "aliases", list(existing_aliases))
    
    if success:
        await message.reply(
            f"✅ <b>Aliases added!</b>\n\n"
            f"📺 {anime_data.get('name_display', anime_name)}\n"
            f"🏷 <code>{', '.join(existing_aliases)}</code>"
        )
    else:
        await message.reply("❌ Failed!")

@bot.on_message(filters.command("set_start_img") & filters.private)
async def set_start_img_cmd(client: Client, message: Message):
    """Set banner"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        return
    
    if len(message.command) > 1:
        url = message.command[1]
        if not url.startswith(("http://", "https://")):
            await message.reply("❌ Invalid URL!")
            return
        
        try:
            test = await message.reply_photo(photo=url, caption="Testing...")
            db.set_setting("start_image", url)
            await test.edit_caption(f"✅ Banner updated!")
        except Exception as e:
            await message.reply(f"❌ Invalid image: {e}")
        return
    
    state_mgr.set_state(user_id, "SET_START_IMG", {})
    await message.reply("🖼 <b>Send new image URL:</b>\n\nOr <code>cancel</code>")

@bot.on_message(filters.command("set_start_msg") & filters.private)
async def set_start_msg_cmd(client: Client, message: Message):
    """Set welcome message"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        return
    
    if len(message.command) > 1:
        new_msg = " ".join(message.command[1:])
        db.set_setting("start_message", new_msg)
        await message.reply("✅ Welcome message updated!")
        return
    
    state_mgr.set_state(user_id, "SET_START_MSG", {})
    await message.reply("📝 <b>Send new welcome message:</b>\n\nOr <code>cancel</code>")

@bot.on_message(filters.command("set_threshold") & filters.private)
async def set_threshold_cmd(client: Client, message: Message):
    """Set fuzzy threshold"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        return
    
    if len(message.command) > 1:
        try:
            threshold = int(message.command[1])
            if 30 <= threshold <= 100:
                db.set_setting("fuzzy_threshold", threshold)
                await message.reply(f"✅ Threshold set to <code>{threshold}%</code>")
            else:
                await message.reply("❌ Must be 30-100!")
        except ValueError:
            await message.reply("❌ Invalid number!")
        return
    
    current = db.get_setting("fuzzy_threshold", FUZZY_THRESHOLD)
    await message.reply(
        f"🎯 <b>Fuzzy Threshold</b>: <code>{current}%</code>\n\n"
        f"<b>Usage:</b> <code>/set_threshold 70</code>\n"
        f"Lower = More results, Higher = Stricter"
    )

@bot.on_message(filters.command("bulk") & filters.private)
async def bulk_cmd(client: Client, message: Message):
    """Bulk upload guide"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    await message.reply(
        "📦 <b>BULK UPLOAD</b>\n\n"
        "<b>Format:</b>\n"
        "<code>Name | Image URL | Link | Description | Aliases</code>\n\n"
        "<b>Example:</b>\n"
        "<pre>Solo Leveling | https://img.com/solo.jpg | https://t.me/... | A weak hunter... | sl, solo lev</pre>\n\n"
        "Send <code>.txt</code> file to process."
    )

@bot.on_message(filters.command("list") & filters.private)
async def list_cmd(client: Client, message: Message):
    """List animes"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    animes = db.get_all_animes()
    if not animes:
        await message.reply("📭 Database empty!")
        return
    
    items = sorted(animes.items(), key=lambda x: x[1].get("name_display", x[0]))
    
    for i in range(0, len(items), 15):
        chunk = items[i:i+15]
        text = f"📚 <b>LIST</b> ({i+1}-{min(i+15, len(items))}/{len(items)})\n\n"
        
        for idx, (name, data) in enumerate(chunk, i+1):
            display = data.get("name_display", name)
            views = data.get("views", 0)
            text += f"<code>{idx}.</code> <b>{display}</b> 👁{views}\n"
        
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.3)

@bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_cmd(client: Client, message: Message):
    """Broadcast"""
    if not state_mgr.is_admin(message.from_user.id):
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
            logger.error(f"Broadcast to {uid} failed: {e}")
    
    await status.edit(f"📢 Done! ✅ {sent} | 🚫 {blocked}")

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client: Client, message: Message):
    """Cancel operation"""
    user_id = message.from_user.id
    
    if state_mgr.get_state(user_id):
        state_mgr.clear_state(user_id)
        await message.reply("✅ Cancelled!")
    else:
        await message.reply("ℹ️ Nothing to cancel.")

# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT HANDLER (BULK UPLOAD)
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.document & filters.private)
async def doc_handler(client: Client, message: Message):
    """Handle bulk upload"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    if not message.document.file_name.endswith('.txt'):
        return
    
    status = await message.reply("⏳ Processing...")
    
    try:
        path = await message.download()
        added, updated, errors = 0, 0, []
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '|' not in line:
                errors.append(f"Line {line_num}: No separator")
                continue
            
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 4:
                errors.append(f"Line {line_num}: Incomplete")
                continue
            
            name, img, link, desc = parts[0], parts[1], parts[2], parts[3]
            aliases = [a.strip() for a in parts[4].split(',')] if len(parts) > 4 else []
            
            if not all([name, img, link]):
                errors.append(f"Line {line_num}: Missing fields")
                continue
            
            # Check if exists
            existing = db.get_anime(name)
            if existing:
                actual_name = existing.get("_matched_name", name.lower())
                db.update_anime_field(actual_name, "image_url", img)
                db.update_anime_field(actual_name, "download_link", link)
                db.update_anime_field(actual_name, "desc", desc)
                if aliases:
                    existing_aliases = set(existing.get("aliases", []))
                    existing_aliases.update(aliases)
                    db.update_anime_field(actual_name, "aliases", list(existing_aliases))
                updated += 1
            else:
                db.add_anime(name, {
                    "name_display": name,
                    "image_url": img,
                    "download_link": link,
                    "desc": desc,
                    "aliases": aliases,
                    "added_by": message.from_user.id,
                    "added_at": datetime.now().isoformat(),
                    "views": 0
                })
                added += 1
        
        if os.path.exists(path):
            os.remove(path)
        
        result = f"📦 <b>Complete!</b>\n\n✅ Added: <code>{added}</code>\n🔄 Updated: <code>{updated}</code>\n❌ Errors: <code>{len(errors)}</code>"
        await status.edit(result)
        
    except Exception as e:
        logger.error(f"Bulk error: {e}")
        await status.edit(f"❌ Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN MESSAGE HANDLER - FIXED SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

async def perform_anime_search(message: Message, query: str):
    """Perform search and send result"""
    if not query or len(query) < 1:
        await message.reply("❌ Query too short!")
        return
    
    # Use fixed fuzzy search
    result = FuzzySearchEngine.search_anime(query)
    
    if result:
        anime_name = result.get("_matched_name", "unknown")
        display_name = result.get("name_display", anime_name)
        
        # Increment views
        if anime_name in db.data.get("animes", {}):
            db.data["animes"][anime_name]["views"] = result.get("views", 0) + 1
            db.save()
        
        # Update stats
        db.increment_search_stat(anime_name, True)
        
        # YOUR EXACT CAPTION - NO CHANGES
        caption = (
            f"<blockquote>✨ <b>{display_name.upper()}</b> ✨</blockquote>\n\n"
            f"<b><blockquote>📖 {result.get('desc', 'No description')}</blockquote></b>\n\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
            f"🔰 <b>FOR MORE JOIN:</b>\n"
            f"<blockquote>👉 @KENSHIN_ANIME\n"
            f"👉 @MANWHA_VERSE</blockquote>"
        )
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 DOWNLOAD / WATCH NOW", url=result.get("download_link", CHANNEL_LINK))]
        ])
        
        try:
            await message.reply_photo(
                photo=result.get("image_url"),
                caption=caption,
                reply_markup=buttons
            )
        except Exception as e:
            logger.error(f"Photo error: {e}")
            await message.reply(caption, reply_markup=buttons)
        
        db.add_user(message.from_user.id)
    else:
        # No match
        db.increment_search_stat("unknown", False)
        
        # Get suggestions
        suggestions = get_search_suggestions(query)
        
        text = f"🔍 <b>No match for '</b><code>{query[:40]}</code><b>'</b>\n\n"
        
        if suggestions:
            text += "<b>Did you mean:</b>\n"
            for sug in suggestions[:5]:
                text += f"• <code>{sug}</code>\n"
            text += "\n"
        
        text += "Try different spelling or /report to request."
        
        await message.reply(text)

def get_search_suggestions(query: str) -> List[str]:
    """Get suggestions based on partial matches"""
    animes = db.get_all_animes()
    suggestions = []
    
    query_norm = FuzzySearchEngine.normalize_text(query)
    query_words = set(query_norm.split()) if query_norm else set()
    
    for name, data in animes.items():
        display = data.get("name_display", name)
        display_norm = FuzzySearchEngine.normalize_text(display)
        
        # Check word overlap
        display_words = set(display_norm.split()) if display_norm else set()
        if query_words & display_words:
            if display not in suggestions:
                suggestions.append(display)
        
        # Check aliases
        for alias in data.get("aliases", []):
            alias_norm = FuzzySearchEngine.normalize_text(alias)
            alias_words = set(alias_norm.split()) if alias_norm else set()
            if query_words & alias_words:
                if display not in suggestions:
                    suggestions.append(display)
                    break
    
    return suggestions[:5]

@bot.on_message(filters.text & (filters.private | filters.group))
async def main_handler(client: Client, message: Message):
    """Main handler with state machine and search"""
    user_id = message.from_user.id
    is_group = message.chat.type != "private"
    text = clean_text(message.text, is_group)
    text_lower = text.lower().strip()
    
    if not text:
        return
    
    # Skip commands
    if text.startswith("/"):
        return
    
    # Handle cancel
    if text_lower == "cancel":
        if state_mgr.get_state(user_id):
            state_mgr.clear_state(user_id)
            await message.reply("✅ Cancelled!")
        else:
            await message.reply("ℹ️ Nothing to cancel.")
        return
    
    # Admin state machine
    if not is_group and state_mgr.is_admin(user_id):
        state_info = state_mgr.get_state(user_id)
        
        if state_info:
            current_state = state_info.get("state")
            state_data = state_info.get("data", {})
            
            logger.info(f"Admin {user_id} in state: {current_state}")
            
            # ADD ANIME FLOW
            if current_state == "ADD_NAME":
                if len(text) < 2:
                    await message.reply("❌ Name too short!")
                    return
                
                existing = db.get_anime(text)
                if existing:
                    await message.reply(f"⚠️ <b>'{text}' already exists!</b>\n\nSend different name:")
                    return
                
                state_mgr.set_state(user_id, "ADD_IMAGE", {
                    "name": text,
                    "name_lower": text.lower().strip()
                })
                
                await message.reply(
                    f"✅ <b>Name:</b> <code>{text}</code>\n\n"
                    f"<b>Step 2/5: Image URL</b>\n"
                    f"Send anime poster image URL:"
                )
                return
            
            if current_state == "ADD_IMAGE":
                if not text.startswith(("http://", "https://")):
                    await message.reply("❌ Invalid URL! Must start with http:// or https://")
                    return
                
                # Test image
                try:
                    test_msg = await message.reply_photo(photo=text, caption="Testing...")
                    await test_msg.delete()
                    image_valid = True
                except Exception as e:
                    image_valid = False
                    logger.warning(f"Image test failed: {e}")
                
                if not image_valid:
                    await message.reply(
                        f"⚠️ <b>Warning:</b> Could not verify image.\n\n"
                        f"Send <code>yes</code> to use anyway, or send different URL:"
                    )
                    state_mgr.set_state(user_id, "ADD_IMAGE_CONFIRM", {
                        **state_data,
                        "pending_img": text
                    })
                    return
                
                state_mgr.set_state(user_id, "ADD_LINK", {
                    **state_data,
                    "image": text
                })
                
                await message.reply(
                    f"✅ <b>Image saved!</b>\n\n"
                    f"<b>Step 3/5: Download Link</b>\n"
                    f"Send Telegram or direct download link:"
                )
                return
            
            if current_state == "ADD_IMAGE_CONFIRM":
                if text_lower == "yes":
                    pending_img = state_data.get("pending_img")
                    state_mgr.set_state(user_id, "ADD_LINK", {
                        **state_data,
                        "image": pending_img
                    })
                    await message.reply(
                        f"✅ <b>Image accepted!</b>\n\n"
                        f"<b>Step 3/5: Download Link</b>"
                    )
                else:
                    if not text.startswith(("http://", "https://")):
                        await message.reply("❌ Invalid URL! Send <code>yes</code> or new URL:")
                        return
                    
                    state_mgr.set_state(user_id, "ADD_LINK", {
                        **state_data,
                        "image": text
                    })
                    await message.reply(f"✅ <b>New image saved!</b>\n\n<b>Step 3/5: Download Link</b>")
                return
            
            if current_state == "ADD_LINK":
                if not text.startswith(("http://", "https://", "t.me/")):
                    await message.reply("❌ Invalid link! Must be URL or t.me link:")
                    return
                
                state_mgr.set_state(user_id, "ADD_DESC", {
                    **state_data,
                    "link": text
                })
                
                await message.reply(
                    f"✅ <b>Link saved!</b>\n\n"
                    f"<b>Step 4/5: Description</b>\n"
                    f"Send synopsis (min 10 chars):"
                )
                return
            
            if current_state == "ADD_DESC":
                if len(text) < 10:
                    await message.reply(f"❌ Too short! ({len(text)} chars, need 10+)")
                    return
                
                state_mgr.set_state(user_id, "ADD_ALIASES", {
                    **state_data,
                    "desc": text
                })
                
                await message.reply(
                    f"✅ <b>Description saved!</b>\n\n"
                    f"<b>Step 5/5: Aliases (Optional)</b>\n"
                    f"Send alternate names separated by commas, or <code>skip</code>:\n\n"
                    f"<b>Examples:</b>\n"
                    f"• For Solo Leveling: <code>sl, solo lev, sung jinwoo</code>\n"
                    f"• For Jujutsu Kaisen: <code>jjk, jujutsu</code>"
                )
                return
            
            if current_state == "ADD_ALIASES":
                aliases = []
                if text_lower != "skip":
                    aliases = [a.strip() for a in text.split(",") if a.strip()]
                
                # Save anime
                anime_data = {
                    "name_display": state_data["name"],
                    "image_url": state_data["image"],
                    "download_link": state_data["link"],
                    "desc": state_data["desc"],
                    "aliases": aliases,
                    "added_by": user_id,
                    "added_at": datetime.now().isoformat(),
                    "views": 0
                }
                
                success = db.add_anime(state_data["name_lower"], anime_data)
                
                if success:
                    alias_text = ", ".join(aliases) if aliases else "None"
                    await message.reply(
                        f"╔════════════════════════════════════╗\n"
                        f"║     🎯 SUCCESS! ANIME ADDED          ║\n"
                        f"╚════════════════════════════════════╝\n\n"
                        f"✅ <b>{state_data['name']}</b> added!\n\n"
                        f"🏷 Aliases: <code>{alias_text}</code>\n\n"
                        f"🎉 Users can now search for this anime!\n\n"
                        f"Add another? Use /add_ani"
                    )
                    logger.info(f"Anime added: {state_data['name']}")
                else:
                    await message.reply("❌ <b>Failed to save!</b>")
                
                state_mgr.clear_state(user_id)
                return
            
            # EDIT ANIME FLOW
            if current_state == "EDIT_SELECT":
                anime_list = state_data.get("anime_list", [])
                selected_anime = None
                
                # Check if number input
                if text.isdigit():
                    num = int(text)
                    if 1 <= num <= len(anime_list):
                        selected_anime = anime_list[num - 1][0]
                    else:
                        await message.reply(f"❌ Invalid number! Choose 1-{len(anime_list)}:")
                        return
                else:
                    # Search by name
                    anime_data = db.get_anime(text)
                    if not anime_data:
                        await message.reply(
                            f"❌ Anime '<code>{text}</code>' not found!\n\n"
                            f"Send number from list or exact name:"
                        )
                        return
                    selected_anime = anime_data.get("_matched_name", text.lower())
                
                # Get full data
                anime_data = db.get_anime(selected_anime)
                if not anime_data:
                    await message.reply("❌ Error loading anime data!")
                    state_mgr.clear_state(user_id)
                    return
                
                actual_name = anime_data.get("_matched_name", selected_anime)
                display_name = anime_data.get("name_display", actual_name)
                
                await message.reply(
                    f"╔════════════════════════════════════╗\n"
                    f"║     ✏️ EDITING: {display_name[:20].upper()}...\n"
                    f"╚════════════════════════════════════╝\n\n"
                    f"<b>Current Data:</b>\n\n"
                    f"1️⃣ <b>Name:</b> <code>{display_name}</code>\n"
                    f"2️⃣ <b>Image:</b> <code>{anime_data.get('image_url', 'N/A')[:50]}...</code>\n"
                    f"3️⃣ <b>Link:</b> <code>{anime_data.get('download_link', 'N/A')[:50]}...</code>\n"
                    f"4️⃣ <b>Desc:</b> <code>{anime_data.get('desc', 'N/A')[:80]}...</code>\n"
                    f"5️⃣ <b>Aliases:</b> <code>{', '.join(anime_data.get('aliases', []))}</code>\n\n"
                    f"✏️ <b>What to edit?</b> Send <code>1</code>-<code>5</code>\n"
                    f"❌ Send <code>cancel</code> to abort"
                )
                
                state_mgr.set_state(user_id, "EDIT_FIELD", {
                    "edit_target": actual_name,
                    "anime_data": anime_data
                })
                return
            
            if current_state == "EDIT_FIELD":
                choice = text.strip()
                
                if choice not in ["1", "2", "3", "4", "5"]:
                    await message.reply("❌ Invalid choice! Send <code>1</code>-<code>5</code>:")
                    return
                
                field_map = {
                    "1": ("name_display", "Name"),
                    "2": ("image_url", "Image URL"),
                    "3": ("download_link", "Download Link"),
                    "4": ("desc", "Description"),
                    "5": ("aliases", "Aliases (comma separated)")
                }
                
                field, field_name = field_map[choice]
                current_value = state_data["anime_data"].get(field, "N/A")
                
                if isinstance(current_value, list):
                    current_value = ", ".join(current_value)
                
                await message.reply(
                    f"✏️ <b>Editing {field_name}</b>\n\n"
                    f"<b>Current:</b> <code>{current_value[:200]}</code>\n\n"
                    f"Send new {field_name}:"
                )
                
                state_mgr.set_state(user_id, "EDIT_VALUE", {
                    **state_data,
                    "edit_field": field,
                    "edit_field_name": field_name
                })
                return
            
            if current_state == "EDIT_VALUE":
                target = state_data["edit_target"]
                field = state_data["edit_field"]
                field_name = state_data["edit_field_name"]
                
                # Process value
                if field == "aliases":
                    value = [a.strip() for a in text.split(",") if a.strip()]
                else:
                    value = text
                
                # Update
                success = db.update_anime_field(target, field, value)
                
                if success:
                    await message.reply(
                        f"✅ <b>Updated successfully!</b>\n\n"
                        f"<b>{field_name}</b> changed for <code>{target}</code>"
                    )
                    logger.info(f"Anime edited: {target}, field: {field_name}")
                else:
                    await message.reply("❌ <b>Update failed!</b>")
                
                state_mgr.clear_state(user_id)
                return
            
            # DELETE CONFIRMATION
            if current_state == "DELETE_CONFIRM":
                if text_lower == "yes":
                    target = state_data.get("target")
                    display = state_data.get("display_name")
                    
                    if db.delete_anime(target):
                        await message.reply(f"🗑 <b>'{display}' deleted!</b>")
                        logger.info(f"Anime deleted: {target}")
                    else:
                        await message.reply("❌ <b>Deletion failed!</b>")
                else:
                    await message.reply("❌ Deletion cancelled.")
                
                state_mgr.clear_state(user_id)
                return
            
            # SETTINGS FLOWS
            if current_state == "SET_START_IMG":
                if not text.startswith(("http://", "https://")):
                    await message.reply("❌ Invalid URL!")
                    return
                
                try:
                    test = await message.reply_photo(photo=text, caption="Testing...")
                    db.set_setting("start_image", text)
                    await test.edit_caption(f"✅ Banner updated!")
                except Exception as e:
                    await message.reply(f"❌ Invalid image: {e}")
                
                state_mgr.clear_state(user_id)
                return
            
            if current_state == "SET_START_MSG":
                db.set_setting("start_message", text)
                await message.reply("✅ Welcome message updated!")
                state_mgr.clear_state(user_id)
                return
    
    # ANIME SEARCH (All users)
    # Search even for short queries (1+ chars)
    await perform_anime_search(message, text)

# ═══════════════════════════════════════════════════════════════════════════════
# RUN BOT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     🔥 KENSHIN ANIME BOT ULTIMATE v4.1 🔥                       ║")
    print("║     FIXED SEARCH | Exact Match Priority | Caption Preserved     ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"💾 Database: {DB_FILE}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🎯 Fuzzy Threshold: {FUZZY_THRESHOLD}%")
    print("Starting bot...")
    
    bot.run()
