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
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").replace("@", "")

# File Names & Links
# ✅ PERSISTENT STORAGE PATH (Container mein /data folder mount karo)
DB_FILE = os.environ.get("DB_FILE", "/data/kenshin_data.json")
DEFAULT_START_IMAGE = "https://files.catbox.moe/b2d47q.jpg"
SUPPORT_GROUP = "https://t.me/KENSHIN_ANIME_CHAT"
CHANNEL_LINK = "https://t.me/KENSHIN_ANIME"
OWNER_USERNAME = "@KENSHIN_ANIME_OWNER"

# Default start message
DEFAULT_START_MSG = (
    "🌸 <b>Welcome to KENSHIN ANIME Search!</b> 🌸\n\n"
    "<blockquote>Official bot of ⚜️ @KENSHIN_ANIME ⚜️</blockquote>\n\n"
    "🍿 I provide high-quality Anime links instantly.\n\n"
    "👉 <b>How to find Anime?</b>\n"
    "Just type the name. I can detect it even in sentences!\n"
    "Example: <code>Bhai solo leveling hai kya?</code>\n\n"
    "Use /help to see all features."
)

# --- DATABASE ENGINE (PERSISTENT) ---
def load_db():
    """Load database from persistent storage"""
    # ✅ Ensure directory exists
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Created directory: {db_dir}")
    
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Database loaded: {len(data.get('animes', {}))} animes, {len(data.get('users', []))} users")
                return data
        except Exception as e:
            logger.error(f"DB Load Error: {e}")
    
    logger.info("Creating new database")
    return {
        "users": [],
        "animes": {},
        "settings": {
            "start_img": DEFAULT_START_IMAGE,
            "start_msg": DEFAULT_START_MSG
        }
    }

def save_db(data):
    """Save database to persistent storage"""
    try:
        # ✅ Ensure directory exists before saving
        db_dir = os.path.dirname(DB_FILE)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        # ✅ Atomic write (pehle temp file, phir rename)
        temp_file = DB_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        # ✅ Atomic rename (corruption protection)
        os.replace(temp_file, DB_FILE)
        logger.info(f"Database saved: {len(data.get('animes', {}))} animes")
        return True
    except Exception as e:
        logger.error(f"DB Save Error: {e}")
        return False

# ✅ GLOBAL DB INSTANCE
db = load_db()
admin_states = {}

def add_user_to_db(user_id: int):
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)
        logger.info(f"New User Added: {user_id}")

# --- INITIALIZE BOT ---
print("🛡️ Booting up Kenshin Anime Engine with PyroFork...")

bot = Client(
    "kenshin_pro_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
)

# --- HELPER FUNCTIONS ---
async def is_admin(_, __, message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ <b>Access Denied!</b> Only Owner can use this.")
        return False
    return True

admin_filter = filters.create(is_admin)

def get_text(message: Message) -> str:
    """Get text from message or caption"""
    text = message.text or message.caption or ""
    if BOT_USERNAME and message.chat.type != "private":
        text = text.replace(f"@{BOT_USERNAME}", "").replace(f"@{BOT_USERNAME.lower()}", "")
    return text.strip()

# --- COMMANDS ---

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd_private(client: Client, message: Message):
    """ORIGINAL UI - Private chat only"""
    user_id = message.from_user.id
    add_user_to_db(user_id)
    
    # ✅ Reload DB to get latest settings
    global db
    db = load_db()
    
    start_img = db.get("settings", {}).get("start_img", DEFAULT_START_IMAGE)
    start_msg = db.get("settings", {}).get("start_msg", DEFAULT_START_MSG)
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Join Channel ✨", url=CHANNEL_LINK)],
        [InlineKeyboardButton("💬 Support Group 💬", url=SUPPORT_GROUP)],
        [InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{OWNER_USERNAME.replace('@','')}")]
    ])
    
    try:
        await message.reply_photo(
            photo=start_img,
            caption=start_msg,
            reply_markup=buttons
        )
    except Exception as e:
        logger.error(f"Start photo error: {e}")
        await message.reply(
            text=start_msg,
            reply_markup=buttons,
            disable_web_page_preview=True
        )

