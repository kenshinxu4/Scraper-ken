import os
from telethon import TelegramClient, events, Button

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 12345)) # Railway Environment Variables se lega
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", -100123456789)) # -100 se start hona chahiye

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("Bhai, anime ka naam likho, main pinned messages mein dhoond ke deta hoon! 🔍")

@bot.on(events.NewMessage)
async def search_handler(event):
    if event.is_private or event.is_group:
        query = event.text.lower()
        if query.startswith('/'): return # Commands ko ignore karega

        search_msg = await event.reply("Searching in channel pinned messages... 🔍")
        
        found = False
        # Channel se pinned messages fetch karna
        async for message in bot.iter_messages(CHANNEL_ID, ids=None):
            if message.pinned:
                content = (message.text or "").lower()
                
                if query in content:
                    found = True
                    # Inline Buttons Setup
                    buttons = [
                        [Button.url("▪︎ DOWNLOAD NOW ▪︎", "https://t.me/c/your_channel_link")], # Yahan link automate bhi ho sakta hai
                        [Button.url("▪︎ WATCH NOW ▪︎", "https://t.me/c/your_channel_link")]
                    ]
                    
                    # Agar message mein image hai toh image ke saath bhejega
                    if message.photo:
                        await bot.send_file(event.chat_id, message.photo, caption=message.text, buttons=buttons)
                    else:
                        await event.reply(message.text, buttons=buttons)
                    
                    break # Pehla match milte hi ruk jayega
        
        if not found:
            await search_msg.edit("Bhai, ye anime pinned messages mein nahi mila. 😕")
        else:
            await search_msg.delete()

print("Bot is running...")
bot.run_until_disconnected()
