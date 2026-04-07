#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          🔥 KENSHIN ANIME BOT — ULTRA EDITION v7.0 🔥                      ║
║    Multi-Media Pool | Instant Buttons | Heavy UI | All Bugs Fixed            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, json, asyncio, logging, re, csv, io, random
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import UserIsBlocked, MessageNotModified

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger("KenshinBot")

API_ID       = int(os.environ.get("API_ID", "0"))
API_HASH     = os.environ.get("API_HASH", "").strip()
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID     = int(os.environ.get("ADMIN_ID", "0"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").replace("@", "")

DB_FILE    = os.environ.get("DB_FILE", "/data/kenshin_data.json")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/data/backups")

DEFAULT_START_IMAGE = "https://files.catbox.moe/v4oy6s.jpg"
CHANNEL_LINK   = "https://t.me/KENSHIN_ANIME"
SUPPORT_GROUP  = "https://t.me/KENSHIN_ANIME_CHAT"
OWNER_USERNAME = "@KENSHIN_ANIME_OWNER"

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────────────

class Database:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: Dict[str, Any] = {}
        self._ensure_dirs()
        self._load()

    def _ensure_dirs(self):
        for d in [os.path.dirname(self.filepath), BACKUP_DIR]:
            if d:
                os.makedirs(d, exist_ok=True)

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                self._migrate()
                return
            except Exception as e:
                logger.error(f"DB Load Error: {e}")

        self.data = {
            "users": [],
            "animes": {},
            "aliases": {},
            "settings": {
                "start_media": [{"type": "photo", "url": DEFAULT_START_IMAGE}],
                "start_message": None
            },
            "stats": {
                "searches": 0,
                "downloads": 0,
                "added_at": datetime.now().isoformat()
            }
        }
        self.save()

    def _migrate(self):
        """Auto-migrate old single start_image → new start_media list"""
        settings = self.data.setdefault("settings", {})
        if "start_image" in settings and "start_media" not in settings:
            old = settings.pop("start_image")
            settings["start_media"] = [{"type": "photo", "url": old}]
            self.save()
            logger.info("Migrated: start_image → start_media pool")
        elif "start_media" not in settings:
            settings["start_media"] = [{"type": "photo", "url": DEFAULT_START_IMAGE}]
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

    # ── Media Pool ───────────────────────────────────────────────────────────

    def get_start_media(self) -> List[Dict[str, str]]:
        pool = self.data.get("settings", {}).get("start_media", [])
        return pool if pool else [{"type": "photo", "url": DEFAULT_START_IMAGE}]

    def add_start_media(self, url: str, media_type: str = "photo") -> Tuple[bool, str]:
        """Returns (success, reason)"""
        pool = self.data.setdefault("settings", {}).setdefault("start_media", [])
        if any(m.get("url") == url for m in pool):
            return False, "duplicate"
        pool.append({"type": media_type, "url": url})
        return self.save(), "ok"

    def remove_start_media(self, index: int) -> bool:
        pool = self.data.get("settings", {}).get("start_media", [])
        if 0 <= index < len(pool):
            pool.pop(index)
            return self.save()
        return False

    def get_random_media(self) -> Dict[str, str]:
        pool = self.get_start_media()
        return random.choice(pool)

    # ── Anime CRUD ───────────────────────────────────────────────────────────

    def add_anime(self, name: str, data: Dict[str, Any]) -> bool:
        try:
            key = name.lower().strip()
            self.data["animes"][key] = data
            for alias in data.get("aliases", []):
                self.data["aliases"][alias.lower().strip()] = key
            return self.save()
        except Exception as e:
            logger.error(f"Add failed: {e}")
            return False

    def get_anime(self, name: str) -> Optional[Dict[str, Any]]:
        key = name.lower().strip()
        if key in self.data.get("animes", {}):
            r = self.data["animes"][key].copy()
            r["_key"] = key
            return r
        if key in self.data.get("aliases", {}):
            orig = self.data["aliases"][key]
            if orig in self.data.get("animes", {}):
                r = self.data["animes"][orig].copy()
                r["_key"] = orig
                return r
        return None

    def get_all_animes(self) -> Dict[str, Any]:
        return self.data.get("animes", {})

    def update_anime_field(self, key: str, field: str, value: Any) -> bool:
        try:
            key = key.lower().strip()
            if key in self.data.get("animes", {}):
                self.data["animes"][key][field] = value
                if field == "aliases":
                    # Remove old aliases pointing to this key
                    for a, t in list(self.data.get("aliases", {}).items()):
                        if t == key:
                            del self.data["aliases"][a]
                    # Register new aliases
                    for alias in value:
                        self.data["aliases"][alias.lower().strip()] = key
                return self.save()
            return False
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False

    def delete_anime(self, name: str) -> bool:
        try:
            key = name.lower().strip()
            if key in self.data.get("animes", {}):
                for alias in self.data["animes"][key].get("aliases", []):
                    self.data["aliases"].pop(alias.lower().strip(), None)
                del self.data["animes"][key]
                return self.save()
            return False
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    def add_user(self, user_id: int) -> bool:
        if user_id and user_id not in self.data.get("users", []):
            self.data["users"].append(user_id)
            return self.save()
        return True

    def get_setting(self, key: str, default=None):
        return self.data.get("settings", {}).get(key, default)

    def set_setting(self, key: str, value: Any) -> bool:
        self.data.setdefault("settings", {})[key] = value
        return self.save()

    def increment_stat(self, name: str):
        self.data.setdefault("stats", {})[name] = self.data["stats"].get(name, 0) + 1
        self.save()

    def get_stats(self) -> Dict[str, Any]:
        animes = self.get_all_animes()
        return {
            "total_animes": len(animes),
            "total_users": len(self.data.get("users", [])),
            "total_aliases": len(self.data.get("aliases", {})),
            "total_views": sum(a.get("views", 0) for a in animes.values()),
            "media_pool": len(self.get_start_media()),
            "top_animes": sorted(animes.items(), key=lambda x: x[1].get("views", 0), reverse=True)[:10],
            "recent_animes": sorted(animes.items(), key=lambda x: x[1].get("added_at", ""), reverse=True)[:5],
            "system_stats": self.data.get("stats", {})
        }

    def export_to_json(self) -> str:
        return json.dumps(self.data, indent=2, ensure_ascii=False)

    def export_to_csv(self) -> str:
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Name", "Display Name", "Image URL", "Download Link", "Description", "Aliases", "Views", "Added At"])
        for key, d in self.data.get("animes", {}).items():
            w.writerow([
                key, d.get("name_display", ""), d.get("image_url", ""),
                d.get("download_link", ""), d.get("desc", ""),
                "|".join(d.get("aliases", [])), d.get("views", 0), d.get("added_at", "")
            ])
        return out.getvalue()

    def bulk_import(self, data_list: List[Dict]) -> Tuple[int, int]:
        ok = fail = 0
        for item in data_list:
            try:
                name = item.get("name") or item.get("name_display")
                if not name:
                    fail += 1
                    continue
                existing = self.get_anime(name)
                if existing:
                    self.update_anime_field(
                        existing["_key"], "download_link",
                        item.get("download_link", existing.get("download_link", ""))
                    )
                    ok += 1
                    continue
                if self.add_anime(name, {
                    "name_display": item.get("name_display", name),
                    "image_url": item.get("image_url", DEFAULT_START_IMAGE),
                    "download_link": item.get("download_link", ""),
                    "desc": item.get("desc", "No description"),
                    "aliases": item.get("aliases", []),
                    "added_by": ADMIN_ID,
                    "added_at": datetime.now().isoformat(),
                    "views": 0
                }):
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                logger.error(f"Bulk item error: {e}")
                fail += 1
        return ok, fail


db = Database(DB_FILE)

# ─────────────────────────────────────────────────────────────────────────────
# STATE MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class StateManager:
    def __init__(self):
        self._states: Dict[int, Dict] = {}

    def set(self, uid: int, st: str, data: Dict = None):
        self._states[uid] = {"state": st, "data": data or {}}

    def get(self, uid: int) -> Optional[Dict]:
        return self._states.get(uid)

    def clear(self, uid: int):
        self._states.pop(uid, None)

    def is_admin(self, uid: int) -> bool:
        return uid == ADMIN_ID


state = StateManager()

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class SearchEngine:
    @staticmethod
    def normalize(text: str) -> str:
        return re.sub(r'\s+', ' ', text.lower().strip()) if text else ""

    @staticmethod
    def find_in_text(user_text: str) -> Optional[Dict]:
        if not user_text:
            return None
        clean = SearchEngine.normalize(user_text)
        animes = db.get_all_animes()
        best, best_priority = None, 999

        # Sort by name length desc → longer names win (more specific match)
        for key, data in sorted(animes.items(), key=lambda x: len(x[1].get("name_display", x[0])), reverse=True):
            name = SearchEngine.normalize(data.get("name_display", key))
            if name and name in clean:
                p = 100 - len(name)
                if p < best_priority:
                    best_priority = p
                    best = {**data, "_key": key}
                    continue
            for alias in data.get("aliases", []):
                a = SearchEngine.normalize(alias)
                if a and a in clean:
                    p = 50 - len(a)
                    if p < best_priority:
                        best_priority = p
                        best = {**data, "_key": key}
                    break

        return best

    @staticmethod
    def search(query: str, limit: int = 10) -> List[Dict]:
        if not query:
            return []
        q = SearchEngine.normalize(query)
        results = []
        for key, data in db.get_all_animes().items():
            name = data.get("name_display", key).lower()
            aliases = [a.lower() for a in data.get("aliases", [])]
            score = 0
            if q == name:               score = 100
            elif name.startswith(q):    score = 80
            elif q in name:             score = 60
            elif q in aliases:          score = 50
            else:
                for a in aliases:
                    if q in a:
                        score = 40
                        break
            if score:
                results.append({**data, "_key": key, "_score": score})
        return sorted(results, key=lambda x: x["_score"], reverse=True)[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def trunc(text: str, n: int = 50) -> str:
    if not text:
        return ""
    return text[:n - 3] + "..." if len(text) > n else text

def clean_text(text: str, is_group: bool = False) -> str:
    if not text:
        return ""
    if is_group and BOT_USERNAME:
        text = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.IGNORECASE)
    return ' '.join(text.split()).strip()

async def send_random_media(msg: Message, caption: str, buttons=None):
    """Pick a random photo or video from pool and send it. Falls back to text on error."""
    item = db.get_random_media()
    url  = item.get("url", DEFAULT_START_IMAGE)
    mtype = item.get("type", "photo")

    try:
        if mtype == "video":
            await msg.reply_video(video=url, caption=caption, reply_markup=buttons)
        else:
            await msg.reply_photo(photo=url, caption=caption, reply_markup=buttons)
        return
    except Exception as e:
        logger.warning(f"Media send failed [{mtype} | {url}]: {e}")

    # Fallback: try default image
    try:
        await msg.reply_photo(photo=DEFAULT_START_IMAGE, caption=caption, reply_markup=buttons)
    except Exception:
        await msg.reply(caption, reply_markup=buttons, disable_web_page_preview=True)

# ─────────────────────────────────────────────────────────────────────────────
# BOT INIT
# ─────────────────────────────────────────────────────────────────────────────

bot = Client(
    "kenshin_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
)

# ─────────────────────────────────────────────────────────────────────────────
# USER COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("start") & filters.private)
async def cmd_start(client, message: Message):
    uid = message.from_user.id
    db.add_user(uid)

    custom_msg = db.get_setting("start_message")
    welcome = custom_msg or (
        "🌸 <b>KENSHIN ANIME SEARCH BOT</b> 🌸\n\n"
        "<blockquote>⚜️ Official bot of @KENSHIN_ANIME ⚜️</blockquote>\n\n"
        "🍿 <b>High-quality anime links — instantly!</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔍 <b>How to search?</b>\n"
        "Just type the anime name anywhere in your message!\n\n"
        "💬 <b>Examples:</b>\n"
        "• <code>solo leveling ka link do</code>\n"
        "• <code>bhai jjk hai kya?</code>\n"
        "• <code>I want to watch AOT</code>\n"
        "• <code>demon slayer chahiye</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📖 Tap <b>Help</b> below to see all features!"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌟 Join Channel", url=CHANNEL_LINK),
            InlineKeyboardButton("📚 Manhwa", url="https://t.me/Manwha_verse"),
        ],
        [
            InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP),
            InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAME.replace('@', '')}"),
        ],
        [InlineKeyboardButton("📋 Help & Commands ❓", callback_data="show_help")]
    ])

    await send_random_media(message, welcome, buttons)


