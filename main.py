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

# File Names & Links
DB_FILE = "kenshin_data.json"
DEFAULT_START_IMAGE = "https://files.catbox.moe/v4oy6s.jpg"
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

# --- DATABASE ENGINE ---
def load_db():
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
            "start_msg": DEFAULT_START_MSG
        }
    }

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"DB Save Error: {e}")

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
    parse_mode=enums.ParseMode.HTML  # ✅ FIXED: Use enum instead of string
)

# --- HELPER FUNCTIONS ---
async def is_admin(_, __, message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ <b>Access Denied!</b> Only Owner can use this.")
        return False
    return True

admin_filter = filters.create(is_admin)

# --- USER COMMANDS ---

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    add_user_to_db(user_id)
    
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
        logger.error(f"Start image error: {e}")
        await message.reply(
            text=start_msg,
            reply_markup=buttons,
            disable_web_page_preview=True
        )

@bot.on_message(filters.command("help") & filters.private)
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
            "• <code>/bulk</code> - Instruction for mass upload\n"
            "• <code>/list</code> - Database overview\n"
            "• <code>/stats</code> - Total users & animes\n"
            "• <code>/broadcast</code> - Global announcement\n"
            "• <code>/cancel</code> - Abort ongoing setup"
        )
    await message.reply(help_text)

@bot.on_message(filters.command("report") & filters.private)
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
            f"<b>Username:</b> @{user.username or 'None'}\n\n"
            f"<blockquote>{report_text}</blockquote>\n\n"
            f"Reply to this message to respond to the user."
        )
        await message.reply("✅ <b>Report sent successfully!</b> We'll look into it soon.")
    except Exception as e:
        logger.error(f"Report forwarding failed: {e}")
        await message.reply("❌ Failed to send report. Please contact admin directly.")

# --- ADMIN COMMANDS ---

@bot.on_message(filters.command("stats") & admin_filter & filters.private)
async def stats_cmd(client: Client, message: Message):
    total_users = len(db.get("users", []))
    total_animes = len(db.get("animes", {}))
    await message.reply(
        f"📊 <b>BOT STATISTICS</b>\n\n"
        f"👥 Total Users: <code>{total_users}</code>\n"
        f"🎬 Total Animes: <code>{total_animes}</code>"
    )

@bot.on_message(filters.command("set_start_img") & admin_filter & filters.private)
async def set_start_img_cmd(client: Client, message: Message):
    admin_states[message.from_user.id] = {"step": "SET_START_IMG"}
    await message.reply(
        "🖼 <b>Update Start Image</b>\n\n"
        "Please send the new image URL (Catbox/Telegraph link):\n"
        "Or send <code>cancel</code> to abort."
    )

@bot.on_message(filters.command("set_start_msg") & admin_filter & filters.private)
async def set_start_msg_cmd(client: Client, message: Message):
    current_msg = db.get("settings", {}).get("start_msg", DEFAULT_START_MSG)
    admin_states[message.from_user.id] = {"step": "SET_START_MSG"}
    
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
        "• <code>&lt;code&gt;</code> - <code>Code</code>\n"
        "• <code>&lt;pre&gt;</code> - Preformatted text\n\n"
        "<b>Current Message:</b>\n"
        f"<blockquote>{current_msg[:500]}...</blockquote>\n\n"
        "Send <code>cancel</code> to abort.\n"
        "Send new message to preview:"
    )

@bot.on_message(filters.command("view_start_msg") & admin_filter & filters.private)
async def view_start_msg_cmd(client: Client, message: Message):
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
        "⚠️ <b>Note:</b> Use <code>|</code> as separator (pipe symbol)\n"
        "<b>Example:</b>\n"
        "<code>Solo Leveling | https://catbox.moe/abc.jpg | https://t.me/joinchat/xxx | Best anime ever</code>"
    )

@bot.on_message(filters.command("list") & admin_filter & filters.private)
async def list_cmd(client: Client, message: Message):
    animes = db.get("animes", {})
    if not animes:
        await message.reply("📭 <b>Database is empty!</b>")
        return
    
    items = list(animes.items())
    total = len(items)
    chunk_size = 20
    
    for i in range(0, total, chunk_size):
        chunk = items[i:i + chunk_size]
        text = f"📚 <b>DATABASE LIST</b> (Page {i//chunk_size + 1}/{(total-1)//chunk_size + 1})\n\n"
        
        for name, data in chunk:
            desc = data.get('desc', 'No desc')[:50]
            text += f"• <b>{name.upper()}</b>\n  └ <i>{desc}...</i>\n\n"
        
        await message.reply(text, disable_web_page_preview=True)
        await asyncio.sleep(0.5)

@bot.on_message(filters.command(["add_ani", "edit_ani"]) & admin_filter & filters.private)
async def admin_init(client: Client, message: Message):
    mode = "ADD" if "add" in message.text.lower() else "EDIT"
    admin_states[message.from_user.id] = {"step": "NAME", "mode": mode}
    await message.reply(f"🚀 <b>ENTRY {mode} INITIATED</b>\n\nStep 1: Please enter the <b>Anime Name</b>:")

