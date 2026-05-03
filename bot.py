import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioStream, AudioParameters
import yt_dlp

# ============ SETUP ============
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call = PyTgCalls(app)

# Storage
queues = {}
playing = {}
users = {}  # {user_id: {"phone": "", "logged_in": True}}

# ============ BUTTONS ============
def buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Play", callback_data="play"),
         InlineKeyboardButton("📋 Queue", callback_data="queue")],
        [InlineKeyboardButton("🔊 Join", callback_data="join"),
         InlineKeyboardButton("⏹️ Leave", callback_data="leave")],
        [InlineKeyboardButton("⏸️ Pause", callback_data="pause"),
         InlineKeyboardButton("▶️ Resume", callback_data="resume"),
         InlineKeyboardButton("⏭️ Skip", callback_data="skip")],
        [InlineKeyboardButton("🔑 Login", callback_data="login"),
         InlineKeyboardButton("🚪 Logout", callback_data="logout")]
    ])

# ============ HELPERS ============
async def get_audio(query):
    """YouTube se audio nikalta hai"""
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        if "youtube.com" in query or "youtu.be" in query:
            info = ydl.extract_info(query, download=False)
        else:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            info = info['entries'][0]
        
        # Audio URL find karo
        for f in info['formats']:
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                return {'title': info['title'], 'url': f['url']}
    return None

async def play_next(chat_id):
    """Queue se next song play karega"""
    await asyncio.sleep(2)
    if chat_id in queues and queues[chat_id]:
        song = queues[chat_id].pop(0)
        playing[chat_id] = song
        await call.change_stream(chat_id, AudioStream(song['url'], AudioParameters()))
        await app.send_message(chat_id, f"▶️ **Now Playing:** {song['title']}\n👤 {song['by']}")
        asyncio.create_task(play_next(chat_id))

# ============ COMMANDS ============
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "🎵 **Music Bot**\n✅ ID Login\n✅ Voice Chat\n✅ YouTube/Recording\n\nUse Buttons 👇",
        reply_markup=buttons()
    )

# ============ BUTTON CALLBACKS ============
@app.on_callback_query()
async def callbacks(client, query):
    data = query.data
    chat_id = query.message.chat.id
    user = query.from_user.id
    
    # ===== VOICE CHAT CONTROLS =====
    if data == "join":
        try:
            await call.join_call(chat_id)
            await query.message.edit_text("✅ **Joined Voice Chat!**", reply_markup=buttons())
        except Exception as e:
            await query.message.edit_text(f"❌ Error: {e}", reply_markup=buttons())
    
    elif data == "leave":
        await call.leave_call(chat_id)
        queues[chat_id] = []
        playing[chat_id] = None
        await query.message.edit_text("✅ **Left Voice Chat!**", reply_markup=buttons())
    
    elif data == "pause":
        await call.pause_stream(chat_id)
        await query.answer("⏸️ Paused")
    
    elif data == "resume":
        await call.resume_stream(chat_id)
        await query.answer("▶️ Resumed")
    
    elif data == "skip":
        await call.stop_stream(chat_id)
        await query.answer("⏭️ Skipped")
        await play_next(chat_id)
    
    # ===== QUEUE =====
    elif data == "queue":
        if chat_id in queues and queues[chat_id]:
            txt = "**📋 Queue:**\n"
            for i, s in enumerate(queues[chat_id][:5], 1):
                txt += f"{i}. {s['title'][:40]}\n"
            await query.message.edit_text(txt, reply_markup=buttons())
        else:
            await query.message.edit_text("📋 **Queue Empty!**", reply_markup=buttons())
    
    # ===== PLAY MUSIC =====
    elif data == "play":
        await query.message.edit_text("🎵 **Send YouTube Link or Song Name:**", reply_markup=buttons())
        
        # Wait for user response
        resp = await app.wait_for_message(chat_id, filters=filters.text & filters.user(user), timeout=60)
        if resp:
            msg = await resp.reply_text("🔍 **Searching...**")
            audio = await get_audio(resp.text)
            
            if audio:
                song = {'title': audio['title'], 'url': audio['url'], 'by': query.from_user.first_name}
                
                # Agar kuch play ho raha hai to queue mein daalo
                if chat_id in playing and playing[chat_id]:
                    if chat_id not in queues:
                        queues[chat_id] = []
                    queues[chat_id].append(song)
                    await msg.edit_text(f"✅ **Added to Queue:**\n🎵 {audio['title']}", reply_markup=buttons())
                else:
                    # Direct play karo
                    playing[chat_id] = song
                    await call.change_stream(chat_id, AudioStream(audio['url'], AudioParameters()))
                    await msg.edit_text(f"▶️ **Now Playing:**\n🎵 {audio['title']}", reply_markup=buttons())
                    asyncio.create_task(play_next(chat_id))
            else:
                await msg.edit_text("❌ **No audio found!**", reply_markup=buttons())
    
    # ===== LOGIN SYSTEM =====
    elif data == "login":
        await query.message.edit_text(
            "🔐 **Login Options:**\n\n"
            "1️⃣ **Phone Login:** Send `/login phone`\n"
            "2️⃣ **String Session:** Send `/login string <session>`\n\n"
            "Example:\n`/login +919876543210`",
            reply_markup=buttons()
        )
    
    elif data == "logout":
        if user in users:
            del users[user]
        await query.message.edit_text("✅ **Logged Out!**", reply_markup=buttons())
    
    await query.answer()