@bot.on_message(filters.command("start") & filters.group)
async def cmd_start_group(client, message: Message):
    name = message.from_user.first_name
    await message.reply(
        f"👋 <b>Hey {name}!</b>\n\n"
        f"🔥 I'm <b>Kenshin Anime Bot</b>!\n"
        f"Just type any anime name and I'll find it instantly!\n\n"
        f"<i>💬 DM me for full features → @{BOT_USERNAME or 'Me'}</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Open in DM", url=f"https://t.me/{BOT_USERNAME}")
        ]])
    )


async def build_help_text(is_admin: bool) -> str:
    pool_count = len(db.get_start_media())
    anime_count = len(db.get_all_animes())

    text = (
        "╔════════════════════════════════════╗\n"
        "║    📖  KENSHIN ANIME BOT — HELP    ║\n"
        "╚════════════════════════════════════╝\n\n"
        "━━━━━ 🔍 HOW TO SEARCH ━━━━━\n"
        "Just type anime name naturally in any message!\n\n"
        "💬 <b>Works with:</b>\n"
        "• <code>solo leveling ka link</code>\n"
        "• <code>bhai jjk hai?</code>\n"
        "• <code>I want to watch naruto</code>\n"
        "• <code>aot season 4 chahiye</code>\n\n"
        "━━━━━ 📋 USER COMMANDS ━━━━━\n"
        "🔍 /search <code>&lt;name&gt;</code> — Direct search\n"
        "🔥 /popular — Most watched animes\n"
        "📊 /stats — Bot statistics\n"
        "📢 /report <code>&lt;msg&gt;</code> — Report issue\n\n"
        "━━━━━ 💡 TIPS ━━━━━\n"
        "✅ Short names work! <code>jjk</code>, <code>aot</code>, <code>hxh</code>\n"
        "✅ Works in groups silently\n"
        "✅ Bot detects anime in any sentence\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📺 Animes in DB: <b>{anime_count}</b>\n"
        f"📡 Channel: @KENSHIN_ANIME | @Manwha_verse"
    )

    if is_admin:
        text += (
            "\n\n╔════════════════════════════════════╗\n"
            "║         ⚡ ADMIN PANEL ⚡           ║\n"
            "╚════════════════════════════════════╝\n\n"
            "━━━━━ 📺 ANIME MANAGEMENT ━━━━━\n"
            "➕ /add_ani — Add anime (step-by-step or pipe)\n"
            "✏️ /edit_ani — Edit anime (button UI)\n"
            "🗑 /delete_ani &lt;name&gt; — Delete anime\n"
            "🏷 /add_alias &lt;name&gt; | &lt;a1, a2&gt; — Add aliases\n"
            "📚 /list — List all animes (paginated)\n\n"
            "━━━━━ 🎬 MEDIA POOL ━━━━━\n"
            f"🖼 Pool size: <b>{pool_count} items</b> (shown randomly on /start)\n"
            "🎬 /add_media &lt;url&gt; [photo|video] — Add to pool\n"
            "📋 /list_media — View all media in pool\n"
            "🗑 /del_media &lt;#&gt; — Remove media by number\n\n"
            "━━━━━ 📊 DATA & TOOLS ━━━━━\n"
            "📊 /stats — Full statistics\n"
            "📦 /bulk — Bulk import (reply file + /bulk)\n"
            "💾 /db_export [csv|json] — Export database\n"
            "📡 /broadcast — Broadcast to all users\n\n"
            "━━━━━ ⚙️ SETTINGS ━━━━━\n"
            "📝 /set_start_msg — Edit welcome message\n"
            "❌ /cancel — Cancel any active operation"
        )

    return text


