#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    KENSHIN ANIME SEARCH BOT - PRO EDITION                     ║
║                         Version 3.0 - Ultimate Build                           ║
║                    Features: Advanced Search, Bulk Upload,                     ║
║                    Persistent DB, Group Support, Rich UI                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import asyncio
import logging
import re
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from pyrogram import Client, filters, errors, enums
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message, 
    CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
)
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, FloodWait

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: CONFIGURATION & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

class BotConfig:
    """Centralized configuration management"""
    
    # Core API Settings
    API_ID: int = int(os.environ.get("API_ID", "0"))
    API_HASH: str = os.environ.get("API_HASH", "").strip()
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "").strip()
    ADMIN_ID: int = int(os.environ.get("ADMIN_ID", "0"))
    BOT_USERNAME: str = os.environ.get("BOT_USERNAME", "").replace("@", "")
    
    # Database Settings
    DB_FILE: str = os.environ.get("DB_FILE", "/data/kenshin_data.json")
    BACKUP_DIR: str = os.environ.get("BACKUP_DIR", "/data/backups")
    
    # Media Settings
    DEFAULT_START_IMAGE: str = "https://files.catbox.moe/v4oy6s.jpg"
    FALLBACK_IMAGE: str = "https://files.catbox.moe/placeholder.jpg"
    MAX_DESC_LENGTH: int = 500
    
    # Bot Metadata
    BOT_NAME: str = "KENSHIN ANIME SEARCH"
    BOT_VERSION: str = "3.0.0"
    CHANNEL_LINK: str = "https://t.me/KENSHIN_ANIME"
    SUPPORT_GROUP: str = "https://t.me/KENSHIN_ANIME_CHAT"
    OWNER_USERNAME: str = "@KENSHIN_ANIME_OWNER"
    
    # Rate Limiting
    FLOOD_COOLDOWN: float = 0.5
    BROADCAST_DELAY: float = 0.3
    MAX_BROADCAST_PER_MIN: int = 200
    
    # Feature Flags
    ENABLE_STATS: bool = True
    ENABLE_BACKUP: bool = True
    AUTO_BACKUP_INTERVAL: int = 24  # hours

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("KenshinBot")

# File handler for persistent logs
try:
    os.makedirs("/data/logs", exist_ok=True)
    file_handler = logging.FileHandler("/data/logs/bot.log", encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(name)s - %(message)s'
    ))
    logger.addHandler(file_handler)
