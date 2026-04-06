#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           🔥 KENSHIN ANIME BOT - ULTIMATE EDITION v4.0 🔥                    ║
║              Advanced Fuzzy Search | Smart Matching | Pro Admin              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Features:
- Fuzzy search: "solo" → "Solo Leveling", "jjk" → "Jujutsu Kaisen"
- Multiple aliases per anime
- Robust Add/Edit with state management
- 1000+ lines of professional code
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
FUZZY_THRESHOLD = 65  # Lower = more lenient matching
PARTIAL_THRESHOLD = 75

# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED DATABASE ENGINE WITH MIGRATION
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
            logger.info(f"Created directory: {db_dir}")
    
    def _load_or_init(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(f"Database loaded: {len(self.data.get('animes', {}))} animes")
                return
            except Exception as e:
                logger.error(f"DB Load Error: {e}")
        
        # Initialize fresh database
        self.data = {
            "users": [],
            "animes": {},
            "aliases": {},  # alias -> anime_name mapping
            "settings": {
                "start_image": DEFAULT_START_IMAGE,
                "start_message": None,
                "fuzzy_threshold": FUZZY_THRESHOLD,
                "search_stats": {}
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
        
        # Check old format
        for name, data in list(self.data.get("animes", {}).items()):
            # Migrate description to desc
            if "description" in data and "desc" not in data:
                data["desc"] = data.pop("description")
                migrated = True
            
            # Ensure views field exists
            if "views" not in data:
                data["views"] = 0
                migrated = True
            
            # Ensure aliases field exists
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
    
    # ═════════════════════════════════════════════════════════════════
    # ANIME OPERATIONS
    # ═════════════════════════════════════════════════════════════════
    
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
        name_lower = name.lower().strip()
        
        # Direct match
        if name_lower in self.data.get("animes", {}):
            return self.data["animes"][name_lower]
        
        # Alias match
        if name_lower in self.data.get("aliases", {}):
            original_name = self.data["aliases"][name_lower]
            return self.data["animes"].get(original_name)
        
        return None
    
    def get_all_animes(self) -> Dict[str, Any]:
        return self.data.get("animes", {})
    
    def update_anime_field(self, name: str, field: str, value: Any) -> bool:
        try:
            name_lower = name.lower().strip()
            if name_lower in self.data.get("animes", {}):
                self.data["animes"][name_lower][field] = value
                
                # If updating aliases, refresh alias mappings
                if field == "aliases":
                    # Remove old aliases
                    for alias, target in list(self.data.get("aliases", {}).items()):
                        if target == name_lower:
                            del self.data["aliases"][alias]
                    # Add new aliases
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
                # Remove aliases
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
    
    # ═════════════════════════════════════════════════════════════════
    # USER OPERATIONS
    # ═════════════════════════════════════════════════════════════════
    
    def add_user(self, user_id: int) -> bool:
        if user_id not in self.data.get("users", []):
            self.data["users"].append(user_id)
            return self.save()
        return True
    
    def get_user_count(self) -> int:
        return len(self.data.get("users", []))
    
    # ═════════════════════════════════════════════════════════════════
    # SETTINGS & STATS
    # ═════════════════════════════════════════════════════════════════
    
    def get_setting(self, key: str, default=None):
        return self.data.get("settings", {}).get(key, default)
    
    def set_setting(self, key: str, value: Any) -> bool:
        self.data["settings"][key] = value
        return self.save()
    
    def increment_search_stat(self, anime_name: str, success: bool = True):
        self.data["stats"]["total_searches"] = self.data["stats"].get("total_searches", 0) + 1
        if success:
            self.data["stats"]["successful_searches"] = self.data["stats"].get("successful_searches", 0) + 1
        
        # Track popular animes
        popular = self.data["stats"].get("popular_animes", {})
        popular[anime_name] = popular.get(anime_name, 0) + 1
        self.data["stats"]["popular_animes"] = popular
        
        self.save()
    
    def get_stats(self) -> Dict[str, Any]:
        return self.data.get("stats", {})

db = UltimateDatabase(DB_FILE)

# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED FUZZY SEARCH ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class FuzzySearchEngine:
    """
    Advanced fuzzy matching using multiple algorithms:
    1. Token Set Ratio - for word order independence
    2. Partial Ratio - for substring matching
    3. SequenceMatcher - for typos and similar spellings
    """
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for better matching"""
        text = text.lower().strip()
        # Remove special characters but keep spaces
        text = re.sub(r'[^\w\s]', '', text)
        # Remove extra spaces
        text = ' '.join(text.split())
        return text
    
    @staticmethod
    def calculate_similarity(query: str, target: str) -> float:
        """
        Calculate composite similarity score (0-100)
        Uses multiple algorithms for best results
        """
        query_norm = FuzzySearchEngine.normalize_text(query)
        target_norm = FuzzySearchEngine.normalize_text(target)
        
        if not query_norm or not target_norm:
            return 0.0
        
        # Exact match
        if query_norm == target_norm:
            return 100.0
        
        # Contains query (partial match bonus)
        if query_norm in target_norm or target_norm in query_norm:
            return 95.0
        
        # Token-based matching (word independence)
        query_tokens = set(query_norm.split())
        target_tokens = set(target_norm.split())
        
        if query_tokens and target_tokens:
            intersection = query_tokens & target_tokens
            union = query_tokens | target_tokens
            
            if intersection:
                jaccard = len(intersection) / len(union) * 100
                
                # Bonus for matching first word (important for anime titles)
                query_first = query_norm.split()[0] if query_norm.split() else ""
                target_first = target_norm.split()[0] if target_norm.split() else ""
                
                if query_first == target_first:
                    jaccard += 10
                
                # Bonus for matching any word exactly
                exact_word_matches = sum(1 for w in query_tokens if w in target_tokens)
                jaccard += exact_word_matches * 5
                
                return min(jaccard, 100.0)
        
        # Sequence matching for typos (Levenshtein-like)
        seq_ratio = SequenceMatcher(None, query_norm, target_norm).ratio() * 100
        
        return seq_ratio
    
    @staticmethod
    def find_best_match(query: str, candidates: List[str]) -> Optional[Tuple[str, float]]:
        """Find best matching anime name from candidates"""
        if not query or not candidates:
            return None
        
        best_match = None
        best_score = 0.0
        
        query_norm = FuzzySearchEngine.normalize_text(query)
        
        for candidate in candidates:
            # Check direct match first
            if query_norm == FuzzySearchEngine.normalize_text(candidate):
                return (candidate, 100.0)
            
            # Check aliases if present in anime data
            anime_data = db.get_anime(candidate)
            if anime_data:
                # Check main name
                score = FuzzySearchEngine.calculate_similarity(query, candidate)
                if score > best_score:
                    best_score = score
                    best_match = candidate
                
                # Check all aliases
                for alias in anime_data.get("aliases", []):
                    alias_score = FuzzySearchEngine.calculate_similarity(query, alias)
                    if alias_score > best_score:
                        best_score = alias_score
                        best_match = candidate
            
            else:
                score = FuzzySearchEngine.calculate_similarity(query, candidate)
                if score > best_score:
                    best_score = score
                    best_match = candidate
        
        # Apply threshold
        threshold = db.get_setting("fuzzy_threshold", FUZZY_THRESHOLD)
        if best_score >= threshold:
            return (best_match, best_score)
        
        return None
    
    @staticmethod
    def search_anime(query: str) -> Optional[Dict[str, Any]]:
        """Search anime with fuzzy matching"""
        all_animes = db.get_all_animes()
        
        if not all_animes:
            return None
        
        # Get list of all anime names
        candidates = list(all_animes.keys())
        
        # Find best match
        result = FuzzySearchEngine.find_best_match(query, candidates)
        
        if result:
            anime_name, score = result
            anime_data = all_animes.get(anime_name)
            if anime_data:
                anime_data["_match_score"] = score
                anime_data["_matched_name"] = anime_name
                return anime_data
        
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT FOR CONVERSATIONS
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
    """Clean and normalize user input"""
    if not text:
        return ""
    
    # Remove bot username mentions in groups
    if is_group and BOT_USERNAME:
        text = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    text = ' '.join(text.split()).strip()
    return text

def format_anime_caption(anime_data: Dict[str, Any], show_score: bool = False) -> str:
    """Format anime data into beautiful caption"""
    name = anime_data.get("name_display", "Unknown Anime")
    desc = anime_data.get("desc", "No description available.")
    views = anime_data.get("views", 0)
    
    caption = (
                    f"<blockquote>✨ <b>{display_name.upper()}</b> ✨</blockquote>\n\n"
                    f"<b><blockquote>📖 {data.get('desc', 'No description')}</blockquote></b>\n\n"
                    f"➖➖➖➖➖➖➖➖➖➖\n"
                    f"🔰 <b>FOR MORE JOIN:</b>\n"
                    f"<blockquote>👉 @KENSHIN_ANIME\n"
                    f"👉 @MANWHA_VERSE</blockquote>"
    )
    
    return caption

def create_anime_buttons(anime_data: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Create inline buttons for anime"""
    buttons = [
        [InlineKeyboardButton("🚀 DOWNLOAD / WATCH NOW", url=anime_data.get("download_link", CHANNEL_LINK))]
    ]
    
    # Add additional links if available
    extra_links = anime_data.get("extra_links", [])
    if extra_links:
        row = []
        for link_data in extra_links[:2]:
            row.append(InlineKeyboardButton(
                link_data.get("text", "Link"),
                url=link_data.get("url", CHANNEL_LINK)
            ))
        if row:
            buttons.append(row)
    
    return InlineKeyboardMarkup(buttons)

# ═══════════════════════════════════════════════════════════════════════════════
# USER COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("start") & filters.private)
async def start_private(client: Client, message: Message):
    """Enhanced start command with user registration"""
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
            "🍿 I provide high-quality Anime links instantly with <b>Smart Fuzzy Search!</b>\n\n"
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
    """Group start command"""
    await message.reply(
        f"👋 <b>Hey {message.from_user.first_name}!</b>\n\n"
        f"🍿 I'm Kenshin Anime Bot Ultimate!\n"
        f"Type any anime name and I'll find it with smart fuzzy matching!\n\n"
        f"<i>DM me for full features → @{BOT_USERNAME or 'Bot'}</i>"
    )

@bot.on_message(filters.command("help") & (filters.private | filters.group))
async def help_cmd(client: Client, message: Message):
    """Enhanced help command"""
    is_admin = state_mgr.is_admin(message.from_user.id)
    
    text = (
        "🛠 <b>USER MENU</b>\n\n"
        "• /start - Wake up bot\n"
        "• /help - This menu\n"
        "• /report &lt;msg&gt; - Report issue\n"
        "• /stats - Bot statistics\n"
        "• /search &lt;name&gt; - Advanced search\n\n"
        "🔍 <b>SMART SEARCH TIPS:</b>\n"
        "• Use partial names: <code>solo</code> → Solo Leveling\n"
        "• Use abbreviations: <code>jjk</code> → Jujutsu Kaisen\n"
        "• Use aliases: <code>tonikawa</code> → Tonikaku Kawaii\n"
        "• Typos are auto-corrected!\n\n"
        "<b>Just type any anime name directly!</b>"
    )
    
    if is_admin:
        text += (
            "\n\n⚡ <b>ADMIN PANEL</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Anime Management:</b>\n"
            "• /add_ani - Add new anime (step-by-step)\n"
            "• /edit_ani - Edit existing anime\n"
            "• /delete_ani - Remove anime\n"
            "• /add_alias - Add alias to anime\n"
            "• /bulk - Bulk upload via file\n\n"
            "<b>Bot Settings:</b>\n"
            "• /set_start_img - Change banner\n"
            "• /set_start_msg - Edit welcome text\n"
            "• /view_start_img - Preview banner\n"
            "• /view_start_msg - Preview welcome\n"
            "• /set_threshold - Fuzzy match sensitivity\n\n"
            "<b>Analytics:</b>\n"
            "• /list - All animes (paginated)\n"
            "• /stats - Detailed statistics\n"
            "• /popular - Most searched animes\n"
            "• /broadcast - Message all users\n"
            "• /db_export - Export database\n\n"
            "• /cancel - Cancel current operation"
        )
    
    await message.reply(text)

@bot.on_message(filters.command("report") & (filters.private | filters.group))
async def report_cmd(client: Client, message: Message):
    """Report command with validation"""
    if len(message.command) < 2:
        await message.reply(
            "📝 <b>Report Format:</b>\n"
            "<code>/report Your message here describing the issue</code>\n\n"
            "Example: <code>/report Solo Leveling link is not working</code>"
        )
        return
    
    report_text = " ".join(message.command[1:])
    user = message.from_user
    
    if len(report_text) < 10:
        await message.reply("❌ Report too short! Please provide more details (min 10 characters).")
        return
    
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📢 <b>NEW REPORT</b>\n\n"
            f"👤 <b>From:</b> {user.first_name} (@{user.username or 'N/A'})\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"💬 <b>Chat:</b> {'Private' if message.chat.type == 'private' else message.chat.title}\n"
            f"⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"📝 <b>Message:</b>\n<blockquote>{report_text}</blockquote>"
        )
        await message.reply("✅ Report sent successfully! We'll look into it.")
    except Exception as e:
        logger.error(f"Report failed: {e}")
        await message.reply("❌ Failed to send report. Please try again later.")

@bot.on_message(filters.command("search") & (filters.private | filters.group))
async def search_cmd(client: Client, message: Message):
    """Explicit search command"""
    if len(message.command) < 2:
        await message.reply("🔍 <b>Usage:</b> <code>/search anime name</code>")
        return
    
    query = " ".join(message.command[1:])
    await perform_anime_search(message, query)

@bot.on_message(filters.command("stats") & (filters.private | filters.group))
async def stats_cmd(client: Client, message: Message):
    """Enhanced statistics command"""
    animes = db.get_all_animes()
    users_count = db.get_user_count()
    stats = db.get_stats()
    
    total_searches = stats.get("total_searches", 0)
    successful = stats.get("successful_searches", 0)
    success_rate = (successful / total_searches * 100) if total_searches > 0 else 0
    
    text = (
        f"📊 <b>BOT STATISTICS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>Total Users:</b> <code>{users_count}</code>\n"
        f"🎬 <b>Total Animes:</b> <code>{len(animes)}</code>\n"
        f"🏷 <b>Total Aliases:</b> <code>{len(db.data.get('aliases', {}))}</code>\n\n"
        f"🔍 <b>Search Stats:</b>\n"
        f"• Total Searches: <code>{total_searches}</code>\n"
        f"• Successful: <code>{successful}</code>\n"
        f"• Success Rate: <code>{success_rate:.1f}%</code>\n\n"
        f"💾 <b>Database:</b> <code>{DB_FILE}</code>\n"
        f"🤖 <b>Version:</b> <code>Ultimate v4.0</code>"
    )
    
    await message.reply(text)

@bot.on_message(filters.command("popular") & (filters.private | filters.group))
async def popular_cmd(client: Client, message: Message):
    """Show popular animes"""
    stats = db.get_stats()
    popular = stats.get("popular_animes", {})
    
    if not popular:
        await message.reply("📭 No search data available yet!")
        return
    
    # Sort by views
    sorted_popular = sorted(popular.items(), key=lambda x: x[1], reverse=True)[:10]
    
    text = "🔥 <b>TOP 10 MOST SEARCHED ANIME</b>\n\n"
    for i, (name, count) in enumerate(sorted_popular, 1):
        anime_data = db.get_anime(name)
        display_name = anime_data.get("name_display", name) if anime_data else name
        text += f"<code>{i:2d}.</code> <b>{display_name}</b> - <code>{count}</code> searches\n"
    
    await message.reply(text)

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN COMMANDS - ADD ANIME (FIXED & ENHANCED)
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("add_ani") & filters.private)
async def add_ani_cmd(client: Client, message: Message):
    """Initialize add anime workflow - FIXED VERSION"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b> Only Owner can use this.")
        return
    
    # Check for quick mode: /add_ani name | image | link | desc
    if len(message.command) > 1:
        full_text = " ".join(message.command[1:])
        if "|" in full_text:
            parts = [p.strip() for p in full_text.split("|")]
            if len(parts) >= 4:
                name, img, link, desc = parts[0], parts[1], parts[2], parts[3]
                aliases = parts[4].split(",") if len(parts) > 4 and parts[4] else []
                
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
                    await message.reply(
                        f"✅ <b>Anime added successfully!</b>\n\n"
                        f"📺 <b>{name}</b>\n"
                        f"🏷 Aliases: <code>{', '.join(aliases) if aliases else 'None'}</code>"
                    )
                else:
                    await message.reply("❌ Failed to add anime!")
                return
    
    # Interactive mode
    state_mgr.set_state(user_id, "ADD_NAME", {})
    
    prompt = (
        "╔════════════════════════════════════╗\n"
        "║     🚀 ADD NEW ANIME - STEP 1/5      ║\n"
        "╚════════════════════════════════════╝\n\n"
        "<b>Please send the exact anime name:</b>\n\n"
        "💡 <b>Examples:</b>\n"
        "• <code>Solo Leveling</code>\n"
        "• <code>Jujutsu Kaisen</code>\n"
        "• <code>A Couple of Cuckoos</code>\n\n"
        "❌ Send <code>cancel</code> anytime to abort.\n\n"
        "⏳ <b>Waiting for anime name...</b>"
    )
    
    await message.reply(prompt)

@bot.on_message(filters.command("edit_ani") & filters.private)
async def edit_ani_cmd(client: Client, message: Message):
    """Initialize edit anime workflow - FIXED VERSION"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    animes = db.get_all_animes()
    if not animes:
        await message.reply("📭 <b>No anime in database!</b>\n\nUse /add_ani to add first.")
        return
    
    # Show list with numbers
    items = sorted(animes.items(), key=lambda x: x[1].get("name_display", x[0]))
    
    list_text = (
        f"╔════════════════════════════════════╗\n"
        f"║     ✏️ EDIT ANIME ENTRY              ║\n"
        f"╚════════════════════════════════════╝\n\n"
        f"<b>Available Animes ({len(items)} total):</b>\n\n"
    )
    
    # Create numbered list
    anime_list = []
    for i, (name, data) in enumerate(items[:30], 1):
        display = data.get("name_display", name)
        list_text += f"<code>{i:2d}.</code> {display}\n"
        anime_list.append((name, display))
    
    if len(items) > 30:
        list_text += f"\n<i>... and {len(items) - 30} more</i>\n"
    
    list_text += (
        f"\n✏️ <b>How to select:</b>\n"
        f"• Send the <b>number</b> from the list above\n"
        f"• Or send the <b>exact anime name</b>\n"
        f"• Or send an <b>alias</b> of the anime\n\n"
        f"❌ Send <code>cancel</code> to abort."
    )
    
    # Store anime list in state for number reference
    state_mgr.set_state(user_id, "EDIT_SELECT", {"anime_list": anime_list})
    
    await message.reply(list_text, disable_web_page_preview=True)

@bot.on_message(filters.command("delete_ani") & filters.private)
async def delete_ani_cmd(client: Client, message: Message):
    """Delete anime command"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    if len(message.command) < 2:
        await message.reply(
            "🗑 <b>Delete Anime</b>\n\n"
            "<b>Usage:</b> <code>/delete_ani anime_name</code>\n\n"
            "⚠️ <b>This action cannot be undone!</b>"
        )
        return
    
    name = " ".join(message.command[1:])
    anime_data = db.get_anime(name)
    
    if not anime_data:
        await message.reply(f"❌ Anime '<code>{name}</code>' not found!")
        return
    
    display_name = anime_data.get("name_display", name)
    
    # Confirm deletion
    state_mgr.set_state(user_id, "DELETE_CONFIRM", {
        "target": name.lower(),
        "display_name": display_name
    })
    
    await message.reply(
        f"⚠️ <b>CONFIRM DELETION</b>\n\n"
        f"Are you sure you want to delete:\n"
        f"<b>{display_name}</b>?\n\n"
        f"Send <code>yes</code> to confirm, or <code>cancel</code> to abort."
    )

@bot.on_message(filters.command("add_alias") & filters.private)
async def add_alias_cmd(client: Client, message: Message):
    """Add alias to existing anime"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    if len(message.command) < 3:
        await message.reply(
            "🏷 <b>Add Alias</b>\n\n"
            "<b>Usage:</b> <code>/add_alias anime_name | alias1, alias2, ...</code>\n\n"
            "Example:\n<code>/add_alias Solo Leveling | sl, solo lev</code>"
        )
        return
    
    full_text = " ".join(message.command[1:])
    if "|" not in full_text:
        await message.reply("❌ Invalid format! Use: <code>anime_name | alias1, alias2</code>")
        return
    
    parts = [p.strip() for p in full_text.split("|", 1)]
    anime_name = parts[0]
    new_aliases = [a.strip() for a in parts[1].split(",") if a.strip()]
    
    anime_data = db.get_anime(anime_name)
    if not anime_data:
        await message.reply(f"❌ Anime '<code>{anime_name}</code>' not found!")
        return
    
    # Add new aliases
    existing_aliases = set(anime_data.get("aliases", []))
    existing_aliases.update(new_aliases)
    
    # Update database
    actual_name = anime_data.get("_matched_name", anime_name.lower())
    success = db.update_anime_field(actual_name, "aliases", list(existing_aliases))
    
    if success:
        await message.reply(
            f"✅ <b>Aliases added!</b>\n\n"
            f"📺 <b>{anime_data.get('name_display', anime_name)}</b>\n"
            f"🏷 <b>All aliases:</b> <code>{', '.join(existing_aliases)}</code>"
        )
    else:
        await message.reply("❌ Failed to add aliases!")

# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("set_start_img") & filters.private)
async def set_start_img_cmd(client: Client, message: Message):
    """Set start image/banner"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        return
    
    if len(message.command) > 1:
        url = message.command[1]
        if not url.startswith(("http://", "https://")):
            await message.reply("❌ Invalid URL! Must start with http:// or https://")
            return
        
        try:
            test = await message.reply_photo(photo=url, caption="👁 Testing image...")
            db.set_setting("start_image", url)
            await test.edit_caption(f"✅ Banner updated!\n\n<code>{url}</code>")
        except Exception as e:
            await message.reply(f"❌ Invalid image: {e}")
        return
    
    # Interactive mode
    current = db.get_setting("start_image", DEFAULT_START_IMAGE)
    state_mgr.set_state(user_id, "SET_START_IMG", {})
    
    await message.reply(
        f"🖼 <b>Update Banner</b>\n\n"
        f"Current: <code>{current[:60]}...</code>\n\n"
        f"Send new image URL or <code>cancel</code>\n\n"
        f"<b>Quick mode:</b> <code>/set_start_img &lt;url&gt;</code>"
    )

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
    await message.reply(
        "📝 <b>Update Welcome Text</b>\n\n"
        f"Send new message or <code>cancel</code>\n\n"
        f"<b>Quick mode:</b> <code>/set_start_msg &lt;text&gt;</code>"
    )

@bot.on_message(filters.command("view_start_img") & filters.private)
async def view_start_img_cmd(client: Client, message: Message):
    """View current banner"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    current = db.get_setting("start_image", DEFAULT_START_IMAGE)
    try:
        await message.reply_photo(
            photo=current,
            caption=f"👁 Current Banner\n\n<code>{current}</code>"
        )
    except:
        await message.reply(f"⚠️ Current URL (image may be unavailable):\n<code>{current}</code>")

@bot.on_message(filters.command("view_start_msg") & filters.private)
async def view_start_msg_cmd(client: Client, message: Message):
    """View current welcome message"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    current = db.get_setting("start_message")
    if not current:
        await message.reply("ℹ️ Using default welcome message")
    else:
        await message.reply(f"👁 Current Welcome Message:\n\n{current}")

@bot.on_message(filters.command("set_threshold") & filters.private)
async def set_threshold_cmd(client: Client, message: Message):
    """Set fuzzy matching threshold"""
    user_id = message.from_user.id
    
    if not state_mgr.is_admin(user_id):
        return
    
    if len(message.command) > 1:
        try:
            threshold = int(message.command[1])
            if 30 <= threshold <= 100:
                db.set_setting("fuzzy_threshold", threshold)
                await message.reply(f"✅ Fuzzy threshold set to <code>{threshold}%</code>")
            else:
                await message.reply("❌ Threshold must be between 30 and 100!")
        except ValueError:
            await message.reply("❌ Invalid number!")
        return
    
    current = db.get_setting("fuzzy_threshold", FUZZY_THRESHOLD)
    await message.reply(
        f"🎯 <b>Fuzzy Matching Threshold</b>\n\n"
        f"Current: <code>{current}%</code>\n\n"
        f"<b>What is this?</b>\n"
        f"Lower value = More lenient matching (more results)\n"
        f"Higher value = Stricter matching (fewer results)\n\n"
        f"<b>Usage:</b> <code>/set_threshold &lt;30-100&gt;</code>\n"
        f"Example: <code>/set_threshold 70</code>"
    )

@bot.on_message(filters.command("bulk") & filters.private)
async def bulk_cmd(client: Client, message: Message):
    """Bulk upload instructions"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    await message.reply(
        "📦 <b>BULK UPLOAD GUIDE</b>\n\n"
        "<b>Format (one anime per line):</b>\n"
        "<code>Name | Image URL | Link | Description | Aliases (optional)</code>\n\n"
        "<b>Example:</b>\n"
        "<pre>Solo Leveling | https://img.com/solo.jpg | https://t.me/... | A weak hunter... | sl, solo lev, sung jinwoo\n"
        "Jujutsu Kaisen | https://img.com/jjk.jpg | https://t.me/... | Sorcery battles... | jjk, jujutsu</pre>\n\n"
        "Send a <code>.txt</code> file with this format to process."
    )