@bot.on_message(filters.command("help"))
async def cmd_help(client, message: Message):
    is_admin = state.is_admin(message.from_user.id)
    text = await build_help_text(is_admin)
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌟 Channel", url=CHANNEL_LINK),
            InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP),
        ],
        [InlineKeyboardButton("🔍 Search Anime", switch_inline_query_current_chat="")]
    ])
    await send_random_media(message, text, buttons)


@bot.on_message(filters.command("search"))
async def cmd_search(client, message: Message):
    if len(message.command) < 2:
        await message.reply(
            "🔍 <b>Search Anime</b>\n\n"
            "<b>Usage:</b> <code>/search anime_name</code>\n\n"
            "<b>Examples:</b>\n"
            "• <code>/search solo leveling</code>\n"
            "• <code>/search jjk</code>\n"
            "• <code>/search attack on titan</code>"
        )
        return

    query = " ".join(message.command[1:])
    results = SearchEngine.search(query, limit=10)

    if not results:
        await message.reply(
            f"❌ <b>No results for '<code>{query}</code>'</b>\n\n"
            f"💡 Try different spelling or check /popular\n"
            f"📢 Use /report to request this anime!"
        )
        return

    text = f"🔍 <b>Results for '{query}'</b>  ({len(results)} found)\n\n"
    for i, a in enumerate(results, 1):
        disp = a.get("name_display", a["_key"])
        views = a.get("views", 0)
        desc = trunc(a.get("desc", "No description"), 65)
        aliases = ", ".join(a.get("aliases", [])[:3])
        text += f"<b>{i}. {disp}</b>  👁 {views}\n"
        text += f"   <i>{desc}</i>\n"
        if aliases:
            text += f"   🏷 <code>{aliases}</code>\n"
        text += "\n"

    buttons = [
        [InlineKeyboardButton(f"🎬 {trunc(a.get('name_display', a['_key']), 30)}", callback_data=f"anime_{a['_key']}")]
        for a in results[:6]
    ]
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)


@bot.on_message(filters.command("popular"))
async def cmd_popular(client, message: Message):
    stats = db.get_stats()
    top = stats.get("top_animes", [])
    if not top:
        await message.reply("📭 No data yet! Anime get popular when users search them.")
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = "🔥 <b>MOST POPULAR ANIMES</b> 🔥\n\n"
    for i, (key, data) in enumerate(top[:10]):
        disp = data.get("name_display", key)
        views = data.get("views", 0)
        m = medals[i] if i < len(medals) else "•"
        text += f"{m} <b>{disp}</b> — 👁 <b>{views}</b>\n"
    text += f"\n📊 Total Views: <b>{stats['total_views']}</b>"

    buttons = [
        [InlineKeyboardButton(f"🎬 {trunc(d.get('name_display', k), 30)}", callback_data=f"anime_{k}")]
        for k, d in top[:5]
    ]
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)


@bot.on_message(filters.command("stats"))
async def cmd_stats(client, message: Message):
    is_admin = state.is_admin(message.from_user.id)
    st = db.get_stats()

    text = (
        "📊 <b>BOT STATISTICS</b>\n\n"
        f"📺 Animes: <code>{st['total_animes']}</code>\n"
        f"👥 Users: <code>{st['total_users']}</code>\n"
        f"🏷 Aliases: <code>{st['total_aliases']}</code>\n"
        f"👁 Total Views: <code>{st['total_views']}</code>\n"
        f"🎬 Media Pool: <code>{st['media_pool']}</code> items\n"
    )

    if is_admin:
        sys = st.get("system_stats", {})
        text += (
            f"\n⚙️ <b>System Stats:</b>\n"
            f"🔍 Searches: <code>{sys.get('searches', 0)}</code>\n"
            f"⬇️ Downloads: <code>{sys.get('downloads', 0)}</code>\n\n"
            f"🆕 <b>Recently Added:</b>\n"
        )
        for key, data in st.get("recent_animes", []):
            disp = data.get("name_display", key)
            added = data.get("added_at", "")[:10]
            text += f"• <b>{disp}</b> ({added})\n"

    await message.reply(text)


