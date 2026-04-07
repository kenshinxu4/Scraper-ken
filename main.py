#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           🔥 KENSHIN ANIME BOT - ULTIMATE EDITION v5.1 🔥                      ║
║        TXT Bulk Upload | JSON | CSV | All Commands Fixed | Full Heavy           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import asyncio
import logging
import re
import csv
import io
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter

from pyrogram import Client, filters, errors, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import UserIsBlocked, MessageNotModified

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
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/data/backups")
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
        # Ensure backup dir exists
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR, exist_ok=True)
    
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
            },
            "stats": {
                "searches": 0,
                "downloads": 0,
                "added_at": datetime.now().isoformat()
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
    
    def increment_stat(self, stat_name: str):
        """Increment a stat counter"""
        if "stats" not in self.data:
            self.data["stats"] = {}
        self.data["stats"][stat_name] = self.data["stats"].get(stat_name, 0) + 1
        self.save()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive stats"""
        animes = self.get_all_animes()
        total_animes = len(animes)
        total_users = len(self.data.get("users", []))
        total_aliases = len(self.data.get("aliases", {}))
        
        # Calculate total views
        total_views = sum(a.get("views", 0) for a in animes.values())
        
        # Get most viewed animes
        sorted_animes = sorted(
            animes.items(), 
            key=lambda x: x[1].get("views", 0), 
            reverse=True
        )[:10]
        
        # Get recently added
        recent_animes = sorted(
            animes.items(),
            key=lambda x: x[1].get("added_at", ""),
            reverse=True
        )[:5]
        
        return {
            "total_animes": total_animes,
            "total_users": total_users,
            "total_aliases": total_aliases,
            "total_views": total_views,
            "top_animes": sorted_animes,
            "recent_animes": recent_animes,
            "system_stats": self.data.get("stats", {})
        }
    
    def export_to_json(self) -> str:
        """Export database to JSON string"""
        return json.dumps(self.data, indent=2, ensure_ascii=False)
    
    def export_to_csv(self) -> str:
        """Export animes to CSV format"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Name", "Display Name", "Image URL", "Download Link", 
            "Description", "Aliases", "Views", "Added At"
        ])
        
        # Write data
        for key, data in self.data.get("animes", {}).items():
            writer.writerow([
                key,
                data.get("name_display", ""),
                data.get("image_url", ""),
                data.get("download_link", ""),
                data.get("desc", ""),
                "|".join(data.get("aliases", [])),
                data.get("views", 0),
                data.get("added_at", "")
            ])
        
        return output.getvalue()
    
    def bulk_import(self, data_list: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Bulk import animes from list of dicts
        Returns: (success_count, fail_count)
        """
        success = 0
        failed = 0
        
        for item in data_list:
            try:
                name = item.get("name") or item.get("name_display")
                if not name:
                    failed += 1
                    continue
                
                # Check if exists
                existing = self.get_anime(name)
                if existing:
                    # Update instead of skip
                    self.update_anime_field(
                        existing["_key"], 
                        "download_link", 
                        item.get("download_link", existing.get("download_link"))
                    )
                    success += 1
                    continue
                
                anime_data = {
                    "name_display": item.get("name_display", name),
                    "image_url": item.get("image_url", DEFAULT_START_IMAGE),
                    "download_link": item.get("download_link", ""),
                    "desc": item.get("desc", "No description"),
                    "aliases": item.get("aliases", []),
                    "added_by": ADMIN_ID,
                    "added_at": datetime.now().isoformat(),
                    "views": 0
                }
                
                if self.add_anime(name, anime_data):
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Bulk import error: {e}")
                failed += 1
        
        return success, failed

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
    
    @staticmethod
    def search_anime(query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search animes by query and return sorted results"""
        if not query:
            return []
        
        query_clean = SearchEngine.normalize(query)
        animes = db.get_all_animes()
        results = []
        
        for key, data in animes.items():
            score = 0
            name_display = data.get("name_display", key).lower()
            aliases = [a.lower() for a in data.get("aliases", [])]
            
            # Exact match
            if query_clean == name_display:
                score = 100
            # Starts with
            elif name_display.startswith(query_clean):
                score = 80
            # Contains
            elif query_clean in name_display:
                score = 60
            # Alias exact match
            elif query_clean in aliases:
                score = 50
            # Alias contains
            else:
                for alias in aliases:
                    if query_clean in alias:
                        score = 40
                        break
            
            if score > 0:
                results.append({**data, "_key": key, "_score": score})
        
        # Sort by score descending
        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:limit]

# ═══════════════════════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════════════════════

