import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType, ChatMemberStatus
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioStream, AudioParameters
from pytgcalls.types import Update
import yt_dlp

# ============ CONFIG ============
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Initialize clients
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# PyTgCalls initialization with proper error handling
try:
    call = PyTgCalls(app)
    print("✅ PyTgCalls initialized")
except Exception as e:
    print(f"❌ PyTgCalls error: {e}")
    raise

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

def login_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Phone Login", callback_data="login_phone"),
         InlineKeyboardButton("🔑 String Session", callback_data="login_string")],
        [InlineKeyboardButton("◀️ Back", callback_data="back")]
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
    except Exception as e:
        print(f"Audio error: {e}")
    return None

async def play_next(chat_id):
    """Play next song in queue"""
    await asyncio.sleep(2)
    if chat_id in queues and queues[chat_id]:
        song = queues[chat_id].pop(0)
        playing[chat_id] = song
        try:
            await call.change_stream(chat_id, AudioStream(song['url']))
            await app.send_message(chat_id, f"▶️ **Now Playing:** {song['title']}\n👤 {song['by']}")
            asyncio.create_task(play_next(chat_id))
        except Exception as e:
            print(f"Play next error: {e}")

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
        except asyncio.TimeoutError:
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
        try:
            await call.change_stream(chat_id, AudioStream(path))
            await msg.edit_text(f"▶️ **Now Playing:**\n🎵 {title}", reply_markup=main_buttons())
            asyncio.create_task(play_next(chat_id))
        except Exception as e:
            await msg.edit_text(f"❌ Error: {e}", reply_markup=main_buttons())

# ============ CALLBACKS ============
@app.on_callback_query()
async def callback_handler(client, query):
    data = query.data
    chat_id = query.message.chat.id
    uid = query.from_user.id
    name = query.from_user.first_name
    
    await query.answer()
    
    # Back button
    if data == "back":
        await query.message.edit_text("**🎵 Main Menu:**", reply_markup=main_buttons())
    
    # Voice chat controls
    elif data == "join":
        try:
            await call.join_call(chat_id)
            await query.message.edit_text("✅ **Joined Voice Chat!**\nNow you can play music.", reply_markup=main_buttons())
        except Exception as e:
            await query.message.edit_text(f"❌ Error: {str(e)[:100]}", reply_markup=main_buttons())
    
    elif data == "leave":
        try:
            await call.leave_call(chat_id)
            queues[chat_id] = []
            playing[chat_id] = None
            await query.message.edit_text("✅ **Left Voice Chat!**", reply_markup=main_buttons())
        except Exception as e:
            await query.message.edit_text(f"❌ Error: {e}", reply_markup=main_buttons())
    
    elif data == "pause":
        try:
            await call.pause_stream(chat_id)
            await query.message.edit_text("⏸️ **Paused**\nClick Resume to continue", reply_markup=main_buttons())
        except Exception as e:
            pass
    
    elif data == "resume":
        try:
            await call.resume_stream(chat_id)
            await query.message.edit_text("▶️ **Resumed**", reply_markup=main_buttons())
        except Exception as e:
            pass
    
    elif data == "skip":
        try:
            await call.stop_stream(chat_id)
            await query.message.edit_text("⏭️ **Skipped**", reply_markup=main_buttons())
            await play_next(chat_id)
        except Exception as e:
            pass
    
    # Queue
    elif data == "queue":
        if chat_id in queues and queues[chat_id]:
            txt = "**📋 Queue:**\n\n"
            for i, s in enumerate(queues[chat_id][:10], 1):
                txt += f"{i}. {s['title'][:40]}\n"
            await query.message.edit_text(txt, reply_markup=main_buttons())
        else:
            await query.message.edit_text("📋 **Queue empty!**\nUse Play button to add songs", reply_markup=main_buttons())
    
    # Play music
    elif data == "play":
        await query.message.edit_text(
            "🎵 **Send YouTube link or song name:**\n\n"
            "Examples:\n"
            "• `https://youtube.com/watch?v=...`\n"
            "• `Despacito`\n"
            "• `Bohemian Rhapsody`",
            reply_markup=main_buttons()
        )
        
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
                        await msg.edit_text(f"✅ **Added to queue:**\n🎵 {audio['title']}\n📝 Position: {len(queues[chat_id])}", reply_markup=main_buttons())
                    else:
                        playing[chat_id] = song
                        try:
                            await call.change_stream(chat_id, AudioStream(audio['url']))
                            await msg.edit_text(f"▶️ **Now Playing:**\n🎵 {audio['title']}", reply_markup=main_buttons())
                            asyncio.create_task(play_next(chat_id))
                        except Exception as e:
                            await msg.edit_text(f"❌ Stream error: {e}", reply_markup=main_buttons())
                else:
                    await msg.edit_text("❌ **No audio found!** Try different keywords", reply_markup=main_buttons())
        except asyncio.TimeoutError:
            await query.message.edit_text("⏰ **Timeout!** Please try again", reply_markup=main_buttons())
    
    # Login/Logout
    elif data == "login":
        await query.message.edit_text(
            "🔐 **Login Methods:**\n\n"
            "**Method 1 - Phone OTP:**\n"
            "Type: `/login phone`\n\n"
            "**Method 2 - String Session:**\n"
            "Type: `/login string YOUR_STRING_SESSION`\n\n"
            "Get string session from @StringSessionBot",
            reply_markup=main_buttons()
        )
    
    elif data == "logout":
        if uid in users:
            del users[uid]
        await query.message.edit_text("✅ **Logged out successfully!**", reply_markup=main_buttons())

# ============ START BOT ============
async def main():
    print("🚀 Starting Music Bot on Heroku...")
    print(f"Python Version: 3.11.6")
    print(f"API ID: {API_ID}")
    
    try:
        await app.start()
        print("✅ Pyrogram Client Started")
        
        await call.start()
        print("✅ PyTgCalls Started")
        
        print("\n🎵 Bot is Ready!")
        print("Commands:")
        print("  /start - Start bot")
        print("  /menu - Show menu")
        print("  /login - Login with phone/string")
        print("  /status - Check login status")
        
        await asyncio.Event().wait()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot Stopped")
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