@bot.on_message(filters.command("report"))
async def cmd_report(client, message: Message):
    if len(message.command) < 2:
        await message.reply("📢 <b>Usage:</b> <code>/report your message here</code>")
        return
    report = " ".join(message.command[1:])
    u = message.from_user
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📢 <b>USER REPORT</b>\n\n"
            f"From: {u.first_name} (@{u.username or 'N/A'})\n"
            f"ID: <code>{u.id}</code>\n\n"
            f"📝 {report}"
        )
        await message.reply("✅ <b>Report sent!</b> We'll look into it.")
    except Exception as e:
        logger.error(f"Report error: {e}")
        await message.reply("❌ Failed to send report. Try again later.")

# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — ADD ANIME
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("add_ani") & filters.private)
async def cmd_add_ani(client, message: Message):
    uid = message.from_user.id
    if not state.is_admin(uid):
        await message.reply("❌ Admin only!")
        return

    # Quick-add: /add_ani Name | img | link | desc | alias1,alias2
    if len(message.command) > 1:
        parts = [p.strip() for p in " ".join(message.command[1:]).split("|")]
        if len(parts) >= 4:
            name, img, link, desc = parts[:4]
            aliases = [a.strip() for a in parts[4].split(",")] if len(parts) > 4 else []
            ok = db.add_anime(name, {
                "name_display": name, "image_url": img,
                "download_link": link, "desc": desc, "aliases": aliases,
                "added_by": uid, "added_at": datetime.now().isoformat(), "views": 0
            })
            await message.reply(f"{'✅' if ok else '❌'} <b>{name}</b> {'added!' if ok else 'failed!'}")
            return

    state.set(uid, "ADD_NAME", {})
    await message.reply(
        "🚀 <b>ADD ANIME — Step 1/5</b>\n\n"
        "📝 <b>Send the anime name:</b>\n\n"
        "Examples:\n• <code>Solo Leveling</code>\n• <code>Jujutsu Kaisen</code>\n\n"
        "<i>Send <code>cancel</code> to abort</i>"
    )

# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — MEDIA POOL COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("add_media") & filters.private)
async def cmd_add_media(client, message: Message):
    if not state.is_admin(message.from_user.id):
        await message.reply("❌ Admin only!")
        return

    if len(message.command) < 2:
        await message.reply(
            "🎬 <b>ADD START MEDIA</b>\n\n"
            "<b>Usage:</b> <code>/add_media URL [photo|video]</code>\n\n"
            "<b>Examples:</b>\n"
            "• <code>/add_media https://imgurl.com/anime.jpg photo</code>\n"
            "• <code>/add_media https://files.catbox.moe/xyz.mp4 video</code>\n\n"
            "<b>Default type is photo if not specified.</b>\n\n"
            "These are shown <b>randomly</b> on every /start and /help.\n"
            "Use /list_media to see pool, /del_media to remove."
        )
        return

    args = message.command[1:]
    url   = args[0]
    mtype = args[1].lower() if len(args) > 1 else "photo"

    if mtype not in ("photo", "video"):
        await message.reply("❌ Type must be <code>photo</code> or <code>video</code>")
        return
    if not url.startswith(("http://", "https://")):
        await message.reply("❌ Invalid URL! Must start with http:// or https://")
        return

    status = await message.reply("🔍 <b>Testing media...</b>")
    try:
        if mtype == "video":
            await message.reply_video(video=url, caption="✅ Test — OK")
        else:
            await message.reply_photo(photo=url, caption="✅ Test — OK")

        ok, reason = db.add_start_media(url, mtype)
        pool_size = len(db.get_start_media())

        if ok:
            await status.edit_text(
                f"✅ <b>Media added to pool!</b>\n\n"
                f"{'🎥' if mtype == 'video' else '🖼'} Type: <code>{mtype}</code>\n"
                f"🔗 URL: <code>{trunc(url, 55)}</code>\n"
                f"📦 Pool size: <b>{pool_size}</b> items\n\n"
                f"<i>Bot will randomly pick from pool on /start & /help</i>"
            )
        elif reason == "duplicate":
            await status.edit_text("⚠️ <b>Already exists in pool!</b>")
        else:
            await status.edit_text("❌ <b>Failed to save!</b>")

    except Exception as e:
        await status.edit_text(f"❌ <b>Media test failed!</b>\n\n<code>{e}</code>")


@bot.on_message(filters.command("list_media") & filters.private)
async def cmd_list_media(client, message: Message):
    if not state.is_admin(message.from_user.id):
        await message.reply("❌ Admin only!")
        return

    pool = db.get_start_media()
    text = f"🎬 <b>START MEDIA POOL</b>  ({len(pool)} items)\n\n"
    for i, item in enumerate(pool, 1):
        mtype = item.get("type", "photo")
        url   = item.get("url", "")
        icon  = "🖼" if mtype == "photo" else "🎥"
        text += f"{icon} <b>#{i}</b> [{mtype.upper()}]\n<code>{trunc(url, 60)}</code>\n\n"

    text += "<i>Use /del_media &lt;number&gt; to remove</i>"
    await message.reply(text, disable_web_page_preview=True)


@bot.on_message(filters.command("del_media") & filters.private)
async def cmd_del_media(client, message: Message):
    if not state.is_admin(message.from_user.id):
        await message.reply("❌ Admin only!")
        return

    if len(message.command) < 2 or not message.command[1].isdigit():
        await message.reply("🗑 <b>Usage:</b> <code>/del_media &lt;number&gt;</code>\n\nGet numbers from /list_media")
        return

    idx  = int(message.command[1]) - 1
    pool = db.get_start_media()

    if idx < 0 or idx >= len(pool):
        await message.reply(f"❌ Invalid number! Pool has <b>{len(pool)}</b> items.")
        return

    removed = pool[idx]
    if len(pool) == 1:
        await message.reply("⚠️ <b>Cannot remove the last media!</b>\nAdd another first with /add_media")
        return

    if db.remove_start_media(idx):
        mtype = removed.get("type", "photo")
        url   = removed.get("url", "")
        await message.reply(
            f"✅ <b>Removed from pool!</b>\n\n"
            f"{'🎥' if mtype == 'video' else '🖼'} <code>{mtype}</code>\n"
            f"🔗 <code>{trunc(url, 55)}</code>\n\n"
            f"📦 Pool size: <b>{len(db.get_start_media())}</b> items"
        )
    else:
        await message.reply("❌ Failed to remove!")

# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — EDIT ANI (Full Button UI)
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("edit_ani") & filters.private)
async def cmd_edit_ani(client, message: Message):
    uid = message.from_user.id
    if not state.is_admin(uid):
        await message.reply("❌ Admin only!")
        return

    animes = db.get_all_animes()
    if not animes:
        await message.reply("📭 Database empty! Add animes first with /add_ani")
        return

    if len(message.command) > 1:
        query = " ".join(message.command[1:])
        anime = db.get_anime(query)
        if anime:
            await _show_edit_menu(message, anime)
            return
        results = SearchEngine.search(query, limit=5)
        if results:
            text = f"🔍 <b>Matches for '{query}':</b>\n\n<i>Tap to edit:</i>\n"
            buttons = []
            for i, a in enumerate(results, 1):
                disp = a.get("name_display", a["_key"])
                text += f"{i}. <b>{disp}</b>\n"
                buttons.append([InlineKeyboardButton(f"✏️ {trunc(disp, 30)}", callback_data=f"edit_select_{a['_key']}")])
            buttons.append([InlineKeyboardButton("📋 Full List", callback_data="edit_list_0")])
            await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))
            return

    await _show_edit_list(message, page=0)


async def _show_edit_list(target, page: int = 0):
    """Paginated anime list for editing. target = Message or CallbackQuery.message"""
    animes = db.get_all_animes()
    items  = sorted(animes.items(), key=lambda x: x[1].get("name_display", x[0]))
    per_page   = 8
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * per_page: (page + 1) * per_page]

    text = (
        f"✏️ <b>EDIT ANIME</b>\n"
        f"<i>Page {page+1}/{total_pages}  •  {len(items)} total</i>\n\n"
        "Tap any anime to edit:\n"
    )

    buttons = []
    for key, data in chunk:
        disp  = data.get("name_display", key)
        views = data.get("views", 0)
        buttons.append([InlineKeyboardButton(
            f"✏️ {trunc(disp, 28)}  👁{views}",
            callback_data=f"edit_select_{key}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"edit_list_{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"edit_list_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="edit_cancel")])

    markup = InlineKeyboardMarkup(buttons)
    if isinstance(target, Message):
        await target.reply(text, reply_markup=markup)
    else:
        try:
            await target.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass


async def _show_edit_menu(source, anime: Dict):
    """source = Message or CallbackQuery"""
    key  = anime.get("_key", "")
    disp = anime.get("name_display", key)

    text = (
        f"✏️ <b>EDITING: {disp}</b>\n\n"
        f"📋 <b>Current Data:</b>\n\n"
        f"📝 Name:    <code>{disp}</code>\n"
        f"🖼 Image:   <code>{trunc(anime.get('image_url','N/A'), 50)}</code>\n"
        f"🔗 Link:    <code>{trunc(anime.get('download_link','N/A'), 50)}</code>\n"
        f"📄 Desc:    <code>{trunc(anime.get('desc','N/A'), 65)}</code>\n"
        f"🏷 Aliases: <code>{', '.join(anime.get('aliases',[])[:5]) or 'None'}</code>\n"
        f"👁 Views:   <code>{anime.get('views', 0)}</code>\n\n"
        f"<i>Select a field to edit:</i>"
    )

    buttons = [
        [
            InlineKeyboardButton("📝 Name",   callback_data=f"edit_field_{key}_name"),
            InlineKeyboardButton("🖼 Image",  callback_data=f"edit_field_{key}_image"),
        ],
        [
            InlineKeyboardButton("🔗 Link",   callback_data=f"edit_field_{key}_link"),
            InlineKeyboardButton("📄 Desc",   callback_data=f"edit_field_{key}_desc"),
        ],
        [
            InlineKeyboardButton("🏷 Aliases", callback_data=f"edit_field_{key}_aliases"),
            InlineKeyboardButton("🗑 Delete",  callback_data=f"edit_delete_{key}"),
        ],
        [
            InlineKeyboardButton("🔙 Back",   callback_data="edit_list_0"),
            InlineKeyboardButton("❌ Close",  callback_data="edit_cancel"),
        ]
    ]
    markup = InlineKeyboardMarkup(buttons)

    if isinstance(source, CallbackQuery):
        try:
            await source.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        await source.reply(text, reply_markup=markup, disable_web_page_preview=True)

# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK HANDLERS — ALL answer() CALLED FIRST FOR INSTANT RESPONSE
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^noop$"))
async def cb_noop(client, cq: CallbackQuery):
    await cq.answer()   # Just dismiss the spinner, do nothing


@bot.on_callback_query(filters.regex(r"^show_help$"))
async def cb_show_help(client, cq: CallbackQuery):
    await cq.answer("Loading help...")
    is_admin = state.is_admin(cq.from_user.id)
    text = await build_help_text(is_admin)
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌟 Channel", url=CHANNEL_LINK),
            InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP),
        ],
        [InlineKeyboardButton("🔍 Search Anime", switch_inline_query_current_chat="")]
    ])
    await send_random_media(cq.message, text, buttons)


@bot.on_callback_query(filters.regex(r"^anime_(.+)$"))
async def cb_anime(client, cq: CallbackQuery):
    """Show anime result when tapping search/popular button"""
    await cq.answer("Loading...")
    key   = cq.matches[0].group(1)
    anime = db.get_anime(key)
    if not anime:
        await cq.answer("❌ Anime not found!", show_alert=True)
        return
    await send_anime_result(cq.message, anime, user_id=cq.from_user.id)


@bot.on_callback_query(filters.regex(r"^edit_list_(\d+)$"))
async def cb_edit_list(client, cq: CallbackQuery):
    await cq.answer()
    if not state.is_admin(cq.from_user.id):
        await cq.answer("❌ Admin only!", show_alert=True)
        return
    page = int(cq.matches[0].group(1))
    await _show_edit_list(cq.message, page)


@bot.on_callback_query(filters.regex(r"^edit_select_(.+)$"))
async def cb_edit_select(client, cq: CallbackQuery):
    await cq.answer()
    if not state.is_admin(cq.from_user.id):
        await cq.answer("❌ Admin only!", show_alert=True)
        return
    key   = cq.matches[0].group(1)
    anime = db.get_anime(key)
    if not anime:
        await cq.answer("❌ Not found!", show_alert=True)
        return
    await _show_edit_menu(cq, anime)


