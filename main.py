import asyncio
from telethon import TelegramClient, events, Button

# ====== CONFIG ======
api_id = 123456
api_hash = "YOUR_API_HASH"
bot_token = "YOUR_BOT_TOKEN"
channel_id = -1001234567890   # tera channel id

# ====================

bot = TelegramClient("bot", api_id, api_hash).start(bot_token=bot_token)


@bot.on(events.NewMessage)
async def handler(event):
    query = event.raw_text.lower()

    if event.is_private or event.is_group:
        found = False

        async for msg in bot.iter_messages(channel_id, limit=200):
            if msg.text and query in msg.text.lower():

                found = True

                # IMAGE + TEXT + BUTTON
                buttons = [
                    [Button.url("▪︎ DOWNLOAD NOW ▪︎", msg.link)],
                    [Button.url("▪︎ WATCH NOW ▪︎", msg.link)]
                ]

                if msg.photo:
                    await event.respond(
                        file=msg.photo,
                        message="🔥 FOUND RESULT 🔥",
                        buttons=buttons
                    )
                else:
                    await event.respond(
                        message="🔥 FOUND RESULT 🔥",
                        buttons=buttons
                    )

                break

        if not found:
            await event.respond("❌ Not Found Bro")


print("🚀 Bot Started...")
bot.run_until_disconnected()