@bot.on_message(filters.command("start") & filters.group)
async def start_cmd_group(client: Client, message: Message):
    """Simple version for groups"""
    await message.reply(
        f"👋 <b>Hey {message.from_user.first_name}!</b>\n\n"
        f"I'm Kenshin Anime Bot! 🍿\n"
        f"Type any anime name and I'll find it for you!\n\n"
        f"<i>Tip: Use me in DM for full experience → @{BOT_USERNAME or 'Bot'}</i>"
    )

@bot.on_message(filters.command("help") & (filters.private | filters.group))
async def help_cmd(client: Client, message: Message):
    help_text = (
        "🛠 <b>USER INTERFACE MENU</b>\n\n"
        "• <code>/start</code> - Wake up the bot\n"
        "• <code>/report &lt;msg&gt;</code> - Request anime or report broken links\n"
        "• <code>/help</code> - Show this detailed menu\n\n"
        "🔍 <b>PRO TIP:</b> You don't need commands to search. Just send the anime name directly in the chat!"
    )
    
    if message.from_user.id == ADMIN_ID:
        help_text += (
            "\n\n⚡ <b>ADMINISTRATOR PANEL</b>\n"
            "• <code>/add_ani</code> - Add a new entry\n"
            "• <code>/edit_ani</code> - Modify existing data\n"
            "• <code>/set_start_img</code> - Update bot banner\n"
            "• <code>/set_start_msg</code> - Edit start message with HTML\n"
            "• <code>/view_start_msg</code> - Preview current start message\n"
            "• <code>/view_start_img</code> - Preview current start image\n"
            "• <code>/bulk</code> - Instruction for mass upload\n"
            "• <code>/list</code> - Database overview\n"
            "• <code>/stats</code> - Total users & animes\n"
            "• <code>/broadcast</code> - Global announcement\n"
            "• <code>/cancel</code> - Abort ongoing setup"
        )
    await message.reply(help_text)

@bot.on_message(filters.command("report") & (filters.private | filters.group))
async def report_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply(
            "📝 <b>Report System</b>\n\n"
            "Please use the format:\n"
            "<code>/report Your message here</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/report Solo Leveling link is broken</code>"
        )
        return
    
    report_text = " ".join(message.command[1:])
    user = message.from_user
    
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📢 <b>NEW REPORT</b>\n\n"
            f"<b>From:</b> <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
            f"<b>User ID:</b> <code>{user.id}</code>\n"
            f"<b>Chat:</b> {'Private' if message.chat.type == 'private' else message.chat.title}\n"
            f"<b>Username:</b> @{user.username or 'None'}\n\n"
            f"<blockquote>{report_text}</blockquote>\n\n"
            f"Reply to this message to respond to the user."
        )
        await message.reply("✅ <b>Report sent successfully!</b> We'll look into it soon.")
    except Exception as e:
        logger.error(f"Report forwarding failed: {e}")
        await message.reply("❌ Failed to send report. Please contact admin directly.")

# --- ADMIN COMMANDS (PRIVATE ONLY) ---

@bot.on_message(filters.command("stats") & admin_filter & filters.private)
async def stats_cmd(client: Client, message: Message):
    # ✅ Reload to get latest data
    global db
    db = load_db()
    
    total_users = len(db.get("users", []))
    total_animes = len(db.get("animes", {}))
    await message.reply(
        f"📊 <b>BOT STATISTICS</b>\n\n"
        f"👥 Total Users: <code>{total_users}</code>\n"
        f"🎬 Total Animes: <code>{total_animes}</code>\n\n"
        f"💾 <b>Database:</b> <code>{DB_FILE}</code>"
    )

# ✅ FIXED: set_start_img with proper state handling
@bot.on_message(filters.command("set_start_img") & admin_filter & filters.private)
async def set_start_img_cmd(client: Client, message: Message):
    """Set start image - FIXED VERSION"""
    user_id = message.from_user.id
    
    # Check if user sent URL directly with command
    if len(message.command) > 1:
        # Direct URL provided: /set_start_img <url>
        img_url = message.command[1]
        
        # Validate URL
        if not img_url.startswith(("http://", "https://")):
            await message.reply("❌ Invalid URL. Must start with http:// or https://")
            return
        
        # Save to DB
        db["settings"]["start_img"] = img_url
        if save_db(db):
            await message.reply(
                f"✅ <b>Start image updated successfully!</b>\n\n"
                f"New Image URL: <code>{img_url}</code>\n\n"
                f"Use /view_start_img to preview or /start to see it in action!"
            )
        else:
            await message.reply("❌ Failed to save. Check logs.")
        return
    
    # No URL provided, enter interactive mode
    admin_states[user_id] = {"step": "SET_START_IMG"}
    await message.reply(
        "🖼 <b>Update Start Image</b>\n\n"
        "Send the new image URL (Catbox/Telegraph link):\n"
        "Or send <code>cancel</code> to abort.\n\n"
        "<i>Tip: You can also use:</i> <code>/set_start_img &lt;url&gt;</code>"
    )

