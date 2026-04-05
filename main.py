import os
import asyncio
from telethon import TelegramClient, events, Button
from telethon.tl.types import InputMessagesFilterPinned

# --- CONFIGURATION (Railway Variables mein daal dena) ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("Bhai, Anime ka naam likh ke search kar, main pinned messages dekh ke batata hoon! 🍿")

@bot.on(events.NewMessage)
async def search_handler(event):
    if event.is_private or event.is_group:
        query = event.text.lower().strip()
        
        # Commands aur khali text ko ignore karne ke liye
        if query.startswith('/') or len(query) < 2:
            return

        wait_msg = await event.reply("Ruko bhai, pinned messages scan kar raha hoon... 🔍")
        
        found = False
        try:
            # Sirf PINNED messages fetch karega (Max limit 100 pinned messages)
            async for message in bot.iter_messages(CHANNEL_ID, filter=InputMessagesFilterPinned):
                text_content = (message.text or "").lower()
                
                if query in text_content:
                    found = True
                    # Telegram link format for specific message
                    # Channel ID se -100 hatana padta hai public link ke liye
                    clean_id = str(CHANNEL_ID).replace("-100", "")
                    msg_link = f"https://t.me/c/{clean_id}/{message.id}"
                    
                    buttons = [
                        [Button.url("▪︎ DOWNLOAD NOW ▪︎", msg_link)],
                        [Button.url("▪︎ WATCH NOW ▪︎", msg_link)]
                    ]
                    
                    # Agar image hai toh image ke saath, varna simple text
                    if message.photo:
                        await bot.send_file(event.chat_id, message.photo, caption=message.text, buttons=buttons)
                    else:
                        await event.reply(message.text, buttons=buttons)
                    break 

            if not found:
                await wait_msg.edit("Bhai, ye anime pinned messages mein nahi mila. Check karle spelling! 😕")
            else:
                await wait_msg.delete()

        except Exception as e:
            print(f"Error occurred: {e}")
            await wait_msg.edit(f"Error: Bot ko admin bano channel mein! ⚠️")

print("Bot is alive...")
bot.run_until_disconnected()
