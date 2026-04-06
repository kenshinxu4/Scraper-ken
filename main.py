import os
import json
import asyncio
import re
from telethon import TelegramClient, events, Button

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

DB_FILE = "database.json"
DEFAULT_START_IMAGE = "https://files.catbox.moe/v4oy6s.jpg"

bot = TelegramClient('kenshin_final_pro', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- DATABASE LOGIC ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: 
            data = json.load(f)
            # Migration check for new structure
            if "settings" not in data:
                data["settings"] = {"start_img": DEFAULT_START_IMAGE}
            if "users" not in data:
                data["users"] = []
            if "animes" not in data:
                # Handles old format where animes were top-level
                animes = {k: v for k, v in data.items() if k not in ["users", "settings"]}
                data = {"users": data.get("users", []), "animes": animes, "settings": {"start_img": DEFAULT_START_IMAGE}}
            return data
    return {"users": [], "animes": {}, "settings": {"start_img": DEFAULT_START_IMAGE}}

def save_db(data):
    with open(DB_FILE, "w") as f: 
        json.dump(data, f, indent=4)

db = load_db()
admin_states = {}

def add_user_to_db(user_id):
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)

# --- USER COMMANDS ---

@bot.on(events.NewMessage(pattern=r'^/start$'))
async def start_cmd(event):
    add_user_to_db(event.chat_id)
    start_img = db["settings"].get("start_img", DEFAULT_START_IMAGE)
    
    welcome_text = (
        "🌸 **Welcome to the KENSHIN ANIME Official Bot!** 🌸\n\n"
        "Powered by ⚜️ **@KENSHIN_ANIME** ⚜️\n\n"
        "🍿 We provide high-quality Direct Download and Watch links for all your favorite anime series and movies!\n\n"
        "👉 **How to find Anime?**\n"
        "Just type the anime name in the chat. My smart system will detect it even if you mention it in a sentence!\n"
        "Example: `Can I get Solo Leveling?` or `Solo Leveling Hindi Dubbed`.\n\n"
        "Type `/help` for a list of commands. Enjoy! ✨"
    )
    
    buttons = [
        [Button.url("✨ Join Channel ✨", "https://t.me/KENSHIN_ANIME")],
        [Button.url("💬 Support Group 💬", "https://t.me/KENSHIN_ANIME_CHAT")]
    ]
    
    try:
        await bot.send_file(event.chat_id, start_img, caption=welcome_text, buttons=buttons)
    except:
        await event.reply(welcome_text, buttons=buttons)

@bot.on(events.NewMessage(pattern=r'^/help$'))
async def help_cmd(event):
    help_text = (
        "🛠 **User Command Menu** 🛠\n\n"
        "• `/start` - Start or restart the bot interface\n"
        "• `/report <message>` - Request an anime or report broken links\n"
        "• `/help` - View this help guide\n\n"
        "🔍 **Search Tips:**\n"
        "No need for commands to search. Just type the anime name naturally in the chat."
    )
    
    if event.sender_id == ADMIN_ID:
        help_text += (
            "\n\n👑 **Admin Control Panel:**\n"
            "• `/add_ani` - Add single entry\n"
            "• `/edit_ani` - Update existing entry\n"
            "• `/set_start_img <link>` - Change Start Image\n"
            "• `/bulk` - View Bulk Upload instructions\n"
            "• `/list` - View all database entries\n"
            "• `/broadcast <msg>` - Message all users\n"
            "• `/cancel` - Cancel ongoing admin task"
        )
    await event.reply(help_text)

@bot.on(events.NewMessage(pattern=r'^/report(?: |$)(.*)'))
async def report_cmd(event):
    msg = event.pattern_match.group(1).strip()
    if not msg:
        return await event.reply("⚠️ **Usage:**\n`/report [Describe your issue or request]`")
    
    user = await event.get_sender()
    name = f"@{user.username}" if user.username else f"ID: {user.id}"
    
    report_to_admin = f"📢 **NEW USER REPORT**\n\n👤 **From:** {name}\n📝 **Message:** {msg}"
    
    try:
        await bot.send_message(ADMIN_ID, report_to_admin)
        await event.reply("✅ Your report/request has been sent to **@KENSHIN_ANIME**. We will process it as soon as possible!")
    except:
        await event.reply("❌ Failed to send report to admin.")

# --- ADMIN FEATURE COMMANDS ---

@bot.on(events.NewMessage(pattern=r'^/set_start_img(?: |$)(.*)'))
async def set_start_img(event):
    if event.sender_id != ADMIN_ID: return
    link = event.pattern_match.group(1).strip()
    if not link.startswith("http"):
        return await event.reply("⚠️ Please provide a valid direct Image Link (e.g., ending in .jpg or .png)")
    
    db["settings"]["start_img"] = link
    save_db(db)
    await event.reply(f"✅ **Success!** Start message image updated.\nNew Link: {link}")

@bot.on(events.NewMessage(pattern=r'^/broadcast(?: |$)(.*)'))
async def broadcast_cmd(event):
    if event.sender_id != ADMIN_ID: return
    msg_text = event.pattern_match.group(1).strip()
    reply_msg = await event.get_reply_message()
    
    if not msg_text and not reply_msg:
        return await event.reply("⚠️ Usage: `/broadcast [text]` or reply to a message with `/broadcast`")
    
    status = await event.reply("📡 **Broadcasting... Please wait.**")
    success = 0
    failed = 0
    
    for user_id in db["users"]:
        try:
            if reply_msg:
                await bot.send_message(user_id, reply_msg)
            else:
                await bot.send_message(user_id, msg_text)
            success += 1
            await asyncio.sleep(0.3)
        except:
            failed += 1
            
    await status.edit(f"✅ **Broadcast Finished!**\n\n🎯 Sent: {success}\n🚫 Failed: {failed}")