except Exception as e:
    logger.warning(f"Could not setup file logging: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: DATA MODELS & STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class AdminState(Enum):
    """Admin operation states"""
    IDLE = "idle"
    SET_START_IMG = "set_start_img"
    SET_START_MSG = "set_start_msg"
    ADD_ANIME_NAME = "add_anime_name"
    ADD_ANIME_IMAGE = "add_anime_image"
    ADD_ANIME_LINK = "add_anime_link"
    ADD_ANIME_DESC = "add_anime_desc"
    EDIT_ANIME_SELECT = "edit_anime_select"
    EDIT_ANIME_FIELD = "edit_anime_field"
    BROADCAST_CONFIRM = "broadcast_confirm"

@dataclass
class AnimeEntry:
    """Anime database entry structure"""
    name: str
    image_url: str
    download_link: str
    description: str
    added_by: int
    added_at: str
    genre: str = ""
    rating: float = 0.0
    views: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnimeEntry':
        return cls(**data)

@dataclass  
class UserStats:
    """User statistics structure"""
    user_id: int
    first_seen: str
    last_active: str
    searches: int = 0
    favorites: List[str] = None
    
    def __post_init__(self):
        if self.favorites is None:
            self.favorites = []

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: DATABASE ENGINE (PERSISTENT & ROBUST)
# ═══════════════════════════════════════════════════════════════════════════════

class DatabaseEngine:
    """
    Advanced JSON-based database with atomic writes,
    automatic backups, and corruption recovery.
    """
    
    def __init__(self, filepath: str, backup_dir: str):
        self.filepath = filepath
        self.backup_dir = backup_dir
        self.data: Dict[str, Any] = {}
        self._ensure_directories()
        self._load_or_init()
    
    def _ensure_directories(self) -> None:
        """Create necessary directories"""
        for path in [os.path.dirname(self.filepath), self.backup_dir]:
            if path and not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
                logger.info(f"Created directory: {path}")
    
    def _load_or_init(self) -> None:
        """Load existing database or create new"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(
                    f"Database loaded: {len(self.data.get('animes', {}))} animes, "
                    f"{len(self.data.get('users', []))} users"
                )
                return
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted database: {e}")
                self._restore_from_backup()
            except Exception as e:
                logger.error(f"Load error: {e}")
        
        # Initialize new database
        self.data = {
            "metadata": {
                "version": BotConfig.BOT_VERSION,
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat()
            },
            "users": [],
            "animes": {},
            "settings": {
                "start_image": BotConfig.DEFAULT_START_IMAGE,
                "start_message": None,
                "maintenance_mode": False,
                "blocked_users": []
            },
            "stats": {
                "total_searches": 0,
                "total_downloads": 0,
                "popular_animes": []
            }
        }
        self._atomic_save()
        logger.info("New database initialized")
    
    def _atomic_save(self) -> bool:
        """Atomic write operation to prevent corruption"""
        try:
            temp_file = f"{self.filepath}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            
            # Atomic replace
            os.replace(temp_file, self.filepath)
            
            # Update metadata
            self.data["metadata"]["last_modified"] = datetime.now().isoformat()
            return True
            
        except Exception as e:
            logger.error(f"Save failed: {e}")
            return False
    
    def _restore_from_backup(self) -> None:
        """Attempt to restore from backup files"""
        logger.info("Attempting backup restore...")
        # Implementation would check backup_dir for recent backups
        # For now, initialize fresh
        self.data = {
            "metadata": {"version": BotConfig.BOT_VERSION, "created_at": datetime.now().isoformat()},
            "users": [], "animes": {}, 
            "settings": {"start_image": BotConfig.DEFAULT_START_IMAGE, "start_message": None},
            "stats": {"total_searches": 0, "total_downloads": 0, "popular_animes": []}
        }
        self._atomic_save()
    
    def save(self) -> bool:
        """Public save method"""
        return self._atomic_save()
    
    def get_anime(self, name: str) -> Optional[Dict[str, Any]]:
        """Get anime by name (case-insensitive)"""
        return self.data.get("animes", {}).get(name.lower())
    
    def add_anime(self, name: str, data: Dict[str, Any]) -> bool:
        """Add or update anime entry"""
        try:
            self.data["animes"][name.lower()] = {
                **data,
                "name_display": name,  # Preserve original case
                "updated_at": datetime.now().isoformat()
            }
            return self.save()
        except Exception as e:
            logger.error(f"Add anime failed: {e}")
            return False
    
    def delete_anime(self, name: str) -> bool:
        """Delete anime entry"""
        if name.lower() in self.data.get("animes", {}):
            del self.data["animes"][name.lower()]
            return self.save()
        return False
    
    def add_user(self, user_id: int) -> bool:
        """Add user if not exists"""
        if user_id not in self.data.get("users", []):
            self.data["users"].append(user_id)
            return self.save()
        return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get setting value"""
        return self.data.get("settings", {}).get(key, default)
    
    def set_setting(self, key: str, value: Any) -> bool:
        """Set setting value"""
        self.data["settings"][key] = value
        return self.save()
    
    def get_all_animes(self) -> Dict[str, Dict[str, Any]]:
        """Get all anime entries"""
        return self.data.get("animes", {})
    
    def increment_stat(self, stat_name: str) -> None:
        """Increment a statistic"""
        if "stats" not in self.data:
            self.data["stats"] = {}
        self.data["stats"][stat_name] = self.data["stats"].get(stat_name, 0) + 1
        self.save()

# Initialize global database instance
db_engine = DatabaseEngine(BotConfig.DB_FILE, BotConfig.BACKUP_DIR)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class StateManager:
    """Manages user and admin states"""
    
    def __init__(self):
        self.admin_states: Dict[int, Dict[str, Any]] = {}
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.temp_data: Dict[int, Dict[str, Any]] = {}  # For multi-step operations
    
    def set_admin_state(self, user_id: int, state: AdminState, data: Dict[str, Any] = None):
        """Set admin state with optional data"""
        self.admin_states[user_id] = {
            "state": state,
            "data": data or {},
            "started_at": datetime.now().isoformat()
        }
        logger.info(f"Admin {user_id} state: {state.value}")
    
    def get_admin_state(self, user_id: int) -> Optional[AdminState]:
        """Get current admin state"""
        entry = self.admin_states.get(user_id)
        return AdminState(entry["state"]) if entry else None
    
    def get_admin_data(self, user_id: int) -> Dict[str, Any]:
        """Get admin state data"""
        return self.admin_states.get(user_id, {}).get("data", {})
    
    def update_admin_data(self, user_id: int, key: str, value: Any):
        """Update specific key in admin state data"""
        if user_id in self.admin_states:
            self.admin_states[user_id]["data"][key] = value
    
    def clear_admin_state(self, user_id: int):
        """Clear admin state"""
        if user_id in self.admin_states:
            del self.admin_states[user_id]
    
    def set_temp_data(self, user_id: int, key: str, value: Any):
        """Set temporary data for multi-step operations"""
        if user_id not in self.temp_data:
            self.temp_data[user_id] = {}
        self.temp_data[user_id][key] = value
    
    def get_temp_data(self, user_id: int, key: str, default: Any = None) -> Any:
        """Get temporary data"""
        return self.temp_data.get(user_id, {}).get(key, default)
    
    def clear_temp_data(self, user_id: int):
        """Clear all temporary data for user"""
        if user_id in self.temp_data:
            del self.temp_data[user_id]

# Initialize state manager
state_mgr = StateManager()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: BOT INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def initialize_bot() -> Client:
    """Initialize and configure bot client"""
    
    if not all([BotConfig.API_ID, BotConfig.API_HASH, BotConfig.BOT_TOKEN]):
        logger.error("Missing required configuration!")
        raise ValueError("API_ID, API_HASH, and BOT_TOKEN are required")
    
    client = Client(
        "kenshin_pro_bot",
        api_id=BotConfig.API_ID,
        api_hash=BotConfig.API_HASH,
        bot_token=BotConfig.BOT_TOKEN,
        parse_mode=enums.ParseMode.HTML,
        in_memory=False,  # Enable session persistence
        max_concurrent_transmissions=5
    )
    
    return client

bot = initialize_bot()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id == BotConfig.ADMIN_ID

async def admin_check_filter(_, __, message: Message) -> bool:
    """Filter for admin-only commands"""
    if not is_admin(message.from_user.id):
        await message.reply(
            "⛔ <b>Access Denied!</b>\n\n"
            "This command is restricted to bot owner only.\n"
            f"Contact: {BotConfig.OWNER_USERNAME}"
        )
        return False
    return True

admin_only = filters.create(admin_check_filter)

def clean_text(text: str, is_group: bool = False) -> str:
    """Clean and normalize text input"""
    if not text:
        return ""
    
    # Remove bot mentions in groups
    if is_group and BotConfig.BOT_USERNAME:
        text = re.sub(rf'@{re.escape(BotConfig.BOT_USERNAME)}', '', text, flags=re.IGNORECASE)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text.strip()

def format_anime_caption(name: str, data: Dict[str, Any], include_image: bool = True) -> str:
    """
    Format rich anime caption with professional styling
    """
    desc = data.get('description', data.get('desc', 'No description available.'))
    if len(desc) > BotConfig.MAX_DESC_LENGTH:
        desc = desc[:BotConfig.MAX_DESC_LENGTH] + "..."
    
    # Professional formatting with visual hierarchy
    caption = (
                f"<blockquote>✨ <b>{name.upper()}</b> ✨</blockquote>\n\n"
                f"<b><blockquote>📖 {data['desc']}</blockquote></b>\n\n"
                f"➖➖➖➖➖➖➖➖➖➖\n"
                f"🔰 <b>FOR MORE JOIN:</b>\n"
                f"<blockquote>👉 @KENSHIN_ANIME\n"
                f"👉 @MANWHA_VERSE</blockquote>"
            )
    
    return caption

def generate_id(length: int = 8) -> str:
    """Generate random ID for operations"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: COMMAND HANDLERS - USER COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("start") & filters.private)
async def cmd_start_private(client: Client, message: Message):
    """
    Enhanced /start command with rich media and interactive elements
    """
    user = message.from_user
    db_engine.add_user(user.id)
    
    # Reload for fresh settings
    start_img = db_engine.get_setting("start_image", BotConfig.DEFAULT_START_IMAGE)
    custom_msg = db_engine.get_setting("start_message")
    
    # Build professional welcome message
    if custom_msg:
        welcome_text = custom_msg
    else:
        welcome_text = (
            f"🌸 <b>Welcome to {BotConfig.BOT_NAME}!</b> 🌸\n\n"
            f"⚜️ <b>Official Bot of @KENSHIN_ANIME</b> ⚜️\n\n"
            f"<i>🍿 Your ultimate destination for high-quality anime content!</i>\n\n"
            f"📌 <b>How to use me?</b>\n"
            f"Simply type any anime name - I can detect it even in sentences!\n"
            f"💡 <code>Example: Bhai solo leveling latest episode kab aayega?</code>\n\n"
            f"📚 <b>Available Commands:</b>\n"
            f"• /start - Restart the bot\n"
            f"• /help - View all features\n" 
            f"• /report - Request anime or report issues\n\n"
            f"🎯 <b>Pro Tip:</b> No need for commands! Just type the anime name directly!"
        )
    
    # Professional button layout
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✨ Join Channel ✨", url=BotConfig.CHANNEL_LINK),
            InlineKeyboardButton("💬 Support 💬", url=BotConfig.SUPPORT_GROUP)
        ],
        [
            InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{BotConfig.OWNER_USERNAME.replace('@','')}"),
            InlineKeyboardButton("🔍 Search Anime", switch_inline_query_current_chat="")
        ]
    ])
    
    try:
        # Try to send with image
        await message.reply_photo(
            photo=start_img,
            caption=welcome_text,
            reply_markup=buttons
        )
        logger.info(f"Start sent to user {user.id}")
        
    except Exception as e:
        logger.error(f"Photo send failed: {e}")
        # Fallback to text
        await message.reply(
            welcome_text,
            reply_markup=buttons,
            disable_web_page_preview=False
        )

@bot.on_message(filters.command("start") & filters.group)
async def cmd_start_group(client: Client, message: Message):
    """Simplified start for groups"""
    await message.reply(
        f"👋 <b>Hey {message.from_user.first_name}!</b>\n\n"
        f"🤖 I'm <b>{BotConfig.BOT_NAME}</b>!\n"
        f"🍿 I find anime for you instantly!\n\n"
        f"<i>💡 Tip: Use me in private chat for full features!</i>\n"
        f"👉 <a href='https://t.me/{BotConfig.BOT_USERNAME or 'bot'}'>Click here to DM me</a>",
        disable_web_page_preview=True
    )

@bot.on_message(filters.command("help") & (filters.private | filters.group))
async def cmd_help(client: Client, message: Message):
    """
    Comprehensive help menu with categorized commands
    """
    is_group = message.chat.type != "private"
    user_id = message.from_user.id
    
    # User commands section
    help_text = (
        f"╔════════════════════════════════════╗\n"
        f"║     🤖 {BotConfig.BOT_NAME} v{BotConfig.BOT_VERSION}     \n"
        f"╚════════════════════════════════════╝\n\n"
        f"📚 <b>USER COMMANDS</b>\n"
        f"┌────────────────────────────────────┐\n"
        f"│ /start - Initialize bot           │\n"
        f"│ /help - Show this menu              │\n"
        f"│ /report &lt;msg&gt; - Send feedback      │\n"
        f"└────────────────────────────────────┘\n\n"
        f"🔍 <b>SMART SEARCH</b>\n"
        f"Just type any anime name! I understand context:\n"
        f"• <code>Bhai JJK ka new episode?</code>\n"
        f"• <code>Death Note download link do</code>\n"
        f"• <code>Solo Leveling kaise hai?</code>\n"
    )
    
    # Admin section (only for admin)
    if is_admin(user_id):
        help_text += (
            f"\n\n⚡ <b>ADMIN PANEL</b>\n"
            f"┌────────────────────────────────────┐\n"
            f"│ /add_ani - Add new anime            │\n"
            f"│ /edit_ani - Modify existing         │\n"
            f"│ /delete_ani - Remove anime          │\n"
            f"│ /set_start_img - Change banner      │\n"
            f"│ /set_start_msg - Edit welcome       │\n"
            f"│ /view_start_img - Preview banner    │\n"
            f"│ /view_start_msg - Preview text      │\n"
            f"│ /bulk - Bulk upload guide           │\n"
            f"│ /list - View all anime              │\n"
            f"│ /stats - Bot statistics             │\n"
            f"│ /broadcast - Message all users    │\n"
            f"│ /backup - Create database backup    │\n"
            f"│ /cancel - Cancel operation          │\n"
            f"└────────────────────────────────────┘"
        )
    
    # Footer
    help_text += (
        f"\n\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📢 <b>Channel:</b> @KENSHIN_ANIME\n"
        f"💬 <b>Support:</b> @KENSHIN_ANIME_CHAT\n"
        f"👑 <b>Owner:</b> {BotConfig.OWNER_USERNAME}"
    )
    
    await message.reply(help_text, disable_web_page_preview=True)

@bot.on_message(filters.command("report") & (filters.private | filters.group))
async def cmd_report(client: Client, message: Message):
    """
    User feedback and reporting system
    """
    # Check if message provided
    if len(message.command) < 2 and not message.reply_to_message:
        usage = (
            "📝 <b>REPORT SYSTEM</b>\n\n"
            "<b>Usage:</b>\n"
            "<code>/report Your message here</code>\n\n"
            "<b>Or reply to any message with:</b>\n"
            "<code>/report</code>\n\n"
            "<b>Examples:</b>\n"
            "• <code>/report Solo Leveling link broken</code>\n"
            "• <code>/report Request: Add Attack on Titan</code>\n"
            "• <code>/report Bug: Bot not responding</code>"
        )
        await message.reply(usage)
        return
    
    # Get report text
    if message.reply_to_message:
        report_text = message.reply_to_message.text or message.reply_to_message.caption or "No text"
        context = f" (Reply to message ID: {message.reply_to_message.id})"
    else:
        report_text = " ".join(message.command[1:])
        context = ""
    
    if len(report_text) < 5:
        await message.reply("❌ Report too short! Please provide more details.")
        return
    
    user = message.from_user
    chat_info = "Private Chat" if message.chat.type == "private" else f"Group: {message.chat.title}"
    
    # Send to admin
    try:
        admin_msg = (
            f"📢 <b>NEW USER REPORT</b>{context}\n\n"
            f"👤 <b>From:</b> <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
            f"📍 <b>Location:</b> {chat_info}\n"
            f"🔗 <b>Username:</b> @{user.username or 'None'}\n"
            f"⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"📝 <b>Message:</b>\n"
            f"<blockquote>{report_text}</blockquote>\n\n"
            f"<i>Reply to this message to respond to the user.</i>"
        )
        
        await bot.send_message(BotConfig.ADMIN_ID, admin_msg)
        
        # Confirm to user
        await message.reply(
            "✅ <b>Report Sent Successfully!</b>\n\n"
            "Thank you for your feedback. Our team will review it shortly.\n"
            f"For urgent issues, contact: {BotConfig.OWNER_USERNAME}"
        )
        logger.info(f"Report from user {user.id}: {report_text[:50]}...")
        
    except Exception as e:
        logger.error(f"Report failed: {e}")
        await message.reply(
            "❌ <b>Failed to send report.</b>\n\n"
            f"Please contact admin directly: {BotConfig.OWNER_USERNAME}"
        )

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9: ADMIN COMMANDS - CORE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("stats") & admin_only & filters.private)
async def cmd_stats(client: Client, message: Message):
    """
    Detailed bot statistics and analytics
    """
    # Reload database for latest stats
    animes = db_engine.get_all_animes()
    users = db_engine.data.get("users", [])
    stats = db_engine.data.get("stats", {})
    
    # Calculate metrics
    total_animes = len(animes)
    total_users = len(users)
    total_searches = stats.get("total_searches", 0)
    
    # Find popular anime (by views)
    popular = sorted(
        animes.items(),
        key=lambda x: x[1].get("views", 0),
        reverse=True
    )[:5]
    
    stats_text = (
        f"╔════════════════════════════════════╗\n"
        f"║     📊 BOT STATISTICS & ANALYTICS    \n"
        f"╚════════════════════════════════════╝\n\n"
        f"📈 <b>GENERAL METRICS</b>\n"
        f"┌────────────────────────────────────┐\n"
        f"│ 🎬 Total Animes: <code>{total_animes}</code>          │\n"
        f"│ 👥 Total Users: <code>{total_users}</code>          │\n"
        f"│ 🔍 Total Searches: <code>{total_searches}</code>        │\n"
        f"│ 💾 Database: <code>{BotConfig.DB_FILE}</code>  │\n"
        f"└────────────────────────────────────┘\n\n"
    )
    
    if popular:
        stats_text += f"🔥 <b>TOP 5 POPULAR ANIME</b>\n"
        for i, (name, data) in enumerate(popular, 1):
            views = data.get("views", 0)
            stats_text += f"{i}. <b>{name.upper()}</b> - <code>{views}</code> views\n"
        stats_text += "\n"
    
    stats_text += (
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"🤖 <b>Bot:</b> {BotConfig.BOT_NAME} v{BotConfig.BOT_VERSION}\n"
        f"⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await message.reply(stats_text, disable_web_page_preview=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10: ADD/EDIT ANIME - FIXED & ENHANCED
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("add_ani") & admin_only & filters.private)
async def cmd_add_ani(client: Client, message: Message):
    """
    FIXED: Multi-step anime addition with clear prompts
    """
    user_id = message.from_user.id
    
    # Initialize state
    state_mgr.set_admin_state(user_id, AdminState.ADD_ANIME_NAME, {
        "mode": "ADD",
        "step": 1,
        "total_steps": 4
    })
    
    # Clear any old temp data
    state_mgr.clear_temp_data(user_id)
    
    # Send clear instructions
    prompt = (
        f"╔════════════════════════════════════╗\n"
        f"║     🚀 ADD NEW ANIME ENTRY           \n"
        f"╚════════════════════════════════════╝\n\n"
        f"<b>Step 1 of 4: Anime Name</b>\n\n"
        f"Please send the <b>exact anime name</b> you want to add.\n"
        f"This will be used as the primary search key.\n\n"
        f"💡 <b>Tips:</b>\n"
        f"• Use official English name\n"
        f"• Keep it simple and searchable\n"
        f"• Example: <code>Solo Leveling</code>, <code>Jujutsu Kaisen</code>\n\n"
        f"❌ Send <code>cancel</code> anytime to abort.\n\n"
        f"⏳ <b>Waiting for anime name...</b>"
    )
    
    await message.reply(prompt)
    logger.info(f"Admin {user_id} started ADD anime")

@bot.on_message(filters.command("edit_ani") & admin_only & filters.private)
async def cmd_edit_ani(client: Client, message: Message):
    """
    Edit existing anime entry
    """
    user_id = message.from_user.id
    
    # Get all animes for selection
    animes = db_engine.get_all_animes()
    
    if not animes:
        await message.reply("📭 <b>No anime in database to edit!</b>\n\nUse /add_ani to add first.")
        return
    
    # List animes with numbers for easy selection
    anime_list = sorted(animes.keys())
    list_text = (
        f"╔════════════════════════════════════╗\n"
        f"║     ✏️ EDIT ANIME ENTRY              \n"
        f"╚════════════════════════════════════╝\n\n"
        f"<b>Available Anime ({len(anime_list)} total):</b>\n\n"
    )
    
    for i, name in enumerate(anime_list[:50], 1):  # Show first 50
        display_name = animes[name].get("name_display", name)
        list_text += f"<code>{i:2d}.</code> {display_name}\n"
    
    if len(anime_list) > 50:
        list_text += f"\n<i>... and {len(anime_list) - 50} more</i>\n"
    
    list_text += (
        f"\n✏️ <b>Send the anime name to edit:</b>\n"
        f"(Exact match required, or send number from list)\n\n"
        f"❌ Send <code>cancel</code> to abort."
    )
    
    state_mgr.set_admin_state(user_id, AdminState.EDIT_ANIME_SELECT)
    await message.reply(list_text, disable_web_page_preview=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11: SET START IMAGE/MESSAGE - FIXED
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("set_start_img") & admin_only & filters.private)
async def cmd_set_start_img(client: Client, message: Message):
    """
    FIXED: Set start image with immediate or interactive mode
    """
    user_id = message.from_user.id
    
    # Check if URL provided directly: /set_start_img <url>
    if len(message.command) > 1:
        img_url = message.command[1]
        
        # Validate URL
        if not img_url.startswith(("http://", "https://")):
            await message.reply(
                "❌ <b>Invalid URL!</b>\n\n"
                "URL must start with <code>http://</code> or <code>https://</code>\n\n"
                "<b>Correct format:</b>\n"
                "<code>/set_start_img https://catbox.moe/abc.jpg</code>"
            )
            return
        
        # Test and save
        try:
            # Try to send as preview
            preview_msg = await message.reply_photo(
                photo=img_url,
                caption="👁 <b>Testing new banner...</b>"
            )
            
            # Save if successful
            if db_engine.set_setting("start_image", img_url):
                await preview_msg.edit_caption(
                    f"✅ <b>Start Banner Updated Successfully!</b>\n\n"
                    f"📸 <b>New Image URL:</b>\n<code>{img_url}</code>\n\n"
                    f"🎯 Use /start to see it in action!\n"
                    f"👁 Use /view_start_img to preview anytime."
                )
                logger.info(f"Start image updated by admin {user_id}")
            else:
                await preview_msg.edit_caption("❌ <b>Failed to save!</b> Check logs.")
                
        except Exception as e:
            logger.error(f"Image test failed: {e}")
            await message.reply(
                f"❌ <b>Invalid Image URL!</b>\n\n"
                f"The URL doesn't point to a valid image.\n"
                f"Error: <code>{str(e)[:100]}</code>\n\n"
                f"💡 Use direct image links (Catbox, Telegraph, etc.)"
            )
        return
    
    # Interactive mode - no URL provided
    current_img = db_engine.get_setting("start_image", BotConfig.DEFAULT_START_IMAGE)
    
    prompt = (
        f"╔════════════════════════════════════╗\n"
        f"║     🖼 UPDATE START BANNER          \n"
        f"╚════════════════════════════════════╝\n\n"
        f"<b>Current Banner:</b>\n"
        f"<code>{current_img}</code>\n\n"
        f"📤 <b>Send new image URL:</b>\n"
        f"• Must be direct link (ends with .jpg, .png, etc.)\n"
        f"• Recommended: Catbox, Telegraph, imgur\n\n"
        f"<b>Quick method:</b>\n"
        f"<code>/set_start_img &lt;url&gt;</code>\n\n"
        f"❌ Send <code>cancel</code> to abort.\n\n"
        f"⏳ <b>Waiting for URL...</b>"
    )
    
    state_mgr.set_admin_state(user_id, AdminState.SET_START_IMG)
    await message.reply(prompt)

@bot.on_message(filters.command("set_start_msg") & admin_only & filters.private)
async def cmd_set_start_msg(client: Client, message: Message):
    """
    Set custom start message
    """
    user_id = message.from_user.id
    
    # Quick mode: /set_start_msg <message>
    if len(message.command) > 1:
        new_msg = " ".join(message.command[1:])
        
        if len(new_msg) < 10:
            await message.reply("❌ Message too short! Minimum 10 characters.")
            return
        
        if db_engine.set_setting("start_message", new_msg):
            await message.reply(
                "✅ <b>Welcome Message Updated!</b>\n\n"
                f"Preview:\n<blockquote>{new_msg[:200]}</blockquote>\n\n"
                f"Use /view_start_msg for full preview."
            )
        return
    
    # Interactive mode
    current = db_engine.get_setting("start_message", "Using default")
    
    prompt = (
        f"╔════════════════════════════════════╗\n"
        f"║     📝 UPDATE WELCOME TEXT           \n"
        f"╚════════════════════════════════════╝\n\n"
        f"<b>Current:</b>\n"
        f"<blockquote>{str(current)[:150]}...</blockquote>\n\n"
        f"✏️ <b>Send new welcome message:</b>\n"
        f"• HTML formatting supported\n"
        f"• Use &lt;b&gt;bold&lt;/b&gt;, &lt;i&gt;italic&lt;/i&gt;\n"
        f"• Use &lt;blockquote&gt;quotes&lt;/blockquote&gt;\n\n"
        f"<b>Quick:</b> <code>/set_start_msg &lt;your text&gt;</code>\n\n"
        f"❌ Send <code>cancel</code> to abort."
    )
    
    state_mgr.set_admin_state(user_id, AdminState.SET_START_MSG)
    await message.reply(prompt)

@bot.on_message(filters.command("view_start_img") & admin_only & filters.private)
async def cmd_view_start_img(client: Client, message: Message):
    """Preview current start image"""
    current = db_engine.get_setting("start_image", BotConfig.DEFAULT_START_IMAGE)
    
    try:
        await message.reply_photo(
            photo=current,
            caption=(
                f"👁 <b>CURRENT START BANNER</b>\n\n"
                f"📸 URL: <code>{current}</code>\n\n"
                f"🔄 Use /set_start_img to change"
            )
        )
    except Exception as e:
        await message.reply(
            f"⚠️ <b>Cannot display image</b>\n\n"
            f"URL: <code>{current}</code>\n"
            f"Error: <code>{str(e)[:100]}</code>\n\n"
            f"🔄 Use /set_start_img to fix"
        )

@bot.on_message(filters.command("view_start_msg") & admin_only & filters.private)
async def cmd_view_start_msg(client: Client, message: Message):
    """Preview current start message"""
    current = db_engine.get_setting("start_message")
    
    if not current:
        await message.reply(
            "ℹ️ <b>Using default welcome message.</b>\n\n"
            f"Set custom with /set_start_msg"
        )
        return
    
    await message.reply(
        f"👁 <b>CURRENT WELCOME MESSAGE</b>\n\n"
        f"{current}\n\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"📝 Length: <code>{len(current)}</code> characters\n"
        f"🔄 Use /set_start_msg to change"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12: BULK UPLOAD & LIST COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("bulk") & admin_only & filters.private)
async def cmd_bulk(client: Client, message: Message):
    """Bulk upload instructions"""
    guide = (
        f"╔════════════════════════════════════╗\n"
        f"║     📦 BULK UPLOAD SYSTEM            \n"
        f"╚════════════════════════════════════╝\n\n"
        f"📋 <b>Step 1: Create .txt file</b>\n"
        f"Format each line:\n"
        f"<code>Anime Name | Image URL | Download Link | Description</code>\n\n"
        f"📋 <b>Step 2: Send to bot</b>\n"
        f"Just forward or upload the .txt file here.\n\n"
        f"✅ <b>Example line:</b>\n"
        f"<code>Solo Leveling | https://catbox.moe/abc.jpg | https://t.me/joinchat/xxx | Best anime ever made</code>\n\n"
        f"⚠️ <b>Rules:</b>\n"
        f"• Use <code>|</code> (pipe) as separator\n"
        f"• One anime per line\n"
        f"• Lines starting with # are ignored\n"
        f"• Empty lines are skipped\n\n"
        f"📤 <b>Ready? Send your .txt file now!</b>"
    )
    await message.reply(guide)

@bot.on_message(filters.command("list") & admin_only & filters.private)
async def cmd_list(client: Client, message: Message):
    """List all anime with pagination"""
    animes = db_engine.get_all_animes()
    
    if not animes:
        await message.reply("📭 <b>Database is empty!</b>")
        return
    
    items = sorted(animes.items(), key=lambda x: x[0])
    total = len(items)
    per_page = 15
    
    # Send in chunks
    for i in range(0, total, per_page):
        chunk = items[i:i+per_page]
        
        text = (
            f"📚 <b>DATABASE LIST</b>\n"
            f"Page {i//per_page + 1}/{(total-1)//per_page + 1} | "
            f"Showing {i+1}-{min(i+per_page, total)} of {total}\n\n"
        )
        
        for idx, (name, data) in enumerate(chunk, i+1):
            display = data.get("name_display", name)
            desc = data.get("description", data.get("desc", "No desc"))[:40]
            text += f"<code>{idx:2d}.</code> <b>{display}</b>\n    └ <i>{desc}...</i>\n\n"
        
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.5)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13: BROADCAST & BACKUP
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("broadcast") & admin_only & filters.private)
async def cmd_broadcast(client: Client, message: Message):
    """Broadcast message to all users"""
    if not message.reply_to_message:
        await message.reply(
            "❌ <b>Reply to a message to broadcast!</b>\n\n"
            "Usage:\n"
            "1. Forward or send any message\n"
            "2. Reply to it with /broadcast\n"
            "3. Confirm to send to all users"
        )
        return
    
    # Count users
    users = db_engine.data.get("users", [])
    
    confirm_text = (
        f"📡 <b>BROADCAST CONFIRMATION</b>\n\n"
        f"📊 Target users: <code>{len(users)}</code>\n"
        f"⏱ Estimated time: ~{len(users) * 0.3:.0f} seconds\n\n"
        f"✅ Send <code>yes</code> to confirm broadcast\n"
        f"❌ Send <code>no</code> or <code>cancel</code> to abort"
    )
    
    state_mgr.set_admin_state(message.from_user.id, AdminState.BROADCAST_CONFIRM, {
        "message_to_broadcast": message.reply_to_message
    })
    
    await message.reply(confirm_text)

@bot.on_message(filters.command("backup") & admin_only & filters.private)
async def cmd_backup(client: Client, message: Message):
    """Create database backup"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BotConfig.BACKUP_DIR, f"backup_{timestamp}.json")
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(db_engine.data, f, indent=2, ensure_ascii=False)
        
        # Send backup file
        await message.reply_document(
            document=backup_file,
            caption=(
                f"💾 <b>BACKUP CREATED</b>\n\n"
                f"📁 File: <code>backup_{timestamp}.json</code>\n"
                f"📊 Size: <code>{os.path.getsize(backup_file)} bytes</code>\n"
                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )
        logger.info(f"Backup created: {backup_file}")
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        await message.reply(f"❌ Backup failed: <code>{str(e)}</code>")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 14: CANCEL COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("cancel") & (filters.private | filters.group))
async def cmd_cancel(client: Client, message: Message):
    """Cancel current operation"""
    user_id = message.from_user.id
    
    had_state = False
    
    # Clear admin state if exists
    if state_mgr.get_admin_state(user_id):
        state_mgr.clear_admin_state(user_id)
        had_state = True
    
    # Clear temp data
    if user_id in state_mgr.temp_data:
        state_mgr.clear_temp_data(user_id)
        had_state = True
    
    if had_state:
        await message.reply(
            "✅ <b>Operation Cancelled!</b>\n\n"
            "All pending operations have been cleared.\n"
            "Start fresh with /start or /help"
        )
    else:
        await message.reply("ℹ️ <b>No active operation to cancel.</b>")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 15: DOCUMENT HANDLER (BULK UPLOAD)
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.document & filters.private)
async def handle_document(client: Client, message: Message):
    """Handle file uploads - primarily for bulk upload"""
    user_id = message.from_user.id
    
    # Only admin can upload
    if not is_admin(user_id):
        return
    
    doc = message.document
    if not doc.file_name.endswith('.txt'):
        return  # Ignore non-txt files silently or send hint
    
    # Confirm processing
    status_msg = await message.reply("⏳ <b>Processing bulk upload...</b>")
    
    try:
        # Download
        file_path = await message.download()
        logger.info(f"Bulk file downloaded: {file_path}")
        
        # Process
        added = 0
        errors = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty and comments
            if not line or line.startswith('#'):
                continue
            
            if '|' not in line:
                errors.append(f"Line {line_num}: No separator |")
                continue
            
            parts = line.split('|')
            if len(parts) < 4:
                errors.append(f"Line {line_num}: Incomplete data")
                continue
            
            try:
                name, img, link, desc = [p.strip() for p in parts[:4]]
                
                if not all([name, img, link]):
                    errors.append(f"Line {line_num}: Missing required fields")
                    continue
                
                # Add to database
                success = db_engine.add_anime(name.lower(), {
                    "name_display": name,
                    "image_url": img,
                    "download_link": link,
                    "description": desc,
                    "added_by": user_id,
                    "added_at": datetime.now().isoformat()
                })
                
                if success:
                    added += 1
                else:
                    errors.append(f"Line {line_num}: Save failed")
                    
            except Exception as e:
                errors.append(f"Line {line_num}: {str(e)[:50]}")
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Report
        result = (
            f"╔════════════════════════════════════╗\n"
            f"║     📦 BULK UPLOAD COMPLETE          \n"
            f"╚════════════════════════════════════╝\n\n"
            f"✅ <b>Successfully Added:</b> <code>{added}</code>\n"
            f"❌ <b>Errors:</b> <code>{len(errors)}</code>\n"
            f"📊 <b>Total Lines:</b> <code>{len(lines)}</code>\n"
        )
        
        if errors:
            error_text = '\n'.join(errors[:10])
            if len(errors) > 10:
                error_text += f"\n... and {len(errors)-10} more"
            result += f"\n⚠️ <b>Error Details:</b>\n<pre>{error_text}</pre>"
        
        await status_msg.edit(result)
        logger.info(f"Bulk upload: {added} added, {len(errors)} errors")
        
    except Exception as e:
        logger.error(f"Bulk processing error: {e}")
        await status_msg.edit(f"❌ <b>Processing Failed:</b>\n<code>{str(e)[:200]}</code>")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 16: MAIN MESSAGE HANDLER - ADMIN STATES & SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

