import os
import json
import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters, errors, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# --- LOGGING SETUP ---
logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# ✅ FIX: Better env handling with defaults
API_ID = int(os.environ.get("API_ID") or 0)
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID") or 0)
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").replace("@", "")

# File Paths
DB_FILE = os.environ.get("DB_FILE", "kenshin_data.json")  # Default to local if not set
DEFAULT_START_IMAGE = "https://files.catbox.moe/v4oy6s.jpg"
SUPPORT_GROUP = "https://t.me/KENSHIN_ANIME_CHAT"
CHANNEL_LINK = "https://t.me/KENSHIN_ANIME"
OWNER_USERNAME = "@KENSHIN_ANIME_OWNER"

# --- DATABASE ENGINE ---
def load_db():
    """Load database"""
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"DB Load Error: {e}")
    
    return {
        "users": [],
        "animes": {},
        "settings": {
            "start_img": DEFAULT_START_IMAGE,
            "start_msg": None  # Will use built-in
        }
    }

def save_db(data):
    """Save database"""
    try:
        db_dir = os.path.dirname(DB_FILE)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        temp_file = DB_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        os.replace(temp_file, DB_FILE)
        return True
    except Exception as e:
        logger.error(f"DB Save Error: {e}")
        return False

db = load_db()
admin_states = {}

def add_user_to_db(user_id: int):
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)
        logger.info(f"New User: {user_id}")

# --- BOT INIT ---
print("🛡️ Booting Kenshin Anime Engine...")

bot = Client(
    "kenshin_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
)