@bot.on(events.NewMessage(pattern=r'^/list$'))
async def list_ani(event):
    if event.sender_id != ADMIN_ID: return
    if not db["animes"]:
        return await event.reply("⚠️ No animes in the database yet!")
    
    content = "📂 **Database List:**\n\n"
    for n in db["animes"].keys():
        content += f"• `{n.title()}`\n"
    
    # Split into multiple messages if too long
    if len(content) > 4000:
        for x in range(0, len(content), 4000):
            await event.reply(content[x:x+4000])
    else:
        await event.reply(content)

# --- ADMIN STEP HANDLERS (Add/Edit) ---

@bot.on(events.NewMessage(pattern=r'^/add_ani$|^/edit_ani$'))
async def admin_init(event):
    if event.sender_id != ADMIN_ID: return
    mode = "ADD" if "/add_ani" in event.text else "EDIT"
    admin_states[event.sender_id] = {"step": "GET_NAME", "mode": mode}
    await event.reply(f"🚀 **{mode} Mode**\nEnter the **Anime Name**:")

@bot.on(events.NewMessage)
async def admin_flow(event):
    user_id = event.sender_id
    if user_id not in admin_states or event.text.startswith('/'): return

    state = admin_states[user_id]
    step = state["step"]

    if step == "GET_NAME":
        name = event.text.strip().lower()
        if state["mode"] == "EDIT" and name not in db["animes"]:
            return await event.reply("❌ This anime is not in our database!")
        state["name"] = name
        state["step"] = "GET_IMAGE"
        await event.reply(f"📌 Name: `{name.title()}`\n👉 Now send the **Direct Image Link**:")

    elif step == "GET_IMAGE":
        state["img"] = event.text.strip()
        state["step"] = "GET_LINK"
        await event.reply("🖼 Image Link saved!\n👉 Now send the **Download/Watch Link**:")

    elif step == "GET_LINK":
        state["link"] = event.text.strip()
        state["step"] = "GET_DESC"
        await event.reply("🔗 Link saved!\n👉 Now enter the **Synopsis / Description**:")

    elif step == "GET_DESC":
        name = state["name"]
        db["animes"][name] = {
            "img": state["img"],
            "link": state["link"],
            "desc": event.text.strip()
        }
        save_db(db)
        del admin_states[user_id]
        await event.reply(f"🎊 **Success!** `{name.title()}` added/updated in the database!")

# --- BULK UPLOAD HANDLER ---
@bot.on(events.NewMessage)
async def handle_bulk_file(event):
    if event.sender_id == ADMIN_ID and event.document and event.document.mime_type == "text/plain":
        file = await event.download_media(bytes)
        content = file.decode('utf-8').split('\n')
        count = 0
        for line in content:
            if "|" in line:
                try:
                    parts = line.split('|')
                    name = parts[0].strip().lower()
                    db["animes"][name] = {
                        "img": parts[1].strip(),
                        "link": parts[2].strip(),
                        "desc": parts[3].strip()
                    }
                    count += 1
                except: continue
        save_db(db)
        await event.reply(f"✅ Bulk Upload finished! **{count}** entries processed.")

# --- SMART KEYWORD SEARCH LOGIC (Core Feature) ---

@bot.on(events.NewMessage)
async def smart_search(event):
    # Don't trigger search for commands or during admin setup
    if event.text.startswith('/') or event.sender_id in admin_states: 
        return
    
    add_user_to_db(event.chat_id)
    
    user_text = event.text.lower()
    found_any = False

    # Check for every anime name stored in our database
    # This allows matching "solo leveling" inside "Bro did you watch solo leveling dubbed?"
    for anime_name, data in db["animes"].items():
        # Check if the saved anime name exists as a substring in the user message
        if anime_name in user_text:
            found_any = True
            link = data['link']
            img = data['img']
            desc = data['desc']
            
            buttons = [[Button.url("▪︎ DOWNLOAD / WATCH NOW ▪︎", link)]]
            caption = f"🎬 **{anime_name.upper()}**\n\n📖 **Synopsis:**\n{desc}\n\n✨ Uploaded by **@KENSHIN_ANIME**"
            
            try:
                # Reply directly to the user's message
                await event.reply(caption, file=img, buttons=buttons)
            except:
                await event.reply(f"⚠️ *(Image error)*\n\n{caption}", buttons=buttons)
            
            # We break after first match to avoid spamming multiple replies for one message
            # If you want it to find ALL matches, remove 'break' and 'return'
            return

    # Optional: Small response for private chat if nothing found
    if not found_any and event.is_private and len(user_text) > 4:
        # We only reply if the message looks like a search query
        pass 

@bot.on(events.NewMessage(pattern=r'^/cancel$'))
async def cancel_task(event):
    if event.sender_id in admin_states:
        del admin_states[event.sender_id]
        await event.reply("✅ Current admin process cancelled.")

print("🚀 KENSHIN ANIME ULTIMATE BOT IS LIVE!")
bot.run_until_disconnected()