def clean_text(text: str, is_group: bool = False) -> str:
    if not text:
        return ""
    if is_group and BOT_USERNAME:
        text = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.IGNORECASE)
    return ' '.join(text.split()).strip()

def format_bytes(size):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

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
        "• /search &lt;name&gt; - Search anime by name\n"
        "• /popular - Show most popular animes\n"
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
            "• /list - List all animes\n"
            "• /search - Advanced search\n"
            "• /stats - Bot statistics\n"
            "• /popular - Popular animes\n"
            "• /db_export - Export database\n"
            "• /bulk - Bulk import animes (JSON/CSV/TXT)\n"
            "• /broadcast - Broadcast message\n"
            "• /set_start_img - Change banner\n"
            "• /set_start_msg - Edit welcome\n"
            "• /cancel - Cancel operation"
        )
    
    await message.reply(text)

@bot.on_message(filters.command("search"))
async def search_cmd(client, message):
    """Search command - works for both users and admins"""
    if len(message.command) < 2:
        await message.reply(
            "🔍 <b>Usage:</b> <code>/search anime_name</code>\n\n"
            "Example: <code>/search solo leveling</code>"
        )
        return
    
    query = " ".join(message.command[1:])
    results = SearchEngine.search_anime(query, limit=10)
    
    if not results:
        await message.reply(f"❌ No results found for '<code>{query}</code>'")
        return
    
    text = f"🔍 <b>Search Results for '{query}':</b>\n\n"
    
    for i, anime in enumerate(results, 1):
        display = anime.get("name_display", anime["_key"])
        views = anime.get("views", 0)
        desc = anime.get("desc", "No description")[:60]
        aliases = anime.get("aliases", [])
        
        text += f"{i}. <b>{display}</b> 👁 {views}\n"
        text += f"   <i>{desc}...</i>\n"
        if aliases:
            text += f"   🏷 <code>{', '.join(aliases[:3])}</code>\n"
        text += "\n"
    
    # Add buttons for top 5 results
    buttons = []
    for anime in results[:5]:
        display = anime.get("name_display", anime["_key"])
        # Create a callback or just use the name for text search
        buttons.append([InlineKeyboardButton(f"🎬 {display}", callback_data=f"get_{anime['_key']}")])
    
    if not buttons:
        buttons = [[InlineKeyboardButton("🔍 Try Text Search", switch_inline_query=query)]]
    
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

@bot.on_message(filters.command("popular"))
async def popular_cmd(client, message):
    """Show most popular animes by views"""
    stats = db.get_stats()
    top_animes = stats.get("top_animes", [])
    
    if not top_animes:
        await message.reply("📭 No anime data available yet!")
        return
    
    text = "🔥 <b>POPULAR ANIMES</b> 🔥\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (key, data) in enumerate(top_animes[:10]):
        display = data.get("name_display", key)
        views = data.get("views", 0)
        desc = data.get("desc", "No description")[:50]
        
        text += f"{medals[i] if i < 10 else '•'} <b>{display}</b>\n"
        text += f"   👁 <b>{views}</b> views | {desc}...\n\n"
    
    text += f"\n📊 Total Views: <b>{stats.get('total_views', 0)}</b>"
    
    await message.reply(text, disable_web_page_preview=True)

@bot.on_message(filters.command("stats"))
async def stats_cmd(client, message):
    """Show bot statistics"""
    is_admin = state.is_admin(message.from_user.id)
    
    stats = db.get_stats()
    
    text = (
        "📊 <b>BOT STATISTICS</b> 📊\n\n"
        f"📺 <b>Total Animes:</b> <code>{stats['total_animes']}</code>\n"
        f"👥 <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
        f"🏷 <b>Total Aliases:</b> <code>{stats['total_aliases']}</code>\n"
        f"👁 <b>Total Views:</b> <code>{stats['total_views']}</code>\n\n"
    )
    
    if is_admin:
        sys_stats = stats.get("system_stats", {})
        text += (
            "⚙️ <b>System Stats:</b>\n"
            f"🔍 Total Searches: <code>{sys_stats.get('searches', 0)}</code>\n"
            f"⬇️ Total Downloads: <code>{sys_stats.get('downloads', 0)}</code>\n\n"
        )
        
        # Recent additions
        text += "🆕 <b>Recently Added:</b>\n"
        for key, data in stats.get("recent_animes", [])[:5]:
            display = data.get("name_display", key)
            added = data.get("added_at", "Unknown")[:10]
            text += f"• <b>{display}</b> ({added})\n"
    
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
# ADMIN COMMANDS - FIXED AND ENHANCED
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
            views = data.get("views", 0)
            text += f"<code>{idx}.</code> <b>{display}</b> 👁{views} 🏷{aliases}\n"
        
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.3)