# ✅ NEW: View current start image
@bot.on_message(filters.command("view_start_img") & admin_filter & filters.private)
async def view_start_img_cmd(client: Client, message: Message):
    """View current start image"""
    global db
    db = load_db()  # Reload to get latest
    
    current_img = db.get("settings", {}).get("start_img", DEFAULT_START_IMAGE)
    
    try:
        await message.reply_photo(
            photo=current_img,
            caption=f"👁 <b>CURRENT START IMAGE</b>\n\n"
                    f"URL: <code>{current_img}</code>\n\n"
                    f"Use <code>/set_start_img</code> to change."
        )
    except Exception as e:
        await message.reply(
            f"⚠️ <b>Cannot display image</b>\n\n"
            f"URL: <code>{current_img}</code>\n"
            f"Error: <code>{str(e)}</code>\n\n"
            f"Use <code>/set_start_img</code> to change."
        )

@bot.on_message(filters.command("set_start_msg") & admin_filter & filters.private)
async def set_start_msg_cmd(client: Client, message: Message):
    """Set start message"""
    user_id = message.from_user.id
    
    # Check if user sent message directly with command
    if len(message.command) > 1:
        # Direct message provided: /set_start_msg <message>
        new_msg = " ".join(message.command[1:])
        
        db["settings"]["start_msg"] = new_msg
        if save_db(db):
            await message.reply(
                f"✅ <b>Start message updated!</b>\n\n"
                f"Use /view_start_msg to preview."
            )
        else:
            await message.reply("❌ Failed to save.")
        return
    
    # Interactive mode
    current_msg = db.get("settings", {}).get("start_msg", DEFAULT_START_MSG)
    admin_states[user_id] = {"step": "SET_START_MSG"}
    
    await message.reply(
        "📝 <b>EDIT START MESSAGE</b>\n\n"
        "Send new start message with <b>HTML formatting</b>:\n\n"
        "<b>Supported Tags:</b>\n"
        "• <code>&lt;b&gt;</code> - <b>Bold</b>\n"
        "• <code>&lt;i&gt;</code> - <i>Italic</i>\n"
        "• <code>&lt;u&gt;</code> - <u>Underline</u>\n"
        "• <code>&lt;s&gt;</code> - <s>Strikethrough</s>\n"
        "• <code>&lt;blockquote&gt;</code> - <blockquote>Quote</blockquote>\n"
        "• <code>&lt;a href='url'&gt;</code> - <a href='https://t.me'>Links</a>\n"
        "• <code>&lt;code&gt;</code> - <code>Code</code>\n\n"
        "<b>Current Message:</b>\n"
        f"<blockquote>{current_msg[:300]}...</blockquote>\n\n"
        "Send <code>cancel</code> to abort.\n"
        "Or use: <code>/set_start_msg &lt;your message&gt;</code>"
    )

@bot.on_message(filters.command("view_start_msg") & admin_filter & filters.private)
async def view_start_msg_cmd(client: Client, message: Message):
    """View current start message"""
    global db
    db = load_db()
    
    current_msg = db.get("settings", {}).get("start_msg", DEFAULT_START_MSG)
    await message.reply(
        f"👁 <b>CURRENT START MESSAGE</b>:\n\n"
        f"{current_msg}\n\n"
        "Use <code>/set_start_msg</code> to edit."
    )

@bot.on_message(filters.command("bulk") & admin_filter & filters.private)
async def bulk_cmd(client: Client, message: Message):
    await message.reply(
        "📦 <b>BULK UPLOAD INSTRUCTIONS</b>\n\n"
        "1. Create a <code>.txt</code> file\n"
        "2. Format each line as:\n"
        "<code>Anime Name | Image URL | Download Link | Description</code>\n\n"
        "3. Send the file to this bot\n\n"
        "⚠️ <b>Note:</b> Use <code>|</code> as separator\n"
        "<b>Example:</b>\n"
        "<code>Solo Leveling | https://catbox.moe/abc.jpg | https://t.me/xxx | Best anime</code>"
    )

