import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioStream, AudioParameters
import yt_dlp

# ============ CONFIG ============
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call = PyTgCalls(app)

# Storage
queues = {}
playing = {}
users = {}

# ============ BUTTONS ============
def main_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Play", callback_data="play"),
         InlineKeyboardButton("📋 Queue", callback_data="queue")],
        [InlineKeyboardButton("🔊 Join VC", callback_data="join"),
         InlineKeyboardButton("⏹️ Leave VC", callback_data="leave")],
        [InlineKeyboardButton("⏸️ Pause", callback_data="pause"),
         InlineKeyboardButton("▶️ Resume", callback_data="resume"),
         InlineKeyboardButton("⏭️ Skip", callback_data="skip")],
        [InlineKeyboardButton("🔑 Login", callback_data="login"),
         InlineKeyboardButton("🚪 Logout", callback_data="logout")]
    ])

# ============ HELPERS ============
async def get_audio(query):
    """Extract audio from YouTube"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if 'youtube.com' in query or 'youtu.be' in query:
                info = ydl.extract_info(query, download=False)
            else:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if 'entries' in info:
                    info = info['entries'][0]
            
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    return {
                        'title': info.get('title', 'Unknown'),
                        'url': f.get('url')
                    }
    except:
        pass
    return None

async def play_next(chat_id):
    """Play next song in queue"""
    await asyncio.sleep(2)
    if chat_id in queues and queues[chat_id]:
        song = queues[chat_id].pop(0)
        playing[chat_id] = song
        await call.change_stream(chat_id, AudioStream(song['url'], AudioParameters()))
        await app.send_message(chat_id, f"▶️ **Now Playing:** {song['title']}\n👤 {song['by']}")
        asyncio.create_task(play_next(chat_id))

# ============ COMMANDS ============
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "**🎵 Music Bot**\n\n"
        "✅ ID Login (Phone/String)\n"
        "✅ Voice Chat Join/Leave\n"
        "✅ YouTube/Recording Play\n\n"
        "Use buttons below 👇",
        reply_markup=main_buttons()
    )

@app.on_message(filters.command("menu"))
async def menu_cmd(client, message):
    await message.reply_text("**🎮 Menu:**", reply_markup=main_buttons())

@app.on_message(filters.command("status"))
async def status_cmd(client, message):
    uid = message.from_user.id
    if uid in users and users[uid].get('logged_in'):
        await message.reply_text(f"✅ **Logged In**\nMethod: {users[uid].get('method', 'unknown')}")
    else:
        await message.reply_text("❌ **Not logged in!**\nUse /login")

# ============ LOGIN SYSTEM ============
@app.on_message(filters.command("login"))
async def login_cmd(client, message):
    uid = message.from_user.id
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply_text(
            "**🔐 Login Methods:**\n\n"
            "`/login phone` - OTP login\n"
            "`/login string <session>` - String session\n\n"
            "Example: `/login +919876543210`"
        )
        return
    
    if args[1] == "phone":
        users[uid] = {"method": "phone", "logged_in": True}
        await message.reply_text("📱 **Send phone number:**\nExample: `+919876543210`")
        
        try:
            resp = await app.wait_for_message(message.chat.id, filters=filters.text & filters.user(uid), timeout=60)
            if resp:
                users[uid]['phone'] = resp.text
                await resp.reply_text(f"✅ **Logged in!**\n📱 {resp.text}\nUse /menu", reply_markup=main_buttons())
        except:
            await message.reply_text("⏰ Timeout!")
    
    elif args[1] == "string" and len(args) >= 3:
        users[uid] = {"method": "string", "session": args[2], "logged_in": True}
        await message.reply_text("✅ **String session saved!**\nUse /menu", reply_markup=main_buttons())

# ============ VOICE/AUDIO PLAY ============
@app.on_message(filters.voice | filters.audio)
async def audio_play(client, message):
    chat_id = message.chat.id
    msg = await message.reply_text("📥 **Downloading...**")
    path = await message.download()
    
    title = message.audio.file_name if message.audio else f"Voice {message.date.strftime('%H:%M')}"
    song = {'title': title, 'url': path, 'by': message.from_user.first_name}
    
    if chat_id in playing and playing[chat_id]:
        if chat_id not in queues:
            queues[chat_id] = []
        queues[chat_id].append(song)
        await msg.edit_text(f"✅ **Added to queue:**\n🎵 {title}")
    else:
        playing[chat_id] = song
        await call.change_stream(chat_id, AudioStream(path, AudioParameters()))
        await msg.edit_text(f"▶️ **Now Playing:**\n🎵 {title}", reply_markup=main_buttons())
        asyncio.create_task(play_next(chat_id))

# ============ CALLBACKS ============
@app.on_callback_query()
async def callback_handler(client, query):
    data = query.data
    chat_id = query.message.chat.id
    uid = query.from_user.id
    name = query.from_user.first_name
    
    await query.answer()
    
    # Voice chat controls
    if data == "join":
        try:
            await call.join_call(chat_id)
            await query.message.edit_text("✅ **Joined Voice Chat!**", reply_markup=main_buttons())
        except Exception as e:
            await query.message.edit_text(f"❌ Error: {e}", reply_markup=main_buttons())
    
    elif data == "leave":
        await call.leave_call(chat_id)
        queues[chat_id] = []
        playing[chat_id] = None
        await query.message.edit_text("✅ **Left Voice Chat!**", reply_markup=main_buttons())
    
    elif data == "pause":
        await call.pause_stream(chat_id)
        await query.message.edit_text("⏸️ **Paused**", reply_markup=main_buttons())
    
    elif data == "resume":
        await call.resume_stream(chat_id)
        await query.message.edit_text("▶️ **Resumed**", reply_markup=main_buttons())
    
    elif data == "skip":
        await call.stop_stream(chat_id)
        await query.message.edit_text("⏭️ **Skipped**", reply_markup=main_buttons())
        await play_next(chat_id)
    
    # Queue
    elif data == "queue":
        if chat_id in queues and queues[chat_id]:
            txt = "**📋 Queue:**\n\n"
            for i, s in enumerate(queues[chat_id][:10], 1):
                txt += f"{i}. {s['title'][:40]}\n"
            await query.message.edit_text(txt, reply_markup=main_buttons())
        else:
            await query.message.edit_text("📋 **Queue empty!**", reply_markup=main_buttons())
    
    # Play music
    elif data == "play":
        await query.message.edit_text("🎵 **Send YouTube link or song name:**\nExample: `Despacito`", reply_markup=main_buttons())
        
        try:
            resp = await app.wait_for_message(chat_id, filters=filters.text & filters.user(uid), timeout=60)
            if resp:
                msg = await resp.reply_text("🔍 **Searching...**")
                audio = await get_audio(resp.text)
                
                if audio:
                    song = {'title': audio['title'], 'url': audio['url'], 'by': name}
                    
                    if chat_id in playing and playing[chat_id]:
                        if chat_id not in queues:
                            queues[chat_id] = []
                        queues[chat_id].append(song)
                        await msg.edit_text(f"✅ **Added:** {audio['title']}", reply_markup=main_buttons())
                    else:
                        playing[chat_id] = song
                        await call.change_stream(chat_id, AudioStream(audio['url'], AudioParameters()))
                        await msg.edit_text(f"▶️ **Playing:** {audio['title']}", reply_markup=main_buttons())
                        asyncio.create_task(play_next(chat_id))
                else:
                    await msg.edit_text("❌ **Not found!**", reply_markup=main_buttons())
        except:
            await query.message.edit_text("⏰ **Timeout!**", reply_markup=main_buttons())
    
    # Login/Logout
    elif data == "login":
        await query.message.edit_text(
            "🔐 **Login:**\n\n"
            "• `/login phone` - OTP login\n"
            "• `/login string <session>` - String login\n\n"
            "Get string: @StringSessionBot",
            reply_markup=main_buttons()
        )
    
    elif data == "logout":
        if uid in users:
            del users[uid]
        await query.message.edit_text("✅ **Logged out!**", reply_markup=main_buttons())

# ============ START ============
async def main():
    print("🚀 Starting bot on Python 3.11.6...")
    await app.start()
    await call.start()
    print("✅ Bot is ready!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