# ═══════════════════════════════════════════════════════════════════════════════
# FIXED COMMANDS: /db_export, /bulk, /stats, /popular, /search
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command("db_export") & filters.private)
async def db_export_cmd(client, message):
    """Export database as JSON or CSV"""
    user_id = message.from_user.id
    if not state.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    # Check if format specified
    fmt = "json"  # default
    if len(message.command) > 1:
        fmt = message.command[1].lower()
    
    try:
        if fmt == "csv":
            # Export as CSV
            csv_data = db.export_to_csv()
            filename = f"kenshin_animes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Send as document
            file_obj = io.BytesIO(csv_data.encode('utf-8'))
            file_obj.name = filename
            
            await message.reply_document(
                document=file_obj,
                caption=f"📊 <b>Database Export (CSV)</b>\n\n"
                        f"📁 File: <code>{filename}</code>\n"
                        f"📺 Animes: <code>{len(db.get_all_animes())}</code>\n"
                        f"📅 Date: <code>{datetime.now().strftime('%Y-%m-%d %H:%M')}</code>"
            )
        else:
            # Export as JSON
            json_data = db.export_to_json()
            filename = f"kenshin_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Save backup file
            backup_path = os.path.join(BACKUP_DIR, filename)
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            
            # Send as document
            file_obj = io.BytesIO(json_data.encode('utf-8'))
            file_obj.name = filename
            
            await message.reply_document(
                document=file_obj,
                caption=f"💾 <b>Database Export (JSON)</b>\n\n"
                        f"📁 File: <code>{filename}</code>\n"
                        f"📺 Animes: <code>{len(db.get_all_animes())}</code>\n"
                        f"👥 Users: <code>{len(db.data.get('users', []))}</code>\n"
                        f"💾 Backup saved to: <code>{backup_path}</code>"
            )
        
        logger.info(f"Database exported by {user_id} in {fmt} format")
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        await message.reply(f"❌ <b>Export failed:</b> <code>{str(e)}</code>")

