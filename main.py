import os
from telethon import TelegramClient, events, Button
from telethon.tl.types import InputMessagesFilterPinned  # Ye zaroori hai

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", -100123456789))

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("Bhai, anime ka naam likho, main pinned messages mein dhoond ke deta hoon! 🔍")

@bot.on(events.NewMessage)
async def search_handler(event):
    # Sirf text messages par kaam karega aur commands ko ignore karega
    if event.is_private or event.is_group:
        query = event.text.lower()
        if query.startswith('/') or not query:
            return

        search_msg = await event.reply("Searching in pinned messages... 🔍")
        
        found = False
        try:
            # Hum sirf PINNED messages fetch kar rahe hain (ye bots ke liye allowed hai)
            async for message in bot.iter_messages(CHANNEL_ID, filter=InputMessagesFilterPinned):
                content = (message.text or "").lower()
                
                if query in content:
                    found = True
                    # Buttons logic
                    buttons = [
                        [Button.url("▪︎ DOWNLOAD NOW ▪︎", f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{message.id}")],
                        [Button.url("▪︎ WATCH NOW ▪︎", f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{message.id}")]
                    ]
                    
                    if message.photo:
                        await bot.send_file(event.chat_id, message.photo, caption=message.text, buttons=buttons)
                    else:
                        await event.reply(message.text, buttons=buttons)
                    break 

            if not found:
                await search_msg.edit("Bhai, ye anime pinned messages mein nahi mila. 😕")
            else:
                await search_msg.delete()

        except Exception as e:
            print(f"Error: {e}")
            await search_msg.edit("Kuch gadbad ho gayi, check logs! ⚠️")

print("Bot is running...")
bot.run_until_disconnected()
