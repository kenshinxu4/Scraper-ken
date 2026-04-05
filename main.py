import os
import asyncio
from telethon import TelegramClient, events, Button
from telethon.tl.types import InputMessagesFilterPinned
from telethon.errors import ChannelPrivateError, ChatAdminRequiredError

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

bot = TelegramClient('kenshin_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("Bhai, main tayyar hoon! Anime ka naam likho. 🔍")

@bot.on(events.NewMessage)
async def search_handler(event):
    if event.is_private or event.is_group:
        query = event.text.lower().strip()
        if query.startswith('/') or len(query) < 2: return

        status_msg = await event.reply("Ruko, channel mein dhoond raha hoon... 🔍")
        
        try:
            # Step 1: Force bot to find the channel entity
            channel_entity = await bot.get_entity(CHANNEL_ID)
            
            found = False
            # Step 2: Fetch only Pinned Messages
            async for message in bot.iter_messages(channel_entity, filter=InputMessagesFilterPinned):
                content = (message.text or "").lower()
                
                if query in content:
                    found = True
                    # Button Link Logic
                    clean_id = str(CHANNEL_ID).replace("-100", "")
                    msg_link = f"https://t.me/c/{clean_id}/{message.id}"
                    
                    markup = [
                        [Button.url("▪︎ DOWNLOAD NOW ▪︎", msg_link)],
                        [Button.url("▪︎ WATCH NOW ▪︎", msg_link)]
                    ]
                    
                    if message.photo:
                        await bot.send_file(event.chat_id, message.photo, caption=message.text, buttons=markup)
                    else:
                        await event.reply(message.text, buttons=markup)
                    break 

            if not found:
                await status_msg.edit("Bhai, pinned messages mein ye anime nahi mila. 😕")
            else:
                await status_msg.delete()

        except ChatAdminRequiredError:
            await status_msg.edit("Abhi bhi wahi dikkat! Bot ko channel mein ADMIN banao (Permissions check karo). ⚠️")
        except ValueError:
            await status_msg.edit("Bhai, CHANNEL_ID galat hai. Check karo ki wo -100 se start ho rahi hai ya nahi. ❌")
        except Exception as e:
            # Asli error yahan dikhega
            print(f"ERROR: {e}")
            await status_msg.edit(f"Asli Error ye hai: {e}")

print("Bot is running...")
bot.run_until_disconnected()