@bot.on_message(filters.command("list") & admin_filter & filters.private)
async def list_cmd(client: Client, message: Message):
    """List all anime"""
    global db
    db = load_db()  # Reload
    
    animes = db.get("animes", {})
    if not animes:
        await message.reply("📭 <b>Database is empty!</b>")
        return
    
    items = list(animes.items())
    total = len(items)
    chunk_size = 20
    
    for i in range(0, total, chunk_size):
        chunk = items[i:i + chunk_size]
        text = f"📚 <b>DATABASE LIST</b> ({i+1}-{min(i+chunk_size, total)}/{total})\n\n"
        
        for name, data in chunk:
            desc = data.get('desc', 'No desc')[:40]
            text += f"• <b>{name.upper()}</b>\n  └ <i>{desc}...</i>\n\n"
        
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.5)

@bot.on_message(filters.command(["add_ani", "edit_ani"]) & admin_filter & filters.private)
async def admin_init(client: Client, message: Message):
    mode = "ADD" if "add" in message.text.lower() else "EDIT"
    admin_states[message.from_user.id] = {"step": "NAME", "mode": mode}
    await message.reply(f"🚀 <b>ENTRY {mode} INITIATED</b>\n\nStep 1: Send <b>Anime Name</b>:")

@bot.on_message(filters.command("broadcast") & admin_filter & filters.private)
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to broadcast it.")
        return
    
    confirm = await message.reply("📡 <b>Broadcast Started...</b>")
    count, deleted = 0, 0
    
    for user_id in db.get("users", []):
        try:
            await message.reply_to_message.copy(user_id)
            count += 1
            await asyncio.sleep(0.2)
        except errors.UserIsBlocked:
            deleted += 1
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
    
    await confirm.edit(
        f"📢 <b>Broadcast Complete!</b>\n\n"
        f"✅ Delivered: <code>{count}</code>\n"
        f"🚫 Failed: <code>{deleted}</code>"
    )