@bot.on_message(filters.command("list") & filters.private)
async def list_cmd(client: Client, message: Message):
    """List all animes with pagination"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    animes = db.get_all_animes()
    if not animes:
        await message.reply("📭 Database empty!")
        return
    
    items = sorted(animes.items(), key=lambda x: x[1].get("name_display", x[0]))
    
    # Send in chunks of 15
    for i in range(0, len(items), 15):
        chunk = items[i:i+15]
        text = f"📚 <b>ANIME LIST</b> ({i+1}-{min(i+15, len(items))}/{len(items)})\n\n"
        
        for idx, (name, data) in enumerate(chunk, i+1):
            display = data.get("name_display", name)
            views = data.get("views", 0)
            aliases = len(data.get("aliases", []))
            text += f"<code>{idx}.</code> <b>{display}</b> 👁{views} 🏷{aliases}\n"
        
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.3)

@bot.on_message(filters.command("db_export") & filters.private)
async def db_export_cmd(client: Client, message: Message):
    """Export database as file"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    try:
        with open(DB_FILE, 'rb') as f:
            await message.reply_document(
                document=f,
                caption=f"💾 Database Export\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
    except Exception as e:
        await message.reply(f"❌ Export failed: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# BROADCAST & CANCEL
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_cmd(client: Client, message: Message):
    """Broadcast message to all users"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    if not message.reply_to_message:
        await message.reply(
            "📢 <b>Broadcast</b>\n\n"
            "Reply to any message with <code>/broadcast</code> to send it to all users.\n\n"
            "⚠️ This may take time for large user bases!"
        )
        return
    
    users = db.data.get("users", [])
    if not users:
        await message.reply("📭 No users to broadcast to!")
        return
    
    status = await message.reply(f"📡 Broadcasting to {len(users)} users...")
    
    sent, blocked, failed = 0, 0, 0
    for uid in users:
        try:
            await message.reply_to_message.copy(uid)
            sent += 1
            if sent % 50 == 0:
                await status.edit(f"📡 Progress: {sent}/{len(users)} sent...")
            await asyncio.sleep(0.2)
        except UserIsBlocked:
            blocked += 1
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast to {uid} failed: {e}")
    
    await status.edit(
        f"📢 <b>Broadcast Complete!</b>\n\n"
        f"✅ Sent: <code>{sent}</code>\n"
        f"🚫 Blocked: <code>{blocked}</code>\n"
        f"❌ Failed: <code>{failed}</code>"
    )

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client: Client, message: Message):
    """Cancel current operation"""
    user_id = message.from_user.id
    
    if state_mgr.get_state(user_id):
        state_mgr.clear_state(user_id)
        await message.reply("✅ Operation cancelled!")
    else:
        await message.reply("ℹ️ No active operation to cancel.")

# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT HANDLER (BULK UPLOAD)
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.document & filters.private)
async def doc_handler(client: Client, message: Message):
    """Handle bulk upload files"""
    if not state_mgr.is_admin(message.from_user.id):
        return
    
    if not message.document.file_name.endswith('.txt'):
        return
    
    status = await message.reply("⏳ Processing bulk upload...")
    
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
                errors.append(f"Line {line_num}: Incomplete data")
                continue
            
            name, img, link, desc = parts[0], parts[1], parts[2], parts[3]
            aliases = [a.strip() for a in parts[4].split(',')] if len(parts) > 4 else []
            
            if not all([name, img, link]):
                errors.append(f"Line {line_num}: Missing required fields")
                continue
            
            # Check if exists
            existing = db.get_anime(name)
            if existing:
                # Update existing
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
                # Add new
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
        
        # Cleanup
        if os.path.exists(path):
            os.remove(path)
        
        # Report
        result = (
            f"📦 <b>Bulk Upload Complete!</b>\n\n"
            f"✅ Added: <code>{added}</code>\n"
            f"🔄 Updated: <code>{updated}</code>\n"
            f"❌ Errors: <code>{len(errors)}</code>"
        )
        
        if errors:
            error_text = "\n".join(errors[:10])
            if len(errors) > 10:
                error_text += f"\n... and {len(errors) - 10} more"
            result += f"\n\n<b>Errors:</b>\n<pre>{error_text}</pre>"
        
        await status.edit(result)
        
    except Exception as e:
        logger.error(f"Bulk error: {e}")
        await status.edit(f"❌ Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN MESSAGE HANDLER - ADVANCED FUZZY SEARCH & STATES
# ═══════════════════════════════════════════════════════════════════════════════

async def perform_anime_search(message: Message, query: str):
    """Perform fuzzy anime search and send result"""
    if not query or len(query) < 2:
        await message.reply("❌ Search query too short! (min 2 characters)")
        return
    
    # Search with fuzzy matching
    result = FuzzySearchEngine.search_anime(query)
    
    if result:
        anime_name = result.get("_matched_name", "unknown")
        display_name = result.get("name_display", anime_name)
        
        # Increment views
        db.data["animes"][anime_name]["views"] = result.get("views", 0) + 1
        db.save()
        
        # Update stats
        db.increment_search_stat(anime_name, True)
        
        # Send result
        caption = format_anime_caption(result, show_score=True)
        buttons = create_anime_buttons(result)
        
        try:
            await message.reply_photo(
                photo=result.get("image_url"),
                caption=caption,
                reply_markup=buttons
            )
        except Exception as e:
            logger.error(f"Photo error: {e}")
            await message.reply(caption, reply_markup=buttons)
        
        # Register user
        db.add_user(message.from_user.id)
    else:
        # No match
        db.increment_search_stat("unknown", False)
        
        suggestions = get_search_suggestions(query)
        
        text = (
            f"🔍 <b>No exact match for '</b><code>{query[:40]}</code><b>'</b>\n\n"
        )
        
        if suggestions:
            text += "<b>Did you mean:</b>\n"
            for sug in suggestions[:5]:
                text += f"• <code>{sug}</code>\n"
            text += "\n"
        
        text += "Try different spelling or use /report to request this anime."
        
        await message.reply(text)

def get_search_suggestions(query: str) -> List[str]:
    """Get search suggestions based on partial matches"""
    animes = db.get_all_animes()
    suggestions = []
    
    query_words = set(FuzzySearchEngine.normalize_text(query).split())
    
    for name, data in animes.items():
        display = data.get("name_display", name)
        name_words = set(FuzzySearchEngine.normalize_text(display).split())
        
        # Check word overlap
        if query_words & name_words:
            suggestions.append(display)
        
        # Check aliases
        for alias in data.get("aliases", []):
            alias_words = set(FuzzySearchEngine.normalize_text(alias).split())
            if query_words & alias_words and display not in suggestions:
                suggestions.append(display)
    
    return suggestions[:5]

@bot.on_message(filters.text & (filters.private | filters.group))
async def main_handler(client: Client, message: Message):
    """Main message handler with state machine and fuzzy search"""
    user_id = message.from_user.id
    is_group = message.chat.type != "private"
    text = clean_text(message.text, is_group)
    text_lower = text.lower().strip()
    
    if not text:
        return
    
    # Skip commands
    if text.startswith("/"):
        return
    
    # ═════════════════════════════════════════════════════════════════
    # HANDLE CANCEL
    # ═════════════════════════════════════════════════════════════════
    if text_lower == "cancel":
        if state_mgr.get_state(user_id):
            state_mgr.clear_state(user_id)
            await message.reply("✅ Cancelled!")
        else:
            await message.reply("ℹ️ Nothing to cancel.")
        return
    
    # ═════════════════════════════════════════════════════════════════
    # ADMIN STATE MACHINE (Private only)
    # ═════════════════════════════════════════════════════════════════
    if not is_group and state_mgr.is_admin(user_id):
        state_info = state_mgr.get_state(user_id)
        
        if state_info:
            current_state = state_info.get("state")
            state_data = state_info.get("data", {})
            
            logger.info(f"Admin {user_id} in state: {current_state}, received: {text[:50]}...")
            
            # ═════════════════════════════════════════════════════════════
            # ADD ANIME FLOW - 5 Steps
            # ═════════════════════════════════════════════════════════════
            if current_state == "ADD_NAME":
                if len(text) < 2:
                    await message.reply("❌ Name too short! Send a valid anime name:")
                    return
                
                # Check if exists
                existing = db.get_anime(text)
                if existing:
                    await message.reply(
                        f"⚠️ <b>'{text}' already exists!</b>\n\n"
                        f"Use /edit_ani to modify it, or send a different name:"
                    )
                    return
                
                state_mgr.set_state(user_id, "ADD_IMAGE", {
                    "name": text,
                    "name_lower": text.lower().strip()
                })
                
                await message.reply(
                    f"✅ <b>Name:</b> <code>{text}</code>\n\n"
                    f"<b>Step 2/5: Image URL</b>\n"
                    f"Send the anime poster/cover image URL:\n\n"
                    f"💡 Recommended: Catbox.moe, Telegraph, imgur\n"
                    f"❌ Send <code>cancel</code> to abort"
                )
                return
            
            if current_state == "ADD_IMAGE":
                if not text.startswith(("http://", "https://")):
                    await message.reply("❌ Invalid URL! Must start with http:// or https://\n\nSend a valid image URL:")
                    return
                
                # Test image
                test_msg = None
                try:
                    test_msg = await message.reply_photo(
                        photo=text,
                        caption="👁 Testing image..."
                    )
                    await test_msg.delete()
                    image_valid = True
                except Exception as e:
                    image_valid = False
                    logger.warning(f"Image test failed: {e}")
                
                if not image_valid:
                    await message.reply(
                        f"⚠️ <b>Warning:</b> Could not verify image.\n\n"
                        f"Send <code>yes</code> to use anyway, or send a different URL:"
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
                    f"Send Telegram channel/group link or direct download URL:"
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
                        f"<b>Step 3/5: Download Link</b>\n"
                        f"Send the download link:"
                    )
                else:
                    # User sent new URL
                    if not text.startswith(("http://", "https://")):
                        await message.reply("❌ Invalid URL! Send <code>yes</code> or a new URL:")
                        return
                    
                    state_mgr.set_state(user_id, "ADD_LINK", {
                        **state_data,
                        "image": text
                    })
                    await message.reply(f"✅ <b>New image saved!</b>\n\n<b>Step 3/5: Download Link</b>")
                return
            
            if current_state == "ADD_LINK":
                if not text.startswith(("http://", "https://", "t.me/")):
                    await message.reply("❌ Invalid link! Must be a URL or t.me link:\n\nSend a valid download link:")
                    return
                
                state_mgr.set_state(user_id, "ADD_DESC", {
                    **state_data,
                    "link": text
                })
                
                await message.reply(
                    f"✅ <b>Link saved!</b>\n\n"
                    f"<b>Step 4/5: Description</b>\n"
                    f"Send a short synopsis/description (min 10 characters):\n\n"
                    f"<b>Example:</b>\n"
                    f"<code>A weak hunter gains the power to level up infinitely. The ultimate power fantasy!</code>"
                )
                return
            
            if current_state == "ADD_DESC":
                if len(text) < 10:
                    await message.reply(f"❌ Too short! ({len(text)} chars, need 10+)\n\nSend a longer description:")
                    return
                
                state_mgr.set_state(user_id, "ADD_ALIASES", {
                    **state_data,
                    "desc": text
                })
                
                await message.reply(
                    f"✅ <b>Description saved!</b>\n\n"
                    f"<b>Step 5/5: Aliases (Optional)</b>\n"
                    f"Send alternate names/abbreviations separated by commas, or send <code>skip</code>:\n\n"
                    f"<b>Examples:</b>\n"
                    f"• For Solo Leveling: <code>sl, solo lev, sung jinwoo</code>\n"
                    f"• For Jujutsu Kaisen: <code>jjk, jujutsu</code>\n"
                    f"• For A Couple of Cuckoos: <code>cuckoos, couple cuckoos</code>"
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
                        f"📊 <b>Summary:</b>\n"
                        f"• Name: <code>{state_data['name']}</code>\n"
                        f"• Aliases: <code>{alias_text}</code>\n"
                        f"• Image: <code>{state_data['image'][:50]}...</code>\n"
                        f"• Link: <code>{state_data['link'][:50]}...</code>\n"
                        f"• Desc: <code>{state_data['desc'][:50]}...</code>\n\n"
                        f"🎉 Users can now search for this anime!\n\n"
                        f"Add another? Use /add_ani"
                    )
                    logger.info(f"Anime added: {state_data['name']} by admin {user_id}")
                else:
                    await message.reply("❌ <b>Failed to save!</b> Check logs.")
                
                state_mgr.clear_state(user_id)
                return
            
            # ═════════════════════════════════════════════════════════════
            # EDIT ANIME FLOW - FIXED VERSION
            # ═════════════════════════════════════════════════════════════
            if current_state == "EDIT_SELECT":
                anime_list = state_data.get("anime_list", [])
                selected_anime = None
                
                # Check if number input
                if text.isdigit():
                    num = int(text)
                    if 1 <= num <= len(anime_list):
                        selected_anime = anime_list[num - 1][0]  # Get the key
                    else:
                        await message.reply(f"❌ Invalid number! Choose 1-{len(anime_list)}:")
                        return
                else:
                    # Search by name/alias
                    selected_anime = text_lower
                    anime_data = db.get_anime(selected_anime)
                    if not anime_data:
                        await message.reply(
                            f"❌ Anime '<code>{text}</code>' not found!\n\n"
                            f"Send a number from the list or exact name:"
                        )
                        return
                
                # Get full data
                anime_data = db.get_anime(selected_anime)
                if not anime_data:
                    await message.reply("❌ Error loading anime data!")
                    state_mgr.clear_state(user_id)
                    return
                
                actual_name = anime_data.get("_matched_name", selected_anime)
                display_name = anime_data.get("name_display", actual_name)
                
                # Show current data
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
                        f"<b>{field_name}</b> changed for <code>{target}</code>\n\n"
                        f"<b>New value:</b> <code>{str(value)[:100]}</code>"
                    )
                    logger.info(f"Anime edited: {target}, field: {field_name}")
                else:
                    await message.reply("❌ <b>Update failed!</b>")
                
                state_mgr.clear_state(user_id)
                return
            
            # ═════════════════════════════════════════════════════════════
            # DELETE CONFIRMATION
            # ═════════════════════════════════════════════════════════════
            if current_state == "DELETE_CONFIRM":
                if text_lower == "yes":
                    target = state_data.get("target")
                    display = state_data.get("display_name")
                    
                    if db.delete_anime(target):
                        await message.reply(f"🗑 <b>'{display}' deleted successfully!</b>")
                        logger.info(f"Anime deleted: {target}")
                    else:
                        await message.reply("❌ <b>Deletion failed!</b>")
                else:
                    await message.reply("❌ Deletion cancelled.")
                
                state_mgr.clear_state(user_id)
                return
            
            # ═════════════════════════════════════════════════════════════
            # SETTINGS FLOWS
            # ═════════════════════════════════════════════════════════════
            if current_state == "SET_START_IMG":
                if not text.startswith(("http://", "https://")):
                    await message.reply("❌ Invalid URL! Must start with http:// or https://")
                    return
                
                try:
                    test = await message.reply_photo(photo=text, caption="Testing...")
                    db.set_setting("start_image", text)
                    await test.edit_caption(f"✅ Banner updated!\n\n<code>{text}</code>")
                except Exception as e:
                    await message.reply(f"❌ Invalid image: {e}")
                
                state_mgr.clear_state(user_id)
                return
            
            if current_state == "SET_START_MSG":
                db.set_setting("start_message", text)
                await message.reply("✅ Welcome message updated!")
                state_mgr.clear_state(user_id)
                return
    
    # ═════════════════════════════════════════════════════════════════
    # ANIME SEARCH (All users - Group & Private)
    # ═════════════════════════════════════════════════════════════════
    if len(text) >= 2:  # Min 2 chars for search
        await perform_anime_search(message, text)

# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    """Handle callback queries"""
    data = callback_query.data
    
    if data == "cancel":
        user_id = callback_query.from_user.id
        state_mgr.clear_state(user_id)
        await callback_query.answer("Cancelled!")
        await callback_query.message.edit_text("✅ Operation cancelled.")
    
    else:
        await callback_query.answer("Processing...")

@bot.on_error()
async def error_handler(client: Client, error: Exception):
    """Global error handler"""
    logger.error(f"Bot error: {error}")

# ═══════════════════════════════════════════════════════════════════════════════
# RUN BOT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     🔥 KENSHIN ANIME BOT ULTIMATE v4.0 🔥                       ║")
    print("║     Advanced Fuzzy Search | Smart Matching | 1000+ Lines        ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"💾 Database: {DB_FILE}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🎯 Fuzzy Threshold: {FUZZY_THRESHOLD}%")
    print("Starting bot...")
    
    bot.run()