# --- HELPERS ---
async def is_admin(_, __, message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ <b>Access Denied!</b>")
        return False
    return True

admin_filter = filters.create(is_admin)

def get_text(message: Message) -> str:
    text = message.text or message.caption or ""
    if BOT_USERNAME and message.chat.type != "private":
        text = text.replace(f"@{BOT_USERNAME}", "").replace(f"@{BOT_USERNAME.lower()}", "")
    return text.strip()

# --- COMMANDS ---

@bot.on_message(filters.command("start") & filters.private)
async def start_private(client: Client, message: Message):
    user_id = message.from_user.id
    add_user_to_db(user_id)
    
    # Reload for fresh data
    global db
    db = load_db()
    
    start_img = db.get("settings", {}).get("start_img", DEFAULT_START_IMAGE)
    
    # ✅ IMAGE-STYLE CAPTION (No <blockquote>, clean look)
    welcome_text = (
        "🌸 <b>Welcome to KENSHIN ANIME Search!</b> 🌸\n\n"
        "⚜️ <b>Official bot of @KENSHIN_ANIME</b> ⚜️\n\n"
        "🍿 <i>I provide high-quality Anime links instantly.</i>\n\n"
        "📌 <b>How to find Anime?</b>\n"
        "Just type the name. I can detect it even in sentences!\n"
        "💡 <code>Example: Bhai solo leveling hai kya?</code>\n\n"
        "👉 Use /help to see all features."
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Join Channel ✨", url=CHANNEL_LINK)],
        [InlineKeyboardButton("💬 Support Group 💬", url=SUPPORT_GROUP)],
        [InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{OWNER_USERNAME.replace('@','')}")]
    ])
    
    try:
        await message.reply_photo(
            photo=start_img,
            caption=welcome_text,
            reply_markup=buttons
        )
    except Exception as e:
        logger.error(f"Photo error: {e}")
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
    
    if message.from_user.id == ADMIN_ID:
        text += (
            "\n\n⚡ <b>ADMIN PANEL</b>\n"
            "• /add_ani - Add anime\n"
            "• /edit_ani - Edit anime\n"
            "• /set_start_img - Change banner\n"
            "• /set_start_msg - Change welcome text\n"
            "• /view_start_img - Preview banner\n"
            "• /bulk - Bulk upload info\n"
            "• /list - All animes\n"
            "• /stats - Statistics\n"
            "• /broadcast - Send to all\n"
            "• /cancel - Cancel task"
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
            f"Chat: {message.chat.title if message.chat.type != 'private' else 'DM'}\n\n"
            f"📝 {report_text}"
        )
        await message.reply("✅ Report sent!")
    except Exception as e:
        logger.error(f"Report error: {e}")
        await message.reply("❌ Failed to send.")

# --- ADMIN COMMANDS ---

@bot.on_message(filters.command("stats") & admin_filter & filters.private)
async def stats_cmd(client: Client, message: Message):
    global db
    db = load_db()
    
    await message.reply(
        f"📊 <b>STATISTICS</b>\n\n"
        f"👥 Users: <code>{len(db.get('users', []))}</code>\n"
        f"🎬 Animes: <code>{len(db.get('animes', {}))}</code>\n"
        f"💾 DB: <code>{DB_FILE}</code>"
    )

@bot.on_message(filters.command("set_start_img") & admin_filter & filters.private)
async def set_start_img(client: Client, message: Message):
    """Quick or interactive mode"""
    user_id = message.from_user.id
    
    # Quick mode: /set_start_img <url>
    if len(message.command) > 1:
        url = message.command[1]
        if not url.startswith(("http://", "https://")):
            await message.reply("❌ URL must start with http:// or https://")
            return
        
        db["settings"]["start_img"] = url
        save_db(db)
        
        # Preview
        try:
            await message.reply_photo(
                photo=url,
                caption=f"✅ <b>Banner updated!</b>\n\nURL: <code>{url}</code>"
            )
        except:
            await message.reply(f"✅ Updated!\n\nURL: <code>{url}</code>\n⚠️ Couldn't preview, check URL.")
        return
    
    # Interactive mode
    admin_states[user_id] = {"step": "SET_START_IMG"}
    await message.reply(
        "🖼 <b>Send new banner URL</b>\n\n"
        "Or use: <code>/set_start_img &lt;url&gt;</code>\n"
        "Send <code>cancel</code> to abort."
    )

@bot.on_message(filters.command("view_start_img") & admin_filter & filters.private)
async def view_start_img(client: Client, message: Message):
    global db
    db = load_db()
    
    img = db.get("settings", {}).get("start_img", DEFAULT_START_IMAGE)
    
    try:
        await message.reply_photo(
            photo=img,
            caption=f"👁 <b>Current Banner</b>\n\nURL: <code>{img}</code>"
        )
    except:
        await message.reply(f"⚠️ <b>Current Banner URL:</b>\n<code>{img}</code>")

@bot.on_message(filters.command("set_start_msg") & admin_filter & filters.private)
async def set_start_msg(client: Client, message: Message):
    user_id = message.from_user.id
    
    if len(message.command) > 1:
        new_msg = " ".join(message.command[1:])
        db["settings"]["start_msg"] = new_msg
        save_db(db)
        await message.reply("✅ Welcome text updated!")
        return
    
    admin_states[user_id] = {"step": "SET_START_MSG"}
    await message.reply(
        "📝 <b>Send new welcome text</b> (HTML allowed)\n\n"
        "Or use: <code>/set_start_msg &lt;text&gt;</code>"
    )

@bot.on_message(filters.command("view_start_msg") & admin_filter & filters.private)
async def view_start_msg(client: Client, message: Message):
    msg = db.get("settings", {}).get("start_msg", "Using default")
    await message.reply(f"👁 <b>Current Welcome Text:</b>\n\n{msg}")

@bot.on_message(filters.command("bulk") & admin_filter & filters.private)
async def bulk_cmd(client: Client, message: Message):
    await message.reply(
        "📦 <b>BULK UPLOAD</b>\n\n"
        "Format per line:\n"
        "<code>Name | Image URL | Link | Description</code>\n\n"
        "Send <code>.txt</code> file to bot."
    )

@bot.on_message(filters.command("list") & admin_filter & filters.private)
async def list_cmd(client: Client, message: Message):
    global db
    db = load_db()
    
    animes = db.get("animes", {})
    if not animes:
        await message.reply("📭 Database empty!")
        return
    
    items = list(animes.items())
    for i in range(0, len(items), 20):
        chunk = items[i:i+20]
        text = f"📚 <b>LIST</b> ({i+1}-{min(i+20, len(items))}/{len(items)})\n\n"
        for name, data in chunk:
            text += f"• <b>{name.upper()}</b>\n  └ {data.get('desc', 'N/A')[:40]}...\n\n"
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.5)

@bot.on_message(filters.command(["add_ani", "edit_ani"]) & admin_filter & filters.private)
async def add_edit(client: Client, message: Message):
    mode = "ADD" if "add" in message.text.lower() else "EDIT"
    admin_states[message.from_user.id] = {"step": "NAME", "mode": mode}
    await message.reply(f"🚀 <b>{mode}</b> Mode\n\nStep 1: Send anime name")

