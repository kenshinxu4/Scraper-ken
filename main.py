import os
from telethon import TelegramClient, events, Button

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) # Sirf tum command chala sako

bot = TelegramClient('anime_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# In-Memory Database aur States
anime_db = {}  # Yahan saare animes save honge
admin_states = {} # Admin kya add kar raha hai, uska track rakhega

# --- COMMANDS ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_cmd(event):
    await event.reply(
        "👋 Welcome to Anime Bot!\n\n"
        "Sirf anime ka naam likh ke bhejo (e.g., 'solo leveling'). "
        "Agar mere paas available hoga, toh main tumhe links de dunga! 🍿\n\n"
        "Type /help for more info."
    )

@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.reply(
        "🛠 **Help Menu**\n\n"
        "👉 Anime chahiye? Bas naam type karke send karo.\n"
        "👉 Admin commands: `/add_ani` (To add new anime links)\n\n"
        "Note: Agar anime nahi mil raha toh spelling theek se check karo."
    )

@bot.on(events.NewMessage(pattern='/cancel'))
async def cancel_cmd(event):
    if event.sender_id in admin_states:
        del admin_states[event.sender_id]
        await event.reply("❌ Anime add karna cancel kar diya gaya hai.")

@bot.on(events.NewMessage(pattern='/add_ani'))
async def add_ani_cmd(event):
    if event.sender_id != ADMIN_ID:
        return await event.reply("❌ Ye command sirf ADMIN use kar sakta hai!")
    
    # Step 1: Start process
    admin_states[event.sender_id] = {"step": "WAIT_NAME"}
    await event.reply("✅ **Naya Anime Add Kar rahe hain!**\n\n👉 Sabse pehle Anime ka **NAAM** batao: \n*(Cancel karne ke liye /cancel type karein)*")

# --- MAIN LOGIC (Adding & Searching) ---

@bot.on(events.NewMessage)
async def main_handler(event):
    user_id = event.sender_id
    text = event.text.strip().lower()
    
    if text.startswith('/'): return # Ignore other commands

    # -----------------------------------------
    # PART 1: ADMIN FLOW (Anime Add Karne Ka System)
    # -----------------------------------------
    if user_id in admin_states:
        state = admin_states[user_id]
        step = state["step"]
        
        if step == "WAIT_NAME":
            state["name"] = text
            state["step"] = "WAIT_MESSAGE"
            await event.reply(f"📌 Naam set ho gaya: **{text.title()}**\n\n👉 Ab bot ko wo **IMAGE + CAPTION** bhejo jo user ko dikhana hai.")
            return
            
        elif step == "WAIT_MESSAGE":
            if not event.media:
                return await event.reply("❌ Bhai, tumne image nahi bheji! Ek Image bhejo aur uske caption mein text likho.")
            
            # Save original message object
            state["msg_obj"] = event.message 
            state["step"] = "WAIT_DL_LINK"
            await event.reply("🖼 Image aur Text save ho gaya!\n\n👉 Ab **DOWNLOAD NOW** button ka link bhejo (http...):")
            return
            
        elif step == "WAIT_DL_LINK":
            if not text.startswith("http"):
                return await event.reply("❌ Link 'http' se start hona chahiye. Sahi link bhejo.")
            
            state["dl_link"] = text
            state["step"] = "WAIT_WATCH_LINK"
            await event.reply("🔗 Download Link Set!\n\n👉 Ab **WATCH NOW** button ka link bhejo:")
            return
            
        elif step == "WAIT_WATCH_LINK":
            if not text.startswith("http"):
                return await event.reply("❌ Link 'http' se start hona chahiye. Sahi link bhejo.")
            
            # Final Step: Save to our dictionary Database
            anime_name = state["name"]
            anime_db[anime_name] = {
                "msg_obj": state["msg_obj"],
                "dl_link": state["dl_link"],
                "watch_link": text
            }
            del admin_states[user_id] # Clear state
            
            await event.reply(f"🎉 **SUCCESS!** '{anime_name.title()}' database mein save ho gaya hai. Ab koi bhi isko search kar sakta hai!")
            return

    # -----------------------------------------
    # PART 2: USER FLOW (Anime Search Karne Ka System)
    # -----------------------------------------
    if event.is_private or event.is_group:
        found = False
        
        # Check if user's text matches any saved anime name
        for saved_name, data in anime_db.items():
            if saved_name in text or text in saved_name:
                found = True
                msg = data["msg_obj"]
                
                # Buttons banayenge jo admin ne set kiye the
                buttons = [
                    [Button.url("▪︎ DOWNLOAD NOW ▪︎", data["dl_link"])],
                    [Button.url("▪︎ WATCH NOW ▪︎", data["watch_link"])]
                ]
                
                # Image aur text ke sath buttons send karega
                await bot.send_file(
                    event.chat_id, 
                    msg.media, 
                    caption=msg.text, 
                    buttons=buttons
                )
                break 
        
        # Agar bot ke paas result nahi hai (sirf private chat me reply karega, taaki group me spam na ho)
        if not found and event.is_private:
            await event.reply("❌ Ye anime abhi mere paas add nahi hai. Spelling check kar lo ya baad mein try karna!")

print("✅ Bot is Running with Internal Database...")
bot.run_until_disconnected()