@bot.on_callback_query(filters.regex(r"^edit_field_(.+)_(name|image|link|desc|aliases)$"))
async def cb_edit_field(client, cq: CallbackQuery):
    await cq.answer()
    if not state.is_admin(cq.from_user.id):
        await cq.answer("❌ Admin only!", show_alert=True)
        return

    key   = cq.matches[0].group(1)
    field = cq.matches[0].group(2)
    anime = db.get_anime(key)
    if not anime:
        await cq.answer("❌ Not found!", show_alert=True)
        return

    labels = {
        "name": "Name",
        "image": "Image URL",
        "link": "Download Link",
        "desc": "Description",
        "aliases": "Aliases (comma-separated)"
    }
    current = {
        "name":    anime.get("name_display", ""),
        "image":   anime.get("image_url", ""),
        "link":    anime.get("download_link", ""),
        "desc":    anime.get("desc", ""),
        "aliases": ", ".join(anime.get("aliases", []))
    }

    # Set state for text input from user
    state.set(cq.from_user.id, f"EDIT_{field.upper()}", {"anime_key": key, "field": field})

    try:
        await cq.message.edit_text(
            f"✏️ <b>Editing: {labels[field]}</b>\n"
            f"<i>Anime: {anime.get('name_display', key)}</i>\n\n"
            f"📋 <b>Current value:</b>\n"
            f"<code>{current[field][:350] or 'Empty'}</code>\n\n"
            f"✍️ <b>Send new value:</b>\n\n"
            f"<i>Send /cancel to abort</i>",
            disable_web_page_preview=True
        )
    except MessageNotModified:
        pass


@bot.on_callback_query(filters.regex(r"^edit_delete_(.+)$"))
async def cb_edit_delete(client, cq: CallbackQuery):
    await cq.answer("Confirm deletion below!", show_alert=False)
    if not state.is_admin(cq.from_user.id):
        await cq.answer("❌ Admin only!", show_alert=True)
        return

    key   = cq.matches[0].group(1)
    anime = db.get_anime(key)
    if not anime:
        await cq.answer("❌ Not found!", show_alert=True)
        return

    disp = anime.get("name_display", key)
    # Store in state for text confirmation
    state.set(cq.from_user.id, "DELETE_CONFIRM", {"anime_key": key, "display_name": disp})

    try:
        await cq.message.edit_text(
            f"⚠️ <b>CONFIRM DELETE</b> ⚠️\n\n"
            f"Delete: <b>{disp}</b>?\n\n"
            f"Send <code>yes</code> to confirm\n"
            f"Or /cancel to abort\n\n"
            f"<i>This cannot be undone!</i>"
        )
    except MessageNotModified:
        pass


@bot.on_callback_query(filters.regex(r"^edit_cancel$"))
async def cb_edit_cancel(client, cq: CallbackQuery):
    await cq.answer("Cancelled")
    state.clear(cq.from_user.id)
    try:
        await cq.message.edit_text("❌ <b>Edit cancelled.</b>\n\nUse /edit_ani to start again.")
    except MessageNotModified:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# REMAINING ADMIN COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("delete_ani") & filters.private)
async def cmd_delete_ani(client, message: Message):
    uid = message.from_user.id
    if not state.is_admin(uid):
        return
    if len(message.command) < 2:
        await message.reply("🗑 <b>Usage:</b> <code>/delete_ani anime_name</code>")
        return
    name  = " ".join(message.command[1:])
    anime = db.get_anime(name)
    if not anime:
        await message.reply(f"❌ '<code>{name}</code>' not found!")
        return
    disp = anime.get("name_display", name)
    key  = anime.get("_key", name.lower())
    state.set(uid, "DELETE_CONFIRM", {"anime_key": key, "display_name": disp})
    await message.reply(f"⚠️ Delete <b>'{disp}'</b>?\n\nSend <code>yes</code> to confirm or /cancel")


@bot.on_message(filters.command("add_alias") & filters.private)
async def cmd_add_alias(client, message: Message):
    uid = message.from_user.id
    if not state.is_admin(uid):
        return
    full = " ".join(message.command[1:]) if len(message.command) > 1 else ""
    if "|" not in full:
        await message.reply("🏷 <b>Usage:</b> <code>/add_alias anime_name | alias1, alias2</code>")
        return
    parts = full.split("|", 1)
    anime = db.get_anime(parts[0].strip())
    if not anime:
        await message.reply("❌ Anime not found!")
        return
    key        = anime.get("_key", parts[0].strip().lower())
    new_aliases = [a.strip() for a in parts[1].split(",") if a.strip()]
    existing   = set(anime.get("aliases", []))
    existing.update(new_aliases)
    ok = db.update_anime_field(key, "aliases", list(existing))
    await message.reply(
        f"{'✅' if ok else '❌'} Aliases {'updated' if ok else 'failed'}!\n"
        f"📺 <b>{anime.get('name_display', key)}</b>\n"
        f"🏷 <code>{', '.join(existing)}</code>"
    )


@bot.on_message(filters.command("set_start_msg") & filters.private)
async def cmd_set_start_msg(client, message: Message):
    uid = message.from_user.id
    if not state.is_admin(uid):
        return
    if len(message.command) > 1:
        db.set_setting("start_message", " ".join(message.command[1:]))
        await message.reply("✅ Welcome message updated!\n\nTest it with /start")
        return
    state.set(uid, "SET_START_MSG", {})
    await message.reply(
        "📝 <b>Send new welcome message:</b>\n\n"
        "<i>HTML formatting supported.\n"
        "Send /cancel to abort.</i>"
    )


@bot.on_message(filters.command("list") & filters.private)
async def cmd_list(client, message: Message):
    if not state.is_admin(message.from_user.id):
        return
    animes = db.get_all_animes()
    if not animes:
        await message.reply("📭 Database empty!")
        return
    items = sorted(animes.items(), key=lambda x: x[1].get("name_display", x[0]))
    for i in range(0, len(items), 15):
        chunk = items[i:i + 15]
        text  = f"📚 <b>ANIME LIST</b> ({i+1}–{min(i+15, len(items))}/{len(items)})\n\n"
        for idx, (key, d) in enumerate(chunk, i + 1):
            disp  = d.get("name_display", key)
            views = d.get("views", 0)
            alia  = len(d.get("aliases", []))
            text += f"<code>{idx:3}.</code> <b>{disp}</b>  👁{views}  🏷{alia}\n"
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.3)


@bot.on_message(filters.command("db_export") & filters.private)
async def cmd_db_export(client, message: Message):
    uid = message.from_user.id
    if not state.is_admin(uid):
        await message.reply("❌ Admin only!")
        return
    fmt = message.command[1].lower() if len(message.command) > 1 else "json"
    try:
        if fmt == "csv":
            data  = db.export_to_csv()
            fname = f"kenshin_animes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            f     = io.BytesIO(data.encode('utf-8'))
            f.name = fname
            await message.reply_document(f, caption=f"📊 CSV Export — {len(db.get_all_animes())} animes")
        else:
            data  = db.export_to_json()
            fname = f"kenshin_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            bp    = os.path.join(BACKUP_DIR, fname)
            with open(bp, 'w', encoding='utf-8') as bf:
                bf.write(data)
            f     = io.BytesIO(data.encode('utf-8'))
            f.name = fname
            await message.reply_document(
                f,
                caption=(
                    f"💾 <b>JSON Backup</b>\n"
                    f"📺 Animes: {len(db.get_all_animes())} | "
                    f"👥 Users: {len(db.data.get('users', []))}"
                )
            )
    except Exception as e:
        await message.reply(f"❌ Export failed: <code>{e}</code>")