@bot.on_message(filters.command("cancel") & (filters.private | filters.group))
async def cancel_task(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in admin_states:
        del admin_states[user_id]
        await message.reply("✅ <b>Task cancelled.</b>")
    else:
        await message.reply("ℹ️ No active task.")

# ✅ DOCUMENT HANDLER (BULK UPLOAD)
@bot.on_message(filters.document & filters.private)
async def document_handler(client: Client, message: Message):
    """Handle bulk upload"""
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    
    if not message.document.file_name.endswith(".txt"):
        return
    
    msg = await message.reply("⏳ <b>Processing Bulk File...</b>")
    
    try:
        file_path = await message.download()
        
        count = 0
        errors_list = []
        
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            if "|" not in line:
                errors_list.append(f"Line {line_num}: No | found")
                continue
            
            try:
                parts = line.split("|")
                if len(parts) < 4:
                    errors_list.append(f"Line {line_num}: Incomplete")
                    continue
                
                name, img, link, desc = [p.strip() for p in parts[:4]]
                
                if not all([name, img, link]):
                    errors_list.append(f"Line {line_num}: Missing fields")
                    continue
                
                db["animes"][name.lower()] = {"img": img, "link": link, "desc": desc}
                count += 1
                
            except Exception as e:
                errors_list.append(f"Line {line_num}: {str(e)}")
        
        save_db(db)
        
        if os.path.exists(file_path):
            os.remove(file_path)
        
        result = f"✅ <b>Bulk Complete!</b>\n\nAdded: <code>{count}</code>"
        if errors_list:
            result += f"\n⚠️ Errors: <code>{len(errors_list)}</code>"
        
        await msg.edit(result)
        
    except Exception as e:
        logger.error(f"Bulk error: {e}")
        await msg.edit(f"❌ <b>Error:</b> <code>{str(e)}</code>")

# ✅ MESSAGE HANDLER (TEXT & ADMIN STATES)
COMMANDS_LIST = ["start", "help", "report", "stats", "set_start_img", "set_start_msg", 
                 "view_start_msg", "view_start_img", "bulk", "list", "add_ani", "edit_ani", 
                 "broadcast", "cancel"]

@bot.on_message(filters.text & (filters.private | filters.group) & ~filters.command(COMMANDS_LIST))
async def message_handler(client: Client, message: Message):
    """Handle text messages and admin states"""
    global db
    
    user_id = message.from_user.id
    raw_text = get_text(message)
    lower_text = raw_text.lower()
    
    if not raw_text:
        return
    
    # Cancel check
    if lower_text == "cancel" and user_id in admin_states:
        del admin_states[user_id]
        await message.reply("✅ <b>Cancelled.</b>")
        return
    
    # ✅ ADMIN STATES (Private only)
    if user_id in admin_states and message.chat.type == "private":
        state = admin_states[user_id]
        step = state.get("step")
        
        # SET START IMAGE (Interactive mode)
        if step == "SET_START_IMG":
            if not raw_text.startswith(("http://", "https://")):
                await message.reply("❌ Invalid URL. Must start with http:// or https://")
                return
            
            db["settings"]["start_img"] = raw_text
            save_db(db)
            del admin_states[user_id]
            
            await message.reply(
                f"✅ <b>Start image updated!</b>\n\n"
                f"URL: <code>{raw_text}</code>\n"
                f"Use /view_start_img to verify."
            )
            return
        
        # SET START MESSAGE
        if step == "SET_START_MSG":
            preview_text = (
                f"👁 <b>PREVIEW:</b>\n\n{raw_text}\n\n"
                f"Reply <code>yes</code> to save, or send new text."
            )
            state["pending_msg"] = raw_text
            state["step"] = "CONFIRM_START_MSG"
            await message.reply(preview_text, disable_web_page_preview=True)
            return
        
        # CONFIRM START MESSAGE
        if step == "CONFIRM_START_MSG":
            if lower_text == "yes":
                db["settings"]["start_msg"] = state["pending_msg"]
                save_db(db)
                del admin_states[user_id]
                await message.reply("✅ <b>Start message saved!</b>")
            else:
                state["pending_msg"] = raw_text
                await message.reply(
                    f"👁 <b>UPDATED PREVIEW:</b>\n\n{raw_text}\n\n"
                    f"Reply <code>yes</code> to save."
                )
            return
        
        # ADD/EDIT ANIME
        if state.get("mode") in ["ADD", "EDIT"]:
            if step == "NAME":
                state["name"] = lower_text
                state["step"] = "IMG"
                await message.reply("🔗 <b>Step 2:</b> Send <b>Image URL</b>:")
            
            elif step == "IMG":
                state["img"] = raw_text
                state["step"] = "LINK"
                await message.reply("📥 <b>Step 3:</b> Send <b>Download Link</b>:")
            
            elif step == "LINK":
                state["link"] = raw_text
                state["step"] = "DESC"
                await message.reply("📝 <b>Step 4:</b> Send <b>Description</b>:")
            
            elif step == "DESC":
                db["animes"][state["name"]] = {
                    "img": state["img"],
                    "link": state["link"],
                    "desc": raw_text
                }
                save_db(db)
                del admin_states[user_id]
                await message.reply(f"🎯 <b>SUCCESS!</b> <code>{state['name'].upper()}</code> added!")
        return
    
    # ✅ SMART SEARCH (Private & Group)
    db = load_db()  # Reload for latest data
    anime_keys = sorted(db.get("animes", {}).keys(), key=len, reverse=True)
    
    for name in anime_keys:
        if name in lower_text:
            data = db["animes"][name]
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 DOWNLOAD / WATCH NOW 🚀", url=data['link'])]
            ])
            caption = (
                f"🎬 <b>ANIME:✨ {name.upper()} ✨</b>\n\n"
                f"📖 <b>SYNOPSIS:</b>\n<b><blockquote>{data['desc']}</blockquote></b>\n\n"
                f"✨ <b>FOR MORE JOIN:</b><b><blockquote>[@KENSHIN_ANIME & @MANWHA_VERSE]</blockquote></b>"
            )
            
            try:
                await message.reply_photo(photo=data['img'], caption=caption, reply_markup=buttons)
            except:
                await message.reply(f"⚠️ <b>{name.upper()}</b>\n\n{caption}", reply_markup=buttons)
            
            add_user_to_db(user_id)
            return

# --- RUN BOT ---
if __name__ == "__main__":
    print("💎 Kenshin Pro with Persistent Data is Online!")
    print(f"💾 Database: {DB_FILE}")
    bot.run()