@bot.on_message(filters.command("broadcast") & admin_filter & filters.private)
async def broadcast(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to broadcast")
        return
    
    confirm = await message.reply("📡 Broadcasting...")
    sent, failed = 0, 0
    
    for uid in db.get("users", []):
        try:
            await message.reply_to_message.copy(uid)
            sent += 1
            await asyncio.sleep(0.2)
        except:
            failed += 1
    
    await confirm.edit(f"📢 Done!\n✅ {sent}\n❌ {failed}")

@bot.on_message(filters.command("cancel") & (filters.private | filters.group))
async def cancel(client: Client, message: Message):
    uid = message.from_user.id
    if uid in admin_states:
        del admin_states[uid]
        await message.reply("✅ Cancelled.")
    else:
        await message.reply("ℹ️ Nothing to cancel.")

# --- DOCUMENT HANDLER (BULK) ---
@bot.on_message(filters.document & filters.private)
async def doc_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not message.document.file_name.endswith(".txt"):
        return
    
    msg = await message.reply("⏳ Processing...")
    
    try:
        path = await message.download()
        count = 0
        
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "|" not in line:
                    continue
                
                parts = line.split("|")
                if len(parts) < 4:
                    continue
                
                name, img, link, desc = [p.strip() for p in parts[:4]]
                if all([name, img, link]):
                    db["animes"][name.lower()] = {"img": img, "link": link, "desc": desc}
                    count += 1
        
        save_db(db)
        if os.path.exists(path):
            os.remove(path)
        
        await msg.edit(f"✅ Added <code>{count}</code> animes!")
        
    except Exception as e:
        logger.error(f"Bulk error: {e}")
        await msg.edit(f"❌ Error: {e}")

# --- MESSAGE HANDLER (SEARCH) ---
COMMANDS = ["start", "help", "report", "stats", "set_start_img", "set_start_msg",
            "view_start_img", "view_start_msg", "bulk", "list", "add_ani", "edit_ani",
            "broadcast", "cancel"]

@bot.on_message(filters.text & (filters.private | filters.group) & ~filters.command(COMMANDS))
async def search(client: Client, message: Message):
    global db
    db = load_db()
    
    uid = message.from_user.id
    text = get_text(message).lower()
    
    if not text or text.startswith("/"):
        return
    
    # Cancel check
    if text == "cancel" and uid in admin_states:
        del admin_states[uid]
        await message.reply("✅ Cancelled.")
        return
    
    # Admin states
    if uid in admin_states and message.chat.type == "private":
        state = admin_states[uid]
        step = state.get("step")
        
        if step == "SET_START_IMG":
            if not text.startswith(("http://", "https://")):
                await message.reply("❌ Invalid URL")
                return
            
            db["settings"]["start_img"] = text
            save_db(db)
            del admin_states[uid]
            
            try:
                await message.reply_photo(
                    photo=text,
                    caption="✅ <b>Banner updated!</b>"
                )
            except:
                await message.reply("✅ Updated! (Preview failed)")
            return
        
        if step == "SET_START_MSG":
            db["settings"]["start_msg"] = text
            save_db(db)
            del admin_states[uid]
            await message.reply("✅ Welcome text updated!")
            return
        
        # Add/Edit flow
        if state.get("mode") in ["ADD", "EDIT"]:
            if step == "NAME":
                state["name"] = text
                state["step"] = "IMG"
                await message.reply("🔗 Step 2: Image URL")
            
            elif step == "IMG":
                state["img"] = text
                state["step"] = "LINK"
                await message.reply("📥 Step 3: Download Link")
            
            elif step == "LINK":
                state["link"] = text
                state["step"] = "DESC"
                await message.reply("📝 Step 4: Description")
            
            elif step == "DESC":
                db["animes"][state["name"]] = {
                    "img": state["img"],
                    "link": state["link"],
                    "desc": text
                }
                save_db(db)
                del admin_states[uid]
                await message.reply(f"🎯 <b>{state['name'].upper()}</b> added!")
        return
    
    # Search
    for name in sorted(db.get("animes", {}).keys(), key=len, reverse=True):
        if name in text:
            data = db["animes"][name]
            
            # ✅ IMAGE-STYLE CAPTION (Clean, no blockquote)
            caption = (
                f"<blockquote>✨ <b>{name.upper()}</b> ✨</blockquote>\n\n"
                f"<b><blockquote>📖 {data['desc']}</blockquote></b>\n\n"
                f"➖➖➖➖➖➖➖➖➖➖\n"
                f"🔰 <b>FOR MORE JOIN:</b>\n"
                f"<blockquote>👉 @KENSHIN_ANIME\n"
                f"👉 @MANWHA_VERSE</blockquote>"
            )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 DOWNLOAD / WATCH NOW", url=data['link'])]
            ])
            
            try:
                await message.reply_photo(
                    photo=data['img'],
                    caption=caption,
                    reply_markup=buttons
                )
            except:
                await message.reply(
                    f"⚠️ <b>{name.upper()}</b>\n\n{caption}",
                    reply_markup=buttons
                )
            
            add_user_to_db(uid)
            return

# --- RUN ---
if __name__ == "__main__":
    print("💎 Kenshin Bot Online!")
    print(f"💾 DB: {DB_FILE}")
    bot.run()