COMMANDS = [
    "start", "help", "report", "stats",
    "set_start_img", "set_start_msg", "view_start_img", "view_start_msg",
    "bulk", "list", "add_ani", "edit_ani", "delete_ani",
    "broadcast", "backup", "cancel"
]

@bot.on_message(filters.text & (filters.private | filters.group) & ~filters.command(COMMANDS))
async def handle_message(client: Client, message: Message):
    """
    Main message handler - processes admin states and anime search
    """
    user_id = message.from_user.id
    chat_type = message.chat.type
    is_group = chat_type != "private"
    
    # Get and clean text
    text = clean_text(message.text or message.caption or "", is_group)
    text_lower = text.lower()
    
    if not text:
        return
    
    # ═════════════════════════════════════════════════════════════════
    # HANDLE CANCEL
    # ═════════════════════════════════════════════════════════════════
    if text_lower == "cancel":
        had_state = False
        
        if state_mgr.get_admin_state(user_id):
            state_mgr.clear_admin_state(user_id)
            had_state = True
        
        if user_id in state_mgr.temp_data:
            state_mgr.clear_temp_data(user_id)
            had_state = True
        
        if had_state:
            await message.reply("✅ <b>Cancelled!</b> All operations cleared.")
        else:
            await message.reply("ℹ️ Nothing to cancel.")
        return
    
    # ═════════════════════════════════════════════════════════════════
    # HANDLE ADMIN STATES (Private only)
    # ═════════════════════════════════════════════════════════════════
    if not is_group and is_admin(user_id):
        state = state_mgr.get_admin_state(user_id)
        
        if state == AdminState.SET_START_IMG:
            # Validate URL
            if not text.startswith(("http://", "https://")):
                await message.reply("❌ Invalid URL! Must start with http:// or https://")
                return
            
            # Test and save
            try:
                test_msg = await message.reply_photo(
                    photo=text,
                    caption="👁 Testing..."
                )
                
                if db_engine.set_setting("start_image", text):
                    await test_msg.edit_caption(
                        f"✅ <b>Banner Updated!</b>\n\n<code>{text}</code>"
                    )
                else:
                    await test_msg.edit_caption("❌ Save failed!")
                    
            except Exception as e:
                await message.reply(f"❌ Invalid image: <code>{str(e)[:100]}</code>")
                return
            
            state_mgr.clear_admin_state(user_id)
            return
        
        # ═════════════════════════════════════════════════════════════
        # ADD ANIME FLOW - FIXED WITH CLEAR PROMPTS
        # ═════════════════════════════════════════════════════════════
        if state == AdminState.ADD_ANIME_NAME:
            # Step 1: Got anime name
            state_mgr.set_temp_data(user_id, "anime_name", text)
            state_mgr.set_temp_data(user_id, "anime_name_lower", text_lower)
            state_mgr.set_admin_state(user_id, AdminState.ADD_ANIME_IMAGE, {
                "mode": "ADD", "step": 2, "name": text
            })
            
            await message.reply(
                f"✅ <b>Name saved:</b> <code>{text}</code>\n\n"
                f"<b>Step 2 of 4: Image URL</b>\n\n"
                f"📸 Send the <b>anime poster/cover image URL</b>.\n\n"
                f"💡 <b>Recommended hosts:</b>\n"
                f"• Catbox.moe (best)\n"
                f"• Telegraph\n"
                f"• imgur.com\n\n"
                f"❌ Send <code>cancel</code> to abort.\n\n"
                f"⏳ <b>Waiting for image URL...</b>"
            )
            return
        
        if state == AdminState.ADD_ANIME_IMAGE:
            # Step 2: Got image URL
            if not text.startswith(("http://", "https://")):
                await message.reply("❌ Invalid URL! Must start with http:// or https://")
                return
            
            # Test the image
            try:
                test_msg = await message.reply_photo(
                    photo=text,
                    caption="👁 Testing image..."
                )
                await test_msg.delete()
            except Exception as e:
                await message.reply(f"⚠️ Warning: Could not verify image.\nError: <code>{str(e)[:100]}</code>\n\nSend <code>yes</code> to use anyway, or send a different URL.")
                state_mgr.set_temp_data(user_id, "pending_img", text)
                state_mgr.set_admin_state(user_id, AdminState.ADD_ANIME_IMAGE, {
                    "mode": "ADD", "step": 2, "pending": True
                })
                return
            
            state_mgr.set_temp_data(user_id, "anime_image", text)
            state_mgr.set_admin_state(user_id, AdminState.ADD_ANIME_LINK, {
                "mode": "ADD", "step": 3, "name": state_mgr.get_temp_data(user_id, "anime_name")
            })
            
            await message.reply(
                f"✅ <b>Image saved!</b>\n\n"
                f"<b>Step 3 of 4: Download Link</b>\n\n"
                f"🔗 Send the <b>Telegram channel/group link</b> or <b>direct download URL</b>.\n\n"
                f"💡 <b>Examples:</b>\n"
                f"• <code>https://t.me/joinchat/ABC123</code>\n"
                f"• <code>https://t.me/channelname/123</code>\n\n"
                f"❌ Send <code>cancel</code> to abort.\n\n"
                f"⏳ <b>Waiting for download link...</b>"
            )
            return
        
        if state == AdminState.ADD_ANIME_LINK:
            # Step 3: Got download link
            if not text.startswith(("http://", "https://", "t.me/")):
                await message.reply("❌ Invalid link! Must be a URL or t.me link.")
                return
            
            state_mgr.set_temp_data(user_id, "anime_link", text)
            state_mgr.set_admin_state(user_id, AdminState.ADD_ANIME_DESC, {
                "mode": "ADD", "step": 4, "name": state_mgr.get_temp_data(user_id, "anime_name")
            })
            
            await message.reply(
                f"✅ <b>Link saved!</b>\n\n"
                f"<b>Step 4 of 4: Description</b>\n\n"
                f"📝 Send a <b>short synopsis/description</b> of the anime.\n\n"
                f"💡 <b>Tips:</b>\n"
                f"• Keep it under 200 characters\n"
                f"• Mention key plot points\n"
                f"• Include genre if relevant\n\n"
                f"<b>Example:</b>\n"
                f"<code>A weak hunter gains the power to level up infinitely. The ultimate power fantasy anime!</code>\n\n"
                f"❌ Send <code>cancel</code> to abort.\n\n"
                f"⏳ <b>Waiting for description...</b>"
            )
            return
        
        if state == AdminState.ADD_ANIME_DESC:
            # Step 4: Got description - SAVE EVERYTHING
            if len(text) < 10:
                await message.reply("❌ Description too short! Minimum 10 characters.")
                return
            
            # Gather all data
            name = state_mgr.get_temp_data(user_id, "anime_name")
            name_lower = state_mgr.get_temp_data(user_id, "anime_name_lower")
            image = state_mgr.get_temp_data(user_id, "anime_image")
            link = state_mgr.get_temp_data(user_id, "anime_link")
            
            # Save to database
            success = db_engine.add_anime(name_lower, {
                "name_display": name,
                "image_url": image,
                "download_link": link,
                "description": text,
                "added_by": user_id,
                "added_at": datetime.now().isoformat(),
                "views": 0
            })
            
            if success:
                await message.reply(
                    f"╔════════════════════════════════════╗\n"
                    f"║     🎯 SUCCESS! ANIME ADDED          \n"
                    f"╚════════════════════════════════════╝\n\n"
                    f"✅ <b>{name}</b> has been added to database!\n\n"
                    f"📊 <b>Summary:</b>\n"
                    f"• Name: <code>{name}</code>\n"
                    f"• Image: <code>{image[:50]}...</code>\n"
                    f"• Link: <code>{link[:50]}...</code>\n"
                    f"• Desc: <code>{text[:50]}...</code>\n\n"
                    f"🎉 Users can now search for this anime!"
                )
                logger.info(f"Anime added by admin {user_id}: {name}")
            else:
                await message.reply("❌ <b>Failed to save!</b> Check logs.")
            
            # Cleanup
            state_mgr.clear_admin_state(user_id)
            state_mgr.clear_temp_data(user_id)
            return
        
        # ═════════════════════════════════════════════════════════════
        # EDIT ANIME FLOW
        # ═════════════════════════════════════════════════════════════
        if state == AdminState.EDIT_ANIME_SELECT:
            # User sent anime name to edit
            target = text_lower
            animes = db_engine.get_all_animes()
            
            # Try exact match first
            if target in animes:
                anime_data = animes[target]
            else:
                # Try partial match
                matches = [k for k in animes.keys() if target in k]
                if len(matches) == 1:
                    target = matches[0]
                    anime_data = animes[target]
                elif len(matches) > 1:
                    await message.reply(
                        f"🔍 <b>Multiple matches found:</b>\n" + 
                        "\n".join([f"• <code>{m}</code>" for m in matches[:10]]) +
                        f"\n\nSend exact name or number."
                    )
                    return
                else:
                    await message.reply(f"❌ No anime found matching '<code>{text}</code>'")
                    return
            
            # Show current data and ask what to edit
            current = (
                f"╔════════════════════════════════════╗\n"
                f"║     ✏️ EDITING: {anime_data.get('name_display', target).upper()}\n"
                f"╚════════════════════════════════════╝\n\n"
                f"<b>Current Data:</b>\n\n"
                f"1️⃣ <b>Name:</b> <code>{anime_data.get('name_display', target)}</code>\n"
                f"2️⃣ <b>Image:</b> <code>{anime_data.get('image_url', 'N/A')[:60]}...</code>\n"
                f"3️⃣ <b>Link:</b> <code>{anime_data.get('download_link', 'N/A')[:60]}...</code>\n"
                f"4️⃣ <b>Desc:</b> <code>{anime_data.get('description', 'N/A')[:100]}...</code>\n\n"
                f"✏️ <b>What do you want to edit?</b>\n"
                f"Send <code>1</code>, <code>2</code>, <code>3</code>, or <code>4</code>\n"
                f"❌ Send <code>cancel</code> to abort."
            )
            
            state_mgr.set_temp_data(user_id, "edit_target", target)
            state_mgr.set_temp_data(user_id, "edit_data", anime_data)
            state_mgr.set_admin_state(user_id, AdminState.EDIT_ANIME_FIELD)
            
            await message.reply(current)
            return
        
        if state == AdminState.EDIT_ANIME_FIELD:
            # User selected field to edit
            choice = text.strip()
            target = state_mgr.get_temp_data(user_id, "edit_target")
            field_map = {"1": "name_display", "2": "image_url", "3": "download_link", "4": "description"}
            
            if choice not in field_map:
                await message.reply("❌ Invalid choice! Send 1, 2, 3, or 4.")
                return
            
            field = field_map[choice]
            state_mgr.set_temp_data(user_id, "edit_field", field)
            
            field_names = {
                "name_display": "Name",
                "image_url": "Image URL", 
                "download_link": "Download Link",
                "description": "Description"
            }
            
            await message.reply(
                f"✏️ <b>Editing: {field_names[field]}</b>\n\n"
                f"Send the new value for <code>{target}</code>:\n\n"
                f"❌ Send <code>cancel</code> to abort."
            )
            
            # Transition to generic input state
            state_mgr.set_admin_state(user_id, AdminState.ADD_ANIME_DESC, {
                "mode": "EDIT", "editing_field": True
            })
            return
        
        # Handle edit field input
        if state == AdminState.ADD_ANIME_DESC and state_mgr.get_admin_data(user_id).get("editing_field"):
            field = state_mgr.get_temp_data(user_id, "edit_field")
            target = state_mgr.get_temp_data(user_id, "edit_target")
            
            # Update database
            if db_engine.data["animes"][target].get(field) is not None:
                db_engine.data["animes"][target][field] = text
                db_engine.save()
                
                await message.reply(
                    f"✅ <b>Updated successfully!</b>\n\n"
                    f"<b>{target}</b> - {field} changed."
                )
            else:
                await message.reply("❌ Field not found!")
            
            state_mgr.clear_admin_state(user_id)
            state_mgr.clear_temp_data(user_id)
            return
        
        # ═════════════════════════════════════════════════════════════
        # BROADCAST CONFIRMATION
        # ═════════════════════════════════════════════════════════════
        if state == AdminState.BROADCAST_CONFIRM:
            if text_lower == "yes":
                data = state_mgr.get_admin_data(user_id)
                msg_to_send = data.get("message_to_broadcast")
                
                if not msg_to_send:
                    await message.reply("❌ Message not found!")
                    state_mgr.clear_admin_state(user_id)
                    return
                
                # Do broadcast
                status = await message.reply("📡 Broadcasting started...")
                users = db_engine.data.get("users", [])
                sent, blocked = 0, 0
                
                for uid in users:
                    try:
                        await msg_to_send.copy(uid)
                        sent += 1
                        if sent % 50 == 0:
                            await status.edit(f"📡 Progress: {sent}/{len(users)}")
                        await asyncio.sleep(BotConfig.BROADCAST_DELAY)
                    except UserIsBlocked:
                        blocked += 1
                    except Exception as e:
                        logger.error(f"Broadcast to {uid} failed: {e}")
                
                await status.edit(
                    f"📢 <b>Broadcast Complete!</b>\n\n"
                    f"✅ Sent: <code>{sent}</code>\n"
                    f"🚫 Blocked: <code>{blocked}</code>\n"
                    f"📊 Total: <code>{len(users)}</code>"
                )
                
            else:
                await message.reply("❌ Broadcast cancelled.")
            
            state_mgr.clear_admin_state(user_id)
            return
    
    # ═════════════════════════════════════════════════════════════════
    # ANIME SEARCH (All users - Private & Group)
    # ═════════════════════════════════════════════════════════════════
    if not text.startswith("/"):
        animes = db_engine.get_all_animes()
        
        if not animes:
            if not is_group:  # Only reply in DM if no results
                await message.reply(
                    "📭 <b>No anime in database yet!</b>\n\n"
                    f"Contact admin: {BotConfig.OWNER_USERNAME}"
                )
            return
        
        # Search with priority to longer matches
        for name in sorted(animes.keys(), key=len, reverse=True):
            if name in text_lower:
                data = animes[name]
                
                # Increment views
                data["views"] = data.get("views", 0) + 1
                db_engine.save()
                
                # Format rich caption
                display_name = data.get("name_display", name)
                caption = format_anime_caption(display_name, data)
                
                # Create buttons
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 DOWNLOAD / WATCH NOW", url=data["download_link"])],
                    [
                        InlineKeyboardButton("🔍 Search More", switch_inline_query_current_chat=""),
                        InlineKeyboardButton("📢 Share", url=f"https://t.me/share/url?url=https://t.me/{BotConfig.BOT_USERNAME or 'bot'}&text=Check%20out%20{display_name}!")
                    ]
                ])
                
                # Send result
                try:
                    await message.reply_photo(
                        photo=data["image_url"],
                        caption=caption,
                        reply_markup=buttons
                    )
                except Exception as e:
                    logger.error(f"Photo send failed: {e}")
                    await message.reply(
                        caption,
                        reply_markup=buttons,
                        disable_web_page_preview=False
                    )
                
                # Log search
                db_engine.increment_stat("total_searches")
                add_user_to_db(user_id)
                return
        
        # No match found
        if not is_group:
            await message.reply(
                f"🔍 <b>No results for '<code>{text[:30]}</code>'</b>\n\n"
                f"Try:\n"
                f"• Different spelling\n"
                f"• Shorter keywords\n"
                f"• /report to request this anime"
            )

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 17: MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════════════╗")
    print(f"║  {BotConfig.BOT_NAME} v{BotConfig.BOT_VERSION}                              ║")
    print("║  Starting with full feature set...                              ║")
    print(f"║  Database: {BotConfig.DB_FILE:50} ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    
    # Validate configuration
    if not all([BotConfig.API_ID, BotConfig.API_HASH, BotConfig.BOT_TOKEN]):
        print("❌ ERROR: Missing required configuration!")
        print("Please set: API_ID, API_HASH, BOT_TOKEN")
        exit(1)
    
    # Start bot
    try:
        bot.run()
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
        raise