def _parse_txt_bulk(path: str) -> List[Dict]:
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 4:
                continue
            try:
                data.append({
                    "name": parts[0], "name_display": parts[0],
                    "image_url": parts[1] or DEFAULT_START_IMAGE,
                    "download_link": parts[2],
                    "desc": parts[3] or "No description",
                    "aliases": [a.strip() for a in parts[4].split(',') if a.strip()] if len(parts) > 4 else []
                })
            except Exception as e:
                logger.error(f"TXT line {line_num}: {e}")
    return data


@bot.on_message(filters.command("bulk") & filters.private)
async def cmd_bulk(client, message: Message):
    uid = message.from_user.id
    if not state.is_admin(uid):
        return

    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply(
            "📦 <b>BULK IMPORT</b>\n\n"
            "<b>TXT (Easiest):</b>\n"
            "<code>Name | Image URL | Link | Desc | alias1,alias2</code>\n\n"
            "<b>JSON:</b>\n"
            "<code>[{\"name\":\"...\",\"image_url\":\"...\",\"download_link\":\"...\",\"desc\":\"...\",\"aliases\":[]}]</code>\n\n"
            "<b>CSV:</b>\n"
            "<code>Name,Image URL,Download Link,Description,Aliases</code>\n\n"
            "<b>How:</b> Send your file, then reply it with <code>/bulk</code>"
        )
        return

    doc    = message.reply_to_message.document
    fname  = doc.file_name.lower()
    status = await message.reply("⬇️ <b>Downloading file...</b>")

    try:
        fpath = await message.reply_to_message.download()
        await status.edit_text("📊 <b>Processing data...</b>")
        data = []

        if fname.endswith('.txt'):
            data = _parse_txt_bulk(fpath)
        elif fname.endswith('.json'):
            with open(fpath, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            if isinstance(raw, list):
                data = raw
            elif isinstance(raw, dict) and "animes" in raw:
                for k, v in raw["animes"].items():
                    v["name"] = k
                    data.append(v)
        elif fname.endswith('.csv'):
            with open(fpath, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    aliases_raw = row.get("Aliases") or row.get("aliases", "")
                    data.append({
                        "name": row.get("Name") or row.get("name"),
                        "name_display": row.get("Display Name") or row.get("name_display"),
                        "image_url": row.get("Image URL") or row.get("image_url", DEFAULT_START_IMAGE),
                        "download_link": row.get("Download Link") or row.get("download_link"),
                        "desc": row.get("Description") or row.get("desc", "No description"),
                        "aliases": aliases_raw.split("|") if "|" in aliases_raw else []
                    })
        else:
            await status.edit_text("❌ <b>Unsupported format!</b> Use .txt, .json, or .csv")
            os.remove(fpath)
            return

        os.remove(fpath)

        if not data:
            await status.edit_text("❌ <b>No valid data found!</b>")
            return

        await status.edit_text(f"🔄 <b>Importing {len(data)} animes...</b>")
        ok, fail = db.bulk_import(data)

        await status.edit_text(
            f"✅ <b>BULK IMPORT COMPLETE</b>\n\n"
            f"📊 Processed: <code>{len(data)}</code>\n"
            f"✅ Success:   <code>{ok}</code>\n"
            f"❌ Failed:    <code>{fail}</code>\n\n"
            f"📺 DB total: <code>{len(db.get_all_animes())}</code> animes"
        )

    except Exception as e:
        logger.error(f"Bulk error: {e}")
        await status.edit_text(f"❌ Import failed: <code>{e}</code>")
        if 'fpath' in locals() and os.path.exists(fpath):
            os.remove(fpath)


@bot.on_message(filters.command("broadcast") & filters.private)
async def cmd_broadcast(client, message: Message):
    if not state.is_admin(message.from_user.id):
        return
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message with <code>/broadcast</code>")
        return
    users  = db.data.get("users", [])
    status = await message.reply(f"📡 Broadcasting to <b>{len(users)}</b> users...")
    sent = blocked = 0
    for uid in users:
        try:
            await message.reply_to_message.copy(uid)
            sent += 1
            if sent % 50 == 0:
                await status.edit_text(f"📡 Progress: {sent}/{len(users)}...")
            await asyncio.sleep(0.2)
        except UserIsBlocked:
            blocked += 1
        except Exception as e:
            logger.error(f"Broadcast {uid}: {e}")
    await status.edit_text(f"📢 <b>Done!</b>  ✅ {sent} sent  |  🚫 {blocked} blocked")


@bot.on_message(filters.command("cancel") & filters.private)
async def cmd_cancel(client, message: Message):
    uid = message.from_user.id
    if state.get(uid):
        state.clear(uid)
        await message.reply("✅ <b>Cancelled!</b>")
    else:
        await message.reply("ℹ️ Nothing to cancel.")

# ─────────────────────────────────────────────────────────────────────────────
# ANIME RESULT SENDER
# ─────────────────────────────────────────────────────────────────────────────

async def send_anime_result(message: Message, anime: Dict, user_id: int = None):
    """
    Send anime info card. user_id override for callbacks where
    message.from_user is the bot itself.
    """
    key  = anime.get("_key", "")
    disp = anime.get("name_display", key)

    # Track view
    if key in db.data.get("animes", {}):
        db.data["animes"][key]["views"] = anime.get("views", 0) + 1
        db.save()

    uid = user_id or (message.from_user.id if message.from_user else None)
    if uid:
        db.add_user(uid)
    db.increment_stat("searches")
    db.increment_stat("downloads")

    caption = (
        f"<blockquote>✨ <b>{disp.upper()}</b> ✨</blockquote>\n\n"
        f"<blockquote>📖 {anime.get('desc', 'No description')}</blockquote>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔰 <b>FOR MORE ANIME JOIN:</b>\n"
        f"<blockquote>👉 @KENSHIN_ANIME\n👉 @Manwha_verse</blockquote>"
    )

    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 DOWNLOAD / WATCH NOW 🚀", url=anime.get("download_link", CHANNEL_LINK))
    ]])

    try:
        await message.reply_photo(photo=anime.get("image_url"), caption=caption, reply_markup=buttons)
    except Exception as e:
        logger.error(f"Result photo error: {e}")
        await message.reply(caption, reply_markup=buttons, disable_web_page_preview=True)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN MESSAGE HANDLER (Private)
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.text & filters.private)
async def handle_private(client, message: Message):
    uid  = message.from_user.id
    text = message.text
    if not text or text.startswith("/"):
        return
    tl = text.lower().strip()

    # Universal cancel
    if tl == "cancel":
        state.clear(uid)
        await message.reply("✅ <b>Cancelled!</b>")
        return

    st = state.get(uid)
    if st and state.is_admin(uid):
        cur  = st["state"]
        data = st["data"]

        # ── EDIT FIELD INPUT ─────────────────────────────────────────────────
        if cur.startswith("EDIT_"):
            field = cur.replace("EDIT_", "").lower()
            key   = data.get("anime_key")
            if not key:
                await message.reply("❌ Error! Use /edit_ani again.")
                state.clear(uid)
                return
            anime = db.get_anime(key)
            if not anime:
                await message.reply("❌ Anime not found!")
                state.clear(uid)
                return

            field_map = {
                "name":    "name_display",
                "image":   "image_url",
                "link":    "download_link",
                "desc":    "desc",
                "aliases": "aliases"
            }
            db_field = field_map.get(field)
            if not db_field:
                await message.reply("❌ Unknown field!")
                state.clear(uid)
                return

            value = [a.strip() for a in text.split(",") if a.strip()] if field == "aliases" else text
            ok    = db.update_anime_field(key, db_field, value)

            if ok:
                await message.reply(
                    f"✅ <b>{field.upper()}</b> updated!\n\n"
                    f"📺 <b>{anime.get('name_display', key)}</b>\n"
                    f"New value: <code>{str(value)[:120]}</code>\n\n"
                    f"<i>Use /edit_ani to continue editing</i>"
                )
            else:
                await message.reply("❌ <b>Update failed!</b>")
            state.clear(uid)
            return

        # ── DELETE CONFIRM ───────────────────────────────────────────────────
        if cur == "DELETE_CONFIRM":
            key  = data.get("anime_key")
            disp = data.get("display_name", key)
            if tl == "yes" and key and db.delete_anime(key):
                await message.reply(f"🗑 <b>'{disp}' deleted successfully!</b>")
            else:
                await message.reply("❌ Delete cancelled.")
            state.clear(uid)
            return

        # ── ADD ANIME FLOW ───────────────────────────────────────────────────
        if cur == "ADD_NAME":
            if len(text) < 2:
                await message.reply("❌ Name too short!")
                return
            if db.get_anime(text):
                await message.reply(f"⚠️ '<b>{text}</b>' already exists! Send a different name:")
                return
            state.set(uid, "ADD_IMAGE", {"name": text, "key": text.lower().strip()})
            await message.reply(f"✅ Name: <code>{text}</code>\n\n🖼 <b>Step 2/5: Image URL</b>")
            return

        if cur == "ADD_IMAGE":
            if not text.startswith(("http://", "https://")):
                await message.reply("❌ Invalid URL! Must start with http:// or https://")
                return
            data["image"] = text
            state.set(uid, "ADD_LINK", data)
            await message.reply("✅ Image saved!\n\n🔗 <b>Step 3/5: Download Link</b>")
            return

        if cur == "ADD_LINK":
            if not text.startswith(("http://", "https://", "t.me/")):
                await message.reply("❌ Invalid link!")
                return
            data["link"] = text
            state.set(uid, "ADD_DESC", data)
            await message.reply("✅ Link saved!\n\n📄 <b>Step 4/5: Description</b>")
            return

        if cur == "ADD_DESC":
            if len(text) < 10:
                await message.reply(f"❌ Too short! ({len(text)} chars, need 10+)")
                return
            data["desc"] = text
            state.set(uid, "ADD_ALIASES", data)
            await message.reply(
                "✅ Description saved!\n\n"
                "🏷 <b>Step 5/5: Aliases</b>\n\n"
                "Send aliases separated by commas, or <code>skip</code>:\n"
                "Example: <code>jjk, jujutsu, JJK Season 2</code>"
            )
            return

        if cur == "ADD_ALIASES":
            aliases = [] if tl == "skip" else [a.strip() for a in text.split(",") if a.strip()]
            ok = db.add_anime(data["key"], {
                "name_display": data["name"],
                "image_url":    data["image"],
                "download_link": data["link"],
                "desc":         data["desc"],
                "aliases":      aliases,
                "added_by":     uid,
                "added_at":     datetime.now().isoformat(),
                "views":        0
            })
            if ok:
                await message.reply(
                    f"╔══════════════════════════════════════╗\n"
                    f"║    🎯 SUCCESS! ANIME ADDED! 🎉        ║\n"
                    f"╚══════════════════════════════════════╝\n\n"
                    f"📺 <b>{data['name']}</b>\n"
                    f"🏷 Aliases: <code>{', '.join(aliases) or 'None'}</code>\n\n"
                    f"<i>Users can now search this anime!</i>\n"
                    f"Add another? → /add_ani"
                )
            else:
                await message.reply("❌ <b>Save failed!</b>")
            state.clear(uid)
            return

        # ── SETTINGS ─────────────────────────────────────────────────────────
        if cur == "SET_START_MSG":
            db.set_setting("start_message", text)
            await message.reply("✅ Welcome message updated!\n\nTest it with /start")
            state.clear(uid)
            return

    # ── ANIME SEARCH (default) ───────────────────────────────────────────────
    if len(text) < 2:
        return

    result = SearchEngine.find_in_text(text)
    if result:
        await send_anime_result(message, result)
    else:
        await message.reply(
            f"🔍 <b>No match found for:</b>\n<code>{text[:50]}</code>\n\n"
            f"💡 Try: /search <code>{text[:25]}</code>\n"
            f"📢 /report to request this anime!"
        )

# ─────────────────────────────────────────────────────────────────────────────
# GROUP HANDLER
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.text & filters.group)
async def handle_group(client, message: Message):
    text = clean_text(message.text, is_group=True)
    if not text or len(text) < 2 or text.startswith("/"):
        return
    result = SearchEngine.find_in_text(text)
    if result:
        await send_anime_result(message, result)
    # Silently ignore if no match in groups

# ─────────────────────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║      🔥 KENSHIN ANIME BOT v7.0 — ULTRA HEAVY EDITION 🔥        ║")
    print("║   Multi-Media Pool | Instant UI | Rich Help | All Bugs Fixed     ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"  💾 DB    : {DB_FILE}")
    print(f"  👤 Admin : {ADMIN_ID}")
    print(f"  🤖 Bot   : @{BOT_USERNAME or 'Not set'}")
    print("  Starting...")
    bot.run()