def parse_txt_bulk_upload(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse TXT file with format:
    Name | Image URL | Link | Description | Aliases
    
    Returns list of anime data dicts
    """
    imported_data = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('#') or line.startswith('//'):
            continue
        
        # Skip header line if it contains "Name" and "Image"
        if 'name' in line.lower() and 'image' in line.lower() and '|' in line:
            continue
        
        # Parse pipe-separated format
        if '|' not in line:
            logger.warning(f"Line {line_num}: No pipe separator found, skipping: {line[:50]}")
            continue
        
        parts = [p.strip() for p in line.split('|')]
        
        # Must have at least 4 parts (Name, Image, Link, Description)
        if len(parts) < 4:
            logger.warning(f"Line {line_num}: Insufficient data (need 4-5 parts), skipping")
            continue
        
        try:
            anime = {
                "name": parts[0],
                "name_display": parts[0],
                "image_url": parts[1] if parts[1] else DEFAULT_START_IMAGE,
                "download_link": parts[2],
                "desc": parts[3] if parts[3] else "No description",
                "aliases": []
            }
            
            # Parse aliases if present (5th column)
            if len(parts) >= 5 and parts[4]:
                # Split by comma for multiple aliases
                aliases = [a.strip() for a in parts[4].split(',') if a.strip()]
                anime["aliases"] = aliases
            
            imported_data.append(anime)
            logger.info(f"Line {line_num}: Parsed '{anime['name']}' with {len(anime['aliases'])} aliases")
            
        except Exception as e:
            logger.error(f"Line {line_num}: Parse error: {e}")
            continue
    
    return imported_data

@bot.on_message(filters.command("bulk") & filters.private)
async def bulk_cmd(client, message):
    """
    Bulk import animes from JSON, CSV, or TXT file
    Usage: Reply to a document with /bulk
    """
    user_id = message.from_user.id
    if not state.is_admin(user_id):
        await message.reply("❌ <b>Access Denied!</b>")
        return
    
    # Check if replying to a document
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply(
            "📦 <b>BULK UPLOAD</b>\n\n"
            "<b>Supported Formats:</b>\n\n"
            "1️⃣ <b>TXT Format</b> (Easiest):\n"
            "<pre>Name | Image URL | Link | Description | Aliases</pre>\n"
            "<b>Example:</b>\n"
            "<pre>Solo Leveling | https://img.com/solo.jpg | https://t.me/... | A weak hunter... | sl, solo lev\n"
            "Jujutsu Kaisen | https://img.com/jjk.jpg | https://t.me/... | Sorcerers... | jjk, jujutsu</pre>\n\n"
            "2️⃣ <b>JSON Format:</b>\n"
            "<pre>[{\n"
            '  \"name\": \"Solo Leveling\",\n'
            '  \"image_url\": \"https://...\",\n'
            '  \"download_link\": \"https://...\",\n'
            '  \"desc\": \"Description\",\n'
            '  \"aliases\": [\"sl\", \"solo lev\"]\n'
            "}]</pre>\n\n"
            "3️⃣ <b>CSV Format:</b>\n"
            "<pre>Name,Image URL,Download Link,Description,Aliases\n"
            "Solo Leveling,https://...,https://...,Desc,sl|solo lev</pre>\n\n"
            "✏️ <b>How to use:</b> Send the file and reply with <code>/bulk</code>"
        )
        return
    
    document = message.reply_to_message.document
    file_name = document.file_name.lower()
    
    # Download file
    status_msg = await message.reply("⬇️ <b>Downloading file...</b>")
    
    try:
        file_path = await message.reply_to_message.download()
        await status_msg.edit_text("📊 <b>Processing data...</b>")
        
        imported_data = []
        file_type = "unknown"
        
        # Process based on file type
        if file_name.endswith('.txt'):
            file_type = "TXT"
            imported_data = parse_txt_bulk_upload(file_path)
            
        elif file_name.endswith('.json'):
            file_type = "JSON"
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    imported_data = data
                elif isinstance(data, dict) and "animes" in data:
                    # Convert from database format
                    for key, anime in data["animes"].items():
                        anime["name"] = key
                        imported_data.append(anime)
                        
        elif file_name.endswith('.csv'):
            file_type = "CSV"
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert CSV row to anime data
                    anime = {
                        "name": row.get("Name") or row.get("name"),
                        "name_display": row.get("Display Name") or row.get("name_display"),
                        "image_url": row.get("Image URL") or row.get("image_url", DEFAULT_START_IMAGE),
                        "download_link": row.get("Download Link") or row.get("download_link"),
                        "desc": row.get("Description") or row.get("desc", "No description"),
                        "aliases": (row.get("Aliases") or row.get("aliases", "")).split("|") if "|" in str(row.get("Aliases") or row.get("aliases", "")) else [],
                        "views": int(row.get("Views") or row.get("views", 0))
                    }
                    imported_data.append(anime)
        else:
            await status_msg.edit_text("❌ <b>Unsupported file format!</b>\nUse .txt, .json, or .csv")
            os.remove(file_path)
            return
        
        if not imported_data:
            await status_msg.edit_text("❌ <b>No valid data found in file!</b>\n\nCheck format and try again.")
            os.remove(file_path)
            return
        
        await status_msg.edit_text(f"🔄 <b>Importing {len(imported_data)} animes from {file_type}...</b>")
        
        # Import data
        success, failed = db.bulk_import(imported_data)
        
        # Cleanup
        os.remove(file_path)
        
        # Send detailed result
        result_text = (
            f"✅ <b>BULK IMPORT COMPLETE</b>\n\n"
            f"📁 <b>File Type:</b> <code>{file_type}</code>\n"
            f"📊 <b>Total Processed:</b> <code>{len(imported_data)}</code>\n"
            f"✅ <b>Success:</b> <code>{success}</code>\n"
            f"❌ <b>Failed:</b> <code>{failed}</code>\n\n"
            f"📺 <b>Total Animes in DB:</b> <code>{len(db.get_all_animes())}</code>"
        )
        
        # If TXT format, show sample of what was imported
        if file_type == "TXT" and success > 0:
            sample = imported_data[:3]
            result_text += "\n\n📋 <b>Sample Imports:</b>\n"
            for anime in sample:
                aliases_str = f" ({', '.join(anime['aliases'])})" if anime['aliases'] else ""
                result_text += f"• <b>{anime['name']}</b>{aliases_str}\n"
        
        await status_msg.edit_text(result_text)
        
        logger.info(f"Bulk import by {user_id}: {success} success, {failed} failed from {file_type}")
        
    except Exception as e:
        logger.error(f"Bulk import error: {e}")
        await status_msg.edit_text(f"❌ <b>Import failed:</b> <code>{str(e)}</code>")
        # Cleanup on error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

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
    
    # Increment search stat
    db.increment_stat("searches")
    
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
        # Increment download stat (when button shown)
        db.increment_stat("downloads")
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
    print("║     🔥 KENSHIN ANIME BOT v5.1 - ULTIMATE 🔥                    ║")
    print("║     TXT Bulk Upload | JSON | CSV | All Fixed | Full Heavy      ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"💾 Database: {DB_FILE}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("Starting bot...")
    
    bot.run()
