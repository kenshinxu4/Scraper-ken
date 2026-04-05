import os
from telethon import TelegramClient, events, Button, functions

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

bot = TelegramClient('kenshin_final', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("Bhai, system update kar diya hai! Ab search karke dekho. 🔍")

@bot.on(events.NewMessage)
async def search_handler(event):
    if event.is_private or event.is_group:
        query = event.text.lower().strip()
        if query.startswith('/') or len(query) < 2: return

        status_msg = await event.reply("Pinned messages mein dhoond raha hoon... 🔍")
        
        try:
            # Step 1: Channel ko pehchaano
            channel = await bot.get_entity(CHANNEL_ID)
            
            # Step 2: Get ALL pinned messages (Restricted Search nahi, direct request hai)
            result = await bot(functions.messages.GetPinnedMessagesRequest(channel=channel))
            
            found = False
            # Step 3: Loop through pinned messages manually
            for message in result.messages:
                content = (message.message or "").lower()
                
                if query in content:
                    found = True
                    # Message Link Create karo
                    short_id = str(CHANNEL_ID).replace("-100", "")
                    msg_link = f"https://t.me/c/{short_id}/{message.id}"
                    
                    markup = [
                        [Button.url("▪︎ DOWNLOAD NOW ▪︎", msg_link)],
                        [Button.url("▪︎ WATCH NOW ▪︎", msg_link)]
                    ]
                    
                    if message.media: # Photo/Video ke liye
                        await bot.send_file(event.chat_id, message.media, caption=message.message, buttons=markup)
                    else:
                        await event.reply(message.message, buttons=markup)
                    break 

            if not found:
                await status_msg.edit("Bhai, pinned messages mein ye anime nahi mila. 😕")
            else:
                await status_msg.delete()

        except Exception as e:
            print(f"ERROR: {e}")
            await status_msg.edit(f"Oops! Dikkat: {e}")

print("Bot is up and running without Search restrictions!")
bot.run_until_disconnected()