# ============ LOGIN COMMANDS ============
@app.on_message(filters.command("login"))
async def login_command(client, message):
    user = message.from_user.id
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply_text("❌ **Usage:**\n`/login phone` - For OTP login\n`/login string <session>` - For string session")
        return
    
    if args[1] == "phone":
        users[user] = {"method": "phone", "status": "waiting_otp"}
        await message.reply_text("📱 **Send your phone number with country code:**\nExample: `+919876543210`")
        
        # Wait for phone number
        resp = await app.wait_for_message(message.chat.id, filters=filters.text & filters.user(user), timeout=60)
        if resp:
            users[user]["phone"] = resp.text
            users[user]["logged_in"] = True
            await resp.reply_text(f"✅ **Logged in with:** {resp.text}\nUse /menu to start bot", reply_markup=buttons())
    
    elif args[1] == "string" and len(args) >= 3:
        users[user] = {"method": "string", "session": args[2], "logged_in": True}
        await message.reply_text("✅ **String session saved!**\nUse /menu to start bot", reply_markup=buttons())
    
    else:
        await message.reply_text("❌ **Invalid format!**")

# ============ RECORDING PLAY (Voice Message ya Audio File) ============
@app.on_message(filters.voice | filters.audio)
async def play_recording(client, message):
    chat_id = message.chat.id
    
    # Download audio
    file_path = await message.download()
    
    song = {
        'title': message.voice.file_name if message.voice else message.audio.file_name,
        'url': file_path,
        'by': message.from_user.first_name
    }
    
    if chat_id in playing and playing[chat_id]:
        if chat_id not in queues:
            queues[chat_id] = []
        queues[chat_id].append(song)
        await message.reply_text(f"✅ **Added to Queue:**\n🎵 {song['title']}", reply_markup=buttons())
    else:
        playing[chat_id] = song
        await call.change_stream(chat_id, AudioStream(file_path, AudioParameters()))
        await message.reply_text(f"▶️ **Now Playing:**\n🎵 {song['title']}", reply_markup=buttons())
        asyncio.create_task(play_next(chat_id))

# ============ CHECK LOGIN STATUS ============
@app.on_message(filters.command("status"))
async def status_command(client, message):
    user = message.from_user.id
    if user in users and users[user].get("logged_in"):
        await message.reply_text(f"✅ **Logged In!**\nMethod: {users[user].get('method', 'unknown')}", reply_markup=buttons())
    else:
        await message.reply_text("❌ **Not logged in!**\nUse /login command", reply_markup=buttons())

@app.on_message(filters.command("menu"))
async def menu_command(client, message):
    await message.reply_text("🎮 **Menu:**", reply_markup=buttons())

# ============ RUN BOT ============
async def main():
    print("🚀 Bot Starting...")
    await app.start()
    await call.start()
    print("✅ Bot Ready! Use @ your bot on Telegram")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