@bot.on_message(filters.command("broadcast") & admin_filter & filters.private)
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to broadcast it.")
        return
    
    confirm = await message.reply("📡 <b>Global Broadcast Started...</b>")
    count, deleted = 0, 0
    
    for user_id in db.get("users", []):
        try:
            await message.reply_to_message.copy(user_id)
            count += 1
            await asyncio.sleep(0.2)
        except errors.UserIsBlocked:
            deleted += 1
        except Exception as e:
            logger.error(f"Broadcast error for {user_id}: {e}")
    
    await confirm.edit(
        f"📢 <b>Broadcast Finished!</b>\n\n"
        f"✅ Delivered: <code>{count}</code>\n"
        f"🚫 Blocked/Failed: <code>{deleted}</code>"
    )

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_task(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in admin_states:
        del admin_states[user_id]
        await message.reply("✅ <b>Current task cancelled.</b>")
    else:
        await message.reply("ℹ️ No active task to cancel.")

# --- MESSAGE HANDLER ---

@bot.on_message(filters.private & filters.text)
async def message_handler(client: Client, message: Message):
    user_id = message.from_user.id
    raw_text = message.text.strip()
    lower_text = raw_text.lower()
    
    # Cancel check
    if lower_text == "cancel" and user_id in admin_states:
        del admin_states[user_id]
        await message.reply("✅ <b>Task cancelled.</b>")
        return
    
    # Admin state handling
    if user_id in admin_states and not raw_text.startswith('/'):
        state = admin_states[user_id]
        step = state.get("step")
        
        # SET START IMAGE
        if step == "SET_START_IMG":
            db["settings"]["start_img"] = raw_text
            save_db(db)
            del admin_states[user_id]
            await message.reply("✅ <b>Start image updated successfully!</b>")
            return
        
        # SET START MESSAGE (with preview)
        if step == "SET_START_MSG":
            # Show preview first
            preview_text = (
                f"👁 <b>PREVIEW:</b>\n\n"
                f"{raw_text}\n\n"
                f"Reply with <code>yes</code> to save, or send new text to edit again.\n"
                f"Send <code>cancel</code> to abort."
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
                await message.reply("✅ <b>Start message updated successfully!</b>")
            else:
                # New text, show preview again
                state["pending_msg"] = raw_text
                preview_text = (
                    f"👁 <b>UPDATED PREVIEW:</b>\n\n"
                    f"{raw_text}\n\n"
                    f"Reply with <code>yes</code> to save, or send new text to edit again."
                )
                await message.reply(preview_text, disable_web_page_preview=True)
            return
        
        # ADD/EDIT ANIME FLOW
        if state["mode"] in ["ADD", "EDIT"]:
            if step == "NAME":
                state["name"] = lower_text
                state["step"] = "IMG"
                await message.reply("🔗 <b>Step 2:</b> Send the <b>Image URL</b> (Catbox/Telegraph):")
            
            elif step == "IMG":
                state["img"] = raw_text
                state["step"] = "LINK"
                await message.reply("📥 <b>Step 3:</b> Send the <b>Download/Join Link</b> (Case Sensitive):")
            
            elif step == "LINK":
                state["link"] = raw_text
                state["step"] = "DESC"
                await message.reply("📝 <b>Step 4:</b> Send a short <b>Synopsis/Description</b>:")
            
            elif step == "DESC":
                db["animes"][state["name"]] = {
                    "img": state["img"],
                    "link": state["link"],
                    "desc": raw_text
                }
                save_db(db)
                del admin_states[user_id]
                await message.reply(f"🎯 <b>SUCCESS!</b>\n<code>{state['name'].upper()}</code> is now live in the database.")
        return
    
    # Bulk file upload (Admin only)
    if user_id == ADMIN_ID and message.document and message.document.file_name.endswith(".txt"):
        msg = await message.reply("⏳ <b>Processing Bulk File...</b>")
        try:
            file_path = await message.download()
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            count = 0
            for line in lines:
                if "|" in line:
                    try:
                        parts = line.split("|")
                        db["animes"][parts[0].strip().lower()] = {
                            "img": parts[1].strip(),
                            "link": parts[2].strip(),
                            "desc": parts[3].strip()
                        }
                        count += 1
                    except:
                        continue
            
            save_db(db)
            os.remove(file_path)
            await msg.edit(f"✅ <b>Bulk Update Complete!</b>\nAdded <code>{count}</code> new records to the database.")
        except Exception as e:
            logger.error(f"Bulk upload error: {e}")
            await msg.edit(f"❌ <b>Error:</b> {str(e)}")
        return
    
    # Smart Search
    if not raw_text.startswith('/') and user_id not in admin_states:
        anime_keys = sorted(db.get("animes", {}).keys(), key=len, reverse=True)
        
        for name in anime_keys:
            if name in lower_text:
                data = db["animes"][name]
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 DOWNLOAD / WATCH NOW 🚀", url=data['link'])]
                ])
                caption = (
                    f"🎬 <b>ANIME FOUND: {name.upper()}</b>\n\n"
                    f"📖 <b>SYNOPSIS:</b>\n<blockquote>{data['desc']}</blockquote>\n\n"
                    f"✨ <b>Channel:</b> @KENSHIN_ANIME"
                )
                
                try:
                    await message.reply_photo(
                        photo=data['img'],
                        caption=caption,
                        reply_markup=buttons
                    )
                except Exception as e:
                    await message.reply(
                        f"⚠️ <b>Image Error, sending text only.</b>\n\n{caption}",
                        reply_markup=buttons,
                        disable_web_page_preview=True
                    )
                add_user_to_db(user_id)
                return

# --- RUN BOT ---
if __name__ == "__main__":
    print("💎 Kenshin Pro Version with PyroFork is Online!")
    bot.run()
